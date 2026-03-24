#!/usr/bin/env python3
"""
命令工具函数模块
"""

from __future__ import annotations

import time
from typing import Tuple, Optional, Any, List, Dict

from src.utils import config


def parse_command(message: str) -> Tuple[str, str]:
    """从消息中提取命令和参数
    
    Args:
        message: 原始消息内容
        
    Returns:
        (命令名, 参数) 元组
    """
    if not message:
        return "", ""
    
    message = message.strip()
    if not message.startswith(config.OPENCODE_COMMAND_PREFIX):
        return "", message
    
    # 移除命令前缀
    message = message[len(config.OPENCODE_COMMAND_PREFIX):]
    
    parts = message.split(maxsplit=1)
    if len(parts) == 0:
        return "", ""
    elif len(parts) == 1:
        return parts[0], ""
    else:
        return parts[0], parts[1].strip()


def is_command(plain_text: str) -> bool:
    """检查消息是否为命令
    
    Args:
        plain_text: 纯文本消息
        
    Returns:
        是否为命令
    """
    if not plain_text:
        return False
    return plain_text.strip().startswith(config.OPENCODE_COMMAND_PREFIX)


def validate_session_id(session_id: str) -> bool:
    """验证会话 ID 格式
    
    Args:
        session_id: 会话 ID
        
    Returns:
        是否有效
    """
    if not session_id:
        return False
    return session_id.startswith("ses_")


def get_session_id_by_index(
    session_manager: Any, 
    user_id: int, 
    index_str: str
) -> Optional[str]:
    """通过序号获取会话 ID
    
    Args:
        session_manager: 会话管理器实例
        user_id: 用户 ID
        index_str: 序号字符串
        
    Returns:
        会话 ID 或 None
    """
    if not session_manager:
        return None
    try:
        index = int(index_str)
        history = session_manager.get_user_session_history(user_id)
        # 按最后访问时间倒序排列
        sorted_history = sorted(
            history, 
            key=lambda x: x.get("last_accessed", x.get("created_at", 0)), 
            reverse=True
        )
        if 1 <= index <= len(sorted_history):
            return sorted_history[index - 1].get("session_id")
        return None
    except (ValueError, IndexError):
        return None


def format_session_list(
    history: List[Dict], 
    current_session_id: Optional[str] = None
) -> str:
    """格式化会话列表
    
    Args:
        history: 会话历史列表
        current_session_id: 当前会话 ID
        
    Returns:
        格式化的会话列表文本
    """
    if not history:
        return "暂无会话历史，使用 /new 创建新会话。"
    
    # 按最后访问时间倒序排列
    sorted_history = sorted(
        history, 
        key=lambda x: x.get("last_accessed", x.get("created_at", 0)), 
        reverse=True
    )
    
    reply = "当前会话列表（按最后访问时间倒序）:\n"
    for i, session_info in enumerate(sorted_history, 1):
        session_id = session_info.get("session_id", "未知")
        title = session_info.get("title", "无标题")
        last_accessed = session_info.get("last_accessed", session_info.get("created_at", 0))
        time_str = time.strftime("%m/%d %H:%M", time.localtime(last_accessed))
        marker = " *" if current_session_id and current_session_id == session_id else ""
        reply += f"{i}. {title} [{time_str}]{marker}\n"
    
    return reply


def format_model_list(
    models: List[str], 
    current_model: str
) -> str:
    """格式化模型列表
    
    Args:
        models: 模型列表
        current_model: 当前模型
        
    Returns:
        格式化的模型列表文本
    """
    models_list = []
    current_index = 0
    for i, m in enumerate(models, 1):
        marker = " *" if m == current_model else ""
        models_list.append(f"  {i}. {m}{marker}")
        if m == current_model:
            current_index = i
    models_text = "\n".join(models_list)
    
    reply = (
        f"当前模型：{current_model}"
        + (f" (序号 {current_index})" if current_index > 0 else "")
        + f"\n\n可用的模型:\n{models_text}\n\n"
        + "使用方法：/model [序号] 或 /model [模型名称]\n"
        + "示例：/model 1 或 /model deepseek/deepseek-reasoner"
    )
    return reply


def format_agent_list(
    agents: List[str], 
    current_agent: str
) -> str:
    """格式化智能体列表
    
    Args:
        agents: 智能体列表
        current_agent: 当前智能体
        
    Returns:
        格式化的智能体列表文本
    """
    agents_list = []
    current_index = 0
    for i, a in enumerate(agents, 1):
        marker = " *" if a == current_agent else ""
        agents_list.append(f"  {i}. {a}{marker}")
        if a == current_agent:
            current_index = i
    agents_text = "\n".join(agents_list)
    
    reply = (
        f"当前智能体：{current_agent}"
        + (f" (序号 {current_index})" if current_index > 0 else "")
        + f"\n\n可用的智能体:\n{agents_text}\n\n"
        + "使用方法：/agent [序号] 或 /agent [智能体名称]\n"
        + "示例：/agent 1 或 /agent sisyphus"
    )
    return reply


def match_model_by_input(
    models: List[str], 
    model_input: str
) -> Optional[str]:
    """根据用户输入匹配模型
    
    Args:
        models: 模型列表
        model_input: 用户输入（序号或名称）
        
    Returns:
        匹配的模型名称或 None
    """
    if not models:
        return None
    
    # 检查是否为序号
    if model_input.isdigit():
        index = int(model_input)
        if 1 <= index <= len(models):
            return models[index - 1]
        return None
    
    # 精确匹配
    if model_input in models:
        return model_input
    
    # 不区分大小写匹配
    for m in models:
        if m.lower() == model_input.lower():
            return m
    
    # 匹配模型名称的最后一部分
    for m in models:
        parts = m.split("/")
        if len(parts) >= 2 and parts[-1].lower() == model_input.lower():
            return m
    
    return None


def match_agent_by_input(
    agents: List[str], 
    agent_input: str
) -> Optional[str]:
    """根据用户输入匹配智能体
    
    Args:
        agents: 智能体列表
        agent_input: 用户输入（序号或名称）
        
    Returns:
        匹配的智能体名称或 None
    """
    if not agents:
        return None
    
    # 检查是否为序号
    if agent_input.isdigit():
        index = int(agent_input)
        if 1 <= index <= len(agents):
            return agents[index - 1]
        return None
    
    # 精确匹配
    if agent_input in agents:
        return agent_input
    
    # 不区分大小写匹配
    for a in agents:
        if a.lower() == agent_input.lower():
            return a
    
    return None