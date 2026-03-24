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
from ..cq_code_parser import extract_plain_text, extract_file_info, extract_quoted_message_id
from ..file_handler import FileHandler
from ..message_queue import MessageQueueProcessor
from ..command_system import CommandSystem
from .message_processor import MessageProcessor

logger = logging.getLogger(__name__)


class MessageRouter:
    """消息路由器
    
    负责消息的路由决策，包括：
    - 白名单检查
    - @机器人检测
    - 命令识别
    - 消息转发
    """
    
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
            get_quoted_message_callback: 获取引用消息完整数据的回调函数，参数：(message_id) -> 消息数据字典
            opencode_available: OpenCode 集成是否可用，默认为 True
        """
        self.file_handler = file_handler
        self.message_queue_processor = message_queue_processor
        self.bot_qq_id = bot_qq_id
        self.command_system = command_system
        self.send_reply_callback = send_reply_callback
        self.get_quoted_message_callback = get_quoted_message_callback
        self.opencode_available = opencode_available
        
        # 创建消息处理器
        http_client = getattr(file_handler, 'http_client', None)
        self.processor = MessageProcessor(file_handler, http_client)
    
    # ==================== 白名单和@检测 ====================
    
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
        
        mention_pattern = f'\\[CQ:at[^\\]]*qq={self.bot_qq_id}[^\\]]*\\]'
        
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
    
    # ==================== 命令处理 ====================
    
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
    
    # ==================== 自动回复 ====================
    
    async def handle_auto_reply(self, message_type: str, group_id: Optional[int], 
                               user_id: Optional[int], plain_text: str) -> None:
        """处理自动回复（使用纯文本）"""
        if not plain_text:
            return
        
        # 对于群聊消息，只处理@机器人的消息（额外安全检查）
        if message_type == 'group' and group_id:
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
    
    # ==================== 主路由方法 ====================
    
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
                logger.info(f"私聊确认回复已关闭，用户 {user_id}")
            elif message_type == 'group' and group_id and user_id:
                logger.info(f"群聊确认回复已关闭 @用户 {user_id}")
        except Exception as e:
            logger.error(f"发送确认回复失败: {e}")
        
        # 处理引用消息
        raw_message = await self._process_quoted_message(
            message, message_type, group_id, user_id, raw_message
        )
        
        # 检查消息是否包含文件
        file_info_list = extract_file_info(raw_message)
        has_files = len(file_info_list) > 0
        
        # 处理特殊消息类型和文件
        processed_text = await self._process_files_and_special(
            raw_message, message_type, group_id, user_id, message, file_info_list
        )
        
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
        
        # 处理群聊@机器人的消息
        if message_type == 'group' and self.is_mentioning_bot(raw_message):
            await self._handle_group_mention(
                message, message_type, group_id, user_id, user_name, raw_message
            )
            return
        
        # 处理私聊非命令消息（转发到OpenCode）
        if message_type == 'private':
            await self.message_queue_processor.enqueue_message(message_type, group_id, user_id, original_plain_text, user_name)
            return
        
        # 使用配置中的自动回复关键词（仅当没有文件且消息没有其他处理时）
        if not has_files and config.ENABLED_FEATURES.get('auto_reply', True):
            await self.handle_auto_reply(message_type, group_id, user_id, plain_text_lower)
    
    # ==================== 私有辅助方法 ====================
    
    async def _process_quoted_message(
        self,
        message: Dict,
        message_type: str,
        group_id: Optional[int],
        user_id: Optional[int],
        raw_message: str
    ) -> str:
        """处理引用消息，返回更新后的 raw_message"""
        quoted_msg_id = extract_quoted_message_id(message)
        if not quoted_msg_id:
            return raw_message
        
        logger.info(f"收到引用消息，引用 ID: {quoted_msg_id}")
        
        # 尝试将消息ID转换为整数
        try:
            quoted_msg_id_for_api = int(quoted_msg_id)
            logger.debug(f"消息ID转换为整数: {quoted_msg_id} -> {quoted_msg_id_for_api}")
        except (ValueError, TypeError):
            quoted_msg_id_for_api = quoted_msg_id
            logger.debug(f"消息ID保持为字符串: {quoted_msg_id}")
        
        # 使用 get_msg API 获取完整消息数据
        quoted_message_data = await self.get_quoted_message_callback(quoted_msg_id_for_api)
        
        # 使用 MessageProcessor 处理引用消息
        quoted_content, quoted_files_info = await self.processor.process_quoted_message(
            quoted_msg_id_for_api, quoted_message_data, group_id, user_id
        )
        
        if not quoted_message_data:
            quoted_content = "[引用消息 ID 无效]"
        elif not quoted_content and not quoted_files_info:
            raw_msg = quoted_message_data.get("raw_message", "")
            file_info_list = extract_file_info(raw_msg) if raw_msg else []
            if not file_info_list:
                quoted_content = "[非文本消息]"
        
        # 构建前缀
        quoted_prefix = self.processor.build_quoted_prefix(quoted_content, quoted_files_info)
        
        if quoted_prefix:
            raw_message = quoted_prefix + raw_message
        
        return raw_message
    
    async def _process_files_and_special(
        self,
        raw_message: str,
        message_type: str,
        group_id: Optional[int],
        user_id: Optional[int],
        message: Dict,
        file_info_list: List[Dict]
    ) -> Optional[str]:
        """处理文件和特殊消息类型"""
        # 处理特殊消息类型（如合并转发、音乐、分享等）
        special_messages, remaining_file_info = self.processor.process_special_message_types(file_info_list)
        
        # 处理 forward 消息
        for file_info in remaining_file_info:
            if file_info.get("type") == "forward":
                forward_id = file_info.get("file_id", "unknown")
                logger.info(f"检测到合并转发消息: {forward_id}，将进行详细处理")
        
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
        
        return processed_text
    
    async def _handle_group_mention(
        self,
        message: Dict,
        message_type: str,
        group_id: Optional[int],
        user_id: Optional[int],
        user_name: str,
        raw_message: str
    ) -> None:
        """处理群聊@机器人的消息"""
        # 检查消息是否包含文件
        file_info_list = extract_file_info(raw_message)
        
        # 处理特殊消息类型和文件
        processed_text = await self._process_files_and_special(
            raw_message, message_type, group_id, user_id, message, file_info_list
        )
        
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