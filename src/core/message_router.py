#!/usr/bin/env python3
"""
消息路由模块
负责处理消息的路由逻辑，包括白名单检查、@检测、命令识别等
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Optional, Any, Callable, Tuple, Awaitable, List, Union
from src.utils import config
from .cq_code_parser import extract_plain_text, extract_file_info, extract_quoted_message_id
from .file_handler import FileHandler
from .message_queue import MessageQueueProcessor
from .command_system import CommandSystem

logger = logging.getLogger(__name__)


class MessageRouter:
    """消息路由器"""
    
    def __init__(
        self,
        file_handler: FileHandler,
        message_queue_processor: MessageQueueProcessor,
        bot_qq_id: Optional[int],
        command_system: Optional[CommandSystem],
        send_reply_callback: Callable[[str, Optional[int], Optional[int], str], Awaitable[None]],
        get_quoted_message_callback: Callable[[Union[int, str]], Awaitable[Optional[Dict[str, Any]]]],
        opencode_available: bool = True
    ):
        """初始化消息路由器
        
        Args:
            file_handler: 文件处理器实例
            message_queue_processor: 消息队列处理器实例
            bot_qq_id: 机器人 QQ 号
            command_system: 命令系统实例
            send_reply_callback: 发送回复的回调函数，参数：(message_type, user_id, group_id, message)
            get_quoted_message_callback: 获取引用消息完整数据的回调函数，参数：(message_id) -> 消息数据字典，message_id 可以是整数或字符串
            opencode_available: OpenCode 集成是否可用，默认为 True
        """
        self.file_handler = file_handler
        self.message_queue_processor = message_queue_processor
        self.bot_qq_id = bot_qq_id
        self.command_system = command_system
        self.send_reply_callback = send_reply_callback
        self.get_quoted_message_callback = get_quoted_message_callback
        self.opencode_available = opencode_available
    
    def is_mentioning_bot(self, raw_message: str) -> bool:
        """检查消息是否@了机器人"""
        if not raw_message:
            logger.debug(f"is_mentioning_bot: raw_message为空")
            return False
        
        if not self.bot_qq_id:
            logger.debug(f"is_mentioning_bot: bot_qq_id为空, raw_message={raw_message[:50]}")
            return False
        
        # 检查是否包含@机器人的CQ码
        # 支持多种格式：
        # 1. [CQ:at,qq=123456]
        # 2. [CQ:at, qq=123456]（逗号后有空格）
        # 3. [CQ:at,qq=123456,name=xxx]（带额外参数）
        # 4. [CQ:at, qq=123456, name=xxx]
        
        # 更灵活的模式：查找[CQ:at后跟qq=bot_qq_id
        # 使用非贪婪匹配，允许中间有其他字符
        mention_pattern = f'\\[CQ:at[^\\]]*qq={self.bot_qq_id}[^\\]]*\\]'
        
        # 调试：打印原始消息和模式
        logger.debug(f"is_mentioning_bot: 检查 bot_qq_id={self.bot_qq_id}")
        logger.debug(f"is_mentioning_bot: raw_message长度={len(raw_message)}, 内容={repr(raw_message)}")
        logger.debug(f"is_mentioning_bot: 灵活模式={mention_pattern}")
        
        match = re.search(mention_pattern, raw_message)
        is_match = bool(match)
        
        if match:
            logger.debug(f"is_mentioning_bot: 匹配成功, match={match.group()}")
        else:
            logger.debug(f"is_mentioning_bot: 无匹配")
        
        logger.debug(f"is_mentioning_bot: 最终结果={is_match}")
        return is_match
    
    def should_process_message(self, message_type: str, user_id: Optional[int], 
                              group_id: Optional[int], raw_message: str) -> bool:
        """判断是否应该处理此消息"""
        logger.debug(f"should_process_message: 开始检查 type={message_type}, user={user_id}, group={group_id}")
        
        # 私聊消息：只处理白名单用户
        if message_type == 'private':
            logger.debug(f"should_process_message: 私聊消息检查, user={user_id}, whitelist={config.QQ_USER_WHITELIST}")
            if user_id in config.QQ_USER_WHITELIST:
                logger.debug(f"处理白名单用户私聊消息: QQ={user_id}, raw_message={raw_message}")
                return True
            else:
                logger.debug(f"忽略非白名单用户私聊消息: QQ={user_id}")
                return False
        
        # 群聊消息：只处理白名单群中白名单用户@机器人的消息
        elif message_type == 'group':
            logger.debug(f"should_process_message: 群聊消息检查, group={group_id}, whitelist={config.GROUP_WHITELIST}")
            # 首先检查群聊白名单
            if group_id not in config.GROUP_WHITELIST:
                logger.debug(f"忽略非白名单群消息: 群={group_id}, 用户={user_id}")
                return False
            
            # 检查用户是否在白名单中
            if user_id not in config.QQ_USER_WHITELIST:
                logger.debug(f"忽略非白名单用户在群聊中的消息: 群={group_id}, 用户={user_id}")
                return False
            
            # 检查是否@机器人
            logger.debug(f"should_process_message: 群和用户都在白名单中，检查@状态")
            is_mentioning = self.is_mentioning_bot(raw_message)
            logger.debug(f"群聊消息检查: 群={group_id}, 用户={user_id}, raw_message={raw_message}, is_mentioning={is_mentioning}, bot_qq_id={self.bot_qq_id}, ENABLE_AT_MENTION={config.ENABLE_AT_MENTION}")
            
            if config.ENABLE_AT_MENTION and is_mentioning:
                logger.debug(f"处理白名单群中白名单用户@机器人消息: 群={group_id}, 用户={user_id}, raw_message={raw_message}")
                return True
            else:
                logger.debug(f"忽略未@机器人的群聊消息: 群={group_id}, 用户={user_id}")
                return False
        
        # 其他类型的消息（如notice, request等）不处理
        else:
            logger.debug(f"should_process_message: 未知消息类型: {message_type}")
            return False
    
    def is_command(self, plain_text: str) -> bool:
        """检查消息是否为命令"""
        if not plain_text:
            return False
        
        # 优先使用命令系统（如果可用）
        if self.command_system:
            return self.command_system.is_command(plain_text)
        
        # 回退到原始实现
        return plain_text.strip().startswith(config.OPENCODE_COMMAND_PREFIX)
    
    def extract_command(self, message: str) -> Tuple[str, str]:
        """从消息中提取命令和参数"""
        if not self.is_command(message):
            return "", message
        
        # 优先使用命令系统（如果可用）
        if self.command_system:
            return self.command_system.extract_command(message)
        
        # 回退到原始实现
        message = message.strip()
        # 移除命令前缀
        if message.startswith(config.OPENCODE_COMMAND_PREFIX):
            message = message[len(config.OPENCODE_COMMAND_PREFIX):]
        
        # 分割命令和参数
        parts = message.split(maxsplit=1)
        if len(parts) == 0:
            return "", ""
        elif len(parts) == 1:
            return parts[0], ""
        else:
            return parts[0], parts[1]
    
    async def handle_command(self, message_type: str, group_id: Optional[int], 
                           user_id: Optional[int], plain_text: str) -> None:
        """处理命令"""
        # 检查OpenCode集成是否可用
        if not self.opencode_available:
            reply = "OpenCode集成当前不可用，无法处理命令。"
            await self.send_reply_callback(message_type, group_id, user_id, reply)
            return
        
        # 提取命令和参数
        command, args = self.extract_command(plain_text)
        if not command:
            logger.warning(f"无法提取命令: {plain_text}")
            return
        
        logger.info(f"处理命令: {command}, 参数: {args}, 用户: {user_id}")
        
        # 使用命令系统处理命令
        if self.command_system:
            success = await self.command_system.handle_command(
                command, message_type, group_id, user_id, args
            )
            if success:
                return
            # 如果命令系统处理失败（未知命令），返回错误信息
            else:
                reply = f"未知命令: {command}\n使用 /help 查看可用命令。"
                await self.send_reply_callback(message_type, group_id, user_id, reply)
        else:
            logger.error("命令系统未初始化，无法处理命令")
            reply = "命令系统暂时不可用，请稍后重试。"
            await self.send_reply_callback(message_type, group_id, user_id, reply)
    
    async def handle_auto_reply(self, message_type: str, group_id: Optional[int], 
                               user_id: Optional[int], plain_text: str) -> None:
        """处理自动回复（使用纯文本）"""
        if not plain_text:
            return
        
        # 对于群聊消息，只处理@机器人的消息（额外安全检查）
        if message_type == 'group' and group_id:
            # 这里无法直接访问raw_message，但我们可以依赖should_process_message的检查
            # 如果should_process_message正确工作，只有@消息会到达这里
            # 为了安全，我们记录一条警告
            logger.debug(f"handle_auto_reply: 处理群聊消息，依赖should_process_message的过滤")
        
        # 检查配置中的关键词（plain_text已经是小写）
        for keyword, replies in config.AUTO_REPLY_KEYWORDS.items():
            keyword_lower = keyword.lower()
            if keyword_lower in plain_text:
                # 随机选择一个回复（简单实现：取第一个）
                reply = replies[0] if replies else f"你说了: {keyword}"
                
                # 根据消息类型发送回复
                await self.send_reply_callback(message_type, group_id, user_id, reply)
                
                logger.info(f"自动回复: {keyword} -> {reply[:50]}...")
                return
        
        # 如果没有匹配的关键词，可以添加其他逻辑
        if config.DEBUG:
            logger.debug(f"未匹配关键词的消息: {plain_text}")
    
    async def _process_files_in_records(self, records: List[Dict], message_type: str, 
                                       group_id: Optional[int], user_id: Optional[int]) -> str:
        """从records中提取文件信息并下载文件
        
        Args:
            records: raw.records列表，包含被引用消息的详细信息
            message_type: 消息类型（private/group）
            group_id: 群号（如果是群消息）
            user_id: 发送文件的用户QQ号
            
        Returns:
            包含文件信息的文本消息
        """
        if not records or not isinstance(records, list):
            return ""
        
        file_messages = []
        
        for record in records:
            if not isinstance(record, dict):
                continue
                
            # 检查record中的elements字段
            elements = record.get('elements', [])
            if not isinstance(elements, list):
                continue
                
            for element in elements:
                if not isinstance(element, dict):
                    continue
                    
                # 检查文件元素
                file_element = element.get('fileElement')
                if isinstance(file_element, dict):
                    file_name = file_element.get('fileName') or file_element.get('file_name')
                    file_size = file_element.get('fileSize') or file_element.get('file_size')
                    file_uuid = file_element.get('fileUuid')
                    file_sub_id = file_element.get('fileSubId')
                    
                    if file_name:
                        # 构建文件信息字典，类似于extract_file_info返回的结构
                        file_info = {
                            'type': 'file',
                            'filename': file_name,
                            'file_size': str(file_size) if file_size else '0',
                            'params': {}
                        }
                        
                        # 如果有file_uuid，可以尝试下载
                        # 注意：引用消息中的文件可能无法直接下载，因为需要特殊的API调用
                        # 我们将file_uuid作为file_id尝试下载
                        if file_uuid:
                            # 构建文件信息字典，添加file_id字段
                            file_info['file_id'] = file_uuid
                            if file_sub_id:
                                # 将file_sub_id也添加到params中，以备后用
                                file_info['params']['file_sub_id'] = file_sub_id
                            
                            # 尝试下载文件
                            try:
                                local_path = await self.file_handler.download_file(
                                    file_info, group_id, user_id
                                )
                                if local_path:
                                    file_messages.append(f"[文件: {file_name}] (已下载到: {local_path})")
                                else:
                                    file_messages.append(f"[文件: {file_name}] (下载失败，可能文件已过期或无权限)")
                            except Exception as e:
                                logger.error(f"下载引用文件失败: {e}")
                                file_messages.append(f"[文件: {file_name}] (下载错误: {str(e)[:50]}...)")
                        else:
                            file_messages.append(f"[文件: {file_name}] (大小: {file_size}字节，无文件ID无法下载)")
                
                # 图片消息
                pic_element = element.get('picElement')
                if isinstance(pic_element, dict):
                    # 提取图片信息
                    file_name = pic_element.get('fileName') or pic_element.get('file_name') or f"image_{pic_element.get('md5HexStr', 'unknown')}.jpg"
                    file_size = pic_element.get('fileSize') or pic_element.get('file_size')
                    
                    # 尝试使用 originImageUrl（如果有 rkey 参数）
                    origin_image_url = pic_element.get('originImageUrl') or pic_element.get('origin_image_url')
                    
                    # 构建图片信息字典
                    image_info = {
                        'type': 'image',
                        'filename': file_name,
                        'file_size': str(file_size) if file_size else '0',
                        'params': {}
                    }
                    
                    # 如果 originImageUrl 包含 rkey，直接使用 URL 下载
                    if origin_image_url and 'rkey=' in origin_image_url:
                        if origin_image_url.startswith('/'):
                            origin_image_url = f'https://multimedia.nt.qq.com.cn{origin_image_url}'
                        image_info['url'] = origin_image_url
                        logger.info(f"使用带 rkey 的 URL 下载图片：{file_name}")
                    # 否则使用 get_image API
                    else:
                        logger.info(f"使用 get_image API 下载图片：{file_name}")
                    
                    # 下载图片
                    try:
                        local_path = await self.file_handler.download_file(
                            image_info, group_id, user_id
                        )
                        if local_path:
                            file_messages.append(f"[图片：{file_name}] (已下载到：{local_path})")
                        else:
                            file_messages.append(f"[图片：{file_name}] (下载失败，可能图片已过期或无权限)")
                    except Exception as e:
                        logger.error(f"下载引用图片失败：{e}")
                        file_messages.append(f"[图片：{file_name}] (下载错误：{str(e)[:50]}...)")
                
                # 语音消息
                ptt_element = element.get('pttElement')
                if isinstance(ptt_element, dict):
                    file_messages.append("[语音消息]")
        
        if file_messages:
            return " ".join(file_messages)
        else:
            return ""
    
    async def route_message(self, message: Dict) -> None:
        """路由消息（原handle_message_reply方法）"""
        message_type = message.get('message_type')
        group_id = message.get('group_id')
        user_id = message.get('user_id')
        raw_message = message.get('raw_message', '').strip()
        
        # 提取用户信息
        sender = message.get('sender', {})
        user_name = sender.get('card') or sender.get('nickname') or f"QQ用户_{user_id}"
        
        # 只处理私聊和群聊消息
        if message_type not in ['private', 'group']:
            return
        
        # 检查是否应该处理此消息（白名单或@机器人）
        should_process = self.should_process_message(message_type, user_id, group_id, raw_message)
        logger.debug(f"route_message: type={message_type}, user={user_id}, group={group_id}, raw='{raw_message}', should_process={should_process}")
        
        if not should_process:
            logger.debug(f"忽略消息: type={message_type}, user={user_id}, group={group_id}")
            return
        
        # 先回复确认消息（已关闭）
        try:
            if message_type == 'private' and user_id:
                # 私聊回复（已关闭）
                # await self.send_reply_callback(message_type, group_id, user_id, "消息已收到")
                logger.info(f"私聊确认回复已关闭，用户 {user_id}")
            elif message_type == 'group' and group_id and user_id:
                # 群聊回复，@用户（已关闭）
                at_user = f"[CQ:at,qq={user_id}]"
                reply_msg = f"{at_user} 消息已收到"
                # await self.send_reply_callback(message_type, group_id, user_id, reply_msg)
                logger.info(f"群聊确认回复已关闭 @用户 {user_id}")
        except Exception as e:
            logger.error(f"发送确认回复失败: {e}")
            # 继续处理消息，不因确认回复失败而中断
        
        # 处理引用消息
        quoted_msg_id = extract_quoted_message_id(message)
        if quoted_msg_id:
            logger.info(f"收到引用消息，引用 ID: {quoted_msg_id}")
            
            # 尝试将消息ID转换为整数（如果可能），因为 OneBot API 通常期望整数
            # 但我们的回调函数现在支持字符串和整数两种类型
            try:
                # 先尝试转换为整数
                quoted_msg_id_for_api = int(quoted_msg_id)
                logger.debug(f"消息ID转换为整数: {quoted_msg_id} -> {quoted_msg_id_for_api}")
            except (ValueError, TypeError):
                # 如果无法转换，保持为字符串
                quoted_msg_id_for_api = quoted_msg_id
                logger.debug(f"消息ID保持为字符串: {quoted_msg_id}")
            
            quoted_content = None
            quoted_files_info = None
            
            # 使用 get_msg API 获取完整消息数据
            quoted_message_data = await self.get_quoted_message_callback(quoted_msg_id_for_api)
            
            if quoted_message_data:
                # 提取文本内容
                message_array = quoted_message_data.get("message", [])
                if isinstance(message_array, list):
                    texts = []
                    for segment in message_array:
                        if isinstance(segment, dict) and segment.get("type") == "text":
                            text = segment.get("data", {}).get("text", "")
                            if text:
                                texts.append(text)
                    quoted_content = " ".join(texts).strip() if texts else None
                    
                    # 处理文件/图片/合并转发
                    raw_msg = quoted_message_data.get("raw_message", "")
                    if raw_msg:
                        file_info_list = extract_file_info(raw_msg)
                        if file_info_list:
                            processed_files = []
                            for file_info in file_info_list:
                                file_type = file_info.get("type")
                                filename = file_info.get("filename", "unknown")
                                
                                # forward 类型特殊处理：使用 get_forward_msg API
                                if file_type == "forward":
                                    forward_id = file_info.get("file_id", "")
                                    http_client = getattr(self.file_handler, 'http_client', None)
                                    if forward_id and http_client:
                                        try:
                                            forward_data = await http_client.get_forward_msg(forward_id)
                                            if forward_data:
                                                messages = forward_data.get("messages", [])
                                                # 解析消息内容
                                                parsed_messages = []
                                                for msg in messages:
                                                    sender = msg.get("sender", {})
                                                    nickname = sender.get("nickname", "未知用户")
                                                    message = msg.get("message", [])
                                                    raw_msg_content = msg.get("raw_message", "")
                                                    
                                                    if isinstance(message, list):
                                                        text_parts = []
                                                        for item in message:
                                                            if isinstance(item, dict):
                                                                item_type = item.get("type", "")
                                                                if item_type == "text":
                                                                    text_parts.append(item.get("data", {}).get("text", ""))
                                                                elif item_type == "image":
                                                                    img_file = item.get("data", {}).get("file", "图片")
                                                                    text_parts.append(f"[图片: {img_file}]")
                                                                elif item_type == "file":
                                                                    file_name = item.get("data", {}).get("file", "文件")
                                                                    text_parts.append(f"[文件: {file_name} (合并转发消息暂时无法下载文件，请单独发送文件)]")
                                                            elif isinstance(item, str):
                                                                text_parts.append(item)
                                                        text_content = "".join(text_parts)
                                                    else:
                                                        text_content = raw_msg_content
                                                    
                                                    if text_content.strip():
                                                        parsed_messages.append(f"{nickname}: {text_content.strip()}")
                                                
                                                if parsed_messages:
                                                    # 显示所有消息内容，不省略
                                                    forward_summary = " | ".join(parsed_messages)
                                                    processed_files.append(f"[forward: {forward_summary}]")
                                                else:
                                                    processed_files.append(f"[forward: {len(messages)}条消息]")
                                                logger.info(f"引用消息中的合并转发消息解析成功: {len(messages)}条")
                                            else:
                                                processed_files.append(f"[forward: {filename}] (解析失败)")
                                        except Exception as e:
                                            logger.warning(f"获取引用消息中的合并转发失败: {e}")
                                            processed_files.append(f"[forward: {filename}] (解析失败)")
                                    else:
                                        processed_files.append(f"[forward: {filename}]")
                                else:
                                    # 其他类型使用 download_file
                                    local_path = await self.file_handler.download_file(
                                        file_info, group_id, user_id
                                    )
                                    
                                    if local_path:
                                        processed_files.append(f"[{file_type}: {filename}] (已下载到：{local_path})")
                                    else:
                                        processed_files.append(f"[{file_type}: {filename}] (下载失败)")
                            
                            quoted_files_info = " ".join(processed_files)
                    
                    if not quoted_content:
                        # 如果有附件（forward/image/file等），不显示 [非文本消息]
                        if not file_info_list:
                            quoted_content = "[非文本消息]"
                else:
                    logger.warning(f"无法获取引用消息：{quoted_msg_id}")
                    quoted_content = "[引用消息已过期或无法获取]"
            else:
                quoted_content = "[引用消息 ID 无效]"
            
            # 构建前缀
            quoted_parts = []
            
            # 检查是否包含 forward 类型
            has_forward_in_files = quoted_files_info and "[forward:" in quoted_files_info
            
            if has_forward_in_files:
                # forward 类型直接显示内容，不显示"引用附件"标签
                # 移除 [forward: ...] 的外层包装
                forward_content = quoted_files_info.replace("[forward: ", "").rstrip("]")
                quoted_parts.append(f"[引用合并转发消息：{forward_content}]")
            elif quoted_files_info:
                # 其他附件类型，检查是否有文本内容
                if quoted_content:
                    quoted_parts.append(f"[引用消息：{quoted_content}]")
                quoted_parts.append(f"[引用附件：{quoted_files_info}]")
            elif quoted_content:
                # 只有文本内容
                quoted_parts.append(f"[引用消息：{quoted_content}]")
            
            if quoted_parts:
                quoted_prefix = " ".join(quoted_parts) + " "
                raw_message = quoted_prefix + raw_message
        
        # 检查消息是否包含文件
        file_info_list = extract_file_info(raw_message)
        has_files = len(file_info_list) > 0
        
        # 处理特殊消息类型（如合并转发、音乐、分享等）
        special_messages = []
        remaining_file_info = []
        for file_info in file_info_list:
            msg_type = file_info.get("type")
            params = file_info.get("params", {})
            
            if msg_type == "forward":
                forward_id = file_info.get("file_id", "unknown")
                # 将forward消息加入remaining_file_info，以便在process_file_message中处理XML内容
                remaining_file_info.append(file_info)
                logger.info(f"检测到合并转发消息: {forward_id}，将进行详细处理")
            elif msg_type == "music":
                music_type = params.get("type", "unknown")
                music_id = params.get("id", "unknown")
                title = params.get("title", "未知音乐")
                special_messages.append(f"用户分享了一首音乐: {title} (类型: {music_type}, ID: {music_id})")
                logger.info(f"检测到音乐分享: {title}")
            elif msg_type == "share":
                title = params.get("title", "未知链接")
                url = params.get("url", "")
                content = params.get("content", "")
                if url:
                    special_messages.append(f"用户分享了一个链接: {title} (URL: {url})")
                else:
                    special_messages.append(f"用户分享了一个链接: {title}")
                logger.info(f"检测到链接分享: {title}")
            elif msg_type == "contact":
                contact_type = params.get("type", "unknown")
                contact_id = params.get("id", "unknown")
                name = params.get("name", "未知联系人")
                special_messages.append(f"用户分享了一个联系人: {name} (类型: {contact_type}, ID: {contact_id})")
                logger.info(f"检测到联系人分享: {name}")
            elif msg_type == "location":
                lat = params.get("lat", "未知")
                lon = params.get("lon", "未知")
                title = params.get("title", "位置分享")
                content = params.get("content", "")
                special_messages.append(f"用户分享了一个位置: {title} (坐标: {lat}, {lon})")
                logger.info(f"检测到位置分享: {title}")
            elif msg_type == "shake":
                special_messages.append("用户发送了一个窗口抖动（戳一戳）")
                logger.info("检测到窗口抖动消息")
            elif msg_type == "poke":
                # poke类型通常通过通知事件处理，但有时也可能作为CQ码出现
                poke_type = params.get("type", "unknown")
                poke_id = params.get("id", "unknown")
                special_messages.append(f"用户发送了一个戳一戳 (类型: {poke_type}, ID: {poke_id})")
                logger.info(f"检测到戳一戳消息: {poke_type}")
            else:
                remaining_file_info.append(file_info)
        
        # 处理文件消息（如果有文件）
        processed_text = None
        if remaining_file_info:
            logger.info(f"准备处理文件消息，forward消息数量: {len([fi for fi in remaining_file_info if fi.get('type') == 'forward'])}")
            logger.info(f"传递给process_file_message的message参数类型: {type(message)}, 包含的键: {list(message.keys())}")
            processed_text = await self.file_handler.process_file_message(raw_message, message_type, group_id, user_id, message)
        
        # 如果有特殊消息，将其添加到处理后的文本中
        if special_messages:
            if processed_text:
                processed_text = " ".join(special_messages) + " " + processed_text
            else:
                processed_text = " ".join(special_messages)
        
        # 提取纯文本消息（去除CQ码）
        original_plain_text = extract_plain_text(raw_message).strip()
        plain_text_lower = original_plain_text.lower()
        
        # 如果有处理过的文件消息，使用处理后的文本
        if processed_text:
            original_plain_text = processed_text.strip()
            plain_text_lower = original_plain_text.lower()
        
        # 检查是否为命令
        if self.is_command(original_plain_text):
            await self.handle_command(message_type, group_id, user_id, original_plain_text)
            return
        
        # 处理特殊回复：私聊hello回复helloword
        if (message_type == 'private' and 
            config.SPECIAL_REPLIES.get('private_hello', {}).get('trigger', 'hello') in plain_text_lower):
            reply = config.SPECIAL_REPLIES['private_hello'].get('reply', 'helloword')
            if user_id:
                await self.send_reply_callback(message_type, None, user_id, reply)
                logger.info(f"特殊回复: private hello -> {reply}")
            return
        
        # 处理群聊@机器人的消息 (should_process_message已经确保是@消息)
        if message_type == 'group' and self.is_mentioning_bot(raw_message):
            # 检查消息是否包含文件
            file_info_list = extract_file_info(raw_message)
            has_files = len(file_info_list) > 0
            
            # 处理特殊消息类型（如合并转发、音乐、分享等）
            special_messages = []
            remaining_file_info = []
            for file_info in file_info_list:
                msg_type = file_info.get("type")
                params = file_info.get("params", {})
                
                if msg_type == "forward":
                    forward_id = file_info.get("file_id", "unknown")
                    # 将forward消息加入remaining_file_info，以便在process_file_message中处理XML内容
                    remaining_file_info.append(file_info)
                    logger.info(f"检测到合并转发消息: {forward_id}，将进行详细处理")
                elif msg_type == "music":
                    music_type = params.get("type", "unknown")
                    music_id = params.get("id", "unknown")
                    title = params.get("title", "未知音乐")
                    special_messages.append(f"用户分享了一首音乐: {title} (类型: {music_type}, ID: {music_id})")
                    logger.info(f"检测到音乐分享: {title}")
                elif msg_type == "share":
                    title = params.get("title", "未知链接")
                    url = params.get("url", "")
                    content = params.get("content", "")
                    if url:
                        special_messages.append(f"用户分享了一个链接: {title} (URL: {url})")
                    else:
                        special_messages.append(f"用户分享了一个链接: {title}")
                    logger.info(f"检测到链接分享: {title}")
                elif msg_type == "contact":
                    contact_type = params.get("type", "unknown")
                    contact_id = params.get("id", "unknown")
                    name = params.get("name", "未知联系人")
                    special_messages.append(f"用户分享了一个联系人: {name} (类型: {contact_type}, ID: {contact_id})")
                    logger.info(f"检测到联系人分享: {name}")
                elif msg_type == "location":
                    lat = params.get("lat", "未知")
                    lon = params.get("lon", "未知")
                    title = params.get("title", "位置分享")
                    content = params.get("content", "")
                    special_messages.append(f"用户分享了一个位置: {title} (坐标: {lat}, {lon})")
                    logger.info(f"检测到位置分享: {title}")
                elif msg_type == "shake":
                    special_messages.append("用户发送了一个窗口抖动（戳一戳）")
                    logger.info("检测到窗口抖动消息")
                elif msg_type == "poke":
                    # poke类型通常通过通知事件处理，但有时也可能作为CQ码出现
                    poke_type = params.get("type", "unknown")
                    poke_id = params.get("id", "unknown")
                    special_messages.append(f"用户发送了一个戳一戳 (类型: {poke_type}, ID: {poke_id})")
                    logger.info(f"检测到戳一戳消息: {poke_type}")
                else:
                    remaining_file_info.append(file_info)
            
            # 处理文件消息（如果有文件）
            processed_text = None
            if remaining_file_info:
                processed_text = await self.file_handler.process_file_message(raw_message, message_type, group_id, user_id, message)
            
            # 如果有特殊消息，将其添加到处理后的文本中
            if special_messages:
                if processed_text:
                    processed_text = " ".join(special_messages) + " " + processed_text
                else:
                    processed_text = " ".join(special_messages)
            
            # 提取@后的纯文本
            at_removed_text = extract_plain_text(raw_message).strip()
            
            # 如果有处理过的文件消息，使用处理后的文本
            if processed_text:
                at_removed_text = processed_text.strip()
            
            if at_removed_text:
                # 检查是否为命令
                if self.is_command(at_removed_text):
                    await self.handle_command(message_type, group_id, user_id, at_removed_text)
                    return
                
                # 如果不是命令，转发到OpenCode
                logger.info(f"收到@机器人的消息: {at_removed_text[:50]}...")
                await self.message_queue_processor.enqueue_message(message_type, group_id, user_id, at_removed_text, user_name)
            return
        
        # 处理私聊非命令消息（转发到OpenCode）
        if message_type == 'private':
            # 检查是否为命令（已在前面处理）
            # 转发到OpenCode
            await self.message_queue_processor.enqueue_message(message_type, group_id, user_id, original_plain_text, user_name)
            return
        
        # 使用配置中的自动回复关键词（仅当没有文件且消息没有其他处理时）
        if not has_files and config.ENABLED_FEATURES.get('auto_reply', True):
            await self.handle_auto_reply(message_type, group_id, user_id, plain_text_lower)