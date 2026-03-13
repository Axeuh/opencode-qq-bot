#!/usr/bin/env python3
"""
OpenCode API模块
用于处理与OpenCode API的HTTP交互，包括消息撤销、恢复、中止会话等操作。
"""

import logging
from typing import Optional, Tuple
import requests

from src.utils import config

# 初始化日志
logger = logging.getLogger(__name__)


class OpenCodeAPI:
    """OpenCode API处理类"""
    
    @staticmethod
    async def abort_session(session_id: str) -> Tuple[bool, str]:
        """中止OpenCode会话
        
        Args:
            session_id: 要中止的会话ID
            
        Returns:
            (成功标志, 消息)
        """
        try:
            # 构建URL
            url = f"http://127.0.0.1:4091/session/{session_id}/abort"
            
            # 构建请求头部
            headers = {
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                "Origin": "http://127.0.0.1:4091",
                "Referer": f"http://127.0.0.1:4091/Lw/session/{session_id}",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "sec-ch-ua": '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "x-opencode-directory": "/"
            }
            
            # 发送POST请求
            response = requests.post(
                url,
                cookies=config.OPENCODE_COOKIES,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return True, "会话已中止"
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
        except ImportError:
            return False, "requests库未安装，请安装: pip install requests"
        except Exception as e:
            logger.error(f"中止OpenCode会话失败: {e}", exc_info=True)
            return False, str(e)
    
    @staticmethod
    async def send_message(session_id: str, message: str, opencode_client=None) -> Tuple[bool, str]:
        """发送消息到OpenCode会话
        
        Args:
            session_id: 目标会话ID
            message: 要发送的消息
            opencode_client: OpenCode客户端实例（可选）
            
        Returns:
            (成功标志, 消息)
        """
        try:
            if not opencode_client:
                return False, "OpenCode客户端不可用"
            
            # 使用OpenCode客户端的send_message方法发送消息到指定会话
            # 设置create_if_not_exists=False，因为会话应该已经存在
            response, error = await opencode_client.send_message(
                message_text=message,
                session_id=session_id,
                create_if_not_exists=False
            )
            
            if error:
                logger.error(f"发送消息到OpenCode会话失败: {error}")
                return False, error
            
            logger.info(f"消息发送成功到会话: {session_id}, 内容: {message[:50]}...")
            return True, "消息发送成功"
            
        except Exception as e:
            logger.error(f"发送消息到OpenCode会话失败: {e}", exc_info=True)
            return False, str(e)
    
    @staticmethod
    async def revert_message(session_id: str, message_id: Optional[str] = None, part_id: Optional[str] = None) -> Tuple[bool, str]:
        """撤销OpenCode会话中的消息
        
        Args:
            session_id: 目标会话ID
            message_id: 消息ID（可选，如果不提供则撤销最后一条消息）
            part_id: 消息部分ID（可选）
            
        Returns:
            (成功标志, 消息)
        """
        try:
            # 构建URL
            url = f"http://127.0.0.1:4091/session/{session_id}/revert"
            
            # 构建请求头部
            headers = {
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                "Origin": "http://127.0.0.1:4091",
                "Referer": f"http://127.0.0.1:4091/Lw/session/{session_id}",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "sec-ch-ua": '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "x-opencode-directory": "/"
            }
            
            # 只有当有请求体时才添加Content-Type头部
            if message_id or part_id:
                headers["Content-Type"] = "application/json"
            
            # 构建请求体
            payload = {}
            if message_id:
                payload["messageID"] = message_id
            if part_id:
                payload["partID"] = part_id
            
            # 发送POST请求
            if payload:  # 如果有请求体，发送JSON
                response = requests.post(
                    url,
                    cookies=config.OPENCODE_COOKIES,
                    headers=headers,
                    json=payload,
                    timeout=10
                )
            else:  # 如果没有请求体，不发送JSON体
                response = requests.post(
                    url,
                    cookies=config.OPENCODE_COOKIES,
                    headers=headers,
                    timeout=10
                )
            
            if response.status_code == 200:
                # 尝试解析JSON响应
                try:
                    result = response.json()
                    
                    # 处理布尔值响应
                    if isinstance(result, bool):
                        if result:
                            return True, "操作成功"
                        else:
                            return False, "操作失败（API返回false）"
                    
                    # 处理字典响应
                    elif isinstance(result, dict):
                        # 检查是否是错误响应
                        if "name" in result and "data" in result:
                            # 错误对象格式：{"name": "UnknownError", "data": {"message": "...", ...}}
                            error_data = result.get("data", {})
                            error_message = error_data.get("message", str(error_data))
                            return False, f"API错误: {error_message}"
                        
                        # 检查是否有success字段
                        success = result.get("success", False)
                        message = result.get("message", "操作完成")
                        
                        # 如果没有success字段，但响应是200，假设成功
                        if "success" not in result:
                            return True, message
                        
                        return success, message
                    
                    # 处理其他类型的响应
                    else:
                        return True, f"响应: {result}"
                        
                except Exception as json_error:
                    # JSON解析失败，返回原始文本
                    response_text = response.text.strip()
                    if response_text:
                        return True, response_text
                    else:
                        return True, "操作完成"
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
        except ImportError:
            return False, "requests库未安装，请安装: pip install requests"
        except Exception as e:
            logger.error(f"撤销OpenCode消息失败: {e}", exc_info=True)
            return False, str(e)
    
    @staticmethod
    async def unrevert_messages(session_id: str) -> Tuple[bool, str]:
        """恢复所有撤销的OpenCode消息
        
        Args:
            session_id: 目标会话ID
            
        Returns:
            (成功标志, 消息)
        """
        try:
            # 构建URL
            url = f"http://127.0.0.1:4091/session/{session_id}/unrevert"
            
            # 构建请求头部
            headers = {
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                "Origin": "http://127.0.0.1:4091",
                "Referer": f"http://127.0.0.1:4091/Lw/session/{session_id}",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "sec-ch-ua": '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "x-opencode-directory": "/"
            }
            
            # 发送POST请求
            response = requests.post(
                url,
                cookies=config.OPENCODE_COOKIES,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                # 尝试解析JSON响应
                try:
                    result = response.json()
                    
                    # 处理布尔值响应
                    if isinstance(result, bool):
                        if result:
                            return True, "操作成功"
                        else:
                            return False, "操作失败（API返回false）"
                    
                    # 处理字典响应
                    elif isinstance(result, dict):
                        # 检查是否是错误响应
                        if "name" in result and "data" in result:
                            # 错误对象格式：{"name": "UnknownError", "data": {"message": "...", ...}}
                            error_data = result.get("data", {})
                            error_message = error_data.get("message", str(error_data))
                            return False, f"API错误: {error_message}"
                        
                        # 检查是否有success字段
                        success = result.get("success", False)
                        message = result.get("message", "操作完成")
                        
                        # 如果没有success字段，但响应是200，假设成功
                        if "success" not in result:
                            return True, message
                        
                        return success, message
                    
                    # 处理其他类型的响应
                    else:
                        return True, f"响应: {result}"
                        
                except Exception as json_error:
                    # JSON解析失败，返回原始文本
                    response_text = response.text.strip()
                    if response_text:
                        return True, response_text
                    else:
                        return True, "操作完成"
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
        except ImportError:
            return False, "requests库未安装，请安装: pip install requests"
        except Exception as e:
            logger.error(f"恢复OpenCode消息失败: {e}", exc_info=True)
            return False, str(e)