# Agent-Session 重构任务书

**负责文件:** `src/session/session_manager.py` (1355 行)
**目标:** 拆分为 3-4 个小模块，每个模块 < 400 行
**优先级:** 高

---

## 任务目标

将 `session_manager.py` (1355 行) 拆分为职责单一的小模块。

---

## 输入文件

`src/session/session_manager.py` - 当前结构:
- UserSession 类 (数据类)
- UserConfig 类 (数据类)
- SessionManager 类 (主类，包含持久化逻辑)

---

## 输出文件结构

```
src/session/
    __init__.py              # 导出 SessionManager, UserSession, UserConfig
    session_manager.py       # SessionManager 核心类 (~400 行)
    user_session.py          # UserSession 数据类 (~200 行)
    user_config.py           # UserConfig 数据类 (~200 行)
    persistence.py           # 文件持久化逻辑 (~300 行)
```

---

## 详细步骤

### Step 1: 分析现有结构

阅读 `session_manager.py`，识别:
- UserSession 类的所有属性和方法
- UserConfig 类的所有属性和方法
- SessionManager 类的核心方法和持久化方法

### Step 2: 创建 user_session.py

提取 UserSession 类:
```python
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime

@dataclass
class UserSession:
    """用户会话数据类"""
    session_id: str
    user_id: int
    created_at: str
    title: Optional[str] = None
    model: Optional[str] = None
    agent: Optional[str] = None
    # ... 其他属性
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        pass
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserSession':
        """从字典创建"""
        pass
```

### Step 3: 创建 user_config.py

提取 UserConfig 类:
```python
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

@dataclass
class UserConfig:
    """用户配置数据类"""
    user_id: int
    current_session_id: Optional[str] = None
    current_model: Optional[str] = None
    current_agent: Optional[str] = None
    # ... 其他属性
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        pass
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserConfig':
        """从字典创建"""
        pass
```

### Step 4: 创建 persistence.py

提取文件持久化逻辑:
```python
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class SessionPersistence:
    """会话持久化管理器"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """确保数据文件存在"""
        pass
    
    def load_all(self) -> Dict[str, Any]:
        """加载所有数据"""
        pass
    
    def save_all(self, data: Dict[str, Any]) -> bool:
        """保存所有数据"""
        pass
    
    # 提取 load_from_file() 的核心逻辑
    def load_sessions(self) -> Dict[int, Dict]:
        """加载会话数据"""
        pass
    
    def load_configs(self) -> Dict[int, Dict]:
        """加载配置数据"""
        pass
```

### Step 5: 重构 session_manager.py

简化 SessionManager 类:
```python
from typing import Optional, Dict, Any, List
from .user_session import UserSession
from .user_config import UserConfig
from .persistence import SessionPersistence

class SessionManager:
    """会话管理器"""
    
    _instance: Optional['SessionManager'] = None
    
    def __init__(self, file_path: str = "data/sessions.json"):
        # 使用持久化管理器
        self._persistence = SessionPersistence(file_path)
        
        # 加载数据
        self._user_sessions: Dict[int, Dict[str, UserSession]] = {}
        self._user_configs: Dict[int, UserConfig] = {}
        self._load_data()
    
    def _load_data(self):
        """加载数据"""
        pass
    
    # 公共 API 保持不变
    def get_user_session(self, user_id: int) -> Optional[UserSession]:
        pass
    
    def create_user_session(self, user_id: int, title: Optional[str] = None) -> UserSession:
        pass
    
    # ... 其他方法
```

### Step 6: 更新 __init__.py

```python
from .session_manager import SessionManager
from .user_session import UserSession
from .user_config import UserConfig
from .persistence import SessionPersistence

__all__ = ['SessionManager', 'UserSession', 'UserConfig', 'SessionPersistence']
```

### Step 7: 更新导入

更新所有引用 session_manager 的文件:
```python
# 旧导入
from src.session.session_manager import SessionManager, UserSession, UserConfig

# 新导入 (向后兼容)
from src.session import SessionManager, UserSession, UserConfig
```

---

## 注意事项

### 必须保持不变

1. **SessionManager 的公共 API**
   - `get_session_manager()` 单例模式
   - 所有公共方法签名

2. **数据文件格式**
   - `data/sessions.json` 格式不变
   - 向后兼容旧数据

3. **UserSession 和 UserConfig 的属性**
   - 所有属性保持不变
   - `to_dict()` 和 `from_dict()` 行为不变

### 重构 load_from_file()

将 135 行的 `load_from_file()` 拆分为:
- `_load_sessions_from_data()` - 加载会话
- `_load_configs_from_data()` - 加载配置
- `_validate_data()` - 验证数据

---

## 验证方式

```bash
# 1. 检查语法
python -m py_compile src/session/session_manager.py
python -m py_compile src/session/user_session.py
python -m py_compile src/session/user_config.py
python -m py_compile src/session/persistence.py

# 2. 检查导入
python -c "from src.session import SessionManager, UserSession, UserConfig; print('OK')"

# 3. 运行测试
python tests/test_session_manager_basic.py

# 4. 验证数据兼容性
python -c "
from src.session import SessionManager
sm = SessionManager()
print(f'用户数: {len(sm._user_configs)}')
print(f'会话数: {sum(len(s) for s in sm._user_sessions.values())}')
"
```

---

## 禁止事项

1. 不要修改 `data/sessions.json` 文件格式
2. 不要修改 SessionManager 的公共方法签名
3. 不要删除任何 UserSession 或 UserConfig 的属性
4. 不要使用 Python 脚本修改代码
5. 不要使用 grep 工具 (用 bash 调用 rg)

---

## 完成标志

- [ ] user_session.py 创建完成
- [ ] user_config.py 创建完成
- [ ] persistence.py 创建完成
- [ ] session_manager.py 简化完成
- [ ] 导入更新完成
- [ ] 测试全部通过
- [ ] 数据兼容性验证通过
- [ ] Git 提交

---

## 如有疑问

向 Sisyphus (主协调器) 询问。