#!/usr/bin/env python3
"""
OpenCode 异步客户端
用于与 OpenCode HTTP 服务器交互的异步 Python 客户端

基于组合模式重构，将功能拆分到独立的 API 模块
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple

# 导入核心客户端和 API 模块
from .client import OpenCodeClient as _BaseClient
from .session_api import SessionAPI
from .message_api import MessageAPI
from .model_api import ModelAPI
from .types import SessionResult, BoolResult, ListResult, RequestResult

logger = logging.getLogger(__name__)


class OpenCodeClient(_BaseClient):
    """
    OpenCode 客户端（组合模式）
    
    将功能拆分到独立的 API 模块，同时保持向后兼容的公共 API
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        directory: Optional[str] = None,
        timeout: Optional[int] = None,
        default_agent: Optional[str] = None,
        default_model: Optional[str] = None,
        default_provider: Optional[str] = None,
        cookies: Optional[Dict[str, str]] = None,
        enable_ntfy: bool = False,
        ntfy_topic: str = "aaa"
    ):
        """
        初始化 OpenCode 客户端
        
        Args:
            base_url: OpenCode 服务器地址
            username: Basic 认证用户名
            password: Basic 认证密码
            token: Bearer 令牌
            directory: 工作目录
            timeout: 请求超时时间（秒）
            default_agent: 默认智能体
            default_model: 默认模型
            default_provider: 默认提供商
            cookies: HTTP Cookies
            enable_ntfy: 是否启用 ntfy 通知
            ntfy_topic: ntfy 主题
        """
        super().__init__(
            base_url=base_url,
            username=username,
            password=password,
            token=token,
            directory=directory,
            timeout=timeout,
            default_agent=default_agent,
            default_model=default_model,
            default_provider=default_provider,
            cookies=cookies,
            enable_ntfy=enable_ntfy,
            ntfy_topic=ntfy_topic
        )
        
        # 组合 API 模块（使用下划线前缀避免与基类的 aiohttp session 冲突）
        self._session_api = SessionAPI(self)
        self._message_api = MessageAPI(self)
        self._model_api = ModelAPI(self)
    
    # ==================== 会话管理 API（向后兼容代理）====================
    
    async def create_session(
        self, 
        title: Optional[str] = None,
        directory: Optional[str] = None
    ) -> SessionResult:
        """创建新会话"""
        return await self._session_api.create_session(title, directory)
    
    async def abort_session(self, session_id: str, directory: Optional[str] = None) -> BoolResult:
        """中止会话"""
        return await self._session_api.abort_session(session_id, directory)
    
    async def revert_last_message(self, session_id: str, directory: Optional[str] = None) -> BoolResult:
        """撤销最后一条消息"""
        return await self._session_api.revert_last_message(session_id, directory)
    
    async def unrevert_messages(self, session_id: str, directory: Optional[str] = None) -> BoolResult:
        """恢复所有撤销的消息"""
        return await self._session_api.unrevert_messages(session_id, directory)
    
    async def list_sessions(self, limit: int = 50) -> ListResult:
        """列出所有会话"""
        return await self._session_api.list_sessions(limit)
    
    async def get_session(self, session_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """获取会话详情"""
        return await self._session_api.get_session(session_id)
    
    async def delete_session(self, session_id: str) -> BoolResult:
        """删除会话"""
        return await self._session_api.delete_session(session_id)
    
    async def summarize_session(
        self,
        session_id: str,
        provider_id: str,
        model_id: str,
        directory: Optional[str] = None
    ) -> BoolResult:
        """压缩/总结当前会话上下文"""
        return await self._session_api.summarize_session(session_id, provider_id, model_id, directory)
    
    async def list_messages(self, session_id: str, limit: Optional[int] = None, directory: Optional[str] = None) -> ListResult:
        """列出会话中的消息"""
        return await self._session_api.list_messages(session_id, limit, directory)
    
    # ==================== 消息 API（向后兼容代理）====================
    
    async def send_message(
        self,
        message_text: str,
        session_id: Optional[str] = None,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        directory: Optional[str] = None,
        create_if_not_exists: bool = True
    ) -> RequestResult:
        """发送消息到 OpenCode 会话"""
        return await self._message_api.send_message(
            message_text=message_text,
            session_id=session_id,
            agent=agent,
            model=model,
            provider=provider,
            directory=directory,
            create_if_not_exists=create_if_not_exists
        )
    
    async def execute_command(
        self,
        session_id: str,
        command: str,
        message_id: Optional[str] = None,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        arguments: Optional[str] = "",
        directory: Optional[str] = None
    ) -> RequestResult:
        """在指定会话中执行斜杠命令"""
        return await self._message_api.execute_command(
            session_id=session_id,
            command=command,
            message_id=message_id,
            agent=agent,
            model=model,
            provider=provider,
            arguments=arguments,
            directory=directory
        )
    
    # ==================== 模型/智能体 API（向后兼容代理）====================
    
    async def get_models(self) -> ListResult:
        """获取可用模型列表"""
        return await self._model_api.get_models()
    
    async def get_agents(self) -> ListResult:
        """获取可用智能体列表"""
        return await self._model_api.get_agents()
    
    async def list_commands(self) -> ListResult:
        """获取可用的斜杠命令列表"""
        return await self._model_api.list_commands()


# ==================== 同步接口包装器（向后兼容）====================

class OpenCodeClientSync:
    """OpenCode 同步客户端（包装异步客户端）"""
    
    def __init__(self, *args, **kwargs):
        self.client = OpenCodeClient(*args, **kwargs)
        self.loop = asyncio.new_event_loop()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _run_async(self, coro):
        """运行异步协程并返回结果"""
        return self.loop.run_until_complete(coro)
    
    def create_session(self, title: Optional[str] = None) -> SessionResult:
        return self._run_async(self.client.create_session(title))
    
    def send_message(self, message_text: str, session_id: Optional[str] = None, **kwargs) -> RequestResult:
        return self._run_async(self.client.send_message(message_text, session_id, **kwargs))
    
    def list_sessions(self, limit: int = 50) -> ListResult:
        return self._run_async(self.client.list_sessions(limit))
    
    def get_session(self, session_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        return self._run_async(self.client.get_session(session_id))
    
    def list_messages(self, session_id: str, limit: Optional[int] = None) -> ListResult:
        return self._run_async(self.client.list_messages(session_id, limit))
    
    def delete_session(self, session_id: str) -> BoolResult:
        return self._run_async(self.client.delete_session(session_id))
    
    def abort_session(self, session_id: str) -> BoolResult:
        return self._run_async(self.client.abort_session(session_id))
    
    def revert_last_message(self, session_id: str) -> BoolResult:
        return self._run_async(self.client.revert_last_message(session_id))
    
    def unrevert_messages(self, session_id: str) -> BoolResult:
        return self._run_async(self.client.unrevert_messages(session_id))
    
    def get_models(self) -> ListResult:
        return self._run_async(self.client.get_models())
    
    def get_agents(self) -> ListResult:
        return self._run_async(self.client.get_agents())
    
    def health_check(self) -> Tuple[bool, Optional[str]]:
        return self._run_async(self.client.health_check())
    
    def close(self):
        self._run_async(self.client.close())
        self.loop.close()


# ==================== 测试函数 ====================

async def test_client():
    """测试 OpenCode 客户端"""
    client = OpenCodeClient()
    
    try:
        # 健康检查
        healthy, msg = await client.health_check()
        print(f"健康检查: {'通过' if healthy else '失败'} - {msg}")
        
        if healthy:
            # 创建会话
            session_id, error = await client.create_session("测试会话")
            if error:
                print(f"创建会话失败: {error}")
                return
            
            print(f"创建会话成功: {session_id}")
            
            # 发送消息
            response, error = await client.send_message(
                "你好，这是一个测试消息",
                session_id=session_id
            )
            
            if error:
                print(f"发送消息失败: {error}")
            else:
                print(f"发送消息成功，响应类型: {type(response)}")
                if isinstance(response, dict) and "parts" in response:
                    for part in response["parts"]:
                        if part.get("type") == "text":
                            print(f"AI 回复: {part.get('text', '')[:100]}...")
            
            # 清理：删除会话
            if session_id:
                success, error = await client.delete_session(str(session_id))
                if success:
                    print(f"删除会话成功: {session_id}")
                else:
                    print(f"删除会话失败: {error}")
        
    finally:
        await client.close()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_client())