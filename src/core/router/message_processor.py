#!/usr/bin/env python3
"""
消息处理器模块
负责处理消息的具体逻辑，包括文件处理、引用消息处理、特殊消息类型处理等
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Any, List, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..file_handler import FileHandler
    from ..napcat_http_client import NapCatHttpClient

logger = logging.getLogger(__name__)


class MessageProcessor:
    """消息处理器
    
    负责处理消息的具体逻辑，包括：
    - 文件处理（从records中提取文件信息并下载）
    - 引用消息处理
    - 特殊消息类型处理（音乐、分享、联系人等）
    """
    
    def __init__(
        self,
        file_handler: "FileHandler",
        http_client: Optional["NapCatHttpClient"] = None
    ):
        """初始化消息处理器
        
        Args:
            file_handler: 文件处理器实例
            http_client: NapCat HTTP 客户端实例（可选）
        """
        self.file_handler = file_handler
        self.http_client = http_client
    
    # ==================== 文件处理相关方法 ====================
    
    async def process_files_in_records(
        self, 
        records: List[Dict], 
        message_type: str,
        group_id: Optional[int], 
        user_id: Optional[int]
    ) -> str:
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
        
        # 1. 提取文件信息
        file_infos = self._extract_file_infos(records)
        
        # 2. 下载文件
        file_messages = await self._download_files(file_infos, group_id, user_id)
        
        return " ".join(file_messages) if file_messages else ""
    
    def _extract_file_infos(self, records: List[Dict]) -> List[Dict]:
        """从records中提取文件信息
        
        Args:
            records: raw.records列表
            
        Returns:
            文件信息列表，每个元素包含 type, filename, file_size, file_id 等字段
        """
        file_infos = []
        
        for record in records:
            if not isinstance(record, dict):
                continue
                
            elements = record.get('elements', [])
            if not isinstance(elements, list):
                continue
                
            for element in elements:
                if not isinstance(element, dict):
                    continue
                
                # 提取文件元素
                file_info = self._extract_single_element_info(element)
                if file_info:
                    file_infos.append(file_info)
        
        return file_infos
    
    def _extract_single_element_info(self, element: Dict) -> Optional[Dict]:
        """从单个元素中提取文件信息
        
        Args:
            element: 元素字典
            
        Returns:
            文件信息字典，如果没有文件则返回 None
        """
        # 检查文件元素
        file_element = element.get('fileElement')
        if isinstance(file_element, dict):
            return self._extract_file_element_info(file_element)
        
        # 检查图片元素
        pic_element = element.get('picElement')
        if isinstance(pic_element, dict):
            return self._extract_pic_element_info(pic_element)
        
        # 检查语音元素
        ptt_element = element.get('pttElement')
        if isinstance(ptt_element, dict):
            return {'type': 'ptt', 'filename': '语音消息'}
        
        return None
    
    def _extract_file_element_info(self, file_element: Dict) -> Dict:
        """提取文件元素信息"""
        file_name = file_element.get('fileName') or file_element.get('file_name')
        file_size = file_element.get('fileSize') or file_element.get('file_size')
        file_uuid = file_element.get('fileUuid')
        file_sub_id = file_element.get('fileSubId')
        
        file_info = {
            'type': 'file',
            'filename': file_name,
            'file_size': str(file_size) if file_size else '0',
            'params': {}
        }
        
        if file_uuid:
            file_info['file_id'] = file_uuid
            if file_sub_id:
                file_info['params']['file_sub_id'] = file_sub_id
        
        return file_info
    
    def _extract_pic_element_info(self, pic_element: Dict) -> Dict:
        """提取图片元素信息"""
        file_name = pic_element.get('fileName') or pic_element.get('file_name') or \
                    f"image_{pic_element.get('md5HexStr', 'unknown')}.jpg"
        file_size = pic_element.get('fileSize') or pic_element.get('file_size')
        origin_image_url = pic_element.get('originImageUrl') or pic_element.get('origin_image_url')
        
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
        
        return image_info
    
    async def _download_files(
        self, 
        file_infos: List[Dict], 
        group_id: Optional[int], 
        user_id: Optional[int]
    ) -> List[str]:
        """下载文件并返回消息列表
        
        Args:
            file_infos: 文件信息列表
            group_id: 群号
            user_id: 用户QQ号
            
        Returns:
            文件消息列表
        """
        file_messages = []
        
        for file_info in file_infos:
            file_type = file_info.get('type')
            filename = file_info.get('filename', 'unknown')
            
            if file_type == 'ptt':
                file_messages.append("[语音消息]")
                continue
            
            # 尝试下载文件
            try:
                local_path = await self.file_handler.download_file(
                    file_info, group_id, user_id
                )
                
                if local_path:
                    file_messages.append(f"[{file_type}：{filename}] (已下载到：{local_path})")
                else:
                    file_messages.append(f"[{file_type}：{filename}] (下载失败，可能文件已过期或无权限)")
            except Exception as e:
                logger.error(f"下载引用文件失败：{e}")
                file_messages.append(f"[{file_type}：{filename}] (下载错误：{str(e)[:50]}...)")
        
        return file_messages
    
    # ==================== 引用消息处理相关方法 ====================
    
    async def process_quoted_message(
        self,
        quoted_msg_id: Union[int, str],
        quoted_message_data: Optional[Dict],
        group_id: Optional[int],
        user_id: Optional[int]
    ) -> Tuple[str, str]:
        """处理引用消息
        
        Args:
            quoted_msg_id: 引用消息ID
            quoted_message_data: 引用消息数据
            group_id: 群号
            user_id: 用户QQ号
            
        Returns:
            (引用内容文本, 引用附件信息)
        """
        if not quoted_message_data:
            return "[引用消息 ID 无效]", ""
        
        # 提取文本内容
        quoted_content = self._extract_quoted_text(quoted_message_data)
        
        # 处理文件/图片/合并转发
        quoted_files_info = ""
        raw_msg = quoted_message_data.get("raw_message", "")
        if raw_msg:
            from ..cq_code_parser import extract_file_info
            file_info_list = extract_file_info(raw_msg)
            if file_info_list:
                quoted_files_info = await self._process_quoted_files(
                    file_info_list, group_id, user_id
                )
        
        if not quoted_content:
            # 如果有附件，不显示 [非文本消息]
            from ..cq_code_parser import extract_file_info
            file_info_list = extract_file_info(raw_msg) if raw_msg else []
            if not file_info_list:
                quoted_content = "[非文本消息]"
        
        return quoted_content, quoted_files_info
    
    def _extract_quoted_text(self, quoted_message_data: Dict) -> str:
        """从引用消息数据中提取文本内容"""
        message_array = quoted_message_data.get("message", [])
        if not isinstance(message_array, list):
            return ""
        
        texts = []
        for segment in message_array:
            if isinstance(segment, dict) and segment.get("type") == "text":
                text = segment.get("data", {}).get("text", "")
                if text:
                    texts.append(text)
        
        return " ".join(texts).strip() if texts else ""
    
    async def _process_quoted_files(
        self,
        file_info_list: List[Dict],
        group_id: Optional[int],
        user_id: Optional[int]
    ) -> str:
        """处理引用消息中的文件"""
        from ..cq_code_parser import extract_file_info
        
        processed_files = []
        for file_info in file_info_list:
            file_type = file_info.get("type")
            filename = file_info.get("filename", "unknown")
            
            # forward 类型特殊处理
            if file_type == "forward":
                forward_result = await self._process_forward_in_quoted(file_info)
                processed_files.append(forward_result)
            else:
                # 其他类型使用 download_file
                local_path = await self.file_handler.download_file(
                    file_info, group_id, user_id
                )
                
                if local_path:
                    processed_files.append(f"[{file_type}: {filename}] (已下载到：{local_path})")
                else:
                    processed_files.append(f"[{file_type}: {filename}] (下载失败)")
        
        return " ".join(processed_files)
    
    async def _process_forward_in_quoted(self, file_info: Dict) -> str:
        """处理引用消息中的合并转发"""
        forward_id = file_info.get("file_id", "")
        filename = file_info.get("filename", "unknown")
        
        if not forward_id or not self.http_client:
            return f"[forward: {filename}]"
        
        try:
            forward_data = await self.http_client.get_forward_msg(forward_id)
            if forward_data:
                messages = forward_data.get("messages", [])
                parsed_messages = self._parse_forward_messages(messages)
                
                if parsed_messages:
                    forward_summary = " | ".join(parsed_messages)
                    return f"[forward: {forward_summary}]"
                else:
                    return f"[forward: {len(messages)}条消息]"
            else:
                return f"[forward: {filename}] (解析失败)"
        except Exception as e:
            logger.warning(f"获取引用消息中的合并转发失败: {e}")
            return f"[forward: {filename}] (解析失败)"
    
    def _parse_forward_messages(self, messages: List[Dict]) -> List[str]:
        """解析合并转发消息列表"""
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
        
        return parsed_messages
    
    # ==================== 特殊消息类型处理 ====================
    
    def process_special_message_types(
        self, 
        file_info_list: List[Dict]
    ) -> Tuple[List[str], List[Dict]]:
        """处理特殊消息类型（音乐、分享、联系人等）
        
        Args:
            file_info_list: 文件信息列表
            
        Returns:
            (特殊消息列表, 剩余文件信息列表)
        """
        special_messages = []
        remaining_file_info = []
        
        for file_info in file_info_list:
            msg_type = file_info.get("type")
            params = file_info.get("params", {})
            
            special_msg = self._get_special_message_text(msg_type, params)
            
            if special_msg:
                special_messages.append(special_msg)
                logger.info(f"检测到{msg_type}消息")
            else:
                remaining_file_info.append(file_info)
        
        return special_messages, remaining_file_info
    
    def _get_special_message_text(self, msg_type: str, params: Dict) -> Optional[str]:
        """获取特殊消息类型的文本描述"""
        if msg_type == "music":
            music_type = params.get("type", "unknown")
            music_id = params.get("id", "unknown")
            title = params.get("title", "未知音乐")
            return f"用户分享了一首音乐: {title} (类型: {music_type}, ID: {music_id})"
        
        elif msg_type == "share":
            title = params.get("title", "未知链接")
            url = params.get("url", "")
            if url:
                return f"用户分享了一个链接: {title} (URL: {url})"
            else:
                return f"用户分享了一个链接: {title}"
        
        elif msg_type == "contact":
            contact_type = params.get("type", "unknown")
            contact_id = params.get("id", "unknown")
            name = params.get("name", "未知联系人")
            return f"用户分享了一个联系人: {name} (类型: {contact_type}, ID: {contact_id})"
        
        elif msg_type == "location":
            lat = params.get("lat", "未知")
            lon = params.get("lon", "未知")
            title = params.get("title", "位置分享")
            return f"用户分享了一个位置: {title} (坐标: {lat}, {lon})"
        
        elif msg_type == "shake":
            return "用户发送了一个窗口抖动（戳一戳）"
        
        elif msg_type == "poke":
            poke_type = params.get("type", "unknown")
            poke_id = params.get("id", "unknown")
            return f"用户发送了一个戳一戳 (类型: {poke_type}, ID: {poke_id})"
        
        return None
    
    # ==================== 引用消息前缀构建 ====================
    
    def build_quoted_prefix(
        self, 
        quoted_content: str, 
        quoted_files_info: str,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        user_name: str = "",
        session_id: Optional[str] = None
    ) -> str:
        """构建引用消息前缀 (JSON格式)
        
        Args:
            quoted_content: 引用内容文本
            quoted_files_info: 引用附件信息
            user_id: 用户QQ号
            group_id: 群号
            user_name: 用户昵称
            session_id: OpenCode会话ID
            
        Returns:
            引用消息前缀
        """
        import json
        
        # 检查是否包含 forward 类型
        has_forward_in_files = quoted_files_info and "[forward:" in quoted_files_info
        
        prefix_data = {"type": "quoted_message"}
        hint_parts = []
        
        if has_forward_in_files:
            # forward 类型
            forward_content = quoted_files_info.replace("[forward: ", "").rstrip("]")
            prefix_data["forward_content"] = forward_content
            hint_parts.append(f"用户{f'({user_name}, ' if user_name else f'(QQ: {user_id}, '}QQ: {user_id})引用了一个合并转发消息")
        elif quoted_files_info:
            # 有附件
            if quoted_content:
                prefix_data["content"] = quoted_content
                hint_parts.append(f"用户{f'({user_name}, ' if user_name else f'(QQ: {user_id}, '}QQ: {user_id})引用了一条消息，内容: {quoted_content[:50]}...")
            prefix_data["attachments"] = quoted_files_info
            hint_parts.append("引用的消息包含附件")
        elif quoted_content:
            # 只有文本内容
            prefix_data["content"] = quoted_content
            hint_parts.append(f"用户{f'({user_name}, ' if user_name else f'(QQ: {user_id}, '}QQ: {user_id})引用了一条消息，内容: {quoted_content[:50]}...")
        
        # 添加用户和群信息
        prefix_data["user_qq"] = str(user_id) if user_id else None
        prefix_data["group_id"] = str(group_id) if group_id else None
        prefix_data["user_name"] = user_name if user_name else None
        prefix_data["session_id"] = session_id
        
        # 添加提示信息
        if hint_parts:
            prefix_data["hint"] = "。".join(hint_parts) + "。请在回复时考虑引用的上下文。"
        
        if prefix_data.get("content") or prefix_data.get("forward_content") or prefix_data.get("attachments"):
            return "<Axeuh_bot>\n" + json.dumps(prefix_data, ensure_ascii=False) + "\n</Axeuh_bot>\n"
        
        return ""