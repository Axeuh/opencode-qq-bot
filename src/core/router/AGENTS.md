# 消息路由模块

**生成日期:** 2026-03-25
**模块数:** 3 Python 文件
**用途:** 消息路由和处理

## 目录结构

```
router/
├── message_router.py    # 路由逻辑 (450 行)
├── message_processor.py # 处理辅助 (471 行)
└── __init__.py
```

## 路由流程

```
收到消息
    → is_whitelisted? (检查用户/群)
    → is_command? (以 / 开头)
    → 是: CommandSystem.handle_command()
    → 否: OpenCodeForwarder.send_to_opencode()
```

## 核心类

| 类名 | 用途 |
|-------|---------|
| `MessageRouter` | 主路由器，白名单检查 |
| `MessageProcessor` | 消息预处理 |

## 查找指南

| 任务 | 位置 |
|------|----------|
| 添加路由规则 | message_router.py |
| 修改白名单 | message_router.py |
| 预处理消息 | message_processor.py |

## 白名单检查

```python
def should_process_message(user_id, group_id):
    if group_id:
        return group_id in GROUP_WHITELIST
    return user_id in USER_WHITELIST
```

## 编码规范

- 本地处理返回 `True` (命令)
- 转发到 OpenCode 返回 `False`
- 处理前先检查白名单