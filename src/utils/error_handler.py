"""
错误处理工具模块
提供统一的错误处理装饰器和工具函数
"""

import logging
import asyncio
from functools import wraps
from typing import Callable, Tuple, Any, Optional

logger = logging.getLogger(__name__)


def handle_errors(
    default_return: Any = None,
    log_level: int = logging.ERROR,
    include_exception: bool = True
) -> Callable:
    """
    错误处理装饰器，返回 (result, error) 元组
    
    Args:
        default_return: 发生错误时的默认返回值
        log_level: 日志级别
        include_exception: 是否在返回中包含异常信息
        
    Returns:
        装饰后的函数，返回 (result, error) 元组
        - result: 函数执行结果或 default_return
        - error: 错误信息字符串，成功时为 None
        
    Example:
        @handle_errors(default_return=None)
        async def risky_operation() -> dict:
            # 可能抛出异常的操作
            return {"status": "ok"}
        
        # 使用
        result, error = await risky_operation()
        if error:
            print(f"操作失败: {error}")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Tuple[Any, Optional[str]]:
            try:
                result = await func(*args, **kwargs)
                # 如果函数本身返回元组，检查是否已经是 (result, error) 格式
                if isinstance(result, tuple) and len(result) == 2:
                    if result[1] is None or isinstance(result[1], str):
                        return result
                return (result, None)
            except Exception as e:
                error_msg = str(e)
                logger.log(log_level, f"{func.__name__} 执行失败: {error_msg}")
                if include_exception:
                    return (default_return, error_msg)
                return (default_return, None)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Tuple[Any, Optional[str]]:
            try:
                result = func(*args, **kwargs)
                if isinstance(result, tuple) and len(result) == 2:
                    return result
                return (result, None)
            except Exception as e:
                error_msg = str(e)
                logger.log(log_level, f"{func.__name__} 执行失败: {error_msg}")
                if include_exception:
                    return (default_return, error_msg)
                return (default_return, None)
        
        # 根据函数类型返回对应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def safe_execute(
    func: Callable,
    *args,
    default_return: Any = None,
    **kwargs
) -> Tuple[Any, Optional[str]]:
    """
    安全执行函数，捕获所有异常
    
    Args:
        func: 要执行的函数
        *args: 位置参数
        default_return: 发生错误时的默认返回值
        **kwargs: 关键字参数
        
    Returns:
        (result, error) 元组
    """
    try:
        result = func(*args, **kwargs)
        return (result, None)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"安全执行失败: {error_msg}")
        return (default_return, error_msg)


async def safe_execute_async(
    func: Callable,
    *args,
    default_return: Any = None,
    **kwargs
) -> Tuple[Any, Optional[str]]:
    """
    安全执行异步函数，捕获所有异常
    
    Args:
        func: 要执行的异步函数
        *args: 位置参数
        default_return: 发生错误时的默认返回值
        **kwargs: 关键字参数
        
    Returns:
        (result, error) 元组
    """
    try:
        result = await func(*args, **kwargs)
        return (result, None)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"安全执行异步函数失败: {error_msg}")
        return (default_return, error_msg)


class ErrorContext:
    """
    错误上下文管理器，用于捕获和记录错误
    
    Example:
        async with ErrorContext("处理消息") as ctx:
            result = await risky_operation()
            
        if ctx.error:
            print(f"错误: {ctx.error}")
    """
    
    def __init__(self, operation_name: str = "操作"):
        self.operation_name = operation_name
        self.error: Optional[str] = None
        self.result: Any = None
    
    async def __aenter__(self) -> 'ErrorContext':
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            self.error = str(exc_val)
            logger.error(f"{self.operation_name}失败: {self.error}")
            return True  # 抑制异常
        return False
    
    def __enter__(self) -> 'ErrorContext':
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            self.error = str(exc_val)
            logger.error(f"{self.operation_name}失败: {self.error}")
            return True
        return False