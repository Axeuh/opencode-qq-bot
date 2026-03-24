# File Handling Module

**Generated:** 2026-03-24
**Modules:** 4 Python files
**Purpose:** File download/upload with three-tier fallback

## STRUCTURE

```
file/
├── file_handler.py      # Coordinator (275 lines)
├── path_resolver.py     # Path utilities (185 lines)
├── validator.py         # File validation (142 lines)
└── downloader.py        # Download core (533 lines)
```

## THREE-TIER FALLBACK

```
1. HTTP API (localhost:3001) - Preferred
    ↓ (fallback)
2. WebSocket API (localhost:3002)
    ↓ (fallback)
3. Path matching (NapCat temp dir)
```

## KEY CLASSES

| Class | Purpose |
|-------|---------|
| `FileHandler` | Main coordinator |
| `Downloader` | Download logic |
| `PathResolver` | WSL/Windows path conversion |
| `Validator` | Size/type validation |

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Download file | downloader.py |
| Convert paths | path_resolver.py |
| Validate file | validator.py |
| Handle forward msg | file_handler.py |

## SUPPORTED TYPES

- Images (download to `downloads/`)
- Videos (download to `downloads/`)
- Audio (download to `downloads/`)
- Documents (path extraction)
- Forward messages (parse content)

## CONVENTIONS

- Always return `(result, error)` tuple
- Use async for all downloads
- Handle WSL path conversion
- Max file size from config