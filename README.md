# OpenCode QQ 机器人部署指南

基于 OneBot V11 协议、NapCat 框架和 OpenCode AI 平台的高级 QQ 机器人，实现 QQ 消息与 OpenCode AI 的无缝集成。

## 项目概述

这是一个纯 Python 实现的 QQ 机器人，核心功能是将 QQ 消息转发到 OpenCode AI 平台进行处理，并提供完整的命令系统用于会话管理、智能体切换、消息撤销等高级操作。

**核心特性**：

- **消息转发**：将白名单内的 QQ 消息转发到 OpenCode AI 平台
- **AI 集成**：与 OpenCode Sisyphus、Prometheus 等智能体无缝协作
- **命令系统**：完整的命令集用于会话管理和机器人控制
- **会话持久化**：用户会话在程序重启后自动恢复
- **热重启**：支持`/reload restart`命令在同一终端内重启程序
- **白名单过滤**：精确控制哪些用户和群组可以交互

**设计原则**：

1. 机器人仅转发白名单内的消息到 OpenCode
2. OpenCode 代理自行回复（通过 qq-message-napcat 技能）
3. 命令直接在机器人本地处理，不转发到 OpenCode
4. 保持轻量级核心，通过配置扩展功能

## 项目结构（纯 Python）

```
mybot/
├── src/                    # Python 源代码
│   ├── core/              # 核心功能
│   │   └── onebot_client.py     # 主机器人客户端
│   ├── opencode/          # OpenCode 集成
│   │   └── opencode_client.py   # OpenCode HTTP 客户端
│   ├── session/           # 会话管理
│   │   └── session_manager.py   # 会话持久化管理
│   └── utils/             # 工具和配置
│       └── config.py      # 配置文件
├── scripts/               # 脚本工具
│   └── run_bot.py        # 启动脚本（推荐）
├── data/                  # 数据存储
│   └── sessions.json     # 会话数据文件
├── logs/                  # 日志目录
├── downloads/             # 文件下载目录
├── docs/                  # 文档
├── tests/                 # 测试文件
├── requirements.txt       # Python 依赖
├── PROJECT_STRUCTURE.md   # 详细项目结构文档
└── README.md             # 本文件
```

## 快速启动

### 前置要求

1. **Python 3.8+** 已安装
2. **OpenCode** 已安装并全局可用（命令行可执行 `opencode`）
3. **NapCat** 已配置并运行（需要 HTTP 和 WebSocket 两个服务器）
4. **配置文件** 已正确设置端口、Token 等参数

### 服务依赖

机器人需要以下服务同时运行：


| 服务             | 默认地址              | 用途                   |
| ---------------- | --------------------- | ---------------------- |
| OpenCode         | http://127.0.0.1:4091 | AI 智能体服务          |
| NapCat HTTP API  | http://localhost:3001 | 文件下载、引用消息获取 |
| NapCat WebSocket | ws://localhost:3002   | 消息收发               |

### 安装步骤

```bash
# 1. 克隆或下载项目到本地
cd D:\Users\Axeuh\Desktop\Axeuh_bot\mybot

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 配置 config.yaml
#    - 确保 WebSocket URL 和 Token 与 NapCat 配置一致
#    - 确保 HTTP API 地址和 Token 正确
#    - 确保 OpenCode 地址正确

# 4. 确保 OpenCode 全局可用
#    命令行执行 opencode 应能正常启动服务
```

### 启动机器人

**推荐方式：使用启动脚本**

```bash
# Windows
start_en.bat

# 或直接运行
D:\Users\Axeuh\Desktop\Axeuh_bot\mybot\start_en.bat
```

启动脚本会自动检查依赖和服务状态。

### NapCat 配置

**推荐使用 NapCat.Linux.Launcher（新式非入侵式启动器）**

不容易被腾讯踢下号

NapCat 需要配置两个服务器：

- **HTTP 服务器**：默认端口 3001，用于文件下载和 API 调用
- **WebSocket 服务器**：默认端口 3002，用于消息收发

**配置文件示例**（NapCat 的 napcat.json）：

```json
{
  "http": {
    "enable": true,
    "host": "0.0.0.0",
    "port": 3001,
    "secret": "fZvJ-zo_TzyAHOoI"
  },
  "ws": {
    "enable": true,
    "host": "0.0.0.0",
    "port": 3002,
    "accessToken": "CqC5dDMXWGUu6NVh"
  }
}
```

