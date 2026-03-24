# OpenCode QQ 机器人 - 开发规范

**项目状态：** 生产就绪
**核心栈：** Python 3.8+, aiohttp, OneBot V11, OpenCode AI
**更新时间：** 2026-03-24

## 项目概述

OpenCode QQ 机器人基于 OneBot V11 协议和 NapCat 框架，实现 QQ 消息与 OpenCode AI 平台的无缝集成。

**核心功能：**

- **白名单消息转发**：将白名单内的 QQ 消息转发到 OpenCode AI
- **完整命令系统**：12个命令（会话管理、模型切换、消息撤销等）
- **会话持久化**：重启自动恢复用户会话，无超时清理机制
- **白名单过滤**：精确控制哪些用户和群组可以交互
- **合并转发消息处理**：解析合并转发消息中的文本、图片、文件
- **定时任务调度**：支持延时和周期性任务

## 开发命令

### 安装和依赖

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 依赖列表
# aiohttp>=3.9.0      # 异步 HTTP/WebSocket 客户端
# PyYAML>=6.0         # YAML 配置解析
# requests>=2.31.0    # HTTP 请求库
```

### 启动命令

```bash
# 推荐方式：使用启动脚本（检查依赖+服务状态）
python scripts/run_bot.py

# 直接启动机器人
python src/core/onebot_client.py

# Windows 启动
start_en.bat          # 启动脚本
restart_bot.bat       # 重启脚本（含语法检查）
```

### 测试命令

```bash
# 运行所有核心命令测试（10个命令）
python tests/test_commands.py

# 测试连接功能
python tests/test_connection.py

# 使用调试接口（不连接真实QQ）
python tests/debug_interface.py

# 运行特定测试
python tests/test_http_api.py        # HTTP API 集成测试
python tests/test_session_manager_basic.py  # 会话管理器测试
```

### 开发调试

```python
# 使用 DebugInterface 类进行集成测试
from debug_interface import DebugInterface

debug = DebugInterface()
await debug.initialize()
await debug.send_private_message(123456789, "/help")
await debug.close()
```

## 代码风格规范

### 命名约定

- **类名**：`PascalCase` (`OneBotClient`, `CommandSystem`)
- **函数名**：`snake_case` (`handle_private_message`, `send_reply`)
- **变量名**：`snake_case` (`user_id`, `session_manager`)
- **常量**：`UPPER_SNAKE_CASE` (`WS_URL`, `OPENCODE_TIMEOUT`)
- **私有成员**：`_leading_underscore` (`_internal_method`, `_private_var`)
- **模块名**：`snake_case` (`message_router.py`, `config_loader.py`)

### 导入约定

```python
# 标准库导入优先
import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any

# 第三方库导入
import aiohttp
import yaml

# 本地模块导入（使用绝对导入）
from src.utils import config
from src.core.command_system import CommandSystem

# 模块内导入（使用相对导入）
from .cq_code_parser import parse_cq_code
from ..opencode.opencode_client import OpenCodeClient
```

### 类型提示

```python
# 广泛使用 typing 模块
from typing import Dict, List, Optional, Any, Callable, Tuple, Set

# 函数类型注解
async def process_message(self, message: str, user_id: int) -> bool:
    """处理消息"""
    pass

# 变量类型注解
user_sessions: Dict[int, UserSession] = {}
config_loader: Optional[ConfigLoader] = None

# 使用 Optional 表示可能为 None
def get_user_session(user_id: int) -> Optional[UserSession]:
    pass
```

### 异步编程模式

```python
# 所有网络操作使用 async/await
async def _handle_websocket_message(self, message: dict) -> None:
    """处理 WebSocket 消息"""
    try:
        await self.message_router.route_message(message)
    except Exception as e:
        logger.error(f"处理消息失败: {e}")

# 异步方法命名不加特殊前缀
async def send_reply(self, user_id: int, message: str) -> bool:
    pass

# 主入口使用 asyncio.run()
if __name__ == "__main__":
    asyncio.run(main())
```

### 错误处理

```python
# 标准错误处理模式
try:
    result = await self.perform_operation()
    if not result:
        logger.warning("操作返回 False")
        return False
except ConnectionError as e:
    logger.error(f"连接错误: {e}")
    await self.send_reply(user_id, "网络连接失败")
    return False
