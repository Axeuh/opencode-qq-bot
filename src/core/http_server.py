#!/usr/bin/env python3
"""
HTTP 服务器模块
为机器人提供 HTTP API 接口
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import time
from collections import defaultdict
from typing import Optional, Callable, Dict, Any, Awaitable, List, Tuple

from aiohttp import web, ClientSession, ClientError

logger = logging.getLogger(__name__)

# OpenCode代理配置
try:
    from ..utils import config as bot_config
    OPENCODE_BASE_URL = bot_config.OPENCODE_BASE_URL.rstrip('/')
    OPENCODE_COOKIES = bot_config.OPENCODE_COOKIES
    OPENCODE_DIRECTORY = bot_config.OPENCODE_DIRECTORY
except ImportError:
    OPENCODE_BASE_URL = "http://127.0.0.1:4091"
    OPENCODE_COOKIES = {}
    OPENCODE_DIRECTORY = "C:\\"


class HTTPServer:
    """HTTP 服务器，提供 API 接口"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        http_port: Optional[int] = None,  # HTTP端口（可选，用于同时支持HTTP和HTTPS）
        access_token: str = "",
        ssl_cert: Optional[str] = None,
        ssl_key: Optional[str] = None,
        reload_callback: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None,
        get_user_config_callback: Optional[Callable[[int], Awaitable[Dict[str, Any]]]] = None,
        set_user_config_callback: Optional[Callable[[int, str, Any], Awaitable[Dict[str, Any]]]] = None,
        list_agents_callback: Optional[Callable[[], Awaitable[List[str]]]] = None,
        list_models_callback: Optional[Callable[[], Awaitable[List[str]]]] = None,
        get_user_tasks_callback: Optional[Callable[[int], Awaitable[List[Dict[str, Any]]]]] = None,
        create_task_callback: Optional[Callable[[int, str, str, str, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
        update_task_callback: Optional[Callable[[int, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
        delete_task_callback: Optional[Callable[[int, str], Awaitable[Dict[str, Any]]]] = None,
        # Session 回调
        get_user_sessions_callback: Optional[Callable[[int], Awaitable[Dict[str, Any]]]] = None,
        switch_session_callback: Optional[Callable[[int, str], Awaitable[Dict[str, Any]]]] = None,
        create_session_callback: Optional[Callable[[int, Optional[str]], Awaitable[Dict[str, Any]]]] = None,
        delete_session_callback: Optional[Callable[[int, str], Awaitable[Dict[str, Any]]]] = None,
        # Session Title 回调
        set_session_title_callback: Optional[Callable[[int, str, str], Awaitable[Dict[str, Any]]]] = None,
        # Directory 回调
        get_directory_callback: Optional[Callable[[int], Awaitable[Dict[str, Any]]]] = None,
        set_directory_callback: Optional[Callable[[int, str, Optional[str]], Awaitable[Dict[str, Any]]]] = None
    ):
        """初始化 HTTP 服务器

        Args:
            host: 监听地址
            port: 监听端口
            access_token: API 访问令牌（可选）
            reload_callback: 热重载回调函数（异步），返回执行结果
            get_user_config_callback: 获取用户配置回调函数（异步），参数(user_id)，返回用户配置字典
            set_user_config_callback: 设置用户配置回调函数（异步），参数(user_id, key, value)，返回执行结果
            list_agents_callback: 获取智能体列表回调函数（异步），返回智能体列表
            list_models_callback: 获取模型列表回调函数（异步），返回模型列表
            get_user_tasks_callback: 获取用户任务列表回调函数（异步），参数(user_id)，返回任务列表
            create_task_callback: 创建任务回调函数（异步），参数(user_id, session_id, task_name, prompt, schedule_type, schedule_config)，返回任务信息
            update_task_callback: 更新任务回调函数（异步），参数(user_id, task_id, updates)，返回任务信息
            delete_task_callback: 删除任务回调函数（异步），参数(user_id, task_id)，返回执行结果
            get_user_sessions_callback: 获取用户会话列表回调函数（异步），参数(user_id)，返回会话列表
            switch_session_callback: 切换会话回调函数（异步），参数(user_id, session_id)，返回会话信息
            create_session_callback: 创建会话回调函数（异步），参数(user_id, title)，返回新会话信息
            delete_session_callback: 删除会话回调函数（异步），参数(user_id, session_id)，返回执行结果
        """
        self.host = host
        self.port = port
        self.http_port = http_port
        self.access_token = access_token
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.reload_callback = reload_callback
        self.get_user_config_callback = get_user_config_callback
        self.set_user_config_callback = set_user_config_callback
        self.list_agents_callback = list_agents_callback
        self.list_models_callback = list_models_callback
        self.get_user_tasks_callback = get_user_tasks_callback
        self.create_task_callback = create_task_callback
        self.update_task_callback = update_task_callback
        self.delete_task_callback = delete_task_callback
        # Session 回调
        self.get_user_sessions_callback = get_user_sessions_callback
        self.switch_session_callback = switch_session_callback
        self.create_session_callback = create_session_callback
        self.delete_session_callback = delete_session_callback
        # Session Title 回调
        self.set_session_title_callback = set_session_title_callback
        # Directory 回调
        self.get_directory_callback = get_directory_callback
        self.set_directory_callback = set_directory_callback

        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.http_site: Optional[web.TCPSite] = None  # HTTP站点（可选）
        self._running = False
        
        # 登录速率限制
        self._login_attempts: Dict[str, List[float]] = defaultdict(list)  # IP -> [timestamp1, timestamp2, ...]
        self._login_cooldown: Dict[str, float] = {}  # IP -> last_attempt_time
        
        # Web登录session管理
        self._web_sessions: Dict[str, Dict[str, Any]] = {}  # token -> {user_id, created_at, expires_at}
        
        # 加载白名单配置
        self._whitelist: List[int] = []
        try:
            from ..utils import config as bot_config
            if hasattr(bot_config, 'QQ_USER_WHITELIST'):
                self._whitelist = bot_config.QQ_USER_WHITELIST
        except (ImportError, AttributeError):
            pass

    def _generate_session_token(self) -> str:
        """生成随机会话token"""
        import secrets
        return secrets.token_hex(32)
    
    def _create_web_session(self, user_id: int) -> str:
        """创建Web会话
        
        Args:
            user_id: 用户QQ号
            
        Returns:
            会话token
        """
        import time
        token = self._generate_session_token()
        now = time.time()
        self._web_sessions[token] = {
            "user_id": user_id,
            "created_at": now,
            "expires_at": now + 86400 * 7  # 7天过期
        }
        return token
    
    def _validate_web_session(self, token: str) -> Optional[int]:
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
    
    def _destroy_web_session(self, token: str) -> None:
        """销毁Web会话"""
        if token in self._web_sessions:
            del self._web_sessions[token]

    def _check_auth(self, request: web.Request) -> Tuple[bool, Optional[int]]:
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
            user_id = self._validate_web_session(token)
            if user_id:
                return True, user_id
        
        # 如果配置了 access_token，也支持API token认证
        if self.access_token and token == self.access_token:
            return True, None
        
        return False, None

    def _check_rate_limit(self, client_ip: str) -> Dict[str, Any]:
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

    def _record_login_attempt(self, client_ip: str):
        """记录登录尝试"""
        now = time.time()
        self._login_cooldown[client_ip] = now
        self._login_attempts[client_ip].append(now)

    async def handle_login(self, request: web.Request) -> web.Response:
        """登录验证端点
        
        检查:
        1. QQ号是否在白名单中
        2. 用户是否设置了密码
        3. 密码验证
        4. 速率限制（同一设备2秒只能尝试一次，1分钟最多10次）
        """
        try:
            # 获取客户端IP
            client_ip = request.remote or "unknown"
            
            # 检查速率限制
            rate_check = self._check_rate_limit(client_ip)
            if not rate_check["success"]:
                return web.json_response(rate_check, status=429)
            
            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                self._record_login_attempt(client_ip)
                return web.json_response({
                    "success": False,
                    "error": "无效的请求格式"
                }, status=400)
            
            qq_id = body.get("qq_id")
            password = body.get("password", "")
            
            if not qq_id:
                self._record_login_attempt(client_ip)
                return web.json_response({
                    "success": False,
                    "error": "请输入QQ号"
                }, status=400)
            
            try:
                qq_id = int(qq_id)
            except ValueError:
                self._record_login_attempt(client_ip)
                return web.json_response({
                    "success": False,
                    "error": "QQ号必须是数字"
                }, status=400)
            
            # 检查白名单
            if self._whitelist and qq_id not in self._whitelist:
                self._record_login_attempt(client_ip)
                logger.warning(f"非白名单用户尝试登录: QQ={qq_id}, IP={client_ip}")
                return web.json_response({
                    "success": False,
                    "error": "您不在白名单中，无法登录"
                }, status=403)
            
            # 获取会话管理器
            try:
                from ..session.session_manager import get_session_manager
                session_manager = get_session_manager()
            except ImportError:
                session_manager = None
            
            # 检查用户是否设置了密码
            has_password = session_manager.user_has_password(qq_id) if session_manager else False
            
            if not has_password:
                # 用户未设置密码，返回需要设置密码的响应
                self._record_login_attempt(client_ip)
                logger.info(f"用户未设置密码: QQ={qq_id}, IP={client_ip}")
                return web.json_response({
                    "success": False,
                    "need_set_password": True,
                    "error": "请先设置密码"
                }, status=200)
            
            # 用户已设置密码，验证密码
            if not password:
                self._record_login_attempt(client_ip)
                return web.json_response({
                    "success": False,
                    "need_password": True,
                    "error": "请输入密码"
                }, status=200)
            
            # 验证密码
            if session_manager and session_manager.verify_user_password(qq_id, password):
                # 登录成功
                self._record_login_attempt(client_ip)
                logger.info(f"用户登录成功: QQ={qq_id}, IP={client_ip}")
                
                # 创建Web会话token
                session_token = self._create_web_session(qq_id)
                
                response = web.json_response({
                    "success": True,
                    "message": "登录成功",
                    "qq_id": qq_id,
                    "token": session_token
                })
                
                # 设置Cookie
                response.set_cookie(
                    "session_token", 
                    session_token, 
                    max_age=86400 * 7,  # 7天
                    httponly=True,
                    secure=True,  # 仅HTTPS
                    samesite="Lax"
                )
                
                return response
            else:
                # 密码错误
                self._record_login_attempt(client_ip)
                logger.warning(f"密码错误: QQ={qq_id}, IP={client_ip}")
                return web.json_response({
                    "success": False,
                    "need_password": True,
                    "error": "密码错误"
                }, status=200)
            
        except Exception as e:
            logger.error(f"处理登录请求失败: {e}")
            return web.json_response({
                "success": False,
                "error": "服务器错误"
            }, status=500)

    async def handle_health(self, request: web.Request) -> web.Response:
        """健康检查端点"""
        return web.json_response({
            "success": True,
            "status": "healthy",
            "service": "QQ Bot HTTP Server"
        })

    async def handle_set_password(self, request: web.Request) -> web.Response:
        """设置密码端点（首次设置）
        
        请求格式: {"qq_id": 123456, "password": "xxx"}
        """
        try:
            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "无效的请求格式"
                }, status=400)
            
            qq_id = body.get("qq_id")
            password = body.get("password", "")
            
            if not qq_id:
                return web.json_response({
                    "success": False,
                    "error": "请输入QQ号"
                }, status=400)
            
            try:
                qq_id = int(qq_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "QQ号必须是数字"
                }, status=400)
            
            # 检查密码长度
            if len(password) < 6:
                return web.json_response({
                    "success": False,
                    "error": "密码长度至少6位"
                }, status=400)
            
            # 检查白名单
            if self._whitelist and qq_id not in self._whitelist:
                logger.warning(f"非白名单用户尝试设置密码: QQ={qq_id}")
                return web.json_response({
                    "success": False,
                    "error": "您不在白名单中"
                }, status=403)
            
            # 获取会话管理器
            try:
                from ..session.session_manager import get_session_manager
                session_manager = get_session_manager()
            except ImportError:
                return web.json_response({
                    "success": False,
                    "error": "服务器配置错误"
                }, status=500)
            
            # 检查用户是否已设置密码
            if session_manager.user_has_password(qq_id):
                return web.json_response({
                    "success": False,
                    "error": "您已设置密码，请使用修改密码功能"
                }, status=400)
            
            # 设置密码
            if session_manager.set_user_password(qq_id, password):
                logger.info(f"用户设置密码成功: QQ={qq_id}")
                
                # 创建Web会话token
                session_token = self._create_web_session(qq_id)
                
                response = web.json_response({
                    "success": True,
                    "message": "密码设置成功",
                    "token": session_token
                })
                
                # 设置Cookie
                response.set_cookie(
                    "session_token", 
                    session_token, 
                    max_age=86400 * 7,  # 7天
                    httponly=True,
                    secure=True,  # 仅HTTPS
                    samesite="Lax"
                )
                
                return response
            else:
                return web.json_response({
                    "success": False,
                    "error": "密码设置失败"
                }, status=500)
            
        except Exception as e:
            logger.error(f"设置密码失败: {e}")
            return web.json_response({
                "success": False,
                "error": "服务器错误"
            }, status=500)

    async def handle_change_password(self, request: web.Request) -> web.Response:
        """修改密码端点
        
        请求格式: {"qq_id": 123456, "old_password": "xxx", "new_password": "xxx"}
        """
        try:
            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "无效的请求格式"
                }, status=400)
            
            qq_id = body.get("qq_id")
            old_password = body.get("old_password", "")
            new_password = body.get("new_password", "")
            
            if not qq_id:
                return web.json_response({
                    "success": False,
                    "error": "请输入QQ号"
                }, status=400)
            
            try:
                qq_id = int(qq_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "QQ号必须是数字"
                }, status=400)
            
            # 检查新密码长度
            if len(new_password) < 6:
                return web.json_response({
                    "success": False,
                    "error": "新密码长度至少6位"
                }, status=400)
            
            # 获取会话管理器
            try:
                from ..session.session_manager import get_session_manager
                session_manager = get_session_manager()
            except ImportError:
                return web.json_response({
                    "success": False,
                    "error": "服务器配置错误"
                }, status=500)
            
            # 检查用户是否设置了密码
            if not session_manager.user_has_password(qq_id):
                return web.json_response({
                    "success": False,
                    "error": "您尚未设置密码，请先设置密码"
                }, status=400)
            
            # 验证旧密码
            if not session_manager.verify_user_password(qq_id, old_password):
                return web.json_response({
                    "success": False,
                    "error": "原密码错误"
                }, status=400)
            
            # 设置新密码
            if session_manager.set_user_password(qq_id, new_password):
                logger.info(f"用户修改密码成功: QQ={qq_id}")
                return web.json_response({
                    "success": True,
                    "message": "密码修改成功"
                })
            else:
                return web.json_response({
                    "success": False,
                    "error": "密码修改失败"
                }, status=500)
            
        except Exception as e:
            logger.error(f"修改密码失败: {e}")
            return web.json_response({
                "success": False,
                "error": "服务器错误"
            }, status=500)

    async def handle_reload(self, request: web.Request) -> web.Response:
        """热重载机器人端点（重载代码和配置）"""
        try:
            if not self.reload_callback:
                return web.json_response({
                    "success": False,
                    "error": "Reload callback not configured"
                }, status=500)

            logger.info("收到热重载请求")

            # 调用热重载回调
            result = await self.reload_callback()

            return web.json_response({
                "success": True,
                "message": "Hot reload completed",
                "details": result
            })

        except Exception as e:
            logger.error(f"处理热重载请求失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_get_agents(self, request: web.Request) -> web.Response:
        """获取用户当前智能体 (POST)"""
        try:
            if not self.get_user_config_callback:
                return web.json_response({
                    "success": False,
                    "error": "Get user config callback not configured"
                }, status=500)

            # 从请求体获取用户QQ号
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            user_id = body.get("user_id")
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 获取用户配置
            result = await self.get_user_config_callback(user_id)

            return web.json_response({
                "success": True,
                "user_id": user_id,
                "agent": result.get("agent", "")
            })

        except Exception as e:
            logger.error(f"获取用户智能体失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_set_agents(self, request: web.Request) -> web.Response:
        """设置用户智能体"""
        try:
            if not self.set_user_config_callback:
                return web.json_response({
                    "success": False,
                    "error": "Set user config callback not configured"
                }, status=500)

            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            # 验证必需参数
            user_id = body.get("user_id")
            agent = body.get("agent")

            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            if not agent:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: agent"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 设置用户配置
            result = await self.set_user_config_callback(user_id, "agent", agent)

            if not result.get("success", True):
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to set agent")
                }, status=400)

            return web.json_response({
                "success": True,
                "user_id": user_id,
                "agent": result.get("agent", agent),
                "message": "Agent updated successfully"
            })

        except Exception as e:
            logger.error(f"设置用户智能体失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_get_model(self, request: web.Request) -> web.Response:
        """获取用户当前模型 (POST)"""
        try:
            if not self.get_user_config_callback:
                return web.json_response({
                    "success": False,
                    "error": "Get user config callback not configured"
                }, status=500)

            # 从请求体获取用户QQ号
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            user_id = body.get("user_id")
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 获取用户配置
            result = await self.get_user_config_callback(user_id)

            return web.json_response({
                "success": True,
                "user_id": user_id,
                "model": result.get("model", ""),
                "agent": result.get("agent", ""),
                "provider": result.get("provider", "")
            })

        except Exception as e:
            logger.error(f"获取用户模型失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_set_model(self, request: web.Request) -> web.Response:
        """设置用户模型"""
        try:
            if not self.set_user_config_callback:
                return web.json_response({
                    "success": False,
                    "error": "Set user config callback not configured"
                }, status=500)

            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            # 验证必需参数
            user_id = body.get("user_id")
            model = body.get("model")

            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            if not model:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: model"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 设置用户配置
            result = await self.set_user_config_callback(user_id, "model", model)

            if not result.get("success", True):
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to set model")
                }, status=400)

            return web.json_response({
                "success": True,
                "user_id": user_id,
                "model": result.get("model", model),
                "provider": result.get("provider", ""),
                "message": "Model updated successfully"
            })

        except Exception as e:
            logger.error(f"设置用户模型失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_list_agents(self, request: web.Request) -> web.Response:
        """获取可用智能体列表"""
        try:
            # 从回调或配置获取智能体列表
            if self.list_agents_callback:
                agents = await self.list_agents_callback()
            else:
                # 返回默认提示
                agents = []
            
            return web.json_response({
                "success": True,
                "agents": agents,
                "count": len(agents)
            })

        except Exception as e:
            logger.error(f"获取智能体列表失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_list_models(self, request: web.Request) -> web.Response:
        """获取可用模型列表"""
        try:
            # 从回调或配置获取模型列表
            if self.list_models_callback:
                models = await self.list_models_callback()
            else:
                # 返回默认提示
                models = []
            
            return web.json_response({
                "success": True,
                "models": models,
                "count": len(models)
            })

        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_get_tasks(self, request: web.Request) -> web.Response:
        """获取用户定时任务列表 (POST)"""
        try:
            if not self.get_user_tasks_callback:
                return web.json_response({
                    "success": False,
                    "error": "Get user tasks callback not configured"
                }, status=500)

            # 从请求体获取用户QQ号
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            user_id = body.get("user_id")
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 获取用户任务列表
            tasks = await self.get_user_tasks_callback(user_id)

            return web.json_response({
                "success": True,
                "user_id": user_id,
                "tasks": tasks,
                "count": len(tasks)
            })

        except Exception as e:
            logger.error(f"获取用户任务列表失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_create_task(self, request: web.Request) -> web.Response:
        """创建定时任务 (POST)"""
        try:
            if not self.create_task_callback:
                return web.json_response({
                    "success": False,
                    "error": "Create task callback not configured"
                }, status=500)

            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            # 验证必需参数
            user_id = body.get("user_id")
            session_id = body.get("session_id")
            task_name = body.get("task_name")
            prompt = body.get("prompt")
            schedule_type = body.get("schedule_type")
            schedule_config = body.get("schedule_config", {})

            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            if not session_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: session_id"
                }, status=400)

            if not task_name:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: task_name"
                }, status=400)

            if not prompt:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: prompt"
                }, status=400)

            if not schedule_type:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: schedule_type"
                }, status=400)

            # 验证 schedule_type
            valid_types = ["delay", "scheduled"]
            if schedule_type not in valid_types:
                return web.json_response({
                    "success": False,
                    "error": f"Invalid schedule_type: {schedule_type}. Valid types: {valid_types}"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 创建任务
            result = await self.create_task_callback(
                user_id, session_id, task_name, prompt, schedule_type, schedule_config
            )

            if not result.get("success", True):
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to create task")
                }, status=400)

            return web.json_response({
                "success": True,
                "message": "Task created successfully",
                "task": result.get("task", {})
            })

        except Exception as e:
            logger.error(f"创建定时任务失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_delete_task(self, request: web.Request) -> web.Response:
        """删除定时任务 (POST)"""
        try:
            if not self.delete_task_callback:
                return web.json_response({
                    "success": False,
                    "error": "Delete task callback not configured"
                }, status=500)

            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            # 验证必需参数
            user_id = body.get("user_id")
            task_id = body.get("task_id")

            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            if not task_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: task_id"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 删除任务
            result = await self.delete_task_callback(user_id, task_id)

            if not result.get("success", True):
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to delete task")
                }, status=400)

            return web.json_response({
                "success": True,
                "message": "Task deleted successfully"
            })

        except Exception as e:
            logger.error(f"删除定时任务失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_update_task(self, request: web.Request) -> web.Response:
        """更新定时任务 (POST)"""
        try:
            if not self.update_task_callback:
                return web.json_response({
                    "success": False,
                    "error": "Update task callback not configured"
                }, status=500)

            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            # 验证必需参数
            user_id = body.get("user_id")
            task_id = body.get("task_id")
            updates = body.get("updates", {})

            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            if not task_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: task_id"
                }, status=400)

            if not updates:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: updates"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 更新任务
            result = await self.update_task_callback(user_id, task_id, updates)

            if not result.get("success", True):
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to update task")
                }, status=400)

            return web.json_response({
                "success": True,
                "message": "Task updated successfully",
                "task": result.get("task", {})
            })

        except Exception as e:
            logger.error(f"更新定时任务失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_session_list(self, request: web.Request) -> web.Response:
        """获取用户会话列表 (POST)"""
        try:
            # 从请求体获取用户QQ号
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            user_id = body.get("user_id")
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 统一使用用户会话列表回调
            if not self.get_user_sessions_callback:
                return web.json_response({
                    "success": False,
                    "error": "Get user sessions callback not configured"
                }, status=500)

            result = await self.get_user_sessions_callback(user_id)
            
            # 转换格式
            session_list = []
            if result.get("current"):
                session_list.append(result["current"])
            for s in result.get("history", []):
                session_list.append(s)

            return web.json_response({
                "success": True,
                "user_id": user_id,
                "sessions": session_list,
                "count": len(session_list)
            })

        except Exception as e:
            logger.error(f"获取用户会话列表失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_session_switch(self, request: web.Request) -> web.Response:
        """切换会话 (POST)"""
        try:
            if not self.switch_session_callback:
                return web.json_response({
                    "success": False,
                    "error": "Switch session callback not configured"
                }, status=500)

            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            # 验证必需参数
            user_id = body.get("user_id")
            session_id = body.get("session_id")

            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            if not session_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: session_id"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 切换会话
            result = await self.switch_session_callback(user_id, session_id)

            if not result.get("success", True):
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to switch session")
                }, status=400)

            return web.json_response({
                "success": True,
                "message": "Session switched successfully",
                "session": result.get("session", {})
            })

        except Exception as e:
            logger.error(f"切换会话失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_session_new(self, request: web.Request) -> web.Response:
        """创建新会话 (POST)"""
        try:
            if not self.create_session_callback:
                return web.json_response({
                    "success": False,
                    "error": "Create session callback not configured"
                }, status=500)

            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            # 验证必需参数
            user_id = body.get("user_id")
            title = body.get("title")  # 可选

            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 创建会话
            result = await self.create_session_callback(user_id, title)

            if not result.get("success", True):
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to create session")
                }, status=400)

            return web.json_response({
                "success": True,
                "message": "Session created successfully",
                "session": result.get("session", {})
            })

        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_session_delete(self, request: web.Request) -> web.Response:
        """删除会话 (POST)"""
        try:
            if not self.delete_session_callback:
                return web.json_response({
                    "success": False,
                    "error": "Delete session callback not configured"
                }, status=500)

            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            # 验证必需参数
            user_id = body.get("user_id")
            session_id = body.get("session_id")

            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            if not session_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: session_id"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 删除会话
            result = await self.delete_session_callback(user_id, session_id)

            if not result.get("success", True):
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to delete session")
                }, status=400)

            return web.json_response({
                "success": True,
                "message": "Session deleted successfully"
            })

        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_set_session_title(self, request: web.Request) -> web.Response:
        """设置会话标题 (POST)"""
        try:
            if not self.set_session_title_callback:
                return web.json_response({
                    "success": False,
                    "error": "Set session title callback not configured"
                }, status=500)

            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            # 验证必需参数
            user_id = body.get("user_id")
            session_id = body.get("session_id")
            title = body.get("title")

            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            if not session_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: session_id"
                }, status=400)

            if not title:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: title"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 设置会话标题
            result = await self.set_session_title_callback(user_id, session_id, title)

            if not result.get("success", True):
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to set session title")
                }, status=400)

            return web.json_response({
                "success": True,
                "message": "Session title updated successfully",
                "session_id": session_id,
                "title": title
            })

        except Exception as e:
            logger.error(f"设置会话标题失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_get_directory(self, request: web.Request) -> web.Response:
        """获取用户当前工作目录 (POST)"""
        try:
            if not self.get_directory_callback:
                return web.json_response({
                    "success": False,
                    "error": "Get directory callback not configured"
                }, status=500)

            # 从请求体获取用户QQ号
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            user_id = body.get("user_id")
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 获取用户目录
            result = await self.get_directory_callback(user_id)

            return web.json_response({
                "success": True,
                "user_id": user_id,
                "directory": result.get("directory", "/")
            })

        except Exception as e:
            logger.error(f"获取用户目录失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_set_directory(self, request: web.Request) -> web.Response:
        """设置用户工作目录 (POST)"""
        try:
            if not self.set_directory_callback:
                return web.json_response({
                    "success": False,
                    "error": "Set directory callback not configured"
                }, status=500)

            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            # 验证必需参数
            user_id = body.get("user_id")
            directory = body.get("directory")
            session_id = body.get("session_id")  # 可选参数

            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: user_id"
                }, status=400)

            if not directory:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: directory"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 设置用户目录（传递session_id）
            result = await self.set_directory_callback(user_id, directory, session_id)

            if not result.get("success", True):
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to set directory")
                }, status=400)

            return web.json_response({
                "success": True,
                "user_id": user_id,
                "directory": result.get("directory", directory),
                "message": "Directory updated successfully"
            })

        except Exception as e:
            logger.error(f"设置用户目录失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    # ========================================
    # OpenCode 代理 API
    # ========================================

    def _build_opencode_headers(self) -> Dict[str, str]:
        """构建OpenCode请求头"""
        headers = {
            "Content-Type": "application/json",
            "x-opencode-directory": OPENCODE_DIRECTORY,
        }
        if OPENCODE_COOKIES:
            cookie_str = "; ".join([f"{k}={v}" for k, v in OPENCODE_COOKIES.items()])
            headers["Cookie"] = cookie_str
        return headers

    async def handle_opencode_events(self, request: web.Request) -> web.StreamResponse:
        """代理OpenCode SSE事件流"""
        response = web.StreamResponse()
        response.content_type = 'text/event-stream'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Connection'] = 'keep-alive'
        response.headers['Access-Control-Allow-Origin'] = '*'
        await response.prepare(request)
        
        try:
            async with ClientSession() as session:
                headers = self._build_opencode_headers()
                async with session.get(
                    f'{OPENCODE_BASE_URL}/global/event',
                    headers=headers,
                    timeout=None
                ) as upstream:
                    async for line in upstream.content:
                        try:
                            await response.write(line)
                        except Exception as e:
                            logger.debug(f"SSE写入失败: {e}")
                            break
        except ClientError as e:
            logger.error(f"OpenCode SSE连接失败: {e}")
        except Exception as e:
            logger.error(f"SSE代理异常: {e}")
        return response

    async def handle_opencode_session_list(self, request: web.Request) -> web.Response:
        """代理OpenCode会话列表"""
        try:
            async with ClientSession() as session:
                headers = self._build_opencode_headers()
                params = dict(request.query)
                async with session.get(
                    f'{OPENCODE_BASE_URL}/session',
                    headers=headers,
                    params=params
                ) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"代理会话列表失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def handle_opencode_session_create(self, request: web.Request) -> web.Response:
        """代理OpenCode创建会话"""
        try:
            body = await request.read()
            async with ClientSession() as session:
                headers = self._build_opencode_headers()
                async with session.post(
                    f'{OPENCODE_BASE_URL}/session',
                    headers=headers,
                    data=body
                ) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"代理创建会话失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def handle_opencode_session_delete(self, request: web.Request) -> web.Response:
        """代理OpenCode删除会话"""
        try:
            session_id = request.match_info.get('session_id')
            if not session_id:
                return web.json_response({"success": False, "error": "Missing session_id"}, status=400)
            async with ClientSession() as session:
                headers = self._build_opencode_headers()
                async with session.delete(
                    f'{OPENCODE_BASE_URL}/session/{session_id}',
                    headers=headers
                ) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"代理删除会话失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def handle_opencode_messages_get(self, request: web.Request) -> web.Response:
        """代理OpenCode获取消息列表"""
        try:
            session_id = request.match_info.get('session_id')
            if not session_id:
                return web.json_response({"success": False, "error": "Missing session_id"}, status=400)
            params = dict(request.query)
            async with ClientSession() as session:
                headers = self._build_opencode_headers()
                async with session.get(
                    f'{OPENCODE_BASE_URL}/session/{session_id}/message',
                    headers=headers,
                    params=params
                ) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"代理获取消息失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def handle_opencode_message_send(self, request: web.Request) -> web.Response:
        """代理OpenCode发送消息"""
        try:
            session_id = request.match_info.get('session_id')
            if not session_id:
                return web.json_response({"success": False, "error": "Missing session_id"}, status=400)
            
            body = await request.read()
            
            # 从认证中间件获取用户ID
            user_id = request.get("user_id")
            
            # 构建请求头
            headers = self._build_opencode_headers()
            
            # 获取用户的会话目录
            user_directory = OPENCODE_DIRECTORY
            if user_id and self.get_directory_callback:
                try:
                    dir_result = await self.get_directory_callback(user_id)
                    if dir_result and dir_result.get("directory"):
                        user_directory = dir_result.get("directory")
                except Exception as e:
                    logger.warning(f"获取用户目录失败: {e}")
            
            # 确保目录不为空
            if not user_directory:
                user_directory = OPENCODE_DIRECTORY
            
            # 设置正确的目录和 Referer
            import base64
            directory_b64 = base64.b64encode(user_directory.encode()).decode()
            headers["x-opencode-directory"] = user_directory
            headers["Referer"] = f"{OPENCODE_BASE_URL}/{directory_b64}/session/{session_id}"
            
            # 打印请求日志
            logger.info(f"[OpenCode代理] POST {OPENCODE_BASE_URL}/session/{session_id}/message")
            logger.info(f"[OpenCode代理] Headers: {headers}")
            logger.info(f"[OpenCode代理] Body: {body[:200] if len(body) > 200 else body}")
            
            async with ClientSession() as session:
                async with session.post(
                    f'{OPENCODE_BASE_URL}/session/{session_id}/message',
                    headers=headers,
                    data=body
                ) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"代理发送消息失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def handle_opencode_models(self, request: web.Request) -> web.Response:
        """代理OpenCode模型列表"""
        try:
            async with ClientSession() as session:
                headers = self._build_opencode_headers()
                async with session.get(
                    f'{OPENCODE_BASE_URL}/config/providers',
                    headers=headers
                ) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"代理模型列表失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def handle_opencode_agents(self, request: web.Request) -> web.Response:
        """代理OpenCode智能体列表"""
        try:
            async with ClientSession() as session:
                headers = self._build_opencode_headers()
                async with session.get(
                    f'{OPENCODE_BASE_URL}/agent',
                    headers=headers
                ) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"代理智能体列表失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def handle_get_qq_userinfo(self, request: web.Request) -> web.Response:
        """获取QQ用户信息（通过napcat API）"""
        try:
            user_id = request.match_info.get("user_id") or request.query.get("user_id")
            if not user_id:
                return web.json_response({"success": False, "error": "Missing user_id"}, status=400)
            
            # napcat HTTP API配置
            napcat_url = "http://localhost:3001"
            napcat_token = "fZvJ-zo_TzyAHOoI"
            
            async with ClientSession() as session:
                headers = {"Authorization": f"Bearer {napcat_token}"}
                async with session.post(
                    f"{napcat_url}/get_stranger_info",
                    json={"user_id": user_id},
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "ok" and data.get("data"):
                            user_info = data["data"]
                            return web.json_response({
                                "success": True,
                                "user_id": user_info.get("user_id"),
                                "nickname": user_info.get("nickname", ""),
                                "remark": user_info.get("remark", "")
                            })
                        else:
                            return web.json_response({
                                "success": False, 
                                "error": data.get("message", "Failed to get user info")
                            }, status=500)
                    else:
                        return web.json_response({
                            "success": False, 
                            "error": f"napcat API error: {resp.status}"
                        }, status=500)
        except Exception as e:
            logger.error(f"获取QQ用户信息失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def handle_upload(self, request: web.Request) -> web.Response:
        """文件上传端点 (POST /api/upload)
        
        接收 multipart/form-data 请求，保存文件到 downloads/{user_id}/ 目录
        
        字段:
            - file: 上传的文件
            - user_id: 用户QQ号
            
        支持的文件类型:
            - 图片: jpg, png, gif, webp
            - 文档: pdf, doc, docx, xlsx, txt
            - 压缩包: zip, rar
            
        最大文件大小: 50MB
        """
        import os
        from datetime import datetime
        
        # 允许的文件扩展名
        ALLOWED_EXTENSIONS = {
            # 图片
            'jpg', 'jpeg', 'png', 'gif', 'webp',
            # 文档
            'pdf', 'doc', 'docx', 'xlsx', 'txt',
            # 压缩包
            'zip', 'rar'
        }
        
        # 最大文件大小 50MB
        MAX_FILE_SIZE = 50 * 1024 * 1024
        
        try:
            # 获取 multipart reader
            reader = await request.multipart()
            
            file_data = None
            file_name = None
            user_id = None
            
            # 解析 multipart 字段
            async for field in reader:
                if field.name == 'user_id':
                    # 读取 user_id 字段
                    user_id_bytes = await field.read()
                    user_id = user_id_bytes.decode('utf-8')
                    
                elif field.name == 'file':
                    # 读取文件字段
                    file_name = field.filename
                    file_data = await field.read()
            
            # 验证必需参数
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required field: user_id"
                }, status=400)
            
            if not file_data or not file_name:
                return web.json_response({
                    "success": False,
                    "error": "Missing required field: file"
                }, status=400)
            
            # 验证 user_id 格式
            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)
            
            # 检查文件大小
            file_size = len(file_data)
            if file_size > MAX_FILE_SIZE:
                return web.json_response({
                    "success": False,
                    "error": f"File size exceeds limit: {file_size} bytes > {MAX_FILE_SIZE} bytes (50MB)"
                }, status=400)
            
            # 检查文件类型
            file_ext = os.path.splitext(file_name)[1].lower().lstrip('.')
            if file_ext not in ALLOWED_EXTENSIONS:
                return web.json_response({
                    "success": False,
                    "error": f"File type not allowed: {file_ext}. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                }, status=400)
            
            # 创建用户目录
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            download_dir = os.path.join(base_dir, 'downloads', str(user_id))
            os.makedirs(download_dir, exist_ok=True)
            
            # 处理文件名冲突
            safe_filename = "".join(c for c in file_name if c.isalnum() or c in "._- ")
            save_path = os.path.join(download_dir, safe_filename)
            
            # 如果文件已存在，添加时间戳
            if os.path.exists(save_path):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_name, ext = os.path.splitext(safe_filename)
                safe_filename = f"{base_name}_{timestamp}{ext}"
                save_path = os.path.join(download_dir, safe_filename)
            
            # 保存文件
            with open(save_path, 'wb') as f:
                f.write(file_data)
            
            # 构建返回路径
            relative_path = f"downloads/{user_id}/{safe_filename}"
            absolute_path = os.path.abspath(save_path)
            
            logger.info(f"文件上传成功: user_id={user_id}, file={safe_filename}, size={file_size}")
            
            return web.json_response({
                "success": True,
                "file_path": relative_path,
                "absolute_path": absolute_path,
                "file_name": safe_filename,
                "file_size": file_size
            })
            
        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def handle_not_found(self, request: web.Request) -> web.Response:
        """404 处理"""
        return web.json_response({
            "success": False,
            "error": "Not Found"
        }, status=404)

    async def handle_index(self, request: web.Request) -> web.FileResponse:
        """返回index.html"""
        import os
        # 尝试多个可能的位置
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', 'web', 'index.html'),
            os.path.join(os.path.dirname(__file__), '..', 'web', 'index.html'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'index.html'),
        ]
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                return web.FileResponse(abs_path)
        return web.json_response({"success": False, "error": "index.html not found"}, status=404)

    async def auth_middleware(self, app: web.Application, handler: Callable) -> Callable:
        """认证中间件
        
        自动验证所有需要认证的API端点
        """
        async def middleware_handler(request: web.Request) -> web.StreamResponse:
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
            
            # 需要认证的API端点
            is_authenticated, user_id = self._check_auth(request)
            
            if not is_authenticated:
                return web.json_response({
                    "success": False,
                    "error": "未登录或会话已过期",
                    "need_login": True
                }, status=401)
            
            # 将用户ID存储到请求中
            request["user_id"] = user_id
            
            return await handler(request)
        
        return middleware_handler

    def setup_routes(self) -> None:
        """设置路由"""
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_post("/api/reload", self.handle_reload)
        # 登录验证
        self.app.router.add_post("/api/login", self.handle_login)
        # 密码管理
        self.app.router.add_post("/api/password/set", self.handle_set_password)
        self.app.router.add_post("/api/password/change", self.handle_change_password)
        # 静态文件
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/index.html", self.handle_index)
        # Agents 端点
        self.app.router.add_post("/api/agents/get", self.handle_get_agents)
        self.app.router.add_post("/api/agents/set", self.handle_set_agents)
        self.app.router.add_get("/api/agents", self.handle_list_agents)
        # Model 端点
        self.app.router.add_post("/api/model/get", self.handle_get_model)
        self.app.router.add_post("/api/model/set", self.handle_set_model)
        self.app.router.add_get("/api/models", self.handle_list_models)
        # Task 端点
        self.app.router.add_post("/api/task/get", self.handle_get_tasks)
        self.app.router.add_post("/api/task/set", self.handle_create_task)
        self.app.router.add_post("/api/task/update", self.handle_update_task)
        self.app.router.add_post("/api/task/delete", self.handle_delete_task)
        # Session 端点
        self.app.router.add_post("/api/session/list", self.handle_session_list)
        self.app.router.add_post("/api/session/switch", self.handle_session_switch)
        self.app.router.add_post("/api/session/new", self.handle_session_new)
        self.app.router.add_post("/api/session/delete", self.handle_session_delete)
        self.app.router.add_post("/api/session/title", self.handle_set_session_title)
        # Directory 端点
        self.app.router.add_post("/api/directory/get", self.handle_get_directory)
        self.app.router.add_post("/api/directory/set", self.handle_set_directory)
        # 文件上传端点
        self.app.router.add_post("/api/upload", self.handle_upload)
        # OpenCode 代理端点
        self.app.router.add_get("/api/opencode/events", self.handle_opencode_events)
        self.app.router.add_get("/api/opencode/sessions", self.handle_opencode_session_list)
        self.app.router.add_post("/api/opencode/sessions", self.handle_opencode_session_create)
        self.app.router.add_delete("/api/opencode/sessions/{session_id}", self.handle_opencode_session_delete)
        self.app.router.add_get("/api/opencode/sessions/{session_id}/messages", self.handle_opencode_messages_get)
        self.app.router.add_post("/api/opencode/sessions/{session_id}/messages", self.handle_opencode_message_send)
        self.app.router.add_get("/api/opencode/models", self.handle_opencode_models)
        self.app.router.add_get("/api/opencode/agents", self.handle_opencode_agents)
        # QQ用户信息端点
        self.app.router.add_get("/api/qq/userinfo/{user_id}", self.handle_get_qq_userinfo)
        self.app.router.add_get("/api/qq/userinfo", self.handle_get_qq_userinfo)
        self.app.router.add_route("*", "/{tail:.*}", self.handle_not_found)

    async def start(self) -> None:
        """启动 HTTP 服务器"""
        if self._running:
            logger.warning("HTTP 服务器已在运行")
            return

        try:
            # 创建中间件
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
                
                # 需要认证的API端点
                is_authenticated, user_id = self._check_auth(request)
                
                if not is_authenticated:
                    return web.json_response({
                        "success": False,
                        "error": "未登录或会话已过期",
                        "need_login": True
                    }, status=401)
                
                # 将用户ID存储到请求中
                request["user_id"] = user_id
                
                return await handler(request)

            self.app = web.Application(middlewares=[auth_middleware])
            self.setup_routes()

            # 禁用访问日志（只保留错误日志）
            # access_log = logging.getLogger('aiohttp.access')
            # access_log.setLevel(logging.DEBUG)

            self.runner = web.AppRunner(self.app, access_log=None)
            await self.runner.setup()

            # 配置SSL
            ssl_context = None
            if self.ssl_cert and self.ssl_key:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(self.ssl_cert, self.ssl_key)
                logger.info(f"SSL证书已加载: {self.ssl_cert}")

            # 创建主站点（HTTPS或HTTP）
            self.site = web.TCPSite(self.runner, self.host, self.port, ssl_context=ssl_context)
            await self.site.start()

            # 如果配置了SSL和HTTP端口，创建额外的HTTP站点
            if ssl_context and self.http_port:
                self.http_site = web.TCPSite(self.runner, self.host, self.http_port, ssl_context=None)
                await self.http_site.start()
                logger.info(f"HTTP 服务器已启动: http://{self.host}:{self.http_port}")

            self._running = True
            
            # 显示启动信息
            if ssl_context:
                logger.info(f"HTTPS 服务器已启动: https://{self.host}:{self.port}")
                if self.http_port:
                    logger.info(f"HTTP 服务器已启动: http://{self.host}:{self.http_port}")
            else:
                logger.info(f"HTTP 服务器已启动: http://{self.host}:{self.port}")
            logger.info(f"API 端点:")
            logger.info(f"  GET  /health           - 健康检查")
            logger.info(f"  POST /api/reload       - 热重载代码和配置")
            logger.info(f"  GET  /api/agents       - 获取可用智能体列表")
            logger.info(f"  POST /api/agents/get   - 获取用户智能体")
            logger.info(f"  POST /api/agents/set   - 设置用户智能体")
            logger.info(f"  GET  /api/models       - 获取可用模型列表")
            logger.info(f"  POST /api/model/get    - 获取用户模型")
            logger.info(f"  POST /api/model/set    - 设置用户模型")
            logger.info(f"  POST /api/task/get     - 获取用户任务列表")
            logger.info(f"  POST /api/task/set     - 创建定时任务")
            logger.info(f"  POST /api/task/update  - 更新定时任务")
            logger.info(f"  POST /api/task/delete  - 删除定时任务")
            logger.info(f"  POST /api/session/list   - 获取用户会话列表")
            logger.info(f"  POST /api/session/switch - 切换会话")
            logger.info(f"  POST /api/session/new    - 创建新会话")
            logger.info(f"  POST /api/session/delete - 删除会话")
            logger.info(f"  POST /api/session/title  - 设置会话标题")
            logger.info(f"  POST /api/directory/get  - 获取用户工作目录")
            logger.info(f"  POST /api/directory/set  - 设置用户工作目录")
            # OpenCode 代理端点
            logger.info(f"  GET  /api/opencode/events - OpenCode SSE事件流")
            logger.info(f"  GET  /api/opencode/sessions - OpenCode会话列表")
            logger.info(f"  POST /api/opencode/sessions - OpenCode创建会话")
            logger.info(f"  GET  /api/opencode/sessions/{{id}}/messages - OpenCode消息列表")
            logger.info(f"  POST /api/opencode/sessions/{{id}}/messages - OpenCode发送消息")
            logger.info(f"  GET  /api/opencode/models - OpenCode模型列表")
            logger.info(f"  GET  /api/opencode/agents - OpenCode智能体列表")

        except Exception as e:
            logger.error(f"启动 HTTP 服务器失败: {e}")
            raise

    async def stop(self) -> None:
        """停止 HTTP 服务器"""
        if not self._running:
            return

        try:
            if self.runner:
                await self.runner.cleanup()

            self._running = False
            logger.info("HTTP 服务器已停止")

        except Exception as e:
            logger.error(f"停止 HTTP 服务器失败: {e}")

    @property
    def is_running(self) -> bool:
        """检查服务器是否在运行"""
        return self._running


if __name__ == "__main__":
    # 测试代码
    async def test_reload():
        print("测试热重载回调")
        return {"message": "Test reload"}

    async def main():
        server = HTTPServer(
            host="127.0.0.1",
            port=8080,
            reload_callback=test_reload
        )

        await server.start()

        print("服务器已启动，按 Ctrl+C 停止")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

        await server.stop()

    asyncio.run(main())