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
        get_directory_callback: Optional[Callable[[int, Optional[str]], Awaitable[Dict[str, Any]]]] = None,
        session_manager: Optional[Any] = None,
    ):
        """初始化OpenCode代理处理器
        
        Args:
            get_directory_callback: 获取目录回调，参数(user_id, session_id)
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
        """代理OpenCode异步发送消息 (使用 prompt_async 端点)"""
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
            
            # 构建JSON前缀 - 添加到 parts 中的文本内容
            if user_id and body_data.get("parts"):
                prefix_data = {
                    "type": "web_message",
                    "user_qq": str(user_id),
                    "user_name": user_name if user_name else None,
                    "session_id": session_id,
                    "hint": f"用户{f'({user_name}, ' if user_name else f'(QQ: {user_id}, '}QQ: {user_id})通过网页发送了一条消息。"
                }
                json_prefix = "<Axeuh_bot>\n" + json.dumps(prefix_data, ensure_ascii=False) + "\n</Axeuh_bot>\n\n"
                
                # 在 parts 的文本内容前面添加JSON前缀
                for part in body_data["parts"]:
                    if part.get("type") == "text" and part.get("text"):
                        part["text"] = json_prefix + part["text"]
                        break
                
                body = json.dumps(body_data).encode()
                logger.debug(f"已添加JSON前缀到网页消息，user_id={user_id}, session_id={session_id}")
            
            # 构建请求头
            headers = self._build_opencode_headers()
            
            # 获取用户的会话目录
            user_directory = OPENCODE_DIRECTORY
            if user_id and self.get_directory_callback:
                try:
                    dir_result = await self.get_directory_callback(user_id, session_id)
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
            
            # 发送消息前先中断会话（确保新消息能被处理）
            try:
                abort_headers = headers.copy()
                async with ClientSession() as abort_session:
                    async with abort_session.post(
                        f'{OPENCODE_BASE_URL}/session/{session_id}/abort',
                        headers=abort_headers
                    ) as abort_resp:
                        if abort_resp.status == 200:
                            logger.info(f"网页消息发送前自动中断会话: {session_id}")
                        else:
                            logger.debug(f"中断会话返回状态: {abort_resp.status}")
            except Exception as abort_e:
                # 中断失败不应阻止消息发送
                logger.debug(f"尝试中断会话失败（继续发送）: {abort_e}")
            
            # 使用 prompt_async 端点进行异步发送
            async with ClientSession() as session:
                async with session.post(
                    f'{OPENCODE_BASE_URL}/session/{session_id}/prompt_async',
                    headers=headers,
                    data=body
                ) as upstream:
                    data = await upstream.read()
                    # prompt_async 返回 204 No Content
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
    
    async def handle_opencode_session_abort(self, request: web.Request) -> web.Response:
        """代理OpenCode中止会话"""
        try:
            session_id = request.match_info.get('session_id')
            if not session_id:
                return web.json_response({"success": False, "error": "Missing session_id"}, status=400)
            
            # 从认证中间件获取用户ID
            user_id = request.get("user_id")
            
            # 构建请求头
            headers = self._build_opencode_headers()
            
            # 获取用户的会话目录
            user_directory = OPENCODE_DIRECTORY
            if user_id and self.get_directory_callback:
                try:
                    dir_result = await self.get_directory_callback(user_id, session_id)
                    if dir_result and dir_result.get("directory"):
                        user_directory = dir_result.get("directory")
                except Exception as e:
                    logger.warning(f"获取用户目录失败: {e}")
            
            # 确保目录不为空
            if not user_directory:
                user_directory = OPENCODE_DIRECTORY
            
            # 设置正确的目录
            headers["x-opencode-directory"] = user_directory
            
            async with ClientSession() as session:
                async with session.post(
                    f'{OPENCODE_BASE_URL}/session/{session_id}/abort',
                    headers=headers
                ) as upstream:
                    data = await upstream.read()
                    logger.info(f"中止会话: {session_id}, 状态: {upstream.status}")
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"代理中止会话失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)
    
    async def handle_opencode_session_command(self, request: web.Request) -> web.Response:
        """代理OpenCode会话命令执行"""
        try:
            session_id = request.match_info.get('session_id')
            if not session_id:
                return web.json_response({"success": False, "error": "Missing session_id"}, status=400)
            
            # 从认证中间件获取用户ID
            user_id = request.get("user_id")
            
            # 获取请求体
            body = await request.json()
            
            # 构建请求头
            headers = self._build_opencode_headers()
            headers["Content-Type"] = "application/json"
            
            # 获取用户的会话目录
            user_directory = OPENCODE_DIRECTORY
            if user_id and self.get_directory_callback:
                try:
                    dir_result = await self.get_directory_callback(user_id, session_id)
                    if dir_result and dir_result.get("directory"):
                        user_directory = dir_result.get("directory")
                except Exception as e:
                    logger.warning(f"获取用户目录失败: {e}")
            
            # 确保目录不为空
            if not user_directory:
                user_directory = OPENCODE_DIRECTORY
            
            # 设置正确的目录
            directory_b64 = base64.b64encode(user_directory.encode()).decode().rstrip('=')
            headers["x-opencode-directory"] = user_directory
            headers["Referer"] = f"{OPENCODE_BASE_URL}/{directory_b64}/session/{session_id}"
            
            async with ClientSession() as session:
                async with session.post(
                    f'{OPENCODE_BASE_URL}/session/{session_id}/command',
                    headers=headers,
                    json=body
                ) as upstream:
                    data = await upstream.read()
                    logger.info(f"执行命令: {body.get('command', 'unknown')}, 会话: {session_id}, 状态: {upstream.status}")
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"代理命令执行失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)
    
    async def handle_opencode_commands(self, request: web.Request) -> web.Response:
        """代理OpenCode命令列表"""
        try:
            async with ClientSession() as session:
                headers = self._build_opencode_headers()
                async with session.get(
                    f'{OPENCODE_BASE_URL}/command',
                    headers=headers
                ) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"代理命令列表失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)
    
    async def handle_opencode_session_status(self, request: web.Request) -> web.Response:
        """代理OpenCode会话状态（获取所有会话的busy/idle状态）"""
        try:
            user_id = request.get("user_id")
            headers = self._build_opencode_headers()
            
            user_directory = OPENCODE_DIRECTORY
            if user_id and self.get_directory_callback:
                try:
                    dir_result = await self.get_directory_callback(user_id, None)
                    if dir_result and dir_result.get("directory"):
                        user_directory = dir_result.get("directory")
                except Exception as e:
                    logger.warning(f"获取用户目录失败: {e}")
            
            if not user_directory:
                user_directory = OPENCODE_DIRECTORY
            
            headers["x-opencode-directory"] = user_directory
            
            async with ClientSession() as session:
                async with session.get(
                    f'{OPENCODE_BASE_URL}/session/status',
                    headers=headers
                ) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"获取会话状态失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)
    
    async def handle_opencode_session_diff(self, request: web.Request) -> web.Response:
        """代理OpenCode获取会话差异"""
        try:
            session_id = request.match_info.get('session_id')
            if not session_id:
                return web.json_response({"success": False, "error": "Missing session_id"}, status=400)
            
            user_id = request.get("user_id")
            headers = self._build_opencode_headers()
            
            user_directory = OPENCODE_DIRECTORY
            if user_id and self.get_directory_callback:
                try:
                    dir_result = await self.get_directory_callback(user_id, session_id)
                    if dir_result and dir_result.get("directory"):
                        user_directory = dir_result.get("directory")
                except Exception as e:
                    logger.warning(f"获取用户目录失败: {e}")
            
            if not user_directory:
                user_directory = OPENCODE_DIRECTORY
            
            headers["x-opencode-directory"] = user_directory
            
            # 获取查询参数
            query_string = request.query_string
            url = f'{OPENCODE_BASE_URL}/session/{session_id}/diff'
            if query_string:
                url += f'?{query_string}'
            
            async with ClientSession() as session:
                async with session.get(url, headers=headers) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"获取会话差异失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)
    
    async def handle_opencode_session_summarize(self, request: web.Request) -> web.Response:
        """代理OpenCode总结会话"""
        try:
            session_id = request.match_info.get('session_id')
            if not session_id:
                return web.json_response({"success": False, "error": "Missing session_id"}, status=400)
            
            user_id = request.get("user_id")
            body = await request.json()
            
            headers = self._build_opencode_headers()
            headers["Content-Type"] = "application/json"
            
            user_directory = OPENCODE_DIRECTORY
            if user_id and self.get_directory_callback:
                try:
                    dir_result = await self.get_directory_callback(user_id, session_id)
                    if dir_result and dir_result.get("directory"):
                        user_directory = dir_result.get("directory")
                except Exception as e:
                    logger.warning(f"获取用户目录失败: {e}")
            
            if not user_directory:
                user_directory = OPENCODE_DIRECTORY
            
            headers["x-opencode-directory"] = user_directory
            
            async with ClientSession() as session:
                async with session.post(
                    f'{OPENCODE_BASE_URL}/session/{session_id}/summarize',
                    headers=headers,
                    json=body
                ) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"总结会话失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)
    
    async def handle_opencode_session_revert(self, request: web.Request) -> web.Response:
        """代理OpenCode回退消息"""
        try:
            session_id = request.match_info.get('session_id')
            if not session_id:
                return web.json_response({"success": False, "error": "Missing session_id"}, status=400)
            
            user_id = request.get("user_id")
            body = await request.json()
            
            headers = self._build_opencode_headers()
            headers["Content-Type"] = "application/json"
            
            user_directory = OPENCODE_DIRECTORY
            if user_id and self.get_directory_callback:
                try:
                    dir_result = await self.get_directory_callback(user_id, session_id)
                    if dir_result and dir_result.get("directory"):
                        user_directory = dir_result.get("directory")
                except Exception as e:
                    logger.warning(f"获取用户目录失败: {e}")
            
            if not user_directory:
                user_directory = OPENCODE_DIRECTORY
            
            headers["x-opencode-directory"] = user_directory
            
            async with ClientSession() as session:
                async with session.post(
                    f'{OPENCODE_BASE_URL}/session/{session_id}/revert',
                    headers=headers,
                    json=body
                ) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"回退消息失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)
    
    async def handle_opencode_session_unrevert(self, request: web.Request) -> web.Response:
        """代理OpenCode恢复回退的消息"""
        try:
            session_id = request.match_info.get('session_id')
            if not session_id:
                return web.json_response({"success": False, "error": "Missing session_id"}, status=400)
            
            user_id = request.get("user_id")
            
            headers = self._build_opencode_headers()
            headers["Content-Type"] = "application/json"
            
            user_directory = OPENCODE_DIRECTORY
            if user_id and self.get_directory_callback:
                try:
                    dir_result = await self.get_directory_callback(user_id, session_id)
                    if dir_result and dir_result.get("directory"):
                        user_directory = dir_result.get("directory")
                except Exception as e:
                    logger.warning(f"获取用户目录失败: {e}")
            
            if not user_directory:
                user_directory = OPENCODE_DIRECTORY
            
            headers["x-opencode-directory"] = user_directory
            
            async with ClientSession() as session:
                async with session.post(
                    f'{OPENCODE_BASE_URL}/session/{session_id}/unrevert',
                    headers=headers
                ) as upstream:
                    data = await upstream.read()
                    return web.Response(status=upstream.status, body=data, content_type='application/json')
        except Exception as e:
            logger.error(f"恢复回退消息失败: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)