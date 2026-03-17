"""
HTTP 回调处理模块
处理 HTTP 服务器接收到的各种请求
"""

import logging
import re
import uuid
from typing import Dict, List, Any, Optional

from src.utils import config

logger = logging.getLogger(__name__)


class HTTPCallbackHandler:
    """
    HTTP 回调处理器
    处理来自 HTTP 服务器的各种请求
    """
    
    def __init__(
        self,
        session_manager: Any,
        opencode_client: Any,
        hot_reload_callback: Any
    ):
        """
        初始化回调处理器
        
        Args:
            session_manager: 会话管理器实例
            opencode_client: OpenCode 客户端实例
            hot_reload_callback: 热重载回调函数
        """
        self.session_manager = session_manager
        self.opencode_client = opencode_client
        self.hot_reload_callback = hot_reload_callback
    
    # ==================== 任务管理回调 ====================
    
    async def handle_get_user_tasks(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户任务列表"""
        from .task_storage import get_task_storage
        from .task_scheduler import get_task_scheduler
        
        storage = get_task_storage()
        scheduler = get_task_scheduler()
        
        tasks = storage.get_user_tasks(user_id)
        return [scheduler.get_task_info(task) for task in tasks]
    
    async def handle_create_task(
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
    
    async def handle_delete_task(self, user_id: int, task_id: str) -> Dict[str, Any]:
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
    
    async def handle_update_task(self, user_id: int, task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
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
    
    # ==================== 智能体和模型回调 ====================
    
    async def handle_list_agents(self) -> List[str]:
        """获取可用智能体列表"""
        return list(config.OPENCODE_SUPPORTED_AGENTS)
    
    async def handle_list_models(self) -> List[str]:
        """获取可用模型列表"""
        return list(config.OPENCODE_SUPPORTED_MODELS)
    
    # ==================== 用户配置回调 ====================
    
    async def handle_get_user_config(self, user_id: int) -> Dict[str, Any]:
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
    
    async def handle_set_user_config(self, user_id: int, key: str, value: Any) -> Dict[str, Any]:
        """设置用户配置的回调函数"""
        if not self.session_manager:
            return {"success": False, "error": "Session manager not available"}
        
        result: Dict[str, Any] = {"success": True}
        
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
    
    # ==================== 会话管理回调 ====================
    
    async def handle_get_user_sessions(self, user_id: int) -> Dict[str, Any]:
        """获取用户会话列表的回调函数"""
        if not self.session_manager:
            return {"current": None, "history": [], "count": 0}
        
        # 获取当前会话
        current_session = self.session_manager.get_user_session(user_id)
        current_info = None
        if current_session:
            current_info = {
                "session_id": current_session.session_id,
                "title": current_session.title,
                "created_at": current_session.created_at,
                "last_accessed": current_session.last_accessed
            }
        
        # 获取历史会话
        history = self.session_manager.get_user_session_history(user_id)
        history_info = []
        for session in history:
            info = {
                "session_id": session.get("session_id", ""),
                "title": session.get("title", ""),
                "created_at": session.get("created_at", 0),
                "last_accessed": session.get("last_accessed", 0)
            }
            # 排除当前会话
            if current_info and info["session_id"] == current_info["session_id"]:
                continue
            history_info.append(info)
        
        total_count = (1 if current_info else 0) + len(history_info)
        
        return {
            "current": current_info,
            "history": history_info,
            "count": total_count
        }
    
    async def handle_switch_session(self, user_id: int, session_id: str) -> Dict[str, Any]:
        """切换会话的回调函数"""
        if not self.session_manager:
            return {"success": False, "error": "Session manager not available"}
        
        try:
            new_session = self.session_manager.switch_to_session(user_id, session_id)
            logger.info(f"用户 {user_id} 切换到会话: {session_id}")
            return {
                "success": True,
                "session": {
                    "session_id": new_session.session_id,
                    "title": new_session.title,
                    "created_at": new_session.created_at,
                    "last_accessed": new_session.last_accessed
                }
            }
        except Exception as e:
            logger.error(f"切换会话失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def handle_create_session(self, user_id: int, title: Optional[str] = None) -> Dict[str, Any]:
        """创建新会话的回调函数"""
        if not self.session_manager:
            return {"success": False, "error": "Session manager not available"}
        
        # 生成新的 session_id
        session_id = f"ses_{uuid.uuid4().hex[:16]}"
        
        try:
            new_session = self.session_manager.create_user_session(
                user_id=user_id,
                session_id=session_id,
                title=title
            )
            logger.info(f"用户 {user_id} 创建新会话: {session_id}")
            return {
                "success": True,
                "session": {
                    "session_id": new_session.session_id,
                    "title": new_session.title,
                    "created_at": new_session.created_at,
                    "last_accessed": new_session.last_accessed
                }
            }
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def handle_delete_session(self, user_id: int, session_id: str) -> Dict[str, Any]:
        """删除会话的回调函数"""
        if not self.session_manager:
            return {"success": False, "error": "Session manager not available"}
        
        try:
            result = self.session_manager.delete_session_by_id(user_id, session_id)
            if result:
                logger.info(f"用户 {user_id} 删除会话: {session_id}")
                return {"success": True}
            else:
                return {"success": False, "error": "Session not found"}
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def handle_set_session_title(self, user_id: int, session_id: str, title: str) -> Dict[str, Any]:
        """设置会话标题的回调函数"""
        if not self.session_manager:
            return {"success": False, "error": "Session manager not available"}
        
        try:
            result = self.session_manager.update_session_title(user_id, session_id, title)
            if result:
                logger.info(f"用户 {user_id} 设置会话标题: {session_id} -> {title}")
                return {"success": True}
            else:
                return {"success": False, "error": "Session not found"}
        except Exception as e:
            logger.error(f"设置会话标题失败: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== 目录管理回调 ====================
    
    async def handle_get_directory(self, user_id: int) -> Dict[str, Any]:
        """获取用户工作目录的回调函数"""
        if not self.session_manager:
            return {"directory": "/"}
        
        user_config = self.session_manager.get_user_config(user_id)
        if user_config:
            return {"directory": user_config.directory or "/"}
        return {"directory": "/"}
    
    async def handle_set_directory(self, user_id: int, directory: str) -> Dict[str, Any]:
        """设置用户工作目录的回调函数"""
        if not self.session_manager:
            return {"success": False, "error": "Session manager not available"}
        
        # 验证目录格式
        if not directory or not isinstance(directory, str):
            return {"success": False, "error": "Invalid directory"}
        
        # 规范化目录路径
        directory = directory.strip()
        logger.debug(f"原始目录: {directory}")
        # 只对Unix风格的相对路径添加/前缀
        # Windows路径（以盘符开头）保持原样
        if (not directory.startswith("/") and 
            not re.match(r'^[a-zA-Z]:[\\/]', directory)):
            directory = "/" + directory
            logger.debug(f"规范化后目录: {directory}")
        
        self.session_manager.update_user_config(user_id, directory=directory)
        logger.info(f"用户 {user_id} 工作目录已更新为: {directory}")
        
        return {
            "success": True,
            "directory": directory
        }
    
    # ==================== 热重载回调 ====================
    
    async def handle_http_reload(self) -> Dict[str, Any]:
        """处理 HTTP 热重载请求的回调函数"""
        logger.info("收到 HTTP 热重载请求")
        
        try:
            result = await self.hot_reload_callback()
            return result
        except Exception as e:
            logger.error(f"HTTP 热重载请求处理失败: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== 回调字典生成 ====================
    
    def get_callbacks(self) -> Dict[str, Any]:
        """
        获取所有回调函数的字典
        
        Returns:
            回调函数字典，可直接传递给 HTTPServer
        """
        return {
            'reload_callback': self.handle_http_reload,
            'get_user_config_callback': self.handle_get_user_config,
            'set_user_config_callback': self.handle_set_user_config,
            'list_agents_callback': self.handle_list_agents,
            'list_models_callback': self.handle_list_models,
            'get_user_tasks_callback': self.handle_get_user_tasks,
            'create_task_callback': self.handle_create_task,
            'update_task_callback': self.handle_update_task,
            'delete_task_callback': self.handle_delete_task,
            # Session 回调
            'get_user_sessions_callback': self.handle_get_user_sessions,
            'switch_session_callback': self.handle_switch_session,
            'create_session_callback': self.handle_create_session,
            'delete_session_callback': self.handle_delete_session,
            'set_session_title_callback': self.handle_set_session_title,
            # Directory 回调
            'get_directory_callback': self.handle_get_directory,
            'set_directory_callback': self.handle_set_directory
        }