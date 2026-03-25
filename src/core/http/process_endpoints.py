#!/usr/bin/env python3
"""
进程控制端点模块
提供进程管理相关的 HTTP 端点
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

from aiohttp import web

if TYPE_CHECKING:
    from .process_manager import ProcessManager

logger = logging.getLogger(__name__)


class ProcessEndpoints:
    """进程控制端点处理器
    
    负责:
    - OpenCode 进程状态查询
    - OpenCode 进程重启
    - Bot 进程状态
    """
    
    def __init__(self, process_manager: Optional["ProcessManager"] = None):
        """初始化进程控制端点处理器
        
        Args:
            process_manager: 进程管理器实例
        """
        self.process_manager = process_manager
    
    def set_process_manager(self, process_manager: "ProcessManager"):
        """设置进程管理器"""
        self.process_manager = process_manager
    
    async def handle_get_status(self, request: web.Request) -> web.Response:
        """获取进程状态"""
        try:
            if not self.process_manager:
                return web.json_response({
                    "success": False,
                    "error": "Process manager not initialized"
                }, status=500)
            
            status = self.process_manager.get_status()
            
            return web.json_response({
                "success": True,
                "status": status
            })
            
        except Exception as e:
            logger.error(f"获取进程状态失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def handle_restart_opencode(self, request: web.Request) -> web.Response:
        """重启 OpenCode 进程"""
        try:
            if not self.process_manager:
                return web.json_response({
                    "success": False,
                    "error": "Process manager not initialized"
                }, status=500)
            
            logger.info("收到重启 OpenCode 请求")
            
            result = await self.process_manager.restart_opencode()
            
            return web.json_response({
                "success": result.get("success", False),
                "message": "OpenCode restarted" if result.get("success") else result.get("error"),
                "details": result
            })
            
        except Exception as e:
            logger.error(f"重启 OpenCode 失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def handle_start_opencode(self, request: web.Request) -> web.Response:
        """启动 OpenCode 进程"""
        try:
            if not self.process_manager:
                return web.json_response({
                    "success": False,
                    "error": "Process manager not initialized"
                }, status=500)
            
            logger.info("收到启动 OpenCode 请求")
            
            result = await self.process_manager.start_opencode()
            
            return web.json_response({
                "success": result.get("success", False),
                "message": "OpenCode started" if result.get("success") else result.get("error"),
                "pid": result.get("pid")
            })
            
        except Exception as e:
            logger.error(f"启动 OpenCode 失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def handle_stop_opencode(self, request: web.Request) -> web.Response:
        """停止 OpenCode 进程"""
        try:
            if not self.process_manager:
                return web.json_response({
                    "success": False,
                    "error": "Process manager not initialized"
                }, status=500)
            
            logger.info("收到停止 OpenCode 请求")
            
            result = await self.process_manager.stop_opencode()
            
            return web.json_response({
                "success": result.get("success", False),
                "message": "OpenCode stopped" if result.get("success") else result.get("error")
            })
            
        except Exception as e:
            logger.error(f"停止 OpenCode 失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def handle_restart_bot(self, request: web.Request) -> web.Response:
        """重启 Bot 进程（内置实现）
        
        使用 os.execv 实现进程重启
        """
        try:
            logger.info("收到重启 Bot 请求")
            
            # 1. 保存活跃会话到文件（供重启后恢复）
            if self.process_manager and self.process_manager.opencode_client:
                logger.info("正在保存活跃会话...")
                saved_sessions = await self.process_manager._save_active_sessions()
                logger.info(f"已保存 {len(saved_sessions)} 个活跃会话")
                
                # 将会话信息写入临时文件
                import os
                sessions_file = os.path.join(os.getcwd(), "data", "sessions_to_recover.json")
                os.makedirs(os.path.dirname(sessions_file), exist_ok=True)
                with open(sessions_file, 'w', encoding='utf-8') as f:
                    json.dump(saved_sessions, f, ensure_ascii=False, indent=2)
                logger.info(f"会话信息已保存到: {sessions_file}")
            
            # 2. 停止 SSE 监听（释放端口连接）
            if self.process_manager and self.process_manager.on_before_opencode_stop:
                logger.info("正在停止 SSE 监听...")
                try:
                    await self.process_manager.on_before_opencode_stop()
                except Exception as e:
                    logger.warning(f"停止 SSE 监听失败: {e}")
            
            # 3. 延迟执行重启，先返回响应
            import asyncio
            asyncio.get_event_loop().call_later(1.0, self._do_restart_bot)
            
            return web.json_response({
                "success": True,
                "message": "Bot restart initiated. Bot will restart in 1 second."
            })
            
        except Exception as e:
            logger.error(f"请求重启 Bot 失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    def _do_restart_bot(self):
        """执行 Bot 重启"""
        import os
        import sys
        
        logger.info("正在重启 Bot...")
        
        # 获取当前 Python 解释器和脚本路径
        python = sys.executable
        script = sys.argv[0]
        
        logger.info(f"执行重启: {python} {script}")
        
        # 使用 os.execv 替换当前进程
        os.execv(python, [python] + sys.argv)
    
    def register_routes(self, app: web.Application):
        """注册路由到应用
        
        Args:
            app: aiohttp 应用实例
        """
        app.router.add_get('/api/system/status', self.handle_get_status)
        app.router.add_post('/api/system/restart/opencode', self.handle_restart_opencode)
        app.router.add_post('/api/system/start/opencode', self.handle_start_opencode)
        app.router.add_post('/api/system/stop/opencode', self.handle_stop_opencode)
        app.router.add_post('/api/system/restart/bot', self.handle_restart_bot)