### WSL 环境配置（Windows + WSL 部署）

如果 bot 运行在 Windows，NapCat 部署在 WSL，需要配置 WSL 权限：

1. **启用 WSL 网络共享**：

   ```bash
   # 在 WSL 中运行
   sudo chmod -R 755 /root/.config/QQ/NapCat/temp
   ```
2. **Windows 访问 WSL 文件**：

   - 路径格式：`\\wsl.localhost\Ubuntu-22.04\root\.config\QQ\NapCat\temp`
   - 或使用 IP 访问：`\\172.27.213.195\wsl-root\root\.config\QQ\NapCat\temp`
3. **配置文件中的路径转换**：

   - WSL 路径自动转换为 Windows 网络共享路径
   - 确保 Windows 可以读取 WSL 文件系统

## 机器人功能

### 1. 基础功能

- **白名单过滤**：仅处理指定用户和群组的消息
- **自动重连**：网络断开时自动重连 NapCat 服务器
- **心跳机制**：定期发送心跳包保持连接
- **日志记录**：详细的运行日志，便于调试

### 2. 命令系统（核心功能）

机器人支持以下命令（所有命令以 `/` 开头）：


| 命令              | 功能               | 示例                                | 说明                                 |
| ----------------- | ------------------ | ----------------------------------- | ------------------------------------ |
| `/help`           | 显示帮助信息       | `/help`                             | 查看所有可用命令                     |
| `/new`            | 创建新会话         | `/new`                              | 开始新的 OpenCode 对话               |
| `/session [ID]`   | 切换到指定会话     | `/session ses_abc123`               | 支持任意会话 ID，无需存在检查        |
| `/agents`         | 列出可用智能体     | `/agents`                           | 查看可用的 OpenCode 智能体           |
| `/model [名称]`   | 切换模型           | `/model deepseek/deepseek-reasoner` | 切换 OpenCode 使用的模型             |
| `/stop`           | 停止当前会话       | `/stop`                             | 向 OpenCode 发送中止请求             |
| `/undo`           | 撤销最后一条消息   | `/undo`                             | 用户友好回复："已撤销最后一条消息"   |
| `/redo`           | 恢复所有撤销的消息 | `/redo`                             | 用户友好回复："已恢复所有撤销的消息" |
| `/reload`         | 重新加载配置       | `/reload`                           | 重新加载配置文件                     |
| `/reload restart` | 重启机器人程序     | `/reload restart`                   | 在同一终端内热重启                   |
| `/command [命令]` | 执行 OpenCode 命令 | `/command /init-deep`               | 执行 OpenCode 内置命令               |
| `/compact`        | 压缩对话上下文     | `/compact`                          | 压缩当前对话以节省上下文空间         |
| `/directory`      | 切换工作目录       | `/directory /path`                  | **暂时禁用**，所有操作基于根路径 `/` |

### 3. OpenCode 集成

- **消息转发**：白名单内的消息自动转发到 OpenCode
- **智能体支持**：支持 Sisyphus、Prometheus、Atlas 等多种智能体
- **模型切换**：可随时切换不同的 AI 模型
- **会话管理**：每个用户有独立的会话上下文

**重要说明**：

- OpenCode 通过 **skill** 发送 QQ 消息，不通过 bot 程序
- bot 程序只负责接收消息并转发到 OpenCode
- OpenCode 回复通过 `qq-message-napcat` skill 直接调用 NapCat API 发送

### 4. OpenCode Skill 功能

OpenCode 提供以下 skill 用于与 bot 交互：


| Skill               | 功能         | 说明                              |
| ------------------- | ------------ | --------------------------------- |
| `qq-message-napcat` | 发送 QQ 消息 | 支持私聊、群聊、图片、文件        |
| `定时消息`          | 设置定时任务 | 定时发送消息到 OpenCode           |
| 模型设置            | 切换 AI 模型 | 通过`/model` 命令或 OpenCode 配置 |
| 智能体设置          | 切换智能体   | 通过`/agents` 命令查看可用智能体  |

### 5. 会话管理

