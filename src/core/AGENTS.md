# 核心功能模块

**生成时间：** 2026-03-13  
**模块数量：** 23 个 Python 文件  
**架构风格：** 职责分离，异步优先，中文注释

## 模块分类

### 🎯 核心控制器 (4个文件)
| 模块 | 职责 | 关键方法 |
|------|------|----------|
| `onebot_client.py` | 机器人主类，继承自 `OneBotV11Client` | `main()`, `run()`, `_handle_message()` |
| `message_router.py` | 消息路由决策器 | `route_message()`, `_process_private_message()` |
| `command_system.py` | 命令解析和执行 | `execute_command()`, `_parse_command()` |
| `opencode_integration.py` | OpenCode 服务桥接层 | `send_to_opencode()`, `get_opencode_response()` |

### 🔗 连接管理 (3个文件)
| 模块 | 职责 | 关键方法 |
|------|------|----------|
| `connection_manager.py` | WebSocket 连接生命周期 | `connect()`, `reconnect()`, `close()` |
| `connection_lifecycle.py` | 连接状态机和事件处理 | `on_connect()`, `on_disconnect()` |
| `napcat_http_client.py` | NapCat HTTP API 客户端 | `get_message()`, `get_file()`, `get_forward_msg()` |

### 💬 消息处理 (5个文件)
| 模块 | 职责 | 关键方法 |
|------|------|----------|
| `message_utils.py` | 消息工具函数 | `check_whitelist()`, `format_message()` |
| `cq_code_parser.py` | CQ 码解析器 | `parse_cq_code()`, `extract_file_info()` |
| `message_queue.py` | 消息队列处理器 | `process_queue()`, `add_to_queue()` |
| `api_sender.py` | API 消息发送器 | `send_private_message()`, `send_group_message()` |
| `file_handler.py` | 文件上传下载处理 | `download_file()`, `_download_forward_files()` |

### 🔧 系统功能 (5个文件)
| 模块 | 职责 | 关键方法 |
|------|------|----------|
| `restart_handler.py` | 热重启处理器 | `restart_application()`, `_create_restart_script()` |
| `config_manager.py` | 配置管理 | `setup_logging()`, `load_config()` |
| `time_utils.py` | 时间工具函数 | `get_cross_platform_time()` |
| `task_scheduler.py` | 定时任务调度器 | `schedule_task()`, `run_scheduled_tasks()` |
| `task_storage.py` | 任务持久化存储 | `save_task()`, `load_tasks()` |

### 🤖 OpenCode 集成 (3个文件)
| 模块 | 职责 | 关键方法 |
|------|------|----------|
| `opencode_api.py` | OpenCode API 封装 | `create_session()`, `send_message()` |
| `opencode_initializer.py` | OpenCode 服务初始化 | `initialize_opencode()`, `check_opencode_status()` |
| `event_handlers.py` | OpenCode 事件处理器 | `handle_opencode_event()` |

### 🖥️ UI/会话管理 (3个文件)
| 模块 | 职责 | 关键方法 |
|------|------|----------|
| `session_ui_manager.py` | 用户会话界面管理 | `get_user_session()`, `update_session_ui()` |
| `http_server.py` | HTTP 服务器（API端点） | `start_server()`, `handle_request()` |

## 核心类详解

### OneBotClient (`onebot_client.py`)
```python
class OneBotClient(OneBotV11Client):
    """QQ 机器人主客户端类"""
    
    def __init__(self):
        # 初始化所有管理器
        self.message_router = MessageRouter(self)
        self.connection_manager = ConnectionManager(self)
        self.command_system = CommandSystem(self)
        self.opencode_integration = OpenCodeIntegration(self)
        self.session_ui_manager = SessionUIManager(self)
        self.restart_handler = RestartHandler(self)
        
    async def _handle_message(self, message: dict):
        """处理收到的 QQ 消息"""
        return await self.message_router.route_message(message)
```

