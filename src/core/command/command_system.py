#!/usr/bin/env python3
"""
命令系统模块 - 处理 QQ 机器人命令

重构后的版本，使用组合模式将命令处理委托给专门的处理器。
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Any, Callable

from src.utils import config

from .utils import parse_command, is_command
from .help_handler import HelpHandler
from .session_handler import SessionHandler
from .model_handler import ModelHandler
from .task_handler import TaskHandler
from .message_handler import MessageHandler

logger = logging.getLogger(__name__)


class CommandSystem:
    """命令系统，处理所有机器人命令
    
    使用组合模式将命令处理委托给专门的处理器：
    - HelpHandler: /help 命令
    - SessionHandler: /new, /session, /stop, /path 命令
    - ModelHandler: /agent, /model 命令
    - TaskHandler: /command, /reload 命令
    - MessageHandler: /undo, /redo, /compact 命令
    """
    
    def __init__(
        self,
        session_manager: Optional[Any] = None,
        opencode_client: Optional[Any] = None,
        send_reply_callback: Optional[Callable[[str, Optional[int], Optional[int], str], Any]] = None,
        hot_reload_callback: Optional[Callable[[], Any]] = None
    ):
        """初始化命令系统
        
        Args:
            session_manager: 会话管理器实例
            opencode_client: OpenCode 客户端实例
            send_reply_callback: 发送回复的回调函数
            hot_reload_callback: 热重载回调函数
        """
        self.session_manager = session_manager
        self.opencode_client = opencode_client
        self.send_reply_callback = send_reply_callback
        self.hot_reload_callback = hot_reload_callback
        
        # 初始化各处理器
        self.help_handler = HelpHandler(send_reply_callback=send_reply_callback)
        
        self.session_handler = SessionHandler(
            session_manager=session_manager,
            opencode_client=opencode_client,
            send_reply_callback=send_reply_callback
        )
        
        self.model_handler = ModelHandler(
            session_manager=session_manager,
            opencode_client=opencode_client,
            send_reply_callback=send_reply_callback
        )
        
        self.task_handler = TaskHandler(
            session_manager=session_manager,
            opencode_client=opencode_client,
            send_reply_callback=send_reply_callback,
            hot_reload_callback=hot_reload_callback
        )
        
        self.message_handler = MessageHandler(
            session_manager=session_manager,
            opencode_client=opencode_client,
            send_reply_callback=send_reply_callback
        )
        
        # 命令映射表
        self.command_handlers: Dict[str, Callable] = {
            'help': self.help_handler.handle_help,
            'new': self.session_handler.handle_new,
            'agent': self.model_handler.handle_agent,
            'model': self.model_handler.handle_model,
            'path': self.session_handler.handle_path,
            'session': self.session_handler.handle_session,
            'reload': self.task_handler.handle_reload,
            'stop': self.session_handler.handle_stop,
            'undo': self.message_handler.handle_undo,
            'redo': self.message_handler.handle_redo,
            'command': self.task_handler.handle_command,
            'compact': self.message_handler.handle_compact,
        }
    
    def is_command(self, plain_text: str) -> bool:
        """检查消息是否为命令"""
        return is_command(plain_text)
    
    def extract_command(self, message: str) -> tuple:
        """从消息中提取命令和参数"""
        return parse_command(message)
    
    async def handle_command(
        self, 
        command_name: str, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> bool:
        """处理命令的主入口方法
        
        Args:
            command_name: 命令名称（不含前缀）
            message_type: 消息类型
            group_id: 群组 ID
            user_id: 用户 ID
            args: 命令参数
            
        Returns:
            bool: 是否处理成功
        """
        if command_name not in self.command_handlers:
            return False
        
        handler = self.command_handlers[command_name]
        try:
            await handler(message_type, group_id, user_id, args)
            return True
        except Exception as e:
            logger.error(f"处理命令失败：{e}")
            await self.send_reply(message_type, group_id, user_id, f"处理命令失败：{str(e)}")
            return True
    
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
        else:
            logger.warning(f"未设置 send_reply_callback: {reply[:50]}...")
    
    # ==================== 向后兼容方法 ====================
    # 以下方法保持与旧 API 兼容，委托给相应的处理器
    
    async def handle_help_command(
        self, 
        message_type: str, 
        group_id: Optional[int],
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /help 命令（向后兼容）"""
        await self.help_handler.handle_help(message_type, group_id, user_id, args)
    
    async def handle_new_command(
        self, 
        message_type: str, 
        group_id: Optional[int],
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /new 命令（向后兼容）"""
        await self.session_handler.handle_new(message_type, group_id, user_id, args)
    
    async def handle_agent_command(
        self, 
        message_type: str, 
        group_id: Optional[int],
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /agent 命令（向后兼容）"""
        await self.model_handler.handle_agent(message_type, group_id, user_id, args)
    
    async def handle_model_command(
        self, 
        message_type: str, 
        group_id: Optional[int],
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /model 命令（向后兼容）"""
        await self.model_handler.handle_model(message_type, group_id, user_id, args)
    
    async def handle_path_command(
        self, 
        message_type: str, 
        group_id: Optional[int],
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /path 命令（向后兼容）"""
        await self.session_handler.handle_path(message_type, group_id, user_id, args)
    
    async def handle_session_command(
        self, 
        message_type: str, 
        group_id: Optional[int],
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /session 命令（向后兼容）"""
        await self.session_handler.handle_session(message_type, group_id, user_id, args)
    
    async def handle_reload_command(
        self, 
        message_type: str, 
        group_id: Optional[int],
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /reload 命令（向后兼容）"""
        await self.task_handler.handle_reload(message_type, group_id, user_id, args)
    
    async def handle_stop_command(
        self, 
        message_type: str, 
        group_id: Optional[int],
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /stop 命令（向后兼容）"""
        await self.session_handler.handle_stop(message_type, group_id, user_id, args)
    
    async def handle_undo_command(
        self, 
        message_type: str, 
        group_id: Optional[int],
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /undo 命令（向后兼容）"""
        await self.message_handler.handle_undo(message_type, group_id, user_id, args)
    
    async def handle_redo_command(
        self, 
        message_type: str, 
        group_id: Optional[int],
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /redo 命令（向后兼容）"""
        await self.message_handler.handle_redo(message_type, group_id, user_id, args)
    
    async def handle_command_command(
        self, 
        message_type: str, 
        group_id: Optional[int],
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /command 命令（向后兼容）"""
        await self.task_handler.handle_command(message_type, group_id, user_id, args)
    
    async def handle_compact_command(
        self, 
        message_type: str, 
        group_id: Optional[int],
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /compact 命令（向后兼容）"""
        await self.message_handler.handle_compact(message_type, group_id, user_id, args)