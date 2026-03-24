#!/usr/bin/env python3
"""
任务端点模块
包含任务列表、创建、更新、删除等端点处理
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional, Callable, Any, Awaitable, Dict, List

from aiohttp import web

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TaskEndpoints:
    """任务端点处理器
    
    负责:
    - 获取任务列表
    - 创建任务
    - 更新任务
    - 删除任务
    """
    
    def __init__(
        self,
        get_user_tasks_callback: Optional[Callable[[int], Awaitable[List[Dict[str, Any]]]]] = None,
        create_task_callback: Optional[Callable[[int, str, str, str, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
        update_task_callback: Optional[Callable[[int, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
        delete_task_callback: Optional[Callable[[int, str], Awaitable[Dict[str, Any]]]] = None,
    ):
        """初始化任务端点处理器
        
        Args:
            get_user_tasks_callback: 获取用户任务列表回调
            create_task_callback: 创建任务回调
            update_task_callback: 更新任务回调
            delete_task_callback: 删除任务回调
        """
        self.get_user_tasks_callback = get_user_tasks_callback
        self.create_task_callback = create_task_callback
        self.update_task_callback = update_task_callback
        self.delete_task_callback = delete_task_callback
    
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