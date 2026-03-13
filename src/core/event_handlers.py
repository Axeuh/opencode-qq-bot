#!/usr/bin/env python3
"""
事件处理器模块
从onebot_client.py中提取的事件处理方法
"""

import json
import logging
from typing import Dict, Optional, Any

from src.utils import config
from .message_router import MessageRouter

logger = logging.getLogger(__name__)


class EventHandlers:
    """处理OneBot客户端的事件"""
    
    def __init__(
        self,
        message_router: Optional[MessageRouter] = None,
        bot_qq_id: Optional[int] = None
    ):
        """初始化事件处理器
        
        Args:
            message_router: 消息路由器实例（可选）
            bot_qq_id: 机器人QQ号（可选）
        """
        self.message_router = message_router
        self.bot_qq_id = bot_qq_id
        logger.info(f"EventHandlers初始化: message_router={'已设置' if message_router else 'None'}, bot_qq_id={bot_qq_id}")
    
    async def handle_meta_event(self, message: Dict):
        """处理元事件"""
        meta_event_type = message.get('meta_event_type')
        
        if meta_event_type == 'heartbeat':
            # 忽略心跳消息，避免日志过多
            if config.DEBUG:
                logger.debug(f"收到心跳，状态: {message.get('status')}")
            
            # 从心跳消息中获取机器人QQ号
            if self.bot_qq_id is None:
                self.bot_qq_id = message.get('self_id')
                if self.bot_qq_id:
                    logger.info(f"从心跳获取机器人QQ号: {self.bot_qq_id}")
                    # 同步更新MessageRouter的bot_qq_id
                    if self.message_router:
                        self.message_router.bot_qq_id = self.bot_qq_id
                        logger.info(f"已同步MessageRouter的bot_qq_id: {self.bot_qq_id}")
                    else:
                        logger.warning(f"无法同步MessageRouter的bot_qq_id: message_router为None")
            return
        
        elif meta_event_type == 'lifecycle':
            sub_type = message.get('sub_type')
            if sub_type == 'connect':
                # 连接事件中获取机器人QQ号
                self.bot_qq_id = message.get('self_id')
                if self.bot_qq_id:
                    logger.info(f"机器人QQ号: {self.bot_qq_id}")
                    # 同步更新MessageRouter的bot_qq_id
                    if self.message_router:
                        self.message_router.bot_qq_id = self.bot_qq_id
                        logger.info(f"已同步MessageRouter的bot_qq_id: {self.bot_qq_id}")
                    else:
                        logger.warning(f"无法同步MessageRouter的bot_qq_id: message_router为None")
                else:
                    logger.warning("无法从连接事件获取机器人QQ号")
        
        logger.info(f"收到元事件: {meta_event_type}")
    
    async def handle_message_event(self, message: Dict):
        """处理消息事件"""
        logger.debug(f"收到消息事件: {json.dumps(message, ensure_ascii=False)}")
        
        # 委托给消息路由器
        if self.message_router:
            await self.message_router.route_message(message)
        else:
            logger.warning("消息路由器未初始化，无法处理消息事件")
    
    async def handle_notice_event(self, message: Dict):
        """处理通知事件"""
        notice_type = message.get('notice_type')
        logger.info(f"收到通知事件: {notice_type}")
        logger.debug(f"通知事件原始消息: {json.dumps(message, ensure_ascii=False)}")
        
        # 处理戳一戳消息
        if notice_type == 'notify':
            sub_type = message.get('sub_type')
            if sub_type == 'poke':
                # 戳一戳消息处理
                target_id = message.get('target_id')  # 被戳者
                user_id = message.get('user_id')      # 发送者
                group_id = message.get('group_id')    # 群聊ID（如果存在）
                
                logger.info(f"收到戳一戳消息: 发送者={user_id}, 被戳者={target_id}, 群聊={group_id}")
                logger.debug(f"戳一戳处理: target_id类型={type(target_id)}, bot_qq_id={self.bot_qq_id}, bot_qq_id类型={type(self.bot_qq_id)}")
                
                # 检查是否是戳机器人
                if target_id == self.bot_qq_id:
                    logger.info(f"机器人被用户 {user_id} 戳了一下")
                    
                    # 检查user_id是否有效
                    if user_id is None:
                        logger.warning("戳一戳消息中缺少user_id，无法处理")
                        return
                    
                    # 根据配置决定是否处理戳一戳
                    poke_reply_enabled = config.ENABLED_FEATURES.get('poke_reply', False)
                    logger.debug(f"戳一戳处理配置: poke_reply={poke_reply_enabled}")
                    
                    if poke_reply_enabled:
                        # 尝试打断用户的OpenCode会话
                        session_interrupted = await self._interrupt_opencode_session(user_id)
                        if session_interrupted:
                            logger.info(f"已成功打断用户 {user_id} 的OpenCode会话")
                        else:
                            logger.info(f"用户 {user_id} 没有活动的OpenCode会话或打断失败")
                        
                        # 发送戳一戳消息到OpenCode（不回复到QQ）
                        await self._send_poke_to_opencode(user_id, group_id)
                    else:
                        logger.info(f"戳一戳处理功能未启用，不发送任何消息")
                else:
                    logger.debug(f"戳一戳目标不是机器人: target_id={target_id}, bot_qq_id={self.bot_qq_id}")
        else:
            logger.debug(f"其他通知类型: {notice_type}, sub_type: {message.get('sub_type')}")
    
    async def _send_reply(self, message_type: str, group_id: Optional[int], user_id: Optional[int], message: str):
        """发送回复消息
        
        Args:
            message_type: 消息类型 ('private' 或 'group')
            group_id: 群聊ID（群聊消息时使用）
            user_id: 用户ID（私聊消息时使用）
            message: 要发送的消息内容
        """
        if not self.message_router:
            logger.error("消息路由器未初始化，无法发送回复")
            return
        
        # 使用消息路由器的发送回调
        try:
            await self.message_router.send_reply_callback(message_type, group_id, user_id, message)
        except Exception as e:
            logger.error(f"发送回复失败: {e}")
    
    async def _interrupt_opencode_session(self, user_id: int) -> bool:
        """打断用户的OpenCode会话
        
        Args:
            user_id: 用户QQ号
            
        Returns:
            bool: 是否成功打断会话（如果用户没有活动会话，返回False）
        """
        try:
            # 检查消息路由器是否存在
            if not self.message_router:
                logger.warning(f"消息路由器未初始化，无法打断用户 {user_id} 的OpenCode会话")
                return False
            
            # 检查命令系统是否存在
            if not self.message_router.command_system:
                logger.warning(f"命令系统未初始化，无法打断用户 {user_id} 的OpenCode会话")
                return False
            
            command_system = self.message_router.command_system
            
            # 检查会话管理器是否存在
            if not command_system.session_manager:
                logger.warning(f"会话管理器未初始化，无法打断用户 {user_id} 的OpenCode会话")
                return False
            
            # 检查OpenCode客户端是否存在
            if not command_system.opencode_client:
                logger.warning(f"OpenCode客户端未初始化，无法打断用户 {user_id} 的OpenCode会话")
                return False
            
            # 获取用户的当前会话
            current_session = command_system.session_manager.get_user_session(user_id)
            if not current_session:
                logger.info(f"用户 {user_id} 没有活动的OpenCode会话，无需打断")
                return False
            
            # 中断会话
            logger.info(f"正在打断用户 {user_id} 的OpenCode会话: {current_session.session_id}")
            success, error = await command_system.opencode_client.abort_session(current_session.session_id)
            
            if success:
                logger.info(f"成功打断用户 {user_id} 的OpenCode会话: {current_session.session_id}")
                return True
            else:
                logger.error(f"打断用户 {user_id} 的OpenCode会话失败: {error}")
                return False
                
        except Exception as e:
            logger.error(f"打断OpenCode会话时发生异常: {e}")
            return False
    
    async def _send_poke_to_opencode(self, user_id: int, group_id: Optional[int]):
        """发送戳一戳消息到OpenCode
        
        Args:
            user_id: 发送戳一戳的用户QQ号
            group_id: 群聊ID（如果存在）
        """
        try:
            # 检查消息路由器是否存在
            if not self.message_router:
                logger.warning(f"消息路由器未初始化，无法发送戳一戳消息到OpenCode")
                return
            
            # 检查OpenCode集成是否可用
            if not self.message_router.opencode_available:
                logger.warning(f"OpenCode集成不可用，无法发送戳一戳消息")
                return
            
            # 从消息路由器获取消息队列处理器
            message_queue_processor = self.message_router.message_queue_processor
            if not message_queue_processor:
                logger.warning(f"消息队列处理器未初始化，无法发送戳一戳消息")
                return
            
            # 构建戳一戳消息内容（纯文本，不包含前缀，前缀由forward_to_opencode_sync添加）
            message_text = "用户发来了戳一戳，请求回应"
            
            # 获取用户名（可能需要从其他地方获取，这里简化处理）
            user_name = f"QQ用户_{user_id}"
            display_name = user_name
            
            logger.info(f"准备发送戳一戳消息到OpenCode: 用户={user_id}, 群聊={group_id}, 消息内容='{message_text}'")
            
            # 将消息添加到队列，等待OpenCode处理
            # 注意：plain_text应该是纯消息内容，不含前缀
            await message_queue_processor.enqueue_message(
                message_type='group' if group_id else 'private',
                group_id=group_id,
                user_id=user_id,  # 这里传入的是戳一戳发送者的user_id
                plain_text=message_text,  # 纯消息内容
                user_name=display_name
            )
            
            logger.info(f"戳一戳消息已发送到OpenCode队列")
            
        except Exception as e:
            logger.error(f"发送戳一戳消息到OpenCode时发生异常: {e}")
    
    async def handle_request_event(self, message: Dict):
        """处理请求事件"""
        request_type = message.get('request_type')
        logger.info(f"收到请求事件: {request_type}")


if __name__ == "__main__":
    # 测试代码
    print("EventHandlers模块导入测试完成")