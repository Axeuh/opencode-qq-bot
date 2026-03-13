#!/usr/bin/env python3
"""
OpenCode集成模块
负责OpenCode客户端初始化、消息转发和API操作
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING, Callable, Awaitable

if TYPE_CHECKING:
    from src.opencode.opencode_client import OpenCodeClient, OpenCodeClientSync
    from src.session.session_manager import SessionManager
    from .command_system import CommandSystem

logger = logging.getLogger(__name__)


def _should_silent_error(error_info: dict) -> bool:
    """判断错误是否应该静默（不显示给用户）
    
    Args:
        error_info: 错误信息字典，包含 name、data 等字段
        
    Returns:
        True 表示应该静默，False 表示应该显示给用户
    """
    # 获取错误名称
    error_name = error_info.get("name", "")
    
    # 需要静默的错误类型列表
    SILENT_ERRORS = [
        "MessageAbortedError",  # 会话被打断（如戳一戳导致的 abort）
        "SessionAbortedError",  # 会话中止
        "OperationAbortedError",  # 操作被中止
    ]
    
    # 检查是否在静默列表中
    if error_name in SILENT_ERRORS:
        logger.debug(f"静默错误：{error_name} - {error_info.get('data', {}).get('message', '')}")
        return True
    
    return False


class OpenCodeIntegration:
    """OpenCode集成管理器"""
    
    def __init__(self, config_manager):
        """初始化OpenCode集成
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.opencode_client: Optional["OpenCodeClient"] = None
        self.opencode_sync_client: Optional["OpenCodeClientSync"] = None
        self.session_manager: Optional["SessionManager"] = None
        self.command_system: Optional["CommandSystem"] = None
        
        # OpenCode可用性标志
        self.opencode_available = False
        
        # 初始化OpenCode客户端（如果可用）
        self._check_opencode_availability()
        if self.opencode_available:
            self._init_opencode_integration()
    
    def _check_opencode_availability(self) -> None:
        """检查OpenCode模块是否可用"""
        try:
            from src.opencode.opencode_client import OpenCodeClient, OpenCodeClientSync
            from src.session.session_manager import SessionManager, get_session_manager
            self.opencode_available = True
            logger.debug("OpenCode模块可用")
        except ImportError as e:
            logger.warning(f"OpenCode模块导入失败: {e}，OpenCode功能将不可用")
            self.opencode_available = False
    
    def _init_opencode_integration(self) -> None:
        """初始化OpenCode客户端、会话管理器和命令系统"""
        if not self.opencode_available:
            logger.warning("OpenCode模块不可用，跳过初始化")
            return
        
        try:
            from src.opencode.opencode_client import OpenCodeClient, OpenCodeClientSync
            from src.session.session_manager import SessionManager, get_session_manager
            
            opencode_config = self.config_manager.opencode_config
            
            # 初始化异步OpenCode客户端
            auth_config = opencode_config["auth"]
            self.opencode_client = OpenCodeClient(
                base_url=opencode_config["base_url"],
                username=auth_config.get("username"),
                password=auth_config.get("password"),
                token=auth_config.get("token"),
                cookies=opencode_config["cookies"],
                timeout=opencode_config["timeout"],
                directory=opencode_config["directory"],
                default_agent=opencode_config["default_agent"],
                default_model=opencode_config["default_model"],
                default_provider=opencode_config["default_provider"]
            )
            
            # 初始化同步OpenCode客户端（用于队列处理）
            self.opencode_sync_client = OpenCodeClientSync(
                base_url=opencode_config["base_url"],
                username=auth_config.get("username"),
                password=auth_config.get("password"),
                token=auth_config.get("token"),
                cookies=opencode_config["cookies"],
                timeout=opencode_config["timeout"],
                directory=opencode_config["directory"],
                default_agent=opencode_config["default_agent"],
                default_model=opencode_config["default_model"],
                default_provider=opencode_config["default_provider"]
            )
            
            # 初始化会话管理器
            self.session_manager = get_session_manager()
            
            # 初始化命令系统（如果可用）
            try:
                from .command_system import CommandSystem
                self.command_system = CommandSystem(
                    session_manager=self.session_manager,
                    opencode_client=self.opencode_client,
                    send_reply_callback=None  # 调试接口中不使用回复回调
                )
            except ImportError as e:
                logger.warning(f"命令系统导入失败: {e}")
                self.command_system = None

            
        except Exception as e:
            logger.error(f"OpenCode集成初始化失败: {e}", exc_info=True)
            self.opencode_available = False
    
    async def close(self) -> None:
        """关闭OpenCode客户端"""
        if self.opencode_client:
            await self.opencode_client.close()
        if self.opencode_sync_client:
            self.opencode_sync_client.close()
    
    async def forward_to_opencode(self, message_type: str, group_id: Optional[int],
                                user_id: Optional[int], plain_text: str,
                                send_reply_callback: Optional[Callable[[str, Optional[int], Optional[int], str], Awaitable[None]]] = None) -> None:
        """将消息转发到OpenCode
        
        Args:
            message_type: 消息类型 ('private' 或 'group')
            group_id: 群号（群聊时）
            user_id: 用户QQ号
            plain_text: 纯文本消息
            send_reply_callback: 发送回复的回调函数，接受参数 (message_type, group_id, user_id, reply)
        """
        if not self.opencode_available or not self.opencode_client:
            reply = "OpenCode集成当前不可用，无法处理消息。"
            if send_reply_callback:
                await send_reply_callback(message_type, group_id, user_id, reply)
            return
        
        if not user_id:
            logger.warning("无法转发消息到OpenCode: user_id为空")
            return
        
        try:
            # 获取配置
            config = self.config_manager.opencode_config
            system_prompt_enabled = config["system_prompt"].get("enabled", False)
            suppress_opencode_replies = config["system_prompt"].get("suppress_opencode_replies", True)
            system_prompt_text = config["system_prompt"].get("prompt_text", "")
            max_length = config["message_config"].get("max_message_length", 5000)
            
            # 获取用户的会话ID
            session_id = None
            if self.session_manager:
                session = self.session_manager.get_user_session(user_id)
                if session:
                    session_id = session.session_id
            
            # 从用户会话中获取 directory 配置
            user_directory = session.directory if session else config.OPENCODE_DIRECTORY
            
            # 如果没有会话ID，创建一个新会话
            if not session_id:
                if self.session_manager and self.opencode_client:
                    # 创建新会话（使用用户配置的 directory）
                    new_session_id, error = await self.opencode_client.create_session(
                        title=f"QQ 用户_{user_id}",
                        directory=user_directory
                    )
                    if new_session_id and not error:
                        session_id = new_session_id
                        # 在会话管理器中注册新会话
                        self.session_manager.create_user_session(
                            user_id=user_id,
                            session_id=session_id,
                            title=f"QQ用户_{user_id}",
                            group_id=group_id
                        )
                        logger.info(f"为用户 {user_id} 创建新会话：{session_id} (目录：{user_directory})")
                    else:
                        error_msg = error or "未知错误"
                        reply = f"创建会话失败: {error_msg}"
                        if send_reply_callback:
                            await send_reply_callback(message_type, group_id, user_id, reply)
                        return
                else:
                    reply = "无法创建会话：会话管理器或客户端不可用"
                    if send_reply_callback:
                        await send_reply_callback(message_type, group_id, user_id, reply)
                    return
            
            # 检查是否需要发送系统提示词
            session = None
            if self.session_manager:
                session = self.session_manager.get_user_session(user_id)
            
            # 构建要发送的消息
            message_to_send = plain_text
            
            # 检查是否需要发送系统提示词
            if system_prompt_enabled and system_prompt_text and session and not session.system_prompt_sent:
                # 添加用户信息前缀（区分群聊和私聊）
                display_name = f"QQ用户_{user_id}"  # 这里没有user_name参数，使用默认
                if message_type == "group" and group_id:
                    # 群聊消息：包含群号和用户信息
                    user_info = f"[QQ用户 \"{user_id}\" 在QQ群 \"{group_id}\" 发送了一个消息, qq用户名称: {display_name}，你需要在群里回复]"
                else:
                    # 私聊消息：只包含用户信息
                    user_info = f"[QQ用户{user_id}发送了一个消息，请私聊回复, qq用户名称: {display_name}]"
                
                # 将系统提示词、用户信息和消息合并
                message_to_send = f"系统提示词: {system_prompt_text}\n\n{user_info}\n用户消息: {plain_text}"
                logger.info(f"首次消息，包含系统提示词，会话ID: {session_id}")
                
                # 更新会话状态，标记系统提示词已发送
                session.system_prompt_sent = True
                # 保存会话状态
                if self.session_manager:
                    try:
                        self.session_manager.save_to_file()
                    except Exception as e:
                        logger.warning(f"保存会话状态失败（不影响当前功能）: {e}")
            else:
                # 非首次消息，添加用户信息前缀
                display_name = f"QQ用户_{user_id}"  # 这里没有user_name参数，使用默认
                if message_type == "group" and group_id:
                    # 群聊消息：包含群号和用户信息
                    message_to_send = f"[QQ用户{user_id}在QQ群{group_id}发送了一个消息, qq用户名称: {display_name}，你需要在群里回复]\n{plain_text}"
                else:
                    # 私聊消息：只包含用户信息
                    message_to_send = f"[QQ用户{user_id}发送了一个消息，请私聊回复, qq用户名称: {display_name}]\n{plain_text}"
            
            # 发送消息到OpenCode
            logger.info(f"转发消息到OpenCode: 用户={user_id}, 会话={session_id}, 消息长度={len(message_to_send)}")
            
            # 截断过长的消息
            if len(message_to_send) > max_length:
                original_length = len(message_to_send)
                message_to_send = message_to_send[:max_length] + f"...（消息过长，已截断，原长{original_length}字符）"
                logger.warning(f"消息过长，已截断: {original_length} -> {max_length}")
            
            # 从用户会话中获取 agent/model/provider/directory 配置
            user_agent = session.agent if session else config.OPENCODE_DEFAULT_AGENT
            user_model = session.model if session else config.OPENCODE_DEFAULT_MODEL
            user_provider = session.provider if session else config.OPENCODE_DEFAULT_PROVIDER
            user_directory = session.directory if session else config.OPENCODE_DIRECTORY
            
            logger.debug(f"使用用户配置：agent={user_agent}, model={user_model}, provider={user_provider}, directory={user_directory}")
            
            # 发送消息（使用用户配置的 agent/model/provider/directory）
            response, error = await self.opencode_client.send_message(
                message_text=message_to_send,
                session_id=session_id,
                agent=user_agent,
                model=user_model,
                provider=user_provider,
                directory=user_directory
            )
            
            if error:
                reply = f"OpenCode处理失败: {error}"
                logger.error(f"OpenCode处理失败: {error}")
                if send_reply_callback:
                    await send_reply_callback(message_type, group_id, user_id, reply)
                return
            
            # 提取回复文本
            if response and isinstance(response, dict) and response.get("parts"):
                # 从parts中提取文本回复
                text_parts = []
                for part in response.get("parts", []):
                    if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                        text_parts.append(part.get("text"))
                
                if text_parts:
                    reply = "\n\n".join(text_parts)
                    # 截断过长的回复
                    if len(reply) > max_length:
                        reply = reply[:max_length] + "...（回复过长，已截断）"
                    
                    # 根据配置决定是否发送回复
                    if suppress_opencode_replies:
                        logger.info(f"OpenCode回复已接收但抑制发送 (用户={user_id}, 长度={len(reply)})")
                    else:
                        if send_reply_callback:
                            await send_reply_callback(message_type, group_id, user_id, reply)
                            logger.info(f"OpenCode回复发送成功，长度: {len(reply)}")
                else:
                    # 无文本回复，只记录日志，不发送任何回复
                    logger.info(f"OpenCode已处理，但未返回文本回复 (用户={user_id})")
            else:
                # 响应格式异常，检查是否包含错误信息
                if response and isinstance(response, dict):
                    # 提取 response 中的 error 字段
                    error_info = response.get("error", response.get("message", str(response)))
                    
                    # 检查是否是应该静默的错误类型
                    if isinstance(error_info, dict) and _should_silent_error(error_info):
                        # 静默错误，只记录日志，不发送给用户
                        logger.info(f"OpenCode 返回可忽略错误 (用户={user_id}, 会话={session_id}): {error_info.get('name')}")
                        return  # 完成，不发送错误提示
                    
                    # 其他错误类型，发送给用户
                    reply = f"OpenCode 错误：{error_info}"
                else:
                    reply = "OpenCode 响应格式异常"
                
                if send_reply_callback:
                    await send_reply_callback(message_type, group_id, user_id, reply)
                logger.warning("OpenCode 响应格式异常 (用户=%s, 会话=%s)", user_id, session_id)
                return  # 完成（格式异常）
            
        except Exception as e:
            logger.error(f"转发消息失败: {e}")
            reply = f"处理消息时发生错误: {str(e)}"
            if send_reply_callback:
                await send_reply_callback(message_type, group_id, user_id, reply)
    async def forward_to_opencode_sync(self, message_type: str, group_id: Optional[int],
                                      user_id: Optional[int], plain_text: str,
                                      user_name: Optional[str] = None,
                                      send_reply_callback: Optional[Callable[[str, Optional[int], Optional[int], str], Awaitable[None]]] = None) -> None:
        """同步版本的OpenCode转发（用于队列处理）
        
        这是forward_to_opencode的简化版本，去除了队列逻辑，直接发送回复。
        
        Args:
            message_type: 消息类型 ('private' 或 'group')
            group_id: 群号（群聊时）
            user_id: 用户QQ号
            plain_text: 纯文本消息
            user_name: 用户显示名称（可选）
            send_reply_callback: 发送回复的回调函数，接受参数 (message_type, group_id, user_id, reply)
        """
        if not self.opencode_available or not self.opencode_client:
            logger.warning(f"OpenCode不可用，丢弃消息: user_id={user_id}, opencode_available={self.opencode_available}, opencode_client={self.opencode_client is not None}")
            return
        
        # 类型检查
        if user_id is None:
            logger.error("无法处理消息: user_id为None")
            return
        
        # 获取配置
        config = self.config_manager.opencode_config
        max_length = config["message_config"].get("max_message_length", 2000)
        
        # 安全获取 system_prompt 配置（可能是字符串而不是字典）
        system_prompt_config = config.get("system_prompt", {})
        if isinstance(system_prompt_config, dict):
            system_prompt_enabled = system_prompt_config.get("enabled", False)
            suppress_opencode_replies = system_prompt_config.get("suppress_opencode_replies", True)
            system_prompt_text = system_prompt_config.get("prompt_text", "")
        else:
            # 如果配置格式错误，使用默认值
            logger.warning(f"system_prompt 配置格式错误: {type(system_prompt_config)}, 使用默认值")
            system_prompt_enabled = False
            suppress_opencode_replies = True
            system_prompt_text = ""
        
        try:
            # 获取用户的会话ID
            session_id = None
            session = None
            if self.session_manager:
                session = self.session_manager.get_user_session(user_id)
                if session:
                    session_id = session.session_id
            
            # 从用户会话中获取 directory 配置
            user_directory = session.directory if session else config["directory"]
            
            if not session_id:
                if self.session_manager and self.opencode_client:
                    new_session_id, error = await self.opencode_client.create_session(
                        title=f"QQ 用户_{user_id}",
                        directory=user_directory
                    )
                    if new_session_id and not error:
                        session_id = new_session_id
                        session = self.session_manager.create_user_session(
                            user_id=user_id,
                            session_id=session_id,
                            title=f"QQ用户_{user_id}",
                            group_id=group_id
                        )
                    else:
                        error_msg = error or "未知错误"
                        logger.error(f"创建OpenCode会话失败: {error_msg}")
                        # 不发送错误回复，避免重复发送
                        return
                else:
                    logger.error("无法创建OpenCode会话：会话管理器或客户端不可用")
                    # 不发送错误回复，避免重复发送
                    return
            
            # 构建要发送的消息
            message_to_send = plain_text
            
            # 检查是否需要发送系统提示词
            if system_prompt_enabled and system_prompt_text and session and not session.system_prompt_sent:
