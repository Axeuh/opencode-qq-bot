# 源代码模块

**生成时间：** 2026-03-12  
**核心职责：** OpenCode QQ 机器人的 Python 实现代码  
**模块风格：** 中文注释 + 英文代码，异步优先

## 模块结构

```
src/
├── core/              # 核心功能（23个文件）
│   ├── onebot_client.py      # 主机器人客户端
│   ├── message_router.py     # 消息路由处理器
│   ├── opencode_integration.py  # OpenCode 集成层
│   ├── command_system.py     # 命令解析和执行
│   ├── connection_manager.py # WebSocket 连接管理
│   ├── session_ui_manager.py # 会话界面管理
│   ├── napcat_http_client.py # NapCat HTTP API 客户端
│   ├── restart_handler.py    # 热重启处理器
│   └── ... (15+ 其他核心模块)
├── opencode/          # OpenCode 客户端集成（1个主文件）
│   └── opencode_client.py   # OpenCode HTTP 客户端
├── session/           # 会话管理（2个文件）
│   └── session_manager.py   # 会话持久化管理
├── utils/             # 工具函数和配置（3个文件）
│   ├── config.py      # 遗留配置模块
│   └── config_loader.py  # YAML 配置加载器
└── commands/          # 命令处理（1个文件）
    └── __init__.py    # 命令模块初始化
```

## 模块职责

### core/ - 核心机器人功能
**核心文件**：
- `onebot_client.py` - 机器人主类，继承自 `OneBotV11Client`
- `message_router.py` - 处理所有收到的 QQ 消息，决定转发还是本地处理
- `opencode_integration.py` - 与 OpenCode 服务的桥接层
- `command_system.py` - 解析和执行 `/` 开头的命令
- `connection_manager.py` - WebSocket 连接的生命周期管理
- `session_ui_manager.py` - 管理用户的会话状态和 UI 交互

**辅助文件**：
- `napcat_http_client.py` - NapCat HTTP API 客户端（用于获取引用消息）
- `restart_handler.py` - 处理 `/reload restart` 命令，实现热重启
- `file_handler.py` - 处理文件上传和下载
- `cq_code_parser.py` - 解析 CQ 码（QQ 消息格式）

### opencode/ - OpenCode 客户端
**关键 API**：
```python
# opencode_client.py 提供以下核心方法：
- abort_session(session_id)     # 中止会话（/stop 命令）
- revert_last_message(session_id) # 撤销消息（/undo 命令）  
- unrevert_messages(session_id)   # 恢复消息（/redo 命令）
```

**集成模式**：
- 使用 HTTP 客户端与本地 OpenCode 服务通信
- 默认地址：`http://127.0.0.1:4091`
- 支持完整的 OpenCode 会话管理功能

### session/ - 会话管理
**主要功能**：
- 会话持久化：自动保存到 `data/sessions.json`

- 会话数据格式：
  ```json
  {
    "user_id": "123456789",
    "session_id": "ses_abc123",
    "created_at": "2026-03-10T14:30:00",
    "last_accessed": "2026-03-12T09:15:00"
  }
  ```

### utils/ - 工具函数
**配置管理**：
- `config.py` - 遗留配置模块（逐步迁移到 YAML）
- `config_loader.py` - 加载 `config.yaml` 文件

**迁移状态**：
- ✅ 主要配置已迁移到 `config.yaml`
- ⚠️ 部分代码仍引用 `src.utils.config`
- 📅 建议逐步迁移遗留引用

## 代码规范

### 命名约定
- **类名**：`PascalCase` (如 `OneBotClient`)
- **函数名**：`snake_case` (如 `handle_private_message`)
- **常量**：`UPPER_SNAKE_CASE` (如 `DEFAULT_TIMEOUT`)
- **私有成员**：`_leading_underscore` (如 `_internal_method`)

### 注释风格
```python
# 中文单行注释
async def process_message(self, message: str) -> bool:
    """
    处理收到的 QQ 消息
    
    Args:
        message: 原始消息内容
        
    Returns:
        bool: 是否处理成功
    """
    # 具体实现...
```

### 异步模式
所有网络操作使用 `async/await`：
```python
async def _handle_websocket_message(self, message: dict):
    """处理 WebSocket 消息"""
    try:
        await self.message_router.route_message(message)
    except Exception as e:
        logger.error(f"处理消息失败: {e}")
```

## 模块间依赖关系

```
onebot_client.py (主入口)
    │
    ├── message_router.py (消息路由)
    │   ├── command_system.py (命令处理)
    │   └── opencode_integration.py (AI 集成)
    │       └── opencode_client.py (OpenCode 客户端)
    │
    ├── connection_manager.py (连接管理)
    │   └── napcat_http_client.py (HTTP API)
    │
    ├── session_ui_manager.py (会话管理)
    │   └── session_manager.py (持久化)
    │
    └── restart_handler.py (热重启)
```

## 开发指南

### 添加新功能
1. **新命令**：在 `command_system.py` 中添加处理逻辑
2. **新消息类型**：在 `message_router.py` 中添加路由规则
3. **新 OpenCode API**：在 `opencode_client.py` 中添加方法
4. **新配置项**：在 `config.yaml` 中添加，通过 `config_loader.py` 加载

### 调试技巧
```python
# 在 core 模块中启用详细日志
logger = logging.getLogger(__name__)
logger.debug(f"处理消息: {message}")
```

### 测试集成
所有模块都可通过 `debug_interface.py` 进行集成测试：
```python
from debug_interface import DebugInterface

debug = DebugInterface()
await debug.initialize()
# 测试特定模块功能
```

---

**子模块详情：**
- [core/AGENTS.md](./core/AGENTS.md) - 核心功能模块详细文档
