#!/usr/bin/env python3
"""
重启处理器模块 - 处理QQ机器人重启逻辑
从onebot_client.py中提取的重启逻辑
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
import os
import signal
from typing import Optional, Any, Callable
from collections.abc import Awaitable

logger = logging.getLogger(__name__)


class RestartHandler:
    """重启处理器，负责机器人程序重启"""
    
    def __init__(
        self,
        session_manager: Optional[Any] = None,
        tasks: Optional[list] = None,
        ws: Optional[Any] = None,
        session: Optional[Any] = None,
        opencode_client: Optional[Any] = None,
        opencode_sync_client: Optional[Any] = None,
        restarting_flag: Optional[Any] = None,
        connected_flag: Optional[Any] = None,
        stop_queue_processor_callback: Optional[Callable[[], Awaitable[None]]] = None
    ):
        """初始化重启处理器
        
        Args:
            session_manager: 会话管理器实例
            tasks: 异步任务列表
            ws: WebSocket连接实例
            session: HTTP会话实例
            opencode_client: OpenCode异步客户端实例
            opencode_sync_client: OpenCode同步客户端实例
            restarting_flag: 重启标志的引用（需要可写）
            connected_flag: 连接标志的引用（需要可写）
            stop_queue_processor_callback: 停止消息队列处理器的回调函数（异步）
        """
        self.session_manager = session_manager
        self.tasks = tasks or []
        self.ws = ws
        self.session = session
        self.opencode_client = opencode_client
        self.opencode_sync_client = opencode_sync_client
        self.restarting_flag = restarting_flag
        self.connected_flag = connected_flag
        self.stop_queue_processor_callback = stop_queue_processor_callback
    
    async def perform_restart(self) -> None:
        """执行机器人程序重启"""
        try:
            logger.info("开始执行机器人程序重启...")
            
            # 保存会话状态
            if self.session_manager:
                try:
                    self.session_manager.save_to_file()
                    logger.info("会话状态已保存")
                except Exception as e:
                    logger.warning(f"保存会话状态失败: {e}")
            
            # 获取当前工作目录和脚本路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            src_dir = os.path.dirname(current_dir)  # src目录
            project_dir = os.path.dirname(src_dir)  # 项目根目录
            
            # 确定启动脚本 - 使用scripts/run_bot.py
            startup_script = os.path.join(project_dir, "scripts", "run_bot.py")
            if not os.path.exists(startup_script):
                # 回退到根目录的run_bot.py（如果存在）
                startup_script = os.path.join(project_dir, "run_bot.py")
                if not os.path.exists(startup_script):
                    logger.error(f"找不到启动脚本: {startup_script}")
                    raise FileNotFoundError(f"找不到启动脚本: {startup_script}")
            
            logger.info(f"将启动脚本: {startup_script}")
            
            # 构建启动命令
            python_executable = sys.executable
            
            # 启动新进程
            env = os.environ.copy()
            # 添加重启标志到环境变量，以便新进程知道这是重启
            env["QQ_BOT_RESTARTED"] = "1"
            
            # 在Windows上，忽略SIGINT信号，让Ctrl+C传递给子进程
            if sys.platform == "win32":
                try:
                    signal.signal(signal.SIGINT, signal.SIG_IGN)
                    logger.info("已设置忽略SIGINT信号，Ctrl+C将传递给子进程")
                except Exception as e:
                    logger.warning(f"设置信号处理失败: {e}")
            
            # 根据操作系统使用适当的参数
            if sys.platform == "win32":
                # Windows: 使用CREATE_NEW_PROCESS_GROUP创建新的控制台进程组
                # 这有助于信号（如Ctrl+C）正确传递给子进程
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                # Unix-like系统：使用默认值
                creation_flags = 0
            
            try:
                # 启动新进程（在同一终端）
                # 显式设置stdin/stdout/stderr为None以继承父进程的控制台
                new_process = subprocess.Popen(
                    [python_executable, startup_script],
                    cwd=project_dir,
                    env=env,
                    creationflags=creation_flags,
                    stdin=None,
                    stdout=None,
                    stderr=None
                )
                
                logger.info(f"新进程已启动，PID: {new_process.pid}")
                
                # 短暂延迟，确保新进程已启动
                await asyncio.sleep(2)
                
                # 优雅关闭当前进程
                logger.info("优雅关闭当前进程...")
                
                # 设置重启标志，让主循环自然退出
                if self.restarting_flag is not None:
                    self.restarting_flag = True
                if self.connected_flag is not None:
                    self.connected_flag = False
                
                # 停止消息队列处理器
                if self.stop_queue_processor_callback:
                    try:
                        await self.stop_queue_processor_callback()
                        logger.info("消息队列处理器已停止")
                    except Exception as e:
                        logger.error(f"停止消息队列处理器时出错: {e}")
                else:
                    logger.warning("未提供stop_queue_processor_callback，消息队列处理器可能无法正确停止")
                
                # 取消所有任务
                for task in self.tasks:
                    if not task.done():
                        task.cancel()
                
                # 关闭WebSocket连接
                if self.ws and not getattr(self.ws, 'closed', True):
                    await self.ws.close()
                
                # 关闭HTTP会话
                if self.session:
                    await self.session.close()
                
                # 关闭OpenCode客户端
                if self.opencode_client:
                    try:
                        await self.opencode_client.close()
                        logger.info("OpenCode异步客户端已关闭")
                    except Exception as e:
                        logger.error(f"关闭OpenCode异步客户端时出错: {e}")
                
                if self.opencode_sync_client:
                    try:
                        self.opencode_sync_client.close()
                        logger.info("OpenCode同步客户端已关闭")
                    except Exception as e:
                        logger.error(f"关闭OpenCode同步客户端时出错: {e}")
                
                # 等待所有任务完成（带超时）
                logger.info("等待异步任务完成...")
                try:
                    # 收集未完成的任务
                    pending_tasks = [task for task in self.tasks if not task.done()]
                    if pending_tasks:
                        logger.info(f"等待{len(pending_tasks)}个任务完成...")
                        # 等待最多5秒
                        await asyncio.wait(pending_tasks, timeout=5.0)
                except Exception as e:
                    logger.warning(f"等待任务完成时出错: {e}")
                
                logger.info("重启过程完成，当前进程将自然退出")
                
                # 短暂延迟，确保新进程完全启动
                await asyncio.sleep(1)
                
                # 在Windows上，需要更长的等待时间以确保控制台交接
                if sys.platform == "win32":
                    logger.info("Windows系统: 额外等待2秒确保控制台交接...")
                    await asyncio.sleep(2)
                
                # 正常退出当前进程，让新进程接管终端
                # 使用sys.exit()而不是os._exit()以允许Python清理资源
                sys.exit(0)
            except Exception as e:
                logger.error(f"启动新进程失败: {e}")
                raise
                
        except Exception as e:
            logger.error(f"执行重启失败: {e}")
            raise