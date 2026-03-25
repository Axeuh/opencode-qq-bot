# OpenCode QQ 机器人

基于 OneBot V11 协议、NapCat 框架和 OpenCode AI 平台的高级 QQ 机器人，实现 QQ 消息与 OpenCode AI 的无缝集成。

## 项目概述

这是一个纯 Python 实现的 QQ 机器人，核心功能是将 QQ 消息转发到 OpenCode AI 平台进行处理，并提供完整的命令系统用于会话管理、智能体切换、消息撤销等高级操作。

**核心特性**：

- **消息转发**：将白名单内的 QQ 消息转发到 OpenCode AI 平台
- **AI 集成**：与 OpenCode Sisyphus、Prometheus 等智能体无缝协作
- **命令系统**：完整的命令集用于会话管理和机器人控制
- **Web 控制台**：内置 HTTPS Web 管理界面
- **会话持久化**：用户会话在程序重启后自动恢复
- **热重启**：支持`/reload restart`命令在同一终端内重启程序
- **白名单过滤**：精确控制哪些用户和群组可以交互
- **定时任务**：支持延时任务和定时任务调度

**设计原则**：

1. 机器人仅转发白名单内的消息到 OpenCode
2. OpenCode 代理自行回复（通过 qq-message-napcat 技能）
3. 命令直接在机器人本地处理，不转发到 OpenCode
4. 保持轻量级核心，通过配置扩展功能

## 项目结构

```
mybot-web/
├── src/                    # Python 源码 (72 模块)
│   ├── core/              # 核心功能 (28 模块)
│   │   ├── http/          # HTTP 服务器 (11 模块)
│   │   ├── command/       # 命令系统 (8 模块)
│   │   ├── file/          # 文件处理 (4 模块)
│   │   └── router/        # 消息路由 (3 模块)
│   ├── opencode/          # OpenCode 客户端 (7 模块)
│   ├── session/           # 会话管理 (5 模块)
│   └── utils/             # 工具函数 (4 模块)
├── web/                    # 前端 Web 控制台
│   ├── index.html         # 主页面
│   ├── css/styles.css     # 样式文件
│   └── js/                # JavaScript 模块 (10 个文件)
│       ├── app.js         # 应用入口
│       ├── config.js      # 智能体/模型选择
│       ├── message.js     # 消息渲染
│       ├── session.js     # 会话管理
│       ├── sse.js         # SSE 流式消息
│       └── ...
├── tests/                 # 测试脚本 (17 文件)
├── scripts/               # 启动脚本
├── data/                  # 持久化数据
│   ├── sessions.json      # 会话数据
│   └── tasks.json         # 定时任务数据
├── logs/                  # 日志目录
├── config.yaml            # 主配置文件 (YAML)
├── requirements.txt       # Python 依赖
└── README.md              # 本文件
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
| Web 控制台       | https://127.0.0.1:4090 | Web 管理界面          |

### 安装步骤

```bash
# 1. 克隆或下载项目到本地
cd D:\Users\Axeuh\Desktop\Axeuh_bot\mybot-web

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
python scripts/run_bot.py
```

启动脚本会自动检查依赖和服务状态。

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
| `/agent [名称]`   | 列出/切换智能体    | `/agent` 或 `/agent 1`              | 查看或切换 OpenCode 智能体           |
| `/model [名称]`   | 列出/切换模型      | `/model` 或 `/model glm-5`          | 切换 OpenCode 使用的模型             |
| `/stop`           | 停止当前会话       | `/stop`                             | 向 OpenCode 发送中止请求             |
| `/undo`           | 撤销最后一条消息   | `/undo`                             | 用户友好回复："已撤销最后一条消息"   |
| `/redo`           | 恢复所有撤销的消息 | `/redo`                             | 用户友好回复："已恢复所有撤销的消息" |
| `/reload`         | 重新加载配置       | `/reload`                           | 重新加载配置文件                     |
| `/reload restart` | 重启机器人程序     | `/reload restart`                   | 在同一终端内热重启                   |
| `/command [命令]` | 执行 OpenCode 命令 | `/command /init-deep`               | 执行 OpenCode 内置命令               |
| `/compact`        | 压缩对话上下文     | `/compact`                          | 压缩当前对话以节省上下文空间         |
| `/directory`      | 切换工作目录       | `/directory /path`                  | 切换 OpenCode 工作目录               |

### 3. Web 控制台

机器人内置 HTTPS Web 控制台，提供图形化管理界面：

- **消息流显示**：实时显示对话消息
- **会话管理**：创建、切换、删除会话
- **智能体/模型选择**：图形化选择智能体和模型
- **工作目录设置**：可视化配置工作路径

**访问地址**：`https://127.0.0.1:4090`

### 4. OpenCode 集成

- **消息转发**：白名单内的消息自动转发到 OpenCode
- **智能体支持**：支持 Sisyphus、Prometheus 等多种智能体
- **模型切换**：可随时切换不同的 AI 模型
- **会话管理**：每个用户有独立的会话上下文

**重要说明**：

