#!/usr/bin/env python3
"""
HTTP 服务器模块
为机器人提供 HTTP API 接口
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional, Callable, Dict, Any, Awaitable, List

from aiohttp import web

logger = logging.getLogger(__name__)


class HTTPServer:
    """HTTP 服务器，提供 API 接口"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        access_token: str = "",
        reload_callback: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None,
        get_user_config_callback: Optional[Callable[[int], Awaitable[Dict[str, Any]]]] = None,
        set_user_config_callback: Optional[Callable[[int, str, Any], Awaitable[Dict[str, Any]]]] = None,
        list_agents_callback: Optional[Callable[[], Awaitable[List[str]]]] = None,
        list_models_callback: Optional[Callable[[], Awaitable[List[str]]]] = None,
        get_user_tasks_callback: Optional[Callable[[int], Awaitable[List[Dict[str, Any]]]]] = None,
        create_task_callback: Optional[Callable[[int, str, str, str, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
        update_task_callback: Optional[Callable[[int, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
        delete_task_callback: Optional[Callable[[int, str], Awaitable[Dict[str, Any]]]] = None
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
        """
        self.host = host
        self.port = port
        self.access_token = access_token
        self.reload_callback = reload_callback
        self.get_user_config_callback = get_user_config_callback
        self.set_user_config_callback = set_user_config_callback
        self.list_agents_callback = list_agents_callback
        self.list_models_callback = list_models_callback
        self.get_user_tasks_callback = get_user_tasks_callback
        self.create_task_callback = create_task_callback
        self.update_task_callback = update_task_callback
        self.delete_task_callback = delete_task_callback

        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._running = False

    def _check_auth(self, request: web.Request) -> bool:
        """检查请求认证

        Args:
            request: HTTP 请求对象

        Returns:
            认证是否通过
        """
        # 如果未配置 access_token，则不需要认证
        if not self.access_token:
            return True

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

        return token == self.access_token

    async def handle_health(self, request: web.Request) -> web.Response:
        """健康检查端点"""
        return web.json_response({
            "success": True,
            "status": "healthy",
            "service": "QQ Bot HTTP Server"
        })

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

    async def handle_not_found(self, request: web.Request) -> web.Response:
        """404 处理"""
        return web.json_response({
            "success": False,
            "error": "Not Found"
        }, status=404)

    def setup_routes(self) -> None:
        """设置路由"""
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_post("/api/reload", self.handle_reload)
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
                # 跳过健康检查端点的认证
                if request.path == "/health":
                    return await handler(request)

                # 检查认证
                if not self._check_auth(request):
                    return web.json_response(
                        {"success": False, "error": "Unauthorized"},
                        status=401
                    )

                return await handler(request)

            self.app = web.Application(middlewares=[auth_middleware])
            self.setup_routes()

            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()

            self._running = True
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