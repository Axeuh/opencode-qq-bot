#!/usr/bin/env python3
"""
任务命令处理器模块 - 处理 /command, /reload 命令
"""

from __future__ import annotations

import logging
from typing import Optional, Callable, Any, List, Dict

from .utils import get_session_id_by_index

logger = logging.getLogger(__name__)


class TaskHandler:
    """任务命令处理器"""
    
    def __init__(
        self,
        session_manager: Optional[Any] = None,
        opencode_client: Optional[Any] = None,
        send_reply_callback: Optional[Callable[[str, Optional[int], Optional[int], str], Any]] = None,
        hot_reload_callback: Optional[Callable[[], Any]] = None
    ):
        self.session_manager = session_manager
        self.opencode_client = opencode_client
        self.send_reply_callback = send_reply_callback
        self.hot_reload_callback = hot_reload_callback
    
    async def send_reply(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        reply: str
    ) -> None:
        """发送回复消息"""
        if self.send_reply_callback:
            await self.send_reply_callback(message_type, group_id, user_id, reply)
    
    # ==================== /reload 命令 ====================
    
    async def handle_reload(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /reload 命令 - 热重载代码和配置"""
        if self.hot_reload_callback:
            reply = "正在执行热重载..."
            await self.send_reply(message_type, group_id, user_id, reply)
            
            try:
                result = await self.hot_reload_callback()
                if result.get("success", False):
                    modules_count = len(result.get("modules_reload", []))
                    reply = f"热重载完成\n配置: {'成功' if result.get('config_reload') else '失败'}\n模块: {modules_count} 个已重载"
                    if result.get("errors"):
                        reply += f"\n警告: {len(result['errors'])} 个错误"
                else:
                    reply = f"热重载失败: {result.get('error', '未知错误')}"
            except Exception as e:
                reply = f"热重载异常: {str(e)}"
        else:
            reply = "热重载回调未配置"
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    # ==================== /command 命令 ====================
    
    async def handle_command(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /command 命令 - 列出或执行斜杠命令"""
        if not user_id:
            await self.send_reply(message_type, group_id, user_id, "无法识别用户。")
            return
        
        if not self.session_manager or not self.opencode_client:
            await self.send_reply(message_type, group_id, user_id, "OpenCode 集成不可用。")
            return
        
        args_lower = args.strip().lower()
        
        # 显示帮助
        if args_lower == "help":
            await self._show_command_help(message_type, group_id, user_id)
            return
        
        # 列出可用命令
        if not args or args_lower == "list":
            await self._list_commands(message_type, group_id, user_id)
            return
        
        # 解析参数
        parts = args.strip().split(maxsplit=1)
        
        # 检查是否以数字开头（通过序号执行命令）
        if parts and parts[0].isdigit():
            await self._execute_by_index(message_type, group_id, user_id, parts)
            return
        
        # 原有格式：/command [会话 ID] [命令]
        await self._execute_by_session_id(message_type, group_id, user_id, args)
    
    async def _show_command_help(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int
    ) -> None:
        """显示命令帮助"""
        help_text = (
            "斜杠命令帮助\n\n"
            "可用格式:\n"
            "  /command - 列出所有可用的斜杠命令\n"
            "  /command [序号] - 执行对应序号的命令\n"
            "  /command [会话 ID] [命令] - 在指定会话中执行指定命令\n\n"
            "说明:\n"
            "* 序号来自 /command 显示的命令列表\n"
            "* 会话 ID 格式为 ses_xxxxxxxxxxxxx"
        )
        await self.send_reply(message_type, group_id, user_id, help_text)
    
    async def _list_commands(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int
    ) -> None:
        """列出可用命令"""
        commands, error = await self.opencode_client.list_commands()
        
        if error:
            await self.send_reply(message_type, group_id, user_id, f"获取命令列表失败：{error}")
            return
        
        if not commands:
            await self.send_reply(message_type, group_id, user_id, "当前没有可用的斜杠命令。")
            return
        
        # 格式化命令列表
        reply = "可用的斜杠命令:\n"
        for i, cmd in enumerate(commands, 1):
            if isinstance(cmd, dict):
                cmd_name = cmd.get("name", cmd.get("command", "未知"))
                reply += f"  {i}. {cmd_name}\n"
            else:
                reply += f"  {i}. {cmd}\n"
        
        reply += "\n使用方法：/command [序号] [参数]"
        await self.send_reply(message_type, group_id, user_id, reply)
    
    async def _execute_by_index(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        parts: list
    ) -> None:
        """通过序号执行命令"""
        command_index = int(parts[0])
        command_args = parts[1] if len(parts) > 1 else ""
        
        # 获取命令列表
        commands, error = await self.opencode_client.list_commands()
        
        if error:
            await self.send_reply(message_type, group_id, user_id, f"获取命令列表失败：{error}")
            return
        
        if not commands:
            await self.send_reply(message_type, group_id, user_id, "当前没有可用的斜杠命令。")
            return
        
        # 验证序号范围
        if command_index < 1 or command_index > len(commands):
            await self.send_reply(message_type, group_id, user_id, 
                f"无效的序号：{command_index}（有效范围：1-{len(commands)}）")
            return
        
        # 获取命令名称
        cmd = commands[command_index - 1]
        if isinstance(cmd, dict):
            command = cmd.get("name", cmd.get("command", ""))
        else:
            command = str(cmd)
        
        # 确保命令以/开头
        if not command.startswith("/"):
            command = "/" + command
        
        # 获取用户的活跃会话
        user_session = self.session_manager.get_user_session(user_id)
        if not user_session:
            await self.send_reply(message_type, group_id, user_id, "没有活跃的会话，请先使用 /new 创建会话。")
            return
        
        # 执行命令
        await self._execute_opencode_command(
            message_type, group_id, user_id,
            user_session.session_id,
            command,
            user_session.agent,
            user_session.model,
            user_session.provider,
            command_args
        )
    
    async def _execute_by_session_id(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        args: str
    ) -> None:
        """通过会话 ID 执行命令"""
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            await self.send_reply(message_type, group_id, user_id, 
                "格式错误\n用法：\n  /command [序号] - 执行对应序号的命令\n  /command [会话 ID] [命令] - 在指定会话执行命令")
            return
        
        session_target, command = parts[0], parts[1]
        
        # 验证命令格式
        if not command.startswith("/"):
            await self.send_reply(message_type, group_id, user_id, f"命令应以/开头：{command}")
            return
        
        # 解析会话 ID
        session_id = await self._resolve_session_id(message_type, group_id, user_id, session_target)
        if not session_id:
            return  # 错误已处理
        
        # 获取用户的 agent 和 model 配置
        user_session = self.session_manager.get_user_session(user_id)
        agent = user_session.agent if user_session else None
        model = user_session.model if user_session else None
        provider = user_session.provider if user_session else None
        
        # 执行命令
        await self._execute_opencode_command(
            message_type, group_id, user_id,
            session_id, command, agent, model, provider, ""
        )
    
    async def _resolve_session_id(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        session_target: str
    ) -> Optional[str]:
        """解析会话 ID"""
        if session_target.startswith("ses_"):
            return session_target
        
        # 尝试作为序号解析
        session_id = get_session_id_by_index(self.session_manager, user_id, session_target)
        if not session_id:
            await self.send_reply(message_type, group_id, user_id, f"无效的会话 ID 或序号：{session_target}")
            return None
        
        return session_id
    
    async def _execute_opencode_command(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int,
        session_id: str,
        command: str,
        agent: Optional[str],
        model: Optional[str],
        provider: Optional[str],
        command_args: str
    ) -> None:
        """执行 OpenCode 命令"""
        try:
            result, error = await self.opencode_client.execute_command(
                session_id=session_id,
                command=command,
                agent=agent,
                model=model,
                provider=provider,
                arguments=command_args
            )
            
            if error:
                await self.send_reply(message_type, group_id, user_id, f"执行命令失败：{error}")
                return
            
            # 返回执行结果
            if result:
                await self._send_command_result(message_type, group_id, user_id, command, command_args, result)
            else:
                reply = f"命令已发送\n命令：{command}"
                if command_args:
                    reply += f"\n参数：{command_args}"
                await self.send_reply(message_type, group_id, user_id, reply)
                
        except Exception as e:
            logger.error(f"执行斜杠命令失败：{e}")
            await self.send_reply(message_type, group_id, user_id, f"执行失败：{str(e)}")
    
    async def _send_command_result(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int,
        command: str,
        command_args: str,
        result: Dict
    ) -> None:
        """发送命令执行结果"""
        result_parts = result.get("parts", [])
        
        reply = f"命令执行成功\n命令：{command}"
        if command_args:
            reply += f"\n参数：{command_args}"
        reply += "\n"
        
        # 提取响应文本
        for part in result_parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
                if text:
                    reply += f"\n响应：{text[:500]}"
                    if len(text) > 500:
                        reply += "..."
                    break
        
        await self.send_reply(message_type, group_id, user_id, reply)