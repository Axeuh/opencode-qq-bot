# OpenCode Event Stream API Documentation

## Overview

OpenCode provides a real-time event stream via Server-Sent Events (SSE) at:
```
http://127.0.0.1:4091/global/event
```

This endpoint streams all events occurring within OpenCode, including:
- Server connection status
- Session state changes
- Message generation (streaming)
- Tool execution
- LSP diagnostics
- Todo updates

## Connection

### Endpoint
- **URL**: `http://127.0.0.1:4091/global/event`
- **Protocol**: Server-Sent Events (SSE)
- **Method**: GET
- **Content-Type**: `text/event-stream`

### Connection Example (Python)
```python
import requests

response = requests.get("http://127.0.0.1:4091/global/event", stream=True)
response.encoding = 'utf-8'

for line in response.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith("data:"):
            data = line[5:].strip()
            # Parse JSON data
```

---

## Event Structure

Each event follows this JSON structure:
```json
{
  "directory": "C:\\",
  "payload": {
    "type": "<event_type>",
    "properties": {
      // Event-specific properties
    }
  }
}
```

---

## Event Types

### 1. Server Events

#### `server.connected`
Triggered when a client connects to the event stream.

```json
{
  "payload": {
    "type": "server.connected",
    "properties": {}
  }
}
```

#### `server.heartbeat`
Periodic heartbeat sent every 10 seconds to maintain connection.

```json
{
  "payload": {
    "type": "server.heartbeat",
    "properties": {}
  }
}
```

---

### 2. Session Events

#### `session.status`
Reports the current session status.

```json
{
  "directory": "C:\\",
  "payload": {
    "type": "session.status",
    "properties": {
      "sessionID": "ses_xxx..."
    }
  }
}
```

#### `session.updated`
Triggered when session information changes.

```json
{
  "directory": "C:\\",
  "payload": {
    "type": "session.updated",
    "properties": {}
  }
}
```

#### `session.diff`
Reports changes/differences in session state.

```json
{
  "directory": "C:\\",
  "payload": {
    "type": "session.diff",
    "properties": {
      "sessionID": "ses_xxx..."
    }
  }
}
```

#### `session.created`
Triggered when a new session is created (e.g., when spawning a subagent).

```json
{
  "directory": "C:\\",
  "payload": {
    "type": "session.created",
    "properties": {
      "info": {
        "id": "ses_xxx...",
        "slug": "eager-river",
        "version": "1.2.26",
        "projectID": "global",
        "directory": "C:\\",
        "parentID": "ses_parent...",
        "title": "Task Name (@Sisyphus-Junior subagent)",
        "time": {
          "created": 1773660043195,
          "updated": 1773660043195
        }
      }
    }
  }
}
```

**Key Properties:**
- `parentID` - Parent session ID (when spawned from another session)
- `title` - Contains task description and agent type

---

### 3. Message Events

#### `message.part.updated`
Triggered when a message part is created or updated.

**Part Types:**
- `step-start` - Beginning of a reasoning step
- `reasoning` - AI thinking/reasoning content
- `tool` - Tool execution
- `step-finish` - End of a reasoning step

**Example - Step Start:**
```json
{
  "directory": "C:\\",
  "payload": {
    "type": "message.part.updated",
    "properties": {
      "part": {
        "id": "prt_xxx...",
        "sessionID": "ses_xxx...",
        "messageID": "msg_xxx...",
        "type": "step-start"
      }
    }
  }
}
```

**Example - Tool Execution:**
```json
{
  "directory": "C:\\",
  "payload": {
    "type": "message.part.updated",
    "properties": {
      "part": {
        "id": "prt_xxx...",
        "sessionID": "ses_xxx...",
        "messageID": "msg_xxx...",
        "type": "tool",
        "callID": "tool-xxx...",
        "tool": "bash",
        "state": {
          "status": "running",
          "input": {
            "command": "echo test"
          }
        }
      }
    }
  }
}
```

**Tool Status Values:**
- `pending` - Tool call queued
- `running` - Tool executing
- `completed` - Tool finished

#### `message.part.delta`
Streaming text content (reasoning or output).

```json
{
  "directory": "C:\\",
  "payload": {
    "type": "message.part.delta",
    "properties": {
      "sessionID": "ses_xxx...",
      "messageID": "msg_xxx...",
      "partID": "prt_xxx...",
      "field": "text",
      "delta": "Hello"
    }
  }
}
```

