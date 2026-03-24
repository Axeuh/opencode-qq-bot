# OpenCode QQ Bot - Project Knowledge Base

**Generated:** 2026-03-24
**Commit:** 4db4026
**Branch:** master

## OVERVIEW

QQ bot integrating with OpenCode AI platform via OneBot V11 protocol and NapCat framework.
Core stack: Python 3.8+, aiohttp, WebSocket, HTTP API.

## STRUCTURE

```
mybot-web/
├── src/                    # Python source (72 modules)
│   ├── core/              # Core functionality (27 modules)
│   │   ├── http/          # HTTP server (10 modules)
│   │   ├── command/       # Command system (8 modules)
│   │   ├── file/          # File handling (4 modules)
│   │   └── router/        # Message routing (3 modules)
│   ├── opencode/          # OpenCode client (7 modules)
│   ├── session/           # Session management (5 modules)
│   └── utils/             # Utilities (4 modules)
├── tests/                 # Test scripts (17 files)
├── scripts/               # Startup scripts
├── data/                  # Persistent data
├── config.yaml           # Main config (YAML)
└── requirements.txt      # Dependencies (4 packages)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add new QQ command | `src/core/command/` | Create handler in appropriate file |
| Add HTTP endpoint | `src/core/http/` | Add to routes.py, create endpoint handler |
| Modify OpenCode integration | `src/opencode/` | client.py for base, *_api.py for domains |
| Session management | `src/session/` | session_manager.py for core logic |
| Configuration | `config.yaml` + `src/utils/config_loader.py` | YAML format, loader supports dot paths |
| WebSocket handling | `src/core/connection_manager.py` | NapCat WebSocket client |
| Message routing | `src/core/router/` | White list + command detection |
| File download | `src/core/file/` | Three-tier fallback mechanism |

## CONVENTIONS

### Naming
- Classes: `PascalCase` (`OneBotClient`, `CommandSystem`)
- Functions: `snake_case` (`handle_private_message`)
- Constants: `UPPER_SNAKE_CASE` (`WS_URL`)
- Private: `_leading_underscore` (`_internal_method`)

### Async Pattern
All network operations use `async/await`. Entry point: `asyncio.run(main())`.

### Error Handling
Use `@handle_errors` decorator from `src/utils/error_handler.py`. Returns `(result, error)` tuple.

### Type Hints
Required on all public functions. Use `Optional[T]` for nullable returns.

## ANTI-PATTERNS (AVOID)

1. **Bare `except:`** - Use `except Exception as e:` instead
2. **`as any` / `@ts-ignore`** - Never suppress type errors
3. **Sync network calls** - Always use async in async context
4. **Global state mutation** - Use dependency injection
5. **Large files (>500 lines)** - Split into focused modules

## COMMANDS

```bash
# Start bot
python scripts/run_bot.py

# Run tests
python tests/test_commands.py

# Check connection
python tests/test_connection.py

# Debug interface
python tests/debug_interface.py
```

## SERVICE DEPENDENCIES

- NapCat WebSocket: `ws://localhost:3002`
- NapCat HTTP API: `http://localhost:3001`
- OpenCode Service: `http://127.0.0.1:4091`

## ARCHITECTURE

**Coordinator Pattern:**
```
onebot_client.py (coordinator)
    ├── ConnectionManager (WebSocket)
    ├── HTTPServer (HTTP API)
    ├── MessageRouter (routing)
    │   ├── CommandSystem (commands)
    │   └── OpenCodeForwarder (AI)
    ├── FileHandler (files)
    └── TaskScheduler (scheduled tasks)
```

## SUBMODULES

- [src/AGENTS.md](./src/AGENTS.md) - Source code details
- [src/core/AGENTS.md](./src/core/AGENTS.md) - Core modules
- [tests/AGENTS.md](./tests/AGENTS.md) - Test architecture