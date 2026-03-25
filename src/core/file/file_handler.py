#!/usr/bin/env python3
"""
文件处理器 - 处理QQ机器人文件上传和下载
重构后的核心类，组合 PathResolver, FileValidator, FileDownloader
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Awaitable

from .downloader import FileDownloader
from .path_resolver import PathResolver
from .validator import FileValidator

logger = logging.getLogger(__name__)


class FileHandler:
    """文件处理器，负责文件下载、保存和管理
    
    公共 API:
        - download_file(): 下载文件
        - process_file_message(): 处理文件消息
        - get_file_type_directory(): 获取文件类型目录
        - cleanup_old_files(): 清理旧文件
        - get_download_stats(): 获取下载统计
    """
    
    def __init__(
        self,
        base_download_dir: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        api_callback: Optional[Callable[[str, Dict[str, Any], float], Awaitable[Optional[Dict[str, Any]]]]] = None
    ):
        """初始化文件处理器
        
        Args:
            base_download_dir: 文件下载的基础目录
            config: 文件配置字典
            api_callback: 可选的API回调函数，用于发送OneBot API请求
        """
        self.base_download_dir = base_download_dir
        self.config = config or {}
        self.api_callback = api_callback
        
        # 设置默认配置
        self._init_default_config()
        
        # 初始化子组件
        self.path_resolver = PathResolver()
        self.validator = FileValidator(self.config)
        self.downloader = FileDownloader(base_download_dir, self.config, api_callback)
        
        # 确保下载目录存在
        self._ensure_download_dirs()
        
        logger.info(f"文件处理器初始化完成，下载目录: {self.base_download_dir or self.config.get('download_dir', 'downloads')}")
    
    def _init_default_config(self) -> None:
        """初始化默认配置"""
        default_config = {
            "auto_download_files": True,
            "include_file_path_in_message": True,
            "file_message_prefix": "用户发送了一个文件，文件路径: ",
            "continue_on_download_fail": True,
            "max_file_size_mb": 500,
            "max_file_size": 500 * 1024 * 1024,
            "allowed_file_types": ["image", "file", "video", "voice"],
            "image_download_dir": "images",
            "file_download_dir": "files",
            "video_download_dir": "videos",
            "voice_download_dir": "voice",
            "download_dir": "downloads",
            "naming_strategy": "original",
            "download_wait_time": 2,
            "napcat_temp_dir": r"C:\Users\Administrator\Documents\Tencent Files\NapCat\temp"
        }
        
        for key, default_value in default_config.items():
            self.config[key] = self.config.get(key, default_value)
    
    def _ensure_download_dirs(self) -> None:
        """确保下载目录存在"""
        download_dir = self.config.get("download_dir", "downloads")
        os.makedirs(download_dir, exist_ok=True)
        
        if self.base_download_dir:
            os.makedirs(self.base_download_dir, exist_ok=True)
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """更新文件配置
        
        Args:
            config: 新的配置字典
        """
        self.config.update(config)
        self.validator = FileValidator(self.config)
        self.downloader = FileDownloader(self.base_download_dir, self.config, self.api_callback)
        logger.debug(f"文件配置已更新: {config}")
    
    # ==================== 公共 API ====================
    
    async def download_file(
        self,
        file_info: Dict[str, Any],
        group_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Optional[str]:
        """下载文件到本地
        
        Args:
            file_info: 文件信息字典
            group_id: 群号（如果是群文件）
            user_id: 发送文件的用户 QQ 号
            
        Returns:
            下载后的本地文件路径，或 None（下载失败）
        """
        return await self.downloader.download_file(file_info, group_id, user_id)
    
    async def process_file_message(
        self,
        raw_message: str,
        message_type: str,
        group_id: Optional[int] = None,
        user_id: Optional[int] = None,
        original_message: Optional[Dict[str, Any]] = None
    ) -> str:
        """处理文件消息，返回要转发给OpenCode的文本
        
        Args:
            raw_message: 原始消息内容
            message_type: 消息类型（private/group）
            group_id: 群号（如果是群消息）
            user_id: 发送文件的用户QQ号
            original_message: 原始消息字典（可选）
            
        Returns:
            处理后的消息文本
        """
        from ..cq_code_parser import extract_file_info, extract_plain_text
        
        # 提取文件信息
        file_info_list = extract_file_info(raw_message)
        
        if not file_info_list:
            return extract_plain_text(raw_message)
        
        processed_messages = []
        
        # 处理每个文件
        for file_info in file_info_list:
            file_msg = await self._process_single_file(
                file_info, group_id, user_id, original_message
            )
            if file_msg:
                processed_messages.append(file_msg)
        
        # 提取其他文本内容
        plain_text = extract_plain_text(raw_message)
        if plain_text:
            processed_messages.insert(0, plain_text)
        
        result = " ".join(processed_messages)
        logger.debug(f"处理后的文件消息: {result}")
        return result
    
    def get_file_type_directory(self, file_type: str) -> str:
        """获取文件类型对应的下载目录
        
        Args:
            file_type: 文件类型（image, file, video, voice等）
            
        Returns:
            目录名称
        """
        type_dir_map = {
            "image": self.config.get("image_download_dir", "images"),
            "file": self.config.get("file_download_dir", "files"),
            "video": self.config.get("video_download_dir", "videos"),
            "voice": self.config.get("voice_download_dir", "voice")
        }
        return type_dir_map.get(file_type, file_type + "s")
    
    def cleanup_old_files(self, max_age_days: int = 30) -> int:
        """清理旧文件
        
        Args:
            max_age_days: 最大保留天数
            
        Returns:
            删除的文件数量
        """
        if not self.base_download_dir or not os.path.exists(self.base_download_dir):
            return 0
        
        deleted_count = 0
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
        
        for root, dirs, files in os.walk(self.base_download_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_mtime = os.path.getmtime(file_path)
                    if file_mtime < cutoff_time:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.debug(f"清理旧文件: {file_path}")
                except Exception as e:
                    logger.error(f"清理文件失败 {file_path}: {e}")
        
        logger.info(f"文件清理完成，删除了 {deleted_count} 个旧文件")
        return deleted_count
    
    def get_download_stats(self) -> Dict[str, Any]:
        """获取下载统计信息
        
        Returns:
            统计信息字典
        """
        if not self.base_download_dir or not os.path.exists(self.base_download_dir):
            return {"total_files": 0, "total_size_mb": 0, "by_type": {}}
        
        stats = {
            "total_files": 0,
            "total_size_bytes": 0,
            "by_type": {}
        }
        
        for root, dirs, files in os.walk(self.base_download_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(file_path)
                    stats["total_files"] += 1
                    stats["total_size_bytes"] += file_size
                    
                    rel_path = os.path.relpath(root, self.base_download_dir)
                    dir_parts = rel_path.split(os.sep)
                    file_type = dir_parts[0] if dir_parts else "unknown"
                    
                    if file_type not in stats["by_type"]:
                        stats["by_type"][file_type] = {"count": 0, "size_bytes": 0}
                    
                    stats["by_type"][file_type]["count"] += 1
                    stats["by_type"][file_type]["size_bytes"] += file_size
                except Exception as e:
                    logger.error(f"统计文件失败 {file_path}: {e}")
        
        stats["total_size_mb"] = round(stats["total_size_bytes"] / (1024 * 1024), 2)
        for file_type in stats["by_type"]:
            bytes_val = stats["by_type"][file_type]["size_bytes"]
            stats["by_type"][file_type]["size_mb"] = round(bytes_val / (1024 * 1024), 2)
        
        return stats
    
    # ==================== 私有方法 - 文件处理 ====================
    
    async def _process_single_file(
        self,
        file_info: Dict[str, Any],
        group_id: Optional[int],
        user_id: Optional[int],
        original_message: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """处理单个文件
        
        Args:
            file_info: 文件信息
            group_id: 群号
            user_id: 用户 QQ 号
            original_message: 原始消息字典
            
        Returns:
            处理后的消息文本
        """
        filename = file_info.get("filename", "unknown_file")
        file_id = file_info.get("file_id", "")
        file_type = file_info.get("type", "file")
        
        # 图片消息处理
        if file_type == "image":
            return await self._process_image_file(file_info, group_id, user_id, filename)
        
        # 合并转发消息处理
        if file_type == "forward":
            return await self._process_forward_message(
                file_info, group_id, user_id, original_message
            )
        
        # 其他文件类型处理
        return await self._process_other_file(file_info, group_id, user_id, filename, file_id)
    
    async def _process_image_file(
        self,
        file_info: Dict[str, Any],
        group_id: Optional[int],
        user_id: Optional[int],
        filename: str
    ) -> str:
        """处理图片文件 (JSON格式输出)"""
        import json
        url = file_info.get("params", {}).get("url", "")
        
        local_path = await self.download_file(file_info, group_id, user_id)
        
        if local_path:
            file_data = {
                "type": "file",
                "file_type": "image",
                "filename": filename,
                "local_path": local_path,
                "status": "downloaded",
                "hint": f"用户发送了一张图片，文件名: {filename}，已下载到本地路径: {local_path}。如果需要分析图片内容，可以使用图片路径。"
            }
            file_msg = "<Axeuh_bot>\n" + json.dumps(file_data, ensure_ascii=False) + "\n</Axeuh_bot>"
            logger.info(f"图片下载成功：{filename} -> {local_path}")
        elif self.config.get("continue_on_download_fail", True):
            file_data = {
                "type": "file",
                "file_type": "image",
                "filename": filename,
                "url": url if url else None,
                "status": "download_failed",
                "hint": f"用户发送了一张图片，文件名: {filename}，但下载失败。如有URL可尝试通过URL访问。"
            }
            file_msg = "<Axeuh_bot>\n" + json.dumps(file_data, ensure_ascii=False) + "\n</Axeuh_bot>"
            logger.warning(f"图片下载失败但仍继续处理：{filename}")
        else:
            logger.error(f"图片下载失败且配置为不继续处理：{filename}")
            return ""
        
        return file_msg
    
    async def _process_forward_message(
        self,
        file_info: Dict[str, Any],
        group_id: Optional[int],
        user_id: Optional[int],
        original_message: Optional[Dict[str, Any]]
    ) -> str:
        """处理合并转发消息 (JSON格式输出)"""
        import json
        forward_id = file_info.get("file_id", "")
        params = file_info.get("params", {})
        
        # 尝试获取转发消息内容
        forward_messages = await self._get_forward_messages(forward_id)
        
        if forward_messages:
            return await self._parse_forward_messages(
                forward_messages, forward_id, group_id, user_id
            )
        
        # 回退到 XML 解析
        return await self._fallback_xml_parse(
            forward_id, params, original_message, forward_id
        )
    
    async def _get_forward_messages(self, forward_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取合并转发消息列表"""
        if not forward_id:
            return None
        
        # 尝试 HTTP API
        if self.downloader.http_client:
            try:
                logger.info(f"使用 HTTP API 获取合并转发消息: {forward_id}")
                forward_data = await self.downloader.http_client.get_forward_msg(forward_id)
                if forward_data:
                    messages = forward_data.get("messages", [])
                    logger.info(f"HTTP get_forward_msg 成功，获取到 {len(messages)} 条消息")
                    return messages
            except Exception as e:
                logger.warning(f"HTTP get_forward_msg 异常: {e}")
        
        # 回退到 WebSocket API
        if self.api_callback:
            try:
                logger.info(f"使用 WebSocket API 获取合并转发消息: {forward_id}")
                result = await self.api_callback("get_forward_msg", {"message_id": forward_id}, 30.0)
                if result and result.get("status") == "ok":
                    forward_data = result.get("data", {})
                    messages = forward_data.get("messages", [])
                    logger.info(f"WebSocket get_forward_msg 成功，获取到 {len(messages)} 条消息")
                    return messages
            except Exception as e:
                logger.warning(f"WebSocket get_forward_msg 异常: {e}")
        
        return None
    
    async def _parse_forward_messages(
        self,
        forward_messages: List[Dict[str, Any]],
        forward_id: str,
        group_id: Optional[int],
        user_id: Optional[int]
    ) -> str:
        """解析合并转发消息列表 (JSON格式输出)"""
        import json
        parsed_messages = []
        downloaded_files = []
        
        for msg in forward_messages:
            sender = msg.get("sender", {})
            nickname = sender.get("nickname", "未知用户")
            message = msg.get("message", [])
            raw_message = msg.get("raw_message", "")
            
            text_content = await self._parse_forward_message_items(
                message, raw_message, group_id, user_id, downloaded_files
            )
            
            if text_content.strip():
                parsed_messages.append({
                    "sender": nickname,
                    "content": text_content.strip()
                })
        
        if parsed_messages:
            # 构建hint
            hint_text = f"用户发送了一个合并转发消息，共{len(parsed_messages)}条消息。"
            if downloaded_files:
                hint_text += f"其中包含{len(downloaded_files)}个附件已下载。"
            hint_text += "请根据转发消息的内容进行回复。"
            
            forward_data = {
                "type": "forward_message",
                "forward_id": forward_id,
                "message_count": len(parsed_messages),
                "messages": parsed_messages,
                "downloaded_files": [
                    {"type": ftype, "filename": fname, "local_path": fpath}
                    for ftype, fname, fpath in downloaded_files
                ] if downloaded_files else [],
                "hint": hint_text
            }
            logger.info(f"合并转发消息解析成功: {len(parsed_messages)}条消息, 下载{len(downloaded_files)}个文件")
            return "<Axeuh_bot>\n" + json.dumps(forward_data, ensure_ascii=False) + "\n</Axeuh_bot>"
        
        return "<Axeuh_bot>\n" + json.dumps({
            "type": "forward_message", 
            "forward_id": forward_id, 
            "status": "empty",
            "hint": "用户发送了一个合并转发消息，但内容为空或无法解析。"
        }, ensure_ascii=False) + "\n</Axeuh_bot>"
    
    async def _parse_forward_message_items(
        self,
        message: Any,
        raw_message: str,
        group_id: Optional[int],
        user_id: Optional[int],
        downloaded_files: List[Tuple[str, str, str]]
    ) -> str:
        """解析合并转发消息中的项目"""
        text_parts = []
        
        if isinstance(message, list):
            for item in message:
                if isinstance(item, dict):
                    item_type = item.get("type", "")
                    
                    if item_type == "text":
                        text_parts.append(item.get("data", {}).get("text", ""))
                    
                    elif item_type == "image":
                        await self._process_forward_image(
                            item, text_parts, downloaded_files, group_id, user_id
                        )
                    
                    elif item_type == "file":
                        self._process_forward_file(item, text_parts)
                
                elif isinstance(item, str):
                    text_parts.append(item)
            
            return "".join(text_parts)
        
        elif isinstance(message, str):
            return message
        else:
            return raw_message
    
    async def _process_forward_image(
        self,
        item: Dict[str, Any],
        text_parts: List[str],
        downloaded_files: List[Tuple[str, str, str]],
        group_id: Optional[int],
        user_id: Optional[int]
    ) -> None:
        """处理合并转发消息中的图片"""
        img_data = item.get("data", {})
        img_url = img_data.get("url", "")
        img_file = img_data.get("file", "unknown.png")
        
        if self.config.get("auto_download_files", True) and img_url:
            img_file_info = {
                "type": "image",
                "filename": img_file,
                "params": {"url": img_url}
            }
            
            local_path = await self.download_file(img_file_info, group_id, user_id)
            
            if local_path:
                text_parts.append(f"[图片: {local_path}]")
                downloaded_files.append(("图片", img_file, local_path))
            else:
                text_parts.append(f"[图片: {img_file} (下载失败)]")
        else:
            text_parts.append(f"[图片: {img_file}]")
    
    def _process_forward_file(
        self,
        item: Dict[str, Any],
        text_parts: List[str]
    ) -> None:
        """处理合并转发消息中的文件"""
        file_data = item.get("data", {})
        file_name = file_data.get("file", "unknown_file")
        
        text_parts.append(f"[文件: {file_name} (合并转发消息暂时无法下载文件，请提醒用户单独发送文件)]")
        logger.info(f"合并转发消息中的文件无法下载: {file_name}")
    
    async def _fallback_xml_parse(
        self,
        forward_id: str,
        params: Dict[str, Any],
        original_message: Optional[Dict[str, Any]],
        default_forward_id: str
    ) -> str:
        """回退到 XML 解析 (JSON格式输出)"""
        import json
        logger.info(f"get_forward_msg API 不可用，尝试 XML 解析")
        
        xml_content = self._extract_xml_content(params, original_message)
        
        if xml_content:
            try:
                titles = self._extract_titles_from_xml(xml_content)
                
                if titles:
                    return self._build_forward_message_from_titles(titles)
            except Exception as e:
                logger.debug(f"XML解析转发消息失败: {e}")
        else:
            logger.info(f"合并转发消息无XML内容可用，forward_id: {forward_id}")
        
        # 返回默认的JSON格式
        return "<Axeuh_bot>\n" + json.dumps({
            "type": "forward_message",
            "forward_id": default_forward_id,
            "status": "parse_failed",
            "source": "fallback",
            "hint": f"用户发送了一个合并转发消息(ID: {default_forward_id})，但无法解析具体内容。"
        }, ensure_ascii=False) + "\n</Axeuh_bot>"
    
    def _extract_xml_content(
        self,
        params: Dict[str, Any],
        original_message: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """提取 XML 内容"""
        # 从 params 中获取
        if "xml_content" in params:
            xml_content = params["xml_content"]
            logger.debug(f"从CQ码params中获取XML内容，长度: {len(xml_content)}")
            return xml_content
        
        # 从 original_message 中获取
        if original_message is not None:
            try:
                logger.debug(f"尝试从original_message提取XML内容")
                raw_data = original_message.get('raw', {})
                elements = raw_data.get('elements', [])
                if elements and isinstance(elements, list) and len(elements) > 0:
                    first_element = elements[0]
                    multi_forward = first_element.get('multiForwardMsgElement')
                    if multi_forward and 'xmlContent' in multi_forward:
                        xml_content = multi_forward['xmlContent']
                        logger.debug(f"从raw.elements中获取XML内容，长度: {len(xml_content)}")
                        return xml_content
            except Exception as e:
                logger.debug(f"从raw字段提取XML内容失败: {e}")
        
        return None
    
    def _extract_titles_from_xml(self, xml_content: str) -> List[str]:
        """从 XML 中提取标题"""
        title_pattern = r'<title[^>]*>([^<]+)</title>'
        matches = re.findall(title_pattern, xml_content)
        
        if matches:
            titles = [match.strip() for match in matches]
            logger.info(f"从XML中提取到{len(titles)}个标题")
            return titles
        
        return []
    
    def _build_forward_message_from_titles(self, titles: List[str]) -> str:
        """从标题构建转发消息 (JSON格式输出)"""
        import json
        def clean_title_text(text: str) -> str:
            cleaned = re.sub(r'^[^:：]+[:：]\s*', '', text)
            return cleaned.strip()
        
        cleaned_titles = [clean_title_text(title) for title in titles]
        
        forward_data = {
            "type": "forward_message",
            "source": "xml_parse",
            "titles": titles,
            "content_preview": cleaned_titles[1:] if len(cleaned_titles) > 1 else [],
            "hint": f"用户发送了一个合并转发消息，主标题: {titles[0] if titles else '未知'}。请根据转发消息的内容进行回复。"
        }
        
        return "<Axeuh_bot>\n" + json.dumps(forward_data, ensure_ascii=False) + "\n</Axeuh_bot>"
    
async def _process_other_file(
        self,
        file_info: Dict[str, Any],
        group_id: Optional[int],
        user_id: Optional[int],
        filename: str,
        file_id: str
    ) -> str:
        """处理其他文件类型 (JSON格式输出)"""
        import json
        file_type = file_info.get("type", "file")
        url = file_info.get("url") or file_info.get("params", {}).get("url")
        
        if not self.config.get("auto_download_files", True):
            file_data = {
                "type": "file",
                "file_type": file_type,
                "filename": filename,
                "file_id": file_id,
                "status": "skipped",
                "reason": "auto_download_disabled",
                "hint": f"用户发送了一个{file_type}文件，文件名: {filename}，但未自动下载。如有需要可以请求下载。"
            }
            logger.info(f"跳过文件下载: {filename} (配置为不自动下载)")
            return "<Axeuh_bot>\n" + json.dumps(file_data, ensure_ascii=False) + "\n</Axeuh_bot>"
        
        local_path = await self.download_file(file_info, group_id, user_id)
        
        if local_path:
            file_data = {
                "type": "file",
                "file_type": file_type,
                "filename": filename,
                "file_id": file_id,
                "local_path": local_path,
                "status": "downloaded",
                "hint": f"用户发送了一个{file_type}文件，文件名: {filename}，已下载到本地路径: {local_path}。如需处理文件内容，可以使用该路径。"
            }
            logger.info(f"文件信息已添加到消息: {filename} -> {local_path}")
            return "<Axeuh_bot>\n" + json.dumps(file_data, ensure_ascii=False) + "\n</Axeuh_bot>"
        
        if self.config.get("continue_on_download_fail", True):
            file_data = {
                "type": "file",
                "file_type": file_type,
                "filename": filename,
                "file_id": file_id,
                "url": url,
                "status": "download_failed",
                "hint": f"用户发送了一个{file_type}文件，文件名: {filename}，但下载失败。"
            }
            logger.warning(f"文件下载失败但仍继续处理：{filename}")
            return "<Axeuh_bot>\n" + json.dumps(file_data, ensure_ascii=False) + "\n</Axeuh_bot>"
        
        logger.error(f"文件下载失败且配置为不继续处理：{filename}")
        return ""


# 导入 Tuple 用于类型提示
from typing import Tuple