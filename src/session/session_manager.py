#!/usr/bin/env python3
"""
会话管理器
管理QQ用户到OpenCode会话的映射

支持：
- 用户会话映射（用户ID -> 会话ID）
- 用户配置存储（agent, model等）
- 持久化存储（内存、文件）
"""

import logging
import time
import threading
import atexit
from typing import Dict, List, Optional, Any

try:
    from ..utils import config
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from src.utils import config
    except ImportError:
        import config  # pyright: ignore[reportMissingImports]

from .user_session import UserSession
from .user_config import UserConfig
from .persistence import SessionPersistence

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器"""
    
    def __init__(
        self,
        storage_type: Optional[str] = None,
        file_path: Optional[str] = None,
        max_sessions_per_user: Optional[int] = None,
        enable_ntfy: bool = False,
        ntfy_topic: str = "aaa"
    ):
        """
        初始化会话管理器
        
        Args:
            storage_type: 存储类型（memory, file）
            file_path: 文件存储路径
            max_sessions_per_user: 每个用户最大会话数
            enable_ntfy: 是否启用ntfy通知
            ntfy_topic: ntfy主题
        """
        # 使用配置默认值
        config_data = config.OPENCODE_SESSION_CONFIG
        self.storage_type = storage_type or config_data.get("storage_type", "memory")
        self.file_path = file_path or config_data.get("file_path", "sessions.json")
        self.max_sessions_per_user = max_sessions_per_user or config_data.get("max_sessions_per_user", 10)
        self.enable_ntfy = enable_ntfy
        self.ntfy_topic = ntfy_topic
        
        # 初始化持久化管理器
        self._persistence = SessionPersistence(
            self.file_path,
            enable_ntfy=self.enable_ntfy,
            ntfy_topic=self.ntfy_topic
        )
        
        # 存储
        self.user_sessions: Dict[int, UserSession] = {}
        self.user_configs: Dict[int, UserConfig] = {}
        self.user_session_history: Dict[int, List[Dict[str, Any]]] = {}
        
        # 锁
        self.lock = threading.RLock()
        
        # 加载持久化数据
        if self.storage_type == "file":
            logger.info(f"初始化: 存储类型为file，尝试从 {self.file_path} 加载数据")
            self._load_data()
            logger.info(f"初始化: 数据加载完成")
        else:
            logger.info(f"初始化: 存储类型为 {self.storage_type}，使用内存存储")
        
        logger.info(f"会话管理器初始化完成，存储类型: {self.storage_type}")
        if self.storage_type == "file":
            logger.info(f"数据文件: {self.file_path}")
    
    def _load_data(self) -> None:
        """从持久化存储加载数据"""
        user_sessions, user_configs, user_session_history = self._persistence.load_all()
        self.user_sessions = user_sessions
        self.user_configs = user_configs
        self.user_session_history = user_session_history
    
    def _save_data(self) -> bool:
        """保存数据到持久化存储"""
        if self.storage_type != "file":
            return False
        return self._persistence.save_all(
            self.user_sessions,
            self.user_configs,
            self.user_session_history
        )
    
    def get_user_session(self, user_id: int) -> Optional[UserSession]:
        """
        获取用户当前会话
        
        Args:
            user_id: QQ用户ID
            
        Returns:
            用户会话对象，如果不存在则返回None
        """
        with self.lock:
            session = self.user_sessions.get(user_id)
            if session:
                session.update_access()
            return session
    
    def get_session_by_id(self, user_id: int, session_id: str) -> Optional[UserSession]:
        """
        根据session_id获取用户的指定会话
        
        会先检查当前活跃会话，如果没有匹配则从历史记录中查找。
        
        Args:
            user_id: QQ用户ID
            session_id: OpenCode会话ID
            
        Returns:
            用户会话对象，如果不存在则返回None
        """
        with self.lock:
            # 先检查当前活跃会话
            current = self.user_sessions.get(user_id)
            if current and current.session_id == session_id:
                current.update_access()
                return current
            
            # 从历史记录中查找
            history = self.user_session_history.get(user_id, [])
            for session_data in history:
                if isinstance(session_data, dict) and session_data.get("session_id") == session_id:
                    # 找到了，创建一个临时UserSession对象返回
                    return UserSession(
                        user_id=user_id,
                        session_id=session_id,
                        title=session_data.get("title", ""),
                        created_at=session_data.get("created_at", time.time()),
                        last_accessed=session_data.get("last_accessed", time.time()),
                        agent=session_data.get("agent", config.OPENCODE_DEFAULT_AGENT),
                        model=session_data.get("model", config.OPENCODE_DEFAULT_MODEL),
                        provider=session_data.get("provider", config.OPENCODE_DEFAULT_PROVIDER),
                        directory=session_data.get("directory", config.OPENCODE_DIRECTORY)
                    )
            
            return None
    
    def create_user_session(
        self,
        user_id: int,
        session_id: str,
        title: Optional[str] = None,
        group_id: Optional[int] = None,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ) -> UserSession:
        """
        创建用户会话（如果已存在则替换）
        
        Args:
            user_id: QQ用户ID
            session_id: OpenCode会话ID
            title: 会话标题
            group_id: 群ID（可选）
            agent: 智能体
            model: 模型
            provider: 提供商
            
        Returns:
            创建的会话对象
        """
        with self.lock:
            # 获取或创建用户配置
            config_obj = self.user_configs.get(user_id)
            if not config_obj:
                config_obj = UserConfig(user_id=user_id)
                self.user_configs[user_id] = config_obj
            
            # 更新用户配置（如果提供了新值）
            if agent:
                config_obj.agent = agent
            if model:
                config_obj.model = model
            if provider:
                config_obj.provider = provider
            
            # 构建标题
            if title is not None:
                session_title = title
            elif group_id:
                session_title = f"QQ用户_{user_id}_群{group_id}"
            else:
                session_title = f"QQ用户_{user_id}"

            session = UserSession(
                user_id=user_id,
                session_id=session_id,
                title=session_title,
                group_id=group_id,
                agent=config_obj.agent,
                model=config_obj.model,
                provider=config_obj.provider,
                directory=config.OPENCODE_DIRECTORY or "C:/",
                created_at=time.time(),
                last_accessed=time.time()
            )
            
            # 保存到当前会话
            old_session = self.user_sessions.get(user_id)
            if old_session:
                logger.info(f"替换用户 {user_id} 的会话: {old_session.session_id} -> {session_id}")
            
            self.user_sessions[user_id] = session
            
            # 添加到历史记录
            if user_id not in self.user_session_history:
                self.user_session_history[user_id] = []
            
            history = self.user_session_history[user_id]
            history.append({
                "session_id": session_id,
                "title": session_title,
                "created_at": time.time(),
                "last_accessed": time.time(),
                "directory": config.OPENCODE_DIRECTORY or "C:/"
            })
            if len(history) > self.max_sessions_per_user:
                removed = history.pop(0)
                logger.debug(f"用户 {user_id} 历史会话超过限制，移除最旧会话: {removed.get('session_id', removed) if isinstance(removed, dict) else removed}")
            
            logger.info(f"创建用户会话: 用户={user_id}, 会话={session_id}, 标题={session_title}")
            
            # 保存到文件
            self._save_data()
            
            # 发送ntfy通知
            if self.enable_ntfy:
                self._persistence.send_ntfy_notification(
                    f"用户 {user_id} 创建OpenCode会话: {session_id}",
                    "会话创建"
                )
            
            return session
    
    def update_user_config(
        self,
        user_id: int,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Optional[UserConfig]:
        """
        更新用户配置
        
        Args:
            user_id: QQ 用户 ID
            agent: 智能体
            model: 模型
            provider: 提供商
            
        Returns:
            更新后的配置对象，如果用户不存在则返回 None
        """
        with self.lock:
            config_obj = self.user_configs.get(user_id)
            if not config_obj:
                config_obj = UserConfig(user_id=user_id)
                self.user_configs[user_id] = config_obj
            
            updated = False
            if agent is not None:
                config_obj.agent = agent
                updated = True
            if model is not None:
                if "/" in model:
                    provider_parts = model.split("/", 1)
                    extracted_provider = provider_parts[0]
                    extracted_model_name = provider_parts[1]
                    if config_obj.model != extracted_model_name:
                        config_obj.model = extracted_model_name
                        updated = True
                    if config_obj.provider != extracted_provider:
                        config_obj.provider = extracted_provider
                        updated = True
                else:
                    if config_obj.model != model:
                        config_obj.model = model
                        updated = True
            if provider is not None:
                if config_obj.provider != provider:
                    config_obj.provider = provider
                    updated = True
            
            # 同时更新当前会话的配置
            session = self.user_sessions.get(user_id)
            if session:
                if agent is not None:
                    session.agent = agent
                if model is not None:
                    session.model = config_obj.model
                if provider is not None:
                    session.provider = config_obj.provider
            
            if updated:
                logger.info(f"更新用户配置：用户={user_id}, agent={agent}, model={model}, provider={provider}")
                self._save_data()
            
            return config_obj
    
    def get_user_config(self, user_id: int) -> Optional[UserConfig]:
        """
        获取用户配置
        
        Args:
            user_id: QQ 用户 ID
            
        Returns:
            用户配置对象，如果不存在则返回 None
        """
        with self.lock:
            return self.user_configs.get(user_id)
    
    def set_session_path(
        self,
        user_id: int,
        session_id: Optional[str] = None,
        path: Optional[str] = None,
        reset_to_default: bool = False
    ) -> bool:
        """
        设置会话路径
        
        Args:
            user_id: QQ用户ID
            session_id: 会话ID（如果为None则使用当前会话）
            path: 要设置的路径
            reset_to_default: 是否重置为默认路径
            
        Returns:
            是否成功设置
        """
        with self.lock:
            target_session = None
            target_session_id = session_id
            
            if session_id:
                # 先检查当前活跃会话
                current_session = self.user_sessions.get(user_id)
                if current_session and current_session.session_id == session_id:
                    target_session = current_session
                else:
                    # 从历史记录中查找并更新
                    history = self.user_session_history.get(user_id, [])
                    for session_info in history:
                        if session_info.get("session_id") == session_id:
                            # 找到了，直接更新历史记录中的directory
                            if reset_to_default:
                                new_path = config.OPENCODE_DIRECTORY or "C:/"
                            elif path is not None:
                                new_path = path
                            else:
                                logger.warning(f"未指定路径也未要求重置: user_id={user_id}")
                                return False
                            
                            session_info["directory"] = new_path
                            self._save_data()
                            logger.info(f"设置用户 {user_id} 历史会话 {session_id} 路径为: {new_path}")
                            return True
            
            if not target_session:
                target_session = self.user_sessions.get(user_id)
                if target_session:
                    target_session_id = target_session.session_id
            
            if not target_session:
                logger.warning(f"未找到用户 {user_id} 的会话")
                return False
            
            if reset_to_default:
                new_path = config.OPENCODE_DIRECTORY or "C:/"
                logger.info(f"重置用户 {user_id} 会话 {target_session.session_id} 路径为默认: {new_path}")
            elif path is not None:
                new_path = path
                logger.info(f"设置用户 {user_id} 会话 {target_session.session_id} 路径为: {new_path}")
            else:
                logger.warning(f"未指定路径也未要求重置: user_id={user_id}")
                return False
            
            target_session.directory = new_path
            
            history = self.user_session_history.get(user_id, [])
            for session_info in history:
                if session_info.get("session_id") == target_session.session_id:
                    session_info["directory"] = new_path
                    break
            
            self._save_data()
            return True
    
    def update_session_tokens(
        self,
        user_id: int,
        session_id: str,
        tokens: Dict[str, int]
    ) -> bool:
        """
        更新会话的token统计
        
        Args:
            user_id: QQ用户ID
            session_id: 会话ID
            tokens: token统计 {total, input, output}
            
        Returns:
            是否更新成功
        """
        with self.lock:
            target_session = None
            
            current_session = self.user_sessions.get(user_id)
            if current_session and current_session.session_id == session_id:
                target_session = current_session
            else:
                history = self.user_session_history.get(user_id, [])
                for session_info in history:
                    if session_info.get("session_id") == session_id:
                        session_info["tokens"] = tokens
                        self._save_data()
                        return True
            
            if not target_session:
                logger.warning(f"未找到会话 {session_id}")
                return False
            
            target_session.tokens = tokens
            
            history = self.user_session_history.get(user_id, [])
            for session_info in history:
                if session_info.get("session_id") == session_id:
                    session_info["tokens"] = tokens
                    break
            
            self._save_data()
            logger.debug(f"更新会话 {session_id} tokens: {tokens}")
            return True
    
    def get_session_path(
        self,
        user_id: int,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """
        获取会话路径
        
        Args:
            user_id: QQ用户ID
            session_id: 会话ID（如果为None则使用当前会话）
            
        Returns:
            会话路径，如果未找到则返回None
        """
        with self.lock:
            target_session = None
            
            if session_id:
                current_session = self.user_sessions.get(user_id)
                if current_session and current_session.session_id == session_id:
                    target_session = current_session
                else:
                    history = self.user_session_history.get(user_id, [])
                    for session_info in history:
                        if session_info.get("session_id") == session_id:
                            return config.OPENCODE_DIRECTORY or "C:/"
            
            if not target_session:
                target_session = self.user_sessions.get(user_id)
            
            if not target_session:
                return None
            
            return target_session.directory
    
    def delete_user_session(self, user_id: int) -> bool:
        """
        删除用户当前会话
        
        Args:
            user_id: QQ用户ID
            
        Returns:
            是否成功删除
        """
        with self.lock:
            if user_id in self.user_sessions:
                session_id = self.user_sessions[user_id].session_id
                del self.user_sessions[user_id]
                logger.info(f"删除用户会话: 用户={user_id}, 会话={session_id}")
                
                if self.enable_ntfy:
                    self._persistence.send_ntfy_notification(
                        f"用户 {user_id} 删除OpenCode会话: {session_id}",
                        "会话删除"
                    )
                
                self._save_data()
                return True
            return False
    
    def delete_session_by_id(self, user_id: int, session_id: str) -> bool:
        """根据会话 ID 删除指定会话
        
        Args:
            user_id: QQ 用户 ID
            session_id: 要删除的会话 ID
            
        Returns:
            是否成功删除
        """
        with self.lock:
            history = self.user_session_history.get(user_id, [])
            original_count = len(history)
            history = [s for s in history if s.get("session_id") != session_id]
            
            if len(history) < original_count:
                self.user_session_history[user_id] = history
                logger.info(f"删除会话：用户={user_id}, 会话={session_id}")
                
                if self.enable_ntfy:
                    self._persistence.send_ntfy_notification(
                        f"用户 {user_id} 删除会话：{session_id}",
                        "会话删除"
                    )
                
                self._save_data()
                return True
            return False
    
    def delete_all_sessions(self, user_id: int) -> int:
        """删除用户的所有会话
        
        Args:
            user_id: QQ 用户 ID
            
        Returns:
            删除的会话数量
        """
        with self.lock:
            deleted_count = 0
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
                deleted_count += 1
            
            history = self.user_session_history.get(user_id, [])
            deleted_count += len(history)
            
            if user_id in self.user_session_history:
                del self.user_session_history[user_id]
            
            if deleted_count > 0:
                logger.info(f"删除用户所有会话：用户={user_id}, 删除数量={deleted_count}")
                
                if self.enable_ntfy:
                    self._persistence.send_ntfy_notification(
                        f"用户 {user_id} 删除所有 {deleted_count} 个会话",
                        "批量删除会话"
                    )
                
                self._save_data()
            
            return deleted_count
    
    def set_user_password(self, user_id: int, password: str) -> bool:
        """设置用户密码（bcrypt哈希）
        
        Args:
            user_id: 用户ID
            password: 明文密码（最小6位）
            
        Returns:
            是否成功设置
        """
        if len(password) < 6:
            logger.warning(f"密码长度不足6位: user_id={user_id}")
            return False
        
        try:
            import bcrypt
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            
            with self.lock:
                config_obj = self.user_configs.get(user_id)
                if not config_obj:
                    config_obj = UserConfig(user_id=user_id)
                    self.user_configs[user_id] = config_obj
                
                config_obj.password = hashed
                self._save_data()
            
            logger.info(f"用户密码已设置: user_id={user_id}")
            return True
            
        except ImportError:
            logger.error("bcrypt模块未安装，无法设置密码")
            return False
        except Exception as e:
            logger.error(f"设置密码失败: {e}")
            return False
    
    def verify_user_password(self, user_id: int, password: str) -> bool:
        """验证用户密码
        
        Args:
            user_id: 用户ID
            password: 明文密码
            
        Returns:
            密码是否正确
        """
        with self.lock:
            config_obj = self.user_configs.get(user_id)
            if not config_obj or not config_obj.password:
                return False
            
            try:
                import bcrypt
                return bcrypt.checkpw(password.encode('utf-8'), config_obj.password.encode('utf-8'))
            except ImportError:
                logger.error("bcrypt模块未安装，无法验证密码")
                return False
            except Exception as e:
                logger.error(f"验证密码失败: {e}")
                return False
    
    def user_has_password(self, user_id: int) -> bool:
        """检查用户是否设置了密码
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否设置了密码
        """
        with self.lock:
            config_obj = self.user_configs.get(user_id)
            return config_obj is not None and bool(config_obj.password)
    
    def get_all_users(self) -> List[int]:
        """获取所有有会话的用户ID"""
        with self.lock:
            return list(self.user_sessions.keys())
    
    def get_session_count(self) -> int:
        """获取当前会话数量"""
        with self.lock:
            return len(self.user_sessions)
    
    def get_user_session_history(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的会话历史记录
        
        Args:
            user_id: QQ用户ID
            
        Returns:
            用户的会话历史列表
        """
        with self.lock:
            return self.user_session_history.get(user_id, [])
    
    def switch_to_session(self, user_id: int, target_session_id: str) -> UserSession:
        """切换到指定的会话
        
        Args:
            user_id: QQ 用户 ID
            target_session_id: 要切换到的会话 ID
            
        Returns:
            切换后的会话对象
        """
        with self.lock:
            history = self.user_session_history.get(user_id, [])
            target_session_info = None
            
            for session_info in history:
                if session_info.get("session_id") == target_session_id:
                    target_session_info = session_info
                    break
            
            if not target_session_info:
                target_session_info = {
                    "session_id": target_session_id,
                    "title": f"QQ 用户_{user_id}",
                    "created_at": time.time(),
                    "last_accessed": time.time()
                }
                history.append(target_session_info)
                self.user_session_history[user_id] = history
                logger.info(f"创建新的会话信息并添加到历史记录：用户={user_id}, 会话={target_session_id}")
            else:
                target_session_info["last_accessed"] = time.time()
                logger.debug(f"更新会话最后访问时间：用户={user_id}, 会话={target_session_id}")
            
            current_session = self.user_sessions.get(user_id)
            
            directory = target_session_info.get("directory") if target_session_info else None
            if not directory:
                if current_session:
                    directory = current_session.directory
                else:
                    directory = config.OPENCODE_DIRECTORY or "C:/"
            
            new_session = UserSession(
                user_id=user_id,
                session_id=target_session_id,
                title=str(target_session_info.get("title", f"QQ 用户_{user_id}")),
                agent=current_session.agent if current_session else config.OPENCODE_DEFAULT_AGENT,
                model=current_session.model if current_session else config.OPENCODE_DEFAULT_MODEL,
                provider=current_session.provider if current_session else config.OPENCODE_DEFAULT_PROVIDER,
                directory=directory,
                created_at=float(target_session_info.get("created_at", time.time())),
                last_accessed=time.time()
            )
            
            self.user_sessions[user_id] = new_session
            
            logger.info(f"用户 {user_id} 切换到会话：{target_session_id}")
            
            self._save_data()
            
            return new_session
    
    def update_session_title(self, user_id: int, session_id: str, new_title: str) -> bool:
        """更新会话标题
        
        Args:
            user_id: QQ用户ID
            session_id: 会话ID
            new_title: 新标题
            
        Returns:
            是否成功更新
        """
        with self.lock:
            updated = False
            
            current_session = self.user_sessions.get(user_id)
            if current_session and current_session.session_id == session_id:
                old_title = current_session.title
                current_session.title = new_title
                logger.info(f"更新当前会话标题: 用户={user_id}, 会话={session_id}, {old_title} -> {new_title}")
                updated = True
            
            history = self.user_session_history.get(user_id, [])
            for session_info in history:
                if session_info.get("session_id") == session_id:
                    old_title = session_info.get("title", "")
                    session_info["title"] = new_title
                    logger.info(f"更新历史会话标题: 用户={user_id}, 会话={session_id}, {old_title} -> {new_title}")
                    updated = True
            
            if updated:
                self._save_data()
            
            return updated
    
    def get_session_info_by_id(self, user_id: int, session_id: str) -> Optional[Dict[str, Any]]:
        """根据会话ID获取会话信息（包括历史会话）
        
        Args:
            user_id: QQ用户ID
            session_id: 会话ID
            
        Returns:
            会话信息字典
        """
        with self.lock:
            current_session = self.user_sessions.get(user_id)
            if current_session and current_session.session_id == session_id:
                return {
                    "session_id": current_session.session_id,
                    "title": current_session.title,
                    "created_at": current_session.created_at,
                    "last_accessed": current_session.last_accessed,
                    "is_current": True
                }
            
            history = self.user_session_history.get(user_id, [])
            for session_info in history:
                if session_info.get("session_id") == session_id:
                    result = session_info.copy()
                    result["is_current"] = False
                    return result
            
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            return {
                "total_sessions": len(self.user_sessions),
                "total_configs": len(self.user_configs),
                "active_users": len([s for s in self.user_sessions.values() if s.is_active]),
                "storage_type": self.storage_type,
            }
    
    def clear_all(self) -> None:
        """清除所有数据"""
        with self.lock:
            self.user_sessions.clear()
            self.user_configs.clear()
            self.user_session_history.clear()
            logger.warning("已清除所有会话数据")
            
            if self.storage_type == "file":
                self._save_data()
            
            if self.enable_ntfy:
                self._persistence.send_ntfy_notification(
                    "已清除所有会话数据",
                    "会话管理器清理"
                )
    
    def shutdown(self) -> bool:
        """显式关闭会话管理器，确保数据保存
        
        Returns:
            是否成功保存
        """
        logger.info("会话管理器正在关闭...")
        
        if self.storage_type == "file":
            try:
                result = self._save_data()
                if result:
                    logger.info("会话数据已保存")
                else:
                    logger.warning("会话数据保存失败")
                return result
            except Exception as e:
                logger.error(f"保存会话数据时出错: {e}")
                return False
        return True
    
    def __del__(self):
        """析构函数"""
        try:
            if self.storage_type == "file":
                self._save_data()
        except:
            pass
    
    # 兼容旧方法名
    def load_from_file(self) -> bool:
        """从文件加载数据（兼容旧API）"""
        if self.storage_type != "file":
            logger.debug(f"load_from_file: 存储类型不是file，而是 {self.storage_type}")
            return False
        
        self._load_data()
        return True
    
    def save_to_file(self) -> bool:
        """保存数据到文件（兼容旧API）"""
        return self._save_data()


