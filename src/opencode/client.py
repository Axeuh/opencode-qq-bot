#!/usr/bin/env python3
"""
OpenCode 核心客户端
提供基础的 HTTP 客户端功能
"""

import aiohttp
import asyncio
import base64
import json
import logging
from typing import Dict, List, Optional, Any, Tuple

try:
    from ..utils import config
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from utils import config
    except ImportError:
        import config

from .types import ClientConfig, RequestResult

logger = logging.getLogger(__name__)


class OpenCodeClient:
    """OpenCode 异步 HTTP 客户端"""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        directory: Optional[str] = None,
        timeout: Optional[int] = None,
        default_agent: Optional[str] = None,
        default_model: Optional[str] = None,
        default_provider: Optional[str] = None,
        cookies: Optional[Dict[str, str]] = None,
        enable_ntfy: bool = False,
        ntfy_topic: str = "aaa"
    ):
        """
        初始化 OpenCode 客户端
        
        Args:
            base_url: OpenCode 服务器地址
            username: Basic 认证用户名
            password: Basic 认证密码
            token: Bearer 令牌
            directory: 工作目录
            timeout: 请求超时时间（秒）
            default_agent: 默认智能体
            default_model: 默认模型
            default_provider: 默认提供商
            cookies: HTTP Cookies
            enable_ntfy: 是否启用 ntfy 通知
            ntfy_topic: ntfy 主题
        """
        # 使用配置默认值
        self.base_url = base_url or config.OPENCODE_BASE_URL.rstrip('/')
        self.username = username or config.OPENCODE_AUTH.get("username")
        self.password = password or config.OPENCODE_AUTH.get("password")
        self.token = token or config.OPENCODE_AUTH.get("token")
        self.directory = directory or config.OPENCODE_DIRECTORY
        self.timeout = timeout or config.OPENCODE_TIMEOUT
        self.default_agent = default_agent or config.OPENCODE_DEFAULT_AGENT
        self.default_model = default_model or config.OPENCODE_DEFAULT_MODEL
        self.default_provider = default_provider or config.OPENCODE_DEFAULT_PROVIDER
        self.cookies = cookies or config.OPENCODE_COOKIES.copy()
        self.enable_ntfy = enable_ntfy
        self.ntfy_topic = ntfy_topic
        
        # aiohttp 会话
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 认证头部
        self.headers = self._build_auth_headers()
        self.headers.update({
            "Content-Type": "application/json",
            "x-opencode-directory": self.directory,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        
        # 状态
        self.connected = False
    
    def _build_auth_headers(self) -> Dict[str, str]:
        """构建认证头部"""
        headers = {}
        
        # Basic 认证
        if self.username and self.password:
            auth_str = f"{self.username}:{self.password}"
            auth_b64 = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {auth_b64}"
        
        # Bearer 令牌认证
        elif self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        return headers
    
    @staticmethod
    def parse_model_string(model_str: str) -> Tuple[str, str]:
        """
        解析模型字符串，格式为：供应商/模型名称
        
        支持格式：
        - "供应商/模型名称" -> ("供应商", "模型名称")
        - "模型名称" -> (使用默认提供商, "模型名称")
        
        Args:
            model_str: 模型字符串
        
        Returns:
            (供应商, 模型名称) 元组
        """
        if not model_str:
            return "", ""
        
        # 如果包含斜杠，则拆分
        if "/" in model_str:
            parts = model_str.split("/", 1)
            provider = parts[0]
            model = parts[1]
        else:
            # 不包含斜杠，尝试推断提供商
            model = model_str
            # 根据常见模式推断提供商
            if model.startswith("deepseek-"):
                provider = "deepseek"
            elif model.startswith("claude-"):
                provider = "anthropic"
            elif model.startswith("gpt-"):
                provider = "openai"
            else:
                # 默认为 opencode
                provider = "opencode"
        
        return provider, model
    
    async def ensure_session(self) -> None:
        """确保 aiohttp 会话存在"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                cookies=self.cookies,
                headers=self.headers
            )
            self.connected = True
    
    async def close(self) -> None:
        """关闭客户端"""
        if self.session and not self.session.closed:
            await self.session.close()
        self.connected = False
        logger.info("OpenCode 客户端已关闭")
    
    async def _send_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        extra_headers: Optional[Dict] = None
    ) -> RequestResult:
        """
        发送 HTTP 请求
        
        Args:
            method: HTTP 方法（GET, POST, DELETE 等）
            endpoint: API 端点（相对路径）
            json_data: JSON 请求体
            params: 查询参数
            extra_headers: 额外的请求头
            
        Returns:
            (响应数据, 错误消息) 元组
        """
        await self.ensure_session()
        assert self.session is not None
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # 合并默认 headers 和额外 headers
        request_headers = dict(self.headers)
        if extra_headers:
            request_headers.update(extra_headers)
        
        try:
            # 构建请求参数
            request_kwargs = {
                'method': method,
                'url': url,
                'headers': request_headers
            }
            if json_data is not None:
                request_kwargs['json'] = json_data
            if params is not None:
                request_kwargs['params'] = params
            
            async with self.session.request(**request_kwargs) as response:
                # 检查响应状态
                if response.status >= 400:
                    error_text = await response.text()
                    return None, f"HTTP {response.status}: {error_text}"
                
                # 尝试解析 JSON 响应
                try:
                    data = await response.json()
                    return data, None
                except (json.JSONDecodeError, aiohttp.ContentTypeError):
                    # 如果不是 JSON，返回文本
                    text = await response.text()
                    return {"text": text}, None
                    
        except aiohttp.ClientError as e:
            return None, f"HTTP 客户端错误: {str(e)}"
        except asyncio.TimeoutError:
            return None, f"请求超时 ({self.timeout}秒)"
        except Exception as e:
            return None, f"未知错误: {str(e)}"
    
    async def health_check(self) -> Tuple[bool, Optional[str]]:
        """
        健康检查
        
        Returns:
            (是否健康, 错误消息) 元组
        """
        data, error = await self._send_request(
            method="GET",
            endpoint="/global/health"
        )
        
        if error:
            return False, error
        
        # 检查健康状态
        if isinstance(data, dict):
            status = data.get("status", "").lower()
            return status == "healthy", data.get("message", "未知状态")
        
        return True, None
    
    async def send_ntfy_notification(self, message: str, title: Optional[str] = None) -> None:
        """发送 ntfy 通知（如果启用）"""
        if not self.enable_ntfy:
            return
        
        try:
            import sys
            sys.path.append(r'C:\Users\Axeuh\.config\opencode\skills\ntfy-notification\scripts')
            from send_notification import send_ntfy_notification
            
            response = send_ntfy_notification(
                topic=self.ntfy_topic,
                message=message,
                title=title or "OpenCode 客户端通知",
                priority="default"
            )
            
            if response.status_code == 200:
                logger.debug(f"ntfy 通知发送成功: {message}")
            else:
                logger.warning(f"ntfy 通知发送失败: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"发送 ntfy 通知失败: {e}")