- **会话持久化**：所有会话永久保存在 `data/sessions.json` 中，无超时清理机制
- **重启恢复**：程序重启后自动恢复所有用户会话
- **无检查切换**：可切换到任意会话 ID，即使不在历史记录中

## 配置说明

### 主要配置 (`config.yaml`)

OpenCode QQ 机器人使用 YAML 格式配置文件，所有配置项集中在 `config.yaml` 文件中。项目还保留了 `src/utils/config.py` 作为遗留配置模块以保持向后兼容。

**核心配置项：**

```yaml
# WebSocket 服务器地址（NapCat 配置）
websocket:
  url: "ws://localhost:3002"
  access_token: "CqC5dDMXWGUu6NVh"
  heartbeat_interval: 30000  # 心跳间隔（毫秒）
  reconnect_interval: 5000   # 重连间隔（毫秒）

# HTTP API 配置（引用消息获取）
http_api:
  base_url: "http://localhost:3001"  # NapCat HTTP API 地址
  access_token: "fZvJ-zo_TzyAHOoI"
  timeout: 30  # 请求超时（秒）
  enabled: true  # 必须设为 true 才能使用引用消息功能

# OpenCode 服务器配置
opencode:
  host: "127.0.0.1"
  port: 4091
  directory: "/"
  default_agent: "Sisyphus (Ultraworker)"
  default_model: "alibaba-coding-plan-cn/qwen3.5-plus"

# 白名单配置
whitelist:
  qq_users:
    - 123456789
    - 123456789
    - 123456789
    # 添加更多允许的用户 QQ 号
  groups:
    - 123456789
    - 123456789
    # 添加更多允许的群组号
```

### ⚠️ 安全警告

**请谨慎添加其他 QQ 用户到白名单！**

添加用户到白名单意味着：

- 该用户可以通过 QQ 消息控制你的 OpenCode
- OpenCode 拥有执行任意代码、读写文件的权限
- **该用户实际上获得了你电脑的完全控制权**

**安全建议**：

1. 仅添加你完全信任的用户（如你自己的账号）
2. 不要添加陌生人或不熟悉的用户
3. 不要在公共群聊中泄露你的机器人配置
4. 定期检查和清理白名单

# 会话管理配置

session:
storage_type: "file"  # memory 或 file
file_path: "data/sessions.json"
max_sessions_per_user: 100

# 日志配置

logging:
log_file: "logs/onebot_client.log"
log_level: "DEBUG"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
error_log_separate: true  # 错误日志单独保存
error_log_file: "logs/onebot_client_error.log"


### 重要配置项说明

1. **`WS_URL`**：必须与 NapCat WebSocket 服务器地址一致（当前：`ws://localhost:3002`）
2. **`ACCESS_TOKEN`**：必须与 NapCat 配置的 Token 一致
3. **`HTTP_API_BASE_URL`**：NapCat HTTP API 地址，用于获取引用消息（当前：`http://localhost:3001`）
4. **`HTTP_API_ENABLED`**：必须设为 `true` 才能使用引用消息获取功能
5. **`QQ_USER_WHITELIST`**：添加允许使用机器人的 QQ 号
6. **`GROUP_WHITELIST`**：添加允许使用机器人的群组号

## 故障排除

### 常见问题及解决方法

#### 1. 连接失败

```

❌ 连接到 NapCat 服务器失败

```

**解决方法**：

- 检查 NapCat 是否正在运行
- 确认 WebSocket 服务器地址和端口正确（当前：`ws://localhost:3002`）
- 验证 Access Token 是否正确（当前：`CqC5dDMXWGUu6NVh`）
- 运行测试连接：`python tests/test_connection.py`


#### 2. OpenCode 消息发送失败

消息发送到 OpenCode 失败，OpenCode 端报错



**解决方法**：

- 检查 `config.yaml` 中的模型名称和智能体名称是否正确
- OpenCode 对模型和智能体名称有严格要求，名称不匹配会导致请求失败

**如何获取正确的名称**：

1. 打开 OpenCode Web 界面（http://127.0.0.1:4091）
2. 打开浏览器开发者工具（F12）→ Network 标签页
3. 在 OpenCode Web 发送一条消息
4. 找到 `prompt_async` 请求，查看请求体
5. 请求体中包含正确的 `model` 和 `agent` 名称

