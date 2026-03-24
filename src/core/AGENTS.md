# Core Modules

**Generated:** 2026-03-24
**Modules:** 27 Python files
**Architecture:** Coordinator + Dependency Injection

## STRUCTURE

```
core/
├── onebot_client.py      # Coordinator (318 lines)
├── connection_manager.py # WebSocket (532 lines)
├── task_scheduler.py     # Scheduling (306 lines)
├── client_initializer.py # DI container (310 lines)
├── http/                 # HTTP server (10 modules)
├── command/              # QQ commands (8 modules)
├── file/                 # File handling (4 modules)
└── router/               # Message routing (3 modules)
```

## KEY CLASSES

| Class | File | Purpose |
|-------|------|---------|
| `OneBotClient` | onebot_client.py | Main coordinator |
| `ConnectionManager` | connection_manager.py | WebSocket lifecycle |
| `ClientInitializer` | client_initializer.py | DI container |
| `TaskScheduler` | task_scheduler.py | Scheduled tasks |

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add HTTP endpoint | `http/` directory |
| Add QQ command | `command/` directory |
| Handle file download | `file/` directory |
| Route messages | `router/` directory |
| WebSocket connection | `connection_manager.py` |
| Init components | `client_initializer.py` |

## COORDINATOR PATTERN

```python
OneBotClient (coordinator)
    ├── ConnectionManager (WebSocket)
    ├── HTTPServer → http/
    ├── MessageRouter → router/
    │   ├── CommandSystem → command/
    │   └── OpenCodeForwarder
    └── FileHandler → file/
```

## SUBMODULES

- [http/AGENTS.md](./http/AGENTS.md) - HTTP server
- [command/AGENTS.md](./command/AGENTS.md) - Command system
- [file/AGENTS.md](./file/AGENTS.md) - File handling
- [router/AGENTS.md](./router/AGENTS.md) - Message routing