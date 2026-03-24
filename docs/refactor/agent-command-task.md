# Agent-Command 重构任务书

**负责文件:** `src/core/command_system.py` (1007 行)
**目标:** 拆分为 4-5 个小模块，每个模块 < 400 行
**优先级:** 高

---

## 任务目标

将 `command_system.py` (1007 行) 拆分为职责单一的小模块，并重构过长函数。

---

## 输入文件

`src/core/command_system.py` - 当前结构:
- CommandSystem 类
- 12 个命令处理器
- `handle_command_command()` (217 行) - 最长函数

---

## 支持的命令

| 命令 | 功能 | 处理方法 |
|------|------|----------|
| /help | 显示帮助 | _handle_help() |
| /new | 创建新会话 | _handle_new_session() |
| /session | 切换会话 | _handle_session_command() |
| /agents | 列出智能体 | _handle_list_agents() |
| /model | 切换模型 | _handle_model_command() |
| /stop | 停止会话 | _handle_stop_session() |
| /undo | 撤销消息 | _handle_undo_message() |
| /redo | 恢复消息 | _handle_redo_message() |
| /reload | 重载配置 | _handle_reload_config() |
| /command | 执行命令 | _handle_command_command() |
| /compact | 压缩上下文 | _handle_compact() |
| /directory | 切换目录 | _handle_directory() |

---

## 输出文件结构

```
src/core/command/
    __init__.py              # 导出 CommandSystem
    command_system.py        # CommandSystem 核心类 (~200 行)
    help_handler.py          # /help 命令 (~50 行)
    session_handler.py       # 会话相关命令 (~200 行)
    model_handler.py         # 模型/智能体命令 (~150 行)
    task_handler.py          # /command, /directory (~200 行)
    message_handler.py       # /undo, /redo, /compact (~150 行)
    utils.py                 # 命令工具函数 (~100 行)
```

---

## 详细步骤

### Step 1: 创建目录结构

```bash
mkdir -p src/core/command
touch src/core/command/__init__.py
```

### Step 2: 创建 utils.py

提取命令工具函数:
```python
def parse_command(message: str) -> tuple:
    """解析命令字符串"""
    pass

def format_help_text() -> str:
    """格式化帮助文本"""
    pass

def validate_session_id(session_id: str) -> bool:
    """验证会话 ID 格式"""
    pass
```

### Step 3: 创建 help_handler.py

提取 /help 命令:
```python
class HelpHandler:
    """帮助命令处理器"""
    
    @staticmethod
    def get_help_text() -> str:
        """获取帮助文本"""
        return """可用命令:
/help - 显示帮助
/new - 创建新会话
...
"""
```

### Step 4: 创建 session_handler.py

提取会话相关命令:
- `_handle_new_session()`
- `_handle_session_command()` (147 行 -> 拆分)
- `_handle_stop_session()`

**_handle_session_command() 重构:**
```python
async def handle_session_command(self, user_id: int, args: str):
    # 1. 解析参数
    session_id = self._parse_session_id(args)
    
    # 2. 切换会话
    result = await self._switch_to_session(user_id, session_id)
    
    # 3. 发送响应
    await self._send_switch_response(user_id, result)
```

### Step 5: 创建 model_handler.py

提取模型/智能体命令:
- `_handle_list_agents()`
- `_handle_model_command()` (118 行 -> 拆分)

**_handle_model_command() 重构:**
```python
async def handle_model_command(self, user_id: int, args: str):
    if not args:
        # 列出可用模型
        return await self._list_models(user_id)
    
    # 切换模型
    return await self._switch_model(user_id, args)
```

### Step 6: 创建 task_handler.py

提取任务相关命令:
- `_handle_command_command()` (217 行 -> 拆分为 4 个函数)
- `_handle_directory()`

**_handle_command_command() 重构:**
```python
async def handle_command_command(self, user_id: int, args: str):
    # 1. 验证命令
    if not self._validate_opencode_command(args):
        return await self._send_invalid_command_response(user_id)
    
    # 2. 获取会话
    session_id = self._get_user_session_id(user_id)
    
    # 3. 执行命令
    result = await self._execute_opencode_command(session_id, args)
    
    # 4. 发送响应
    await self._send_command_response(user_id, result)
```

### Step 7: 创建 message_handler.py

提取消息操作命令:
- `_handle_undo_message()`
- `_handle_redo_message()`
- `_handle_compact()`

### Step 8: 重构 command_system.py

简化为核心类:
```python
from .help_handler import HelpHandler
from .session_handler import SessionHandler
from .model_handler import ModelHandler
from .task_handler import TaskHandler
from .message_handler import MessageHandler

class CommandSystem:
    """命令系统"""
    
    def __init__(self, session_manager, opencode_client, ...):
        # 初始化各处理器
        self.help = HelpHandler()
        self.session = SessionHandler(session_manager, opencode_client)
        self.model = ModelHandler(opencode_client)
        self.task = TaskHandler(opencode_client)
        self.message = MessageHandler(opencode_client)
    
    async def execute_command(self, message: str, user_id: int):
        """执行命令"""
        command, args = self._parse_command(message)
        
        handlers = {
            '/help': self.help.handle_help,
            '/new': self.session.handle_new_session,
            '/session': self.session.handle_session_command,
            '/model': self.model.handle_model_command,
            '/agents': self.model.handle_list_agents,
            '/stop': self.session.handle_stop_session,
            '/undo': self.message.handle_undo,
            '/redo': self.message.handle_redo,
            '/compact': self.message.handle_compact,
            '/reload': self._handle_reload_config,
            '/command': self.task.handle_command_command,
            '/directory': self.task.handle_directory,
        }
        
        handler = handlers.get(command)
        if handler:
            return await handler(user_id, args)
        return False
```

---

## 注意事项

### 必须保持不变

1. **12 个命令功能**
   - 命令名称不变
   - 命令行为不变

2. **CommandSystem 公共 API**
   - `execute_command()` 方法签名不变
   - 构造函数参数不变

3. **错误响应格式**
   - 错误消息格式统一

### 重构重点

1. **_handle_command_command() (217 行)**
   - 必须拆分为至少 4 个子函数
   - 每个子函数 < 60 行

2. **_handle_session_command() (147 行)**
   - 拆分为 3 个子函数

3. **_handle_model_command() (118 行)**
   - 拆分为 2 个子函数

---

## 验证方式

```bash
# 1. 检查语法
python -m py_compile src/core/command/command_system.py

# 2. 检查导入
python -c "from src.core.command import CommandSystem; print('OK')"

# 3. 运行命令测试
python tests/test_commands.py
```

---

## 禁止事项

1. 不要修改命令名称和行为
2. 不要修改公共 API
3. 不要删除错误处理逻辑
4. 不要使用 Python 脚本修改代码
5. 不要使用 grep 工具 (用 bash 调用 rg)

---

## 完成标志

- [ ] 目录结构创建完成
- [ ] 所有处理器文件创建完成
- [ ] 过长函数重构完成
- [ ] command_system.py 简化完成
- [ ] 导入更新完成
- [ ] 测试全部通过
- [ ] Git 提交

---

## 如有疑问

向 Sisyphus (主协调器) 询问。