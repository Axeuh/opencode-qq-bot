#!/usr/bin/env python3
"""
NapCat HTTP客户端模块
提供通过HTTP API调用NapCat功能的方法，作为WebSocket的备选方案
"""

import logging
import json
import asyncio
import aiohttp
from typing import Dict, Optional, Any, Union
from src.utils import config

logger = logging.getLogger(__name__)


class NapCatHttpClient:
    """NapCat HTTP API客户端"""
    
    def __init__(self):
        """初始化HTTP客户端"""
        self.base_url = config.HTTP_API_BASE_URL
        self.access_token = config.HTTP_API_ACCESS_TOKEN
        self.timeout = config.HTTP_API_TIMEOUT
        self.enabled = config.HTTP_API_ENABLED
        self.retry_count = config.HTTP_API_RETRY_COUNT
        self.retry_delay = config.HTTP_API_RETRY_DELAY
        
        # aiohttp会话
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 请求头
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.access_token}' if self.access_token else None,
            'User-Agent': 'AxeuhBot/1.0'
        }
        # 移除空的header值
        self.headers = {k: v for k, v in self.headers.items() if v is not None}
        
        logger.info(f"NapCat HTTP客户端初始化: base_url={self.base_url}, enabled={self.enabled}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def connect(self):
        """创建HTTP会话"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self.headers
            )
            logger.debug("NapCat HTTP客户端会话已创建")
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("NapCat HTTP客户端会话已关闭")
    
    def is_enabled(self) -> bool:
        """检查HTTP API是否启用"""
        return self.enabled
    
    async def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """发送HTTP请求到NapCat API
        
        Args:
            endpoint: API端点，如 '/get_msg'
            data: 请求数据
            
        Returns:
            响应数据字典，或None（请求失败）
        """
        if not self.enabled:
            logger.warning(f"HTTP API未启用，跳过请求: {endpoint}")
            return None
        
        await self.connect()
        
        url = f"{self.base_url.rstrip('/')}{endpoint}"
        
        for attempt in range(self.retry_count):
            try:
                logger.debug(f"发送HTTP请求到 {url} (尝试 {attempt+1}/{self.retry_count})")
                logger.debug(f"请求数据: {json.dumps(data, ensure_ascii=False)}")
                
                async with self.session.post(url, json=data) as response:
                    response_text = await response.text()
                    
                    logger.debug(f"HTTP响应状态: {response.status}")
                    logger.debug(f"HTTP响应内容: {response_text}")
                    
                    if response.status == 200:
                        try:
                            result = json.loads(response_text)
                            logger.info(f"HTTP请求成功: {endpoint}, 状态: {result.get('status', 'unknown')}")
                            return result
                        except json.JSONDecodeError as e:
                            logger.error(f"HTTP响应JSON解析失败: {e}, 响应内容: {response_text}")
                            # 如果是最后一次尝试，返回原始文本包装成字典
                            if attempt == self.retry_count - 1:
                                return {'status': 'error', 'message': f'JSON解析失败: {e}', 'raw_response': response_text}
                    else:
                        logger.warning(f"HTTP请求失败: {endpoint}, 状态码: {response.status}, 响应: {response_text}")
                        if attempt < self.retry_count - 1:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        return {'status': 'error', 'retcode': response.status, 'message': response_text}
                        
            except aiohttp.ClientError as e:
                logger.error(f"HTTP客户端错误: {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                return {'status': 'error', 'message': f'HTTP客户端错误: {e}'}
            except asyncio.TimeoutError:
                logger.error(f"HTTP请求超时: {endpoint}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                return {'status': 'error', 'message': '请求超时'}
            except Exception as e:
                logger.error(f"HTTP请求异常: {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                return {'status': 'error', 'message': f'请求异常: {e}'}
        
        return None
    
    async def get_msg(self, message_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """获取消息详情（HTTP API版本）
        
        Args:
            message_id: 消息ID（整数或字符串）
            
        Returns:
            消息数据字典，或None（获取失败）
        """
        try:
            # 转换message_id为整数（如果可能）
            msg_id = int(message_id) if str(message_id).isdigit() else message_id
            
            data = {
                "message_id": msg_id
            }
            
            result = await self._make_request('/get_msg', data)
            
            if result and result.get('status') == 'ok':
                return result.get('data', result)
            else:
                error_msg = result.get('message', 'Unknown error') if result else '请求失败'
                logger.warning(f"获取消息失败: message_id={message_id}, 错误: {error_msg}")
                return None
                
        except Exception as e:
            logger.error(f"get_msg调用异常: {e}")
            return None
    
    async def send_private_msg(self, user_id: int, message: str) -> Optional[Dict[str, Any]]:
        """发送私聊消息（HTTP API版本）
        
        Args:
            user_id: 用户QQ号
            message: 消息内容
            
        Returns:
            发送结果，或None（发送失败）
        """
        data = {
            "user_id": user_id,
            "message": message
        }
        
        result = await self._make_request('/send_private_msg', data)
        
        if result and result.get('status') == 'ok':
            return result.get('data', result)
        else:
            error_msg = result.get('message', 'Unknown error') if result else '请求失败'
            logger.warning(f"发送私聊消息失败: user_id={user_id}, 错误: {error_msg}")
            return None
    
    async def send_group_msg(self, group_id: int, message: str) -> Optional[Dict[str, Any]]:
        """发送群消息（HTTP API版本）
        
        Args:
            group_id: 群号
            message: 消息内容
            
        Returns:
            发送结果，或None（发送失败）
        """
        data = {
            "group_id": group_id,
            "message": message
        }
        
        result = await self._make_request('/send_group_msg', data)
        
        if result and result.get('status') == 'ok':
            return result.get('data', result)
        else:
            error_msg = result.get('message', 'Unknown error') if result else '请求失败'
            logger.warning(f"发送群消息失败: group_id={group_id}, 错误: {error_msg}")
            return None
    
    async def get_status(self) -> Optional[Dict[str, Any]]:
        """获取NapCat状态（HTTP API版本）
        
        Returns:
            状态信息，或None（获取失败）
        """
        result = await self._make_request('/get_status', {})
        
        if result and result.get('status') == 'ok':
            return result.get('data', result)
        else:
            return None
    
    async def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """获取文件信息（HTTP API版本）
        
        Args:
            file_id: 文件ID
            
        Returns:
            文件信息字典，包含 file, url, file_size, file_name
            或None（获取失败）
        """
        data = {
            "file_id": file_id
        }
        
        result = await self._make_request('/get_file', data)
        
        if result and result.get('status') == 'ok':
            file_data = result.get('data', result)
            logger.info(f"HTTP get_file 成功: file_id={file_id}, file={file_data.get('file', 'N/A')}")
            return file_data
        else:
            error_msg = result.get('message', 'Unknown error') if result else '请求失败'
            logger.warning(f"获取文件失败: file_id={file_id}, 错误: {error_msg}")
            return None
    
    async def get_image(self, file: str) -> Optional[Dict[str, Any]]:
        """获取图片信息（HTTP API版本）
        
        Args:
            file: 图片文件名或file_id
            
        Returns:
            图片信息字典，包含 file, url, file_size
            或None（获取失败）
        """
        data = {
            "file": file
        }
        
        result = await self._make_request('/get_image', data)
        
        if result and result.get('status') == 'ok':
            image_data = result.get('data', result)
            logger.info(f"HTTP get_image 成功: file={file}")
            return image_data
        else:
            error_msg = result.get('message', 'Unknown error') if result else '请求失败'
            logger.warning(f"获取图片失败: file={file}, 错误: {error_msg}")
            return None
    
    async def get_forward_msg(self, message_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """获取合并转发消息内容（HTTP API版本）
        
        Args:
            message_id: 合并转发消息ID
            
        Returns:
            消息数据字典，包含 messages 列表
            或None（获取失败）
        """
        data = {
            "message_id": message_id
        }
        
        result = await self._make_request('/get_forward_msg', data)
        
        if result and result.get('status') == 'ok':
            forward_data = result.get('data', {})
            messages = forward_data.get('messages', [])
            logger.info(f"HTTP get_forward_msg 成功: message_id={message_id}, 消息数={len(messages)}")
            return forward_data
        else:
            error_msg = result.get('message', 'Unknown error') if result else '请求失败'
            logger.warning(f"获取合并转发消息失败: message_id={message_id}, 错误: {error_msg}")
            return None
    
    async def test_connection(self) -> bool:
        """测试HTTP API连接
        
        Returns:
            连接是否成功
        """
        try:
            result = await self.get_status()
            if result:
                logger.info(f"HTTP API连接测试成功: {result}")
                return True
            else:
                logger.warning("HTTP API连接测试失败: 无响应")
                return False
        except Exception as e:
            logger.error(f"HTTP API连接测试异常: {e}")
            return False


async def test_napcat_http_client():
    """测试NapCat HTTP客户端"""
    import sys
    
    print("=== NapCat HTTP客户端测试 ===")
    
    async with NapCatHttpClient() as client:
        # 测试连接
        print("1. 测试连接...")
        if not client.is_enabled():
            print("HTTP API未启用，跳过测试")
            return
        
        connected = await client.test_connection()
        if not connected:
            print("连接测试失败，检查NapCat HTTP服务是否运行")
            return
        
        print("✓ 连接测试成功")
        
        # 测试get_msg（使用一个测试消息ID）
        # 这里需要提供一个实际的消息ID进行测试
        # 例如: test_message_id = 1822260651
        
        print("\n测试完成")
    

if __name__ == "__main__":
    asyncio.run(test_napcat_http_client())