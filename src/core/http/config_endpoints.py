#!/usr/bin/env python3
"""
配置端点模块
包含模型、智能体、目录等配置端点处理
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional, Callable, Any, Awaitable, Dict, List

from aiohttp import web

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ConfigEndpoints:
    """配置端点处理器
    
    负责:
    - 获取/设置模型
    - 获取/设置智能体
    - 获取/设置工作目录
    - 获取模型/智能体列表
    - 热重载
    """
    
    def __init__(
        self,
        reload_callback: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None,
        get_user_config_callback: Optional[Callable[[int], Awaitable[Dict[str, Any]]]] = None,
        set_user_config_callback: Optional[Callable[[int, str, Any], Awaitable[Dict[str, Any]]]] = None,
        list_agents_callback: Optional[Callable[[], Awaitable[List[str]]]] = None,
        list_models_callback: Optional[Callable[[], Awaitable[List[str]]]] = None,
        get_directory_callback: Optional[Callable[[int, Optional[str]], Awaitable[Dict[str, Any]]]] = None,
        set_directory_callback: Optional[Callable[[int, str, Optional[str]], Awaitable[Dict[str, Any]]]] = None,
    ):
        """初始化配置端点处理器
        
        Args:
            reload_callback: 热重载回调
            get_user_config_callback: 获取用户配置回调
            set_user_config_callback: 设置用户配置回调
            list_agents_callback: 获取智能体列表回调
            list_models_callback: 获取模型列表回调
            get_directory_callback: 获取目录回调
            set_directory_callback: 设置目录回调
        """
        self.reload_callback = reload_callback
        self.get_user_config_callback = get_user_config_callback
        self.set_user_config_callback = set_user_config_callback
        self.list_agents_callback = list_agents_callback
        self.list_models_callback = list_models_callback
        self.get_directory_callback = get_directory_callback
        self.set_directory_callback = set_directory_callback
    
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