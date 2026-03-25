# 核心模块

**生成日期:** 2026-03-25
**模块数:** 28 Python 文件
**架构:** 协调器 + 依赖注入

## 目录结构

```
core/
├── onebot_client.py      # 协调器 (318 行)
├── connection_manager.py # WebSocket (532 行)
├── task_scheduler.py     # 调度器 (306 行)
├── client_initializer.py # DI 容器 (310 行)
├── process_manager.py    # 进程控制 (200+ 行)
├── http/                 # HTTP 服务器 (11 模块)
├── command/              # QQ 命令 (8 模块)
├── file/                 # 文件处理 (4 模块)
└── router/               # 消息路由 (3 模块)
```

## 核心类

| 类名 | 文件 | 用途 |
|-------|------|---------|
| `OneBotClient` | onebot_client.py | 主协调器 |
| `ConnectionManager` | connection_manager.py | WebSocket 生命周期 |
| `ClientInitializer` | client_initializer.py | DI 容器 |
| `TaskScheduler` | task_scheduler.py | 定时任务 |
| `ProcessManager` | process_manager.py | OpenCode/Bot 进程控制 |

## 查找指南

| 任务 | 位置 |
|------|----------|
| 添加 HTTP 端点 | `http/` 目录 |
| 添加 QQ 命令 | `command/` 目录 |
| 处理文件下载 | `file/` 目录 |
| 路由消息 | `router/` 目录 |
| WebSocket 连接 | `connection_manager.py` |
| 初始化组件 | `client_initializer.py` |
| 重启 OpenCode/Bot | `process_manager.py` |
| PID 追踪 | `process_manager.py` (data/opencode.pid) |
| 会话保存/恢复 | `process_manager.py` |

## 协调器模式

```python
OneBotClient (协调器)
    ├── ConnectionManager (WebSocket)
    ├── HTTPServer → http/
    │   └── ProcessManager (进程控制)
    ├── MessageRouter → router/
    │   ├── CommandSystem → command/
    │   └── OpenCodeForwarder
    └── FileHandler → file/
```

## 进程管理器

```python
ProcessManager
    # PID 缓存
    pid_file = "data/opencode.pid"
    _save_pid_to_file(pid)
    _restore_process_from_pid()

    # OpenCode 控制
    async start_opencode(force=False)
    async stop_opencode()
    async restart_opencode()

    # 会话恢复
    async _save_active_sessions()  # 重启前
    async _recover_sessions()      # 重启后 (异步)
```

## 子模块文档

- [http/AGENTS.md](./http/AGENTS.md) - HTTP 服务器
- [command/AGENTS.md](./command/AGENTS.md) - 命令系统
- [file/AGENTS.md](./file/AGENTS.md) - 文件处理
- [router/AGENTS.md](./router/AGENTS.md) - 消息路由