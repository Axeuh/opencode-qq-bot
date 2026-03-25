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
from .http import HTTPServer

# 导入新模块
from .http_callbacks import HTTPCallbackHandler
from .task_executor import TaskExecutor
from .lifecycle_manager import LifecycleManager
from .process_manager import ProcessManager, init_process_manager

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
        
        # 10. 初始化进程管理器
        self._init_process_manager()
        
        # 11. 注册默认处理器
        self.lifecycle_manager.register_default_handlers()
        
        # 12. 初始化 HTTP 服务器
        self._init_http_server()
        
        # 13. 初始化定时任务调度器
        self._init_task_scheduler()
        
        # 14. 初始化连接生命周期管理器
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
        
        # 进程管理器
        self.process_manager: Optional[ProcessManager] = None
    
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
            opencode_available=self.opencode_available,
            session_manager=self.session_manager
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
    
    def _init_process_manager(self):
        """初始化进程管理器"""
        if not self.opencode_available:
            logger.info("OpenCode 不可用，跳过进程管理器初始化")
            return
        
        self.process_manager = init_process_manager(
            opencode_port=config.OPENCODE_PORT,
            session_manager=self.session_manager,
            opencode_client=self.opencode_client
        )
        
        logger.info(f"进程管理器已初始化，OpenCode 端口: {config.OPENCODE_PORT}")
    
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
            http_port=config.HTTP_SERVER_HTTP_PORT,
            access_token=config.HTTP_SERVER_ACCESS_TOKEN,
            ssl_cert=config.HTTP_SERVER_SSL_CERT,
            ssl_key=config.HTTP_SERVER_SSL_KEY,
            session_manager=self.session_manager,
            process_manager=self.process_manager,
            **callbacks
        )
        
        # 设置进程管理器的 SSE 停止回调
        if self.process_manager and self.http_server:
            async def stop_sse_callback():
                self.http_server.stop_sse_listening()
                # 等待连接断开
                import asyncio
                await asyncio.sleep(2)
            
            self.process_manager.on_before_opencode_stop = stop_sse_callback
        
        # 显示服务器地址
        if config.HTTP_SERVER_SSL_CERT and config.HTTP_SERVER_SSL_KEY:
            https_url = f"https://{config.HTTP_SERVER_HOST}:{config.HTTP_SERVER_PORT}"
            if config.HTTP_SERVER_HTTP_PORT:
                http_url = f"http://{config.HTTP_SERVER_HOST}:{config.HTTP_SERVER_HTTP_PORT}"
                logger.info(f"HTTP 服务器已配置: {https_url} (HTTPS) 和 {http_url} (HTTP)")
            else:
                logger.info(f"HTTP 服务器已配置: {https_url} (HTTPS)")
        else:
            http_url = f"http://{config.HTTP_SERVER_HOST}:{config.HTTP_SERVER_PORT}"
            logger.info(f"HTTP 服务器已配置: {http_url}")
    
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
    print(f"OpenCode端口: {config.OPENCODE_PORT}")
    print(f"自动回复功能: {'启用' if config.ENABLED_FEATURES.get('auto_reply') else '禁用'}")
    print("=" * 40)
    
    client = OneBotClient()
    
    # 启动 OpenCode 进程（如果进程管理器可用）
    if client.process_manager:
        logger.info("启动 OpenCode 进程...")
        result = await client.process_manager.start_opencode()
        if result.get("success"):
            logger.info("OpenCode 进程已启动")
            # 启动进程监控
            await client.process_manager.start_monitoring()
            
            # 检查是否有需要恢复的会话（Bot 重启后）
            import os
            import json
            sessions_file = os.path.join(os.getcwd(), "data", "sessions_to_recover.json")
            if os.path.exists(sessions_file):
                try:
                    with open(sessions_file, 'r', encoding='utf-8') as f:
                        sessions_to_recover = json.load(f)
                    
                    if sessions_to_recover:
                        logger.info(f"发现 {len(sessions_to_recover)} 个需要恢复的会话")
                        # 等待 OpenCode API 就绪
                        for i in range(10):
                            if await client.process_manager._check_opencode_api_ready():
                                break
                            await asyncio.sleep(0.5)
                        
                        # 恢复会话
                        recovery_result = await client.process_manager._recover_sessions(sessions_to_recover)
                        logger.info(f"会话恢复结果: {recovery_result}")
                    
                    # 删除临时文件
                    os.remove(sessions_file)
                    logger.info("已删除会话恢复临时文件")
                    
                except Exception as e:
                    logger.error(f"恢复会话失败: {e}")
        else:
            logger.warning(f"OpenCode 进程启动失败: {result.get('error')}")
    
    try:
        await client.connection_lifecycle.run()
    finally:
        # 清理进程管理器
        if client.process_manager:
            logger.info("停止进程监控...")
            await client.process_manager.stop_monitoring()
            client.process_manager.cleanup()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已退出")
    except Exception as e:
        print(f"程序错误: {e}")
        sys.exit(1)