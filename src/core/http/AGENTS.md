# HTTP Server Module

**Generated:** 2026-03-24
**Modules:** 10 Python files
**Endpoints:** 36 HTTP routes

## STRUCTURE

```
http/
├── server.py            # HTTPServer class (297 lines)
├── routes.py            # Route definitions (182 lines)
├── middleware.py        # Auth middleware (156 lines)
├── auth_handler.py      # Login/password (357 lines)
├── session_endpoints.py # Session API (440 lines)
├── task_endpoints.py    # Task API (328 lines)
├── config_endpoints.py  # Config API (477 lines)
├── upload_handler.py    # File upload (215 lines)
└── opencode_proxy.py    # OpenCode proxy (298 lines)
```

## ENDPOINTS

| Category | Routes | File |
|----------|--------|------|
| Auth | `/api/login`, `/api/password/*` | auth_handler.py |
| Session | `/api/session/*` | session_endpoints.py |
| Task | `/api/task/*` | task_endpoints.py |
| Config | `/api/agents/*`, `/api/model/*` | config_endpoints.py |
| Upload | `/api/upload` | upload_handler.py |
| OpenCode | `/api/opencode/*` | opencode_proxy.py |

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add new endpoint | routes.py + create handler |
| Modify auth | auth_handler.py, middleware.py |
| Session API | session_endpoints.py |
| Task API | task_endpoints.py |
| OpenCode proxy | opencode_proxy.py |

## KEY CLASSES

| Class | Purpose |
|-------|---------|
| `HTTPServer` | Main server, route setup |
| `AuthMiddleware` | Token validation, rate limiting |
| `AuthHandler` | Login, password management |

## AUTH FLOW

```
Request → Middleware (token check)
    → Handler (business logic)
    → Response (JSON)
```

## CONVENTIONS

- All handlers are async methods
- Return `web.json_response()`
- Use `@require_auth` decorator for protected routes
- Error responses: `{"error": "message"}`