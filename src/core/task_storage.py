#!/usr/bin/env python3
"""
定时任务存储模块
负责定时任务的持久化存储
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """定时类型"""
    DELAY = "delay"           # 延时任务：一次性，指定分钟后触发
    SCHEDULED = "scheduled"   # 定时任务：按周算，可设置重复


@dataclass
class Task:
    """定时任务数据结构"""
    task_id: str                    # 任务唯一ID
    user_id: int                    # 用户QQ号
    session_id: str                 # OpenCode会话ID
    task_name: str                  # 任务名称
    prompt: str                     # 任务提示词
    schedule_type: str              # 定时类型: delay/scheduled
    schedule_config: Dict[str, Any] # 定时配置
    enabled: bool = True            # 是否启用
    repeat: bool = False            # 是否重复执行（仅scheduled类型有效）
    created_at: float = 0           # 创建时间戳
    last_run: Optional[float] = None    # 上次运行时间
    next_run: Optional[float] = None    # 下次运行时间
    run_count: int = 0              # 运行次数

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """从字典创建"""
        return cls(**data)


class TaskStorage:
    """定时任务存储管理器"""
    
    DEFAULT_FILE = "data/tasks.json"
    
    def __init__(self, file_path: Optional[str] = None):
        """初始化存储管理器
        
        Args:
            file_path: 存储文件路径，默认为 data/tasks.json
        """
        self.file_path = file_path or self.DEFAULT_FILE
        self._tasks: Dict[str, Task] = {}  # task_id -> Task
        self._user_tasks: Dict[int, List[str]] = {}  # user_id -> [task_ids]
        self._load()
    
    def _load(self) -> None:
        """从文件加载任务数据"""
        if not os.path.exists(self.file_path):
            logger.info(f"任务文件不存在，将创建新文件: {self.file_path}")
            self._ensure_dir()
            return
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for task_data in data.get("tasks", []):
                task = Task.from_dict(task_data)
                self._tasks[task.task_id] = task
                
                if task.user_id not in self._user_tasks:
                    self._user_tasks[task.user_id] = []
                self._user_tasks[task.user_id].append(task.task_id)
            
            logger.info(f"已加载 {len(self._tasks)} 个定时任务")
            
        except Exception as e:
            logger.error(f"加载任务文件失败: {e}")
    
    def _save(self) -> bool:
        """保存任务数据到文件"""
        try:
            self._ensure_dir()
            
            data = {
                "version": 1,
                "updated_at": datetime.now().isoformat(),
                "tasks": [task.to_dict() for task in self._tasks.values()]
            }
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"已保存 {len(self._tasks)} 个任务到 {self.file_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存任务文件失败: {e}")
            return False
    
    def _ensure_dir(self) -> None:
        """确保存储目录存在"""
        dir_path = os.path.dirname(self.file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
    
    def create_task(
        self,
        user_id: int,
        session_id: str,
        task_name: str,
        prompt: str,
        schedule_type: str,
        schedule_config: Dict[str, Any]
    ) -> Task:
        """创建新任务
        
        Args:
            user_id: 用户QQ号
            session_id: OpenCode会话ID
            task_name: 任务名称
            prompt: 任务提示词
            schedule_type: 定时类型
            schedule_config: 定时配置
            
        Returns:
            创建的任务对象
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        task = Task(
            task_id=task_id,
            user_id=user_id,
            session_id=session_id,
            task_name=task_name,
            prompt=prompt,
            schedule_type=schedule_type,
            schedule_config=schedule_config,
            enabled=True,
            created_at=datetime.now().timestamp()
        )
        
        self._tasks[task_id] = task
        
        if user_id not in self._user_tasks:
            self._user_tasks[user_id] = []
        self._user_tasks[user_id].append(task_id)
        
        self._save()
        logger.info(f"创建任务: {task_id} - {task_name}")
        
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务对象，不存在返回None
        """
        return self._tasks.get(task_id)
    
    def get_user_tasks(self, user_id: int) -> List[Task]:
        """获取用户的所有任务
        
        Args:
            user_id: 用户QQ号
            
        Returns:
            任务列表
        """
        task_ids = self._user_tasks.get(user_id, [])
        tasks = []
        for task_id in task_ids:
            task = self._tasks.get(task_id)
            if task:
                tasks.append(task)
        return tasks
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否删除成功
        """
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        user_id = task.user_id
        
        # 从任务字典中删除
        del self._tasks[task_id]
        
        # 从用户任务列表中删除
        if user_id in self._user_tasks:
            if task_id in self._user_tasks[user_id]:
                self._user_tasks[user_id].remove(task_id)
        
        self._save()
        logger.info(f"删除任务: {task_id}")
        
        return True
    
    def update_task(
        self,
        task_id: str,
        **kwargs
    ) -> Optional[Task]:
        """更新任务
        
        Args:
            task_id: 任务ID
            **kwargs: 要更新的字段
            
        Returns:
            更新后的任务，不存在返回None
        """
        task = self._tasks.get(task_id)
        if not task:
            return None
        
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        self._save()
        logger.info(f"更新任务: {task_id}")
        
        return task
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def get_enabled_tasks(self) -> List[Task]:
        """获取所有启用的任务"""
        return [task for task in self._tasks.values() if task.enabled]


# 全局存储实例
_task_storage: Optional[TaskStorage] = None


def get_task_storage() -> TaskStorage:
    """获取全局任务存储实例"""
    global _task_storage
    if _task_storage is None:
        _task_storage = TaskStorage()
    return _task_storage