# 添加用户信息前缀（区分群聊和私聊）
                display_name = user_name or f"QQ用户_{user_id}"
                session_title = session.title if session else f"QQ用户_{user_id}"
                if message_type == "group" and group_id:
                    # 群聊消息：包含群号、用户信息、会话ID和标题
                    user_info = f"[QQ用户 \"{user_id}\" 在QQ群 \"{group_id}\" 发送了一个消息, qq用户名称: \"{display_name}\", 会话ID: \"{session_id}\" ,你需要在群里at并回复]"
                else:
                    # 私聊消息：包含用户信息、会话ID和标题
                    user_info = f"[QQ用户 \"{user_id}\" 发送了一个消息，请私聊回复, qq用户名称: \"{display_name}\" , 会话ID: \"{session_id}\"]"
                
                # 将系统提示词、用户信息和消息合并
                message_to_send = f"系统提示词: {system_prompt_text}\n\n{user_info}\n用户消息: {plain_text}"
                logger.info(f"首次消息，包含系统提示词，会话ID: {session_id}")
                
                # 更新会话状态，标记系统提示词已发送
                session.system_prompt_sent = True
                # 保存会话状态
                if self.session_manager:
                    try:
                        self.session_manager.save_to_file()
                    except Exception as e:
                        logger.warning(f"保存会话状态失败（不影响当前功能）: {e}")
            else:
