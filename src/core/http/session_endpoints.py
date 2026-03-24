#!/usr/bin/env python3
"""
会话端点模块
包含会话列表、切换、创建、删除等端点处理
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional, Callable, Any, Awaitable, Dict

from aiohttp import web

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SessionEndpoints:
    """会话端点处理器
    
    负责:
    - 获取会话列表
    - 切换会话
    - 创建新会话
    - 删除会话
    - 设置会话标题
    - 更新会话tokens
    """
    
    def __init__(
        self,
        get_user_sessions_callback: Optional[Callable[[int], Awaitable[Dict[str, Any]]]] = None,
        switch_session_callback: Optional[Callable[[int, str], Awaitable[Dict[str, Any]]]] = None,
        create_session_callback: Optional[Callable[[int, Optional[str]], Awaitable[Dict[str, Any]]]] = None,
        delete_session_callback: Optional[Callable[[int, str], Awaitable[Dict[str, Any]]]] = None,
        set_session_title_callback: Optional[Callable[[int, str, str], Awaitable[Dict[str, Any]]]] = None,
        update_session_tokens_callback: Optional[Callable[[int, str, Dict[str, int]], Awaitable[Dict[str, Any]]]] = None,
    ):
        """初始化会话端点处理器
        
        Args:
            get_user_sessions_callback: 获取用户会话列表回调
            switch_session_callback: 切换会话回调
            create_session_callback: 创建会话回调
            delete_session_callback: 删除会话回调
            set_session_title_callback: 设置会话标题回调
            update_session_tokens_callback: 更新会话tokens回调
        """
        self.get_user_sessions_callback = get_user_sessions_callback
        self.switch_session_callback = switch_session_callback
        self.create_session_callback = create_session_callback
        self.delete_session_callback = delete_session_callback
        self.set_session_title_callback = set_session_title_callback
        self.update_session_tokens_callback = update_session_tokens_callback
    
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

    async def handle_update_session_tokens(self, request: web.Request) -> web.Response:
        """更新会话token统计 (POST)"""
        try:
            if not self.update_session_tokens_callback:
                return web.json_response({
                    "success": False,
                    "error": "Update session tokens callback not configured"
                }, status=500)

            # 从请求体获取参数
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid JSON body"
                }, status=400)

            user_id = body.get("user_id")
            session_id = body.get("session_id")
            tokens = body.get("tokens")

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

            if not tokens:
                return web.json_response({
                    "success": False,
                    "error": "Missing required parameter: tokens"
                }, status=400)

            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)

            # 更新会话tokens
            result = await self.update_session_tokens_callback(user_id, session_id, tokens)

            if not result.get("success", True):
                return web.json_response({
                    "success": False,
                    "error": result.get("error", "Failed to update session tokens")
                }, status=400)

            return web.json_response({
                "success": True,
                "message": "Session tokens updated successfully",
                "session_id": session_id
            })

        except Exception as e:
            logger.error(f"更新会话tokens失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)