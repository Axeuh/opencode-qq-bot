#!/usr/bin/env python3
"""
OneBot V11 Python客户端
用于连接NapCat WebSocket Server的QQ机器人

重构版本：使用协调器模式，将职责委托给专门的模块
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Dict, Optional, Any, Callable

from src.utils import config
from .config_manager import setup_logging, ConfigManager
from .opencode_integration import OpenCodeIntegration
from .file_handler import FileHandler
from .restart_handler import RestartHandler
from .message_queue import MessageQueueProcessor
from .session_ui_manager import SessionUIManager
from .connection_manager import ConnectionManager
from .message_router import MessageRouter
from .connection_lifecycle import ConnectionLifecycle
from .event_handlers import EventHandlers
from .api_sender import ApiSender
from .http_server import HTTPServer

# 导入新模块
from .http_callbacks import HTTPCallbackHandler
from .task_executor import TaskExecutor
from .lifecycle_manager import LifecycleManager

# 配置日志
setup_logging()
logger = logging.getLogger(__name__)

# OpenCode集成检查
try:
    from src.opencode.opencode_client import OpenCodeClient, OpenCodeClientSync
    from src.session.session_manager import SessionManager
    OPENCODE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"OpenCode模块导入失败: {e}，OpenCode功能将不可用")
    OPENCODE_AVAILABLE = False


class OneBotClient:
    """
    OneBot V11协议客户端
    
    重构后的协调器模式：
    - ClientInitializer: 负责初始化所有组件
    - HTTPCallbackHandler: 处理 HTTP 回调
    - TaskExecutor: 执行定时任务
    - LifecycleManager: 管理生命周期和热重载
    """
    
    def __init__(self):
        """初始化客户端"""
        # 1. 初始化核心组件
        self._init_core_components()
        
        # 2. 初始化API发送器
        self.api_sender = ApiSender(
            connection_manager=self.connection_manager
        )
        
        # 3. 初始化消息处理器
        self._init_message_handlers()
        
        # 4. 初始化OpenCode客户端
        self._init_opencode()
        
        # 5. 初始化重启处理器
        self._init_restart_handler()
        
        # 6. 初始化文件处理组件
        self._init_file_handling()
        
        # 7. 初始化消息路由器
        self._init_message_router()
        
        # 8. 初始化事件处理器
        self.event_handlers = EventHandlers(
            message_router=self.message_router,
            bot_qq_id=self.bot_qq_id
        )
        
        # 9. 初始化生命周期管理器
        self._init_lifecycle_manager()
        
        # 10. 注册默认处理器
        self.lifecycle_manager.register_default_handlers()
        
        # 11. 初始化 HTTP 服务器
        self._init_http_server()
        
        # 12. 初始化定时任务调度器
        self._init_task_scheduler()
        
        # 13. 初始化连接生命周期管理器
        self.connection_lifecycle = ConnectionLifecycle(
            connection_manager=self.connection_manager,
            message_queue_processor=self.message_queue_processor,
            opencode_client=self.opencode_client,
            opencode_sync_client=self.opencode_sync_client,
            session_manager=self.session_manager,
            bot_qq_id=self.bot_qq_id,
            opencode_available=self.opencode_available,
            http_server=self.http_server,
            task_scheduler=self.task_scheduler
        )
    
    def _init_core_components(self):
        """初始化核心组件"""
        self.connection_manager = ConnectionManager()
        self.bot_qq_id = config.BOT_QQ_ID
        
        # OpenCode集成相关属性
        self.opencode_client: Optional["OpenCodeClient"] = None
        self.opencode_sync_client: Optional["OpenCodeClientSync"] = None
        self.session_manager: Optional["SessionManager"] = None
        self.opencode_available = OPENCODE_AVAILABLE
        self.command_system: Optional[Any] = None
        
        # HTTP 服务器和任务调度器
        self.http_server: Optional[HTTPServer] = None
        self.task_scheduler: Optional[Any] = None
    
    def _init_message_handlers(self):
        """初始化消息处理器"""
        self.config_manager = ConfigManager()
        self.opencode_integration = OpenCodeIntegration(self.config_manager)
        
        self.message_queue_processor = MessageQueueProcessor(
            opencode_integration=self.opencode_integration,
            send_reply_callback=self.api_sender.send_reply,
            api_sender=self.api_sender
        )
        
        self.session_ui_manager = SessionUIManager(
            session_manager=self.session_manager,
            send_reply_callback=self.api_sender.send_reply
        )
    
    def _init_opencode(self):
        """初始化OpenCode客户端"""
        if not self.opencode_available:
            return
        
        from .opencode_initializer import OpenCodeInitializer
        
        initializer = OpenCodeInitializer(
            config_module=config,
            api_sender=self.api_sender,
            logger=logger,
            hot_reload_callback=self.perform_hot_reload
        )
        
        result = initializer.initialize(opencode_available=self.opencode_available)
        
        if result:
            self.opencode_client, self.opencode_sync_client, self.session_manager, self.command_system = result
        else:
            self.opencode_available = False
            self.opencode_client = None
            self.opencode_sync_client = None
            self.session_manager = None
            self.command_system = None
    
    def _init_restart_handler(self):
        """初始化重启处理器"""
        self.restart_handler = RestartHandler(
            session_manager=self.session_manager,
            tasks=self.connection_manager.tasks,
            ws=self.connection_manager.ws,
            session=self.connection_manager.session,
            opencode_client=self.opencode_client,
            opencode_sync_client=self.opencode_sync_client,
            restarting_flag=self.connection_manager.restarting,
            connected_flag=self.connection_manager.connected,
            stop_queue_processor_callback=self.message_queue_processor.stop_queue_processor
        )
    
    def _init_file_handling(self):
        """初始化文件处理组件"""
        import os
        self.file_config = config.FILE_HANDLING_CONFIG
        os.makedirs(self.file_config.get("download_dir", "downloads"), exist_ok=True)
        
        self.file_handler = FileHandler(
            base_download_dir=self.file_config.get("download_dir", "downloads"),
            config=self.file_config,
            api_callback=self.api_sender.send_action_with_response
        )
    
    def _init_message_router(self):
        """初始化消息路由器"""
        self.message_router = MessageRouter(
            file_handler=self.file_handler,
            message_queue_processor=self.message_queue_processor,
            bot_qq_id=self.bot_qq_id,
            command_system=self.command_system,
            send_reply_callback=self.api_sender.send_reply,
            get_quoted_message_callback=self.api_sender.get_quoted_message_full,
            opencode_available=self.opencode_available
        )
    
    def _init_lifecycle_manager(self):
        """初始化生命周期管理器"""
        self.lifecycle_manager = LifecycleManager(
            session_manager=self.session_manager,
            message_router=self.message_router,
            restart_handler=self.restart_handler,
            connection_manager=self.connection_manager,
            event_handlers=self.event_handlers
        )
    
    def _init_http_server(self):
        """初始化 HTTP 服务器"""
        if not config.HTTP_SERVER_ENABLED:
            logger.info("HTTP 服务器已禁用")
            return
        
        # 创建 HTTP 回调处理器
        self.http_callback_handler = HTTPCallbackHandler(
            session_manager=self.session_manager,
            opencode_client=self.opencode_client,
            hot_reload_callback=self.perform_hot_reload
        )
        
        # 获取回调字典
        callbacks = self.http_callback_handler.get_callbacks()
        
        self.http_server = HTTPServer(
            host=config.HTTP_SERVER_HOST,
            port=config.HTTP_SERVER_PORT,
            access_token=config.HTTP_SERVER_ACCESS_TOKEN,
            **callbacks
        )
        
        logger.info(f"HTTP 服务器已配置: http://{config.HTTP_SERVER_HOST}:{config.HTTP_SERVER_PORT}")
    
    def _init_task_scheduler(self):
        """初始化定时任务调度器"""
        from .task_scheduler import init_task_scheduler
        
        # 创建任务执行器
        self.task_executor = TaskExecutor(
            opencode_client=self.opencode_client,
            session_manager=self.session_manager
        )
        
        # 创建任务执行回调
        self.task_scheduler = init_task_scheduler(self.task_executor.execute_task)
        
        logger.info("定时任务调度器已配置")
    
    # ==================== 公共 API（保持向后兼容）====================
    
    async def perform_hot_reload(self) -> Dict[str, Any]:
        """
        执行热重载（重载代码和配置，不退出进程）
        
        委托给 LifecycleManager
        """
        return await self.lifecycle_manager.perform_hot_reload()
    
    async def _handle_http_reload(self) -> Dict[str, Any]:
        """处理 HTTP 热重载请求的回调函数"""
        return await self.http_callback_handler.handle_http_reload()
    
    async def _handle_http_restart(self) -> Dict[str, Any]:
        """处理 HTTP 重启请求的回调函数"""
        return await self.lifecycle_manager.handle_http_restart()
    
    def register_default_handlers(self):
        """注册默认消息处理器"""
        self.lifecycle_manager.register_default_handlers()
    
    def on_message(self, post_type: str, handler: Callable):
        """注册消息处理器"""
        self.connection_manager.register_message_handler(post_type, handler)


async def main():
    """主函数"""
    print(f"=== {config.BOT_NAME} Python客户端 ===")
    print(f"WebSocket服务器: {config.WS_URL}")
    print(f"自动回复功能: {'启用' if config.ENABLED_FEATURES.get('auto_reply') else '禁用'}")
    print("=" * 40)
    
    client = OneBotClient()
    await client.connection_lifecycle.run()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已退出")
    except Exception as e:
        print(f"程序错误: {e}")
        sys.exit(1)