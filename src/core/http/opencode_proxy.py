#!/usr/bin/env python3
"""
OpenCode代理模块
包含OpenCode API代理端点处理
"""

from __future__ import annotations

import base64
import json
import logging
from typing import TYPE_CHECKING, Optional, Callable, Any, Awaitable, Dict

from aiohttp import web, ClientSession, ClientError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# OpenCode代理配置
try:
    from ...utils import config as bot_config
    OPENCODE_BASE_URL = bot_config.OPENCODE_BASE_URL.rstrip('/')
    OPENCODE_COOKIES = bot_config.OPENCODE_COOKIES
    OPENCODE_DIRECTORY = bot_config.OPENCODE_DIRECTORY
except ImportError:
    OPENCODE_BASE_URL = "http://127.0.0.1:4091"
    OPENCODE_COOKIES = {}
    OPENCODE_DIRECTORY = "C:\\"


class OpenCodeProxy:
    """OpenCode代理处理器
    
    负责:
    - 代理OpenCode SSE事件流
    - 代理OpenCode会话操作
    - 代理OpenCode消息操作
    - 代理OpenCode模型/智能体列表
    - 获取QQ用户信息
    """
    
    def __init__(
        self,
        get_directory_callback: Optional[Callable[[int], Awaitable[Dict[str, Any]]]] = None,
        session_manager: Optional[Any] = None,
    ):
        """初始化OpenCode代理处理器
        
        Args:
            get_directory_callback: 获取目录回调
            session_manager: 会话管理器实例
        """
        self.get_directory_callback = get_directory_callback
        self.session_manager = session_manager
    
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
            body_data = json.loads(body) if body else {}
            
            # 从认证中间件获取用户ID
            user_id = request.get("user_id")
            
            # 获取用户昵称
            user_name = ""
            if user_id:
                # 尝试从session_manager获取用户昵称
                if self.session_manager:
                    user_session = self.session_manager.get_user_session(user_id)
                    if user_session and hasattr(user_session, 'user_name'):
                        user_name = user_session.user_name or ""
                
                # 如果没有昵称，尝试从napcat获取
                if not user_name:
                    try:
                        user_name = await self._get_user_nickname(str(user_id))
                    except Exception as e:
                        logger.debug(f"获取用户昵称失败: {e}")
            
            # 构建JSON前缀
            if user_id and body_data.get("prompt"):
                prefix_data = {
                    "type": "web_message",
                    "user_qq": str(user_id),
                    "user_name": user_name if user_name else None,
                    "session_id": session_id,
                    "hint": f"用户{f'({user_name}, ' if user_name else f'(QQ: {user_id}, '}QQ: {user_id})通过网页发送了一条消息。"
                }
                json_prefix = "<Axeuh_bot>\n" + json.dumps(prefix_data, ensure_ascii=False) + "\n</Axeuh_bot>\n"
                
                # 在消息前面添加JSON前缀
                body_data["prompt"] = json_prefix + body_data["prompt"]
                body = json.dumps(body_data).encode()
                logger.debug(f"已添加JSON前缀到网页消息，user_id={user_id}, session_id={session_id}")
            
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
            directory_b64 = base64.b64encode(user_directory.encode()).decode()
            headers["x-opencode-directory"] = user_directory
            headers["Referer"] = f"{OPENCODE_BASE_URL}/{directory_b64}/session/{session_id}"
            
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
    
    async def _get_user_nickname(self, user_id: str) -> str:
        """从napcat获取用户昵称"""
        try:
            # 从配置加载napcat HTTP API配置
            try:
                from ...utils import config as bot_config
                napcat_url = bot_config.HTTP_API_BASE_URL
                napcat_token = bot_config.HTTP_API_ACCESS_TOKEN
            except ImportError:
                napcat_url = "http://localhost:3001"
                napcat_token = ""
            
            async with ClientSession() as session:
                headers = {}
                if napcat_token:
                    headers["Authorization"] = f"Bearer {napcat_token}"
                async with session.post(
                    f"{napcat_url}/get_stranger_info",
                    json={"user_id": user_id},
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "ok" and data.get("data"):
                            return data["data"].get("nickname", "")
        except Exception as e:
            logger.debug(f"获取用户昵称失败: {e}")
        return ""
    
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
            
            # 从配置加载napcat HTTP API配置
            try:
                from ...utils import config as bot_config
                napcat_url = bot_config.HTTP_API_BASE_URL
                napcat_token = bot_config.HTTP_API_ACCESS_TOKEN
            except ImportError:
                napcat_url = "http://localhost:3001"
                napcat_token = ""
            
            async with ClientSession() as session:
                headers = {}
                if napcat_token:
                    headers["Authorization"] = f"Bearer {napcat_token}"
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