#!/usr/bin/env python3
"""
会话持久化管理器
负责会话数据的文件存储和加载
"""

import json
import logging
import time
import os
import tempfile
import shutil
from typing import Dict, Any, Optional, List
from pathlib import Path

try:
    from ..utils import config
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from src.utils import config
    except ImportError:
        import config  # pyright: ignore[reportMissingImports]

from .user_session import UserSession
from .user_config import UserConfig

logger = logging.getLogger(__name__)


class SessionPersistence:
    """会话持久化管理器"""
    
    def __init__(self, file_path: str, enable_ntfy: bool = False, ntfy_topic: str = "aaa"):
        """
        初始化持久化管理器
        
        Args:
            file_path: 数据文件路径
            enable_ntfy: 是否启用ntfy通知
            ntfy_topic: ntfy主题
        """
        self.file_path = file_path
        self.enable_ntfy = enable_ntfy
        self.ntfy_topic = ntfy_topic
        
        # 确保文件路径是绝对路径
        if not os.path.isabs(self.file_path):
            self.file_path = os.path.abspath(self.file_path)
        
        # 确保目录存在
        self._ensure_directory_exists()
    
    def _ensure_directory_exists(self) -> None:
        """确保数据文件目录存在"""
        target_dir = os.path.dirname(self.file_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
    
    def load_all(
        self
    ) -> tuple[
        Dict[int, UserSession],
        Dict[int, UserConfig],
        Dict[int, List[Dict[str, Any]]]
    ]:
        """
        从文件加载所有数据
        
        Returns:
            元组: (user_sessions, user_configs, user_session_history)
        """
        user_sessions: Dict[int, UserSession] = {}
        user_configs: Dict[int, UserConfig] = {}
        user_session_history: Dict[int, List[Dict[str, Any]]] = {}
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 加载用户会话
            for session_data in data.get("user_sessions", []):
                try:
                    session = UserSession.from_dict(session_data)
                    
                    # 统一模型格式：只存储模型名称，不包含供应商前缀
                    if session.model and "/" in session.model:
                        old_model = session.model
                        parts = session.model.split("/", 1)
                        session.model = parts[1]
                        if not session.provider:
                            session.provider = parts[0]
                        logger.info(f"转换会话模型格式: 用户={session.user_id}, {old_model} -> {session.model}")
                    
                    user_sessions[session.user_id] = session
                except Exception as e:
                    logger.warning(f"加载会话数据失败: {e}")
            
            # 加载用户配置
            for config_data in data.get("user_configs", []):
                try:
                    config_obj = UserConfig.from_dict(config_data)
                    
                    # 统一模型格式
                    if config_obj.model:
                        old_model = config_obj.model
                        
                        if "/" in config_obj.model:
                            parts = config_obj.model.split("/", 1)
                            extracted_provider = parts[0]
                            extracted_model = parts[1]
                            config_obj.model = extracted_model
                            if not config_obj.provider:
                                config_obj.provider = extracted_provider
                            logger.info(f"分离模型前缀: 用户={config_obj.user_id}, {old_model} -> model={extracted_model}, provider={extracted_provider}")
                    
                    user_configs[config_obj.user_id] = config_obj
                except Exception as e:
                    logger.warning(f"加载用户配置失败: {e}")
            
            # 加载历史记录
            raw_history = data.get("user_session_history", {})
            
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
                                "created_at": time.time()
                            })
                        else:
                            # 新格式：字典
                            converted_history.append(item)
                    user_session_history[user_id] = converted_history
            
            # 如果没有历史记录，从会话数据初始化
            if not user_session_history:
                for session_data in data.get("user_sessions", []):
                    user_id = session_data.get("user_id")
                    if user_id is None:
                        continue
                    if isinstance(user_id, str):
                        try:
                            user_id = int(user_id)
                        except ValueError:
                            pass
                    
                    if user_id not in user_session_history:
                        user_session_history[user_id] = []
                    
                    user_session_history[user_id].append({
                        "session_id": session_data.get("session_id"),
                        "title": session_data.get("title", f"QQ用户_{user_id}_会话"),
                        "created_at": session_data.get("created_at", time.time()),
                        "last_accessed": session_data.get("last_accessed"),
                        "agent": session_data.get("agent"),
                        "model": session_data.get("model"),
                        "directory": session_data.get("directory", config.OPENCODE_DIRECTORY or "C:/"),
                        "tokens": session_data.get("tokens")
                    })
                logger.info(f"从user_sessions数组初始化了 {len(user_session_history)} 个用户的历史记录")
            
            logger.info(f"从文件加载数据成功: {self.file_path}")
            logger.info(f"  加载了 {len(user_sessions)} 个用户会话")
            logger.info(f"  加载了 {len(user_configs)} 个用户配置")
            
        except FileNotFoundError:
            logger.info(f"数据文件不存在，将创建新文件: {self.file_path}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
        except Exception as e:
            logger.error(f"加载文件失败: {e}")
        
        return user_sessions, user_configs, user_session_history
    
    def save_all(
        self,
        user_sessions: Dict[int, UserSession],
        user_configs: Dict[int, UserConfig],
        user_session_history: Dict[int, List[Dict[str, Any]]]
    ) -> bool:
        """
        保存所有数据到文件
        
        Args:
            user_sessions: 用户会话字典
            user_configs: 用户配置字典
            user_session_history: 用户会话历史字典
            
        Returns:
            是否成功保存
        """
        try:
            logger.debug(f"save_all: 准备保存数据，当前有 {len(user_sessions)} 个会话，{len(user_configs)} 个配置")
            
            data = {
                "user_sessions": [session.to_dict() for session in user_sessions.values()],
                "user_configs": [cfg.to_dict() for cfg in user_configs.values()],
                "user_session_history": user_session_history,
                "metadata": {
                    "saved_at": time.time(),
                    "session_count": len(user_sessions),
                    "config_count": len(user_configs)
                }
            }
            
            logger.debug(f"save_all: 当前工作目录 = {os.getcwd()}")
            logger.debug(f"save_all: 文件路径 = {self.file_path}")
            
            # 确保目标目录存在
            target_dir = os.path.dirname(self.file_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            
            temp_file = None
            try:
                # 使用临时文件确保原子性写入
                temp_fd, temp_file = tempfile.mkstemp(dir=target_dir or '.', suffix='.tmp')
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # 替换原文件
                shutil.move(temp_file, self.file_path)
                
                logger.info(f"save_all: 数据保存成功到 {self.file_path}，保存了 {len(user_sessions)} 个会话")
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
    
    def send_ntfy_notification(self, message: str, title: str) -> None:
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