**Properties:**
- `field` - Usually "text" for text content
- `delta` - Incremental text chunk

#### `message.updated`
Triggered when a message is finalized or updated.

```json
{
  "directory": "C:\\",
  "payload": {
    "type": "message.updated",
    "properties": {
      "info": {
        "id": "msg_xxx...",
        "sessionID": "ses_xxx...",
        "role": "assistant",
        "modelID": "glm-5",
        "providerID": "alibaba-coding-plan-cn",
        "agent": "Sisyphus (Ultraworker)",
        "finish": "tool-calls",
        "tokens": {
          "total": 53974,
          "input": 223,
          "output": 26,
          "reasoning": 7,
          "cache": {
            "read": 43007,
            "write": 0
          }
        }
      }
    }
  }
}
```

**Finish Reasons:**
- `tool-calls` - Message ended with tool calls
- `stop` - Normal completion
- `error` - Error occurred

---

### 4. Todo Events

#### `todo.updated`
Triggered when todo list is modified.

```json
{
  "directory": "C:\\",
  "payload": {
    "type": "todo.updated",
    "properties": {
      "sessionID": "ses_xxx..."
    }
  }
}
```

---

### 5. LSP Events

#### `lsp.client.diagnostics`
Triggered when LSP diagnostics are available.

```json
{
  "directory": "C:\\",
  "payload": {
    "type": "lsp.client.diagnostics",
    "properties": {}
  }
}
```

---

### 6. TUI Events

#### `tui.toast.show`
Triggered when a toast notification is displayed in the TUI.

```json
{
  "directory": "C:\\",
  "payload": {
    "type": "tui.toast.show",
    "properties": {
      "title": "New Background Task",
      "message": "Queued (1):\n[Q] Task Name (Agent) - Queued",
      "variant": "info",
      "duration": 3000
    }
  }
}
```

**Variant Values:**
- `info` - Information message
- `success` - Success message
- `warning` - Warning message
- `error` - Error message

---

### 7. Task/Subagent Events

When spawning a subagent via `task()`, the following event sequence occurs:

#### Task Tool Execution
```json
{
  "directory": "C:\\",
  "payload": {
    "type": "message.part.updated",
    "properties": {
      "part": {
        "id": "prt_xxx...",
        "sessionID": "ses_parent...",
        "messageID": "msg_xxx...",
        "type": "tool",
        "callID": "tool-xxx...",
        "tool": "task",
        "state": {
          "status": "running",
          "input": {
            "category": "quick",
            "description": "Task description",
            "load_skills": [],
            "prompt": "Task prompt content...",
            "run_in_background": true,
            "subagent_type": "Sisyphus-Junior"
          },
          "title": "Task description",
          "time": {
            "start": 1773660043165
          }
        }
      }
    }
  }
}
```

**Task Flow:**
1. `message.part.updated` (tool=task, status=pending)
2. `message.part.updated` (tool=task, status=running)
3. `tui.toast.show` (notification)
4. `session.created` (new subagent session)
5. `session.updated` (session info)
6. `message.updated` (user message in new session)
7. `message.part.updated` (text part with prompt)

---

## Event Flow Example

### Typical Message Generation Flow:
```
1. message.part.updated (type: step-start)
2. message.part.updated (type: reasoning)
3. message.part.delta (multiple times - streaming text)
4. message.part.updated (type: tool, status: pending)
5. message.part.updated (type: tool, status: running)
6. message.part.updated (type: tool, status: completed)
7. message.part.updated (type: reasoning)
8. message.part.updated (type: step-finish)
9. message.updated (final message info)
10. session.status
11. session.updated
12. session.diff
```

---

## Tool Types Observed

| Tool Name | Description |
|-----------|-------------|
| `bash` | Shell command execution |
| `read` | File reading |
| `write` | File writing |
| `edit` | File editing |
| `grep` | Content search |
| `glob` | File pattern matching |
| `pty_read` | PTY output reading |
| `pty_write` | PTY input writing |
| `pty_spawn` | PTY process spawning |
| `pty_kill` | PTY process termination |
| `todowrite` | Todo list management |
| `skill_mcp` | MCP skill invocation |
| `lsp_diagnostics` | LSP diagnostics |
| `lsp_symbols` | LSP symbols |
| `lsp_goto_definition` | Go to definition |
| `lsp_find_references` | Find references |
| `webfetch` | Web content fetching |
| `websearch_web_search_exa` | Web search |
| `look_at` | Media file analysis |
| `compress` | Context compression |
| `task` | Subagent task spawning |
| `background_output` | Background task output |
| `background_cancel` | Cancel background task |

