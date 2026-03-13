#!/usr/bin/env python3
"""
消息队列处理器模块 - 处理消息的异步队列和并行处理
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


class MessageQueueProcessor:
    """消息队列处理器，负责消息的异步队列处理和并行执行"""
    
    def __init__(self, opencode_integration, send_reply_callback: Callable, api_sender=None):
        """
        初始化消息队列处理器
        
        Args:
            opencode_integration: OpenCode集成对象，提供forward_to_opencode_sync方法
            send_reply_callback: 发送回复的回调函数，格式为:
                async def callback(message_type: str, target_id: int, 
                                 content: str, group_id: Optional[int] = None)
            api_sender: API发送器，用于设置输入状态
        """
        self.opencode_integration = opencode_integration
        self.send_reply_callback = send_reply_callback
        self.api_sender = api_sender
        
        # 消息队列用于异步处理
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.queue_processor_task: Optional[asyncio.Task] = None
        self.queue_processing = False
        
        # 队列统计
        self.queue_stats = {
            "processed": 0,
            "failed": 0,
            "retried": 0,
            "enqueued": 0,
            "active": 0,
            "max_queue_size": 0
        }
        self.queue_stats_lock = asyncio.Lock()
    
    async def start_queue_processor(self):
        """启动消息队列处理器"""
        if self.queue_processing:
            logger.warning("消息队列处理器已在运行")
            return
        
        self.queue_processing = True
        self.queue_processor_task = asyncio.create_task(self.queue_processor_loop())
        logger.info("消息队列处理器已启动")
    
    async def stop_queue_processor(self):
        """停止消息队列处理器"""
        self.queue_processing = False
        if self.queue_processor_task:
            # 保存任务引用以便从任务列表中移除
            task_to_remove = self.queue_processor_task
            task_to_remove.cancel()
            try:
                await task_to_remove
            except asyncio.CancelledError:
                pass
            self.queue_processor_task = None
            logger.info("消息队列处理器已停止")
    
    async def queue_processor_loop(self):
        """消息队列处理循环 - 并行处理消息"""
        logger.info("消息队列处理器开始运行（并行模式）")
        
        # 用于跟踪活跃任务
        active_tasks = set()
        
        while self.queue_processing:
            try:
                # 从队列获取消息（带超时，以便定期检查queue_processing标志和清理已完成任务）
                task = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=0.5  # 更短的超时，以便更频繁地检查任务状态
                )
            except asyncio.TimeoutError:
                # 清理已完成的任务
                if active_tasks:
                    done_tasks = {t for t in active_tasks if t.done()}
                    for task_obj in done_tasks:
                        try:
                            # 获取任务结果，捕获任何异常
                            await task_obj
                        except Exception as e:
                            logger.error(f"队列任务执行失败: {e}")
                        active_tasks.remove(task_obj)
                continue  # 超时时继续下一次循环
            
            # 为每个消息创建独立的任务并行处理
            process_task = asyncio.create_task(self._process_queued_message(task))
            active_tasks.add(process_task)
            
            # 添加回调以在任务完成时清理
            def make_task_done_callback(task_set, message_queue):
                def callback(task_obj):
                    try:
                        task_set.discard(task_obj)
                        # 标记原始任务完成
                        try:
                            message_queue.task_done()
                        except ValueError:
                            # 如果task_done被调用多次，忽略错误
                            pass
                    except Exception as e:
                        logger.error(f"清理任务时出错: {e}")
                return callback
            
            process_task.add_done_callback(make_task_done_callback(active_tasks, self.message_queue))
            
            # 如果活跃任务太多，等待一些完成（限制并发数）
            max_concurrent = 10  # 最大并发任务数
            if len(active_tasks) >= max_concurrent:
                logger.debug(f"达到最大并发数({max_concurrent})，等待任务完成")
                # 等待至少一个任务完成
                done, pending = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED)
                # 清理已完成的任务
                for task_obj in done:
                    active_tasks.discard(task_obj)
                    try:
                        await task_obj
                    except Exception as e:
                        logger.error(f"并发任务执行失败: {e}")
            continue  # 继续下一次循环
        
        # 等待所有剩余任务完成
        if active_tasks:
            logger.info(f"等待{len(active_tasks)}个活跃任务完成...")
            try:
                await asyncio.wait_for(asyncio.gather(*active_tasks, return_exceptions=True), timeout=10.0)
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"等待任务完成时超时或出错: {e}")
        
        logger.info("消息队列处理器已退出")
    
    async def _process_queued_message(self, task: Dict[str, Any]):
        """处理队列中的消息任务"""
        try:
            # 类型检查：确保 task 是字典
            if not isinstance(task, dict):
                logger.error(f"队列任务类型错误: 期望 dict，实际得到 {type(task).__name__}: {task}")
                return
            
            message_type = task.get("message_type")
            group_id = task.get("group_id")
            user_id = task.get("user_id")
            plain_text = task.get("plain_text")
            user_name = task.get("user_name")
            
            # 类型检查
            if not message_type or not user_id or plain_text is None:
                logger.warning(f"无效的队列任务: {task}")
                return
        
            # 确保plain_text是字符串
            plain_text_str = str(plain_text) if plain_text is not None else ""
            
            logger.debug(f"处理队列消息: 用户={user_id}, 名称={user_name}, 类型={message_type}, 长度={len(plain_text_str)}")
            
            # 创建持续发送输入状态的后台任务
            typing_task = None
            stop_typing = asyncio.Event()
            
            async def keep_typing_status():
                """持续发送输入状态，直到收到停止信号"""
                # 首次立即设置输入状态
                try:
                    if user_id and self.api_sender:
                        await self.api_sender.set_input_status(user_id, 1)
                        logger.debug(f"设置输入状态：用户={user_id}")
                except Exception as e:
                    logger.debug(f"设置输入状态失败：{e}")
                
                # 之后每 5 秒刷新一次输入状态
                while not stop_typing.is_set():
                    try:
                        await asyncio.wait_for(stop_typing.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        # 超时后刷新输入状态
                        try:
                            if user_id and self.api_sender:
                                await self.api_sender.set_input_status(user_id, 1)
                                logger.debug(f"刷新输入状态：用户={user_id}")
                        except Exception as e:
                            logger.debug(f"设置输入状态失败：{e}")
            
            # 启动后台任务
            if user_id and self.api_sender:
                typing_task = asyncio.create_task(keep_typing_status())
            
            try:
                # 调用原始的消息转发逻辑
                await self.opencode_integration.forward_to_opencode_sync(
                    message_type, group_id, user_id, plain_text_str, user_name, send_reply_callback=self.send_reply_callback
                )
            finally:
                # 停止输入状态任务
                stop_typing.set()
                if typing_task:
                    try:
                        await asyncio.wait_for(typing_task, timeout=5.0)
                    except asyncio.TimeoutError:
                        typing_task.cancel()
                logger.debug(f"已停止输入状态: 用户={user_id}")
            
        except Exception as e:
            import traceback
            logger.error(f"处理队列消息失败: {e}")
            logger.error(f"异常堆栈: {traceback.format_exc()}")
    
    async def enqueue_message(self, message_type: str, group_id: Optional[int],
                            user_id: Optional[int], plain_text: str,
                            user_name: Optional[str] = None):
        """将消息加入处理队列"""
        if not self.queue_processing:
            logger.warning("消息队列处理器未运行，将直接处理消息")
            await self.opencode_integration.forward_to_opencode_sync(
                message_type, group_id, user_id, plain_text, user_name, 
                send_reply_callback=self.send_reply_callback
            )
            return
        
        task = {
            "message_type": message_type,
            "group_id": group_id,
            "user_id": user_id,
            "plain_text": plain_text,
            "user_name": user_name,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        await self.message_queue.put(task)
        logger.debug(f"消息已加入队列: 用户={user_id}, 名称={user_name}, 队列大小={self.message_queue.qsize()}")