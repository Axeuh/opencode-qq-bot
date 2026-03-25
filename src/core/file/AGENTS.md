# 文件处理模块

**生成日期:** 2026-03-25
**模块数:** 4 Python 文件
**用途:** 文件下载/上传，三层回退机制

## 目录结构

```
file/
├── file_handler.py      # 协调器 (275 行)
├── path_resolver.py     # 路径工具 (185 行)
├── validator.py         # 文件验证 (142 行)
└── downloader.py        # 下载核心 (533 行)
```

## 三层回退机制

```
1. HTTP API (localhost:3001) - 首选
    ↓ (回退)
2. WebSocket API (localhost:3002)
    ↓ (回退)
3. 路径匹配 (NapCat 临时目录)
```

## 核心类

| 类名 | 用途 |
|-------|---------|
| `FileHandler` | 主协调器 |
| `Downloader` | 下载逻辑 |
| `PathResolver` | WSL/Windows 路径转换 |
| `Validator` | 大小/类型验证 |

## 查找指南

| 任务 | 位置 |
|------|----------|
| 下载文件 | downloader.py |
| 转换路径 | path_resolver.py |
| 验证文件 | validator.py |
| 处理转发消息 | file_handler.py |

## 支持的文件类型

- 图片 (下载到 `downloads/`)
- 视频 (下载到 `downloads/`)
- 音频 (下载到 `downloads/`)
- 文档 (路径提取)
- 转发消息 (解析内容)

## 编码规范

- 始终返回 `(result, error)` 元组
- 所有下载使用异步
- 处理 WSL 路径转换
- 最大文件大小从配置读取