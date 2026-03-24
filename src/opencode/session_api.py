#!/usr/bin/env python3
"""
OpenCode 会话 API
提供会话管理相关的 API 方法
"""

import aiohttp
import asyncio
import base64
import logging
from typing import Dict, List, Optional, Tuple

try:
    from ..utils import config
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from utils import config
    except ImportError:
        import config

from .types import SessionResult, BoolResult, ListResult

logger = logging.getLogger(__name__)


class SessionAPI:
    """会话 API"""
    
    def __init__(self, client):
        """
        初始化会话 API
        
        Args:
            client: OpenCodeClient 实例
        """
        self._client = client
    
    def _get_client(self):
        """获取客户端实例"""
        return self._client
    
    async def create_session(
        self, 
        title: Optional[str] = None,
        directory: Optional[str] = None
    ) -> SessionResult:
        """
        创建新会话
        
        Args:
            title: 会话标题
            directory: 工作目录
            
        Returns:
            (会话 ID, 错误消息) 元组
        """
        client = self._get_client()
        session_title = title or f"QQ 机器人会话_{asyncio.get_event_loop().time():.0f}"
        
        # 构建额外请求头
        extra_headers = {}
        if directory:
            directory_b64 = base64.b64encode(directory.encode()).decode()
            referer = f"{client.base_url}/{directory_b64}/session"
            extra_headers["Referer"] = referer
            extra_headers["x-opencode-directory"] = directory
        
        data, error = await client._send_request(
            method="POST",
            endpoint="/session",
            json_data={"title": session_title},
            extra_headers=extra_headers if extra_headers else None
        )
        
        if error:
            return None, error
        
        # 提取会话 ID
        session_id = data.get("id") if isinstance(data, dict) else None
        if not session_id:
            return None, "响应中未找到会话 ID"
        
        logger.info(f"创建 OpenCode 会话成功：{session_id} (标题：{session_title}, 目录：{directory})")
        return session_id, None
    
    async def abort_session(self, session_id: str, directory: Optional[str] = None) -> BoolResult:
        """
        中止/停止当前 OpenCode 会话
        
        Args:
            session_id: 会话 ID
            directory: 工作目录
            
        Returns:
            (是否成功, 错误消息) 元组
        """
        client = self._get_client()
        work_directory = directory or client.directory or "/"
        directory_b64 = base64.b64encode(work_directory.encode()).decode()
        
        url = f"{config.OPENCODE_BASE_URL}/session/{session_id}/abort"
        
        headers = {
            "Accept": "*/*",
            "Origin": client.base_url,
            "Referer": f"{client.base_url}/{directory_b64}/session/{session_id}",
            "x-opencode-directory": work_directory
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as http_client:
                async with http_client.post(
                    url,
                    cookies=config.OPENCODE_COOKIES,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        logger.info(f"中止会话成功：{session_id}")
                        return True, None
                    else:
                        text = await response.text()
                        return False, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"中止会话失败：{e}")
            return False, str(e)
    
    async def revert_last_message(self, session_id: str, directory: Optional[str] = None) -> BoolResult:
        """
        撤销会话中的最后一条消息
        
        Args:
            session_id: 会话 ID
            directory: 工作目录
            
        Returns:
            (是否成功, 错误消息) 元组
        """
        client = self._get_client()
        work_directory = directory or client.directory or "/"
        directory_b64 = base64.b64encode(work_directory.encode()).decode()
        
        # 先获取消息列表以获取最后一条消息的 ID
        messages, error = await self.list_messages(session_id, limit=10)
        
        message_id = None
        if messages:
            for msg in reversed(messages):
                if isinstance(msg, dict) and "info" in msg:
                    message_id = msg["info"].get("id")
                    break
        
        url = f"{config.OPENCODE_BASE_URL}/session/{session_id}/revert"
        
        headers = {
            "Accept": "*/*",
            "Origin": client.base_url,
            "Referer": f"{client.base_url}/{directory_b64}/session/{session_id}",
            "x-opencode-directory": work_directory
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as http_client:
                if message_id:
                    async with http_client.post(
                        url,
                        cookies=config.OPENCODE_COOKIES,
                        headers=headers,
                        json={"messageID": message_id}
                    ) as response:
                        if response.status == 200:
                            logger.info(f"撤销最后一条消息成功：{session_id}, messageID: {message_id}")
                            return True, None
                        else:
                            text = await response.text()
                            return False, f"HTTP {response.status}: {text}"
                else:
                    async with http_client.post(
                        url,
                        cookies=config.OPENCODE_COOKIES,
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            logger.info(f"撤销最后一条消息成功：{session_id}")
                            return True, None
                        else:
                            text = await response.text()
                            return False, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"撤销消息失败：{e}")
            return False, str(e)
    
    async def unrevert_messages(self, session_id: str, directory: Optional[str] = None) -> BoolResult:
        """
        恢复所有撤销的消息
        
        Args:
            session_id: 会话 ID
            directory: 工作目录
            
        Returns:
            (是否成功, 错误消息) 元组
        """
        client = self._get_client()
        work_directory = directory or client.directory or "/"
        directory_b64 = base64.b64encode(work_directory.encode()).decode()
        
        url = f"{config.OPENCODE_BASE_URL}/session/{session_id}/unrevert"
        
        headers = {
            "Accept": "*/*",
            "Origin": client.base_url,
            "Referer": f"{client.base_url}/{directory_b64}/session/{session_id}",
            "x-opencode-directory": work_directory
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as http_client:
                async with http_client.post(
                    url,
                    cookies=config.OPENCODE_COOKIES,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        logger.info(f"恢复所有撤销的消息成功：{session_id}")
                        return True, None
                    else:
                        text = await response.text()
                        return False, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"恢复消息失败：{e}")
            return False, str(e)
    
    async def list_sessions(self, limit: int = 50) -> ListResult:
        """
        列出所有会话
        
        Args:
            limit: 返回的会话数量限制
            
        Returns:
            (会话列表, 错误消息) 元组
        """
        client = self._get_client()
        data, error = await client._send_request(
            method="GET",
            endpoint="/session",
            params={"limit": limit} if limit else None
        )
        
        if error:
            return None, error
        
        # 确保返回列表
        if isinstance(data, dict):
            if "id" in data:
                data = [data]
            elif "sessions" in data:
                data = data["sessions"]
        
        return data if isinstance(data, list) else [], None
    
    async def get_session(self, session_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        获取会话详情
        
        Args:
            session_id: 会话 ID
            
        Returns:
            (会话详情, 错误消息) 元组
        """
        client = self._get_client()
        data, error = await client._send_request(
            method="GET",
            endpoint=f"/session/{session_id}"
        )
        
        if error:
            return None, error
        
        return data, None
    
    async def delete_session(self, session_id: str) -> BoolResult:
        """
        删除会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            (是否成功, 错误消息) 元组
        """
        client = self._get_client()
        _, error = await client._send_request(
            method="DELETE",
            endpoint=f"/session/{session_id}"
        )
        
        if error:
            return False, error
        
        logger.info(f"删除会话成功: {session_id}")
        return True, None
    
    async def summarize_session(
        self,
        session_id: str,
        provider_id: str,
        model_id: str,
        directory: Optional[str] = None
    ) -> BoolResult:
        """
        压缩/总结当前会话上下文
        
        Args:
            session_id: 会话 ID
            provider_id: 提供商 ID
            model_id: 模型 ID
            directory: 工作目录
            
        Returns:
            (是否成功, 错误消息) 元组
        """
        client = self._get_client()
        work_directory = directory or client.directory or "/"
        directory_b64 = base64.b64encode(work_directory.encode()).decode()
        
        url = f"{config.OPENCODE_BASE_URL}/session/{session_id}/summarize"
        
        headers = {
            "Accept": "*/*",
            "Origin": client.base_url,
            "Referer": f"{client.base_url}/{directory_b64}/session/{session_id}",
            "x-opencode-directory": work_directory
        }
        
        json_data = {
            "providerID": provider_id,
            "modelID": model_id
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=1200)
            async with aiohttp.ClientSession(timeout=timeout) as http_client:
                async with http_client.post(
                    url,
                    cookies=config.OPENCODE_COOKIES,
                    headers=headers,
                    json=json_data
                ) as response:
                    if response.status == 200:
                        logger.info(f"压缩会话成功：{session_id}")
                        return True, None
                    else:
                        text = await response.text()
                        return False, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"压缩会话失败：{e}")
            return False, str(e)
    
    async def list_messages(self, session_id: str, limit: Optional[int] = None, directory: Optional[str] = None) -> ListResult:
        """
        列出会话中的消息
        
        Args:
            session_id: 会话 ID
            limit: 返回的消息数量限制
            directory: 工作目录
            
        Returns:
            (消息列表, 错误消息) 元组
        """
        client = self._get_client()
        
        # 构建额外请求头
        extra_headers = None
        if directory or client.directory:
            work_directory = directory or client.directory
            directory_b64 = base64.b64encode(work_directory.encode()).decode()
            extra_headers = {
                "Referer": f"{client.base_url}/{directory_b64}/session/{session_id}",
                "x-opencode-directory": work_directory
            }
        
        params = {"limit": limit} if limit else None
        data, error = await client._send_request(
            method="GET",
            endpoint=f"/session/{session_id}/message",
            params=params,
            extra_headers=extra_headers
        )
        
        if error:
            return None, error
        
        # 确保返回列表
        if isinstance(data, dict):
            if "info" in data:
                data = [data]
            elif "messages" in data:
                data = data["messages"]
        
        return data if isinstance(data, list) else [], None