except Exception as e:
    logger.exception(f"未知错误: {e}")
    await self.send_reply(user_id, f"处理失败：{str(e)}")
    return False
```

### 日志记录

```python
# 每个模块创建自己的 logger
logger = logging.getLogger(__name__)

# 分级记录
logger.debug(f"处理消息: {message[:50]}...")  # 调试信息
logger.info(f"用户 {user_id} 发送了消息")      # 普通信息
logger.warning(f"配置项 {key} 未找到")         # 警告信息
logger.error(f"API 调用失败: {response.status}") # 错误信息

# 异常时记录完整堆栈
try:
    risky_operation()
except Exception:
    logger.exception("操作失败")
```

### 注释规范

```python
# 中文单行注释
async def process_message(self, message: str) -> bool:
    """
    处理收到的 QQ 消息
  
    Args:
        message: 原始消息内容，可能包含 CQ 码
        user_id: QQ 用户 ID
      
    Returns:
        bool: 是否处理成功，True 表示已处理不需要转发到 OpenCode
      
    Raises:
        ConnectionError: 网络连接失败时抛出
        ValueError: 消息格式错误时抛出
    """
    # 具体实现...
    return True
```

## 项目结构

```
mybot-web/
├── src/                    # Python 源代码（38个模块）
│   ├── core/              # 核心功能（27个模块）
│   │   ├── onebot_client.py      # 主机器人客户端（协调器，318行）
│   │   ├── http_server.py        # HTTP API 服务器（2242行，最大模块）
│   │   ├── command_system.py     # 命令解析和执行（1007行，12个命令）
│   │   ├── file_handler.py       # 文件处理（932行，三层回退）
│   │   ├── message_router.py     # 消息路由处理器（730行）
│   │   ├── http_callbacks.py     # HTTP回调处理（679行，12个回调）
│   │   ├── opencode_integration.py # OpenCode 集成层（550行）
│   │   ├── connection_manager.py # WebSocket 连接管理（532行）
│   │   ├── client_initializer.py # 组件初始化器（310行）
│   │   ├── task_scheduler.py     # 定时任务调度（306行）
│   │   └── ... (16个其他模块)
│   ├── opencode/          # OpenCode 客户端集成
│   │   └── opencode_client.py   # OpenCode HTTP 客户端（1102行）
│   ├── session/           # 会话管理
│   │   └── session_manager.py   # 会话持久化管理（1311行）
│   └── utils/             # 工具函数和配置
│       ├── config_loader.py  # YAML 配置加载器（356行）
│       ├── config.py      # 遗留配置模块（向后兼容，170行）
│       └── error_handler.py   # 错误处理装饰器（170行）
├── scripts/               # 启动脚本
│   └── run_bot.py        # 推荐入口点（297行，OpenCode监控+服务检查）
├── tests/                 # 测试脚本（17个文件）
│   ├── test_commands.py  # 自动化命令测试（10个命令）
│   ├── debug_interface.py # 调试接口类
│   ├── test_connection.py # WebSocket 连接测试
│   └── ... (14个其他测试)
├── data/                  # 数据存储
│   ├── sessions.json     # 会话数据文件（永久保存）
│   └── tasks.json        # 定时任务数据
├── docs/                  # 文档和测试数据（30个文件）
├── logs/                  # 运行日志
├── downloads/             # 文件下载目录
├── web/                   # Web 界面（1个HTML文件）
├── config.yaml           # 主配置文件（YAML，170行）
├── requirements.txt      # Python 依赖（4个包）
├── start_en.bat          # Windows 启动脚本
├── restart_bot.bat       # Windows 重启脚本（含语法检查）
└── README.md             # 完整项目文档
```

## 配置系统

### 配置文件

- **主配置**：`config.yaml` (YAML 格式，170行)
- **兼容层**：`src/utils/config.py` (导出配置变量)
- **加载器**：`src/utils/config_loader.py` (YAML 解析)

### 核心配置项

```yaml
# WebSocket 配置（NapCat）
websocket:
  url: "ws://localhost:3002"
  access_token: "CqC5dDMXWGUu6NVh"

# HTTP API 配置（引用消息获取）
http_api:
  base_url: "http://localhost:3001"
  enabled: true  # 必须为 true 才能获取引用消息

