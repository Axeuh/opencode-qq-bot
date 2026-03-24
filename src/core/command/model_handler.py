#!/usr/bin/env python3
"""
模型和智能体命令处理器模块 - 处理 /agent, /model 命令
"""

from __future__ import annotations

import logging
from typing import Optional, Callable, Any, List

from src.utils import config
from src.utils.config_loader import is_excluded

from .utils import format_model_list, format_agent_list, match_model_by_input, match_agent_by_input

logger = logging.getLogger(__name__)


class ModelHandler:
    """模型和智能体命令处理器"""
    
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
    
    # ==================== /agent 命令 ====================
    
    async def handle_agent(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /agent 命令 - 列出或切换智能体"""
        if not self.session_manager or not user_id:
            await self.send_reply(message_type, group_id, user_id, "会话管理器不可用。")
            return
        
        if not self.opencode_client:
            await self.send_reply(message_type, group_id, user_id, "OpenCode 客户端不可用。")
            return
        
        # 获取智能体列表
        agents = await self._get_available_agents()
        if agents is None:
            return  # 错误已在 _get_available_agents 中处理
        
        if not args:
            await self._show_agent_list(message_type, group_id, user_id, agents)
        else:
            await self._switch_agent(message_type, group_id, user_id, agents, args.strip())
    
    async def _get_available_agents(self) -> Optional[List[str]]:
        """获取可用智能体列表"""
        agents_data, error = await self.opencode_client.get_agents()
        if error:
            # 需要调用者提供 message_type 等参数来发送错误消息
            return None
        
        agents = []
        excluded_agents = config.OPENCODE_EXCLUDED_AGENTS or []
        if agents_data:
            for agent in agents_data:
                try:
                    if isinstance(agent, dict):
                        agent_name = agent.get("name") or agent.get("id") or str(agent)
                    elif isinstance(agent, str):
                        agent_name = agent
                    else:
                        agent_name = str(agent) if agent else ""
                    
                    if agent_name and not is_excluded(agent_name, excluded_agents):
                        agents.append(agent_name)
                except Exception as e:
                    logger.warning(f"处理智能体数据时出错: {e}, agent={agent}")
                    continue
        
        return agents
    
    async def _show_agent_list(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        agents: List[str]
    ) -> None:
        """显示智能体列表"""
        user_config = self.session_manager.get_user_config(user_id)
        current_agent = user_config.agent if user_config else config.OPENCODE_DEFAULT_AGENT
        
        reply = format_agent_list(agents, current_agent)
        await self.send_reply(message_type, group_id, user_id, reply)
    
    async def _switch_agent(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        agents: List[str], 
        agent_input: str
    ) -> None:
        """切换智能体"""
        matched_agent = match_agent_by_input(agents, agent_input)
        
        if matched_agent:
            self.session_manager.update_user_config(user_id, agent=matched_agent)
            reply = f"智能体已切换到：{matched_agent}\n\n配置已保存，重启后仍然有效。"
        else:
            reply = f"未找到智能体：{agent_input}"
        
        await self.send_reply(message_type, group_id, user_id, reply)
    
    # ==================== /model 命令 ====================
    
    async def handle_model(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: Optional[int], 
        args: str
    ) -> None:
        """处理 /model 命令 - 列出或切换模型"""
        if not self.session_manager or not user_id:
            await self.send_reply(message_type, group_id, user_id, "会话管理器不可用。")
            return
        
        if not self.opencode_client:
            await self.send_reply(message_type, group_id, user_id, "OpenCode 客户端不可用。")
            return
        
        # 获取模型列表
        models = await self._get_available_models(message_type, group_id, user_id)
        if models is None:
            return  # 错误已处理
        
        if not args:
            await self._show_model_list(message_type, group_id, user_id, models)
        else:
            await self._switch_model(message_type, group_id, user_id, models, args.strip())
    
    async def _get_available_models(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int
    ) -> Optional[List[str]]:
        """获取可用模型列表"""
        models_data, error = await self.opencode_client.get_models()
        if error:
            await self.send_reply(message_type, group_id, user_id, f"获取模型列表失败：{error}")
            return None
        
        models = []
        excluded_models = config.OPENCODE_EXCLUDED_MODELS or []
        if models_data:
            for model in models_data:
                try:
                    if isinstance(model, dict):
                        provider_id = model.get("provider_id", "")
                        model_id = model.get("model_id", "")
                        if provider_id and model_id:
                            full_model_id = f"{provider_id}/{model_id}"
                        else:
                            full_model_id = model_id or model.get("id") or ""
                        
                        if full_model_id and not is_excluded(full_model_id, excluded_models):
                            models.append(full_model_id)
                    elif isinstance(model, str):
                        if model and not is_excluded(model, excluded_models):
                            models.append(model)
                    else:
                        model_str = str(model) if model else ""
                        if model_str and not is_excluded(model_str, excluded_models):
                            models.append(model_str)
                except Exception as e:
                    logger.warning(f"处理模型数据时出错: {e}, model={model}")
                    continue
        
        return models
    
    async def _show_model_list(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        models: List[str]
    ) -> None:
        """显示模型列表"""
        user_config = self.session_manager.get_user_config(user_id)
        current_model = user_config.model if user_config else config.OPENCODE_DEFAULT_MODEL
        
        reply = format_model_list(models, current_model)
        await self.send_reply(message_type, group_id, user_id, reply)
    
    async def _switch_model(
        self, 
        message_type: str, 
        group_id: Optional[int], 
        user_id: int, 
        models: List[str], 
        model_input: str
    ) -> None:
        """切换模型"""
        matched_model = match_model_by_input(models, model_input)
        
        if matched_model:
            self.session_manager.update_user_config(user_id, model=matched_model)
            reply = f"模型已切换到：{matched_model}\n\n配置已保存，重启后仍然有效。"
        else:
            # 提供模糊匹配建议
            suggestions = [m for m in models if model_input.lower() in m.lower()]
            
            if suggestions:
                suggestion_text = "\n".join([f"  - {s}" for s in suggestions[:3]])
                reply = f"未找到模型：{model_input}\n\n您是否想要：\n{suggestion_text}"
            else:
                reply = f"未找到模型：{model_input}\n使用 /model 查看可用模型列表。"
        
        await self.send_reply(message_type, group_id, user_id, reply)