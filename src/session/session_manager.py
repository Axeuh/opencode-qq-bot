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
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserSession':
        """从字典创建"""
        return cls(**data)
    
    def update_access(self) -> None:
        """更新访问时间"""
        self.last_accessed = time.time()
        self.message_count += 1
    



@dataclass
class UserConfig:
    """用户配置"""
    user_id: int
    agent: str = config.OPENCODE_DEFAULT_AGENT
    model: str = config.OPENCODE_DEFAULT_MODEL
    provider: str = config.OPENCODE_DEFAULT_PROVIDER
    directory: str = config.OPENCODE_DIRECTORY
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserConfig':
        """从字典创建"""
        return cls(**data)


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
                directory=config_obj.directory,
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
                "last_accessed": time.time()
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
        provider: Optional[str] = None,
        directory: Optional[str] = None
    ) -> Optional[UserConfig]:
        """
        更新用户配置
        
        Args:
            user_id: QQ 用户 ID
            agent: 智能体
            model: 模型
            provider: 提供商
            directory: 工作目录
            
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
            if directory is not None:
                config_obj.directory = directory
                updated = True
            
            # 同时更新当前会话的配置（如果存在）
            session = self.user_sessions.get(user_id)
            if session:
                if agent is not None:
                    session.agent = agent
                if model is not None:
                    session.model = model
                if provider is not None:
                    session.provider = provider
                if directory is not None:
                    session.directory = directory
            
            if updated:
                logger.info(f"更新用户配置：用户={user_id}, agent={agent}, model={model}, provider={provider}, directory={directory}")
                self.save_to_file()
            
            return config_obj
    
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
            new_session = UserSession(
                user_id=user_id,
                session_id=target_session_id,
                title=str(target_session_info.get("title", f"QQ 用户_{user_id}")),
                agent=current_session.agent if current_session else config.OPENCODE_DEFAULT_AGENT,
                model=current_session.model if current_session else config.OPENCODE_DEFAULT_MODEL,
                provider=current_session.provider if current_session else config.OPENCODE_DEFAULT_PROVIDER,
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
                        
                        # 转换旧的模型格式：deepseek/deepseek-chat -> deepseek-chat
                        # 转换旧的模型格式：deepseek/deepseek-reasoner -> deepseek-reasoner
                        if session.model and session.model.startswith("deepseek/deepseek-"):
                            old_model = session.model
                            session.model = session.model.replace("deepseek/deepseek-", "deepseek-")
                            logger.info(f"转换会话模型格式: 用户={session.user_id}, {old_model} -> {session.model}")
                        
                        self.user_sessions[session.user_id] = session
                    except Exception as e:
                        logger.warning(f"加载会话数据失败: {e}")
                
                # 加载用户配置
                self.user_configs.clear()
                for config_data in data.get("user_configs", []):
                    try:
                        config_obj = UserConfig.from_dict(config_data)
                        
                        # 转换模型格式以确保一致性
                        # 1. 将简短的deepseek模型转换为完整格式（向后兼容）
                        # 2. 确保所有模型使用供应商/模型格式
                        if config_obj.model:
                            old_model = config_obj.model
                            
                            # 如果是简短的deepseek模型，转换为完整格式
                            if config_obj.model in ["deepseek-chat", "deepseek-reasoner"]:
                                config_obj.model = f"deepseek/{config_obj.model}"
                                logger.info(f"转换简短模型格式为完整格式: 用户={config_obj.user_id}, {old_model} -> {config_obj.model}")
                            # 如果是旧的完整格式（deepseek/deepseek-chat），转换为正确格式（deepseek/deepseek-chat保持不变）
                            elif config_obj.model.startswith("deepseek/deepseek-"):
                                # 已经是对的正确格式，无需转换
                                pass
                            # 检查是否需要添加供应商前缀
                            elif "/" not in config_obj.model:
                                # 没有供应商前缀，默认为opencode
                                if not config_obj.model.startswith("opencode/"):
                                    config_obj.model = f"opencode/{config_obj.model}"
                                    logger.info(f"添加默认供应商前缀: 用户={config_obj.user_id}, {old_model} -> {config_obj.model}")
                        
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