# 添加用户信息前缀（区分群聊和私聊）
                display_name = user_name or f"QQ用户_{user_id}"
                session_title = session.title if session else f"QQ用户_{user_id}"
                if message_type == "group" and group_id:
                    # 群聊消息：包含群号、用户信息、会话ID和标题
                    message_to_send = f"[QQ用户 \"{user_id}\" 在QQ群 \"{group_id}\" 发送了一个消息, qq用户名称: \"{display_name}\", 会话ID: \"{session_id}\" ,你需要在群里at并回复]\n{plain_text}"
                else:
                    # 私聊消息：包含用户信息、会话ID和标题
                    message_to_send = f"[QQ用户 \"{user_id}\" 发送了一个消息，请私聊回复, qq用户名称: \"{display_name}\" , 会话ID: \"{session_id}\"]\n{plain_text}"

            # 截断过长的消息
            if len(message_to_send) > max_length:
                original_length = len(message_to_send)
                message_to_send = message_to_send[:max_length] + f"...（消息过长，已截断，原长{original_length}字符）"
                logger.warning(f"消息过长，已截断: {original_length} -> {max_length}")

            logger.info(f"消息内容：{message_to_send}")
            
            # 从用户会话中获取 agent/model/provider/directory 配置
            user_agent = session.agent if session else config["default_agent"]
            user_model = session.model if session else config["default_model"]
            user_provider = session.provider if session else config["default_provider"]
            user_directory = session.directory if session else config["directory"]
            
            logger.debug(f"使用用户配置：agent={user_agent}, model={user_model}, provider={user_provider}, directory={user_directory}")
            
            # 发送消息（使用用户配置的 agent/model/provider/directory）
            response, error = await self.opencode_client.send_message(
                message_text=message_to_send,
                session_id=session_id,
                agent=user_agent,
                model=user_model,
                provider=user_provider,
                directory=user_directory
            )
            
            if error:
                logger.error(f"OpenCode处理失败: {error}")
                # 失败时不发送任何回复，避免重复发送
                return
            
            # 提取回复文本
            if response and isinstance(response, dict) and response.get("parts"):
                text_parts = []
                for part in response.get("parts", []):
                    if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                        text_parts.append(part.get("text"))
                
                if text_parts:
                    reply = "\n\n".join(text_parts)
                    if len(reply) > max_length:
                        reply = reply[:max_length] + "...（回复过长，已截断）"
                    
                    # 根据配置决定是否发送回复
                    if suppress_opencode_replies:
                        logger.info(f"消息处理成功，但抑制回复发送 (用户={user_id}, 长度={len(reply)})")
                        return  # 成功但不发送回复，退出函数
                    else:
                        if send_reply_callback:
                            await send_reply_callback(message_type, group_id, user_id, reply)
                            logger.info(f"OpenCode回复发送成功 (用户={user_id}, 长度={len(reply)})")
                        else:
                            logger.warning(f"未提供send_reply_callback，无法发送回复 (用户={user_id})")
                        return  # 成功并发送回复，退出函数
                else:
                    # 无文本回复，只记录日志，不发送任何回复
                    logger.info(f"OpenCode已处理，但未返回文本回复 (用户={user_id})")
                    return  # 完成（无文本回复）
            else:
