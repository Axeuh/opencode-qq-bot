#!/usr/bin/env python3
"""
OpenCode 类型定义
定义 OpenCode 客户端使用的类型和数据类
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class SessionInfo:
    """会话信息"""
    session_id: str
    created_at: str = ""
    title: Optional[str] = None
    model: Optional[str] = None
    agent: Optional[str] = None
    provider: Optional[str] = None
    directory: Optional[str] = None


@dataclass
class MessageResult:
    """消息发送结果"""
    success: bool
    response: Optional[Dict] = None
    error: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class ModelInfo:
    """模型信息"""
    provider_id: str
    provider_name: str
    model_id: str
    model_name: str
    description: str = ""
    context_length: Optional[int] = None
    max_output_tokens: Optional[int] = None


@dataclass
class AgentInfo:
    """智能体信息"""
    id: str
    name: str
    description: str = ""


@dataclass
class CommandInfo:
    """命令信息"""
    name: str
    description: str = ""


@dataclass
class ClientConfig:
    """OpenCode 客户端配置"""
    base_url: str = "http://127.0.0.1:4091"
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    directory: str = "/"
    timeout: int = 120
    default_agent: str = "Sisyphus (Ultraworker)"
    default_model: str = "alibaba-coding-plan-cn/qwen3.5-plus"
    default_provider: str = ""
    cookies: Dict[str, str] = field(default_factory=dict)
    enable_ntfy: bool = False
    ntfy_topic: str = "aaa"


# 类型别名
RequestResult = Tuple[Optional[Dict], Optional[str]]
SessionResult = Tuple[Optional[str], Optional[str]]
BoolResult = Tuple[bool, Optional[str]]
ListResult = Tuple[Optional[List[Dict]], Optional[str]]