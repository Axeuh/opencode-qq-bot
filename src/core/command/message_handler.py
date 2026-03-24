#!/usr/bin/env python3
"""
消息操作命令处理器模块 - 处理 /undo, /redo, /compact 命令
"""

from __future__ import annotations

import logging
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


class MessageHandler:
    """消息操作命令处理器"""
    
    def __init__(
        self,
        session_manager: Optional[Any] = None,
        opencode_client: Optional[Any] = None,
        send_reply_callback: Optional[Callable[[str, Optional[int], Optional[int], str], Any]] = None
    ):
        self.session_manager = session_manager
        self.opencode_client = opencode_client
        self.send_reply_callback = send_reply_callback
    
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
    
    # ==================== /undo 命令 ====================
    
    async def handle_undo(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /undo 命令 - 撤销最后一条消息"""
        if not user_id or not self.session_manager:
            await self.send_reply(message_type, group_id, user_id, "无法识别用户或会话管理器不可用。")
            return
        
        current_session = self.session_manager.get_user_session(user_id)
        if not current_session:
            await self.send_reply(message_type, group_id, user_id, "没有活动的会话。")
            return
        
        if self.opencode_client:
            success, error = await self.opencode_client.revert_last_message(current_session.session_id)
            reply = "已撤销最后一条消息" if success else f"撤销失败：{error}"
        else:
            reply = "OpenCode 客户端不可用"
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    # ==================== /redo 命令 ====================
    
    async def handle_redo(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /redo 命令 - 恢复所有撤销的消息"""
        if not user_id or not self.session_manager:
            await self.send_reply(message_type, group_id, user_id, "无法识别用户或会话管理器不可用。")
            return
        
        current_session = self.session_manager.get_user_session(user_id)
        if not current_session:
            await self.send_reply(message_type, group_id, user_id, "没有活动的会话。")
            return
        
        if self.opencode_client:
            success, error = await self.opencode_client.unrevert_messages(current_session.session_id)
            reply = "已恢复 OpenCode 会话中所有撤销的消息" if success else f"恢复失败：{error}"
        else:
            reply = "OpenCode 客户端不可用"
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    # ==================== /compact 命令 ====================
    
    async def handle_compact(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /compact 命令 - 压缩当前会话上下文"""
        if not user_id:
            logger.warning("无法处理/compact 命令：user_id 为空")
            return
        
        if not self.session_manager:
            await self.send_reply(message_type, group_id, user_id, "会话管理器不可用")
            return
        
        if not self.opencode_client:
            await self.send_reply(message_type, group_id, user_id, "OpenCode 客户端不可用")
            return
        
        # 获取用户当前会话
        user_session = self.session_manager.get_user_session(user_id)
        if not user_session:
            await self.send_reply(message_type, group_id, user_id, "没有活动的会话，请先使用/new 创建新会话")
            return
        
        session_id = user_session.session_id
        provider_id = user_session.provider
        model_id = user_session.model
        
        await self.send_reply(message_type, group_id, user_id, "正在压缩会话...")
        
        # 调用 API 压缩会话
        success, error = await self.opencode_client.summarize_session(
            session_id=session_id,
            provider_id=provider_id,
            model_id=model_id
        )
        
        if success:
            await self.send_reply(message_type, group_id, user_id, "会话已压缩")
        else:
            await self.send_reply(message_type, group_id, user_id, f"压缩失败：{error}")