# Session Management Module

**Generated:** 2026-03-24
**Modules:** 5 Python files
**Purpose:** User session and config persistence

## STRUCTURE

```
session/
├── __init__.py
├── session_manager.py   # Core manager (919 lines)
├── user_session.py      # UserSession dataclass (168 lines)
├── user_config.py       # UserConfig dataclass (124 lines)
└── persistence.py       # File storage (268 lines)
```

## KEY CLASSES

| Class | File | Purpose |
|-------|------|---------|
| `SessionManager` | session_manager.py | Singleton manager |
| `UserSession` | user_session.py | Session data container |
| `UserConfig` | user_config.py | User preferences |
| `Persistence` | persistence.py | File I/O |

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Get/create session | session_manager.py |
| Modify session data | user_session.py |
| User preferences | user_config.py |
| Storage logic | persistence.py |

## USAGE

```python
from src.session import SessionManager

manager = SessionManager()
session = manager.get_or_create_session(user_id)
session.session_id = "ses_xxx"
session.current_agent = "Sisyphus"
manager.save_sessions()
```

## SESSION FLOW

```
User message received
    → SessionManager.get_or_create_session(user_id)
    → Check if session exists in memory
    → Load from file if needed
    → Return UserSession object
```

## DATA STRUCTURES

```python
UserSession:
    user_id: int
    session_id: str
    current_agent: str
    current_model: str
    directory: str
    created_at: float
    last_active: float

UserConfig:
    default_agent: str
    default_model: str
    default_directory: str
```

## CONVENTIONS

- Singleton pattern for SessionManager
- Auto-save on modification
- File storage in `data/sessions.json`
- Thread-safe operations