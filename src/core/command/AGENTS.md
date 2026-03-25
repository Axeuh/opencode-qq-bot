# 命令系统模块

**生成日期:** 2026-03-25
**模块数:** 8 Python 文件
**命令数:** 12 个 QQ 命令

## 目录结构

```
command/
├── command_system.py    # 路由器 (274 行)
├── utils.py             # 辅助函数 (185 行)
├── help_handler.py      # /help (142 行)
├── session_handler.py   # /new, /session, /stop, /path (468 行)
├── model_handler.py     # /agent, /model (312 行)
├── task_handler.py      # /command, /reload (340 行)
├── message_handler.py   # /undo, /redo, /compact (298 行)
└── __init__.py
```

## 命令列表

| 命令 | 处理器 | 用途 |
|---------|---------|---------|
| `/help` | HelpHandler | 显示帮助 |
| `/new` | SessionHandler | 创建会话 |
| `/session` | SessionHandler | 切换会话 |
| `/stop` | SessionHandler | 停止会话 |
| `/path` | SessionHandler | 设置目录 |
| `/agent` | ModelHandler | 列出/切换智能体 |
| `/model` | ModelHandler | 列出/切换模型 |
| `/command` | TaskHandler | 执行斜杠命令 |
| `/reload` | TaskHandler | 重载配置 |
| `/undo` | MessageHandler | 撤回消息 |
| `/redo` | MessageHandler | 恢复消息 |
| `/compact` | MessageHandler | 压缩上下文 |

## 查找指南

| 任务 | 位置 |
|------|----------|
| 添加新命令 | 创建处理器文件，在 command_system.py 注册 |
| 修改会话命令 | session_handler.py |
| 修改模型命令 | model_handler.py |
| 修改消息命令 | message_handler.py |

## 命令流程

```
QQ 消息 (/help)
    → MessageRouter.is_command()
    → CommandSystem.handle_command()
    → HelpHandler.handle_help()
    → 通过 ApiSender 回复
```

## 编码规范

- 每个处理器是一个带异步方法的类
- 在 `command_system.py` 的 COMMAND_HANDLERS 字典中注册
- 返回 `(success, message)` 元组
- 使用 ApiSender 回复