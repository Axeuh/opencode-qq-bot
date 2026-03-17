#!/usr/bin/env python3
"""
API发送器模块
从onebot_client.py中提取的消息发送相关方法
"""

import logging
import json
import asyncio
import time
from typing import Dict, Optional, Any, Union
from .cq_code_parser import extract_plain_text
from src.utils import config
from .napcat_http_client import NapCatHttpClient

logger = logging.getLogger(__name__)


class ApiSender:
    """OneBot API消息发送器，支持WebSocket和HTTP回退"""
    
    def __init__(self, connection_manager):
        """初始化API发送器
        
        Args:
            connection_manager: WebSocket连接管理器
        """
        self.connection_manager = connection_manager
        
        # 初始化HTTP客户端（如果启用）
        self.http_client: Optional[NapCatHttpClient] = None
        self.http_enabled = config.HTTP_API_ENABLED
        
        if self.http_enabled:
            try:
                self.http_client = NapCatHttpClient()
                logger.info("✅ ApiSender HTTP客户端已初始化")
            except Exception as e:
                logger.warning(f"⚠️  HTTP客户端初始化失败: {e}")
                self.http_enabled = False
                self.http_client = None
    
    async def send_action(self, action: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """发送API动作（委托给ConnectionManager）"""
        return await self.connection_manager.send_action(action, params)
    
    async def send_action_with_response(self, action: str, params: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """发送API动作并等待响应（委托给ConnectionManager）"""
        return await self.connection_manager.send_action_with_response(action, params, timeout)
    
    async def send_private_msg(self, user_id: int, message: str) -> Optional[Dict[str, Any]]:
        """发送私聊消息"""
        return await self.send_action('send_private_msg', {
            'user_id': user_id,
            'message': message
        })
    
    async def send_group_msg(self, group_id: int, message: str) -> Optional[Dict[str, Any]]:
        """发送群消息"""
        return await self.send_action('send_group_msg', {
            'group_id': group_id,
            'message': message
        })
    
    async def get_status(self) -> Optional[Dict[str, Any]]:
        """获取状态"""
        return await self.send_action('get_status')
    
    async def send_reply(self, message_type: str, group_id: Optional[int],
                        user_id: Optional[int], reply: str):
        """发送回复消息（公开接口）"""
        if message_type == 'private' and user_id is not None:
            await self.send_private_msg(user_id, reply)
        elif message_type == 'group' and group_id is not None:
            await self.send_group_msg(group_id, reply)
    
    async def set_input_status(self, user_id: int, event_type: int = 1) -> Optional[Dict]:
        """设置输入状态 (0=说话, 1=输入中)
        
        Args:
            user_id: 目标用户QQ号
            event_type: 状态类型 (0=正在说话..., 1=正在输入...)
        """
        return await self.send_action('set_input_status', {
            'user_id': user_id,
            'event_type': event_type
        })

    async def get_quoted_message_full(self, message_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """通过消息 ID 获取被引用消息的完整数据（仅使用 HTTP API）
        
        策略：完全移除 WebSocket 依赖，仅使用 HTTP API
        
        Args:
            message_id: 被引用消息的 ID（整数或字符串）
            
        Returns:
            完整的消息数据字典，或 None（获取失败）
        """
        # HTTP API 配置
        http_max_retries = 3  # HTTP API 重试次数
        http_retry_delay = 1.0  # 秒
        
        logger.info(f"🚀 [仅HTTP] 开始获取引用消息，消息ID: {message_id} (类型: {type(message_id)})")
        
        # 检查 HTTP API 是否启用
        if not self.http_enabled or not self.http_client:
            logger.error(f"❌ HTTP API 未启用或客户端未初始化，无法获取消息: message_id={message_id}")
            return None
        
        # HTTP API 重试循环
        for attempt in range(http_max_retries):
            try:
                logger.info(f"📤 HTTP 尝试 {attempt+1}/{http_max_retries} 获取消息ID: {message_id}")
                
                # 添加请求时间戳
                import time
                request_start = time.time()
                
                # 直接使用 HTTP API
                http_response = await self.http_client.get_msg(message_id)
                
                request_duration = time.time() - request_start
                logger.info(f"⏱️  HTTP 请求耗时: {request_duration:.3f}秒")
                
                if http_response:
                    logger.info(f"✅ HTTP 成功获取消息数据，message_id={message_id}")
                    
                    # 记录关键字段
                    if 'message_id' in http_response:
                        logger.info(f"📝 消息ID: {http_response['message_id']}")
                    if 'message_type' in http_response:
                        logger.info(f"📝 消息类型: {http_response['message_type']}")
                    if 'sender' in http_response:
                        logger.info(f"📝 发送者: {http_response['sender'].get('user_id')}")
                    if 'message' in http_response:
                        msg_content = str(http_response['message'])[:200]
                        logger.info(f"📝 消息内容预览: {msg_content}...")
                    
                    logger.info(f"📄 响应数据摘要: {json.dumps(http_response, ensure_ascii=False)[:500]}...")
                    return http_response
                else:
                    logger.warning(f"❌ HTTP 返回 None（尝试{attempt+1}）：message_id={message_id}")
                    
                    if attempt < http_max_retries - 1:
                        logger.info(f"⏳ 等待{http_retry_delay}秒后重试...")
                        await asyncio.sleep(http_retry_delay)
                        continue
                    return None
                    
            except Exception as e:
                logger.error(f"❌ HTTP 获取消息失败（尝试{attempt+1}）：{e}")
                import traceback
                logger.error(f"❌ 异常堆栈: {traceback.format_exc()}")
                
                if attempt < http_max_retries - 1:
                    logger.info(f"⏳ 等待{http_retry_delay}秒后重试...")
                    await asyncio.sleep(http_retry_delay)
                    continue
                return None
        
        # 所有 HTTP 重试都失败
        logger.error(f"💥 所有{http_max_retries}次 HTTP 尝试都失败，message_id={message_id}")
        return None

    async def get_quoted_message_content(self, message_id: Union[int, str]) -> Optional[str]:
        """通过消息 ID 获取被引用消息的纯文本内容（仅使用 HTTP API）
        
        策略：完全移除 WebSocket 依赖，仅使用 HTTP API
        
        Args:
            message_id: 被引用消息的 ID（整数或字符串）
            
        Returns:
            被引用消息的纯文本内容，或 "[图片/表情等非文本消息]"，或 None（获取失败）
        """
        # HTTP API 配置
        http_max_retries = 3  # HTTP API 重试次数
        http_retry_delay = 1.0  # 秒
        
        logger.info(f"🚀 [仅HTTP] 开始获取引用消息纯文本，消息ID: {message_id} (类型: {type(message_id)})")
        
        # 检查 HTTP API 是否启用
        if not self.http_enabled or not self.http_client:
            logger.error(f"❌ HTTP API 未启用或客户端未初始化，无法获取消息内容: message_id={message_id}")
            return None
        
        # HTTP API 重试循环
        for attempt in range(http_max_retries):
            try:
                logger.info(f"📤 HTTP 尝试 {attempt+1}/{http_max_retries} 获取消息内容ID: {message_id}")
                
                # 添加请求时间戳
                import time
                request_start = time.time()
                
                # 直接使用 HTTP API
                http_response = await self.http_client.get_msg(message_id)
                
                request_duration = time.time() - request_start
                logger.info(f"⏱️  HTTP 请求耗时: {request_duration:.3f}秒")
                
                if http_response:
                    logger.info(f"✅ HTTP 成功获取消息内容数据，message_id={message_id}")
                    
                    # 记录关键字段
                    if 'message_id' in http_response:
                        logger.info(f"📝 消息ID: {http_response['message_id']}")
                    if 'message_type' in http_response:
                        logger.info(f"📝 消息类型: {http_response['message_type']}")
                    if 'sender' in http_response:
                        logger.info(f"📝 发送者: {http_response['sender'].get('user_id')}")
                    
                    # 提取消息内容
                    if http_response.get("message"):
                        quoted_message = http_response.get("message", "")
                        if isinstance(quoted_message, str):
                            # 使用现有方法提取纯文本
                            plain_text = extract_plain_text(quoted_message).strip()
                            if plain_text:
                                logger.info(f"✅ 成功提取消息内容：{plain_text[:100]}...")
                                return plain_text
                            else:
                                # 可能是纯图片消息等情况
                                logger.info(f"📷 被引用消息内容为空（可能是图片/表情）：message_id={message_id}")
                                return "[图片/表情等非文本消息]"
                        else:
                            # 消息内容不是字符串
                            logger.warning(f"⚠️ 消息内容不是字符串类型：{type(quoted_message)}")
                            return "[非文本消息]"
                    else:
                        # 消息中没有message字段
                        logger.warning(f"⚠️ 消息数据中没有message字段：{http_response.keys()}")
                        return None
                else:
                    logger.warning(f"❌ HTTP 返回 None（尝试{attempt+1}）：message_id={message_id}")
                    
                    if attempt < http_max_retries - 1:
                        logger.info(f"⏳ 等待{http_retry_delay}秒后重试...")
                        await asyncio.sleep(http_retry_delay)
                        continue
                    return None
                    
            except Exception as e:
                logger.error(f"❌ HTTP 获取消息内容失败（尝试{attempt+1}）：{e}")
                import traceback
                logger.error(f"❌ 异常堆栈: {traceback.format_exc()}")
                
                if attempt < http_max_retries - 1:
                    logger.info(f"⏳ 等待{http_retry_delay}秒后重试...")
                    await asyncio.sleep(http_retry_delay)
                    continue
                return None
        
        # 所有 HTTP 重试都失败
        logger.error(f"💥 所有{http_max_retries}次 HTTP 尝试都失败，message_id={message_id}")
        return None


if __name__ == "__main__":
    # 测试代码
    print("ApiSender模块导入测试完成")