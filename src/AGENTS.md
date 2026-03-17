# 源代码模块

**生成时间：** 2026-03-16  
**核心职责：** OpenCode QQ 机器人的 Python 实现代码  
**模块风格：** 中文注释 + 英文代码，异步优先
**最近重构：** onebot_client.py 架构优化 (807行 → 305行)

## 模块结构

```
src/
├── core/              # 核心功能（27个模块）
│   ├── onebot_client.py      # 主机器人客户端（协调器，305行）
│   ├── client_initializer.py # 组件初始化器（310行）
│   ├── http_callbacks.py     # HTTP回调处理（464行）
│   ├── task_executor.py      # 任务执行逻辑（106行）
│   ├── lifecycle_manager.py  # 生命周期管理（196行）
│   ├── message_router.py     # 消息路由处理器
│   ├── opencode_integration.py  # OpenCode 集成层
│   ├── command_system.py     # 命令解析和执行
│   ├── connection_manager.py # WebSocket 连接管理
│   ├── http_server.py        # HTTP API 服务器
│   ├── file_handler.py       # 文件处理
│   └── ... (16个其他模块)
├── opencode/          # OpenCode 客户端集成（1个主文件）
│   └── opencode_client.py   # OpenCode HTTP 客户端
├── session/           # 会话管理（2个文件）
│   └── session_manager.py   # 会话持久化管理
├── utils/             # 工具函数和配置（3个文件）
│   ├── config.py      # 遗留配置模块
│   ├── config_loader.py  # YAML 配置加载器
│   └── error_handler.py   # 错误处理装饰器（170行）
└── commands/          # 命令处理（1个文件）
    └── __init__.py    # 命令模块初始化
```

## 模块职责

### core/ - 核心机器人功能
**架构模式**：协调器模式 + 依赖注入

**核心控制器（协调器）**：
- `onebot_client.py` - 主机器人客户端，协调所有组件（305行）
- `client_initializer.py` - 组件初始化逻辑，依赖注入（310行）
- `lifecycle_manager.py` - 热重载、重启、事件注册（196行）

**HTTP服务**：
- `http_server.py` - HTTP API 服务器，API端点（1197行）
- `http_callbacks.py` - 12个HTTP回调处理函数（464行）

**任务执行**：
- `task_executor.py` - 定时任务执行逻辑（106行）

**消息处理**：
- `message_router.py` - 处理所有收到的 QQ 消息，决定转发还是本地处理
- `command_system.py` - 解析和执行 `/` 开头的命令（12个命令）
- `file_handler.py` - 文件上传和下载，三层回退机制

**连接管理**：
- `connection_manager.py` - WebSocket 连接的生命周期管理
- `napcat_http_client.py` - NapCat HTTP API 客户端

**OpenCode 集成**：
- `opencode_integration.py` - 与 OpenCode 服务的桥接层
- `opencode_api.py` - OpenCode API 封装
- `opencode_initializer.py` - OpenCode 服务初始化

### utils/ - 工具函数
**错误处理**：
- `error_handler.py` - 错误处理装饰器，统一(result, error)元组模式

**配置管理**：
- `config.py` - 遗留配置模块（逐步迁移到 YAML）
- `config_loader.py` - 加载 `config.yaml` 文件

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
onebot_client.py (主入口/协调器)
    │
    ├── client_initializer.py (初始化器)
    │   ├── opencode_initializer.py
    │   └── 所有其他模块
    │
    ├── lifecycle_manager.py (生命周期)
    │   ├── restart_handler.py
    │   └── config_manager.py
    │
    ├── http_callbacks.py (HTTP回调)
    │   └── http_server.py
    │
    ├── task_executor.py (任务执行)
    │   ├── task_scheduler.py
    │   └── task_storage.py
    │
    ├── message_router.py (消息路由)
    │   ├── command_system.py (命令处理)
    │   └── opencode_integration.py (AI 集成)
    │       └── opencode_client.py (OpenCode 客户端)
    │
    ├── connection_manager.py (连接管理)
    │   ├── connection_lifecycle.py (状态机)
    │   └── napcat_http_client.py (HTTP API)
    │
    └── file_handler.py (文件处理)
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