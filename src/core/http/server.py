#!/usr/bin/env python3
"""
HTTP 服务器核心模块
提供 HTTPServer 类，组合所有处理器
"""

from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Optional, Callable, Dict, Any, Awaitable, List

from aiohttp import web

from .middleware import AuthMiddleware, create_auth_middleware
from .auth_handler import AuthHandler
from .session_endpoints import SessionEndpoints
from .task_endpoints import TaskEndpoints
from .config_endpoints import ConfigEndpoints
from .upload_handler import UploadHandler
from .opencode_proxy import OpenCodeProxy
from .routes import RouteSetup, log_routes_info

logger = logging.getLogger(__name__)


class HTTPServer:
    """HTTP 服务器，提供 API 接口
    
    公共 API:
        - __init__(): 初始化服务器
        - start(): 启动服务器
        - stop(): 停止服务器
        - is_running: 检查服务器是否在运行
    """

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
        # Session Tokens 回调
        update_session_tokens_callback: Optional[Callable[[int, str, Dict[str, int]], Awaitable[Dict[str, Any]]]] = None,
        # Directory 回调
        get_directory_callback: Optional[Callable[[int], Awaitable[Dict[str, Any]]]] = None,
        set_directory_callback: Optional[Callable[[int, str, Optional[str]], Awaitable[Dict[str, Any]]]] = None
    ):
        """初始化 HTTP 服务器

        Args:
            host: 监听地址
            port: 监听端口
            http_port: HTTP端口（可选，用于同时支持HTTP和HTTPS）
            access_token: API 访问令牌（可选）
            ssl_cert: SSL证书路径（可选）
            ssl_key: SSL密钥路径（可选）
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
            set_session_title_callback: 设置会话标题回调函数（异步），参数(user_id, session_id, title)，返回执行结果
            update_session_tokens_callback: 更新会话tokens回调函数（异步），参数(user_id, session_id, tokens)，返回执行结果
            get_directory_callback: 获取目录回调函数（异步），参数(user_id)，返回目录信息
            set_directory_callback: 设置目录回调函数（异步），参数(user_id, directory, session_id)，返回执行结果
        """
        self.host = host
        self.port = port
        self.http_port = http_port
        self.access_token = access_token
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        
        # 存储回调函数
        self.reload_callback = reload_callback
        self.get_user_config_callback = get_user_config_callback
        self.set_user_config_callback = set_user_config_callback
        self.list_agents_callback = list_agents_callback
        self.list_models_callback = list_models_callback
        self.get_user_tasks_callback = get_user_tasks_callback
        self.create_task_callback = create_task_callback
        self.update_task_callback = update_task_callback
        self.delete_task_callback = delete_task_callback
        self.get_user_sessions_callback = get_user_sessions_callback
        self.switch_session_callback = switch_session_callback
        self.create_session_callback = create_session_callback
        self.delete_session_callback = delete_session_callback
        self.set_session_title_callback = set_session_title_callback
        self.update_session_tokens_callback = update_session_tokens_callback
        self.get_directory_callback = get_directory_callback
        self.set_directory_callback = set_directory_callback

        # 服务器状态
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.http_site: Optional[web.TCPSite] = None
        self._running = False
        
        # 加载白名单配置
        self._whitelist: List[int] = []
        try:
            from ...utils import config as bot_config
            if hasattr(bot_config, 'QQ_USER_WHITELIST'):
                self._whitelist = bot_config.QQ_USER_WHITELIST
        except (ImportError, AttributeError):
            pass
        
        # 初始化组件
        self._init_components()
    
    def _init_components(self) -> None:
        """初始化所有组件"""
        # 认证中间件
        self.auth = AuthMiddleware(
            access_token=self.access_token,
            whitelist=self._whitelist
        )
        
        # 认证处理器
        self.auth_handler = AuthHandler(auth=self.auth)
        
        # 会话端点处理器
        self.session_endpoints = SessionEndpoints(
            get_user_sessions_callback=self.get_user_sessions_callback,
            switch_session_callback=self.switch_session_callback,
            create_session_callback=self.create_session_callback,
            delete_session_callback=self.delete_session_callback,
            set_session_title_callback=self.set_session_title_callback,
            update_session_tokens_callback=self.update_session_tokens_callback,
        )
        
        # 任务端点处理器
        self.task_endpoints = TaskEndpoints(
            get_user_tasks_callback=self.get_user_tasks_callback,
            create_task_callback=self.create_task_callback,
            update_task_callback=self.update_task_callback,
            delete_task_callback=self.delete_task_callback,
        )
        
        # 配置端点处理器
        self.config_endpoints = ConfigEndpoints(
            reload_callback=self.reload_callback,
            get_user_config_callback=self.get_user_config_callback,
            set_user_config_callback=self.set_user_config_callback,
            list_agents_callback=self.list_agents_callback,
            list_models_callback=self.list_models_callback,
            get_directory_callback=self.get_directory_callback,
            set_directory_callback=self.set_directory_callback,
        )
        
        # 文件上传处理器
        self.upload_handler = UploadHandler()
        
        # OpenCode代理处理器
        self.opencode_proxy = OpenCodeProxy(
            get_directory_callback=self.get_directory_callback,
        )
        
        # 路由设置器
        self.route_setup = RouteSetup(
            auth_handler=self.auth_handler,
            session_endpoints=self.session_endpoints,
            task_endpoints=self.task_endpoints,
            config_endpoints=self.config_endpoints,
            upload_handler=self.upload_handler,
            opencode_proxy=self.opencode_proxy,
        )

    async def start(self) -> None:
        """启动 HTTP 服务器"""
        if self._running:
            logger.warning("HTTP 服务器已在运行")
            return

        try:
            # 创建认证中间件
            auth_middleware = create_auth_middleware(self.auth)

            # 创建应用
            self.app = web.Application(middlewares=[auth_middleware])
            
            # 设置路由
            self.route_setup.setup_routes(self.app)

            # 创建runner
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
            
            # 打印路由信息
            log_routes_info()

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