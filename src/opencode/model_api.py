#!/usr/bin/env python3
"""
OpenCode 模型/智能体 API
提供模型和智能体查询相关的 API 方法
"""

import logging
from typing import Dict, List, Optional, Tuple

from .types import ListResult

logger = logging.getLogger(__name__)


class ModelAPI:
    """模型/智能体 API"""
    
    def __init__(self, client):
        """
        初始化模型 API
        
        Args:
            client: OpenCodeClient 实例
        """
        self._client = client
    
    def _get_client(self):
        """获取客户端实例"""
        return self._client
    
    async def get_models(self) -> ListResult:
        """
        获取可用模型列表
        
        Returns:
            (模型列表, 错误消息) 元组
        """
        client = self._get_client()
        
        # 尝试获取 providers 配置
        data, error = await client._send_request(
            method="GET",
            endpoint="/config/providers"
        )
        
        if error:
            return None, error
        
        # 解析模型列表
        models = []
        if isinstance(data, dict) and "providers" in data:
            for provider in data["providers"]:
                provider_id = provider.get("id") if isinstance(provider, dict) else ""
                provider_name = provider.get("name", provider_id) if isinstance(provider, dict) else str(provider_id)
                
                provider_models = provider.get("models") if isinstance(provider, dict) else None
                
                if isinstance(provider_models, dict):
                    # 字典格式: {"model-id": {model_data}, ...}
                    for model_id, model_data in provider_models.items():
                        if isinstance(model_data, dict):
                            models.append({
                                "provider_id": provider_id,
                                "provider_name": provider_name,
                                "model_id": model_id,
                                "model_name": model_data.get("name", model_id),
                                "description": model_data.get("description", ""),
                                "context_length": model_data.get("limit", {}).get("context"),
                                "max_output_tokens": model_data.get("limit", {}).get("output"),
                            })
                        else:
                            models.append({
                                "provider_id": provider_id,
                                "provider_name": provider_name,
                                "model_id": str(model_id),
                                "model_name": str(model_id),
                            })
                elif isinstance(provider_models, list):
                    # 列表格式: [{model_data}, ...]
                    for model in provider_models:
                        if isinstance(model, dict):
                            model_id = model.get("id", "")
                            models.append({
                                "provider_id": provider_id,
                                "provider_name": provider_name,
                                "model_id": model_id,
                                "model_name": model.get("name", model_id),
                                "description": model.get("description", ""),
                                "context_length": model.get("contextLength"),
                                "max_output_tokens": model.get("maxOutputTokens"),
                            })
        
        return models, None
    
    async def get_agents(self) -> ListResult:
        """
        获取可用智能体列表
        
        Returns:
            (智能体列表, 错误消息) 元组
        """
        client = self._get_client()
        
        data, error = await client._send_request(
            method="GET",
            endpoint="/agent"
        )
        
        if error:
            return None, error
        
        # 如果返回的是列表，直接返回
        if isinstance(data, list):
            return data, None
        
        # 否则尝试解析
        agents = []
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    agents.append({
                        "id": key,
                        "name": value.get("name", key),
                        "description": value.get("description", "")
                    })
                else:
                    agents.append({
                        "id": key,
                        "name": key,
                        "description": str(value)
                    })
        
        return agents, None
    
    async def list_commands(self) -> ListResult:
        """
        获取可用的斜杠命令列表
        
        Returns:
            (命令列表, 错误消息) 元组
        """
        client = self._get_client()
        
        data, error = await client._send_request(
            method="GET",
            endpoint="/command"
        )
        
        if error:
            return None, error
        
        # 如果返回的是列表，直接返回
        if isinstance(data, list):
            return data, None
        
        # 否则尝试解析
        commands = []
        if isinstance(data, dict):
            if "commands" in data:
                commands = data["commands"]
            else:
                # 可能是单个命令对象
                commands = [data]
        
        return commands, None