# OpenCode 配置
opencode:
  host: "127.0.0.1"
  port: 4091
  default_agent: "Sisyphus (Ultraworker)"
  default_model: "alibaba-coding-plan-cn/qwen3.5-plus"

# 白名单配置
whitelist:
  qq_users: [123456789, 123456789, ...]
  groups: [123456789, 123456789, ...]

# 会话管理
session:
  storage_type: "file"
  file_path: "data/sessions.json"
  max_sessions_per_user: 100
```

## 服务依赖

**运行时必须的服务**:

- NapCat WebSocket: `ws://localhost:3002`
- NapCat HTTP API: `http://localhost:3001` (用于引用消息获取)
- OpenCode 服务: `http://127.0.0.1:4091`

## 架构模式

**协调器模式 (Coordinator Pattern)**:

```
onebot_client.py (协调器)
    ├── ClientInitializer (初始化器)
    ├── LifecycleManager (生命周期)
    ├── HTTPServer (HTTP服务器)
    ├── MessageRouter (消息路由)
    │   ├── CommandSystem (命令处理)
    │   └── OpenCodeIntegration (AI集成)
    ├── ConnectionManager (连接管理)
    └── FileHandler (文件处理)
```

**依赖注入**: `ClientInitializer` 负责所有组件的初始化和依赖注入

## 开发指南

### 添加新命令

1. 在 `src/core/command_system.py` 中添加命令处理逻辑
2. 在 `src/core/onebot_client.py` 的 `_handle_private_message` 中注册命令
3. 在 `tests/test_commands.py` 中添加测试
4. 在文档中更新命令列表

### 添加新功能模块

1. 在 `src/core/` 下创建新模块
2. 遵循命名约定和代码风格
3. 在 `src/core/onebot_client.py` 中初始化模块
4. 添加必要的错误处理和日志记录

### 修改配置

1. 在 `config.yaml` 中添加新配置项
2. 在 `src/utils/config_loader.py` 中加载配置
3. 在 `src/utils/config.py` 中导出变量（保持兼容性）
4. 在代码中使用 `from src.utils import config` 导入配置

### 调试流程

1. **检查日志**: `logs/onebot_client.log`
2. **运行测试**: `python tests/test_commands.py`
3. **使用调试接口**: `python tests/debug_interface.py`
4. **验证服务状态**: 确保 NapCat 和 OpenCode 服务运行

## 故障排除

### 常见问题

1. **连接失败**: 检查 NapCat 是否运行在 `ws://localhost:3002`
2. **消息不转发**: 验证用户是否在白名单中 (`config.yaml`)
3. **会话丢失**: 检查 `data/sessions.json` 文件权限
4. **引用消息超时**: 确保 `http_api.enabled: true`

### 错误码

- **1006514**: NapCat 的 QQ 被腾讯踢下线，需重新登录 QQ 并重启 NapCat
- **连接拒绝**: NapCat 服务未启动或端口被占用
- **认证失败**: Access Token 不正确

## 合并转发消息处理

### 功能概述

机器人支持解析合并转发消息，提取其中的文本、图片和文件信息。

### 处理流程

```
收到合并转发消息
    ↓
get_forward_msg HTTP API 获取消息列表
    ↓
解析每条消息:
  - text → 直接显示
  - image → 使用 URL 下载图片
  - file → 提示用户单独发送
    ↓
构建消息摘要 + 下载路径
```

### API 依赖

- **HTTP API**: `http://localhost:3001` - 优先使用

### 文件下载限制

合并转发消息中的文件无法通过 `get_file` API 下载：

- **原因**: NapCat 的 `downloadRichMedia` 内部超时，file_id 格式不匹配 NapCat UUID
- **解决方案**: 提示用户单独发送文件

### 相关测试

```bash
python tests/test_get_forward_msg.py  # 合并转发消息解析测试
```

---

**相关文档**:

- [README.md](./README.md) - 完整项目文档
- [src/AGENTS.md](./src/AGENTS.md) - 源代码模块详细说明
- [tests/AGENTS.md](./tests/AGENTS.md) - 测试架构文档
- [src/core/AGENTS.md](./src/core/AGENTS.md) - 核心功能模块文档
