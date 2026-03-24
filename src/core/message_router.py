#!/usr/bin/env python3
"""
消息路由模块（兼容层）

此文件保留用于向后兼容，实际实现已移动到 src/core/router/ 目录
"""

# 从新位置导入，保持向后兼容
from .router.message_router import MessageRouter
from .router.message_processor import MessageProcessor

__all__ = ['MessageRouter', 'MessageProcessor']