**示例请求体**：

```json
{
  "model": "alibaba-coding-plan-cn/qwen3.5-plus",
  "agent": "Sisyphus (Ultraworker)",
}
```

将正确的名称更新到 `config.yaml`：

```yaml
opencode:
  default_agent: "Sisyphus (Ultraworker)"  # 从抓包获取
  default_model: "alibaba-coding-plan-cn/qwen3.5-plus"  # 从抓包获取
```

### 日志文件位置

- **主日志**：`logs/onebot_client.log`
- **错误日志**：`logs/onebot_client_error.log`
- **会话数据**：`data/sessions.json`

### NapCat 相关错误

- **错误码 1006514**：NapCat 的 QQ 端被腾讯踢下线，需要重新登录 QQ 账号并重启 NapCat
- **连接拒绝**：NapCat 服务未启动或端口被占用
- **认证失败**：Access Token 不正确

## 扩展开发

### 添加新命令

在 `src/core/onebot_client.py` 中的 `_handle_private_message` 方法添加命令处理：

```python
async def _handle_private_message(self, user_id: int, message: str):
    if message.startswith('/mycommand'):
        # 处理新命令
        await self._send_private_message(user_id, "新命令响应")
        return True
    return False
```

### 修改白名单

编辑 `src/utils/config.py` 中的白名单配置：

```python
QQ_USER_WHITELIST = [
    1234567891,    # 原有用户
    1234567890,    # 新增用户
]

GROUP_WHITELIST = [
    1234567890,     # 原有群组
    1234567891,     # 新增群组
]
```

### 添加 OpenCode 功能

在 `src/opencode/opencode_client.py` 中添加新的 OpenCode API 调用方法。

## 注意事项

### 安全提示

1. **Access Token 保护**：不要将配置文件和 Token 泄露给他人
2. **白名单限制**：仅添加信任的用户和群组到白名单
3. **日志安全**：日志文件可能包含敏感信息，定期清理
4. **QQ 风控**：避免频繁发送消息，以免触发腾讯风控机制

### 性能优化

1. **日志轮转**：主日志10MB/5备份，错误日志5MB/3备份
2. **文件清理**：7天自动清理旧文件
3. **内存管理**：长时间运行时注意内存使用情况

### 兼容性说明

1. **Python 版本**：需要 Python 3.8 或更高版本
2. **NapCat 版本**：需要支持 OneBot V11 协议的 NapCat 版本
3. **OpenCode 版本**：需要本地部署的 OpenCode 服务
4. **操作系统**：主要在 Windows 测试，Linux/macOS 可能需要调整路径

## 测试与调试

### 调试接口 (Debug Interface)

项目提供了专门的调试接口 (`debug_interface.py`)，用于在不连接实际 QQ 机器人服务的情况下测试所有命令功能。

**主要功能**：

- 🔧 **模拟消息发送**：模拟 QQ 私聊和群聊消息
- 🧪 **命令功能测试**：测试所有机器人命令是否正常工作
- 📊 **自动化测试**：支持批量测试和结果报告生成
- 🔍 **详细日志**：提供详细的处理流程和错误信息

**快速使用**：

```bash
# 1. 直接运行调试接口测试
python debug_interface.py

# 2. 运行完整的命令功能测试
python test_commands.py
```

### 调试接口详细说明

#### 1. `debug_interface.py` - 基础调试接口

```python
from debug_interface import DebugInterface

# 初始化调试接口
debug = DebugInterface()
await debug.initialize()

# 发送测试消息
await debug.send_private_message(user_id=123456789, message="/help")
await debug.send_group_message(group_id=123456789, user_id=123456789, message="/help")
```

**核心方法**：

- `initialize()` - 初始化机器人客户端和 OpenCode 集成
- `send_private_message(user_id, message)` - 发送私聊测试消息
- `send_group_message(group_id, user_id, message)` - 发送群聊测试消息
- `close()` - 关闭调试接口


#### 3. OpenCode 客户端 API 更新

最新版本已完善 OpenCode 客户端的 API 方法，支持完整的命令功能：

- **`abort_session(session_id)`** - 中止 OpenCode 会话（对应 `/stop` 命令）
- **`revert_last_message(session_id)`** - 撤销最后一条消息（对应 `/undo` 命令）
- **`unrevert_messages(session_id)`** - 恢复所有撤销的消息（对应 `/redo` 命令）

