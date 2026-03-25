# OpenCode 客户端模块

**生成日期:** 2026-03-25
**模块数:** 7 Python 文件
**用途:** OpenCode AI 平台集成

## 目录结构

```
opencode/
├── __init__.py
├── types.py             # 类型定义 (165 行)
├── client.py            # 基础 HTTP 客户端 (276 行)
├── opencode_client.py   # 组合客户端 (300 行)
├── session_api.py       # 会话 API (409 行)
├── message_api.py       # 消息 API (245 行)
└── model_api.py         # 模型/智能体 API (165 行)
```

## API 模块

| 模块 | 类名 | 方法 |
|--------|-------|---------|
| `session_api.py` | SessionAPI | create_session, abort_session, revert_last_message, list_sessions |
| `message_api.py` | MessageAPI | send_message, execute_command |
| `model_api.py` | ModelAPI | get_models, get_agents, list_commands |

## 查找指南

| 任务 | 位置 |
|------|----------|
| 添加新 API 方法 | 在对应的 *_api.py 中创建 |
| 修改会话处理 | session_api.py |
| 修改消息发送 | message_api.py |
| 修改模型列表 | model_api.py |
| 类型定义 | types.py |

## 使用示例

```python
from src.opencode import OpenCodeClient

client = OpenCodeClient()
session_id, error = await client.create_session("标题")
response, error = await client.send_message("你好", session_id)
models, error = await client.get_models()
await client.close()
```

## 组合模式

```
OpenCodeClient (组合)
    ├── _session_api: SessionAPI
    ├── _message_api: MessageAPI
    └── _model_api: ModelAPI
```

## 编码规范

- 所有 API 方法返回 `(result, error)` 元组
- 使用基础客户端的 `_send_request()`
- 所有网络操作使用 async/await
- 使用 `await client.close()` 关闭客户端