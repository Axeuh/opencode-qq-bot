"""
生命周期管理模块
负责热重载、重启和事件注册
"""

import importlib
import logging
import sys
from typing import Dict, Any, Callable

logger = logging.getLogger(__name__)


class LifecycleManager:
    """
    生命周期管理器
    负责热重载、重启和事件注册
    """
    
    def __init__(
        self,
        session_manager: Any,
        message_router: Any,
        restart_handler: Any,
        connection_manager: Any,
        event_handlers: Any
    ):
        """
        初始化生命周期管理器
        
        Args:
            session_manager: 会话管理器实例
            message_router: 消息路由器实例
            restart_handler: 重启处理器实例
            connection_manager: 连接管理器实例
            event_handlers: 事件处理器实例
        """
        self.session_manager = session_manager
        self.message_router = message_router
        self.restart_handler = restart_handler
        self.connection_manager = connection_manager
        self.event_handlers = event_handlers
    
    async def perform_hot_reload(self) -> Dict[str, Any]:
        """
        执行热重载（重载代码和配置，不退出进程）
        
        Returns:
            包含重载结果的字典
        """
        results = {
            "config_reload": False,
            "modules_reload": [],
            "errors": []
        }
        
        try:
            # 1. 保存会话状态
            if self.session_manager:
                try:
                    self.session_manager.save_to_file()
                    logger.info("会话状态已保存")
                except Exception as e:
                    logger.warning(f"保存会话状态失败: {e}")
                    results["errors"].append(f"保存会话状态失败: {e}")
            
            # 2. 重载配置文件
            try:
                from src.utils import config
                config.update_config_from_reload()
                logger.info("配置文件已重载")
                results["config_reload"] = True
            except Exception as e:
                logger.error(f"重载配置文件失败: {e}")
                results["errors"].append(f"重载配置文件失败: {e}")
            
            # 3. 重载核心模块
            modules_to_reload = [
                "src.utils.config",
                "src.utils.config_loader",
                "src.core.message_router",
                "src.core.command_system",
                "src.core.event_handlers",
                "src.core.file_handler",
            ]
            
            for module_name in modules_to_reload:
                try:
                    if module_name in sys.modules:
                        importlib.reload(sys.modules[module_name])
                        logger.info(f"模块已重载: {module_name}")
                        results["modules_reload"].append(module_name)
                except Exception as e:
                    logger.error(f"重载模块失败 {module_name}: {e}")
                    results["errors"].append(f"重载模块失败 {module_name}: {e}")
            
            # 4. 更新消息路由器的配置
            if self.message_router:
                try:
                    # 更新 bot_qq_id
                    from src.utils import config as fresh_config
                    self.message_router.bot_qq_id = fresh_config.BOT_QQ_ID
                    logger.info("消息路由器配置已更新")
                except Exception as e:
                    logger.error(f"更新消息路由器配置失败: {e}")
                    results["errors"].append(f"更新消息路由器配置失败: {e}")
            
            logger.info("热重载完成")
            results["success"] = len(results["errors"]) == 0
            return results
            
        except Exception as e:
            logger.error(f"执行热重载失败: {e}")
            results["errors"].append(str(e))
            results["success"] = False
            return results
    
    async def handle_http_restart(self) -> Dict[str, Any]:
        """
        处理 HTTP 重启请求的回调函数
        
        Returns:
            包含重启结果的字典
        """
        logger.info("收到 HTTP 重启请求")
        
        try:
            # 调用重启处理器
            await self.restart_handler.perform_restart()
            return {"success": True, "message": "重启已启动"}
        except Exception as e:
            logger.error(f"HTTP 重启请求处理失败: {e}")
            return {"success": False, "error": str(e)}
    
    def register_default_handlers(self) -> None:
        """注册默认消息处理器"""
        # 处理元事件（心跳等）
        self.connection_manager.register_message_handler(
            'meta_event', 
            self.event_handlers.handle_meta_event
        )
        
        # 处理消息事件
        self.connection_manager.register_message_handler(
            'message', 
            self.event_handlers.handle_message_event
        )
        
        # 处理通知事件
        self.connection_manager.register_message_handler(
            'notice', 
            self.event_handlers.handle_notice_event
        )
        
        # 处理请求事件
        self.connection_manager.register_message_handler(
            'request', 
            self.event_handlers.handle_request_event
        )
        
        logger.info("默认消息处理器已注册")
    
    def register_handler(self, post_type: str, handler: Callable) -> None:
        """
        注册消息处理器
        
        Args:
            post_type: 消息类型
            handler: 处理函数
        """
        self.connection_manager.register_message_handler(post_type, handler)
        logger.debug(f"已注册消息处理器: {post_type}")
    
    def update_references(
        self,
        session_manager: Any,
        message_router: Any,
        restart_handler: Any,
        connection_manager: Any,
        event_handlers: Any
    ) -> None:
        """
        更新引用（用于热重载后更新）
        
        Args:
            session_manager: 新的会话管理器实例
            message_router: 新的消息路由器实例
            restart_handler: 新的重启处理器实例
            connection_manager: 新的连接管理器实例
            event_handlers: 新的事件处理器实例
        """
        self.session_manager = session_manager
        self.message_router = message_router
        self.restart_handler = restart_handler
        self.connection_manager = connection_manager
        self.event_handlers = event_handlers
        logger.info("LifecycleManager 引用已更新")