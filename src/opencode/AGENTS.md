# OpenCode Client Module

**Generated:** 2026-03-24
**Modules:** 7 Python files
**Purpose:** OpenCode AI platform integration

## STRUCTURE

```
opencode/
├── __init__.py
├── types.py             # Type definitions (165 lines)
├── client.py            # Base HTTP client (276 lines)
├── opencode_client.py   # Composite client (300 lines)
├── session_api.py       # Session API (409 lines)
├── message_api.py       # Message API (245 lines)
└── model_api.py         # Model/Agent API (165 lines)
```

## API MODULES

| Module | Class | Methods |
|--------|-------|---------|
| `session_api.py` | SessionAPI | create_session, abort_session, revert_last_message, list_sessions |
| `message_api.py` | MessageAPI | send_message, execute_command |
| `model_api.py` | ModelAPI | get_models, get_agents, list_commands |

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add new API method | Create in appropriate *_api.py |
| Modify session handling | session_api.py |
| Modify message sending | message_api.py |
| Modify model listing | model_api.py |
| Type definitions | types.py |

## USAGE

```python
from src.opencode import OpenCodeClient

client = OpenCodeClient()
session_id, error = await client.create_session("Title")
response, error = await client.send_message("Hello", session_id)
models, error = await client.get_models()
await client.close()
```

## COMPOSITION PATTERN

```
OpenCodeClient (composite)
    ├── _session_api: SessionAPI
    ├── _message_api: MessageAPI
    └── _model_api: ModelAPI
```

## CONVENTIONS

- All API methods return `(result, error)` tuple
- Use `_send_request()` from base client
- Async/await for all network operations
- Close client with `await client.close()`