# 响应格式异常，检查是否包含错误信息
                if response and isinstance(response, dict):
                    # 尝试从 info.error 或 error 字段提取错误信息
                    error_info = response.get("info", {}).get("error") or response.get("error") or response.get("message", str(response))
                    
                    # 检查是否是应该静默的错误类型
                    if isinstance(error_info, dict) and _should_silent_error(error_info):
                        # 静默错误，只记录日志，不发送给用户
                        logger.info(f"OpenCode 返回可忽略错误 (用户={user_id}, 会话={session_id}): {error_info.get('name')}")
                        return  # 完成，不发送错误提示
                    
                    # 其他错误类型，发送给用户
                    reply = f"OpenCode 错误：{error_info}"
                else:
                    reply = "OpenCode 响应格式异常"
                if send_reply_callback:
                    await send_reply_callback(message_type, group_id, user_id, reply)
                logger.warning(f"OpenCode 响应格式异常 (用户={user_id}, 会话={session_id})")
                return  # 完成（格式异常）
            
        except asyncio.TimeoutError as e:
            logger.error(f"OpenCode请求超时: {e}")
            # 超时不发送回复，避免重复发送
            return
        except Exception as e:
            logger.error(f"转发消息到OpenCode失败: {e}")
            # 失败时不发送回复，避免重复发送
            return
