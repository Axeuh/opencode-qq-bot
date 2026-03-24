# Message Router Module

**Generated:** 2026-03-24
**Modules:** 3 Python files
**Purpose:** Message routing and processing

## STRUCTURE

```
router/
├── message_router.py    # Routing logic (450 lines)
├── message_processor.py # Processing helpers (471 lines)
└── __init__.py
```

## ROUTING FLOW

```
Message received
    → is_whitelisted? (check user/group)
    → is_command? (starts with /)
    → Yes: CommandSystem.handle_command()
    → No: OpenCodeForwarder.send_to_opencode()
```

## KEY CLASSES

| Class | Purpose |
|-------|---------|
| `MessageRouter` | Main router, whitelist check |
| `MessageProcessor` | Message preprocessing |

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add routing rule | message_router.py |
| Modify whitelist | message_router.py |
| Preprocess messages | message_processor.py |

## WHITELIST CHECK

```python
def should_process_message(user_id, group_id):
    if group_id:
        return group_id in GROUP_WHITELIST
    return user_id in USER_WHITELIST
```

## CONVENTIONS

- Return `True` if handled locally (command)
- Return `False` to forward to OpenCode
- Check whitelist before any processing