---

## Tool Event Examples

### `edit` Tool Event

```json
{
  "type": "message.part.updated",
  "properties": {
    "part": {
      "tool": "edit",
      "state": {
        "status": "running",
        "input": {
          "filePath": "D:\\path\\to\\file.txt",
          "oldString": "old text",
          "newString": "new text"
        },
        "metadata": {
          "diff": "Index: file.txt\n===================================================================\n--- file.txt\n+++ file.txt\n@@ -1,1 +1,1 @@\n-old text\n+new text\n",
          "filediff": {
            "file": "D:\\path\\to\\file.txt",
            "before": "old text",
            "after": "new text",
            "additions": 1,
            "deletions": 1
          }
        }
      }
    }
  }
}
```

### `write` Tool Event

```json
{
  "type": "message.part.updated",
  "properties": {
    "part": {
      "tool": "write",
      "state": {
        "status": "completed",
        "input": {
          "filePath": "D:\\path\\to\\file.txt",
          "content": "File content..."
        },
        "output": "Wrote file successfully."
      }
    }
  }
}
```

---

## File Events

### `file.edited`
Triggered when a file is edited.

```json
{
  "directory": "C:\\",
  "payload": {
    "type": "file.edited",
    "properties": {
      "file": "D:\\path\\to\\file.txt"
    }
  }
}
```

### `file.watcher.updated`
Triggered by file system watcher.

```json
{
  "directory": "C:\\",
  "payload": {
    "type": "file.watcher.updated",
    "properties": {
      "file": "D:\\path\\to\\file.txt",
      "event": "change"
    }
  }
}
```

**Event Values:**
- `add` - File created
- `change` - File modified
- `unlink` - File deleted

---

## Best Practices

### 1. Connection Handling
- Implement automatic reconnection with exponential backoff
- Handle connection timeouts gracefully
- Use UTF-8 encoding for proper text handling

### 2. Event Processing
- Process events asynchronously to avoid blocking
- Buffer delta events for text reconstruction
- Track part IDs for message assembly

### 3. Error Handling
- JSON parsing may fail for incomplete data
- Some events may have empty properties
- Handle missing fields gracefully

---

## Sample Code

### Simple Event Monitor (Python)
```python
# -*- coding: utf-8 -*-
import sys
import io
import requests
import json
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

EVENT_URL = "http://127.0.0.1:4091/global/event"

def listen():
    response = requests.get(EVENT_URL, stream=True, timeout=None)
    response.encoding = 'utf-8'
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str:
                    data = json.loads(data_str)
                    event_type = data.get("payload", {}).get("type", "unknown")
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {event_type}")

if __name__ == "__main__":
    listen()
```

---

---

## User Message Event

When a user sends a message (e.g., via QQ), the following event occurs:

### `message.updated` (user)

```json
{
  "directory": "C:\\",
  "payload": {
    "type": "message.updated",
    "properties": {
      "info": {
        "id": "msg_xxx...",
        "sessionID": "ses_xxx...",
        "role": "user",
        "time": {
          "created": 1773661048744
        },
        "summary": {
          "diffs": []
        },
        "agent": "Sisyphus (Ultraworker)",
        "model": {
          "providerID": "alibaba-coding-plan-cn",
          "modelID": "glm-5"
        }
      }
    }
  }
}
```

**Note:** The user message content is not directly visible in the event. The message text is processed internally.

**Event Flow when receiving user message:**
1. `message.updated` (role=user) - User message metadata
2. `message.updated` (role=assistant) - Assistant prepares to respond
3. `message.part.updated` (type=step-start)
4. `message.part.updated` (type=reasoning)
5. `message.part.delta` - Streaming response
6. ... continues with assistant response

---

## Version

- Document Version: 1.3
- Last Updated: 2026-03-16
- Based on: OpenCode Event Stream Analysis

## Event Types Summary

| Category | Event Types |
|----------|-------------|
| Server | `server.connected`, `server.heartbeat` |
| Session | `session.status`, `session.updated`, `session.diff`, `session.created` |
| Message | `message.part.updated`, `message.part.delta`, `message.updated` |
| Todo | `todo.updated` |
| LSP | `lsp.client.diagnostics` |
| TUI | `tui.toast.show` |
| File | `file.edited`, `file.watcher.updated` |