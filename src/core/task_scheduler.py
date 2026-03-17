#!/usr/bin/env python3
"""
定时任务调度器模块
负责定时任务的调度和执行
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, Awaitable, Dict, Any, List

from .task_storage import Task, TaskStorage, get_task_storage

try:
    from ..utils import config
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from utils import config
    except ImportError:
        import config

logger = logging.getLogger(__name__)


class TaskScheduler:
    """定时任务调度器"""
    
    def __init__(
        self,
        task_storage: Optional[TaskStorage] = None,
        execute_callback: Optional[Callable[[str, str, Dict[str, Any]], Awaitable[None]]] = None,
        check_interval: Optional[int] = None
    ):
        """初始化调度器
        
        Args:
            task_storage: 任务存储实例
            execute_callback: 任务执行回调，参数(session_id, prompt, task_info)
            check_interval: 检查间隔（秒），默认从配置读取
        """
        self.task_storage = task_storage or get_task_storage()
        self.execute_callback = execute_callback
        
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._check_interval = check_interval or config.TASK_SCHEDULER_CHECK_INTERVAL
    
    def _calculate_next_run(self, task: Task) -> Optional[float]:
        """计算下次运行时间
        
        Args:
            task: 任务对象
            
        Returns:
            下次运行时间戳，如果任务不应再运行返回None
        """
        now = datetime.now()
        config = task.schedule_config
        
        if task.schedule_type == "delay":
            # 延时任务：一次性，可设置秒/分/时/日/周/月
            if task.last_run is not None:
                # 已运行过，不再运行
                return None
            
            # 计算延迟时间
            delay = timedelta()
            delay += timedelta(seconds=config.get("seconds", 0))
            delay += timedelta(minutes=config.get("minutes", 0))
            delay += timedelta(hours=config.get("hours", 0))
            delay += timedelta(days=config.get("days", 0))
            delay += timedelta(weeks=config.get("weeks", 0))
            # 月数近似处理
            months = config.get("months", 0)
            if months > 0:
                delay += timedelta(days=months * 30)  # 近似处理
            
            created = datetime.fromtimestamp(task.created_at)
            next_run = created + delay
            return next_run.timestamp()
        
        elif task.schedule_type == "scheduled":
            # 定时任务：按周/月/年
            mode = config.get("mode", "weekly")
            hour = config.get("hour", 9)
            minute = config.get("minute", 0)
            
            if mode == "weekly":
                # 按周：指定星期几
                days = config.get("days", [1, 2, 3, 4, 5, 6, 7])
                
                for i in range(8):
                    check_date = now + timedelta(days=i)
                    check_date = check_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    weekday = check_date.isoweekday()
                    if weekday in days and check_date > now:
                        if not task.repeat and task.last_run is not None:
                            return None
                        return check_date.timestamp()
            
            elif mode == "monthly":
                # 按月：每月指定日期
                day = config.get("day", 1)
                
                for i in range(32):  # 最多检查31天
                    check_date = now + timedelta(days=i)
                    try:
                        check_date = check_date.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
                        if check_date > now:
                            if not task.repeat and task.last_run is not None:
                                return None
                            return check_date.timestamp()
                    except ValueError:
                        # 日期无效（如2月30日），跳过
                        continue
            
            elif mode == "yearly":
                # 按年：每年指定月日
                month = config.get("month", 1)
                day = config.get("day", 1)
                
                for year_offset in range(2):  # 检查今年和明年
                    try:
                        check_date = datetime(now.year + year_offset, month, day, hour, minute, 0)
                        if check_date > now:
                            if not task.repeat and task.last_run is not None:
                                return None
                            return check_date.timestamp()
                    except ValueError:
                        # 日期无效
                        continue
            
            return None
        
        return None
    
    async def _execute_task(self, task: Task) -> None:
        """执行任务
        
        Args:
            task: 任务对象
        """
        if not self.execute_callback:
            logger.warning(f"任务执行回调未配置，无法执行任务: {task.task_id}")
            return
        
        try:
            logger.info(f"执行任务: {task.task_id} - {task.task_name}")
            
            # 立即更新任务状态（开始执行时）
            now = datetime.now().timestamp()
            task.last_run = now
            task.run_count += 1
            
            # 如果是延时任务，立即禁用（防止重复执行）
            if task.schedule_type == "delay":
                task.enabled = False
            
            # 保存状态到存储
            self.task_storage.update_task(
                task.task_id,
                last_run=task.last_run,
                run_count=task.run_count,
                enabled=task.enabled
            )
            
            # 构建任务信息字典
            task_info = {
                "task_id": task.task_id,
                "user_id": task.user_id,
                "session_id": task.session_id,
                "task_name": task.task_name
            }
            
            # 调用执行回调，传递 task_info
            await self.execute_callback(task.session_id, task.prompt, task_info)
            
            # 更新下次运行时间（在回调完成后）
            task.next_run = self._calculate_next_run(task)
            self.task_storage.update_task(task.task_id, next_run=task.next_run)
            
            logger.info(f"任务执行完成: {task.task_id}")
            
        except Exception as e:
            logger.error(f"任务执行失败: {task.task_id} - {e}")
    
    async def _check_tasks(self) -> None:
        """检查并执行到期任务"""
        now = datetime.now().timestamp()
        
        tasks = self.task_storage.get_enabled_tasks()
        
        for task in tasks:
            # 计算下次运行时间
            if task.next_run is None:
                task.next_run = self._calculate_next_run(task)
                if task.next_run:
                    self.task_storage.update_task(task.task_id, next_run=task.next_run)
            
            # 检查是否到期
            if task.next_run and task.next_run <= now:
                await self._execute_task(task)
    
    async def _scheduler_loop(self) -> None:
        """调度器主循环"""
        logger.info("定时任务调度器已启动")
        
        while self._running:
            try:
                await self._check_tasks()
            except Exception as e:
                logger.error(f"任务检查失败: {e}")
            
            await asyncio.sleep(self._check_interval)
        
        logger.info("定时任务调度器已停止")
    
    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            logger.warning("调度器已在运行")
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    async def stop(self) -> None:
        """停止调度器"""
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            
            self._scheduler_task = None
    
    def add_task(self, task: Task) -> None:
        """添加任务（触发立即检查）"""
        next_run = self._calculate_next_run(task)
        if next_run:
            self.task_storage.update_task(task.task_id, next_run=next_run)
    
    def get_task_info(self, task: Task) -> Dict[str, Any]:
        """获取任务信息
        
        Args:
            task: 任务对象
            
        Returns:
            任务信息字典
        """
        next_run_str = None
        if task.next_run:
            next_run_str = datetime.fromtimestamp(task.next_run).strftime("%Y-%m-%d %H:%M:%S")
        
        last_run_str = None
        if task.last_run:
            last_run_str = datetime.fromtimestamp(task.last_run).strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "task_id": task.task_id,
            "user_id": task.user_id,
            "session_id": task.session_id,
            "task_name": task.task_name,
            "prompt": task.prompt[:100] + "..." if len(task.prompt) > 100 else task.prompt,
            "schedule_type": task.schedule_type,
            "schedule_config": task.schedule_config,
            "enabled": task.enabled,
            "created_at": datetime.fromtimestamp(task.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            "last_run": last_run_str,
            "next_run": next_run_str,
            "run_count": task.run_count
        }


# 全局调度器实例
_task_scheduler: Optional[TaskScheduler] = None


def get_task_scheduler() -> TaskScheduler:
    """获取全局调度器实例"""
    global _task_scheduler
    if _task_scheduler is None:
        _task_scheduler = TaskScheduler()
    return _task_scheduler


def init_task_scheduler(execute_callback: Callable[[str, str, Dict[str, Any]], Awaitable[None]]) -> TaskScheduler:
    """初始化全局调度器
    
    Args:
        execute_callback: 任务执行回调，参数(session_id, prompt, task_info)
        
    Returns:
        调度器实例
    """
    global _task_scheduler
    _task_scheduler = TaskScheduler(execute_callback=execute_callback)
    return _task_scheduler