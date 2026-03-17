"""
客户端初始化模块
负责初始化所有核心组件和依赖
"""

import logging
import os
from typing import Any, Optional, Tuple

from src.utils import config

logger = logging.getLogger(__name__)

# OpenCode 集成检查
try:
    from src.opencode.opencode_client import OpenCodeClient, OpenCodeClientSync
    from src.session.session_manager import SessionManager
    OPENCODE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"OpenCode模块导入失败: {e}，OpenCode功能将不可用")
    OPENCODE_AVAILABLE = False


class ClientInitializer:
    """
    客户端初始化器
    负责按依赖顺序初始化所有组件
    """
    
    def __init__(
        self,
        connection_manager: Any,
        api_sender: Any,
        hot_reload_callback: Any
    ):
        """
        初始化器
        
        Args:
            connection_manager: 连接管理器实例
            api_sender: API发送器实例
            hot_reload_callback: 热重载回调函数
        """
        self.connection_manager = connection_manager
        self.api_sender = api_sender
        self.hot_reload_callback = hot_reload_callback
        
        # 初始化结果
        self.opencode_client: Optional["OpenCodeClient"] = None
        self.opencode_sync_client: Optional["OpenCodeClientSync"] = None
        self.session_manager: Optional["SessionManager"] = None
        self.command_system: Optional[Any] = None
        self.opencode_available = OPENCODE_AVAILABLE
    
    def init_core_components(self) -> dict:
        """
        初始化核心组件
        
        Returns:
            包含核心组件的字典
        """
        return {
            'bot_qq_id': config.BOT_QQ_ID,
            'opencode_available': self.opencode_available,
            'opencode_client': None,
            'opencode_sync_client': None,
            'session_manager': None,
            'command_system': None,
            'http_server': None,
            'task_scheduler': None
        }
    
    def init_message_handlers(
        self,
        config_manager_class: Any,
        opencode_integration_class: Any,
        message_queue_processor_class: Any,
        session_ui_manager_class: Any
    ) -> Tuple[Any, Any, Any, Any]:
        """
        初始化消息处理器
        
        Args:
            config_manager_class: ConfigManager 类
            opencode_integration_class: OpenCodeIntegration 类
            message_queue_processor_class: MessageQueueProcessor 类
            session_ui_manager_class: SessionUIManager 类
            
        Returns:
            (config_manager, opencode_integration, message_queue_processor, session_ui_manager)
        """
        config_manager = config_manager_class()
        opencode_integration = opencode_integration_class(config_manager)
        
        message_queue_processor = message_queue_processor_class(
            opencode_integration=opencode_integration,
            send_reply_callback=self.api_sender.send_reply,
            api_sender=self.api_sender
        )
        
        session_ui_manager = session_ui_manager_class(
            session_manager=self.session_manager,
            send_reply_callback=self.api_sender.send_reply
        )
        
        return config_manager, opencode_integration, message_queue_processor, session_ui_manager
    
    def init_opencode(self) -> Optional[Tuple[Any, Any, Any, Any]]:
        """
        初始化 OpenCode 客户端
        
        Returns:
            (opencode_client, opencode_sync_client, session_manager, command_system) 或 None
        """
        if not self.opencode_available:
            return None
        
        from .opencode_initializer import OpenCodeInitializer
        
        initializer = OpenCodeInitializer(
            config_module=config,
            api_sender=self.api_sender,
            logger=logger,
            hot_reload_callback=self.hot_reload_callback
        )
        
        result = initializer.initialize(opencode_available=self.opencode_available)
        
        if result:
            self.opencode_client, self.opencode_sync_client, self.session_manager, self.command_system = result
            return result
        else:
            self.opencode_available = False
            return None
    
    def init_restart_handler(
        self,
        restart_handler_class: Any,
        session_manager: Any,
        message_queue_processor: Any
    ) -> Any:
        """
        初始化重启处理器
        
        Args:
            restart_handler_class: RestartHandler 类
            session_manager: 会话管理器实例
            message_queue_processor: 消息队列处理器实例
            
        Returns:
            RestartHandler 实例
        """
        return restart_handler_class(
            session_manager=session_manager,
            tasks=self.connection_manager.tasks,
            ws=self.connection_manager.ws,
            session=self.connection_manager.session,
            opencode_client=self.opencode_client,
            opencode_sync_client=self.opencode_sync_client,
            restarting_flag=self.connection_manager.restarting,
            connected_flag=self.connection_manager.connected,
            stop_queue_processor_callback=message_queue_processor.stop_queue_processor
        )
    
    def init_file_handling(self, file_handler_class: Any) -> Any:
        """
        初始化文件处理组件
        
        Args:
            file_handler_class: FileHandler 类
            
        Returns:
            FileHandler 实例
        """
        file_config = config.FILE_HANDLING_CONFIG
        # 确保下载目录存在
        os.makedirs(file_config.get("download_dir", "downloads"), exist_ok=True)
        
        return file_handler_class(
            base_download_dir=file_config.get("download_dir", "downloads"),
            config=file_config,
            api_callback=self.api_sender.send_action_with_response
        )
    
    def init_message_router(
        self,
        message_router_class: Any,
        file_handler: Any,
        message_queue_processor: Any,
        command_system: Any,
        bot_qq_id: int
    ) -> Any:
        """
        初始化消息路由器
        
        Args:
            message_router_class: MessageRouter 类
            file_handler: 文件处理器实例
            message_queue_processor: 消息队列处理器实例
            command_system: 命令系统实例
            bot_qq_id: 机器人 QQ 号
            
        Returns:
            MessageRouter 实例
        """
        return message_router_class(
            file_handler=file_handler,
            message_queue_processor=message_queue_processor,
            bot_qq_id=bot_qq_id,
            command_system=command_system,
            send_reply_callback=self.api_sender.send_reply,
            get_quoted_message_callback=self.api_sender.get_quoted_message_full,
            opencode_available=self.opencode_available
        )
    
    def init_http_server(
        self,
        http_server_class: Any,
        callbacks: dict
    ) -> Optional[Any]:
        """
        初始化 HTTP 服务器
        
        Args:
            http_server_class: HTTPServer 类
            callbacks: 回调函数字典
            
        Returns:
            HTTPServer 实例或 None
        """
        if not config.HTTP_SERVER_ENABLED:
            logger.info("HTTP 服务器已禁用")
            return None
        
        http_server = http_server_class(
            host=config.HTTP_SERVER_HOST,
            port=config.HTTP_SERVER_PORT,
            access_token=config.HTTP_SERVER_ACCESS_TOKEN,
            **callbacks
        )
        
        logger.info(f"HTTP 服务器已配置: http://{config.HTTP_SERVER_HOST}:{config.HTTP_SERVER_PORT}")
        return http_server
    
    def init_task_scheduler(self, task_scheduler_module: Any, execute_task_callback: Any) -> Any:
        """
        初始化定时任务调度器
        
        Args:
            task_scheduler_module: task_scheduler 模块
            execute_task_callback: 任务执行回调函数
            
        Returns:
            任务调度器实例
        """
        return task_scheduler_module.init_task_scheduler(execute_task_callback)
    
    def init_connection_lifecycle(
        self,
        connection_lifecycle_class: Any,
        message_queue_processor: Any,
        http_server: Any,
        task_scheduler: Any,
        bot_qq_id: int
    ) -> Any:
        """
        初始化连接生命周期管理器
        
        Args:
            connection_lifecycle_class: ConnectionLifecycle 类
            message_queue_processor: 消息队列处理器实例
            http_server: HTTP 服务器实例
            task_scheduler: 任务调度器实例
            bot_qq_id: 机器人 QQ 号
            
        Returns:
            ConnectionLifecycle 实例
        """
        return connection_lifecycle_class(
            connection_manager=self.connection_manager,
            message_queue_processor=message_queue_processor,
            opencode_client=self.opencode_client,
            opencode_sync_client=self.opencode_sync_client,
            session_manager=self.session_manager,
            bot_qq_id=bot_qq_id,
            opencode_available=self.opencode_available,
            http_server=http_server,
            task_scheduler=task_scheduler
        )
    
    def init_event_handlers(
        self,
        event_handlers_class: Any,
        message_router: Any,
        bot_qq_id: int
    ) -> Any:
        """
        初始化事件处理器
        
        Args:
            event_handlers_class: EventHandlers 类
            message_router: 消息路由器实例
            bot_qq_id: 机器人 QQ 号
            
        Returns:
            EventHandlers 实例
        """
        return event_handlers_class(
            message_router=message_router,
            bot_qq_id=bot_qq_id
        )