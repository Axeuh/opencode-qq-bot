#!/usr/bin/env python3
"""
配置管理模块
用于管理QQ机器人的配置，包括日志设置、配置加载和验证
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from src.utils import config


def setup_logging() -> logging.Logger:
    """设置日志配置"""
    log_config = config.LOGGING_CONFIG
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_config["log_level"]))
    
    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建格式化器
    console_formatter = logging.Formatter(
        fmt=log_config.get("console_format", "[%(asctime)s] %(levelname)s - %(message)s"),
        datefmt=log_config["date_format"]
    )
    
    file_formatter = logging.Formatter(
        fmt=log_config["log_format"],
        datefmt=log_config["date_format"]
    )
    
    # 文件处理器（如果启用）
    if log_config["file_handler"]["enabled"]:
        # 确保日志目录存在
        import os
        log_file = log_config["log_file"]
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        try:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                filename=log_config["log_file"],
                maxBytes=log_config["file_handler"]["max_bytes"],
                backupCount=log_config["file_handler"]["backup_count"],
                encoding=log_config["file_handler"]["encoding"]
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(getattr(logging, log_config["log_level"]))
            root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"创建文件日志处理器失败：{e}")
            # 回退到基本的 FileHandler
            try:
                file_handler = logging.FileHandler(
                    filename=log_config["log_file"],
                    encoding=log_config["file_handler"]["encoding"]
                )
                file_handler.setFormatter(file_formatter)
                file_handler.setLevel(getattr(logging, log_config["log_level"]))
                root_logger.addHandler(file_handler)
            except Exception as e2:
                print(f"创建基本文件日志处理器也失败：{e2}")
    
    # 错误日志单独保存（如果启用）
    if log_config["error_log_separate"]["enabled"]:
        # 确保错误日志目录存在
        import os
        error_log_file = log_config["error_log_separate"]["error_log_file"]
        error_log_dir = os.path.dirname(error_log_file)
        if error_log_dir:
            os.makedirs(error_log_dir, exist_ok=True)
        
        try:
            from logging.handlers import RotatingFileHandler
            error_handler = RotatingFileHandler(
                filename=log_config["error_log_separate"]["error_log_file"],
                maxBytes=log_config["error_log_separate"]["max_bytes"],
                backupCount=log_config["error_log_separate"]["backup_count"],
                encoding=log_config["file_handler"]["encoding"]
            )
            error_handler.setFormatter(file_formatter)
            error_handler.setLevel(logging.ERROR)  # 只记录 ERROR 及以上级别
            root_logger.addHandler(error_handler)
        except Exception as e:
            print(f"创建错误日志处理器失败：{e}")
    
    # 控制台处理器（如果启用）
    if log_config["console_handler"]["enabled"]:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(getattr(logging, log_config["log_level"]))
        root_logger.addHandler(console_handler)
    
    return root_logger


class ConfigManager:
    """配置管理器，提供统一的配置访问接口"""
    
    def __init__(self):
        """初始化配置管理器"""
        self._config = config
        
    @property
    def ws_url(self) -> str:
        """WebSocket服务器URL"""
        return self._config.WS_URL
    
    @property
    def access_token(self) -> Optional[str]:
        """访问令牌"""
        return self._config.ACCESS_TOKEN
    
    @property
    def heartbeat_interval(self) -> int:
        """心跳间隔（秒）"""
        return self._config.HEARTBEAT_INTERVAL
    
    @property
    def reconnect_interval(self) -> int:
        """重连间隔（秒）"""
        return self._config.RECONNECT_INTERVAL
    
    @property
    def bot_name(self) -> str:
        """机器人名称"""
        return self._config.BOT_NAME
    
    @property
    def bot_qq_id(self) -> Optional[int]:
        """机器人QQ号"""
        return self._config.BOT_QQ_ID
    
    @property
    def file_config(self) -> Dict[str, Any]:
        """文件处理配置"""
        return {
            "download_dir": self._config.DOWNLOAD_DIR,
            "temp_dir": self._config.TEMP_DIR,
            "max_file_size": self._config.MAX_FILE_SIZE,
            "allowed_extensions": self._config.ALLOWED_EXTENSIONS,
            "enable_auto_download": self._config.ENABLE_AUTO_DOWNLOAD
        }
    
    @property
    def whitelist_config(self) -> Dict[str, Any]:
        """白名单配置"""
        return {
            "qq_user_whitelist": self._config.QQ_USER_WHITELIST,
            "group_whitelist": self._config.GROUP_WHITELIST,
            "enable_at_mention": self._config.ENABLE_AT_MENTION
        }
    
    @property
    def opencode_config(self) -> Dict[str, Any]:
        """OpenCode集成配置"""
        return {
            "base_url": self._config.OPENCODE_BASE_URL,
            "auth": self._config.OPENCODE_AUTH,
            "cookies": self._config.OPENCODE_COOKIES,
            "timeout": self._config.OPENCODE_TIMEOUT,
            "directory": self._config.OPENCODE_DIRECTORY,
            "default_agent": self._config.OPENCODE_DEFAULT_AGENT,
            "default_model": self._config.OPENCODE_DEFAULT_MODEL,
            "default_provider": self._config.OPENCODE_DEFAULT_PROVIDER,
            "enabled_features": self._config.OPENCODE_ENABLED_FEATURES,
            "message_config": self._config.OPENCODE_MESSAGE_CONFIG,
            "system_prompt": self._config.OPENCODE_SYSTEM_PROMPT
        }
    
    @property
    def enabled_features(self) -> Dict[str, bool]:
        """启用功能配置"""
        return self._config.ENABLED_FEATURES
    
    @property
    def special_replies(self) -> Dict[str, str]:
        """特殊回复配置"""
        return self._config.SPECIAL_REPLIES
    
    def display_config_summary(self) -> None:
        """显示配置摘要"""
        print(f"=== 机器人配置摘要 ===")
        print(f"机器人名称: {self.bot_name}")
        print(f"WebSocket服务器: {self.ws_url}")
        print(f"启用功能: {self.enabled_features}")
        print(f"白名单用户数: {len(self.whitelist_config['qq_user_whitelist'])}")
        print(f"白名单群组数: {len(self.whitelist_config['group_whitelist'])}")
        print(f"OpenCode集成: {'可用' if self.opencode_config['base_url'] else '未配置'}")
        
    def validate_config(self) -> bool:
        """验证必要配置是否存在
        
        Returns:
            bool: 配置是否有效
        """
        required = [
            ("WS_URL", self.ws_url),
            ("BOT_NAME", self.bot_name)
        ]
        
        for name, value in required:
            if not value:
                print(f"错误：缺少必要配置 {name}")
                return False
        
        return True