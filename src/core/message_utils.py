#!/usr/bin/env python3
"""
消息工具函数模块
提供消息处理相关的工具函数，如白名单检查、命令解析等
"""

import logging
from typing import Optional
from src.utils import config

logger = logging.getLogger(__name__)


def check_whitelist(message_type: str, user_id: Optional[int], group_id: Optional[int]) -> bool:
    """检查消息是否来自白名单
    
    Args:
        message_type: 消息类型 ('private' 或 'group')
        user_id: 用户ID（私聊时）
        group_id: 群ID（群聊时）
        
    Returns:
        True如果消息来自白名单，否则False
    """
    if not config.ENABLED_FEATURES.get('whitelist_filter', True):
        return True  # 如果白名单过滤未启用，允许所有消息
    
    # 私聊消息：检查用户是否在QQ用户白名单中
    if message_type == 'private' and user_id:
        if user_id in config.QQ_USER_WHITELIST:
            return True
        else:
            logger.debug(f"忽略非白名单用户消息: QQ={user_id}")
            return False
    
    # 群聊消息：检查群是否在群聊白名单中
    elif message_type == 'group' and group_id:
        if group_id in config.GROUP_WHITELIST:
            return True
        else:
            logger.debug(f"忽略非白名单群消息: 群={group_id}")
            return False
    
    # 其他情况（如未识别的消息类型）
    return False


# 其他工具函数可以在此添加
# 例如：is_mentioning_bot, should_process_message, is_command, extract_command 等