# 全局会话管理器实例（单例模式）
_session_manager_instance: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    """获取全局会话管理器实例"""
    global _session_manager_instance
    if _session_manager_instance is None:
        logger.info("get_session_manager: 创建新的SessionManager实例（单例）")
        _session_manager_instance = SessionManager()
        
        # 注册atexit处理程序
        try:
            def save_on_exit():
                if _session_manager_instance:
                    logger.info("atexit: 程序退出，保存会话数据...")
                    _session_manager_instance.shutdown()
            atexit.register(save_on_exit)
            logger.debug("已注册atexit处理程序")
        except Exception as e:
            logger.warning(f"注册atexit处理程序失败: {e}")
    else:
        logger.debug(f"get_session_manager: 返回现有SessionManager实例，已有 {_session_manager_instance.get_session_count()} 个会话")
    return _session_manager_instance


# 测试函数
def test_session_manager():
    """测试会话管理器"""
    manager = SessionManager(storage_type="memory")
    
    try:
        # 创建会话
        session1 = manager.create_user_session(
            user_id=123456,
            session_id="ses_test_123",
            title="测试会话1"
        )
        print(f"创建会话: {session1.session_id}")
        
        # 获取会话
        session = manager.get_user_session(123456)
        if session:
            print(f"获取会话: {session.session_id}, 最后访问: {session.last_accessed}")
        
        # 更新配置
        manager.update_user_config(123456, agent="Sisyphus", model="claude-3-5-sonnet")
        print(f"更新配置完成")
        
        # 获取配置
        cfg = manager.get_user_config(123456)
        if cfg:
            print(f"用户配置: agent={cfg.agent}, model={cfg.model}")
        
        # 创建另一个会话（替换）
        session2 = manager.create_user_session(
            user_id=123456,
            session_id="ses_test_456",
            title="测试会话2"
        )
        print(f"替换会话: {session2.session_id}")
        
        # 获取统计信息
        stats = manager.get_stats()
        print(f"统计: {stats}")
        
        # 删除会话
        deleted = manager.delete_user_session(123456)
        print(f"删除会话: {'成功' if deleted else '失败'}")
        
    finally:
        pass


if __name__ == "__main__":
    test_session_manager()