### MessageRouter (`message_router.py`)
**路由决策流程**：
1. 检查消息类型（私聊/群聊）
2. 验证白名单权限
3. 判断是否为命令（以 `/` 开头）
4. 命令 → `command_system.execute_command()`
5. 普通消息 → `opencode_integration.send_to_opencode()`

### CommandSystem (`command_system.py`)
**支持的命令**：
```python
COMMAND_HANDLERS = {
    '/help': '_handle_help',
    '/new': '_handle_new_session',
    '/session': '_handle_switch_session',
    '/agents': '_handle_list_agents',
    '/model': '_handle_switch_model',
    '/directory': '_handle_directory',
    '/command': '_handle_command',
    '/stop': '_handle_stop_session',
    '/undo': '_handle_undo_message',
    '/redo': '_handle_redo_message',
    '/compact': '_handle_compact',
    '/reload': '_handle_reload_config',
}
```

## 关键依赖关系

```
onebot_client.py (主入口)
    ├── message_router.py (消息路由)
    │   ├── command_system.py (命令处理)
    │   └── opencode_integration.py (AI集成)
    │       ├── opencode_api.py (API封装)
    │       └── opencode_initializer.py (服务初始化)
    │
    ├── connection_manager.py (连接管理)
    │   ├── connection_lifecycle.py (状态机)
    │   └── napcat_http_client.py (HTTP客户端)
    │
    ├── session_ui_manager.py (会话UI)
    │
    ├── restart_handler.py (热重启)
    │
    └── 其他辅助模块：
        ├── message_utils.py (消息工具)
        ├── cq_code_parser.py (CQ码解析)
        ├── file_handler.py (文件处理)
        ├── config_manager.py (配置管理)
        └── time_utils.py (时间工具)
```

## 模块协作示例

### 处理 `/new` 命令
```
用户发送 "/new"
    ↓
message_router.route_message() 识别为命令
    ↓
command_system.execute_command("/new")
    ↓
opencode_api.create_session() 创建新会话
    ↓
session_ui_manager.update_session_ui() 更新UI状态
    ↓
api_sender.send_private_message() 发送回复
```

### 处理普通消息
```
用户发送 "你好"
    ↓
message_router.route_message() 识别为普通消息
    ↓
opencode_integration.send_to_opencode() 转发到OpenCode
    ↓
opencode_api.send_message() 调用OpenCode API
    ↓
收到OpenCode回复后通过 qq-message-napcat 技能发送
```

## 配置和日志

### 日志配置 (`config_manager.py`)
```python
def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.LOG_FILE),
            logging.StreamHandler()
        ]
    )
```

### 配置加载 (`config_manager.py`)
```python
def load_config():
    """加载配置文件"""
    # 优先使用 config.yaml，回退到 config.py
    config_data = config_loader.load_yaml_config()
    if not config_data:
        config_data = config_loader.load_legacy_config()
    return config_data
```

## 错误处理模式

### 连接错误处理
```python
async def reconnect_with_backoff(self):
    """指数退避重连"""
    for attempt in range(MAX_RETRIES):
        try:
            await self.connection_manager.connect()
            return True
        except ConnectionError as e:
            delay = BASE_DELAY * (2 ** attempt)
            logger.warning(f"连接失败，{delay}秒后重试: {e}")
            await asyncio.sleep(delay)
    return False
```

### 命令错误处理
```python
async def safe_execute_command(self, command: str, user_id: int):
    """安全执行命令，捕获所有异常"""
    try:
        return await self.command_system.execute_command(command, user_id)
    except Exception as e:
        logger.error(f"执行命令失败: {command}, 错误: {e}")
        await self.api_sender.send_private_message(
            user_id, f"命令执行失败: {str(e)}"
        )
        return False
```

## 性能优化

### 消息队列处理 (`message_queue.py`)
- 使用异步队列避免消息丢失
- 批量处理减少API调用
- 优先级队列确保命令优先处理

