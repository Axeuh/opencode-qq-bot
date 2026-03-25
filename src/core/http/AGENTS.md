# HTTP 服务器模块

**生成日期:** 2026-03-25
**模块数:** 11 Python 文件
**端点数:** 41 HTTP 路由

## 目录结构

```
http/
├── server.py            # HTTPServer 类 (297 行)
├── routes.py            # 路由定义 (182 行)
├── middleware.py        # 认证中间件 (156 行)
├── auth_handler.py      # 登录/密码 (357 行)
├── session_endpoints.py # 会话 API (440 行)
├── task_endpoints.py    # 任务 API (328 行)
├── config_endpoints.py  # 配置 API (477 行)
├── upload_handler.py    # 文件上传 (215 行)
├── opencode_proxy.py    # OpenCode 代理 (298 行)
└── process_endpoints.py # 进程控制 (150 行)
```

## 端点分类

| 分类 | 路由 | 文件 |
|----------|--------|------|
| 认证 | `/api/login`, `/api/password/*` | auth_handler.py |
| 会话 | `/api/session/*` | session_endpoints.py |
| 任务 | `/api/task/*` | task_endpoints.py |
| 配置 | `/api/agents/*`, `/api/model/*` | config_endpoints.py |
| 上传 | `/api/upload` | upload_handler.py |
| OpenCode | `/api/opencode/*` | opencode_proxy.py |
| 进程 | `/api/system/*` | process_endpoints.py |

## 查找指南

| 任务 | 位置 |
|------|----------|
| 添加新端点 | routes.py + 创建处理器 |
| 修改认证 | auth_handler.py, middleware.py |
| 会话 API | session_endpoints.py |
| 任务 API | task_endpoints.py |
| OpenCode 代理 | opencode_proxy.py |
| 进程控制 | process_endpoints.py |
| 重启 OpenCode/Bot | process_endpoints.py |

## 进程控制端点

| 端点 | 方法 | 用途 |
|----------|--------|---------|
| `/api/system/status` | GET | 系统状态 (OpenCode 运行状态, 会话数) |
| `/api/system/restart/opencode` | POST | 重启 OpenCode 进程 |
| `/api/system/restart/bot` | POST | 重启 Bot (os.execv) |
| `/api/system/start/opencode` | POST | 启动 OpenCode 进程 |
| `/api/system/stop/opencode` | POST | 停止 OpenCode 进程 |

### 重启流程

```
POST /api/system/restart/bot
    → 停止 SSE 监听 (释放端口)
    → 保存活跃会话 (从 /session/status 获取)
    → 重启 Bot (os.execv)
    → 启动时: 从 PID 文件恢复 OpenCode
    → 异步恢复会话 (向每个会话发送 "继续")
```

### PID 缓存机制

```
ProcessManager 通过 PID 文件追踪 OpenCode:
- data/opencode.pid 存储进程 ID
- Bot 重启时从 PID 恢复进程
- 无需强制杀死 (避免端口占用问题)
```

## 核心类

| 类名 | 用途 |
|-------|---------|
| `HTTPServer` | 主服务器，路由设置 |
| `AuthMiddleware` | Token 验证，限流 |
| `AuthHandler` | 登录，密码管理 |

## 认证流程

```
请求 → 中间件 (token 检查)
    → 处理器 (业务逻辑)
    → 响应 (JSON)
```

## 编码规范

- 所有处理器为异步方法
- 返回 `web.json_response()`
- 受保护路由使用 `@require_auth` 装饰器
- 错误响应: `{"error": "message"}`
- 本地访问 (127.0.0.1) 跳过 token 认证
- 进程端点统一使用 ProcessManager