#!/usr/bin/env python3
"""
OneBot V11 Python客户端
用于连接NapCat WebSocket Server的QQ机器人
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import aiohttp
from typing import Dict, List, Optional, Any, Callable, Tuple
from src.utils import config
from .cq_code_parser import parse_cq_code, extract_file_info, extract_plain_text, extract_quoted_message_id
from .message_utils import check_whitelist
from .command_system import CommandSystem
from .config_manager import setup_logging, ConfigManager
from .opencode_integration import OpenCodeIntegration
from .file_handler import FileHandler
from .restart_handler import RestartHandler
from .opencode_api import OpenCodeAPI
from .message_queue import MessageQueueProcessor
from .session_ui_manager import SessionUIManager
from .connection_manager import ConnectionManager
from .message_router import MessageRouter
from .time_utils import get_cross_platform_time
from .connection_lifecycle import ConnectionLifecycle
from .event_handlers import EventHandlers
from .api_sender import ApiSender
from .opencode_initializer import OpenCodeInitializer
from .http_server import HTTPServer

# 配置日志 - 已移至config_manager模块

# 初始化日志
setup_logging()
logger = logging.getLogger(__name__)

# OpenCode集成
try:
    from src.opencode.opencode_client import OpenCodeClient, OpenCodeClientSync
    from src.session.session_manager import SessionManager, get_session_manager
    OPENCODE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"OpenCode模块导入失败: {e}，OpenCode功能将不可用")
    OPENCODE_AVAILABLE = False

class OneBotClient:
    """OneBot V11协议客户端"""
    
    def __init__(self):
        """初始化客户端"""
        # 初始化核心组件
        self._init_core_components()
        
        # 初始化API发送器（需要connection_manager）
        self.api_sender = ApiSender(
            connection_manager=self.connection_manager
        )
        
        # 初始化消息处理器（队列、UI管理器等，需要api_sender）
        self._init_message_handlers()
        
# 初始化OpenCode客户端（如果可用）
        if self.opencode_available:
            # 使用OpenCodeInitializer进行初始化
            opencode_initializer = OpenCodeInitializer(
                config_module=config,
                api_sender=self.api_sender,
                logger=logger,
                hot_reload_callback=self.perform_hot_reload
            )
            result = opencode_initializer.initialize(opencode_available=self.opencode_available)
            
            if result:
                # 初始化成功，解包结果
                self.opencode_client, self.opencode_sync_client, self.session_manager, self.command_system = result
            else:
                # 初始化失败，设置相关属性为None
                self.opencode_available = False
                self.opencode_client = None
                self.opencode_sync_client = None
                self.session_manager = None
                self.command_system = None
        
        # 初始化重启处理器（依赖多个已初始化的组件）
        self._init_restart_handler()
        
        # 初始化文件处理组件
        self._init_file_handling()
        
        # 初始化消息路由器（依赖几乎所有组件）
        self._init_message_router()
        
        # 初始化事件处理器（需要message_router和bot_qq_id）
        self.event_handlers = EventHandlers(
            message_router=self.message_router,
            bot_qq_id=self.bot_qq_id
        )

# 注册默认处理器
        self.register_default_handlers()
        
        # 初始化 HTTP 服务器（必须在 ConnectionLifecycle 之前）
        self._init_http_server()
        
        # 初始化定时任务调度器（必须在 ConnectionLifecycle 之前）
        self._init_task_scheduler()
        
        # 初始化连接生命周期管理器
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
        # WebSocket连接管理器
        self.connection_manager = ConnectionManager()
        
        # 机器人QQ号，将从NapCat获取
        self.bot_qq_id = config.BOT_QQ_ID
        
        # OpenCode集成相关属性（初始化为None，后续条件初始化）
        self.opencode_client: Optional["OpenCodeClient"] = None
        self.opencode_sync_client: Optional["OpenCodeClientSync"] = None
        self.session_manager: Optional["SessionManager"] = None
        self.opencode_available = OPENCODE_AVAILABLE
        self.command_system: Optional[CommandSystem] = None
        
        # HTTP 服务器（初始化为 None，后续条件初始化）
        self.http_server: Optional[HTTPServer] = None
        
        # 定时任务调度器（初始化为 None，后续条件初始化）
        self.task_scheduler: Optional[Any] = None
    
    def _init_message_handlers(self):
        """初始化消息处理器"""
        # OpenCode集成管理器
        self.config_manager = ConfigManager()
        self.opencode_integration = OpenCodeIntegration(self.config_manager)
        
        # 消息队列处理器
        self.message_queue_processor = MessageQueueProcessor(
            opencode_integration=self.opencode_integration,
            send_reply_callback=self.api_sender.send_reply,
            api_sender=self.api_sender
        )
        
        # 会话UI管理器（session_manager初始为None，OpenCode初始化后更新）
        self.session_ui_manager = SessionUIManager(
            session_manager=self.session_manager,
            send_reply_callback=self.api_sender.send_reply
        )
    
    def _init_restart_handler(self):
        """初始化重启处理器"""
        self.restart_handler = RestartHandler(
            session_manager=self.session_manager,
            tasks=self.connection_manager.tasks,
            ws=self.connection_manager.ws,
            session=self.connection_manager.session,
            opencode_client=self.opencode_client,
            opencode_sync_client=self.opencode_sync_client,
            restarting_flag=self.connection_manager.restarting,  # 传递可写引用
            connected_flag=self.connection_manager.connected,    # 传递可写引用
            stop_queue_processor_callback=self.message_queue_processor.stop_queue_processor
        )
    
    def _init_file_handling(self):
        """初始化文件处理组件"""
        self.file_config = config.FILE_HANDLING_CONFIG
        # 确保下载目录存在
        import os
        os.makedirs(self.file_config.get("download_dir", "downloads"), exist_ok=True)
        
        # 初始化文件处理器
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
    
    def _init_http_server(self):
        """初始化 HTTP 服务器"""
        # 检查是否启用 HTTP 服务器
        if not config.HTTP_SERVER_ENABLED:
            logger.info("HTTP 服务器已禁用")
            return
        
        self.http_server = HTTPServer(
            host=config.HTTP_SERVER_HOST,
            port=config.HTTP_SERVER_PORT,
            access_token=config.HTTP_SERVER_ACCESS_TOKEN,
            reload_callback=self._handle_http_reload,
            get_user_config_callback=self._handle_get_user_config,
            set_user_config_callback=self._handle_set_user_config,
            list_agents_callback=self._handle_list_agents,
            list_models_callback=self._handle_list_models,
            get_user_tasks_callback=self._handle_get_user_tasks,
            create_task_callback=self._handle_create_task,
            update_task_callback=self._handle_update_task,
            delete_task_callback=self._handle_delete_task
        )
        
        logger.info(f"HTTP 服务器已配置: http://{config.HTTP_SERVER_HOST}:{config.HTTP_SERVER_PORT}")
    
    def _init_task_scheduler(self):
        """初始化定时任务调度器"""
        from .task_scheduler import init_task_scheduler
        
        # 创建任务执行回调
        self.task_scheduler = init_task_scheduler(self._execute_task)
        
        logger.info("定时任务调度器已配置")
    
    async def _execute_task(self, session_id: str, prompt: str, task_info: Dict[str, Any] = None) -> None:
        """执行定时任务：发送prompt到opencode会话
        
        Args:
            session_id: OpenCode会话ID
            prompt: 任务提示词
            task_info: 任务信息字典（可选）
        """
        if not self.opencode_client:
            logger.warning(f"OpenCode客户端不可用，无法执行任务: session={session_id}")
            return
        
        try:
            # 获取用户配置的模型
            user_agent = None
            user_model = None
            user_provider = None
            
            if task_info and self.session_manager:
                user_id = task_info.get('user_id')
                if user_id:
                    user_config = self.session_manager.get_user_config(user_id)
                    if user_config:
                        user_agent = user_config.agent
                        user_model = user_config.model
                        user_provider = user_config.provider
                        logger.info(f"使用用户配置: user_id={user_id}, agent={user_agent}, model={user_model}, provider={user_provider}")
            
            # 构建带前缀的prompt
            if task_info:
                prefix = f"[任务 id={task_info.get('task_id', '')}, 用户 qq 号={task_info.get('user_id', '')}, 会话 id={task_info.get('session_id', '')}, 任务名称={task_info.get('task_name', '')}]\n"
                full_prompt = prefix + prompt
            else:
                full_prompt = prompt
            
            logger.info(f"执行定时任务: session={session_id}, prompt={full_prompt[:100]}...")
            
            # 发送消息到OpenCode会话（使用用户配置的模型）
            result, error = await self.opencode_client.send_message(
                message_text=full_prompt,
                session_id=session_id,
                agent=user_agent,
                model=user_model,
                provider=user_provider
            )
            
            if error:
                logger.error(f"定时任务执行失败: session={session_id}, error={error}")
            else:
                logger.info(f"定时任务执行成功: session={session_id}")
                
        except Exception as e:
            logger.error(f"执行定时任务异常: {e}")
    
    async def _handle_get_user_tasks(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户任务列表"""
        from .task_storage import get_task_storage
        from .task_scheduler import get_task_scheduler
        
        storage = get_task_storage()
        scheduler = get_task_scheduler()
        
        tasks = storage.get_user_tasks(user_id)
        return [scheduler.get_task_info(task) for task in tasks]
    
    async def _handle_create_task(
        self, 
        user_id: int, 
        session_id: str, 
        task_name: str, 
        prompt: str, 
        schedule_type: str, 
        schedule_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建定时任务"""
        from .task_storage import get_task_storage
        from .task_scheduler import get_task_scheduler
        
        # 验证schedule_config
        if schedule_type == "delay":
            # 延时任务：检查是否设置了时间参数
            time_params = ["seconds", "minutes", "hours", "days", "weeks", "months"]
            if not any(p in schedule_config for p in time_params):
                return {"success": False, "error": "delay task must have at least one time parameter (seconds/minutes/hours/days/weeks/months)"}
        
        elif schedule_type == "scheduled":
            # 定时任务：检查模式和时间
            mode = schedule_config.get("mode", "weekly")
            if mode not in ["weekly", "monthly", "yearly"]:
                return {"success": False, "error": f"Invalid mode: {mode}. Valid modes: weekly, monthly, yearly"}
            
            if "hour" not in schedule_config:
                return {"success": False, "error": "scheduled task must contain 'hour'"}
            schedule_config.setdefault("minute", 0)
            
            if mode == "weekly" and "days" not in schedule_config:
                return {"success": False, "error": "weekly mode must contain 'days' array"}
            
            if mode == "monthly" and "day" not in schedule_config:
                return {"success": False, "error": "monthly mode must contain 'day'"}
            
            if mode == "yearly":
                if "month" not in schedule_config:
                    return {"success": False, "error": "yearly mode must contain 'month'"}
                if "day" not in schedule_config:
                    return {"success": False, "error": "yearly mode must contain 'day'"}
        
        else:
            return {"success": False, "error": f"Invalid schedule_type: {schedule_type}. Valid types: delay, scheduled"}
        
        storage = get_task_storage()
        scheduler = get_task_scheduler()
        
        # 获取repeat参数（仅scheduled类型有效）
        repeat = schedule_config.pop("repeat", False) if schedule_type == "scheduled" else False
        
        task = storage.create_task(
            user_id=user_id,
            session_id=session_id,
            task_name=task_name,
            prompt=prompt,
            schedule_type=schedule_type,
            schedule_config=schedule_config
        )
        
        # 设置repeat
        if schedule_type == "scheduled" and repeat:
            task.repeat = True
            storage.update_task(task.task_id, repeat=True)
        
        # 通知调度器新任务
        scheduler.add_task(task)
        
        logger.info(f"创建定时任务: {task.task_id} - {task_name}")
        
        return {
            "success": True,
            "task": scheduler.get_task_info(task)
        }
    
    async def _handle_delete_task(self, user_id: int, task_id: str) -> Dict[str, Any]:
        """删除定时任务"""
        from .task_storage import get_task_storage
        
        storage = get_task_storage()
        
        # 验证任务属于该用户
        task = storage.get_task(task_id)
        if not task:
            return {"success": False, "error": "Task not found"}
        
        if task.user_id != user_id:
            return {"success": False, "error": "Task does not belong to user"}
        
        if storage.delete_task(task_id):
            logger.info(f"删除定时任务: {task_id}")
            return {"success": True}
        else:
            return {"success": False, "error": "Failed to delete task"}
    
    async def _handle_update_task(self, user_id: int, task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新定时任务"""
        from .task_storage import get_task_storage
        from .task_scheduler import get_task_scheduler
        
        storage = get_task_storage()
        scheduler = get_task_scheduler()
        
        # 验证任务属于该用户
        task = storage.get_task(task_id)
        if not task:
            return {"success": False, "error": "Task not found"}
        
        if task.user_id != user_id:
            return {"success": False, "error": "Task does not belong to user"}
        
        # 可更新的字段
        allowed_fields = ["task_name", "prompt", "schedule_type", "schedule_config", "enabled"]
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not filtered_updates:
            return {"success": False, "error": "No valid fields to update"}
        
        # 更新任务
        updated_task = storage.update_task(task_id, **filtered_updates)
        if updated_task:
            logger.info(f"更新定时任务: {task_id}, 更新字段: {list(filtered_updates.keys())}")
            return {
                "success": True,
                "task": scheduler.get_task_info(updated_task)
            }
        else:
            return {"success": False, "error": "Failed to update task"}
    
    async def _handle_list_agents(self) -> List[str]:
        """获取可用智能体列表"""
        return list(config.OPENCODE_SUPPORTED_AGENTS)
    
    async def _handle_list_models(self) -> List[str]:
        """获取可用模型列表"""
        return list(config.OPENCODE_SUPPORTED_MODELS)
    
    async def _handle_get_user_config(self, user_id: int) -> Dict[str, Any]:
        """获取用户配置的回调函数"""
        if not self.session_manager:
            return {"agent": "", "model": "", "provider": ""}
        
        user_config = self.session_manager.get_user_config(user_id)
        if user_config:
            return {
                "agent": user_config.agent or "",
                "model": user_config.model or "",
                "provider": user_config.provider or ""
            }
        return {"agent": "", "model": "", "provider": ""}
    
    async def _handle_set_user_config(self, user_id: int, key: str, value: Any) -> Dict[str, Any]:
        """设置用户配置的回调函数"""
        if not self.session_manager:
            return {"success": False, "error": "Session manager not available"}
        
        result = {"success": True}
        
        if key == "agent":
            # 验证智能体是否在支持列表中
            matched_agent = None
            if value in config.OPENCODE_SUPPORTED_AGENTS:
                matched_agent = value
            else:
                # 尝试不区分大小写匹配
                for agent in config.OPENCODE_SUPPORTED_AGENTS:
                    if agent.lower() == str(value).lower():
                        matched_agent = agent
                        break
            
            if not matched_agent:
                return {
                    "success": False,
                    "error": f"Invalid agent: {value}. Available agents: {', '.join(config.OPENCODE_SUPPORTED_AGENTS[:5])}..."
                }
            
            self.session_manager.update_user_config(user_id, agent=matched_agent)
            logger.info(f"用户 {user_id} 智能体已更新为: {matched_agent}")
            result["agent"] = matched_agent
            
        elif key == "model":
            # 验证模型是否在支持列表中
            matched_model = None
            model_str = str(value)
            
            # 检查是否为完整模型ID
            if model_str in config.OPENCODE_SUPPORTED_MODELS:
                matched_model = model_str
            else:
                # 尝试不区分大小写匹配
                for model in config.OPENCODE_SUPPORTED_MODELS:
                    if model.lower() == model_str.lower():
                        matched_model = model
                        break
                
                # 尝试匹配模型名称的最后一部分
                if not matched_model:
                    for model in config.OPENCODE_SUPPORTED_MODELS:
                        parts = model.split("/")
                        if len(parts) >= 2 and parts[-1].lower() == model_str.lower():
                            matched_model = model
                            break
            
            if not matched_model:
                return {
                    "success": False,
                    "error": f"Invalid model: {value}. Use /api/model/list to see available models."
                }
            
            # 从模型ID中提取provider
            if "/" in matched_model:
                provider = matched_model.split("/")[0]
                self.session_manager.update_user_config(user_id, model=matched_model, provider=provider)
                result["provider"] = provider
            else:
                self.session_manager.update_user_config(user_id, model=matched_model)
            result["model"] = matched_model
            logger.info(f"用户 {user_id} 模型已更新为: {matched_model}")
        else:
            return {"success": False, "error": f"Unknown config key: {key}"}
        
        return result
    
    async def _handle_http_reload(self) -> Dict[str, Any]:
        """处理 HTTP 热重载请求的回调函数"""
        logger.info("收到 HTTP 热重载请求")
        
        try:
            result = await self.perform_hot_reload()
            return result
        except Exception as e:
            logger.error(f"HTTP 热重载请求处理失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def perform_hot_reload(self) -> Dict[str, Any]:
        """执行热重载（重载代码和配置，不退出进程）"""
        import importlib
        
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
    
    async def _handle_http_restart(self) -> Dict[str, Any]:
        """处理 HTTP 重启请求的回调函数"""
        logger.info("收到 HTTP 重启请求")
        
        try:
            # 调用重启处理器
            await self.restart_handler.perform_restart()
            return {"success": True, "message": "重启已启动"}
        except Exception as e:
            logger.error(f"HTTP 重启请求处理失败: {e}")
            return {"success": False, "error": str(e)}

    def register_default_handlers(self):
        """注册默认消息处理器"""
        # 处理元事件（心跳等）
        self.on_message('meta_event', self.event_handlers.handle_meta_event)
        
        # 处理消息事件
        self.on_message('message', self.event_handlers.handle_message_event)
        
        # 处理通知事件
        self.on_message('notice', self.event_handlers.handle_notice_event)
        
        # 处理请求事件
        self.on_message('request', self.event_handlers.handle_request_event)
    

    
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