- OpenCode 通过 **skill** 发送 QQ 消息，不通过 bot 程序
- bot 程序只负责接收消息并转发到 OpenCode
- OpenCode 回复通过 `qq-message-napcat` skill 直接调用 NapCat API 发送

### 5. 定时任务

支持延时任务和定时任务：

- **延时任务**：在指定时间后执行（分钟/小时/天/周/月）
- **定时任务**：每周/每月/每年固定时间执行

## 配置说明

### 主要配置 (`config.yaml`)

```yaml
# WebSocket 服务器地址（NapCat 配置）
websocket:
  url: "ws://localhost:3002"
  access_token: "your_access_token"
  heartbeat_interval: 30000  # 心跳间隔（毫秒）
  reconnect_interval: 5000   # 重连间隔（毫秒）

# HTTP API 配置（引用消息获取）
http_api:
  base_url: "http://localhost:3001"
  access_token: "your_http_token"
  timeout: 30
  enabled: true

# OpenCode 服务器配置
opencode:
  host: "127.0.0.1"
  port: 4091
  directory: "C:\\"
  timeout: 300
  default_agent: "Sisyphus (Ultraworker)"
  default_model: "glm-5"
  default_provider: "alibaba-coding-plan-cn"

# HTTP 服务器配置（Web 控制台）
http_server:
  enabled: true
  host: "127.0.0.1"
  port: 4090
  ssl_cert: null  # SSL 证书路径
  ssl_key: null   # SSL 密钥路径

# 白名单配置
whitelist:
  qq_users:
    - 123456789
    # 添加更多允许的用户 QQ 号
  groups:
    - 123456789
    # 添加更多允许的群组号
```

### 智能体名称格式

**重要**：智能体名称必须使用完整格式，不支持简写：

```yaml
# 正确
default_agent: "Sisyphus (Ultraworker)"

# 错误 - 会导致 OpenCode API 调用失败
default_agent: "sisyphus"
```

### 安全警告

**请谨慎添加其他 QQ 用户到白名单！**

添加用户到白名单意味着：
- 该用户可以通过 QQ 消息控制你的 OpenCode
- OpenCode 拥有执行任意代码、读写文件的权限
- **该用户实际上获得了你电脑的完全控制权**

## 故障排除

### 常见问题及解决方法

#### 1. 连接失败

**解决方法**：
- 检查 NapCat 是否正在运行
- 确认 WebSocket 服务器地址和端口正确
- 验证 Access Token 是否正确
- 运行测试连接：`python tests/test_connection.py`

#### 2. OpenCode 消息发送失败

**解决方法**：
- 检查 `config.yaml` 中的智能体名称是否使用完整格式
- 智能体名称不支持简写，必须使用完整名称如 `"Sisyphus (Ultraworker)"`

**如何获取正确的名称**：
1. 打开 OpenCode Web 界面（http://127.0.0.1:4091）
2. 打开浏览器开发者工具（F12）→ Network 标签页
3. 在 OpenCode Web 发送一条消息
4. 找到 `prompt_async` 请求，查看请求体中的 `agent` 和 `model` 名称

### 日志文件位置

- **主日志**：`logs/onebot_client.log`
- **错误日志**：`logs/onebot_client_error.log`
- **会话数据**：`data/sessions.json`

## 扩展开发

### 添加新命令

在 `src/core/command/` 目录下添加新的命令处理器：

```python
# src/core/command/my_handler.py
class MyHandler:
    async def handle_mycmd(self, message_type, group_id, user_id, args):
        # 处理新命令
        await self.send_reply(message_type, group_id, user_id, "响应")
```

### 添加 HTTP 端点

在 `src/core/http/routes.py` 中添加新路由：

```python
router.add_post("/api/my_endpoint", self.handle_my_endpoint)
```

## 注意事项

### 安全提示

1. **Access Token 保护**：不要将配置文件和 Token 泄露给他人
2. **白名单限制**：仅添加信任的用户和群组到白名单
3. **日志安全**：日志文件可能包含敏感信息，定期清理
4. **QQ 风控**：避免频繁发送消息，以免触发腾讯风控机制

### 兼容性说明

1. **Python 版本**：需要 Python 3.8 或更高版本
2. **NapCat 版本**：需要支持 OneBot V11 协议的 NapCat 版本
3. **OpenCode 版本**：需要本地部署的 OpenCode 服务
4. **操作系统**：主要在 Windows 测试，Linux/macOS 可能需要调整路径

## 更新日志

### 最新版本

- **智能体参数统一**：所有代码使用完整智能体名称，不支持简写
- **Web 控制台优化**：添加全局 loading 动画，优化加载体验
- **前端模块化**：JS 拆分为 10 个模块，CSS 独立文件
- **HTTPS 支持**：Web 控制台支持 HTTPS
- **定时任务调度**：支持延时任务和定时任务
- **会话持久化**：重启后会话自动恢复
- **程序热重启**：`/reload restart` 在同一终端内正确重启

## 许可证

本项目仅供学习和技术研究使用，请遵守相关法律法规和腾讯 QQ 用户协议。使用本软件产生的任何后果由使用者自行承担。

---

**项目状态**：生产就绪 - 所有核心功能已实现并通过测试