这些方法通过调用 OpenCode 的相应 HTTP 端点实现：

- `/session/{session_id}/abort` - 中止会话
- `/session/{session_id}/revert` - 撤销消息
- `/session/{session_id}/unrevert` - 恢复消息

### 调试流程建议
2. **特定命令调试**：

   ```python
   # 自定义测试脚本
   from debug_interface import DebugInterface

   async def test_specific_command():
       debug = DebugInterface()
       await debug.initialize()

       # 测试特定命令
       await debug.send_private_message(123456789, "/new 测试会话标题")
       await debug.send_private_message(123456789, "/stop")

       await debug.close()
   ```
3. **错误排查**：

   - 检查 `logs/` 目录下的日志文件
   - 验证 OpenCode 服务是否运行（http://127.0.0.1:4091）
   - 确认会话管理器是否正确初始化

## 技术支持

如遇到问题，请按以下步骤排查：

1. **查看日志**：检查 `logs/onebot_client.log` 获取详细错误信息
2. **测试连接**：运行 `python tests/test_connection.py` 测试基本连接
3. **检查配置**：确认 `src/utils/config.py` 中的配置正确
4. **验证服务**：确保 NapCat 和 OpenCode 服务都在运行
5. **查阅文档**：查看 `docs/` 目录下的详细文档

## 更新日志

### 最新版本修复

- ✅ **会话持久化**：重启后会话自动恢复
- ✅ **程序热重启**：`/reload restart` 在同一终端内正确重启
- ✅ **无检查切换会话**：`/session [ID]` 支持任意会话 ID
- ✅ **用户友好回复**：`/undo` 和 `/redo` 命令显示友好提示
- ✅ **端点地址更新**：所有组件使用 `ws://localhost:3002`
- ✅ **调试接口完善**：新增 `debug_interface.py` 和 `test_commands.py` 测试工具
- ✅ **OpenCode API 完整化**：新增 `abort_session`、`revert_last_message`、`unrevert_messages` 方法
- ✅ **命令功能测试**：10 个核心命令 100% 通过自动化测试
- ✅ **引用消息处理优化**
- ✅ **图片路径格式化修复**：下载的图片路径正确显示在发送到 OpenCode 的消息中
- ✅ **合并转发消息处理**：支持解析合并转发消息中的文本、图片、文件
- ✅ **文件下载三层回退**：HTTP API → WebSocket API → 字符匹配，确保文件下载可靠性
- ✅ **引用消息格式优化**：纯文本/附件/合并转发三种格式，显示更清晰

### 合并转发消息处理说明

机器人支持解析合并转发消息，提取其中的文本、图片和文件：

**处理流程**：

1. 使用 `get_forward_msg` HTTP API 获取消息列表
2. 解析每条消息的发送者、文本内容、图片和文件
3. 图片通过 URL 直接下载到本地
4. 文件提示用户单独发送（NapCat 架构限制，合并转发中的文件无法下载）

**显示格式**：

```
用户发送了一个合并转发消息:
  昵称1: 文本内容1
  昵称2: [图片: /path/to/image.png]
  昵称3: [文件: xxx.mp3 (合并转发消息暂时无法下载文件，请单独发送文件)]

已下载 1 个附件:
  - 图片: image.png -> /path/to/image.png
```

**已知限制**：

- 合并转发消息中的文件无法通过 `get_file` API 下载（NapCat 的 `downloadRichMedia` 内部超时）
- 建议用户单独发送文件以获取下载支持

### 历史版本

- 初始版本：基础消息转发功能
- v1.1：添加完整命令系统
- v1.2：修复会话持久化和热重启问题
- v1.3：优化用户体验和错误处理
- v1.4：完善调试接口和 OpenCode API，支持完整命令功能测试
- v1.5：优化引用消息处理，移除 WebSocket 依赖，提升性能
- v1.6：新增合并转发消息处理，文件下载三层回退机制

## 许可证

本项目仅供学习和技术研究使用，请遵守相关法律法规和腾讯 QQ 用户协议。使用本软件产生的任何后果由使用者自行承担。

---

**项目状态**：✅ 生产就绪 - 所有核心功能已实现并通过测试
