"""
HTTP 回调处理模块
处理 HTTP 服务器接收到的各种请求
"""

import logging
import re
import uuid
from typing import Dict, List, Any, Optional

from src.utils import config
from src.utils.config_loader import is_excluded

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
    
    async def handle_list_agents(self) -> List[Dict[str, str]]:
        """获取可用智能体列表（从 opencode API 动态获取）
        
        Returns:
            智能体对象列表，每个对象包含 id 和 name 字段
        """
        if not self.opencode_client:
            logger.warning("OpenCode 客户端不可用，返回空智能体列表")
            return []
        
        agents_data, error = await self.opencode_client.get_agents()
        if error:
            logger.error(f"获取智能体列表失败: {error}")
            return []
        
        # 提取智能体列表，保留 id 和 name
        agents = []
        excluded_agents = config.OPENCODE_EXCLUDED_AGENTS or []
        if agents_data:
            for agent in agents_data:
                try:
                    if isinstance(agent, dict):
                        # OpenCode API 返回的数据可能使用 name 作为标识
                        # 优先使用 id，如果没有则使用 name
                        agent_id = agent.get("id") or agent.get("name", "")
                        agent_name = agent.get("name", agent_id)
                        # 用 id 做排除检查（因为 id 是唯一标识）
                        if agent_id and not is_excluded(agent_id, excluded_agents):
                            agents.append({
                                "id": agent_id,
                                "name": agent_name
                            })
                    elif isinstance(agent, str):
                        if agent and not is_excluded(agent, excluded_agents):
                            agents.append({
                                "id": agent,
                                "name": agent
                            })
                    else:
                        agent_str = str(agent) if agent else ""
                        if agent_str and not is_excluded(agent_str, excluded_agents):
                            agents.append({
                                "id": agent_str,
                                "name": agent_str
                            })
                except Exception as e:
                    logger.warning(f"处理智能体数据时出错: {e}, agent={agent}")
                    continue
        
        return agents
    
    async def handle_list_models(self) -> List[str]:
        """获取可用模型列表（从 opencode API 动态获取）"""
        if not self.opencode_client:
            logger.warning("OpenCode 客户端不可用，返回空模型列表")
            return []
        
        models_data, error = await self.opencode_client.get_models()
        if error:
            logger.error(f"获取模型列表失败: {error}")
            return []
        
        # 提取模型ID列表并过滤排除项
        models = []
        excluded_models = config.OPENCODE_EXCLUDED_MODELS or []
        if models_data:
            for model in models_data:
                try:
                    if isinstance(model, dict):
                        provider_id = model.get("provider_id", "")
                        model_id = model.get("model_id", "")
                        if provider_id and model_id:
                            full_model_id = f"{provider_id}/{model_id}"
                        else:
                            full_model_id = model_id or model.get("id") or ""
                        
                        if full_model_id and not is_excluded(full_model_id, excluded_models):
                            models.append(full_model_id)
                    elif isinstance(model, str):
                        if model and not is_excluded(model, excluded_models):
                            models.append(model)
                    else:
                        model_str = str(model) if model else ""
                        if model_str and not is_excluded(model_str, excluded_models):
                            models.append(model_str)
                except Exception as e:
                    logger.warning(f"处理模型数据时出错: {e}, model={model}")
                    continue
        
        return models
    
    # ==================== 用户配置回调 ====================
    
    async def handle_get_user_config(self, user_id: int) -> Dict[str, Any]:
        """获取用户配置的回调函数"""
        if not self.session_manager:
            return {"agent": "", "model": "", "provider": ""}
        
        user_config = self.session_manager.get_user_config(user_id)
        if user_config:
            # 构建完整的模型 ID (provider/model 格式)
            full_model_id = ""
            if user_config.model:
                if user_config.provider:
                    full_model_id = f"{user_config.provider}/{user_config.model}"
                else:
                    full_model_id = user_config.model
            
            return {
                "agent": user_config.agent or "",
                "model": full_model_id,  # 返回完整模型 ID
                "provider": user_config.provider or ""
            }
        return {"agent": "", "model": "", "provider": ""}
    
    async def handle_set_user_config(self, user_id: int, key: str, value: Any) -> Dict[str, Any]:
        """设置用户配置的回调函数"""
        if not self.session_manager:
            return {"success": False, "error": "Session manager not available"}
        
        result: Dict[str, Any] = {"success": True}
        
        if key == "agent":
            # 动态获取可用智能体列表进行验证
            available_agents = await self.handle_list_agents()
            matched_agent_id = None
            matched_agent_name = None
            
            # 尝试匹配智能体 ID 或 name
            for agent in available_agents:
                if isinstance(agent, dict):
                    agent_id = agent.get("id", "")
                    agent_name = agent.get("name", agent_id)
                    # 匹配 ID 或 name
                    if (agent_id == value or 
                        agent_id.lower() == str(value).lower() or
                        agent_name == value or
                        agent_name.lower() == str(value).lower()):
                        matched_agent_id = agent_id
                        matched_agent_name = agent_name
                        break
            
            if not matched_agent_id:
                available_ids = [a.get("id", a) if isinstance(a, dict) else a for a in available_agents]
                return {
                    "success": False,
                    "error": f"Invalid agent: {value}. Available agents: {', '.join(available_ids[:5])}"
                }
            
            # 存储智能体 ID
            self.session_manager.update_user_config(user_id, agent=matched_agent_id)
            logger.info(f"用户 {user_id} 智能体已更新为: {matched_agent_id} ({matched_agent_name})")
            result["agent"] = matched_agent_id
            result["agent_name"] = matched_agent_name
            
        elif key == "model":
            # 动态获取可用模型列表进行验证
            available_models = await self.handle_list_models()
            matched_model = None
            model_str = str(value)
            
            # 检查是否为完整模型ID
            if model_str in available_models:
                matched_model = model_str
            else:
                # 尝试不区分大小写匹配
                for model in available_models:
                    if model.lower() == model_str.lower():
                        matched_model = model
                        break
                
                # 尝试匹配模型名称的最后一部分
                if not matched_model:
                    for model in available_models:
                        parts = model.split("/")
                        if len(parts) >= 2 and parts[-1].lower() == model_str.lower():
                            matched_model = model
                            break
            
            if not matched_model:
                return {
                    "success": False,
                    "error": f"Invalid model: {value}. Use /api/model/list to see available models."
                }
            
            # 从模型ID中提取provider和模型名称
            if "/" in matched_model:
                parts = matched_model.split("/")
                provider = parts[0]
                model_name = parts[-1]  # 取最后一部分作为模型名称
                self.session_manager.update_user_config(user_id, model=model_name, provider=provider)
                result["provider"] = provider
                result["model"] = model_name
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
                "last_accessed": current_session.last_accessed,
                "directory": current_session.directory or ""
            }
        
        # 获取历史会话
        history = self.session_manager.get_user_session_history(user_id)
        history_info = []
        for session in history:
            info = {
                "session_id": session.get("session_id", ""),
                "title": session.get("title", ""),
                "created_at": session.get("created_at", 0),
                "last_accessed": session.get("last_accessed", 0),
                "directory": session.get("directory", "")
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
                    "last_accessed": new_session.last_accessed,
                    "directory": new_session.directory or ""
                }
            }
        except Exception as e:
            logger.error(f"切换会话失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def handle_create_session(self, user_id: int, title: Optional[str] = None) -> Dict[str, Any]:
        """创建新会话的回调函数"""
        if not self.session_manager:
            return {"success": False, "error": "Session manager not available"}
        
        if not self.opencode_client:
            return {"success": False, "error": "OpenCode client not available"}
        
        try:
            # 先调用OpenCode API创建真实会话
            session_title = title or f"QQ用户_{user_id}_会话"
            session_id, error = await self.opencode_client.create_session(title=session_title)
            
            if error or not session_id:
                logger.error(f"创建OpenCode会话失败: {error}")
                return {"success": False, "error": f"创建OpenCode会话失败: {error}"}
            
            # 创建本地映射
            new_session = self.session_manager.create_user_session(
                user_id=user_id,
                session_id=session_id,
                title=session_title
            )
            
            logger.info(f"用户 {user_id} 创建新会话: {session_id}")
            return {
                "success": True,
                "session": {
                    "session_id": new_session.session_id,
                    "title": new_session.title,
                    "created_at": new_session.created_at,
                    "last_accessed": new_session.last_accessed,
                    "directory": new_session.directory or ""
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
    
    async def handle_get_directory(self, user_id: int, session_id: str = None) -> Dict[str, Any]:
        """获取用户会话路径的回调函数
        
        Args:
            user_id: 用户ID
            session_id: 会话ID（可选，不传则使用当前会话）
        """
        if not self.session_manager:
            return {"directory": "/"}
        
        # 如果指定了session_id，获取指定会话的路径
        if session_id:
            session = self.session_manager.get_session_by_id(user_id, session_id)
            if session:
                return {"directory": session.directory or "/", "success": True}
            return {"directory": "/", "success": False, "error": "Session not found"}
        
        # 没有指定session_id，获取当前会话
        current_session = self.session_manager.get_user_session(user_id)
        if current_session:
            return {"directory": current_session.directory or "/", "success": True}
        
        # 没有当前会话，返回默认路径
        from ..utils import config
        return {"directory": config.OPENCODE_DIRECTORY or "/", "success": True}
    
    async def handle_set_directory(self, user_id: int, directory: str, session_id: str = None) -> Dict[str, Any]:
        """设置用户会话路径的回调函数
        
        Args:
            user_id: 用户ID
            directory: 目录路径（空字符串表示重置为默认）
            session_id: 会话ID（可选，不传则使用当前会话）
        """
        if not self.session_manager:
            return {"success": False, "error": "Session manager not available"}
        
        # 获取目标会话
        target_session_id = None
        if session_id:
            # get_session_by_id 返回字典，不是 UserSession 对象
            session_info = self.session_manager.get_session_by_id(user_id, session_id)
            if session_info:
                target_session_id = session_info.get("session_id")
        else:
            current_session = self.session_manager.get_user_session(user_id)
            if current_session:
                target_session_id = current_session.session_id
        
        if not target_session_id:
            return {"success": False, "error": "No active session"}
        
        # 验证目录格式
        if not isinstance(directory, str):
            return {"success": False, "error": "Invalid directory"}
        
        directory = directory.strip()
        
        # 如果目录为空字符串，重置为默认路径
        if directory == "":
            success = self.session_manager.set_session_path(
                user_id=user_id,
                session_id=target_session_id,
                reset_to_default=True
            )
            # 获取重置后的路径
            if success:
                from ..utils import config
                directory = config.OPENCODE_DIRECTORY or "/"
        else:
            # 规范化目录路径
            logger.debug(f"原始目录: {directory}")
            # 只对Unix风格的相对路径添加/前缀
            # Windows路径（以盘符开头）保持原样
            if (not directory.startswith("/") and 
                not re.match(r'^[a-zA-Z]:[\\/]', directory)):
                directory = "/" + directory
                logger.debug(f"规范化后目录: {directory}")
            
            # 使用会话管理器设置路径
            success = self.session_manager.set_session_path(
                user_id=user_id,
                session_id=target_session_id,
                path=directory
            )
        
        if success:
            logger.info(f"用户 {user_id} 会话 {target_session_id} 路径已更新为: {directory}")
            return {
                "success": True,
                "directory": directory
            }
        else:
            return {
                "success": False,
                "error": "Failed to set session path"
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