"""
定时任务执行模块
负责执行定时任务并发送到 OpenCode
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TaskExecutor:
    """
    定时任务执行器
    负责执行定时任务并将消息发送到 OpenCode
    """
    
    def __init__(
        self,
        opencode_client: Any,
        session_manager: Any
    ):
        """
        初始化任务执行器
        
        Args:
            opencode_client: OpenCode 客户端实例
            session_manager: 会话管理器实例
        """
        self.opencode_client = opencode_client
        self.session_manager = session_manager
    
    async def execute_task(
        self, 
        session_id: str, 
        prompt: str, 
        task_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        执行定时任务：发送prompt到opencode会话
        
        Args:
            session_id: OpenCode会话ID
            prompt: 任务提示词
            task_info: 任务信息字典（可选）
        """
        if not self.opencode_client:
            logger.warning(f"OpenCode客户端不可用，无法执行任务: session={session_id}")
            return
        
        try:
            # 获取用户配置的模型
            user_agent = None
            user_model = None
            user_provider = None
            
            if task_info and self.session_manager:
                user_id = task_info.get('user_id')
                if user_id:
                    user_config = self.session_manager.get_user_config(user_id)
                    if user_config:
                        user_agent = user_config.agent
                        user_model = user_config.model
                        user_provider = user_config.provider
                        logger.info(f"使用用户配置: user_id={user_id}, agent={user_agent}, model={user_model}, provider={user_provider}")
            
            # 构建带前缀的prompt (JSON格式，带标签)
            if task_info:
                import json
                prefix_data = {
                    "type": "task",
                    "task_id": task_info.get('task_id', ''),
                    "user_qq": task_info.get('user_id', ''),
                    "session_id": task_info.get('session_id', ''),
                    "task_name": task_info.get('task_name', ''),
                    "hint": f"这是一个定时任务，任务ID: {task_info.get('task_id', '')}, 用户QQ: {task_info.get('user_id', '')}, 任务名称: {task_info.get('task_name', '')}。请根据任务要求执行相应操作。"
                }
                prefix = "<Axeuh_bot>\n" + json.dumps(prefix_data, ensure_ascii=False) + "\n</Axeuh_bot>\n"
                full_prompt = prefix + prompt
            else:
                full_prompt = prompt
            
            logger.info(f"执行定时任务: session={session_id}, prompt={full_prompt[:100]}...")
            
            # 发送消息到OpenCode会话（使用用户配置的模型）
            _, error = await self.opencode_client.send_message(
                message_text=full_prompt,
                session_id=session_id,
                agent=user_agent,
                model=user_model,
                provider=user_provider
            )
            
            if error:
                logger.error(f"定时任务执行失败: session={session_id}, error={error}")
            else:
                logger.info(f"定时任务执行成功: session={session_id}")
                
        except Exception as e:
            logger.error(f"执行定时任务异常: {e}")
    
    def update_clients(
        self, 
        opencode_client: Any, 
        session_manager: Any
    ) -> None:
        """
        更新客户端引用（用于热重载后更新）
        
        Args:
            opencode_client: 新的 OpenCode 客户端实例
            session_manager: 新的会话管理器实例
        """
        self.opencode_client = opencode_client
        self.session_manager = session_manager
        logger.info("TaskExecutor 客户端引用已更新")