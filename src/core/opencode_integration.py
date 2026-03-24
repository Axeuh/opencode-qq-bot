#!/usr/bin/env python3
"""
OpenCode 集成模块
负责 OpenCode 客户端初始化和消息转发
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING, Callable, Awaitable

if TYPE_CHECKING:
    from src.opencode.opencode_client import OpenCodeClient, OpenCodeClientSync
    from src.session.session_manager import SessionManager
    from .command_system import CommandSystem

from .opencode_forwarder import OpenCodeForwarder

logger = logging.getLogger(__name__)


class OpenCodeIntegration:
    """OpenCode 集成管理器"""
    
    def __init__(self, config_manager):
        """
        初始化 OpenCode 集成
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.opencode_client: Optional["OpenCodeClient"] = None
        self.opencode_sync_client: Optional["OpenCodeClientSync"] = None
        self.session_manager: Optional["SessionManager"] = None
        self.command_system: Optional["CommandSystem"] = None
        self.forwarder: Optional[OpenCodeForwarder] = None
        
        # OpenCode 可用性标志
        self.opencode_available = False
        
        # 初始化 OpenCode 客户端（如果可用）
        self._check_opencode_availability()
        if self.opencode_available:
            self._init_opencode_integration()
    
    def _check_opencode_availability(self) -> None:
        """检查 OpenCode 模块是否可用"""
        try:
            from src.opencode.opencode_client import OpenCodeClient, OpenCodeClientSync
            from src.session.session_manager import SessionManager, get_session_manager
            self.opencode_available = True
            logger.debug("OpenCode 模块可用")
        except ImportError as e:
            logger.warning(f"OpenCode 模块导入失败: {e}，OpenCode 功能将不可用")
            self.opencode_available = False
    
    def _init_opencode_integration(self) -> None:
        """初始化 OpenCode 客户端、会话管理器和命令系统"""
        if not self.opencode_available:
            logger.warning("OpenCode 模块不可用，跳过初始化")
            return
        
        try:
            from src.opencode.opencode_client import OpenCodeClient, OpenCodeClientSync
            from src.session.session_manager import SessionManager, get_session_manager
            
            opencode_config = self.config_manager.opencode_config
            
            # 初始化异步 OpenCode 客户端
            auth_config = opencode_config["auth"]
            self.opencode_client = OpenCodeClient(
                base_url=opencode_config["base_url"],
                username=auth_config.get("username"),
                password=auth_config.get("password"),
                token=auth_config.get("token"),
                cookies=opencode_config["cookies"],
                timeout=opencode_config["timeout"],
                directory=opencode_config["directory"],
                default_agent=opencode_config["default_agent"],
                default_model=opencode_config["default_model"],
                default_provider=opencode_config["default_provider"]
            )
            
            # 初始化同步 OpenCode 客户端
            self.opencode_sync_client = OpenCodeClientSync(
                base_url=opencode_config["base_url"],
                username=auth_config.get("username"),
                password=auth_config.get("password"),
                token=auth_config.get("token"),
                cookies=opencode_config["cookies"],
                timeout=opencode_config["timeout"],
                directory=opencode_config["directory"],
                default_agent=opencode_config["default_agent"],
                default_model=opencode_config["default_model"],
                default_provider=opencode_config["default_provider"]
            )
            
            # 初始化会话管理器
            self.session_manager = get_session_manager()
            
            # 初始化消息转发器
            self.forwarder = OpenCodeForwarder(
                client=self.opencode_client,
                session_manager=self.session_manager,
                config_manager=self.config_manager
            )
            
            # 初始化命令系统（如果可用）
            try:
                from .command_system import CommandSystem
                self.command_system = CommandSystem(
                    session_manager=self.session_manager,
                    opencode_client=self.opencode_client,
                    send_reply_callback=None
                )
            except ImportError as e:
                logger.warning(f"命令系统导入失败: {e}")
                self.command_system = None
            
        except Exception as e:
            logger.error(f"OpenCode 集成初始化失败: {e}", exc_info=True)
            self.opencode_available = False
    
    async def close(self) -> None:
        """关闭 OpenCode 客户端"""
        if self.opencode_client:
            await self.opencode_client.close()
        if self.opencode_sync_client:
            self.opencode_sync_client.close()
    
    async def forward_to_opencode(
        self,
        message_type: str,
        group_id: Optional[int],
        user_id: Optional[int],
        plain_text: str,
        send_reply_callback: Optional[Callable[[str, Optional[int], Optional[int], str], Awaitable[None]]] = None
    ) -> None:
        """
        将消息转发到 OpenCode（向后兼容接口）
        
        Args:
            message_type: 消息类型 ('private' 或 'group')
            group_id: 群号（群聊时）
            user_id: 用户 QQ 号
            plain_text: 纯文本消息
            send_reply_callback: 发送回复的回调函数
        """
        if not self.opencode_available or not self.forwarder:
            reply = "OpenCode 集成当前不可用，无法处理消息。"
            if send_reply_callback and user_id:
                await send_reply_callback(message_type, group_id, user_id, reply)
            return
        
        await self.forwarder.forward_to_opencode(
            message_type=message_type,
            group_id=group_id,
            user_id=user_id,
            plain_text=plain_text,
            user_name=None,
            send_reply_callback=send_reply_callback
        )
    
    async def forward_to_opencode_sync(
        self,
        message_type: str,
        group_id: Optional[int],
        user_id: Optional[int],
        plain_text: str,
        user_name: Optional[str] = None,
        send_reply_callback: Optional[Callable[[str, Optional[int], Optional[int], str], Awaitable[None]]] = None
    ) -> None:
        """
        同步版本的 OpenCode 转发（用于队列处理）
        
        Args:
            message_type: 消息类型 ('private' 或 'group')
            group_id: 群号（群聊时）
            user_id: 用户 QQ 号
            plain_text: 纯文本消息
            user_name: 用户显示名称（可选）
            send_reply_callback: 发送回复的回调函数
        """
        if not self.opencode_available or not self.forwarder:
            logger.warning(f"OpenCode 不可用，丢弃消息: user_id={user_id}")
            return
        
        await self.forwarder.forward_to_opencode(
            message_type=message_type,
            group_id=group_id,
            user_id=user_id,
            plain_text=plain_text,
            user_name=user_name,
            send_reply_callback=send_reply_callback
        )