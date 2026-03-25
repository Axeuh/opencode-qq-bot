#!/usr/bin/env python3
"""
路由定义模块
包含所有HTTP路由的注册
"""

from __future__ import annotations

import os
import logging
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from .auth_handler import AuthHandler
    from .session_endpoints import SessionEndpoints
    from .task_endpoints import TaskEndpoints
    from .config_endpoints import ConfigEndpoints
    from .upload_handler import UploadHandler
    from .opencode_proxy import OpenCodeProxy
    from .process_endpoints import ProcessEndpoints

logger = logging.getLogger(__name__)


class RouteSetup:
    """路由设置器
    
    负责注册所有HTTP路由
    """
    
    def __init__(
        self,
        auth_handler: "AuthHandler",
        session_endpoints: "SessionEndpoints",
        task_endpoints: "TaskEndpoints",
        config_endpoints: "ConfigEndpoints",
        upload_handler: "UploadHandler",
        opencode_proxy: "OpenCodeProxy",
        process_endpoints: "ProcessEndpoints" = None,
    ):
        """初始化路由设置器
        
        Args:
            auth_handler: 认证处理器
            session_endpoints: 会话端点处理器
            task_endpoints: 任务端点处理器
            config_endpoints: 配置端点处理器
            upload_handler: 文件上传处理器
            opencode_proxy: OpenCode代理处理器
            process_endpoints: 进程控制端点处理器
        """
        self.auth_handler = auth_handler
        self.session_endpoints = session_endpoints
        self.task_endpoints = task_endpoints
        self.config_endpoints = config_endpoints
        self.upload_handler = upload_handler
        self.opencode_proxy = opencode_proxy
        self.process_endpoints = process_endpoints
    
    def setup_routes(self, app: web.Application) -> None:
        """设置路由
        
        Args:
            app: aiohttp应用实例
        """
        router = app.router
        
        # 健康检查
        router.add_get("/health", self.auth_handler.handle_health)
        
        # 热重载
        router.add_post("/api/reload", self.config_endpoints.handle_reload)
        
        # 登录验证
        router.add_post("/api/login", self.auth_handler.handle_login)
        
        # 密码管理
        router.add_post("/api/password/set", self.auth_handler.handle_set_password)
        router.add_post("/api/password/change", self.auth_handler.handle_change_password)
        
        # 静态文件
        router.add_get("/", self.handle_index)
        router.add_get("/index.html", self.handle_index)
        
        # 静态资源目录
        router.add_get("/css/{filename}", self.handle_static_css)
        router.add_get("/js/{filename}", self.handle_static_js)
        
        # Agents 端点
        router.add_post("/api/agents/get", self.config_endpoints.handle_get_agents)
        router.add_post("/api/agents/set", self.config_endpoints.handle_set_agents)
        router.add_get("/api/agents", self.config_endpoints.handle_list_agents)
        
        # Model 端点
        router.add_post("/api/model/get", self.config_endpoints.handle_get_model)
        router.add_post("/api/model/set", self.config_endpoints.handle_set_model)
        router.add_get("/api/models", self.config_endpoints.handle_list_models)
        
        # Task 端点
        router.add_post("/api/task/get", self.task_endpoints.handle_get_tasks)
        router.add_post("/api/task/set", self.task_endpoints.handle_create_task)
        router.add_post("/api/task/update", self.task_endpoints.handle_update_task)
        router.add_post("/api/task/delete", self.task_endpoints.handle_delete_task)
        
        # Session 端点
        router.add_get("/api/session/status", self.session_endpoints.handle_sessions_status)
        router.add_post("/api/session/list", self.session_endpoints.handle_session_list)
        router.add_post("/api/session/switch", self.session_endpoints.handle_session_switch)
        router.add_post("/api/session/new", self.session_endpoints.handle_session_new)
        router.add_post("/api/session/delete", self.session_endpoints.handle_session_delete)
        router.add_post("/api/session/title", self.session_endpoints.handle_set_session_title)
        router.add_post("/api/session/tokens", self.session_endpoints.handle_update_session_tokens)
        
        # Directory 端点
        router.add_post("/api/directory/get", self.config_endpoints.handle_get_directory)
        router.add_post("/api/directory/set", self.config_endpoints.handle_set_directory)
        
        # 文件上传端点
        router.add_post("/api/upload", self.upload_handler.handle_upload)
        
        # OpenCode 代理端点
        router.add_get("/api/opencode/events", self.opencode_proxy.handle_opencode_events)
        router.add_get("/api/opencode/sessions", self.opencode_proxy.handle_opencode_session_list)
        router.add_post("/api/opencode/sessions", self.opencode_proxy.handle_opencode_session_create)
        router.add_delete("/api/opencode/sessions/{session_id}", self.opencode_proxy.handle_opencode_session_delete)
        router.add_get("/api/opencode/sessions/{session_id}/messages", self.opencode_proxy.handle_opencode_messages_get)
        router.add_post("/api/opencode/sessions/{session_id}/messages", self.opencode_proxy.handle_opencode_message_send)
        router.add_get("/api/opencode/models", self.opencode_proxy.handle_opencode_models)
        router.add_get("/api/opencode/agents", self.opencode_proxy.handle_opencode_agents)
        
        # QQ用户信息端点
        router.add_get("/api/qq/userinfo/{user_id}", self.opencode_proxy.handle_get_qq_userinfo)
        router.add_get("/api/qq/userinfo", self.opencode_proxy.handle_get_qq_userinfo)
        
        # 进程控制端点
        if self.process_endpoints:
            router.add_get("/api/system/status", self.process_endpoints.handle_get_status)
            router.add_post("/api/system/restart/opencode", self.process_endpoints.handle_restart_opencode)
            router.add_post("/api/system/start/opencode", self.process_endpoints.handle_start_opencode)
            router.add_post("/api/system/stop/opencode", self.process_endpoints.handle_stop_opencode)
            router.add_post("/api/system/restart/bot", self.process_endpoints.handle_restart_bot)
        
        # 404 处理
        router.add_route("*", "/{tail:.*}", self.handle_not_found)
    
    async def handle_not_found(self, request: web.Request) -> web.Response:
        """404 处理"""
        return web.json_response({
            "success": False,
            "error": "Not Found"
        }, status=404)
    
    async def handle_index(self, request: web.Request) -> web.FileResponse:
        """返回index.html"""
        # 尝试多个可能的位置
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'web', 'index.html'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'web', 'index.html'),
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'index.html'),
        ]
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                return web.FileResponse(abs_path)
        return web.json_response({"success": False, "error": "index.html not found"}, status=404)
    
    async def handle_static_css(self, request: web.Request) -> web.FileResponse:
        """返回CSS文件"""
        filename = request.match_info.get('filename', '')
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'web', 'css', filename),
            os.path.join(os.path.dirname(__file__), '..', '..', 'web', 'css', filename),
        ]
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                return web.FileResponse(abs_path)
        return web.json_response({"success": False, "error": "File not found"}, status=404)
    
    async def handle_static_js(self, request: web.Request) -> web.FileResponse:
        """返回JS文件"""
        filename = request.match_info.get('filename', '')
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'web', 'js', filename),
            os.path.join(os.path.dirname(__file__), '..', '..', 'web', 'js', filename),
        ]
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                return web.FileResponse(abs_path)
        return web.json_response({"success": False, "error": "File not found"}, status=404)


def log_routes_info() -> None:
    """打印路由信息日志"""
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
    logger.info(f"  GET  /api/session/status - 获取所有会话状态")
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
    # 进程控制端点
    logger.info(f"  GET  /api/system/status - 获取进程状态")
    logger.info(f"  POST /api/system/restart/opencode - 重启OpenCode")
    logger.info(f"  POST /api/system/start/opencode - 启动OpenCode")
    logger.info(f"  POST /api/system/stop/opencode - 停止OpenCode")
    logger.info(f"  POST /api/system/restart/bot - 重启Bot")