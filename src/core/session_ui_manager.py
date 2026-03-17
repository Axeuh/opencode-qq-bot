#!/usr/bin/env python3
"""
会话UI管理器模块 - 处理与会话相关的用户界面操作
包括显示会话列表、切换会话、更新标题等功能
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class SessionUIManager:
    """会话UI管理器，处理与会话相关的用户界面操作"""
    
    def __init__(self, session_manager, send_reply_callback):
        """
        初始化会话UI管理器
        
        Args:
            session_manager: 会话管理器对象，提供会话操作接口
            send_reply_callback: 发送回复的回调函数，格式为:
                async def callback(message_type: str, group_id: Optional[int],
                                 user_id: int, reply: str)
        """
        self.session_manager = session_manager
        self.send_reply_callback = send_reply_callback
    
    async def show_session_list(self, message_type: str, group_id: Optional[int], user_id: int):
        """显示会话列表 - 返回带序号的简洁列表，不显示sessionid"""
        if not self.session_manager:
            await self.send_reply_callback(message_type, group_id, user_id, "会话管理器不可用")
            return
        
        try:
            # 获取当前活跃会话
            current_session = self.session_manager.get_user_session(user_id)
            
            # 获取用户的会话历史（使用新方法）
            history = self.session_manager.get_user_session_history(user_id)
            
            if history or current_session:
                reply_lines = ["您的会话列表 (通过序号操作):"]
                
                # 显示所有会话（当前+历史），按创建时间倒序排列
                all_sessions = []
                
                # 添加当前活跃会话到列表（如果有）
                if current_session:
                    all_sessions.append({
                        'session_id': current_session.session_id,
                        'title': current_session.title,
                        'created_at': current_session.created_at,
                        'is_current': True
                    })
                
                # 添加历史会话到列表
                for session_info in history:
                    session_id = session_info.get('session_id')
                    if session_id and (not current_session or session_id != current_session.session_id):
                        all_sessions.append({
                            'session_id': session_id,
                            'title': session_info.get('title', '无标题'),
                            'created_at': session_info.get('created_at', 0),
                            'is_current': False
                        })
                
                # 按创建时间倒序排列
                all_sessions.sort(key=lambda x: x['created_at'], reverse=True)
                
                if all_sessions:
                    reply_lines.append("")
                    for i, session in enumerate(all_sessions, 1):
                        current_indicator = " [当前会话]" if session['is_current'] else ""
                        reply_lines.append(f"{i}. {session['title']}{current_indicator}")
                    
                    reply_lines.append("")
                    reply_lines.append("使用以下命令管理会话:")
                    reply_lines.append("  /session [序号] - 切换到指定会话")
                    reply_lines.append("  /session [序号] title [新标题] - 修改指定会话标题")
                    reply_lines.append("  /session getid [序号] - 获取会话ID")
                    reply_lines.append("  /new [标题] - 创建新会话（可选标题）")
                    
                    # 存储序号到session_id的映射（用于后续命令处理）
                    # 这里只存储简单的映射，实际处理时再按相同逻辑计算
                else:
                    reply_lines.append("\n您还没有创建任何会话。使用 /new 创建新会话。")
                
                reply = "\n".join(reply_lines)
            else:
                reply = "您还没有创建任何会话。使用 /new 创建新会话。"
            
            await self.send_reply_callback(message_type, group_id, user_id, reply)
            
        except Exception as e:
            logger.error(f"显示会话列表失败: {e}")
            await self.send_reply_callback(message_type, group_id, user_id, f"显示会话列表失败: {str(e)}")
    
    async def switch_to_session(self, message_type: str, group_id: Optional[int], user_id: int, session_id: str):
        """切换到指定会话 - 不显示sessionid，只返回标题"""
        if not self.session_manager:
            await self.send_reply_callback(message_type, group_id, user_id, "会话管理器不可用")
            return
        
        try:
            # 检查当前会话是否已经是目标会话
            current_session = self.session_manager.get_user_session(user_id)
            if current_session and current_session.session_id == session_id:
                await self.send_reply_callback(message_type, group_id, user_id,
                                             f"已经是当前会话: {current_session.title}")
                return
            
            # 切换到指定会话（即使不在历史记录中也会创建）
            new_session = self.session_manager.switch_to_session(user_id, session_id)
            if not new_session:
                # 理论上不会发生，因为switch_to_session现在总是返回会话对象
                await self.send_reply_callback(message_type, group_id, user_id,
                                             f"切换到会话失败")
                return
            
            # 获取会话标题（从新创建的会话对象中）
            title = new_session.title if new_session.title else "无标题"
            await self.send_reply_callback(message_type, group_id, user_id,
                                         f"已切换到会话: {title}")
            
        except Exception as e:
            logger.error(f"切换到会话失败: {e}")
            await self.send_reply_callback(message_type, group_id, user_id, f"切换到会话失败: {str(e)}")
    
    async def update_session_title(self, message_type: str, group_id: Optional[int], 
                                 user_id: int, session_id: Optional[str], new_title: str):
        """更新会话标题 - 不显示sessionid"""
        if not self.session_manager:
            await self.send_reply_callback(message_type, group_id, user_id, "会话管理器不可用")
            return
        
        try:
            if not new_title or len(new_title) > 100:
                await self.send_reply_callback(message_type, group_id, user_id,
                                             "标题不能为空且长度不能超过100字符")
                return
            
            # 如果没有指定session_id，则修改当前会话
            if not session_id:
                current_session = self.session_manager.get_user_session(user_id)
                if not current_session:
                    await self.send_reply_callback(message_type, group_id, user_id,
                                                 "您没有活跃会话，请先创建会话")
                    return
                session_id = current_session.session_id
            
            # 获取旧标题用于显示
            session_info = self.session_manager.get_session_by_id(user_id, session_id)
            old_title = session_info.get('title', '无标题') if session_info else '无标题'
            
            # 更新标题
            success = self.session_manager.update_session_title(user_id, session_id, new_title)
            if not success:
                await self.send_reply_callback(message_type, group_id, user_id,
                                             f"更新标题失败，会话不存在")
                return
            
            await self.send_reply_callback(message_type, group_id, user_id,
                                         f"会话标题已更新\n"
                                         f"   旧标题: {old_title}\n"
                                         f"   新标题: {new_title}")
            
        except Exception as e:
            logger.error(f"更新会话标题失败: {e}")
            await self.send_reply_callback(message_type, group_id, user_id, f"更新会话标题失败: {str(e)}")
    
    def get_session_id_by_index(self, user_id: int, index_str: str) -> Optional[str]:
        """根据序号获取session_id
        
        Args:
            user_id: QQ用户ID
            index_str: 序号字符串（如"1", "2"等）
            
        Returns:
            对应的session_id，如果序号无效则返回None
        """
        try:
            index = int(index_str)
            if index < 1:
                return None
                
            if not self.session_manager:
                return None
            
            # 获取当前活跃会话
            current_session = self.session_manager.get_user_session(user_id)
            
            # 获取用户的会话历史
            history = self.session_manager.get_user_session_history(user_id)
            
            # 收集所有会话
            all_sessions = []
            
            # 添加当前活跃会话到列表（如果有）
            if current_session:
                all_sessions.append({
                    'session_id': current_session.session_id,
                    'title': current_session.title,
                    'created_at': current_session.created_at,
                    'is_current': True
                })
            
            # 添加历史会话到列表
            for session_info in history:
                session_id = session_info.get('session_id')
                if session_id and (not current_session or session_id != current_session.session_id):
                    all_sessions.append({
                        'session_id': session_id,
                        'title': session_info.get('title', '无标题'),
                        'created_at': session_info.get('created_at', 0),
                        'is_current': False
                    })
            
            # 按创建时间倒序排列
            all_sessions.sort(key=lambda x: x['created_at'], reverse=True)
            
            # 检查序号是否有效
            if 1 <= index <= len(all_sessions):
                return all_sessions[index - 1]['session_id']
            
            return None
            
        except ValueError:
            return None