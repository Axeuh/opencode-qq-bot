#!/usr/bin/env python3
"""
OpenCode 消息 API
提供消息发送和命令执行相关的 API 方法
"""

import base64
import logging
from typing import Dict, List, Optional, Tuple

from .types import RequestResult

logger = logging.getLogger(__name__)


class MessageAPI:
    """消息 API"""
    
    def __init__(self, client):
        """
        初始化消息 API
        
        Args:
            client: OpenCodeClient 实例
        """
        self._client = client
    
    def _get_client(self):
        """获取客户端实例"""
        return self._client
    
    async def send_message(
        self,
        message_text: str,
        session_id: Optional[str] = None,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        directory: Optional[str] = None,
        create_if_not_exists: bool = True
    ) -> RequestResult:
        """
        发送消息到 OpenCode 会话
        
        Args:
            message_text: 消息文本
            session_id: 会话 ID，如果为 None 则创建新会话
            agent: 智能体名称
            model: 模型 ID
            provider: 提供商 ID
            directory: 工作目录
            create_if_not_exists: 如果会话不存在，是否创建新会话
            
        Returns:
            (响应数据, 错误消息) 元组
        """
        client = self._get_client()
        
        # 使用默认值
        agent = agent or client.default_agent
        model = model or client.default_model
        provider = provider or client.default_provider
        
        # 解析模型字符串（如果提供的是组合格式）
        if model and "/" in model:
            parsed_provider, parsed_model = client.parse_model_string(model)
            model = parsed_model
            if not provider:
                provider = parsed_provider
        elif not provider:
            if model and model.startswith("deepseek-"):
                provider = "deepseek"
            else:
                provider = provider or client.default_provider
        
        # 检查会话 ID
        if not session_id:
            if create_if_not_exists:
                # 导入 SessionAPI 创建会话
                from .session_api import SessionAPI
                session_api = SessionAPI(client)
                session_id, error = await session_api.create_session()
                if error:
                    return None, f"创建会话失败: {error}"
            else:
                return None, "未提供会话 ID 且 create_if_not_exists=False"
        
        # 构建消息载荷
        payload = {
            "agent": agent,
            "model": {
                "modelID": model,
                "providerID": provider
            },
            "parts": [{
                "type": "text",
                "text": message_text
            }]
        }
        
        # 构建额外请求头
        extra_headers = {}
        if directory:
            directory_b64 = base64.b64encode(directory.encode()).decode()
            referer = f"{client.base_url}/{directory_b64}/session/{session_id}"
            extra_headers["Referer"] = referer
            extra_headers["x-opencode-directory"] = directory
        
        # 发送消息
        data, error = await client._send_request(
            method="POST",
            endpoint=f"/session/{session_id}/message",
            json_data=payload,
            extra_headers=extra_headers if extra_headers else None
        )
        
        if error:
            return None, error
        
        # 添加会话 ID 到响应中
        if isinstance(data, dict) and "session_id" not in data:
            data["session_id"] = session_id
        
        logger.info(f"发送消息成功，会话: {session_id}, 长度: {len(message_text)}字符")
        return data, None
    
    async def execute_command(
        self,
        session_id: str,
        command: str,
        message_id: Optional[str] = None,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        arguments: Optional[str] = "",
        directory: Optional[str] = None
    ) -> RequestResult:
        """
        在指定会话中执行斜杠命令
        
        Args:
            session_id: 会话 ID
            command: 命令名称（如 /git, /refactor 等，会自动去除 / 前缀）
            message_id: 消息 ID（可选）
            agent: 智能体名称（可选）
            model: 模型 ID（可选）
            provider: 提供商 ID（可选）
            arguments: 命令参数（可选，默认为空字符串）
            directory: 工作目录（可选）
            
        Returns:
            (响应数据, 错误消息) 元组
        """
        client = self._get_client()
        
        # 去除命令的 / 前缀
        if command.startswith("/"):
            command = command[1:]
        
        # 使用传入的 provider 和 model
        model_str = model or client.default_model
        provider_str = provider or client.default_provider
        
        # 如果没有传入 provider，尝试从 model 字符串解析
        if not provider_str and "/" in model_str:
            provider_str, model_str = client.parse_model_string(model_str)
        
        # 构建 model 字符串
        if provider_str and model_str:
            model_value = f"{provider_str}/{model_str}"
        else:
            model_value = model_str or provider_str or ""
        
        # 构建请求体
        payload = {
            "command": command,
            "arguments": arguments or "",
            "agent": agent or client.default_agent,
            "model": model_value,
            "parts": []
        }
        
        if message_id:
            payload["messageID"] = message_id
        
        # 构建额外请求头
        extra_headers = None
        if directory or client.directory:
            work_directory = directory or client.directory
            directory_b64 = base64.b64encode(work_directory.encode()).decode()
            extra_headers = {
                "Referer": f"{client.base_url}/{directory_b64}/session/{session_id}",
                "x-opencode-directory": work_directory
            }
        
        data, error = await client._send_request(
            method="POST",
            endpoint=f"/session/{session_id}/command",
            json_data=payload,
            extra_headers=extra_headers
        )
        
        if error:
            return None, error
        
        logger.info(f"执行命令成功：{command}，会话：{session_id}")
        return data, None