### 连接池管理 (`connection_manager.py`)
- WebSocket 连接保持活动状态
- HTTP 连接池复用
- 心跳机制检测连接健康

## 扩展指南

### 添加新命令
1. 在 `command_system.py` 的 `COMMAND_HANDLERS` 中添加映射
2. 实现对应的 `_handle_xxx` 方法
3. 在 `message_router.py` 中确保命令被正确路由

### 添加新消息类型
1. 在 `message_router.py` 的 `route_message` 中添加分支
2. 实现对应的处理器模块
3. 更新 `cq_code_parser.py` 如果需要解析新的CQ码

### 添加新集成
1. 创建新的集成类（参考 `opencode_integration.py`）
2. 在 `onebot_client.py` 中初始化
3. 通过 `message_router.py` 或 `command_system.py` 调用

## 合并转发消息处理

### napcat_http_client.py 新增方法

```python
async def get_forward_msg(self, message_id: Union[int, str]) -> Optional[Dict[str, Any]]:
    """
    获取合并转发消息内容（HTTP API版本）
    
    Args:
        message_id: 合并转发消息ID
        
    Returns:
        消息数据字典，包含 messages 列表：
        {
            "messages": [
                {
                    "sender": {"nickname": "用户昵称"},
                    "message": [
                        {"type": "text", "data": {"text": "内容"}},
                        {"type": "image", "data": {"url": "...", "file": "..."}},
                        {"type": "file", "data": {"file_id": "...", "file": "..."}}
                    ]
                }
            ]
        }
    """
```

### file_handler.py 合并转发处理

**处理流程**：
1. 从消息中提取 `forward_id`
2. 调用 `get_forward_msg` API 获取消息列表
3. 遍历消息解析文本/图片/文件
4. 图片：使用 URL 下载到本地
5. 文件：提示用户单独发送（无法下载）

**关键方法**：
```python
async def _process_forward_message(self, file_info: dict, group_id: int, user_id: int) -> str:
    """处理合并转发消息"""
    forward_id = file_info.get("file_id", "")
    
    # 1. 获取消息列表
    forward_data = await self.http_client.get_forward_msg(forward_id)
    messages = forward_data.get("messages", [])
    
    # 2. 解析每条消息
    for msg in messages:
        sender = msg.get("sender", {})
        message = msg.get("message", [])
        
        for item in message:
            if item.get("type") == "text":
                # 文本直接显示
            elif item.get("type") == "image":
                # 图片通过 URL 下载
            elif item.get("type") == "file":
                # 文件提示用户单独发送
```

### 文件下载三层回退机制

**优先级**：
1. **HTTP API** (`http://localhost:3001`) - 优先使用，获取文件确切路径
2. **WebSocket API** (`ws://localhost:3002`) - 回退方案
3. **字符匹配** - 最终回退，从 NapCat 临时目录匹配文件名

**关键方法**：
```python
async def _get_file_info_via_api(self, file_id: str, group_id: int = None) -> Optional[Dict]:
    """通过 API 获取文件信息"""
    # 1. 尝试 HTTP API
    if self.http_client:
        result = await self.http_client.get_file(file_id, group_id)
        if result:
            return result
    
    # 2. 回退到 WebSocket API
    if self.api_callback:
        result = await self.api_callback("get_file", {"file_id": file_id})
        if result:
            return result
    
    return None

def _convert_wsl_path_to_windows(self, wsl_path: str) -> str:
    """将 WSL 路径转换为 Windows 网络共享路径"""
    # /root/.config/QQ/NapCat/temp/xxx
    # → \\172.27.213.195\wsl-root\root\.config\QQ\NapCat\temp\xxx
```

### 已知限制

**合并转发消息中的文件无法下载**：
- **原因**: NapCat 的 `downloadRichMedia` 内部超时，`file_id` 格式不匹配 NapCat UUID
- **错误日志**: `Timeout: NodeIKernelMsgService/downloadRichMedia`
- **解决方案**: 提示用户单独发送文件