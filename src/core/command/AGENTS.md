# Command System Module

**Generated:** 2026-03-24
**Modules:** 8 Python files
**Commands:** 12 QQ commands

## STRUCTURE

```
command/
├── command_system.py    # Router (274 lines)
├── utils.py             # Helpers (185 lines)
├── help_handler.py      # /help (142 lines)
├── session_handler.py   # /new, /session, /stop, /path (468 lines)
├── model_handler.py     # /agent, /model (312 lines)
├── task_handler.py      # /command, /reload (340 lines)
├── message_handler.py   # /undo, /redo, /compact (298 lines)
└── __init__.py
```

## COMMANDS

| Command | Handler | Purpose |
|---------|---------|---------|
| `/help` | HelpHandler | Show help |
| `/new` | SessionHandler | Create session |
| `/session` | SessionHandler | Switch session |
| `/stop` | SessionHandler | Stop session |
| `/path` | SessionHandler | Set directory |
| `/agent` | ModelHandler | List/switch agent |
| `/model` | ModelHandler | List/switch model |
| `/command` | TaskHandler | Execute slash command |
| `/reload` | TaskHandler | Reload config |
| `/undo` | MessageHandler | Revert message |
| `/redo` | MessageHandler | Unrevert messages |
| `/compact` | MessageHandler | Compress context |

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add new command | Create handler file, register in command_system.py |
| Modify session commands | session_handler.py |
| Modify model commands | model_handler.py |
| Modify message commands | message_handler.py |

## COMMAND FLOW

```
QQ Message (/help)
    → MessageRouter.is_command()
    → CommandSystem.handle_command()
    → HelpHandler.handle_help()
    → Reply via ApiSender
```

## CONVENTIONS

- Each handler is a class with async methods
- Register in `command_system.py` COMMAND_HANDLERS dict
- Return `(success, message)` tuple
- Use ApiSender for replies