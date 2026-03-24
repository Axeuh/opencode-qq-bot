#!/usr/bin/env python3
"""
用户配置数据类
存储单个用户的配置信息
"""

import time
from typing import Dict, Any
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
class UserConfig:
    """用户配置"""
    user_id: int
    password: str = ""  # bcrypt哈希密码
    agent: str = config.OPENCODE_DEFAULT_AGENT
    model: str = config.OPENCODE_DEFAULT_MODEL
    provider: str = config.OPENCODE_DEFAULT_PROVIDER
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserConfig':
        """从字典创建，过滤未知字段"""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)