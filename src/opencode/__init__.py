#!/usr/bin/env python3
"""
OpenCode 客户端模块
提供与 OpenCode HTTP 服务器交互的异步 Python 客户端
"""

# 主客户端类（向后兼容）
from .opencode_client import OpenCodeClient, OpenCodeClientSync

# 核心客户端
from .client import OpenCodeClient as BaseOpenCodeClient

# API 模块
from .session_api import SessionAPI
from .message_api import MessageAPI
from .model_api import ModelAPI

# 类型定义
from .types import (
    SessionInfo,
    MessageResult,
    ModelInfo,
    AgentInfo,
    CommandInfo,
    ClientConfig,
    RequestResult,
    SessionResult,
    BoolResult,
    ListResult,
)

__all__ = [
    # 主客户端
    "OpenCodeClient",
    "OpenCodeClientSync",
    "BaseOpenCodeClient",
    # API 模块
    "SessionAPI",
    "MessageAPI",
    "ModelAPI",
    # 类型
    "SessionInfo",
    "MessageResult",
    "ModelInfo",
    "AgentInfo",
    "CommandInfo",
    "ClientConfig",
    "RequestResult",
    "SessionResult",
    "BoolResult",
    "ListResult",
]