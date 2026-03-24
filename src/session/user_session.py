#!/usr/bin/env python3
"""
用户会话数据类
存储单个用户的会话信息
"""

import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, field

try:
    from ..utils import config
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from src.utils import config
    except ImportError:
        import config  # pyright: ignore[reportMissingImports]


@dataclass
class UserSession:
    """用户会话数据"""
    user_id: int
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    title: str = ""
    
    # 用户配置
    agent: str = config.OPENCODE_DEFAULT_AGENT
    model: str = config.OPENCODE_DEFAULT_MODEL
    provider: str = config.OPENCODE_DEFAULT_PROVIDER
    directory: str = config.OPENCODE_DIRECTORY
    
    # 元数据
    group_id: Optional[int] = None  # 最近使用的群ID（如果有）
    message_count: int = 0
    is_active: bool = True
    system_prompt_sent: bool = False  # 系统提示词是否已发送
    tokens: Optional[Dict[str, int]] = None  # token统计 {total, input, output}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserSession':
        """从字典创建，过滤未知字段"""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)
    
    def update_access(self) -> None:
        """更新访问时间"""
        self.last_accessed = time.time()
        self.message_count += 1