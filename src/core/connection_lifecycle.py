#!/usr/bin/env python3
"""
连接生命周期管理模块
从onebot_client.py中提取的连接生命周期相关方法
"""

import asyncio
import logging
from typing import Optional, Dict, Any

from src.utils import config

logger = logging.getLogger(__name__)


class ConnectionLifecycle:
    """管理OneBot客户端的连接生命周期"""
    
    def __init__(
        self,
        connection_manager,
        message_queue_processor,
        opencode_client: Optional[Any] = None,
        opencode_sync_client: Optional[Any] = None,
        session_manager: Optional[Any] = None,
        bot_qq_id: Optional[int] = None,
        opencode_available: bool = True,
        http_server: Optional[Any] = None,
        task_scheduler: Optional[Any] = None
    ):
        """初始化连接生命周期管理器
        
        Args:
            connection_manager: WebSocket连接管理器
            message_queue_processor: 消息队列处理器
            opencode_client: OpenCode异步客户端（可选）
            opencode_sync_client: OpenCode同步客户端（可选）
            session_manager: 会话管理器（可选）
            bot_qq_id: 机器人QQ号（可选）
            opencode_available: OpenCode集成是否可用
            http_server: HTTP服务器实例（可选）
            task_scheduler: 定时任务调度器实例（可选）
        """
        self.connection_manager = connection_manager
        self.message_queue_processor = message_queue_processor
        self.opencode_client = opencode_client
        self.opencode_sync_client = opencode_sync_client
        self.session_manager = session_manager
        self.bot_qq_id = bot_qq_id
        self.opencode_available = opencode_available
        self.http_server = http_server
        self.task_scheduler = task_scheduler
    
    async def connect(self) -> None:
        """连接到WebSocket服务器"""
        # 委托给ConnectionManager
        await self.connection_manager.connect()
        
        # 连接成功，执行后续初始化
        await self.on_connected()
    
    async def on_connected(self) -> None:
        """连接成功后的初始化"""
        logger.info(f"{config.BOT_NAME} 已准备就绪")
        logger.info("等待接收消息...")
        
        # 启动定时任务调度器
        if self.task_scheduler:
            try:
                await self.task_scheduler.start()
                logger.info("定时任务调度器已启动")
            except Exception as e:
                logger.error(f"启动定时任务调度器失败: {e}")
        
        # 启动 HTTP 服务器
        if self.http_server:
            try:
                await self.http_server.start()
            except Exception as e:
                logger.error(f"启动 HTTP 服务器失败: {e}")
        
        # 启动消息队列处理器
        if self.opencode_available and config.OPENCODE_ENABLED_FEATURES.get("message_forwarding", True):
            await self.message_queue_processor.start_queue_processor()
    
    async def disconnect(self) -> None:
        """断开连接"""
        self.connection_manager.connected = False
        
        # 停止定时任务调度器
        if self.task_scheduler:
            try:
                await self.task_scheduler.stop()
                logger.info("定时任务调度器已停止")
            except Exception as e:
                logger.error(f"停止定时任务调度器失败: {e}")
        
        # 停止 HTTP 服务器
        if self.http_server:
            try:
                await self.http_server.stop()
            except Exception as e:
                logger.error(f"停止 HTTP 服务器失败: {e}")
        
        # 停止消息队列处理器
        if self.message_queue_processor.queue_processing:
            await self.message_queue_processor.stop_queue_processor()
        
        # 取消所有任务
        for task in self.connection_manager.tasks:
            task.cancel()
        
        # 关闭WebSocket
        if self.connection_manager.ws:
            await self.connection_manager.ws.close()
        
        # 关闭会话
        if self.connection_manager.session:
            await self.connection_manager.session.close()
        
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
        
        # 保存会话数据
        if self.session_manager:
            try:
                logger.info("正在保存会话数据...")
                if self.session_manager.save_to_file():
                    logger.info("会话数据保存成功")
                else:
                    logger.warning("会话数据保存失败")
            except Exception as e:
                logger.error(f"保存会话数据时出错: {e}")
        
        logger.info("客户端已断开连接")
    
    async def run(self) -> None:
        """运行客户端（主循环）- 持续尝试连接直到成功"""
        try:
            while not self.connection_manager.restarting:
                try:
                    await self.connect()
                    
                    # 连接成功，保持运行直到断开或重启
                    while self.connection_manager.connected and not self.connection_manager.restarting:
                        await asyncio.sleep(1)
                        
                    # 如果连接断开但不是重启，等待10秒后重试
                    if not self.connection_manager.restarting:
                        logger.info("连接断开，10秒后尝试重连...")
                        await asyncio.sleep(10)
                        
                except KeyboardInterrupt:
                    logger.info("收到中断信号，正在关闭...")
                    break
                except Exception as e:
                    logger.error(f"连接过程错误: {e}")
                    if not self.connection_manager.restarting:
                        logger.info("10秒后尝试重连...")
                        await asyncio.sleep(10)
                        
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭...")
        except Exception as e:
            logger.error(f"客户端运行错误: {e}")
        finally:
            # 如果不是重启过程，则断开连接
            if not self.connection_manager.restarting:
                await self.disconnect()


if __name__ == "__main__":
    # 测试代码
    print("ConnectionLifecycle模块导入测试完成")