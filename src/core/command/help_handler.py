#!/usr/bin/env python3
"""
帮助命令处理器模块
"""

from __future__ import annotations

from typing import Optional, Callable, Any


class HelpHandler:
    """帮助命令处理器"""
    
    def __init__(
        self,
        send_reply_callback: Optional[Callable[[str, Optional[int], Optional[int], str], Any]] = None
    ):
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
    
    @staticmethod
    def get_help_text() -> str:
        """获取帮助文本"""
        return (
            "hello 这里是 Axeuh_home~\n"
            "可用命令:\n"
            "  /help      - 显示帮助\n"
            "  /new       - 新建对话（可选标题）\n"
            "  /agent    - 切换智能体\n"
            "  /model     - 切换模型\n"
            "  /path      - 设置会话路径\n"
            "  /session   - 管理会话\n"
            "  /command   - 列出/执行斜杠命令\n"
            "  /reload    - 重启机器人\n"
            "  /stop      - 打断当前会话\n"
            "  /undo      - 撤销上一条消息\n"
            "  /redo      - 恢复所有撤销的消息\n"
            "  /compact   - 压缩当前会话上下文\n\n"
            "当前配置:\n"
            "  * 智能体：Sisyphus (Ultraworker)\n"
            "  * 模型：alibaba-coding-plan-cn/qwen3.5-plus\n\n"
            "使用说明:\n"
            "* 发送任意消息给 Axeuh_home\n"
            "* 群聊需@机器人\n"
            "* 发送 /命令 help 查看详细用法\n"
            "* 例如：/session help, /command help"
        )
    
    async def handle_help(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /help 命令
        
        Args:
            message_type: 消息类型
            group_id: 群组 ID
            user_id: 用户 ID
            args: 命令参数
        """
        reply = self.get_help_text()
        await self.send_reply(message_type, group_id, user_id, reply)