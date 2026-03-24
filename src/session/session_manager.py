#!/usr/bin/env python3
"""
会话管理器
管理QQ用户到OpenCode会话的映射

支持：
- 用户会话映射（用户ID -> 会话ID）
- 用户配置存储（agent, model等）
- 持久化存储（内存、文件）
"""

import json
import logging
import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
try:
    from ..utils import config
except ImportError:
    # 当从外部脚本导入时
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from src.utils import config
    except ImportError:
        import config  # pyright: ignore[reportMissingImports]

logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    """用户会话数据"""
    user_id: int
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    title: str = ""
    
    # 用户配置
    agent: str = config.OPENCODE_DEFAULT_AGENT
    model: str = config.OPENCODE_DEFAULT_MODEL
    provider: str = config.OPENCODE_DEFAULT_PROVIDER
    directory: str = config.OPENCODE_DIRECTORY
    
    # 元数据
    group_id: Optional[int] = None  # 最近使用的群ID（如果有）
    message_count: int = 0
    is_active: bool = True
    system_prompt_sent: bool = False  # 系统提示词是否已发送
    tokens: Optional[Dict[str, int]] = None  # token统计 {total, input, output}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserSession':
        """从字典创建，过滤未知字段"""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)
    
    def update_access(self) -> None:
        """更新访问时间"""
        self.last_accessed = time.time()
        self.message_count += 1
    



