#!/usr/bin/env python3
"""
OpenCode异步客户端
用于与OpenCode HTTP服务器交互的异步Python客户端

基于simple_send.py重构，支持异步操作和配置集成
"""

import aiohttp
import asyncio
import base64
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
try:
    from ..utils import config
except ImportError:
    # 当从外部脚本导入时（例如测试脚本）
    import sys
    import os
    # 尝试不同的路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from utils import config
    except ImportError:
        import config

logger = logging.getLogger(__name__)


class OpenCodeClient:
    """OpenCode异步HTTP客户端"""
    
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
        初始化OpenCode客户端
        
        Args:
            base_url: OpenCode服务器地址，默认为config.OPENCODE_BASE_URL
            username: Basic认证用户名
            password: Basic认证密码
            token: Bearer令牌
            directory: 工作目录
            timeout: 请求超时时间（秒）
            default_agent: 默认智能体
            default_model: 默认模型
            default_provider: 默认提供商
            cookies: HTTP Cookies
            enable_ntfy: 是否启用ntfy通知
            ntfy_topic: ntfy主题
        """
        # 使用配置默认值
        self.base_url = base_url or config.OPENCODE_BASE_URL.rstrip('/')
        self.username = username or config.OPENCODE_AUTH.get("username")
        self.password = password or config.OPENCODE_AUTH.get("password")
        self.token = token or config.OPENCODE_AUTH.get("token")
        self.directory = directory or config.OPENCODE_DIRECTORY
        self.timeout = timeout or config.OPENCODE_TIMEOUT
        self.default_agent = default_agent or config.OPENCODE_DEFAULT_AGENT
        self.default_model = default_model or config.OPENCODE_DEFAULT_MODEL
        self.default_provider = default_provider or config.OPENCODE_DEFAULT_PROVIDER
        self.cookies = cookies or config.OPENCODE_COOKIES.copy()
        self.enable_ntfy = enable_ntfy
        self.ntfy_topic = ntfy_topic
        
        # aiohttp会话
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 认证头部
        self.headers = self._build_auth_headers()
        self.headers.update({
            "Content-Type": "application/json",
            "x-opencode-directory": self.directory,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
        })
        
        # 状态
        self.connected = False
    
    def _build_auth_headers(self) -> Dict[str, str]:
        """构建认证头部"""
        headers = {}
        
        # Basic认证
        if self.username and self.password:
            auth_str = f"{self.username}:{self.password}"
            auth_b64 = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {auth_b64}"
        
        # Bearer令牌认证
        elif self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        return headers
    
    @staticmethod
    def parse_model_string(model_str: str) -> Tuple[str, str]:
        """
        解析模型字符串，格式为：供应商/模型名称
        
        支持格式：
        - "供应商/模型名称" -> ("供应商", "模型名称")
        - "模型名称" -> (使用默认提供商, "模型名称")
        
        Args:
            model_str: 模型字符串
        
        Returns:
            (供应商, 模型名称) 元组
        """
        if not model_str:
            return "", ""
        
        # 如果包含斜杠，则拆分
        if "/" in model_str:
            parts = model_str.split("/", 1)
            provider = parts[0]
            model = parts[1]
        else:
            # 不包含斜杠，尝试推断提供商
            model = model_str
            # 根据常见模式推断提供商
            if model.startswith("deepseek-"):
                provider = "deepseek"
            elif model.startswith("claude-"):
                provider = "anthropic"
            elif model.startswith("gpt-"):
                provider = "openai"
            else:
                # 默认为opencode
                provider = "opencode"
        
        return provider, model
    
    async def ensure_session(self) -> None:
        """确保aiohttp会话存在"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                cookies=self.cookies,
                headers=self.headers
            )
            self.connected = True
    
    async def close(self) -> None:
        """关闭客户端"""
        if self.session and not self.session.closed:
            await self.session.close()
        self.connected = False
        logger.info("OpenCode客户端已关闭")
    
    async def _send_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        extra_headers: Optional[Dict] = None
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        发送HTTP请求
        
        Args:
            method: HTTP方法（GET, POST, DELETE等）
            endpoint: API端点（相对路径）
            json_data: JSON请求体
            params: 查询参数
            
        Returns:
            (响应数据, 错误消息) 元组
        """
        await self.ensure_session()
        assert self.session is not None  # ensure_session保证session不为None
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # 合并默认 headers 和额外 headers
        request_headers = dict(self.headers)
        if extra_headers:
            request_headers.update(extra_headers)
        
        # 打印完整请求信息用于调试
        logger.info(f"[OpenCode请求] {method} {url}")
        logger.info(f"[OpenCode请求] Headers: {request_headers}")
        if json_data:
            logger.info(f"[OpenCode请求] Body: {json_data}")
        
        try:
            # 构建请求参数，只有当 json_data 不为 None 时才传递
            request_kwargs = {
                'method': method,
                'url': url,
                'headers': request_headers
            }
            if json_data is not None:
                request_kwargs['json'] = json_data
            if params is not None:
                request_kwargs['params'] = params
            
            async with self.session.request(**request_kwargs) as response:
                
                # 检查响应状态
                if response.status >= 400:
                    error_text = await response.text()
                    return None, f"HTTP {response.status}: {error_text}"
                
                # 尝试解析JSON响应
                try:
                    data = await response.json()
                    return data, None
                except (json.JSONDecodeError, aiohttp.ContentTypeError):
                    # 如果不是JSON，返回文本
                    text = await response.text()
                    return {"text": text}, None
                    
        except aiohttp.ClientError as e:
            return None, f"HTTP客户端错误: {str(e)}"
        except asyncio.TimeoutError:
            return None, f"请求超时 ({self.timeout}秒)"
        except Exception as e:
            return None, f"未知错误: {str(e)}"
    
    async def create_session(
        self, 
        title: Optional[str] = None,
        directory: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        创建新会话
        
        Args:
            title: 会话标题
            directory: 工作目录（如果提供，会在请求头中设置 Referer 和 x-opencode-directory）
            
        Returns:
            (会话 ID, 错误消息) 元组
        """
        session_title = title or f"QQ 机器人会话_{asyncio.get_event_loop().time():.0f}"
        
        # 构建额外请求头（如果提供了 directory）
        extra_headers = {}
        if directory:
            # 构建 Referer 头：完整URL + Base64 编码的目录路径 + /session
            # 格式: http://127.0.0.1:4091/{directory_b64}/session
            directory_b64 = base64.b64encode(directory.encode()).decode()
            referer = f"{self.base_url}/{directory_b64}/session"
            extra_headers["Referer"] = referer
            extra_headers["x-opencode-directory"] = directory
        
        data, error = await self._send_request(
            method="POST",
            endpoint="/session",
            json_data={"title": session_title},
            extra_headers=extra_headers if extra_headers else None
        )
        
        if error:
            return None, error
        
        # 提取会话 ID
        session_id = data.get("id") if isinstance(data, dict) else None
        if not session_id:
            return None, "响应中未找到会话 ID"
        
        logger.info(f"创建 OpenCode 会话成功：{session_id} (标题：{session_title}, 目录：{directory})")
        return session_id, None
    
    async def send_message(
        self,
        message_text: str,
        session_id: Optional[str] = None,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        directory: Optional[str] = None,
        create_if_not_exists: bool = True
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        发送消息到OpenCode会话
        
        Args:
            message_text: 消息文本
            session_id: 会话ID，如果为None则创建新会话
            agent: 智能体名称
            model: 模型ID
            provider: 提供商ID
            create_if_not_exists: 如果会话不存在，是否创建新会话
            
        Returns:
            (响应数据, 错误消息) 元组
        """
        # 使用默认值
        agent = agent or self.default_agent
        model = model or self.default_model
        provider = provider or self.default_provider
        
        # 解析模型字符串（如果提供的是组合格式）
        if model and "/" in model:
            parsed_provider, parsed_model = self.parse_model_string(model)
            model = parsed_model
            # 只有当没有显式提供provider时才使用解析出的provider
            if not provider:
                provider = parsed_provider
        elif not provider:
            # 如果没有provider，尝试从模型推断
            if model and model.startswith("deepseek-"):
                provider = "deepseek"
            else:
                # 使用默认provider
                provider = provider or self.default_provider
        
        # 检查会话ID
        if not session_id:
            if create_if_not_exists:
                session_id, error = await self.create_session()
                if error:
                    return None, f"创建会话失败: {error}"
            else:
                return None, "未提供会话ID且create_if_not_exists=False"
        
        # 构建消息载荷
        payload = {
            "agent": agent,
            "model": {
                "modelID": model,
                "providerID": provider
            },
            "parts": [{
                "type": "text",
                "text": message_text
            }]
        }
        
        # 构建额外请求头（如果提供了 directory）
        extra_headers = {}
        if directory:
            # 构建 Referer 头：完整URL + Base64 编码的目录路径 + /session + 会话ID
            # 格式: http://127.0.0.1:4091/{directory_b64}/session/{session_id}
            directory_b64 = base64.b64encode(directory.encode()).decode()
            referer = f"{self.base_url}/{directory_b64}/session/{session_id}"
            extra_headers["Referer"] = referer
            extra_headers["x-opencode-directory"] = directory
        
        # 发送消息
        data, error = await self._send_request(
            method="POST",
            endpoint=f"/session/{session_id}/message",
            json_data=payload,
            extra_headers=extra_headers if extra_headers else None
        )
        
        if error:
            return None, error
        
        # 添加会话ID到响应中（用于新建会话的情况）
        if isinstance(data, dict) and "session_id" not in data:
            data["session_id"] = session_id
        
        logger.info(f"发送消息成功，会话: {session_id}, 长度: {len(message_text)}字符")
        return data, None
    
    async def list_messages(self, session_id: str, limit: Optional[int] = None, directory: Optional[str] = None) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """
        列出会话中的消息
        
        Args:
            session_id: 会话ID
            limit: 返回的消息数量限制
            directory: 工作目录（可选，默认使用 self.directory）
            
        Returns:
            (消息列表, 错误消息) 元组
        """
        # 构建额外请求头
        extra_headers = None
        if directory or self.directory:
            work_directory = directory or self.directory
            directory_b64 = base64.b64encode(work_directory.encode()).decode()
            extra_headers = {
                "Referer": f"{self.base_url}/{directory_b64}/session/{session_id}",
                "x-opencode-directory": work_directory
            }
        
        params = {"limit": limit} if limit else None
        data, error = await self._send_request(
            method="GET",
            endpoint=f"/session/{session_id}/message",
            params=params,
            extra_headers=extra_headers
        )
        
        if error:
            return None, error
        
        # 确保返回列表
        if isinstance(data, dict):
            # 如果是单个消息对象，包装成列表
            if "info" in data:
                data = [data]
            elif "messages" in data:
                data = data["messages"]
        
        return data if isinstance(data, list) else [], None
    
    async def list_sessions(self, limit: int = 50) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """
        列出所有会话
        
        Args:
            limit: 返回的会话数量限制
            
        Returns:
            (会话列表, 错误消息) 元组
        """
        data, error = await self._send_request(
            method="GET",
            endpoint="/session",
            params={"limit": limit} if limit else None
        )
        
        if error:
            return None, error
        
        # 确保返回列表
        if isinstance(data, dict):
            # 如果是单个对象，包装成列表
            if "id" in data:
                data = [data]
            elif "sessions" in data:
                data = data["sessions"]
        
        return data if isinstance(data, list) else [], None
    
    async def get_session(self, session_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        获取会话详情
        
        Args:
            session_id: 会话ID
            
        Returns:
            (会话详情, 错误消息) 元组
        """
        data, error = await self._send_request(
            method="GET",
            endpoint=f"/session/{session_id}"
        )
        
        if error:
            return None, error
        
        return data, None
    
    async def delete_session(self, session_id: str) -> Tuple[bool, Optional[str]]:
        """
        删除会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            (是否成功, 错误消息) 元组
        """
        _, error = await self._send_request(
            method="DELETE",
            endpoint=f"/session/{session_id}"
        )
        
        if error:
            return False, error
        
        logger.info(f"删除会话成功: {session_id}")
        return True, None
    
    
    async def summarize_session(
        self,
        session_id: str,
        provider_id: str,
        model_id: str,
        directory: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        压缩/总结当前会话上下文（异步版本）
        
        Args:
            session_id: 会话 ID
            provider_id: 提供商 ID
            model_id: 模型 ID
            directory: 工作目录（可选，默认使用 self.directory）
            
        Returns:
            (是否成功，错误消息) 元组
        """
        # 使用传入的 directory 或默认值
        work_directory = directory or self.directory or "/"
        directory_b64 = base64.b64encode(work_directory.encode()).decode()
        
        url = f"{config.OPENCODE_BASE_URL}/session/{session_id}/summarize"
        
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/{directory_b64}/session/{session_id}",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "sec-ch-ua": '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "x-opencode-directory": work_directory
        }
        
        json_data = {
            "providerID": provider_id,
            "modelID": model_id
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=1200)
            async with aiohttp.ClientSession(timeout=timeout) as client:
                async with client.post(
                    url,
                    cookies=config.OPENCODE_COOKIES,
                    headers=headers,
                    json=json_data
                ) as response:
                    if response.status == 200:
                        logger.info(f"压缩会话成功：{session_id}")
                        return True, None
                    else:
                        text = await response.text()
                        return False, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"压缩会话失败：{e}")
            return False, str(e)

    async def abort_session(self, session_id: str, directory: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        中止/停止当前 OpenCode 会话（异步版本）
        
        Args:
            session_id: 会话 ID
            directory: 工作目录（可选，默认使用 self.directory）
            
        Returns:
            (是否成功，错误消息) 元组
        """
        # 使用传入的 directory 或默认值
        work_directory = directory or self.directory or "/"
        directory_b64 = base64.b64encode(work_directory.encode()).decode()
        
        url = f"{config.OPENCODE_BASE_URL}/session/{session_id}/abort"
        
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/{directory_b64}/session/{session_id}",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "sec-ch-ua": '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "x-opencode-directory": work_directory
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as client:
                async with client.post(
                    url,
                    cookies=config.OPENCODE_COOKIES,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        logger.info(f"中止会话成功：{session_id}")
                        return True, None
                    else:
                        text = await response.text()
                        return False, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"中止会话失败：{e}")
            return False, str(e)
    
    async def revert_last_message(self, session_id: str, directory: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        撤销会话中的最后一条消息（异步版本）
        
        Args:
            session_id: 会话 ID
            directory: 工作目录（可选，默认使用 self.directory）
            
        Returns:
            (是否成功，错误消息) 元组
        """
        # 使用传入的 directory 或默认值
        work_directory = directory or self.directory or "/"
        directory_b64 = base64.b64encode(work_directory.encode()).decode()
        
        # 先获取消息列表以获取最后一条消息的 ID
        messages, error = await self.list_messages(session_id, limit=10)
        
        message_id = None
        if messages:
            # 从后往前找第一条有效的消息
            for msg in reversed(messages):
                if isinstance(msg, dict) and "info" in msg:
                    message_id = msg["info"].get("id")
                    break
        
        url = f"{config.OPENCODE_BASE_URL}/session/{session_id}/revert"
        
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/{directory_b64}/session/{session_id}",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "sec-ch-ua": '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "x-opencode-directory": work_directory
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as client:
                # 如果有 messageID，发送 JSON 请求体
                if message_id:
                    async with client.post(
                        url,
                        cookies=config.OPENCODE_COOKIES,
                        headers=headers,
                        json={"messageID": message_id}
                    ) as response:
                        if response.status == 200:
                            logger.info(f"撤销最后一条消息成功：{session_id}, messageID: {message_id}")
                            return True, None
                        else:
                            text = await response.text()
                            return False, f"HTTP {response.status}: {text}"
                else:
                    # 没有 messageID，不发送请求体
                    async with client.post(
                        url,
                        cookies=config.OPENCODE_COOKIES,
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            logger.info(f"撤销最后一条消息成功：{session_id}")
                            return True, None
                        else:
                            text = await response.text()
                            return False, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"撤销消息失败：{e}")
            return False, str(e)
    
    async def unrevert_messages(self, session_id: str, directory: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        恢复所有撤销的消息（异步版本）
        
        Args:
            session_id: 会话 ID
            directory: 工作目录（可选，默认使用 self.directory）
            
        Returns:
            (是否成功，错误消息) 元组
        """
        # 使用传入的 directory 或默认值
        work_directory = directory or self.directory or "/"
        directory_b64 = base64.b64encode(work_directory.encode()).decode()
        
        url = f"{config.OPENCODE_BASE_URL}/session/{session_id}/unrevert"
        
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/{directory_b64}/session/{session_id}",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "sec-ch-ua": '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "x-opencode-directory": work_directory
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as client:
                async with client.post(
                    url,
                    cookies=config.OPENCODE_COOKIES,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        logger.info(f"恢复所有撤销的消息成功：{session_id}")
                        return True, None
                    else:
                        text = await response.text()
                        return False, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"恢复消息失败：{e}")
            return False, str(e)
    
    async def get_models(self) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """
        获取可用模型列表
        
        注意：OpenCode API可能需要调用/config/providers端点
        
        Returns:
            (模型列表, 错误消息) 元组
        """
        # 尝试获取providers配置
        data, error = await self._send_request(
            method="GET",
            endpoint="/config/providers"
        )
        
        if error:
            return None, error
        
        # 解析模型列表
        models = []
        if isinstance(data, dict) and "providers" in data:
            for provider in data["providers"]:
                provider_id = provider.get("id") if isinstance(provider, dict) else ""
                provider_name = provider.get("name", provider_id) if isinstance(provider, dict) else str(provider_id)
                
                # models 可能是字典格式 {"model-id": {...}} 或列表格式 [{...}, ...]
                provider_models = provider.get("models") if isinstance(provider, dict) else None
                
                if isinstance(provider_models, dict):
                    # 字典格式: {"model-id": {model_data}, ...}
                    for model_id, model_data in provider_models.items():
                        if isinstance(model_data, dict):
                            models.append({
                                "provider_id": provider_id,
                                "provider_name": provider_name,
                                "model_id": model_id,
                                "model_name": model_data.get("name", model_id),
                                "description": model_data.get("description", ""),
                                "context_length": model_data.get("limit", {}).get("context"),
                                "max_output_tokens": model_data.get("limit", {}).get("output"),
                            })
                        else:
                            # model_data 不是字典，直接用 model_id
                            models.append({
                                "provider_id": provider_id,
                                "provider_name": provider_name,
                                "model_id": str(model_id),
                                "model_name": str(model_id),
                            })
                elif isinstance(provider_models, list):
                    # 列表格式: [{model_data}, ...]
                    for model in provider_models:
                        if isinstance(model, dict):
                            model_id = model.get("id", "")
                            models.append({
                                "provider_id": provider_id,
                                "provider_name": provider_name,
                                "model_id": model_id,
                                "model_name": model.get("name", model_id),
                                "description": model.get("description", ""),
                                "context_length": model.get("contextLength"),
                                "max_output_tokens": model.get("maxOutputTokens"),
                            })
        
        return models, None
    
    async def get_agents(self) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """
        获取可用智能体列表
        
        Returns:
            (智能体列表, 错误消息) 元组
        """
        data, error = await self._send_request(
            method="GET",
            endpoint="/agent"
        )
        
        if error:
            return None, error
        
# 如果返回的是列表，直接返回
        if isinstance(data, list):
            return data, None
        
        # 否则尝试解析
        agents = []
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    agents.append({
                        "id": key,
                        "name": value.get("name", key),
                        "description": value.get("description", "")
                    })
                else:
                    agents.append({
                        "id": key,
                        "name": key,
                        "description": str(value)
                    })
        
        return agents, None
    
    async def list_commands(self) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """
        获取可用的斜杠命令列表
        
        Returns:
            (命令列表, 错误消息) 元组
        """
        data, error = await self._send_request(
            method="GET",
            endpoint="/command"
        )
        
        if error:
            return None, error
        
        # 如果返回的是列表，直接返回
        if isinstance(data, list):
            return data, None
        
        # 否则尝试解析
        commands = []
        if isinstance(data, dict):
            if "commands" in data:
                commands = data["commands"]
            else:
                # 可能是单个命令对象
                commands = [data]
        
        return commands, None
    
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
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        在指定会话中执行斜杠命令
        
        Args:
            session_id: 会话 ID
            command: 命令名称（如 /git, /refactor 等，会自动去除/前缀）
            message_id: 消息 ID（可选）
            agent: 智能体名称（可选）
            model: 模型 ID（可选）
            provider: 提供商 ID（可选）
            arguments: 命令参数（可选，默认为空字符串）
            directory: 工作目录（可选，默认使用 self.directory）
            
        Returns:
            (响应数据 {info: Message, parts: Part[]}, 错误消息) 元组
        """
        # 去除命令的 / 前缀
        if command.startswith("/"):
            command = command[1:]
        
        # 使用传入的 provider 和 model
        model_str = model or self.default_model
        provider_str = provider or self.default_provider
        
        # 如果没有传入 provider，尝试从 model 字符串解析
        if not provider_str and "/" in model_str:
            provider_str, model_str = self.parse_model_string(model_str)
        
        # 构建 model 字符串（API 期望字符串格式：provider/model）
        if provider_str and model_str:
            model_value = f"{provider_str}/{model_str}"
        else:
            model_value = model_str or provider_str or ""
        
        # 构建请求体（必须包含所有字段）
        payload = {
            "command": command,
            "arguments": arguments or "",
            "agent": agent or self.default_agent,
            "model": model_value,
            "parts": []
        }
        
        if message_id:
            payload["messageID"] = message_id
        
        # 构建额外请求头
        extra_headers = None
        if directory or self.directory:
            work_directory = directory or self.directory
            directory_b64 = base64.b64encode(work_directory.encode()).decode()
            extra_headers = {
                "Referer": f"{self.base_url}/{directory_b64}/session/{session_id}",
                "x-opencode-directory": work_directory
            }
        
        data, error = await self._send_request(
            method="POST",
            endpoint=f"/session/{session_id}/command",
            json_data=payload,
            extra_headers=extra_headers
        )
        
        if error:
            return None, error
        
        logger.info(f"执行命令成功：{command}，会话：{session_id}")
        return data, None
    
    async def health_check(self) -> Tuple[bool, Optional[str]]:
        """
        健康检查
        
        Returns:
            (是否健康, 错误消息) 元组
        """
        data, error = await self._send_request(
            method="GET",
            endpoint="/global/health"
        )
        
        if error:
            return False, error
        
        # 检查健康状态
        if isinstance(data, dict):
            status = data.get("status", "").lower()
            return status == "healthy", data.get("message", "未知状态")
        
        return True, None
    
    async def send_ntfy_notification(self, message: str, title: Optional[str] = None) -> None:
        """发送ntfy通知（如果启用）"""
        if not self.enable_ntfy:
            return
        
        try:
            # 导入ntfy通知脚本
            import sys
            sys.path.append(r'C:\Users\Axeuh\.config\opencode\skills\ntfy-notification\scripts')
            from send_notification import send_ntfy_notification
            
            response = send_ntfy_notification(
                topic=self.ntfy_topic,
                message=message,
                title=title or "OpenCode客户端通知",
                priority="default"
            )
            
            if response.status_code == 200:
                logger.debug(f"ntfy通知发送成功: {message}")
            else:
                logger.warning(f"ntfy通知发送失败: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"发送ntfy通知失败: {e}")


# 同步接口包装器（为了向后兼容）
class OpenCodeClientSync:
    """OpenCode同步客户端（包装异步客户端）"""
    
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
    
    def create_session(self, title: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        return self._run_async(self.client.create_session(title))
    
    def send_message(self, message_text: str, session_id: Optional[str] = None, **kwargs) -> Tuple[Optional[Dict], Optional[str]]:
        return self._run_async(self.client.send_message(message_text, session_id, **kwargs))
    
    def list_sessions(self, limit: int = 50) -> Tuple[Optional[List[Dict]], Optional[str]]:
        return self._run_async(self.client.list_sessions(limit))
    
    def get_session(self, session_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        return self._run_async(self.client.get_session(session_id))
    
    def list_messages(self, session_id: str, limit: Optional[int] = None) -> Tuple[Optional[List[Dict]], Optional[str]]:
        return self._run_async(self.client.list_messages(session_id, limit))
    
    def delete_session(self, session_id: str) -> Tuple[bool, Optional[str]]:
        return self._run_async(self.client.delete_session(session_id))
    
    def abort_session(self, session_id: str) -> Tuple[bool, Optional[str]]:
        return self._run_async(self.client.abort_session(session_id))
    
    def revert_last_message(self, session_id: str) -> Tuple[bool, Optional[str]]:
        return self._run_async(self.client.revert_last_message(session_id))
    
    def unrevert_messages(self, session_id: str) -> Tuple[bool, Optional[str]]:
        return self._run_async(self.client.unrevert_messages(session_id))
    
    def get_models(self) -> Tuple[Optional[List[Dict]], Optional[str]]:
        return self._run_async(self.client.get_models())
    
    def get_agents(self) -> Tuple[Optional[List[Dict]], Optional[str]]:
        return self._run_async(self.client.get_agents())
    
    def health_check(self) -> Tuple[bool, Optional[str]]:
        return self._run_async(self.client.health_check())
    
    def close(self):
        self._run_async(self.client.close())
        self.loop.close()


# 简单测试函数
async def test_client():
    """测试OpenCode客户端"""
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
                            print(f"AI回复: {part.get('text', '')[:100]}...")
            
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