# Agent-Router 重构任务书

**负责文件:** `src/core/message_router.py` (731 行)
**目标:** 拆分为 2 个小模块
**优先级:** 中

---

## 任务目标

将 `message_router.py` (731 行) 拆分为职责单一的小模块。

---

## 输出文件结构

```
src/core/router/
    __init__.py              # 导出 MessageRouter
    message_router.py        # MessageRouter 核心类 (~400 行)
    message_processor.py     # 消息处理逻辑 (~300 行)
```

---

## 详细步骤

### Step 1: 创建目录结构

```bash
mkdir -p src/core/router
touch src/core/router/__init__.py
```

### Step 2: 分析 message_router.py

识别可提取的逻辑:
- 白名单检查
- 命令识别
- 文件处理 (_process_files_in_records - 124 行)
- 特殊消息处理 (合并转发等)

### Step 3: 创建 message_processor.py

提取消息处理逻辑:
```python
from typing import Dict, Any, Optional, List, Tuple

class MessageProcessor:
    """消息处理器"""
    
    def __init__(self, file_handler, message_queue_processor):
        self.file_handler = file_handler
        self.message_queue_processor = message_queue_processor
    
    async def process_files_in_records(self, records: List[Dict], group_id: int, user_id: int) -> Tuple[str, List[str]]:
        """处理消息记录中的文件 (重构后的 124 行函数)
        
        Returns:
            (消息文本, 下载的文件列表)
        """
        # 拆分为:
        # 1. _extract_file_info() - 提取文件信息
        # 2. _download_files() - 下载文件
        # 3. _build_result() - 构建结果
        
        file_infos = self._extract_file_info(records)
        downloaded = await self._download_files(file_infos, group_id, user_id)
        message_text = self._build_message_text(records)
        
        return message_text, downloaded
    
    def _extract_file_info(self, records: List[Dict]) -> List[Dict]:
        """提取文件信息"""
        pass
    
    async def _download_files(self, file_infos: List[Dict], group_id: int, user_id: int) -> List[str]:
        """下载文件"""
        pass
    
    def _build_message_text(self, records: List[Dict]) -> str:
        """构建消息文本"""
        pass
    
    async def process_forward_message(self, forward_id: str, group_id: int, user_id: int) -> Dict[str, Any]:
        """处理合并转发消息"""
        pass
    
    async def process_image_message(self, image_info: Dict) -> Optional[str]:
        """处理图片消息"""
        pass
```

### Step 4: 简化 message_router.py

```python
from typing import Dict, Any, Optional, Callable
from .message_processor import MessageProcessor

class MessageRouter:
    """消息路由器"""
    
    def __init__(
        self,
        file_handler,
        message_queue_processor,
        bot_qq_id: int,
        command_system,
        send_reply_callback: Callable,
        get_quoted_message_callback: Callable,
        opencode_available: bool = True
    ):
        self.file_handler = file_handler
        self.message_queue_processor = message_queue_processor
        self.bot_qq_id = bot_qq_id
        self.command_system = command_system
        self.send_reply = send_reply_callback
        self.get_quoted_message = get_quoted_message_callback
        self.opencode_available = opencode_available
        
        # 创建消息处理器
        self.processor = MessageProcessor(file_handler, message_queue_processor)
    
    async def route_message(self, message: Dict[str, Any]) -> bool:
        """路由消息
        
        Returns:
            是否处理了消息
        """
        post_type = message.get("post_type")
        
        if post_type == "message":
            return await self._handle_message(message)
        
        return False
    
    async def _handle_message(self, message: Dict[str, Any]) -> bool:
        """处理消息"""
        message_type = message.get("message_type")
        user_id = message.get("user_id")
        
        # 1. 白名单检查
        if not self._check_whitelist(user_id, message.get("group_id")):
            return False
        
        # 2. 提取消息内容
        message_text = self._extract_message_text(message)
        
        # 3. 命令识别
        if message_text.startswith('/'):
            return await self._handle_command(user_id, message_text, message)
        
        # 4. 普通消息转发
        return await self._forward_message(user_id, message_text, message)
    
    def _check_whitelist(self, user_id: int, group_id: Optional[int]) -> bool:
        """检查白名单"""
        pass
    
    def _extract_message_text(self, message: Dict) -> str:
        """提取消息文本"""
        pass
    
    async def _handle_command(self, user_id: int, message: str, raw_message: Dict) -> bool:
        """处理命令"""
        pass
    
    async def _forward_message(self, user_id: int, message: str, raw_message: Dict) -> bool:
        """转发消息"""
        pass
```

---

## 注意事项

### 必须保持不变

1. **MessageRouter 公共 API**
   - `route_message()` 签名不变
   - 构造函数参数不变

2. **消息路由逻辑**
   - 白名单检查行为不变
   - 命令识别逻辑不变

### 重构重点

1. **_process_files_in_records() (124 行)**
   - 拆分为 3 个子方法
   - 每个方法 < 50 行

---

## 验证方式

```bash
# 1. 检查语法
python -m py_compile src/core/router/message_router.py

# 2. 检查导入
python -c "from src.core.router import MessageRouter; print('OK')"

# 3. 运行测试
python tests/test_commands.py
```

---

## 完成标志

- [ ] 目录结构创建完成
- [ ] message_processor.py 创建完成
- [ ] message_router.py 简化完成
- [ ] 过长函数重构完成
- [ ] 测试通过
- [ ] Git 提交

---

## 如有疑问

向 Sisyphus (主协调器) 询问。