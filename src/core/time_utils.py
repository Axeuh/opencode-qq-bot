#!/usr/bin/env python3
"""
时间工具模块
提供跨平台兼容的时间格式化功能
"""

import sys
import time
from typing import Optional


def get_cross_platform_time() -> str:
    """获取跨平台兼容的时间字符串，格式：YYYY/MM/DD HH:MM
    
    跨平台兼容性处理：
    - Windows: 使用 %#m 和 %#d 去掉前导零
    - Linux/macOS: 使用 %-m 和 %-d 去掉前导零
    
    Returns:
        格式化后的时间字符串
    """
    if sys.platform == "win32":
        # Windows平台
        format_str = "%Y/%#m/%#d %H:%M"
    else:
        # Linux/macOS平台
        format_str = "%Y/%-m/%-d %H:%M"
    
    return time.strftime(format_str)


def format_timestamp(timestamp: Optional[float] = None, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """将时间戳格式化为字符串
    
    Args:
        timestamp: 时间戳，默认为当前时间
        format_str: 格式字符串
        
    Returns:
        格式化后的时间字符串
    """
    if timestamp is None:
        timestamp = time.time()
    return time.strftime(format_str, time.localtime(timestamp))


def get_current_time(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前时间字符串
    
    Args:
        format_str: 格式字符串
        
    Returns:
        格式化后的当前时间字符串
    """
    return time.strftime(format_str)


if __name__ == "__main__":
    # 测试代码
    print(f"当前时间（跨平台格式）: {get_cross_platform_time()}")
    print(f"当前时间（标准格式）: {get_current_time()}")
    print(f"时间戳格式化: {format_timestamp()}")
    print("时间工具模块测试完成")