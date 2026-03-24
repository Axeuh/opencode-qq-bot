#!/usr/bin/env python3
"""
OpenCode 消息转发器
负责将 QQ 消息转发到 OpenCode 服务
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING, Callable, Awaitable

if TYPE_CHECKING:
    from src.opencode.opencode_client import OpenCodeClient
    from src.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


def _should_silent_error(error_info: dict) -> bool:
    """判断错误是否应该静默（不显示给用户）
    
    Args:
        error_info: 错误信息字典，包含 name、data 等字段
        
    Returns:
        True 表示应该静默，False 表示应该显示给用户
    """
    error_name = error_info.get("name", "")
    
    SILENT_ERRORS = [
        "MessageAbortedError",
        "SessionAbortedError",
        "OperationAbortedError",
    ]
    
    if error_name in SILENT_ERRORS:
        logger.debug(f"静默错误：{error_name} - {error_info.get('data', {}).get('message', '')}")
        return True
    
    return False


class OpenCodeForwarder:
    """OpenCode 消息转发器"""
    
    def __init__(self, client: "OpenCodeClient", session_manager: "SessionManager", config_manager):
        """
        初始化转发器
        
        Args:
            client: OpenCode 客户端实例
            session_manager: 会话管理器实例
            config_manager: 配置管理器实例
        """
        self._client = client
        self._session_manager = session_manager
        self._config_manager = config_manager
    
    # ==================== 子函数 1: 准备转发 ====================
    
    def _prepare_forward(
        self,
        message_type: str,
        group_id: Optional[int],
        user_id: int,
        plain_text: str
    ) -> Tuple[Dict, Optional[Any], str]:
        """
        准备转发：获取配置和用户会话
        
        Args:
            message_type: 消息类型
            group_id: 群号
            user_id: 用户 ID
            plain_text: 纯文本消息
            
        Returns:
            (配置字典, 用户会话, 用户目录) 元组
        """
        config = self._config_manager.opencode_config
        session = None
        
        if self._session_manager:
            session = self._session_manager.get_user_session(user_id)
        
        user_directory = session.directory if session else config.get("directory", "/")
        
        return config, session, user_directory
    
    # ==================== 子函数 2: 获取/创建会话 ====================
    
    async def _get_or_create_session(
        self,
        user_id: int,
        group_id: Optional[int],
        user_directory: str
    ) -> Tuple[Optional[str], Optional[Any], Optional[str]]:
        """
        获取或创建 OpenCode 会话
        
        Args:
            user_id: 用户 ID
            group_id: 群号
            user_directory: 用户目录
            
        Returns:
            (会话 ID, 用户会话, 错误消息) 元组
        """
        session_id = None
        session = None
        
        if self._session_manager:
            session = self._session_manager.get_user_session(user_id)
            if session:
                session_id = session.session_id
        
        if not session_id:
            if self._session_manager and self._client:
                new_session_id, error = await self._client.create_session(
                    title=f"QQ 用户_{user_id}",
                    directory=user_directory
                )
                if new_session_id and not error:
                    session_id = new_session_id
                    session = self._session_manager.create_user_session(
                        user_id=user_id,
                        session_id=session_id,
                        title=f"QQ用户_{user_id}",
                        group_id=group_id
                    )
                    logger.info(f"为用户 {user_id} 创建新会话：{session_id} (目录：{user_directory})")
                else:
                    return None, None, error or "未知错误"
            else:
                return None, None, "无法创建会话：会话管理器或客户端不可用"
        
        return session_id, session, None
    
    # ==================== 子函数 3: 发送消息 ====================
    
    async def _send_to_opencode(
        self,
        session_id: str,
        session: Optional[Any],
        message_type: str,
        group_id: Optional[int],
        user_id: int,
        plain_text: str,
        user_name: Optional[str] = None
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        发送消息到 OpenCode
        
        Args:
            session_id: 会话 ID
            session: 用户会话
            message_type: 消息类型
            group_id: 群号
            user_id: 用户 ID
            plain_text: 纯文本消息
            user_name: 用户显示名称
            
        Returns:
            (响应数据, 错误消息) 元组
        """
        config = self._config_manager.opencode_config
        max_length = config.get("message_config", {}).get("max_message_length", 2000)
        
        # 获取系统提示词配置
        system_prompt_config = config.get("system_prompt", {})
        if isinstance(system_prompt_config, dict):
            system_prompt_enabled = system_prompt_config.get("enabled", False)
            system_prompt_text = system_prompt_config.get("prompt_text", "")
        else:
            system_prompt_enabled = False
            system_prompt_text = ""
        
        # 构建消息
        message_to_send = self._build_message(
            session=session,
            message_type=message_type,
            group_id=group_id,
            user_id=user_id,
            plain_text=plain_text,
            user_name=user_name,
            session_id=session_id,
            system_prompt_enabled=system_prompt_enabled,
            system_prompt_text=system_prompt_text
        )
        
        # 截断过长的消息
        if len(message_to_send) > max_length:
            original_length = len(message_to_send)
            message_to_send = message_to_send[:max_length] + f"...（消息过长，已截断，原长{original_length}字符）"
            logger.warning(f"消息过长，已截断: {original_length} -> {max_length}")
        
        # 获取用户配置
        user_agent = session.agent if session else config.get("default_agent")
        user_model = session.model if session else config.get("default_model")
        user_provider = session.provider if session else config.get("default_provider")
        user_directory = session.directory if session else config.get("directory", "/")
        
        logger.debug(f"使用用户配置：agent={user_agent}, model={user_model}, provider={user_provider}, directory={user_directory}")
        
        # 发送消息
        response, error = await self._client.send_message(
            message_text=message_to_send,
            session_id=session_id,
            agent=user_agent,
            model=user_model,
            provider=user_provider,
            directory=user_directory
        )
        
        return response, error
    
    def _build_message(
        self,
        session: Optional[Any],
        message_type: str,
        group_id: Optional[int],
        user_id: int,
        plain_text: str,
        user_name: Optional[str],
        session_id: str,
        system_prompt_enabled: bool,
        system_prompt_text: str
    ) -> str:
        """构建要发送的消息"""
        display_name = user_name or f"QQ用户_{user_id}"
        
        # 检查是否需要发送系统提示词
        if system_prompt_enabled and system_prompt_text and session and not session.system_prompt_sent:
            if message_type == "group" and group_id:
                user_info = f"[QQ用户 \"{user_id}\" 在QQ群 \"{group_id}\" 发送了一个消息, qq用户名称: \"{display_name}\", 会话ID: \"{session_id}\" ,你需要在群里at并回复]"
            else:
                user_info = f"[QQ用户 \"{user_id}\" 发送了一个消息，请私聊回复, qq用户名称: \"{display_name}\" , 会话ID: \"{session_id}\"]"
            
            message_to_send = f"系统提示词: {system_prompt_text}\n\n{user_info}\n用户消息: {plain_text}"
            logger.info(f"首次消息，包含系统提示词，会话ID: {session_id}")
            
            # 更新会话状态
            session.system_prompt_sent = True
            if self._session_manager:
                try:
                    self._session_manager.save_to_file()
                except Exception as e:
                    logger.warning(f"保存会话状态失败（不影响当前功能）: {e}")
        else:
            if message_type == "group" and group_id:
                message_to_send = f"[QQ用户 \"{user_id}\" 在QQ群 \"{group_id}\" 发送了一个消息, qq用户名称: \"{display_name}\", 会话ID: \"{session_id}\" ,你需要在群里at并回复]\n{plain_text}"
            else:
                message_to_send = f"[QQ用户 \"{user_id}\" 发送了一个消息，请私聊回复, qq用户名称: \"{display_name}\" , 会话ID: \"{session_id}\"]\n{plain_text}"
        
        return message_to_send
    
    # ==================== 子函数 4: 处理响应 ====================
    
    async def _handle_response(
        self,
        response: Optional[Dict],
        error: Optional[str],
        user_id: int,
        session_id: str,
        message_type: str,
        group_id: Optional[int],
        send_reply_callback: Optional[Callable[[str, Optional[int], Optional[int], str], Awaitable[None]]] = None
    ) -> None:
        """
        处理 OpenCode 响应
        
        Args:
            response: 响应数据
            error: 错误消息
            user_id: 用户 ID
            session_id: 会话 ID
            message_type: 消息类型
            group_id: 群号
            send_reply_callback: 发送回复的回调函数
        """
        config = self._config_manager.opencode_config
        max_length = config.get("message_config", {}).get("max_message_length", 2000)
        
        # 获取抑制回复配置
        system_prompt_config = config.get("system_prompt", {})
        suppress_opencode_replies = system_prompt_config.get("suppress_opencode_replies", True) if isinstance(system_prompt_config, dict) else True
        
        if error:
            logger.error(f"OpenCode 处理失败: {error}")
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
                
                if suppress_opencode_replies:
                    logger.info(f"消息处理成功，但抑制回复发送 (用户={user_id}, 长度={len(reply)})")
                else:
                    if send_reply_callback:
                        await send_reply_callback(message_type, group_id, user_id, reply)
                        logger.info(f"OpenCode 回复发送成功 (用户={user_id}, 长度={len(reply)})")
            else:
                logger.info(f"OpenCode 已处理，但未返回文本回复 (用户={user_id})")
        else:
            # 响应格式异常
            if response and isinstance(response, dict):
                error_info = response.get("info", {}).get("error") or response.get("error") or response.get("message", str(response))
                
                if isinstance(error_info, dict) and _should_silent_error(error_info):
                    logger.info(f"OpenCode 返回可忽略错误 (用户={user_id}, 会话={session_id}): {error_info.get('name')}")
                    return
                
                reply = f"OpenCode 错误：{error_info}"
            else:
                reply = "OpenCode 响应格式异常"
            
            if send_reply_callback:
                await send_reply_callback(message_type, group_id, user_id, reply)
            logger.warning(f"OpenCode 响应格式异常 (用户={user_id}, 会话={session_id})")
    
    # ==================== 主入口函数 ====================
    
    async def forward_to_opencode(
        self,
        message_type: str,
        group_id: Optional[int],
        user_id: Optional[int],
        plain_text: str,
        user_name: Optional[str] = None,
        send_reply_callback: Optional[Callable[[str, Optional[int], Optional[int], str], Awaitable[None]]] = None
    ) -> None:
        """
        将消息转发到 OpenCode
        
        Args:
            message_type: 消息类型 ('private' 或 'group')
            group_id: 群号（群聊时）
            user_id: 用户 QQ 号
            plain_text: 纯文本消息
            user_name: 用户显示名称（可选）
            send_reply_callback: 发送回复的回调函数
        """
        if not user_id:
            logger.warning("无法转发消息到 OpenCode: user_id 为空")
            return
        
        try:
            # 1. 准备转发
            config, session, user_directory = self._prepare_forward(
                message_type, group_id, user_id, plain_text
            )
            
            # 2. 获取或创建会话
            session_id, session, error = await self._get_or_create_session(
                user_id, group_id, user_directory
            )
            
            if error or not session_id:
                logger.error(f"获取/创建会话失败: {error}")
                return
            
            # 3. 发送消息
            response, error = await self._send_to_opencode(
                session_id=session_id,
                session=session,
                message_type=message_type,
                group_id=group_id,
                user_id=user_id,
                plain_text=plain_text,
                user_name=user_name
            )
            
            # 4. 处理响应
            await self._handle_response(
                response=response,
                error=error,
                user_id=user_id,
                session_id=session_id,
                message_type=message_type,
                group_id=group_id,
                send_reply_callback=send_reply_callback
            )
            
        except asyncio.TimeoutError as e:
            logger.error(f"OpenCode 请求超时: {e}")
        except Exception as e:
            logger.error(f"转发消息到 OpenCode 失败: {e}")