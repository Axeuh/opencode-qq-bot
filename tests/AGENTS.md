# Test Architecture

**Generated:** 2026-03-24
**Files:** 17 Python test scripts
**Framework:** Custom (no pytest/unittest)

## STRUCTURE

```
tests/
├── test_commands.py           # Command tests (10 commands)
├── test_connection.py         # WebSocket connection
├── test_http_api.py           # HTTP API tests
├── test_session_manager_basic.py
├── debug_interface.py         # Test utility class
├── test_get_msg*.py           # Message API tests (4 files)
├── test_file*.py              # File handling tests (2 files)
├── test_get_forward_msg.py    # Forward message tests
└── test_lsp_config.py         # LSP config tests
```

## TEST PATTERNS

### No Traditional Framework
- No pytest, unittest, or jest
- Each file is standalone: `python test_xxx.py`
- Integration tests (connect to real services)
- Log-driven verification

### DebugInterface Class

```python
from debug_interface import DebugInterface

debug = DebugInterface()
await debug.initialize()
await debug.send_private_message(user_id, "/help")
await debug.close()
```

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Test commands | test_commands.py |
| Test connection | test_connection.py |
| Mock QQ messages | debug_interface.py |
| Test file handling | test_file*.py |
| Test HTTP API | test_http_api.py |

## SERVICE DEPENDENCIES

Tests require running services:
- NapCat WebSocket: `ws://localhost:3002`
- NapCat HTTP API: `http://localhost:3001`
- OpenCode Service: `http://127.0.0.1:4091`

## RUNNING TESTS

```bash
python tests/test_commands.py
python tests/test_connection.py
python tests/test_http_api.py
```

## CONVENTIONS

- All tests use `asyncio.run()`
- Log results with `logging` module
- Return `(success, message)` tuples
- Manual verification for some tests (check QQ reply)

## COVERAGE

| Module | Test File |
|--------|-----------|
| Commands | test_commands.py |
| Connection | test_connection.py |
| HTTP API | test_http_api.py |
| Session | test_session_manager_basic.py |
| File handling | test_file_download_api.py |
| Forward messages | test_get_forward_msg.py |