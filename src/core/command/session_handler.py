#!/usr/bin/env python3
"""
会话命令处理器模块 - 处理 /new, /session, /stop, /path 命令
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Callable, Any

from src.utils import config

from .utils import get_session_id_by_index, format_session_list

logger = logging.getLogger(__name__)


class SessionHandler:
    """会话命令处理器"""
    
    def __init__(
        self,
        session_manager: Optional[Any] = None,
        opencode_client: Optional[Any] = None,
        send_reply_callback: Optional[Callable[[str, Optional[int], Optional[int], str], Any]] = None
    ):
        self.session_manager = session_manager
        self.opencode_client = opencode_client
        self.send_reply_callback = send_reply_callback
    
    async def send_reply(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        reply: str
    ) -> None:
        """发送回复消息"""
        if self.send_reply_callback:
            await self.send_reply_callback(message_type, group_id, user_id, reply)
    
    # ==================== /new 命令 ====================
    
    async def handle_new(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /new 命令 - 创建新会话"""
        if not user_id:
            logger.warning("无法处理/new 命令：user_id 为空")
            return
        
        if self.session_manager and self.opencode_client:
            try:
                from ..time_utils import get_cross_platform_time
                current_time = get_cross_platform_time()
                title = args.strip() if args and args.strip() else f"QQ_{user_id} | {current_time}"
                
                # 暂时强制使用根路径 "/"
                user_directory = "/"
                
                session_id, error = await self.opencode_client.create_session(
                    title=title,
                    directory=user_directory
                )
                
                if session_id and not error:
                    session = self.session_manager.create_user_session(
                        user_id=user_id,
                        session_id=session_id,
                        title=title,
                        group_id=group_id
                    )
                    reply = f"已创建新的会话\n标题：{title}"
                    logger.info(f"为用户 {user_id} 创建新会话：{session_id}, 标题：{title}")
                else:
                    error_msg = error or "未知错误"
                    reply = f"创建 OpenCode 会话失败：{error_msg}"
                    logger.error(f"创建 OpenCode 会话失败：{error_msg}")
            except Exception as e:
                logger.error(f"创建新会话失败：{e}")
                reply = f"创建新会话失败：{str(e)}"
        else:
            reply = "OpenCode 集成不可用"
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    # ==================== /stop 命令 ====================
    
    async def handle_stop(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /stop 命令 - 停止当前会话"""
        if not user_id or not self.session_manager:
            await self.send_reply(message_type, group_id, user_id, "无法识别用户或会话管理器不可用。")
            return
        
        current_session = self.session_manager.get_user_session(user_id)
        if not current_session:
            await self.send_reply(message_type, group_id, user_id, "没有活动的会话。")
            return
        
        if self.opencode_client:
            success, error = await self.opencode_client.abort_session(current_session.session_id)
            reply = f"已中止会话：{current_session.session_id}" if success else f"中止失败：{error}"
        else:
            reply = "OpenCode 客户端不可用"
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    # ==================== /path 命令 ====================
    
    async def handle_path(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /path 命令 - 设置会话路径"""
        if not self.session_manager or not user_id:
            await self.send_reply(message_type, group_id, user_id, '会话管理器不可用。')
            return
        
        current_session = self.session_manager.get_user_session(user_id)
        
        if not current_session:
            await self.send_reply(message_type, group_id, user_id, '没有活动的会话。请先使用 /new 创建会话。')
            return
        
        args = args.strip()
        
        # 显示帮助
        if not args:
            help_text = (
                "路径命令帮助\n\n"
                "格式：\n"
                "  /path - 显示当前会话路径\n"
                "  /path reset - 重置当前会话为默认路径\n"
                "  /path [路径] - 设置当前会话路径\n\n"
                "说明：\n"
                "* 每个会话有独立的路径设置\n"
                "* 默认路径为配置文件中的 OPENCODE_DIRECTORY\n"
                "* 切换会话时路径保持不变"
            )
            await self.send_reply(message_type, group_id, user_id, help_text)
            return
        
        # 重置路径
        if args.lower() == 'reset':
            success = self.session_manager.set_session_path(
                user_id=user_id,
                session_id=current_session.session_id,
                reset_to_default=True
            )
            if success:
                new_path = self.session_manager.get_session_path(user_id, current_session.session_id)
                await self.send_reply(message_type, group_id, user_id, f'已重置当前会话路径为默认：{new_path}')
            else:
                await self.send_reply(message_type, group_id, user_id, '重置路径失败。')
            return
        
        # 设置路径
        path = args.strip()
        if not path:
            await self.send_reply(message_type, group_id, user_id, '路径不能为空。')
            return
        
        success = self.session_manager.set_session_path(
            user_id=user_id,
            session_id=current_session.session_id,
            path=path
        )
        
        if success:
            await self.send_reply(message_type, group_id, user_id, f'已设置当前会话路径为：{path}')
        else:
            await self.send_reply(message_type, group_id, user_id, '设置路径失败。')
    
    # ==================== /session 命令 ====================
    
    async def handle_session(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /session 命令 - 会话管理"""
        if not user_id:
            logger.warning("无法处理/session 命令：user_id 为空")
            return
        
        if not self.session_manager:
            await self.send_reply(message_type, group_id, user_id, "会话管理器不可用")
            return
        
        try:
            original_args = args.strip()
            args_lower = original_args.lower()
            
            # 显示帮助
            if args_lower == "help":
                await self._show_session_help(message_type, group_id, user_id)
                return
            
            # 显示会话列表
            if not original_args:
                await self._show_session_list(message_type, group_id, user_id)
                return
            
            parts = original_args.split()
            
            # 处理 title 子命令
            if parts[0].lower() == "title" and len(parts) >= 2:
                await self._handle_title_current(message_type, group_id, user_id, parts[1:])
                return
            
            # 处理 getid 子命令
            if parts[0].lower() == "getid" and len(parts) >= 2:
                await self._handle_getid(message_type, group_id, user_id, parts[1])
                return
            
            # 处理 delete 子命令
            if parts[0].lower() == "delete" and len(parts) >= 2:
                await self._handle_delete(message_type, group_id, user_id, parts[1])
                return
            
            # 处理会话 ID 切换或修改标题
            if parts[0].startswith("ses_"):
                await self._handle_session_id_operation(message_type, group_id, user_id, parts)
                return
            
            # 处理序号操作
            await self._handle_index_operation(message_type, group_id, user_id, parts)
            
        except Exception as e:
            logger.error(f"处理/session 命令失败：{e}")
            await self.send_reply(message_type, group_id, user_id, f"处理命令失败：{str(e)}")
    
    async def _show_session_help(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int
    ) -> None:
        """显示会话帮助"""
        help_text = (
            "会话管理命令帮助\n\n"
            "【查看会话】\n"
            "  /session - 显示带序号的会话列表（按最后访问时间排序）\n\n"
            "【切换会话】\n"
            "  /session [序号] - 切换到指定序号的会话\n"
            "  /session [会话 ID] - 直接使用会话 ID 切换\n\n"
            "【管理会话】\n"
            "  /session title [新标题] - 修改当前会话标题\n"
            "  /session [序号] title [新标题] - 修改指定序号的标题\n"
            "  /session [会话 ID] title [新标题] - 修改指定 ID 的标题\n"
            "  /session getid [序号] - 获取指定序号的会话 ID\n\n"
            "【删除会话】\n"
            "  /session delete [序号] - 删除指定序号的会话\n"
            "  /session delete [会话 ID] - 删除指定会话\n"
            "  /session delete 1,2,3 - 批量删除多个会话\n"
            "  /session delete all - 删除所有会话\n\n"
            "【说明】\n"
            "* 序号来自会话列表中的数字编号\n"
            "* 会话 ID 格式为 ses_xxxxxxxxxxxxx\n"
            "* 标题长度不超过 100 字符\n"
            "* 每个用户最多保留 20 个历史会话\n"
            "* 会话列表按最后访问时间排序，最近使用的排前面\n"
            "* 使用 /new [标题] 创建新会话"
        )
        await self.send_reply(message_type, group_id, user_id, help_text)
    
    async def _show_session_list(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int
    ) -> None:
        """显示会话列表"""
        current_session = self.session_manager.get_user_session(user_id)
        history = self.session_manager.get_user_session_history(user_id)
        
        current_session_id = current_session.session_id if current_session else None
        reply = format_session_list(history, current_session_id)
        
        if history:
            reply += (
                "\n【操作】\n"
                "切换会话：/session [序号]\n"
                "修改当前会话标题：/session title [新标题]\n"
                "修改指定会话标题：/session [序号] title [新标题]\n"
                "获取会话 ID: /session getid [序号]\n"
                "删除会话：/session delete [序号]\n"
                "批量删除：/session delete 1,2,3\n"
                "删除所有：/session delete all\n"
                "完整帮助：/session help"
            )
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    async def _handle_title_current(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        title_parts: list
    ) -> None:
        """处理修改当前会话标题"""
        current_session = self.session_manager.get_user_session(user_id)
        if not current_session:
            await self.send_reply(message_type, group_id, user_id, "没有活动的会话，请先使用 /new 创建新会话。")
            return
        new_title = " ".join(title_parts)
        await self._update_session_title(message_type, group_id, user_id, current_session.session_id, new_title)
    
    async def _handle_getid(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        index_str: str
    ) -> None:
        """处理获取会话 ID"""
        session_id = get_session_id_by_index(self.session_manager, user_id, index_str)
        if session_id:
            await self.send_reply(message_type, group_id, user_id, f"会话 ID: {session_id}")
        else:
            await self.send_reply(message_type, group_id, user_id, f"无效的序号：{index_str}")
    
    async def _handle_delete(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        delete_target: str
    ) -> None:
        """处理删除会话"""
        # 批量删除
        if "," in delete_target:
            await self._delete_multiple(message_type, group_id, user_id, delete_target)
            return
        
        # 删除所有
        if delete_target.lower() == "all":
            count = self.session_manager.delete_all_sessions(user_id)
            await self.send_reply(message_type, group_id, user_id, f"已删除所有 {count} 个会话")
            return
        
        # 删除单个
        if delete_target.startswith("ses_"):
            if self.session_manager.delete_session_by_id(user_id, delete_target):
                await self.send_reply(message_type, group_id, user_id, f"已删除会话：{delete_target}")
            else:
                await self.send_reply(message_type, group_id, user_id, f"会话不存在：{delete_target}")
        else:
            session_id = get_session_id_by_index(self.session_manager, user_id, delete_target)
            if session_id:
                if self.session_manager.delete_session_by_id(user_id, session_id):
                    await self.send_reply(message_type, group_id, user_id, f"已删除会话 {delete_target}: {session_id}")
                else:
                    await self.send_reply(message_type, group_id, user_id, "删除失败")
            else:
                await self.send_reply(message_type, group_id, user_id, f"无效的序号：{delete_target}")
    
    async def _delete_multiple(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        indices_str: str
    ) -> None:
        """批量删除会话"""
        indices = indices_str.split(",")
        deleted = []
        failed = []
        for idx in indices:
            idx = idx.strip()
            session_id = get_session_id_by_index(self.session_manager, user_id, idx)
            if session_id and self.session_manager.delete_session_by_id(user_id, session_id):
                deleted.append(idx)
            else:
                failed.append(idx)
        
        reply = f"已删除 {len(deleted)} 个会话"
        if deleted:
            reply += f" (序号：{', '.join(deleted)})"
        if failed:
            reply += f"\n删除失败：{', '.join(failed)}"
        await self.send_reply(message_type, group_id, user_id, reply)
    
    async def _handle_session_id_operation(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        parts: list
    ) -> None:
        """处理会话 ID 操作"""
        session_id = parts[0]
        if len(parts) >= 3 and parts[1].lower() == "title":
            new_title = " ".join(parts[2:])
            await self._update_session_title(message_type, group_id, user_id, session_id, new_title)
        else:
            await self._switch_to_session(message_type, group_id, user_id, session_id)
    
    async def _handle_index_operation(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        parts: list
    ) -> None:
        """处理序号操作"""
        try:
            index = int(parts[0])
            if len(parts) >= 3 and parts[1].lower() == "title":
                session_id = get_session_id_by_index(self.session_manager, user_id, str(index))
                if session_id:
                    new_title = " ".join(parts[2:])
                    await self._update_session_title(message_type, group_id, user_id, session_id, new_title)
                else:
                    await self.send_reply(message_type, group_id, user_id, f"无效的序号：{index}")
            else:
                session_id = get_session_id_by_index(self.session_manager, user_id, str(index))
                if session_id:
                    await self._switch_to_session(message_type, group_id, user_id, session_id)
                else:
                    await self.send_reply(message_type, group_id, user_id, f"无效的序号：{index}")
        except ValueError:
            await self.send_reply(message_type, group_id, user_id, "命令格式错误。使用 /session help 查看帮助。")
    
    async def _switch_to_session(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        session_id: str
    ) -> None:
        """切换到指定会话"""
        self.session_manager.switch_to_session(user_id, session_id)
        await self.send_reply(message_type, group_id, user_id, "已切换到会话")
    
    async def _update_session_title(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        session_id: str, 
        new_title: str
    ) -> None:
        """更新会话标题"""
        if len(new_title) > 100:
            await self.send_reply(message_type, group_id, user_id, "标题过长，请控制在 100 字符以内。")
            return
        
        if self.session_manager.update_session_title(user_id, session_id, new_title):
            await self.send_reply(message_type, group_id, user_id, f"会话标题已更新：{new_title}")
        else:
            await self.send_reply(message_type, group_id, user_id, "更新标题失败，会话不存在。")