@dataclass
class UserConfig:
    """用户配置"""
    user_id: int
    password: str = ""  # bcrypt哈希密码
    agent: str = config.OPENCODE_DEFAULT_AGENT
    model: str = config.OPENCODE_DEFAULT_MODEL
    provider: str = config.OPENCODE_DEFAULT_PROVIDER
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserConfig':
        """从字典创建，过滤未知字段"""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)


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
        
        # 确保文件路径是绝对路径（相对于项目根目录）
        import os
        if not os.path.isabs(self.file_path):
            # 转换为绝对路径（基于当前工作目录，假设是项目根目录）
            self.file_path = os.path.abspath(self.file_path)
        
        # 如果存储类型是文件，确保目录存在
        if self.storage_type == "file":
            target_dir = os.path.dirname(self.file_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
        
        # 存储
        self.user_sessions: Dict[int, UserSession] = {}  # 用户ID -> 当前活跃会话
        self.user_configs: Dict[int, UserConfig] = {}    # 用户ID -> 配置
        self.user_session_history: Dict[int, List[Dict[str, Any]]] = {}  # 用户ID -> 历史会话列表（包含ID、标题、创建时间）
        

        
        # 锁
        self.lock = threading.RLock()
        
        # 加载持久化数据
        if self.storage_type == "file":
            logger.info(f"初始化: 存储类型为file，尝试从 {self.file_path} 加载数据")
            load_result = self.load_from_file()
            logger.info(f"初始化: 数据加载结果: {'成功' if load_result else '失败'}")
        else:
            logger.info(f"初始化: 存储类型为 {self.storage_type}，使用内存存储")
        

        
        logger.info(f"会话管理器初始化完成，存储类型: {self.storage_type}")
        if self.storage_type == "file":
            logger.info(f"数据文件: {self.file_path}")
    

    

    

    
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
        
        Args:
            user_id: QQ用户ID
            session_id: OpenCode会话ID
            
        Returns:
            用户会话对象，如果不存在则返回None
        """
        with self.lock:
            # 先检查是否是当前会话
            current = self.user_sessions.get(user_id)
            if current and current.session_id == session_id:
                current.update_access()
                return current
            
            # 从历史记录中查找
            # 注意：历史记录只保存了会话信息，不是完整的UserSession对象
            # 如果需要完整数据，可能需要从持久化存储加载
            # 这里我们返回None，让调用者知道这个会话不在当前活跃状态
            return None
    
    def set_session_path(self, user_id: int, session_id: str, path: str = None, reset_to_default: bool = False) -> bool:
        """设置会话的工作路径
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            path: 新路径（如果reset_to_default为True则忽略）
            reset_to_default: 是否重置为默认路径
            
        Returns:
            是否成功设置
        """
        with self.lock:
            # 获取当前会话
            current = self.user_sessions.get(user_id)
            if not current or current.session_id != session_id:
                return False
            
            # 确定要设置的路径
            if reset_to_default:
                new_path = config.OPENCODE_DIRECTORY or "C:/"
            else:
                new_path = path
            
            # 更新当前会话的路径
            current.directory = new_path
            
            # 更新历史记录中该会话的路径
            history = self.user_session_history.get(user_id, [])
            for session_info in history:
                if session_info.get("session_id") == session_id:
                    session_info["directory"] = new_path
                    break
            
            # 保存到文件
            self.save_to_file()
            
            logger.info(f"用户 {user_id} 会话 {session_id} 路径设置为: {new_path}")
            return True
    
    def update_session_tokens(self, user_id: int, session_id: str, tokens: Dict[str, int]) -> bool:
        """
        更新会话的token统计
        
        Args:
            user_id: QQ用户ID
            session_id: OpenCode会话ID
            tokens: token统计 {total, input, output}
            
        Returns:
            bool: 是否更新成功
        """
        with self.lock:
            # 更新当前会话
            session = self.user_sessions.get(user_id)
            if session and session.session_id == session_id:
                session.tokens = tokens
                session.last_accessed = time.time()
                
                # 同时更新历史记录
                for session_info in self.user_session_history.get(user_id, []):
                    if session_info.get("session_id") == session_id:
                        session_info["tokens"] = tokens
                        break
                
                # 保存到文件
                self.save_to_file()
                logger.debug(f"用户 {user_id} 会话 {session_id} tokens 更新: {tokens}")
                return True
            
            # 如果不是当前会话，在历史记录中查找
            for session_info in self.user_session_history.get(user_id, []):
                if session_info.get("session_id") == session_id:
                    session_info["tokens"] = tokens
                    
                    # 保存到文件
                    self.save_to_file()
                    logger.debug(f"用户 {user_id} 历史会话 {session_id} tokens 更新: {tokens}")
                    return True
            
            logger.warning(f"未找到用户 {user_id} 的会话 {session_id}")
            return False
    
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
                # 使用传入的标题
                session_title = title
            elif group_id:
                # 在群聊中且未指定标题，使用群聊格式
                session_title = f"QQ用户_{user_id}_群{group_id}"
            else:
                # 私聊中且未指定标题，使用默认格式
                session_title = f"QQ用户_{user_id}"

            session = UserSession(
                user_id=user_id,
                session_id=session_id,
                title=session_title,
                group_id=group_id,
                agent=config_obj.agent,
                model=config_obj.model,
                provider=config_obj.provider,
                directory=config.OPENCODE_DIRECTORY or "C:/",  # 使用默认路径而不是用户配置
                created_at=time.time(),
                last_accessed=time.time()
            )
            
            # 保存到当前会话
            old_session = self.user_sessions.get(user_id)
            if old_session:
                logger.info(f"替换用户 {user_id} 的会话: {old_session.session_id} -> {session_id}")
            
            self.user_sessions[user_id] = session
            
            # 添加到历史记录（存储会话ID、标题、创建时间和最后访问时间）
            if user_id not in self.user_session_history:
                self.user_session_history[user_id] = []
            
# 限制历史记录数量
            history = self.user_session_history[user_id]
            history.append({
                "session_id": session_id,
                "title": session_title,
                "created_at": time.time(),
                "last_accessed": time.time(),
                "directory": config.OPENCODE_DIRECTORY or "C:/"  # 记录会话的默认目录
            })
            if len(history) > self.max_sessions_per_user:
                removed = history.pop(0)
                logger.debug(f"用户 {user_id} 历史会话超过限制，移除最旧会话: {removed.get('session_id', removed) if isinstance(removed, dict) else removed}")
            
            logger.info(f"创建用户会话: 用户={user_id}, 会话={session_id}, 标题={session_title}")
            
            # 保存到文件
            self.save_to_file()
            
            # 发送ntfy通知
            if self.enable_ntfy:
                self._send_ntfy_notification(
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
                # 如果用户没有配置，创建一个
                config_obj = UserConfig(user_id=user_id)
                self.user_configs[user_id] = config_obj
            
            updated = False
            if agent is not None:
                config_obj.agent = agent
                updated = True
            if model is not None:
                # 如果模型ID包含供应商前缀（如 deepseek/deepseek-reasoner）
                if "/" in model:
                    provider_parts = model.split("/", 1)
                    extracted_provider = provider_parts[0]
                    extracted_model_name = provider_parts[1]
                    # 更新模型名称（去掉前缀）
                    if config_obj.model != extracted_model_name:
                        config_obj.model = extracted_model_name
                        updated = True
                    # 更新供应商
                    if config_obj.provider != extracted_provider:
                        config_obj.provider = extracted_provider
                        updated = True
                else:
                    # 模型ID不包含前缀，只更新模型名称
                    if config_obj.model != model:
                        config_obj.model = model
                        updated = True
            if provider is not None:
                if config_obj.provider != provider:
                    config_obj.provider = provider
                    updated = True
            
            # 同时更新当前会话的配置（如果存在）
            session = self.user_sessions.get(user_id)
            if session:
                if agent is not None:
                    session.agent = agent
                if model is not None:
                    # 使用分离后的模型名称，保持与 config_obj 一致
                    session.model = config_obj.model
                if provider is not None:
                    # 使用提取或传入的供应商，保持与 config_obj 一致
                    session.provider = config_obj.provider
            
            if updated:
                logger.info(f"更新用户配置：用户={user_id}, agent={agent}, model={model}, provider={provider}")
                self.save_to_file()
            
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
            path: 要设置的路径（如果reset_to_default为True则忽略）
            reset_to_default: 是否重置为默认路径
            
        Returns:
            是否成功设置
        """
        with self.lock:
            # 获取要设置的会话
            target_session = None
            
            # 如果提供了session_id，查找对应会话
            if session_id:
                # 检查是否是当前会话
                current_session = self.user_sessions.get(user_id)
                if current_session and current_session.session_id == session_id:
                    target_session = current_session
                else:
                    # 在历史记录中查找会话
                    history = self.user_session_history.get(user_id, [])
                    for session_info in history:
                        if session_info.get("session_id") == session_id:
                            # 找到历史会话，但需要确保该会话存在用户会话中
                            # 如果不是当前会话，我们无法直接修改它的路径
                            # 在这种情况下，只修改当前会话或返回错误
                            pass
            
            # 如果没有指定session_id或未找到，使用当前会话
            if not target_session:
                target_session = self.user_sessions.get(user_id)
            
            if not target_session:
                logger.warning(f"未找到用户 {user_id} 的会话")
                return False
            
            # 确定要设置的路径
            if reset_to_default:
                # 重置为默认路径
                new_path = config.OPENCODE_DIRECTORY or "C:/"
                logger.info(f"重置用户 {user_id} 会话 {target_session.session_id} 路径为默认: {new_path}")
            elif path is not None:
                # 设置指定路径
                new_path = path
                logger.info(f"设置用户 {user_id} 会话 {target_session.session_id} 路径为: {new_path}")
            else:
                # 既没有指定路径也没有要求重置
                logger.warning(f"未指定路径也未要求重置: user_id={user_id}")
                return False
            
            # 更新会话路径
            target_session.directory = new_path
            
            # 同时更新历史记录中该会话的路径
            history = self.user_session_history.get(user_id, [])
            for session_info in history:
                if session_info.get("session_id") == target_session.session_id:
                    session_info["directory"] = new_path
                    break
            
            self.save_to_file()
            
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
            # 查找会话
            target_session = None
            
            # 检查当前会话
            current_session = self.user_sessions.get(user_id)
            if current_session and current_session.session_id == session_id:
                target_session = current_session
            else:
                # 在历史记录中查找
                history = self.user_session_history.get(user_id, [])
                for session_info in history:
                    if session_info.get("session_id") == session_id:
                        # 更新历史记录中的tokens
                        session_info["tokens"] = tokens
                        self.save_to_file()
                        return True
            
            if not target_session:
                logger.warning(f"未找到会话 {session_id}")
                return False
            
            # 更新tokens
            target_session.tokens = tokens
            
            # 同时更新历史记录
            history = self.user_session_history.get(user_id, [])
            for session_info in history:
                if session_info.get("session_id") == session_id:
                    session_info["tokens"] = tokens
                    break
            
            self.save_to_file()
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
            # 获取要查询的会话
            target_session = None
            
            # 如果提供了session_id，查找对应会话
            if session_id:
                # 检查是否是当前会话
                current_session = self.user_sessions.get(user_id)
                if current_session and current_session.session_id == session_id:
                    target_session = current_session
                else:
                    # 在历史记录中查找会话
                    history = self.user_session_history.get(user_id, [])
                    for session_info in history:
                        if session_info.get("session_id") == session_id:
                            # 历史会话中没有存储路径信息，返回默认路径
                            return config.OPENCODE_DIRECTORY or "C:/"
            
            # 如果没有指定session_id或未找到，使用当前会话
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
                
                # 发送ntfy通知
                if self.enable_ntfy:
                    self._send_ntfy_notification(
                        f"用户 {user_id} 删除OpenCode会话: {session_id}",
                        "会话删除"
                    )
                
                self.save_to_file()
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
            # 从历史记录中删除
            history = self.user_session_history.get(user_id, [])
            original_count = len(history)
            history = [s for s in history if s.get("session_id") != session_id]
            
            if len(history) < original_count:
                self.user_session_history[user_id] = history
                logger.info(f"删除会话：用户={user_id}, 会话={session_id}")
                
                # 发送 ntfy 通知
                if self.enable_ntfy:
                    self._send_ntfy_notification(
                        f"用户 {user_id} 删除会话：{session_id}",
                        "会话删除"
                    )
                
                self.save_to_file()
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
            # 删除当前会话
            deleted_count = 0
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
                deleted_count += 1
            
            # 删除所有历史记录
            history = self.user_session_history.get(user_id, [])
            deleted_count += len(history)
            
            if user_id in self.user_session_history:
                del self.user_session_history[user_id]
            
            if deleted_count > 0:
                logger.info(f"删除用户所有会话：用户={user_id}, 删除数量={deleted_count}")
                
                # 发送 ntfy 通知
                if self.enable_ntfy:
                    self._send_ntfy_notification(
                        f"用户 {user_id} 删除所有 {deleted_count} 个会话",
                        "批量删除会话"
                    )
                
                self.save_to_file()
            
            return deleted_count
    
    def get_user_config(self, user_id: int) -> Optional[UserConfig]:
        """获取用户配置"""
        with self.lock:
            return self.user_configs.get(user_id)
    
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
            # 生成bcrypt哈希
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            
            with self.lock:
                config_obj = self.user_configs.get(user_id)
                if not config_obj:
                    config_obj = UserConfig(user_id=user_id)
                    self.user_configs[user_id] = config_obj
                
                config_obj.password = hashed
                self.save_to_file()
                
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
            用户的会话历史列表，每个元素包含session_id, title, created_at
        """
        with self.lock:
            return self.user_session_history.get(user_id, [])
    
    def switch_to_session(self, user_id: int, target_session_id: str) -> UserSession:
        """切换到指定的会话
        
        Args:
            user_id: QQ 用户 ID
            target_session_id: 要切换到的会话 ID
            
        Returns:
            切换后的会话对象（总是返回，即使会话不在历史记录中）
        """
        with self.lock:
            # 检查历史记录中是否存在该会话
            history = self.user_session_history.get(user_id, [])
            target_session_info = None
            
            for session_info in history:
                if session_info.get("session_id") == target_session_id:
                    target_session_info = session_info
                    break
            
            # 如果会话不在历史记录中，创建新的会话信息
            if not target_session_info:
                target_session_info = {
                    "session_id": target_session_id,
                    "title": f"QQ 用户_{user_id}",
                    "created_at": time.time(),
                    "last_accessed": time.time()
                }
                # 添加到历史记录
                history.append(target_session_info)
                self.user_session_history[user_id] = history
                logger.info(f"创建新的会话信息并添加到历史记录：用户={user_id}, 会话={target_session_id}")
            else:
                # 【修复】更新历史记录中该会话的最后访问时间
                target_session_info["last_accessed"] = time.time()
                logger.debug(f"更新会话最后访问时间：用户={user_id}, 会话={target_session_id}")
            
# 获取当前会话
            current_session = self.user_sessions.get(user_id)
            
            # 创建新的会话对象
            # 确定目录：优先使用目标会话历史记录中的目录，否则使用当前会话目录，最后使用默认目录
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
            
            # 保存到当前会话
            self.user_sessions[user_id] = new_session
            
            logger.info(f"用户 {user_id} 切换到会话：{target_session_id}")
            
            # 保存到文件
            self.save_to_file()
            
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
            
            # 更新当前活跃会话的标题
            current_session = self.user_sessions.get(user_id)
            if current_session and current_session.session_id == session_id:
                old_title = current_session.title
                current_session.title = new_title
                logger.info(f"更新当前会话标题: 用户={user_id}, 会话={session_id}, {old_title} -> {new_title}")
                updated = True
            
            # 更新历史记录中的标题
            history = self.user_session_history.get(user_id, [])
            for session_info in history:
                if session_info.get("session_id") == session_id:
                    old_title = session_info.get("title", "")
                    session_info["title"] = new_title
                    logger.info(f"更新历史会话标题: 用户={user_id}, 会话={session_id}, {old_title} -> {new_title}")
                    updated = True
            
            if updated:
                self.save_to_file()
            
            return updated
    
    def get_session_by_id(self, user_id: int, session_id: str) -> Optional[Dict[str, Any]]:
        """根据会话ID获取会话信息（包括历史会话）
        
        Args:
            user_id: QQ用户ID
            session_id: 会话ID
            
        Returns:
            会话信息字典，包含session_id, title, created_at等
        """
        with self.lock:
            # 检查当前活跃会话
            current_session = self.user_sessions.get(user_id)
            if current_session and current_session.session_id == session_id:
                return {
                    "session_id": current_session.session_id,
                    "title": current_session.title,
                    "created_at": current_session.created_at,
                    "last_accessed": current_session.last_accessed,
                    "is_current": True
                }
            
            # 检查历史会话
            history = self.user_session_history.get(user_id, [])
            for session_info in history:
                if session_info.get("session_id") == session_id:
                    result = session_info.copy()
                    result["is_current"] = False
                    return result
            
            return None
    

    
    def load_from_file(self) -> bool:
        """
        从文件加载数据
        
        Returns:
            是否成功加载
        """
        if self.storage_type != "file":
            logger.debug(f"load_from_file: 存储类型不是file，而是 {self.storage_type}")
            return False
        
        try:
            import os
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            with self.lock:
                # 加载用户会话
                self.user_sessions.clear()
                for session_data in data.get("user_sessions", []):
                    try:
                        session = UserSession.from_dict(session_data)
                        
                        # 统一模型格式：只存储模型名称，不包含供应商前缀
                        if session.model and "/" in session.model:
                            old_model = session.model
                            parts = session.model.split("/", 1)
                            session.model = parts[1]
                            # 如果 session.provider 为空，使用提取的值
                            if not session.provider:
                                session.provider = parts[0]
                            logger.info(f"转换会话模型格式: 用户={session.user_id}, {old_model} -> {session.model}")
                        
                        self.user_sessions[session.user_id] = session
                    except Exception as e:
                        logger.warning(f"加载会话数据失败: {e}")
                
                # 加载用户配置
                self.user_configs.clear()
                for config_data in data.get("user_configs", []):
                    try:
                        config_obj = UserConfig.from_dict(config_data)
                        
                        # 统一模型格式：只存储模型名称，不包含供应商前缀
                        if config_obj.model:
                            old_model = config_obj.model
                            
                            # 如果模型包含供应商前缀，分离出来
                            if "/" in config_obj.model:
                                parts = config_obj.model.split("/", 1)
                                extracted_provider = parts[0]
                                extracted_model = parts[1]
                                config_obj.model = extracted_model
                                # 如果 provider 为空，使用提取的值
                                if not config_obj.provider:
                                    config_obj.provider = extracted_provider
                                logger.info(f"分离模型前缀: 用户={config_obj.user_id}, {old_model} -> model={extracted_model}, provider={extracted_provider}")
                        
                        self.user_configs[config_obj.user_id] = config_obj
                    except Exception as e:
                        logger.warning(f"加载用户配置失败: {e}")
                
                # 加载历史记录
                raw_history = data.get("user_session_history", {})
                self.user_session_history = {}
                
                # 转换键为整数（JSON键是字符串）并转换历史记录格式
                for user_id_str, history in raw_history.items():
                    try:
                        user_id = int(user_id_str)
                    except ValueError:
                        logger.warning(f"无法将历史记录键转换为整数: {user_id_str}")
                        user_id = user_id_str
                    
                    if isinstance(history, list):
                        converted_history = []
                        for item in history:
                            if isinstance(item, str):
                                # 旧格式：只有会话ID
                                converted_history.append({
                                    "session_id": item,
                                    "title": f"QQ用户_{user_id}_会话",
                                    "created_at": time.time()  # 未知，使用当前时间
                                })
                            else:
                                # 新格式：字典
                                converted_history.append(item)
                        self.user_session_history[user_id] = converted_history
                
                # 如果JSON中没有user_session_history或为空，从user_sessions数组初始化
                if not self.user_session_history:
                    # 从JSON数组按user_id分组
                    for session_data in data.get("user_sessions", []):
                        user_id = session_data.get("user_id")
                        if user_id is None:
                            continue
                        # 转换user_id为整数
                        if isinstance(user_id, str):
                            try:
                                user_id = int(user_id)
                            except ValueError:
                                pass
                        
                        if user_id not in self.user_session_history:
                            self.user_session_history[user_id] = []
                        
                        self.user_session_history[user_id].append({
                            "session_id": session_data.get("session_id"),
                            "title": session_data.get("title", f"QQ用户_{user_id}_会话"),
                            "created_at": session_data.get("created_at", time.time()),
                            "last_accessed": session_data.get("last_accessed"),
                            "agent": session_data.get("agent"),
                            "model": session_data.get("model"),
                            "directory": session_data.get("directory", config.OPENCODE_DIRECTORY or "C:/"),
                            "tokens": session_data.get("tokens")
                        })
                    logger.info(f"从user_sessions数组初始化了 {len(self.user_session_history)} 个用户的历史记录")

            
            logger.info(f"从文件加载数据成功: {self.file_path}")
            logger.info(f"  加载了 {len(self.user_sessions)} 个用户会话")
            logger.info(f"  加载了 {len(self.user_configs)} 个用户配置")
            return True
            
        except FileNotFoundError:
            logger.info(f"数据文件不存在，将创建新文件: {self.file_path}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
            return False
        except Exception as e:
            logger.error(f"加载文件失败: {e}")
            return False
    
    def save_to_file(self) -> bool:
        """
        保存数据到文件
        
        Returns:
            是否成功保存
        """
        if self.storage_type != "file":
            logger.debug(f"save_to_file: 存储类型不是file，而是 {self.storage_type}")
            return False
        
        try:
            with self.lock:
                logger.debug(f"save_to_file: 准备保存数据，当前有 {len(self.user_sessions)} 个会话，{len(self.user_configs)} 个配置")
                for user_id, session in self.user_sessions.items():
                    logger.debug(f"save_to_file: 会话 - 用户 {user_id}: {session.session_id} ({session.title})")
                
                data = {
                    "user_sessions": [session.to_dict() for session in self.user_sessions.values()],
                    "user_configs": [config.to_dict() for config in self.user_configs.values()],
                    "user_session_history": self.user_session_history,
                    "metadata": {
                        "saved_at": time.time(),
                        "session_count": len(self.user_sessions),
                        "config_count": len(self.user_configs)
                    }
                }
            
            # 使用临时文件确保原子性写入
            import tempfile
            import os
            
            # 调试信息：当前工作目录和文件路径
            logger.debug(f"save_to_file: 当前工作目录 = {os.getcwd()}")
            logger.debug(f"save_to_file: 文件路径 = {self.file_path}")
            logger.debug(f"save_to_file: 绝对文件路径 = {os.path.abspath(self.file_path)}")
            
            # 确保目标目录存在
            target_dir = os.path.dirname(self.file_path)
            if target_dir:  # 如果有目录部分
                os.makedirs(target_dir, exist_ok=True)
                logger.debug(f"save_to_file: 确保目录存在: {target_dir}")
            
            temp_file = None
            try:
                # 创建临时文件
                temp_fd, temp_file = tempfile.mkstemp(dir=os.path.dirname(self.file_path) or '.', suffix='.tmp')
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # 替换原文件
                import shutil
                shutil.move(temp_file, self.file_path)
                
                logger.info(f"save_to_file: 数据保存成功到 {self.file_path}，保存了 {len(self.user_sessions)} 个会话")
                return True
                
            except Exception as e:
                logger.error(f"保存文件失败: {e}")
                # 清理临时文件
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except:
                        pass
                return False
                
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            return False
    
    def _send_ntfy_notification(self, message: str, title: str) -> None:
        """发送ntfy通知"""
        if not self.enable_ntfy:
            return
        
        try:
            import sys
            sys.path.append(r'C:\Users\Axeuh\.config\opencode\skills\ntfy-notification\scripts')
            from send_notification import send_ntfy_notification  # pyright: ignore[reportMissingImports]
            
            response = send_ntfy_notification(
                topic=self.ntfy_topic,
                message=message,
                title=title,
                priority="default"
            )
            
            if response.status_code == 200:
                logger.debug(f"ntfy通知发送成功: {message}")
            else:
                logger.warning(f"ntfy通知发送失败: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"发送ntfy通知失败: {e}")
    
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
                self.save_to_file()
            
            # 发送ntfy通知
            if self.enable_ntfy:
                self._send_ntfy_notification(
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
                result = self.save_to_file()
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
        # 尝试调用shutdown，但析构函数可能不会在正确的时间被调用
        try:
            if self.storage_type == "file":
                self.save_to_file()
        except:
            pass  # 析构函数中忽略所有错误


# 全局会话管理器实例（单例模式）
_session_manager_instance: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    """获取全局会话管理器实例"""
    global _session_manager_instance
    if _session_manager_instance is None:
        logger.info("get_session_manager: 创建新的SessionManager实例（单例）")
        _session_manager_instance = SessionManager()
        
        # 注册atexit处理程序，确保程序退出时保存会话
        try:
            import atexit
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
        config = manager.get_user_config(123456)
        if config:
            print(f"用户配置: agent={config.agent}, model={config.model}")
        
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
        # 清理完成，不需要额外操作
        pass


if __name__ == "__main__":
    test_session_manager()