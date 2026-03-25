# 会话管理模块

**生成日期:** 2026-03-25
**模块数:** 5 Python 文件
**用途:** 用户会话和配置持久化

## 目录结构

```
session/
├── __init__.py
├── session_manager.py   # 核心管理器 (919 行)
├── user_session.py      # UserSession 数据类 (168 行)
├── user_config.py       # UserConfig 数据类 (124 行)
└── persistence.py       # 文件存储 (268 行)
```

## 核心类

| 类名 | 文件 | 用途 |
|-------|------|---------|
| `SessionManager` | session_manager.py | 单例管理器 |
| `UserSession` | user_session.py | 会话数据容器 |
| `UserConfig` | user_config.py | 用户偏好设置 |
| `Persistence` | persistence.py | 文件 I/O |

## 查找指南

| 任务 | 位置 |
|------|----------|
| 获取/创建会话 | session_manager.py |
| 修改会话数据 | user_session.py |
| 用户偏好设置 | user_config.py |
| 存储逻辑 | persistence.py |

## 使用示例

```python
from src.session import SessionManager

manager = SessionManager()
session = manager.get_or_create_session(user_id)
session.session_id = "ses_xxx"
session.current_agent = "Sisyphus"
manager.save_sessions()
```

## 会话流程

```
收到用户消息
    → SessionManager.get_or_create_session(user_id)
    → 检查内存中是否存在会话
    → 需要时从文件加载
    → 返回 UserSession 对象
```

## 会话恢复 (进程重启)

```
Bot 重启流程:
    1. 重启前: 保存活跃会话
       → ProcessManager._save_active_sessions()
       → 从 /session/status API 获取
       → 存储 session_ids 和用户信息
       
    2. 重启后: 异步恢复
       → ProcessManager._recover_sessions()
       → asyncio.gather() 并行恢复
       → 向每个活跃会话发送 "继续"
       → 会话之间不阻塞
```

## 数据结构

```python
UserSession:
    user_id: int           # 用户 QQ 号
    session_id: str        # OpenCode 会话 ID
    current_agent: str     # 当前智能体
    current_model: str     # 当前模型
    directory: str         # 工作目录
    created_at: float      # 创建时间
    last_active: float     # 最后活跃时间

UserConfig:
    default_agent: str     # 默认智能体
    default_model: str     # 默认模型
    default_directory: str # 默认目录
```

## 编码规范

- SessionManager 使用单例模式
- 修改时自动保存
- 文件存储于 `data/sessions.json`
- 线程安全操作
- 会话恢复使用异步并行发送
- 重启期间临时存储活跃会话