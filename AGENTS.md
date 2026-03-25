# OpenCode QQ Bot - 项目知识库

**生成日期:** 2026-03-25
**Commit:** 4db4026
**分支:** master

## 概述

通过 OneBot V11 协议和 NapCat 框架集成 OpenCode AI 平台的 QQ 机器人。
核心技术栈: Python 3.8+, aiohttp, WebSocket, HTTP API。

## 目录结构

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
├── tests/                 # 测试脚本 (17 文件)
├── scripts/               # 启动脚本
├── data/                  # 持久化数据
├── config.yaml           # 主配置文件 (YAML)
└── requirements.txt      # 依赖 (4 个包)
```

## 查找指南

| 任务 | 位置 | 说明 |
|------|----------|-------|
| 添加新的 QQ 命令 | `src/core/command/` | 在对应文件中创建处理器 |
| 添加 HTTP 端点 | `src/core/http/` | 添加到 routes.py，创建端点处理器 |
| 修改 OpenCode 集成 | `src/opencode/` | client.py 为基础，*_api.py 为各领域 |
| 会话管理 | `src/session/` | session_manager.py 核心逻辑 |
| 配置管理 | `config.yaml` + `src/utils/config_loader.py` | YAML 格式，支持点路径 |
| WebSocket 处理 | `src/core/connection_manager.py` | NapCat WebSocket 客户端 |
| 消息路由 | `src/core/router/` | 白名单 + 命令检测 |
| 文件下载 | `src/core/file/` | 三层回退机制 |
| 进程管理 | `src/core/process_manager.py` | OpenCode/Bot 重启，PID 追踪 |
| 会话恢复 | `src/core/process_manager.py` | 重启时保存/恢复活跃会话 |

## 编码规范

### 命名约定
- 类名: `PascalCase` (`OneBotClient`, `CommandSystem`)
- 函数名: `snake_case` (`handle_private_message`)
- 常量: `UPPER_SNAKE_CASE` (`WS_URL`)
- 私有成员: `_前缀` (`_internal_method`)

### 异步模式
所有网络操作使用 `async/await`。入口点: `asyncio.run(main())`。

### 错误处理
使用 `src/utils/error_handler.py` 中的 `@handle_errors` 装饰器。返回 `(result, error)` 元组。

### 类型提示
所有公共函数必须有类型提示。可空返回值使用 `Optional[T]`。

## 反模式 (避免)

1. **裸 `except:`** - 使用 `except Exception as e:` 代替
2. **`as any` / `@ts-ignore`** - 禁止抑制类型错误
3. **同步网络调用** - 异步上下文中必须使用异步
4. **全局状态变更** - 使用依赖注入
5. **大文件 (>500 行)** - 拆分为专注模块

## 常用命令

```bash
# 启动机器人
python scripts/run_bot.py

# 运行测试
python tests/test_commands.py

# 检查连接
python tests/test_connection.py

# 调试接口
python tests/debug_interface.py
```

## 服务依赖

- NapCat WebSocket: `ws://localhost:3002`
- NapCat HTTP API: `http://localhost:3001`
- OpenCode 服务: `http://127.0.0.1:4091`

## 架构设计

**协调器模式:**
```
onebot_client.py (协调器)
    ├── ConnectionManager (WebSocket)
    ├── HTTPServer (HTTP API)
    │   └── ProcessManager (进程控制)
    ├── MessageRouter (路由)
    │   ├── CommandSystem (命令)
    │   └── OpenCodeForwarder (AI)
    ├── FileHandler (文件)
    └── TaskScheduler (定时任务)
```

**进程管理:**
```
ProcessManager
    ├── PID 缓存 (data/opencode.pid)
    ├── OpenCode 启动/停止/重启
    ├── Bot 重启 (os.execv)
    ├── 重启前保存会话
    └── 重启后异步恢复会话
```

## 子模块文档

- [src/AGENTS.md](./src/AGENTS.md) - 源码详情
- [src/core/AGENTS.md](./src/core/AGENTS.md) - 核心模块
- [tests/AGENTS.md](./tests/AGENTS.md) - 测试架构