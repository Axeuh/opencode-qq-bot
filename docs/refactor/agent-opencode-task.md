# Agent-OpenCode 重构任务书

**负责文件:** 
- `src/opencode/opencode_client.py` (1102 行)
- `src/core/opencode_integration.py` (550 行)

**目标:** 拆分为职责单一的小模块
**优先级:** 高

---

## 任务目标

将 OpenCode 相关的两个大文件拆分为小模块，提高可维护性。

---

## 输出文件结构

```
src/opencode/
    __init__.py              # 导出 OpenCodeClient
    client.py                # OpenCodeClient 核心类 (~300 行)
    session_api.py           # 会话相关 API (~200 行)
    message_api.py           # 消息相关 API (~200 行)
    model_api.py             # 模型/智能体 API (~150 行)
    types.py                 # 类型定义 (~100 行)

src/core/
    opencode_integration.py  # 简化后的集成层 (~200 行)
    opencode_forwarder.py    # 消息转发逻辑 (~200 行)
```

---

## 详细步骤

### Step 1: 分析 opencode_client.py

识别 OpenCodeClient 的方法分类:
- 会话管理: create_session, abort_session, revert_last_message, unrevert_messages
- 消息处理: send_message, prompt_async
- 模型/智能体: get_models, get_agents, switch_model, switch_agent
- 基础: _request, _get_headers

### Step 2: 创建 types.py

提取类型定义:
```python
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

@dataclass
class SessionInfo:
    session_id: str
    created_at: str
    model: Optional[str] = None
    agent: Optional[str] = None

@dataclass  
class MessageResult:
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
```

### Step 3: 创建 client.py

提取核心客户端类:
```python
import aiohttp
from typing import Optional, Dict, Any

class OpenCodeClient:
    """OpenCode HTTP 客户端"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:4091"):
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取 HTTP 会话"""
        pass
    
    async def close(self):
        """关闭客户端"""
        pass
    
    async def _request(self, method: str, path: str, **kwargs):
        """发送请求"""
        pass
```

### Step 4: 创建 session_api.py

提取会话 API:
```python
from .client import OpenCodeClient
from .types import SessionInfo

class SessionAPI:
    """会话 API"""
    
    def __init__(self, client: OpenCodeClient):
        self._client = client
    
    async def create_session(self, title: Optional[str] = None) -> SessionInfo:
        """创建会话"""
        pass
    
    async def abort_session(self, session_id: str) -> bool:
        """中止会话"""
        pass
    
    async def revert_last_message(self, session_id: str) -> bool:
        """撤销最后一条消息"""
        pass
    
    async def unrevert_messages(self, session_id: str) -> bool:
        """恢复撤销的消息"""
        pass
```

### Step 5: 创建 message_api.py

提取消息 API:
```python
class MessageAPI:
    """消息 API"""
    
    def __init__(self, client: OpenCodeClient):
        self._client = client
    
    async def send_message(self, session_id: str, message: str) -> str:
        """发送消息"""
        pass
    
    async def prompt_async(self, session_id: str, message: str, **kwargs):
        """异步提示"""
        pass
```

### Step 6: 创建 model_api.py

提取模型/智能体 API:
```python
class ModelAPI:
    """模型/智能体 API"""
    
    def __init__(self, client: OpenCodeClient):
        self._client = client
    
    async def get_models(self) -> List[str]:
        """获取模型列表"""
        pass
    
    async def get_agents(self) -> List[str]:
        """获取智能体列表"""
        pass
    
    async def switch_model(self, session_id: str, model: str) -> bool:
        """切换模型"""
        pass
    
    async def switch_agent(self, session_id: str, agent: str) -> bool:
        """切换智能体"""
        pass
```

### Step 7: 重构 opencode_client.py

将原文件改为组合模式:
```python
from .client import OpenCodeClient as _BaseClient
from .session_api import SessionAPI
from .message_api import MessageAPI
from .model_api import ModelAPI

class OpenCodeClient(_BaseClient):
    """OpenCode 客户端 (组合模式)"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:4091"):
        super().__init__(base_url)
        
        # 组合 API
        self.session = SessionAPI(self)
        self.message = MessageAPI(self)
        self.model = ModelAPI(self)
    
    # 向后兼容: 代理方法
    async def create_session(self, *args, **kwargs):
        return await self.session.create_session(*args, **kwargs)
    
    async def send_message(self, *args, **kwargs):
        return await self.message.send_message(*args, **kwargs)
    
    # ... 其他代理方法
```

### Step 8: 拆分 opencode_integration.py

提取 forward_to_opencode() 到 opencode_forwarder.py:
```python
class OpenCodeForwarder:
    """OpenCode 消息转发器"""
    
    def __init__(self, client, session_manager):
        self._client = client
        self._session_manager = session_manager
    
    async def forward_to_opencode(self, user_id: int, message: str, ...):
        """转发消息到 OpenCode"""
        # 原来的 196 行函数拆分为:
        # 1. _prepare_forward() - 准备转发
        # 2. _get_or_create_session() - 获取/创建会话
        # 3. _send_to_opencode() - 发送消息
        # 4. _handle_response() - 处理响应
        pass
```

---

## 注意事项

### 必须保持不变

1. **OpenCodeClient 公共 API**
   - 所有公共方法签名不变
   - 返回值类型不变

2. **异步行为**
   - 所有异步方法保持 async

3. **错误处理**
   - 异常类型不变

### 重构重点

1. **forward_to_opencode() (196 行)**
   - 必须拆分为 4 个子函数
   - 每个子函数 < 60 行

---

## 验证方式

```bash
# 1. 检查语法
python -m py_compile src/opencode/client.py

# 2. 检查导入
python -c "from src.opencode import OpenCodeClient; print('OK')"

# 3. 测试 API 可用性
python -c "
from src.opencode import OpenCodeClient
client = OpenCodeClient()
print('Session API:', hasattr(client, 'create_session'))
print('Message API:', hasattr(client, 'send_message'))
"
```

---

## 完成标志

- [ ] types.py 创建完成
- [ ] client.py 创建完成
- [ ] session_api.py 创建完成
- [ ] message_api.py 创建完成
- [ ] model_api.py 创建完成
- [ ] opencode_client.py 重构完成
- [ ] opencode_forwarder.py 创建完成
- [ ] opencode_integration.py 简化完成
- [ ] 测试通过
- [ ] Git 提交

---

## 如有疑问

向 Sisyphus (主协调器) 询问。