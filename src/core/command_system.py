#!/usr/bin/env python3
"""
命令系统模块 - 处理 QQ 机器人命令
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Tuple

from src.utils import config
from .time_utils import get_cross_platform_time

logger = logging.getLogger(__name__)


class CommandSystem:
    """命令系统，处理所有机器人命令"""
    
    def __init__(
        self,
        session_manager: Optional[Any] = None,
        opencode_client: Optional[Any] = None,
        send_reply_callback: Optional[Callable[[str, Optional[int], Optional[int], str], Any]] = None,
        hot_reload_callback: Optional[Callable[[], Any]] = None
    ):
        self.session_manager = session_manager
        self.opencode_client = opencode_client
        self.send_reply_callback = send_reply_callback
        self.hot_reload_callback = hot_reload_callback
        
        self.command_handlers: Dict[str, Callable] = {
            'help': self.handle_help_command,
            'new': self.handle_new_command,
            'agents': self.handle_agents_command,
            'model': self.handle_model_command,
            'directory': self.handle_directory_command,
            'session': self.handle_session_command,
            'reload': self.handle_reload_command,
            'stop': self.handle_stop_command,
            'undo': self.handle_undo_command,
            'redo': self.handle_redo_command,
            'command': self.handle_command_command,
            'compact': self.handle_compact_command,
        }
    
    def is_command(self, plain_text: str) -> bool:
        """检查消息是否为命令"""
        if not plain_text:
            return False
        return plain_text.strip().startswith(config.OPENCODE_COMMAND_PREFIX)
    
    def extract_command(self, message: str) -> Tuple[str, str]:
        """从消息中提取命令和参数"""
        if not self.is_command(message):
            return "", message
        
        message = message.strip()
        if message.startswith(config.OPENCODE_COMMAND_PREFIX):
            message = message[len(config.OPENCODE_COMMAND_PREFIX):]
        
        parts = message.split(maxsplit=1)
        if len(parts) == 0:
            return "", ""
        elif len(parts) == 1:
            return parts[0], ""
        else:
            return parts[0], parts[1].strip()  # 确保参数没有多余空格
    
    async def handle_command(self, command_name: str, message_type: str, 
                           group_id: Optional[int], user_id: Optional[int], 
                           args: str) -> bool:
        """处理命令的主入口方法"""
        if command_name not in self.command_handlers:
            return False
        
        handler = self.command_handlers[command_name]
        try:
            await handler(message_type, group_id, user_id, args)
            return True
        except Exception as e:
            logger.error(f"处理命令失败：{e}")
            await self.send_reply(message_type, group_id, user_id, f"处理命令失败：{str(e)}")
            return True
    
    async def send_reply(self, message_type: str, group_id: Optional[int], 
                        user_id: Optional[int], reply: str) -> None:
        if self.send_reply_callback:
            await self.send_reply_callback(message_type, group_id, user_id, reply)
        else:
            logger.warning(f"未设置 send_reply_callback: {reply[:50]}...")
    
    async def handle_help_command(self, message_type: str, group_id: Optional[int],
                                user_id: Optional[int], args: str):
        reply = (
            "hello 这里是 Axeuh_home~\n"
            "可用命令:\n"
            "  /help      - 显示帮助\n"
            "  /new       - 新建对话（可选标题）\n"
            "  /agents    - 切换智能体\n"
            "  /model     - 切换模型\n"
            "  /directory - 设置工作目录\n"
            "  /session   - 管理会话\n"
            "  /command   - 列出/执行斜杠命令\n"
            "  /reload    - 重启机器人\n"
            "  /stop      - 打断当前会话\n"
            "  /undo      - 撤销上一条消息\n"
            "  /redo      - 恢复所有撤销的消息\n"
            "  /compact   - 压缩当前会话上下文\n\n"
            "当前配置:\n"
            "  • 智能体：Sisyphus (Ultraworker)\n"
            "  • 模型：alibaba-coding-plan-cn/qwen3.5-plus\n\n"
            "使用说明:\n"
            "• 发送任意消息给 Axeuh_home\n"
            "• 群聊需@机器人\n"
            "• 发送 /命令 help 查看详细用法\n"
            "• 例如：/session help, /command help"
        )
        await self.send_reply(message_type, group_id, user_id, reply)
    
    async def handle_directory_command(self, message_type: str, group_id: Optional[int],
                                     user_id: Optional[int], args: str):
        # 暂时禁用 /directory 功能，所有操作都基于根路径 "/"
        if not self.session_manager or not user_id:
            await self.send_reply(message_type, group_id, user_id, "会话管理器不可用。")
            return
        
        reply = "⚠️ /directory 功能暂时禁用\n\n所有操作当前都基于根路径 \"/\"\n此设置不受用户配置影响。"
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    def _get_session_id_by_index(self, user_id: int, index_str: str) -> Optional[str]:
        try:
            index = int(index_str)
            history = self.session_manager.get_user_session_history(user_id)
            # 按最后访问时间倒序排列（最近使用的在前）
            sorted_history = sorted(history, key=lambda x: x.get("last_accessed", x.get("created_at", 0)), reverse=True)
            if 1 <= index <= len(sorted_history):
                return sorted_history[index - 1].get("session_id")
            return None
        except (ValueError, IndexError):
            return None
    
    async def _show_session_list(self, message_type: str, group_id: Optional[int], user_id: int):
        current_session = self.session_manager.get_user_session(user_id)
        history = self.session_manager.get_user_session_history(user_id)
        
        if not history:
            await self.send_reply(message_type, group_id, user_id, "暂无会话历史，使用 /new 创建新会话。")
            return
        
        # 按最后访问时间倒序排列（最近使用的会话排前面）
        sorted_history = sorted(history, key=lambda x: x.get("last_accessed", x.get("created_at", 0)), reverse=True)
        
        reply = "当前会话列表（按最后访问时间倒序）:\n"
        for i, session_info in enumerate(sorted_history, 1):
            session_id = session_info.get("session_id", "未知")
            title = session_info.get("title", "无标题")
            # 显示最后访问时间
            last_accessed = session_info.get("last_accessed", session_info.get("created_at", 0))
            time_str = time.strftime("%m/%d %H:%M", time.localtime(last_accessed))
            marker = " ✓" if current_session and current_session.session_id == session_id else ""
            reply += f"{i}. {title} [{time_str}]{marker}\n"
        
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
    
    async def _switch_to_session(self, message_type: str, group_id: Optional[int], user_id: int, session_id: str):
        if not self.session_manager:
            await self.send_reply(message_type, group_id, user_id, "会话管理器不可用。")
            return
        
        self.session_manager.switch_to_session(user_id, session_id)
        await self.send_reply(message_type, group_id, user_id, "已切换到会话")
    
    async def _update_session_title(self, message_type: str, group_id: Optional[int], 
                                   user_id: int, session_id: str, new_title: str):
        if not self.session_manager:
            await self.send_reply(message_type, group_id, user_id, "会话管理器不可用。")
            return
        
        if len(new_title) > 100:
            await self.send_reply(message_type, group_id, user_id, "标题过长，请控制在 100 字符以内。")
            return
        
        if self.session_manager.update_session_title(user_id, session_id, new_title):
            await self.send_reply(message_type, group_id, user_id, f"会话标题已更新：{new_title}")
        else:
            await self.send_reply(message_type, group_id, user_id, "更新标题失败，会话不存在。")
    
    async def handle_session_command(self, message_type: str, group_id: Optional[int],
                                    user_id: Optional[int], args: str):
        if not user_id:
            logger.warning("无法处理/session 命令：user_id 为空")
            return
        
        if not self.session_manager:
            await self.send_reply(message_type, group_id, user_id, "会话管理器不可用")
            return
        
        try:
            original_args = args.strip()
            args_lower = original_args.lower()
            
            if args_lower == "help":
                help_text = (
                    "📋 会话管理命令帮助\n\n"
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
                    "• 序号来自会话列表中的数字编号\n"
                    "• 会话 ID 格式为 ses_xxxxxxxxxxxxx\n"
                    "• 标题长度不超过 100 字符\n"
                    "• 每个用户最多保留 20 个历史会话\n"
                    "• 会话列表按最后访问时间排序，最近使用的排前面\n"
                    "• 使用 /new [标题] 创建新会话"
                )
                await self.send_reply(message_type, group_id, user_id, help_text)
                return
            
            if not original_args:
                await self._show_session_list(message_type, group_id, user_id)
                return
            
            parts = original_args.split()
            
            if parts[0].lower() == "title" and len(parts) >= 2:
                current_session = self.session_manager.get_user_session(user_id)
                if not current_session:
                    await self.send_reply(message_type, group_id, user_id, "没有活动的会话，请先使用 /new 创建新会话。")
                    return
                new_title = " ".join(parts[1:])
                await self._update_session_title(message_type, group_id, user_id, 
                                                current_session.session_id, new_title)
                return
            
            if parts[0].lower() == "getid" and len(parts) >= 2:
                session_id = self._get_session_id_by_index(user_id, parts[1])
                if session_id:
                    await self.send_reply(message_type, group_id, user_id, f"会话 ID: {session_id}")
                else:
                    await self.send_reply(message_type, group_id, user_id, f"无效的序号：{parts[1]}")
                return
            
            # Delete 子命令
            if parts[0].lower() == "delete" and len(parts) >= 2:
                delete_target = parts[1]
                
                # 批量删除
                if "," in delete_target:
                    indices = delete_target.split(",")
                    deleted = []
                    failed = []
                    for idx in indices:
                        idx = idx.strip()
                        session_id = self._get_session_id_by_index(user_id, idx)
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
                    session_id = self._get_session_id_by_index(user_id, delete_target)
                    if session_id:
                        if self.session_manager.delete_session_by_id(user_id, session_id):
                            await self.send_reply(message_type, group_id, user_id, f"已删除会话 {delete_target}: {session_id}")
                        else:
                            await self.send_reply(message_type, group_id, user_id, "删除失败")
                    else:
                        await self.send_reply(message_type, group_id, user_id, f"无效的序号：{delete_target}")
                return
            
            if parts[0].startswith("ses_"):
                session_id = parts[0]
                if len(parts) >= 3 and parts[1].lower() == "title":
                    new_title = " ".join(parts[2:])
                    await self._update_session_title(message_type, group_id, user_id, session_id, new_title)
                else:
                    await self._switch_to_session(message_type, group_id, user_id, session_id)
                return
            
            try:
                index = int(parts[0])
                if len(parts) >= 3 and parts[1].lower() == "title":
                    session_id = self._get_session_id_by_index(user_id, str(index))
                    if session_id:
                        new_title = " ".join(parts[2:])
                        await self._update_session_title(message_type, group_id, user_id, session_id, new_title)
                    else:
                        await self.send_reply(message_type, group_id, user_id, f"无效的序号：{index}")
                else:
                    session_id = self._get_session_id_by_index(user_id, str(index))
                    if session_id:
                        await self._switch_to_session(message_type, group_id, user_id, session_id)
                    else:
                        await self.send_reply(message_type, group_id, user_id, f"无效的序号：{index}")
            except ValueError:
                await self.send_reply(message_type, group_id, user_id, "命令格式错误。使用 /session help 查看帮助。")
        
        except Exception as e:
            logger.error(f"处理/session 命令失败：{e}")
            await self.send_reply(message_type, group_id, user_id, f"处理命令失败：{str(e)}")
    
    async def handle_new_command(self, message_type: str, group_id: Optional[int],
                               user_id: Optional[int], args: str):
        if not user_id:
            logger.warning("无法处理/new 命令：user_id 为空")
            return
        
        if self.session_manager and self.opencode_client:
            try:
                current_time = get_cross_platform_time()
                title = args.strip() if args and args.strip() else f"QQ_{user_id} | {current_time}"
                
                # 暂时强制使用根路径 "/"，忽略用户配置中的 directory
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
                    logger.info(f"为用户 {user_id} 创建新会话：{session_id}, 标题：{title}, 目录：{user_directory}")
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
    
    async def handle_agents_command(self, message_type: str, group_id: Optional[int],
                                  user_id: Optional[int], args: str):
        if not self.session_manager or not user_id:
            await self.send_reply(message_type, group_id, user_id, "会话管理器不可用。")
            return
        
        if not args:
            agents_list = "\n".join([f"  • {agent}" for agent in config.OPENCODE_SUPPORTED_AGENTS])
            user_config = self.session_manager.get_user_config(user_id)
            current_agent = user_config.agent if user_config else config.OPENCODE_DEFAULT_AGENT
            
            reply = (
                f"当前智能体：{current_agent}\n\n"
                f"可用的智能体:\n"
                f"{agents_list}\n\n"
                f"使用方法：/agents [智能体名称]\n"
                f"示例：/agents sisyphus"
            )
        else:
            agent_name = args.strip()
            matched_agent = None
            if agent_name in config.OPENCODE_SUPPORTED_AGENTS:
                matched_agent = agent_name
            else:
                for agent in config.OPENCODE_SUPPORTED_AGENTS:
                    if agent.lower() == agent_name.lower():
                        matched_agent = agent
                        break
            
            if matched_agent:
                self.session_manager.update_user_config(user_id, agent=matched_agent)
                reply = f"智能体已切换到：{matched_agent}\n\n配置已保存，重启后仍然有效。"
            else:
                reply = f"未找到智能体：{agent_name}"
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    async def handle_model_command(self, message_type: str, group_id: Optional[int],
                                 user_id: Optional[int], args: str):
        if not self.session_manager or not user_id:
            await self.send_reply(message_type, group_id, user_id, "会话管理器不可用。")
            return
        
        if not args:
            user_config = self.session_manager.get_user_config(user_id)
            current_model = user_config.model if user_config else config.OPENCODE_DEFAULT_MODEL
            
            # 显示带序号的模型列表
            models_list = []
            current_index = 0
            for i, m in enumerate(config.OPENCODE_SUPPORTED_MODELS, 1):
                marker = " *" if m == current_model else ""
                models_list.append(f"  {i}. {m}{marker}")
                if m == current_model:
                    current_index = i
            models = "\n".join(models_list)
            
            reply = (
                f"当前模型：{current_model}"
                + (f" (序号 {current_index})" if current_index > 0 else "")
                + f"\n\n可用的模型:\n{models}\n\n"
                f"使用方法：/model [序号] 或 /model [模型名称]\n"
                f"示例：/model 13 或 /model deepseek/deepseek-reasoner"
            )
        else:
            model_input = args.strip()
            matched_model = None
            
            # 检查是否为序号
            if model_input.isdigit():
                index = int(model_input)
                if 1 <= index <= len(config.OPENCODE_SUPPORTED_MODELS):
                    matched_model = config.OPENCODE_SUPPORTED_MODELS[index - 1]
                else:
                    await self.send_reply(message_type, group_id, user_id, 
                        f"无效的序号：{index}（有效范围：1-{len(config.OPENCODE_SUPPORTED_MODELS)}）")
                    return
            else:
                # 按名称匹配
                # 先尝试精确匹配
                if model_input in config.OPENCODE_SUPPORTED_MODELS:
                    matched_model = model_input
                else:
                    # 尝试不区分大小写匹配
                    for m in config.OPENCODE_SUPPORTED_MODELS:
                        if m.lower() == model_input.lower():
                            matched_model = m
                            break
                    
                    # 尝试匹配模型名称的最后一部分（如 "kimi-k2.5" 匹配 "alibaba-coding-plan-cn/kimi-k2.5"）
                    if not matched_model:
                        for m in config.OPENCODE_SUPPORTED_MODELS:
                            parts = m.split("/")
                            if len(parts) >= 2 and parts[-1].lower() == model_input.lower():
                                matched_model = m
                                break
            
            if matched_model:
                # 从完整模型ID中提取供应商
                if "/" in matched_model:
                    provider_name = matched_model.split("/")[0]
                    self.session_manager.update_user_config(user_id, model=matched_model, provider=provider_name)
                else:
                    self.session_manager.update_user_config(user_id, model=matched_model)
                reply = f"模型已切换到：{matched_model}\n\n配置已保存，重启后仍然有效。"
            else:
# 提供模糊匹配建议
                suggestions = []
                for m in config.OPENCODE_SUPPORTED_MODELS:
                    if model_input.lower() in m.lower():
                        suggestions.append(m)
                
                if suggestions:
                    suggestion_text = "\n".join([f"  • {s}" for s in suggestions[:3]])
                    reply = f"未找到模型：{model_input}\n\n您是否想要：\n{suggestion_text}"
                else:
                    reply = f"未找到模型：{model_input}\n使用 /model 查看可用模型列表。"
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    async def handle_reload_command(self, message_type: str, group_id: Optional[int],
                                   user_id: Optional[int], args: str):
        """处理 /reload 命令 - 热重载代码和配置"""
        if self.hot_reload_callback:
            reply = "正在执行热重载..."
            await self.send_reply(message_type, group_id, user_id, reply)
            
            try:
                result = await self.hot_reload_callback()
                if result.get("success", False):
                    modules_count = len(result.get("modules_reload", []))
                    reply = f"热重载完成\n配置: {'成功' if result.get('config_reload') else '失败'}\n模块: {modules_count} 个已重载"
                    if result.get("errors"):
                        reply += f"\n警告: {len(result['errors'])} 个错误"
                else:
                    reply = f"热重载失败: {result.get('error', '未知错误')}"
            except Exception as e:
                reply = f"热重载异常: {str(e)}"
        else:
            reply = "热重载回调未配置"
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    async def handle_stop_command(self, message_type: str, group_id: Optional[int],
                                user_id: Optional[int], args: str):
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
    
    async def handle_undo_command(self, message_type: str, group_id: Optional[int],
                                user_id: Optional[int], args: str):
        if not user_id or not self.session_manager:
            await self.send_reply(message_type, group_id, user_id, "无法识别用户或会话管理器不可用。")
            return
        
        current_session = self.session_manager.get_user_session(user_id)
        if not current_session:
            await self.send_reply(message_type, group_id, user_id, "没有活动的会话。")
            return
        
        if self.opencode_client:
            success, error = await self.opencode_client.revert_last_message(current_session.session_id)
            reply = "已撤销最后一条消息" if success else f"撤销失败：{error}"
        else:
            reply = "OpenCode 客户端不可用"
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    async def handle_redo_command(self, message_type: str, group_id: Optional[int],
                                user_id: Optional[int], args: str):
        if not user_id or not self.session_manager:
            await self.send_reply(message_type, group_id, user_id, "无法识别用户或会话管理器不可用。")
            return
        
        current_session = self.session_manager.get_user_session(user_id)
        if not current_session:
            await self.send_reply(message_type, group_id, user_id, "没有活动的会话。")
            return
        
        if self.opencode_client:
            success, error = await self.opencode_client.unrevert_messages(current_session.session_id)
            reply = "✅ 已恢复 OpenCode 会话中所有撤销的消息" if success else f"恢复失败：{error}"
        else:
            reply = "OpenCode 客户端不可用"
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    async def handle_command_command(self, message_type: str, group_id: Optional[int],
                                    user_id: Optional[int], args: str):
        """处理/command 命令 - 列出或通过序号执行斜杠命令"""
        if not user_id:
            await self.send_reply(message_type, group_id, user_id, "无法识别用户。")
            return
        
        if not self.session_manager or not self.opencode_client:
            await self.send_reply(message_type, group_id, user_id, "OpenCode 集成不可用。")
            return
        
        args_lower = args.strip().lower()
        
        # 显示帮助
        if args_lower == "help":
            help_text = (
                "斜杠命令帮助\n\n"
                "可用格式:\n"
                "  /command - 列出所有可用的斜杠命令\n"
                "  /command [序号] - 执行对应序号的命令\n"
                "  /command [会话 ID] [命令] - 在指定会话中执行指定命令\n\n"
                "说明:\n"
                "• 序号来自 /command 显示的命令列表\n"
                "• 会话 ID 格式为 ses_xxxxxxxxxxxxx"
            )
            await self.send_reply(message_type, group_id, user_id, help_text)
            return
        
        # 列出可用命令
        if not args or args_lower == "list":
            commands, error = await self.opencode_client.list_commands()
            
            if error:
                await self.send_reply(message_type, group_id, user_id, f"获取命令列表失败：{error}")
                return
            
            if not commands:
                await self.send_reply(message_type, group_id, user_id, "当前没有可用的斜杠命令。")
                return
            
            # 格式化命令列表（只显示名称）
            reply = "可用的斜杠命令:\n"
            for i, cmd in enumerate(commands, 1):
                if isinstance(cmd, dict):
                    cmd_name = cmd.get("name", cmd.get("command", "未知"))
                    reply += f"  {i}. {cmd_name}\n"
                else:
                    reply += f"  {i}. {cmd}\n"
            
            reply += "\n使用方法：/command [序号] [参数]"
            await self.send_reply(message_type, group_id, user_id, reply)
            return
        
        # 解析参数（支持：/command 22 或 /command 22 参数）
        parts = args.strip().split(maxsplit=1)
        
        # 检查是否以数字开头（通过序号执行命令）
        if parts and parts[0].isdigit():
            command_index = int(parts[0])
            command_args = parts[1] if len(parts) > 1 else ""
            
            # 获取命令列表
            commands, error = await self.opencode_client.list_commands()
            
            if error:
                await self.send_reply(message_type, group_id, user_id, f"获取命令列表失败：{error}")
                return
            
            if not commands:
                await self.send_reply(message_type, group_id, user_id, "当前没有可用的斜杠命令。")
                return
            
            # 验证序号范围
            if command_index < 1 or command_index > len(commands):
                await self.send_reply(message_type, group_id, user_id, f"无效的序号：{command_index}（有效范围：1-{len(commands)}）")
                return
            
            # 获取命令名称
            cmd = commands[command_index - 1]
            if isinstance(cmd, dict):
                command = cmd.get("name", cmd.get("command", ""))
            else:
                command = str(cmd)
            
            # 确保命令以/开头
            if not command.startswith("/"):
                command = "/" + command
            
            # 获取用户的活跃会话
            user_session = self.session_manager.get_user_session(user_id)
            if not user_session:
                await self.send_reply(message_type, group_id, user_id, "没有活跃的会话，请先使用 /new 创建会话。")
                return
            
            session_id = user_session.session_id
            agent = user_session.agent
            model = user_session.model
            provider = user_session.provider
            
            # 执行命令（传递参数）
            try:
                result, error = await self.opencode_client.execute_command(
                    session_id=session_id,
                    command=command,
                    agent=agent,
                    model=model,
                    provider=provider,
                    arguments=command_args
                )
                
                if error:
                    await self.send_reply(message_type, group_id, user_id, f"执行命令失败：{error}")
                    return
                
                # 返回执行结果
                if result:
                    result_parts = result.get("parts", [])
                    
                    reply = "命令执行成功\n命令：{command}"
                    if command_args:
                        reply += f"\n参数：{command_args}"
                    reply += "\n"
                    
                    # 提取响应文本
                    for part in result_parts:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text = part.get("text", "")
                            if text:
                                reply += f"\n响应：{text[:500]}"
                                if len(text) > 500:
                                    reply += "..."
                                break
                    
                    await self.send_reply(message_type, group_id, user_id, reply)
                else:
                    reply = f"命令已发送\n命令：{command}"
                    if command_args:
                        reply += f"\n参数：{command_args}"
                    await self.send_reply(message_type, group_id, user_id, reply)
                    
            except Exception as e:
                logger.error(f"执行斜杠命令失败：{e}")
                await self.send_reply(message_type, group_id, user_id, f"执行失败：{str(e)}")
            return
        
        # 原有格式：/command [会话 ID] [命令]
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            await self.send_reply(message_type, group_id, user_id, "格式错误\n用法：\n  /command [序号] - 执行对应序号的命令\n  /command [会话 ID] [命令] - 在指定会话执行命令")
            return
        
        session_target, command = parts[0], parts[1]
        
        # 验证命令格式
        if not command.startswith("/"):
            await self.send_reply(message_type, group_id, user_id, f"命令应以/开头：{command}")
            return
        
        # 解析会话 ID（支持序号或完整 ID）
        session_id = None
        if session_target.startswith("ses_"):
            session_id = session_target
        else:
            # 尝试作为序号解析
            session_id = self._get_session_id_by_index(user_id, session_target)
            if not session_id:
                await self.send_reply(message_type, group_id, user_id, f"无效的会话 ID 或序号：{session_target}")
                return
        
        # 获取用户的 agent 和 model 配置
        user_session = self.session_manager.get_user_session(user_id)
        agent = user_session.agent if user_session else None
        model = user_session.model if user_session else None
        provider = user_session.provider if user_session else None
        
        try:
            result, error = await self.opencode_client.execute_command(
                session_id=session_id,
                command=command,
                agent=agent,
                model=model,
                provider=provider
            )
            
            if error:
                await self.send_reply(message_type, group_id, user_id, f"执行命令失败：{error}")
                return
            
            # 返回执行结果
            if result:
                info = result.get("info", {})
                parts = result.get("parts", [])
                
                reply = f"命令执行成功\n命令：{command}\n"
                
                # 提取响应文本
                for part in parts:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text = part.get("text", "")
                        if text:
                            reply += f"\n响应：{text[:500]}"
                            if len(text) > 500:
                                reply += "..."
                            break
                
                await self.send_reply(message_type, group_id, user_id, reply)
            else:
                await self.send_reply(message_type, group_id, user_id, f"命令已发送\n命令：{command}")
                
        except Exception as e:
            logger.error(f"执行斜杠命令失败：{e}")
            await self.send_reply(message_type, group_id, user_id, f"执行失败：{str(e)}")
    
    async def handle_compact_command(self, message_type: str, group_id: Optional[int],
                                    user_id: Optional[int], args: str):
        """处理/compact 命令 - 压缩当前会话上下文"""
        if not user_id:
            logger.warning("无法处理/compact 命令：user_id 为空")
            return
        
        if not self.session_manager:
            await self.send_reply(message_type, group_id, user_id, "会话管理器不可用")
            return
        
        if not self.opencode_client:
            await self.send_reply(message_type, group_id, user_id, "OpenCode 客户端不可用")
            return
        
        # 获取用户当前会话
        user_session = self.session_manager.get_user_session(user_id)
        if not user_session:
            await self.send_reply(message_type, group_id, user_id, "没有活动的会话，请先使用/new 创建新会话")
            return
        
        session_id = user_session.session_id
        provider_id = user_session.provider
        model_id = user_session.model
        
        await self.send_reply(message_type, group_id, user_id, "正在压缩会话...")
        
        # 调用 API 压缩会话
        success, error = await self.opencode_client.summarize_session(
            session_id=session_id,
            provider_id=provider_id,
            model_id=model_id
        )
        
        if success:
            await self.send_reply(message_type, group_id, user_id, "会话已压缩")
        else:
            await self.send_reply(message_type, group_id, user_id, f"压缩失败：{error}")
