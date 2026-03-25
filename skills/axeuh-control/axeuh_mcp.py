#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Axeuh Control MCP Server
Bot控制MCP服务器
"""
import os
import sys
import threading

# 添加当前目录到路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from mcp.server.fastmcp import FastMCP
from bot_client import BotClient

# 创建MCP服务器
mcp = FastMCP("axeuh-control")

# 初始化客户端
bot_client = BotClient()


# ============================================================
# 用户会话管理 (QQ用户到OpenCode会话的映射, 端口4090)
# ============================================================

@mcp.tool()
def user_session_list(user_id: int) -> str:
    """获取用户的会话映射列表(QQ用户到OpenCode会话的映射)
    
    Args:
        user_id: 用户QQ号
        
    Returns:
        用户会话映射列表
    """
    result = bot_client.list_user_sessions(user_id)
    if result.get("success"):
        # 新格式: sessions数组
        sessions = result.get("sessions", [])
        count = result.get("count", len(sessions))
        
        output = f"用户 {user_id} 的会话映射:\n"
        output += f"\n会话列表 ({count}个):\n"
        
        for s in sessions[:15]:
            title = s.get('title', '无标题')
            session_id = s.get('session_id', '未知')
            output += f"  - {title} (ID: {session_id})\n"
        
        if len(sessions) > 15:
            output += f"  ... 还有 {len(sessions) - 15} 个\n"
        return output
    return f"错误: {result.get('error', '未知错误')}"


@mcp.tool()
def user_session_create(user_id: int, title: str = None) -> str:
    """为用户创建新会话映射
    
    Args:
        user_id: 用户QQ号
        title: 会话标题(可选)
        
    Returns:
        创建结果
    """
    result = bot_client.create_user_session(user_id, title)
    if result.get("success"):
        session_id = result.get("session_id", "unknown")
        return f"用户会话创建成功\n用户ID: {user_id}\n会话ID: {session_id}"
    return f"错误: {result.get('error', '未知错误')}"


@mcp.tool()
def user_session_switch(user_id: int, session_id: str) -> str:
    """切换用户的当前会话
    
    Args:
        user_id: 用户QQ号
        session_id: 目标OpenCode会话ID
        
    Returns:
        切换结果
    """
    result = bot_client.switch_user_session(user_id, session_id)
    if result.get("success"):
        return f"用户 {user_id} 已切换到会话 {session_id}"
    return f"错误: {result.get('error', '未知错误')}"


@mcp.tool()
def user_session_delete(user_id: int, session_id: str) -> str:
    """删除用户的会话映射
    
    Args:
        user_id: 用户QQ号
        session_id: OpenCode会话ID
        
    Returns:
        删除结果
    """
    result = bot_client.delete_user_session(user_id, session_id)
    if result.get("success"):
        return f"用户 {user_id} 的会话 {session_id} 已删除"
    return f"错误: {result.get('error', '未知错误')}"


@mcp.tool()
def session_title_set(user_id: int, session_id: str, title: str) -> str:
    """设置会话标题
    
    Args:
        user_id: 用户QQ号
        session_id: OpenCode会话ID
        title: 新标题
        
    Returns:
        设置结果
    """
    result = bot_client.set_session_title(user_id, session_id, title)
    if result.get("success"):
        return f"会话标题已更新\n会话ID: {session_id}\n新标题: {title}"
    return f"错误: {result.get('error', '未知错误')}"


# ============================================================
# 任务管理 (端口4090)
# ============================================================

@mcp.tool()
def task_list(user_id: int) -> str:
    """获取用户任务列表
    
    Args:
        user_id: 用户QQ号
        
    Returns:
        任务列表
    """
    result = bot_client.list_tasks(user_id)
    if result.get("success"):
        tasks = result.get("tasks", [])
        if not tasks:
            return f"用户 {user_id} 没有任务"
        output = f"用户 {user_id} 的任务列表 ({len(tasks)}个):\n"
        for t in tasks:
            output += f"  - {t.get('task_name')} (ID: {t.get('task_id')})\n"
            output += f"    提示词: {t.get('prompt', '')[:30]}...\n"
        return output
    return f"错误: {result.get('error', '未知错误')}"


@mcp.tool()
def task_create(
    user_id: int, 
    session_id: str, 
    name: str, 
    prompt: str,
    schedule_type: str,
    schedule_config: dict
) -> str:
    """创建定时任务
    
    Args:
        user_id: 用户QQ号
        session_id: OpenCode会话ID
        name: 任务名称
        prompt: 任务提示词
        schedule_type: 计划类型 (delay/scheduled)
        schedule_config: 计划配置
        
    Returns:
        创建结果
    """
    result = bot_client.create_task(user_id, session_id, name, prompt, schedule_type, schedule_config)
    if result.get("success"):
        task_id = result.get("task", {}).get("task_id", "unknown")
        return f"任务创建成功\nID: {task_id}\n名称: {name}"
    return f"错误: {result.get('error', '未知错误')}"


@mcp.tool()
def task_delete(user_id: int, task_id: str) -> str:
    """删除任务
    
    Args:
        user_id: 用户QQ号
        task_id: 任务ID
        
    Returns:
        删除结果
    """
    result = bot_client.delete_task(user_id, task_id)
    if result.get("success"):
        return f"任务 {task_id} 已删除"
    return f"错误: {result.get('error', '未知错误')}"


# ============================================================
# 智能体管理 (端口4090)
# ============================================================

@mcp.tool()
def agent_list() -> str:
    """获取可用智能体列表
    
    Returns:
        智能体列表
    """
    result = bot_client.list_agents()
    if result.get("success"):
        agents = result.get("agents", [])
        if not agents:
            return "没有可用的智能体"
        output = "可用智能体:\n"
        for a in agents:
            if isinstance(a, dict):
                name = a.get("name") or a.get("id", "unknown")
            else:
                name = str(a)
            output += f"  - {name}\n"
        return output
    return f"错误: {result.get('error', '未知错误')}"


@mcp.tool()
def agent_get(user_id: int) -> str:
    """获取用户当前智能体
    
    Args:
        user_id: 用户QQ号
        
    Returns:
        当前智能体名称
    """
    result = bot_client.get_agent(user_id)
    if result.get("success"):
        agent = result.get("agent", "unknown")
        return f"用户 {user_id} 当前智能体: {agent}"
    return f"错误: {result.get('error', '未知错误')}"


@mcp.tool()
def agent_set(user_id: int, agent: str) -> str:
    """设置用户智能体
    
    Args:
        user_id: 用户QQ号
        agent: 智能体名称
        
    Returns:
        设置结果
    """
    result = bot_client.set_agent(user_id, agent)
    if result.get("success"):
        return f"用户 {user_id} 智能体已设置为: {agent}"
    return f"错误: {result.get('error', '未知错误')}"


# ============================================================
# 模型管理 (端口4090)
# ============================================================

@mcp.tool()
def model_list() -> str:
    """获取可用模型列表
    
    Returns:
        模型列表
    """
    result = bot_client.list_models()
    if result.get("success"):
        models = result.get("models", [])
        if not models:
            return "没有可用的模型"
        output = f"可用模型 ({len(models)}个):\n"
        for m in models[:20]:
            # 模型可能是字符串格式 (provider/model_id) 或对象格式
            if isinstance(m, str):
                output += f"  - {m}\n"
            else:
                output += f"  - {m.get('id')} ({m.get('provider', 'unknown')})\n"
        if len(models) > 20:
            output += f"  ... 还有 {len(models) - 20} 个\n"
        return output
    return f"错误: {result.get('error', '未知错误')}"


@mcp.tool()
def model_get(user_id: int) -> str:
    """获取用户当前模型
    
    Args:
        user_id: 用户QQ号
        
    Returns:
        当前模型名称
    """
    result = bot_client.get_model(user_id)
    if result.get("success"):
        model = result.get("model", "unknown")
        provider = result.get("provider", "")
        # 组合完整模型名称: provider/model
        if provider and model:
            full_model = f"{provider}/{model}"
        else:
            full_model = model
        return f"用户 {user_id} 当前模型: {full_model}"
    return f"错误: {result.get('error', '未知错误')}"


@mcp.tool()
def model_set(user_id: int, model: str) -> str:
    """设置用户模型
    
    Args:
        user_id: 用户QQ号
        model: 模型名称
        
    Returns:
        设置结果
    """
    result = bot_client.set_model(user_id, model)
    if result.get("success"):
        return f"用户 {user_id} 模型已设置为: {model}"
    return f"错误: {result.get('error', '未知错误')}"


# ============================================================
# 系统管理 (端口4090)
# ============================================================

@mcp.tool()
def system_health() -> str:
    """检查Bot服务器健康状态
    
    Returns:
        健康状态
    """
    result = bot_client.health()
    if result.get("status") == "ok":
        return "Bot服务器状态: 正常"
    return f"Bot服务器状态: {result}"


@mcp.tool()
def system_restart_opencode() -> str:
    """重启OpenCode进程
    
    Returns:
        重启结果
    """
    # 使用线程发送请求，不等待响应（因为重启会中断连接）
    def _send_restart():
        try:
            bot_client.restart_opencode()
        except:
            pass
    
    threading.Thread(target=_send_restart, daemon=True).start()
    return "OpenCode重启命令已发送"


@mcp.tool()
def system_restart_bot() -> str:
    """重启Bot进程
    
    Returns:
        重启结果
    """
    result = bot_client.restart_bot()
    if result.get("success"):
        return "Bot重启成功"
    return f"错误: {result.get('error', '未知错误')}"


# ============================================================
# 工作目录管理 (端口4090)
# ============================================================

@mcp.tool()
def directory_get(user_id: int) -> str:
    """获取用户工作目录
    
    Args:
        user_id: 用户QQ号
        
    Returns:
        用户当前工作目录
    """
    result = bot_client.get_directory(user_id)
    if result.get("success"):
        directory = result.get("directory", "/")
        return f"用户 {user_id} 当前工作目录: {directory}"
    return f"错误: {result.get('error', '未知错误')}"


@mcp.tool()
def directory_set(user_id: int, directory: str) -> str:
    """设置用户工作目录
    
    Args:
        user_id: 用户QQ号
        directory: 工作目录路径
        
    Returns:
        设置结果
    """
    result = bot_client.set_directory(user_id, directory)
    if result.get("success"):
        return f"用户 {user_id} 工作目录已设置为: {directory}"
    return f"错误: {result.get('error', '未知错误')}"


if __name__ == "__main__":
    mcp.run()