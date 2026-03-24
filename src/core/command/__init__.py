#!/usr/bin/env python3
"""
命令系统模块

提供命令处理功能，包括：
- CommandSystem: 命令系统主类
- HelpHandler: 帮助命令处理器
- SessionHandler: 会话命令处理器
- ModelHandler: 模型/智能体命令处理器
- TaskHandler: 任务命令处理器
- MessageHandler: 消息操作命令处理器
"""

from .command_system import CommandSystem
from .help_handler import HelpHandler
from .session_handler import SessionHandler
from .model_handler import ModelHandler
from .task_handler import TaskHandler
from .message_handler import MessageHandler
from .utils import (
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
    # 主类
    'CommandSystem',
    
    # 处理器
    'HelpHandler',
    'SessionHandler',
    'ModelHandler',
    'TaskHandler',
    'MessageHandler',
    
    # 工具函数
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