#!/usr/bin/env python3
"""
命令系统模块 - 处理 QQ 机器人命令

此文件为向后兼容层，实际实现已迁移到 src/core/command/ 目录。
"""

from __future__ import annotations

# 从新模块导入所有内容
from src.core.command import (
    CommandSystem,
    HelpHandler,
    SessionHandler,
    ModelHandler,
    TaskHandler,
    MessageHandler,
    parse_command,
    is_command,
    validate_session_id,
    get_session_id_by_index,
    format_session_list,
    format_model_list,
    format_agent_list,
    match_model_by_input,
    match_agent_by_input,
)

__all__ = [
    'CommandSystem',
    'HelpHandler',
    'SessionHandler',
    'ModelHandler',
    'TaskHandler',
    'MessageHandler',
    'parse_command',
    'is_command',
    'validate_session_id',
    'get_session_id_by_index',
    'format_session_list',
    'format_model_list',
    'format_agent_list',
    'match_model_by_input',
    'match_agent_by_input',
]