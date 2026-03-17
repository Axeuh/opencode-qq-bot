#!/usr/bin/env python3
"""
OpenCode集成初始化模块
用于集中管理OpenCode客户端的初始化和错误处理
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple, Any

# 尝试导入OpenCode相关模块
try:
    from src.opencode.opencode_client import OpenCodeClient, OpenCodeClientSync
    from src.session.session_manager import get_session_manager
    OPENCODE_MODULES_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"OpenCode模块导入失败: {e}，OpenCode功能将不可用")
    OPENCODE_MODULES_AVAILABLE = False

from .command_system import CommandSystem


class OpenCodeInitializer:
    """OpenCode集成初始化器
    
    负责集中管理OpenCode客户端的初始化、错误处理和资源管理。
    替代原onebot_client.py中的_init_opencode_integration方法。
    """
    
    def __init__(self, config_module: Any, api_sender: Any, logger: Optional[logging.Logger] = None, hot_reload_callback: Any = None):
        """初始化OpenCode初始化器
        
        Args:
            config_module: 配置模块，包含OPENCODE_*等配置项
            api_sender: API发送器，用于命令系统的回调
            logger: 日志记录器，如果为None则创建新记录器
            hot_reload_callback: 热重载回调函数，用于/reload命令
        """
        self.config = config_module
        self.api_sender = api_sender
        self.logger = logger or logging.getLogger(__name__)
        self.hot_reload_callback = hot_reload_callback
    
    def initialize(self, opencode_available: bool = True) -> Optional[Tuple[OpenCodeClient, OpenCodeClientSync, Any, CommandSystem]]:
        """初始化OpenCode集成
        
        根据配置初始化OpenCode异步客户端、同步客户端、会话管理器和命令系统。
        
        Args:
            opencode_available: OpenCode功能是否可用（由调用者检查）
            
        Returns:
            如果初始化成功，返回包含四个对象的元组:
            (opencode_client, opencode_sync_client, session_manager, command_system)
            如果初始化失败或OpenCode不可用，返回None
        """
        if not opencode_available:
            self.logger.warning("OpenCode集成不可用，跳过初始化")
            return None
        
        if not OPENCODE_MODULES_AVAILABLE:
            self.logger.warning("OpenCode模块导入失败，跳过初始化")
            return None
        
        try:
            # 初始化OpenCode异步客户端
            opencode_client = OpenCodeClient(  # type: ignore
                base_url=self.config.OPENCODE_BASE_URL,
                username=self.config.OPENCODE_AUTH.get("username"),
                password=self.config.OPENCODE_AUTH.get("password"),
                token=self.config.OPENCODE_AUTH.get("token"),
                cookies=self.config.OPENCODE_COOKIES,
                timeout=self.config.OPENCODE_TIMEOUT,
                directory=self.config.OPENCODE_DIRECTORY,
                default_agent=self.config.OPENCODE_DEFAULT_AGENT,
                default_model=self.config.OPENCODE_DEFAULT_MODEL,
                default_provider=self.config.OPENCODE_DEFAULT_PROVIDER
            )
            
            # 初始化OpenCode同步客户端（用于命令处理）
            opencode_sync_client = OpenCodeClientSync(  # type: ignore
                base_url=self.config.OPENCODE_BASE_URL,
                username=self.config.OPENCODE_AUTH.get("username"),
                password=self.config.OPENCODE_AUTH.get("password"),
                token=self.config.OPENCODE_AUTH.get("token"),
                cookies=self.config.OPENCODE_COOKIES,
                timeout=self.config.OPENCODE_TIMEOUT,
                directory=self.config.OPENCODE_DIRECTORY,
                default_agent=self.config.OPENCODE_DEFAULT_AGENT,
                default_model=self.config.OPENCODE_DEFAULT_MODEL,
                default_provider=self.config.OPENCODE_DEFAULT_PROVIDER
            )
            
            # 初始化会话管理器
            session_manager = get_session_manager()  # type: ignore
            
            self.logger.info("✓ OpenCode集成初始化成功")
            self.logger.info(f"  服务器: {self.config.OPENCODE_BASE_URL}")
            self.logger.info(f"  默认智能体: {self.config.OPENCODE_DEFAULT_AGENT}")
            self.logger.info(f"  默认模型: {self.config.OPENCODE_DEFAULT_MODEL}")
            
            # 初始化命令系统
            command_system = CommandSystem(
                session_manager=session_manager,
                opencode_client=opencode_client,
                send_reply_callback=self.api_sender.send_reply,
                hot_reload_callback=self.hot_reload_callback
            )
            self.logger.info("✓ 命令系统初始化成功")
            
            return (opencode_client, opencode_sync_client, session_manager, command_system)
            
        except Exception as e:
            self.logger.error(f"OpenCode集成初始化失败: {e}")
            return None