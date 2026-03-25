#!/usr/bin/env python3
"""
HTTP 中间件模块
包含认证中间件和会话管理功能
"""

from __future__ import annotations

import secrets
import time
import logging
from collections import defaultdict
from typing import Dict, Any, Tuple, Optional, List, Callable, Awaitable

from aiohttp import web

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """认证中间件管理器
    
    负责:
    - Web会话token管理
    - 登录速率限制
    - 请求认证检查
    """
    
    def __init__(self, access_token: str = "", whitelist: Optional[List[int]] = None):
        """初始化认证中间件
        
        Args:
            access_token: API访问令牌
            whitelist: 用户白名单
        """
        self.access_token = access_token
        self._whitelist: List[int] = whitelist or []
        
        # 登录速率限制
        self._login_attempts: Dict[str, List[float]] = defaultdict(list)
        self._login_cooldown: Dict[str, float] = {}
        
        # Web登录session管理
        self._web_sessions: Dict[str, Dict[str, Any]] = {}
    
    def generate_session_token(self) -> str:
        """生成随机会话token"""
        return secrets.token_hex(32)
    
    def create_web_session(self, user_id: int) -> str:
        """创建Web会话
        
        Args:
            user_id: 用户QQ号
            
        Returns:
            会话token
        """
        token = self.generate_session_token()
        now = time.time()
        self._web_sessions[token] = {
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + 86400 * 7  # 7天过期
        }
        return token
    
    def validate_web_session(self, token: str) -> Optional[int]:
        """验证Web会话
        
        Args:
            token: 会话token
            
        Returns:
            用户ID，如果无效返回None
        """
        if not token or token not in self._web_sessions:
            return None
        
        session = self._web_sessions[token]
        now = time.time()
        
        # 检查是否过期
        if now > session["expires_at"]:
            del self._web_sessions[token]
            return None
        
        return session["user_id"]
    
    def destroy_web_session(self, token: str) -> None:
        """销毁Web会话"""
        if token in self._web_sessions:
            del self._web_sessions[token]
    
    def check_auth(self, request: web.Request) -> Tuple[bool, Optional[int]]:
        """检查请求认证

        Args:
            request: HTTP 请求对象

        Returns:
            (认证是否通过, 用户ID)
        """
        # 从 Authorization header 获取 token
        auth_header = request.headers.get("Authorization", "")
        
        # 支持 Bearer token 和直接 token
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = auth_header
        
        # 也支持从查询参数获取 token
        if not token:
            token = request.query.get("token", "")
        
        # 也支持从Cookie获取token
        if not token:
            cookies = request.cookies
            token = cookies.get("session_token", "")
        
        # 检查Web会话token
        if token:
            user_id = self.validate_web_session(token)
            if user_id:
                return True, user_id
        
        # 如果配置了 access_token，也支持API token认证
        if self.access_token and token == self.access_token:
            return True, None
        
        return False, None
    
    def check_rate_limit(self, client_ip: str) -> Dict[str, Any]:
        """检查登录速率限制
        
        Args:
            client_ip: 客户端IP地址
            
        Returns:
            检查结果，包含success和error字段
        """
        now = time.time()
        
        # 清理1分钟前的记录
        if client_ip in self._login_attempts:
            self._login_attempts[client_ip] = [
                t for t in self._login_attempts[client_ip] if now - t < 60
            ]
        
        # 检查2秒冷却期
        if client_ip in self._login_cooldown:
            if now - self._login_cooldown[client_ip] < 2:
                return {
                    "success": False,
                    "error": "请求过于频繁，请2秒后再试"
                }
        
        # 检查1分钟内尝试次数
        if len(self._login_attempts.get(client_ip, [])) >= 10:
            return {
                "success": False,
                "error": "登录尝试次数过多，请1分钟后再试"
            }
        
        return {"success": True}
    
    def record_login_attempt(self, client_ip: str) -> None:
        """记录登录尝试"""
        now = time.time()
        self._login_cooldown[client_ip] = now
        self._login_attempts[client_ip].append(now)
    
    @property
    def whitelist(self) -> List[int]:
        """获取白名单"""
        return self._whitelist
    
    @whitelist.setter
    def whitelist(self, value: List[int]) -> None:
        """设置白名单"""
        self._whitelist = value


def create_auth_middleware(auth: AuthMiddleware) -> Callable:
    """创建认证中间件函数
    
    Args:
        auth: AuthMiddleware实例
        
    Returns:
        中间件函数
    """
    @web.middleware
    async def auth_middleware(request: web.Request, handler: Callable) -> web.Response:
        # 公开路径，不需要认证
        public_paths = [
            "/health",
            "/api/login",
            "/api/password/set",
            "/api/password/change",
            "/",
            "/index.html"
        ]
        
        # 检查是否是公开路径
        if request.path in public_paths:
            return await handler(request)
        
        # 检查是否是静态文件
        if not request.path.startswith("/api/"):
            return await handler(request)
        
        # 检查是否来自本地（127.0.0.1或localhost），本地访问跳过认证
        client_host = request.remote or ""
        if client_host in ("127.0.0.1", "::1", "localhost"):
            # 本地访问，跳过认证
            request["user_id"] = None
            return await handler(request)
        
        # 需要认证的API端点
        is_authenticated, user_id = auth.check_auth(request)
        
        if not is_authenticated:
            return web.json_response({
                "success": False,
                "error": "未登录或会话已过期",
                "need_login": True
            }, status=401)
        
        # 将用户ID存储到请求中
        request["user_id"] = user_id
        
        return await handler(request)
    
    return auth_middleware