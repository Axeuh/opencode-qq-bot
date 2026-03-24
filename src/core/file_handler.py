#!/usr/bin/env python3
"""
文件处理模块 - 处理QQ机器人文件上传和下载

此文件为向后兼容层，实际实现已重构到 src/core/file/ 子模块。

重构后的模块结构:
    - file/file_handler.py: FileHandler 核心类
    - file/downloader.py: 文件下载逻辑
    - file/path_resolver.py: 路径解析和 WSL 转换
    - file/validator.py: 文件验证

公共 API 保持不变:
    - FileHandler.download_file()
    - FileHandler.process_file_message()
    - FileHandler.get_file_type_directory()
    - FileHandler.cleanup_old_files()
    - FileHandler.get_download_stats()
"""

# 从新模块导入，保持向后兼容
from .file import FileHandler, FileDownloader, FileValidator, PathResolver

__all__ = [
    "FileHandler",
    "FileDownloader", 
    "FileValidator",
    "PathResolver",
]