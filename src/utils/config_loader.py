"""
配置加载模块
从 YAML 配置文件加载配置，并提供向后兼容的接口
"""

import os
import re
import fnmatch
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional


def matches_pattern(name: str, pattern: str) -> bool:
    """
    检查名称是否匹配通配符模式
    
    Args:
        name: 要检查的名称
        pattern: 通配符模式，支持 * 和 ?
        
    Returns:
        是否匹配
    """
    # 将通配符模式转换为正则表达式
    regex_pattern = fnmatch.translate(pattern)
    return bool(re.match(regex_pattern, name, re.IGNORECASE))


def is_excluded(name: str, excluded_patterns: List[str]) -> bool:
    """
    检查名称是否在排除列表中
    
    Args:
        name: 要检查的名称
        excluded_patterns: 排除模式列表
        
    Returns:
        是否被排除
    """
    if not excluded_patterns:
        return False
    
    for pattern in excluded_patterns:
        if matches_pattern(name, pattern):
            return True
    return False


class ConfigLoader:
    """配置加载器，支持 YAML 配置文件"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置加载器
        
        Args:
            config_path: 配置文件路径，如果为 None 则自动查找
        """
        self.config_path = config_path or self._find_config_file()
        self._config: Optional[Dict[str, Any]] = None
        self._load_config()
    
    def _find_config_file(self) -> str:
        """自动查找配置文件"""
        # 可能的配置文件路径
        possible_paths = [
            "config.yaml",
            "config.yml",
            Path(__file__).parent.parent.parent / "config.yaml",
            Path(__file__).parent.parent.parent / "config.yml",
            # mybot的配置文件路径
            Path(__file__).parent.parent.parent.parent / "mybot" / "config.yaml",
            Path(__file__).parent.parent.parent.parent / "mybot" / "config.yml",
        ]
        
        for path in possible_paths:
            path = Path(path) if not isinstance(path, Path) else path
            if path.exists():
                return str(path.absolute())
        
        # 如果都找不到，返回默认路径
        return str(Path(__file__).parent.parent.parent / "config.yaml")
    
    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件不存在：{self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件解析失败：{e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持点分隔的路径）
        
        Args:
            key: 配置键，如 "websocket.url"
            default: 默认值
            
        Returns:
            配置值
        """
        if self._config is None:
            return default
        
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    @property
    def config(self) -> Dict[str, Any]:
        """获取完整配置字典"""
        if self._config is None:
            raise ValueError("配置未加载")
        return self._config


# 全局配置加载器实例
_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """获取全局配置加载器"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


def reload_config(config_path: Optional[str] = None) -> ConfigLoader:
    """重新加载配置"""
    global _config_loader
    _config_loader = ConfigLoader(config_path)
    return _config_loader


# ==================== 向后兼容的接口 ====================
# 保持与原有代码兼容，提供相同的变量名

# 初始化全局配置加载器
_loader = get_config_loader()

# WebSocket 配置
WS_URL = _loader.get("websocket.url", "ws://localhost:3002")
ACCESS_TOKEN = _loader.get("websocket.access_token", "")
HEARTBEAT_INTERVAL = _loader.get("websocket.heartbeat_interval", 30000)
RECONNECT_INTERVAL = _loader.get("websocket.reconnect_interval", 5000)
WS_EXTRA_HEADERS = _loader.get("websocket.extra_headers", {})

# HTTP API 配置
HTTP_API_BASE_URL = _loader.get("http_api.base_url", "http://localhost:3001")
HTTP_API_ACCESS_TOKEN = _loader.get("http_api.access_token", "")
HTTP_API_TIMEOUT = _loader.get("http_api.timeout", 30)
HTTP_API_ENABLED = _loader.get("http_api.enabled", True)
HTTP_API_RETRY_COUNT = _loader.get("http_api.retry_count", 3)
HTTP_API_RETRY_DELAY = _loader.get("http_api.retry_delay", 1.0)

# 基础配置
DEBUG = _loader.get("bot.debug", False)
BOT_NAME = _loader.get("bot.name", "我的 QQ 机器人")
BOT_QQ_ID = _loader.get("bot.qq_id", "")
ADMIN_QQ = _loader.get("bot.admin_qq", "")

# 功能开关
ENABLED_FEATURES = _loader.get("features", {})

# 白名单配置
QQ_USER_WHITELIST = _loader.get("whitelist.qq_users", [])
GROUP_WHITELIST = _loader.get("whitelist.groups", [])

# OpenCode 配置
OPENCODE_HOST = _loader.get("opencode.host", "127.0.0.1")
OPENCODE_PORT = _loader.get("opencode.port", 4091)
OPENCODE_BASE_URL = f"http://{OPENCODE_HOST}:{OPENCODE_PORT}"
OPENCODE_DIRECTORY = _loader.get("opencode.directory", "C:/")
OPENCODE_TIMEOUT = _loader.get("opencode.timeout", 300)
OPENCODE_DEFAULT_AGENT = _loader.get("opencode.default_agent", "Sisyphus (Ultraworker)")
OPENCODE_DEFAULT_MODEL = _loader.get("opencode.default_model", "")
OPENCODE_DEFAULT_PROVIDER = _loader.get("opencode.default_provider", "")
OPENCODE_AUTH = _loader.get("opencode.auth", {})
OPENCODE_COOKIES = _loader.get("opencode.cookies", {})
OPENCODE_SUPPORTED_AGENTS = _loader.get("opencode.supported_agents", [])
OPENCODE_SUPPORTED_MODELS = _loader.get("opencode.supported_models", [])
OPENCODE_EXCLUDED_AGENTS = _loader.get("opencode.excluded_agents", [])
OPENCODE_EXCLUDED_MODELS = _loader.get("opencode.excluded_models", [])
OPENCODE_COMMAND_PREFIX = _loader.get("opencode.command_prefix", "/")

# 会话配置
OPENCODE_SESSION_CONFIG = _loader.get("session", {})

# 日志配置
LOGGING_CONFIG = _loader.get("logging", {})

# 文件处理配置
FILE_HANDLING_CONFIG = _loader.get("file_handling", {})
DOWNLOAD_DIR = _loader.get("file_handling.download_dir", "downloads")
TEMP_DIR = _loader.get("file_handling.napcat_temp_dir", "")
MAX_FILE_SIZE = _loader.get("file_handling.max_file_size", 52428800)
ALLOWED_EXTENSIONS = _loader.get("file_handling.allowed_extensions", [])
ENABLE_AUTO_DOWNLOAD = _loader.get("file_handling.auto_download", True)

# 特殊回复配置
SPECIAL_REPLIES = _loader.get("special_replies", {})
ENABLE_AT_MENTION = _loader.get("features.mention_bot", True)

# OpenCode 额外配置
OPENCODE_ENABLED_FEATURES = _loader.get("opencode.enabled_features", {})
OPENCODE_MESSAGE_CONFIG = _loader.get("opencode.message_config", {})
OPENCODE_SYSTEM_PROMPT = _loader.get("opencode.system_prompt", "")

# 自动回复配置
AUTO_REPLY_KEYWORDS = _loader.get("auto_reply.keywords", {})

# 消息处理配置
MESSAGE_CONFIG = _loader.get("message", {})

# 任务进度配置
TARGET_GROUP_ID = _loader.get("task_progress.target_group_id", 0)

# 定时任务调度器配置
TASK_SCHEDULER_CHECK_INTERVAL = _loader.get("task_scheduler.check_interval", 10)

# HTTP 服务器配置
HTTP_SERVER_ENABLED = _loader.get("http_server.enabled", True)
HTTP_SERVER_HOST = _loader.get("http_server.host", "127.0.0.1")
HTTP_SERVER_PORT = _loader.get("http_server.port", 8080)
HTTP_SERVER_HTTP_PORT = _loader.get("http_server.http_port", None)
HTTP_SERVER_ACCESS_TOKEN = _loader.get("http_server.access_token", "")
HTTP_SERVER_SSL_CERT = _loader.get("http_server.ssl_cert", None)
HTTP_SERVER_SSL_KEY = _loader.get("http_server.ssl_key", None)


def update_config_from_reload() -> None:
    """从重新加载的配置更新全局变量
    
    用于热重载时更新配置，不需要重启进程
    """
    global _loader
    global WS_URL, ACCESS_TOKEN, HEARTBEAT_INTERVAL, RECONNECT_INTERVAL, WS_EXTRA_HEADERS
    global HTTP_API_BASE_URL, HTTP_API_ACCESS_TOKEN, HTTP_API_TIMEOUT, HTTP_API_ENABLED
    global HTTP_API_RETRY_COUNT, HTTP_API_RETRY_DELAY
    global DEBUG, BOT_NAME, BOT_QQ_ID, ADMIN_QQ
    global ENABLED_FEATURES, QQ_USER_WHITELIST, GROUP_WHITELIST
    global OPENCODE_HOST, OPENCODE_PORT, OPENCODE_BASE_URL, OPENCODE_DIRECTORY, OPENCODE_TIMEOUT
    global OPENCODE_DEFAULT_AGENT, OPENCODE_DEFAULT_MODEL, OPENCODE_DEFAULT_PROVIDER
    global OPENCODE_AUTH, OPENCODE_COOKIES, OPENCODE_SUPPORTED_AGENTS, OPENCODE_SUPPORTED_MODELS
    global OPENCODE_EXCLUDED_AGENTS, OPENCODE_EXCLUDED_MODELS, OPENCODE_COMMAND_PREFIX, OPENCODE_SESSION_CONFIG, LOGGING_CONFIG
    global FILE_HANDLING_CONFIG, DOWNLOAD_DIR, TEMP_DIR, MAX_FILE_SIZE
    global ALLOWED_EXTENSIONS, ENABLE_AUTO_DOWNLOAD
    global SPECIAL_REPLIES, ENABLE_AT_MENTION
    global OPENCODE_ENABLED_FEATURES, OPENCODE_MESSAGE_CONFIG, OPENCODE_SYSTEM_PROMPT
    global AUTO_REPLY_KEYWORDS, MESSAGE_CONFIG, TARGET_GROUP_ID, TASK_SCHEDULER_CHECK_INTERVAL
    global HTTP_SERVER_ENABLED, HTTP_SERVER_HOST, HTTP_SERVER_PORT, HTTP_SERVER_HTTP_PORT, HTTP_SERVER_ACCESS_TOKEN, HTTP_SERVER_SSL_CERT, HTTP_SERVER_SSL_KEY
    
    # 重新加载配置
    _loader = ConfigLoader(_loader.config_path if _loader else None)
    
    # 更新所有全局变量
    WS_URL = _loader.get("websocket.url", "ws://localhost:3002")
    ACCESS_TOKEN = _loader.get("websocket.access_token", "")
    HEARTBEAT_INTERVAL = _loader.get("websocket.heartbeat_interval", 30000)
    RECONNECT_INTERVAL = _loader.get("websocket.reconnect_interval", 5000)
    WS_EXTRA_HEADERS = _loader.get("websocket.extra_headers", {})
    
    HTTP_API_BASE_URL = _loader.get("http_api.base_url", "http://localhost:3001")
    HTTP_API_ACCESS_TOKEN = _loader.get("http_api.access_token", "")
    HTTP_API_TIMEOUT = _loader.get("http_api.timeout", 30)
    HTTP_API_ENABLED = _loader.get("http_api.enabled", True)
    HTTP_API_RETRY_COUNT = _loader.get("http_api.retry_count", 3)
    HTTP_API_RETRY_DELAY = _loader.get("http_api.retry_delay", 1.0)
    
    DEBUG = _loader.get("bot.debug", False)
    BOT_NAME = _loader.get("bot.name", "我的 QQ 机器人")
    BOT_QQ_ID = _loader.get("bot.qq_id", "")
    ADMIN_QQ = _loader.get("bot.admin_qq", "")
    
    ENABLED_FEATURES = _loader.get("features", {})
    QQ_USER_WHITELIST = _loader.get("whitelist.qq_users", [])
    GROUP_WHITELIST = _loader.get("whitelist.groups", [])
    
    OPENCODE_HOST = _loader.get("opencode.host", "127.0.0.1")
    OPENCODE_PORT = _loader.get("opencode.port", 4091)
    OPENCODE_BASE_URL = f"http://{OPENCODE_HOST}:{OPENCODE_PORT}"
    OPENCODE_DIRECTORY = _loader.get("opencode.directory", "C:/")
    OPENCODE_TIMEOUT = _loader.get("opencode.timeout", 300)
    OPENCODE_DEFAULT_AGENT = _loader.get("opencode.default_agent", "Sisyphus (Ultraworker)")
    OPENCODE_DEFAULT_MODEL = _loader.get("opencode.default_model", "")
    OPENCODE_DEFAULT_PROVIDER = _loader.get("opencode.default_provider", "")
    OPENCODE_AUTH = _loader.get("opencode.auth", {})
    OPENCODE_COOKIES = _loader.get("opencode.cookies", {})
    OPENCODE_SUPPORTED_AGENTS = _loader.get("opencode.supported_agents", [])
    OPENCODE_SUPPORTED_MODELS = _loader.get("opencode.supported_models", [])
    OPENCODE_EXCLUDED_AGENTS = _loader.get("opencode.excluded_agents", [])
    OPENCODE_EXCLUDED_MODELS = _loader.get("opencode.excluded_models", [])
    OPENCODE_COMMAND_PREFIX = _loader.get("opencode.command_prefix", "/")
    
    OPENCODE_SESSION_CONFIG = _loader.get("session", {})
    LOGGING_CONFIG = _loader.get("logging", {})
    
    FILE_HANDLING_CONFIG = _loader.get("file_handling", {})
    DOWNLOAD_DIR = _loader.get("file_handling.download_dir", "downloads")
    TEMP_DIR = _loader.get("file_handling.napcat_temp_dir", "")
    MAX_FILE_SIZE = _loader.get("file_handling.max_file_size", 52428800)
    ALLOWED_EXTENSIONS = _loader.get("file_handling.allowed_extensions", [])
    ENABLE_AUTO_DOWNLOAD = _loader.get("file_handling.auto_download", True)
    
    SPECIAL_REPLIES = _loader.get("special_replies", {})
    ENABLE_AT_MENTION = _loader.get("features.mention_bot", True)
    
    OPENCODE_ENABLED_FEATURES = _loader.get("opencode.enabled_features", {})
    OPENCODE_MESSAGE_CONFIG = _loader.get("opencode.message_config", {})
    OPENCODE_SYSTEM_PROMPT = _loader.get("opencode.system_prompt", "")
    
    AUTO_REPLY_KEYWORDS = _loader.get("auto_reply.keywords", {})
    MESSAGE_CONFIG = _loader.get("message", {})
    TARGET_GROUP_ID = _loader.get("task_progress.target_group_id", 0)
    TASK_SCHEDULER_CHECK_INTERVAL = _loader.get("task_scheduler.check_interval", 10)
    
    HTTP_SERVER_ENABLED = _loader.get("http_server.enabled", True)
    HTTP_SERVER_HOST = _loader.get("http_server.host", "127.0.0.1")
    HTTP_SERVER_PORT = _loader.get("http_server.port", 8080)
    HTTP_SERVER_HTTP_PORT = _loader.get("http_server.http_port", None)
    HTTP_SERVER_ACCESS_TOKEN = _loader.get("http_server.access_token", "")
    HTTP_SERVER_SSL_CERT = _loader.get("http_server.ssl_cert", None)
    HTTP_SERVER_SSL_KEY = _loader.get("http_server.ssl_key", None)
