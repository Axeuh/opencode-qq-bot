# Source Code Modules

**Generated:** 2026-03-24
**Modules:** 72 Python files
**Style:** Chinese comments + English code, async-first

## STRUCTURE

```
src/
├── core/              # Core functionality (27 modules)
│   ├── http/          # HTTP server (10 modules)
│   ├── command/       # Command system (8 modules)
│   ├── file/          # File handling (4 modules)
│   └── router/        # Message routing (3 modules)
├── opencode/          # OpenCode client (7 modules)
├── session/           # Session management (5 modules)
└── utils/             # Utilities (4 modules)
```

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add QQ command | `core/command/` - create handler file |
| Add HTTP endpoint | `core/http/` - add to routes.py |
| OpenCode API | `opencode/` - use *_api.py files |
| User sessions | `session/` - session_manager.py |
| Config loading | `utils/config_loader.py` |
| Error handling | `utils/error_handler.py` |

## MODULE RESPONSIBILITIES

### core/ - Core Bot Logic

| Subdir | Files | Purpose |
|--------|-------|---------|
| `http/` | 10 | HTTP API server, endpoints, auth |
| `command/` | 8 | QQ command handlers |
| `file/` | 4 | File download/upload, path resolution |
| `router/` | 3 | Message routing, processing |

### opencode/ - OpenCode Integration

| File | Purpose |
|------|---------|
| `client.py` | Base HTTP client |
| `session_api.py` | Session management API |
| `message_api.py` | Message sending API |
| `model_api.py` | Model/agent listing API |
| `types.py` | Type definitions |

### session/ - Session Management

| File | Purpose |
|------|---------|
| `session_manager.py` | Core session manager |
| `user_session.py` | UserSession dataclass |
| `user_config.py` | UserConfig dataclass |
| `persistence.py` | File persistence |

### utils/ - Utilities

| File | Purpose |
|------|---------|
| `config_loader.py` | YAML config loading |
| `config.py` | Legacy config (compat) |
| `error_handler.py` | Error decorators |

## CONVENTIONS

- **Naming**: `PascalCase` classes, `snake_case` functions
- **Async**: All network ops use `async/await`
- **Types**: Required on public functions
- **Errors**: Return `(result, error)` tuples

## DEPENDENCIES

```
onebot_client.py (coordinator)
    ├── ConnectionManager
    ├── HTTPServer → core/http/
    ├── MessageRouter → core/router/
    │   ├── CommandSystem → core/command/
    │   └── OpenCodeForwarder
    ├── FileHandler → core/file/
    └── TaskScheduler
```

## SUBMODULES

- [core/AGENTS.md](./core/AGENTS.md) - Core modules detail
- [core/http/AGENTS.md](./core/http/AGENTS.md) - HTTP server
- [core/command/AGENTS.md](./core/command/AGENTS.md) - Command system
- [opencode/AGENTS.md](./opencode/AGENTS.md) - OpenCode client
- [session/AGENTS.md](./session/AGENTS.md) - Session management