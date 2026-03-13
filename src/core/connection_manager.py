#!/usr/bin/env python3
"""
WebSocket连接管理器
负责OneBot客户端的WebSocket连接、重连、心跳和消息接收
"""

from __future__ import annotations

import asyncio
import json
import logging
import aiohttp
from typing import Dict, List, Optional, Any, Callable, Union
from src.utils import config

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        """初始化连接管理器"""
        self.ws_url = config.WS_URL
        self.access_token = config.ACCESS_TOKEN
        self.heartbeat_interval = config.HEARTBEAT_INTERVAL
        self.reconnect_interval = config.RECONNECT_INTERVAL
        self.bot_name = config.BOT_NAME
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.connected = False
        
        # 重连控制
        self.retry_count = 0
        self.max_retries = 0  # 0表示无限重试
        self.base_reconnect_delay = 10.0
        self.max_reconnect_delay = 300.0
        
        # 消息处理器
        self.message_handlers: List[Dict] = []
        
        # API请求管理
        self.echo_counter = 1
        self.pending_requests: Dict[Union[int, str], asyncio.Future] = {}
        
        # 任务管理
        self.tasks: List[asyncio.Task] = []
        self.restarting = False
    
    def register_message_handler(self, post_type: str, handler: Callable):
        """注册消息处理器
        
        Args:
            post_type: 消息类型（'message', 'meta_event', 'notice', 'request'）
            handler: 处理函数
        """
        self.message_handlers.append({
            'post_type': post_type,
            'handler': handler
        })
    
    async def cleanup_connection(self):
        """清理旧的连接资源，但不取消所有任务"""
        if self.ws and not self.ws.closed:
            try:
                await self.ws.close()
            except Exception as e:
                logger.warning(f"关闭WebSocket时出错: {e}")
        
        if self.session and not self.session.closed:
            try:
                await self.session.close()
            except Exception as e:
                logger.warning(f"关闭HTTP会话时出错: {e}")
        
        # 重置连接相关状态
        self.ws = None
        self.session = None
        self.connected = False
    
    async def connect(self):
        """连接到WebSocket服务器"""
        # 清理旧的连接资源
        await self.cleanup_connection()
        
        # 构建连接URL，包含access_token作为查询参数（NapCat要求）
        connect_url = self.ws_url
        if self.access_token:
            # 检查URL是否已有查询参数
            separator = '&' if '?' in connect_url else '?'
            connect_url = f"{connect_url}{separator}access_token={self.access_token}"
        
        logger.info(f"正在连接到 {connect_url}...")
        
        headers = {}
        # 注意：NapCat主要使用URL查询参数，但我们也保留HTTP头以防万一
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        
        # 添加配置中的额外头部
        headers.update(config.WS_EXTRA_HEADERS)
        
        logger.debug(f"连接URL: {connect_url}")
        logger.debug(f"请求头: {headers}")
        
        try:
            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(
                connect_url,
                headers=headers,
                heartbeat=self.heartbeat_interval / 1000  # 转换为秒
            )
            
            self.connected = True
            # 连接成功，重置重试计数器
            if self.retry_count > 0:
                logger.info(f"连接成功，重置重试计数器（之前尝试次数: {self.retry_count}）")
                self.retry_count = 0
            logger.info("✓ 已连接到NapCat WebSocket服务器")
            
            # 启动消息接收循环
            receive_task = asyncio.create_task(self.receive_messages())
            self.tasks.append(receive_task)
            
            # 启动心跳任务（如果需要）
            if self.heartbeat_interval > 0:
                heartbeat_task = asyncio.create_task(self.heartbeat_loop())
                self.tasks.append(heartbeat_task)
            
            return True
            
        except aiohttp.ClientConnectorError as e:
            logger.error(f"✗ 网络连接失败: {e}")
            logger.error("请检查:")
            logger.error("1. NapCat是否正在运行")
            logger.error("2. WebSocket服务器端口3001是否已打开")
            logger.error("3. 防火墙是否阻止了本地连接")
            raise e
        except aiohttp.WSServerHandshakeError as e:
            logger.error(f"✗ WebSocket握手失败: {e}")
            logger.error("可能的原因:")
            logger.error("1. Access Token错误或过期")
            logger.error("2. NapCat WebSocket服务器配置错误")
            logger.error(f"当前使用的Token: {'已设置' if self.access_token else '未设置'}")
            if self.access_token:
                logger.error(f"Token长度: {len(self.access_token)}字符")
            raise e
        except aiohttp.ClientResponseError as e:
            logger.error(f"✗ 服务器响应错误: {e}")
            logger.error(f"状态码: {e.status}, 消息: {e.message}")
            logger.error("请检查NapCat日志以获取更多信息")
            raise e
        except asyncio.TimeoutError as e:
            logger.error(f"✗ 连接超时: {e}")
            logger.error("NapCat服务器响应太慢或网络问题")
            raise e
        except Exception as e:
            logger.error(f"✗ 未知错误: {e}")
            logger.error("请检查:")
            logger.error("1. Python依赖是否安装 (pip install aiohttp)")
            logger.error("2. NapCat版本是否兼容")
            logger.error("3. 系统资源是否充足")
            raise e
    
    async def disconnect(self):
        """断开连接"""
        self.connected = False
        
        # 取消所有任务
        for task in self.tasks:
            task.cancel()
        
        # 关闭WebSocket
        if self.ws:
            await self.ws.close()
        
        # 关闭会话
        if self.session:
            await self.session.close()
        
        # 清理待处理请求
        for future in self.pending_requests.values():
            if not future.done():
                future.cancel()
        self.pending_requests.clear()
        
        logger.info("连接已断开")
    
    async def receive_messages(self):
        """接收WebSocket消息"""
        if self.ws is None:
            logger.error("WebSocket连接不存在")
            return
        
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self.process_message(data)
                    except json.JSONDecodeError:
                        logger.error(f"JSON解析错误: {msg.data}")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket错误: {msg.data}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("WebSocket连接已关闭")
                    break
        except Exception as e:
            logger.error(f"接收消息时发生错误: {e}")
        finally:
            self.connected = False
            logger.info("WebSocket连接已断开")
    
    async def process_message(self, message: Dict):
        """处理接收到的消息
        
        Args:
            message: 原始消息数据
        """
        # 首先检查是否为API响应（包含echo字段）
        echo = message.get('echo')
        if echo is not None:
            # 处理NapCat Issue #950：空字符串echo问题
            if isinstance(echo, str) and echo == "":
                # 空字符串echo，不尝试匹配pending_requests（NapCat已知问题）
                logger.debug(f"收到空字符串echo，跳过匹配（NapCat Issue #950）")
                logger.debug(f"完整消息内容: {message}")
                return
            
            # 调试日志：记录echo处理和pending_requests状态
            logger.debug(f"处理消息echo: {repr(echo)}, 类型: {type(echo)}")
            logger.debug(f"pending_requests keys: {list(self.pending_requests.keys())}")
            
            # OneBot v11规范：echo可以是任意类型，需要尝试所有可能的匹配
            # 机器人代码存储的键是字符串（如："1", "2", "3"...），但NapCat可能返回整数或字符串
            
            future = None
            matched_key = None
            
            # 方法1：尝试直接匹配（如果echo是字符串且存在）
            if isinstance(echo, str) and echo in self.pending_requests:
                future = self.pending_requests.pop(echo)
                matched_key = echo
            
            # 方法2：尝试将echo转换为字符串后匹配（如果NapCat返回整数echo）
            if future is None:
                echo_str = str(echo)
                if echo_str in self.pending_requests:
                    future = self.pending_requests.pop(echo_str)
                    matched_key = echo_str
            
            # 方法3：尝试类型转换匹配（复杂情况，如echo是对象等）
            if future is None:
                # 尝试处理数字echo的特殊情况
                try:
                    if isinstance(echo, (int, float)):
                        # 如果是数字，尝试多种表示方式
                        possible_keys = [
                            str(int(echo)),    # "123"
                            str(float(echo)),  # "123.0"
                            echo,              # 123
                            str(echo)          # "123"（备用）
                        ]
                        for key in possible_keys:
                            if key in self.pending_requests:
                                future = self.pending_requests.pop(key)
                                matched_key = key
                                break
                except (ValueError, TypeError):
                    pass
            
            if future:
                if not future.done():
                    try:
                        future.set_result(message)
                        logger.info(f"✅ API响应匹配成功: echo={repr(echo)} -> 匹配键={repr(matched_key)}")
                    except asyncio.CancelledError:
                        # Future已被取消（超时后），但仍记录响应到达信息
                        logger.warning(f"响应到达但Future已取消: echo={repr(echo)}，匹配键={repr(matched_key)}")
                        # 清理条目（如果仍在pending_requests中）
                        if matched_key in self.pending_requests:
                            self.pending_requests.pop(matched_key, None)
                    except Exception as e:
                        logger.error(f"设置Future结果失败: {e}")
                        # 如果Future已取消，清理条目
                        if matched_key in self.pending_requests:
                            self.pending_requests.pop(matched_key, None)
                else:
                    # future 已完成（可能是超时取消），但仍记录响应信息
                    future_state = "已完成" if future.cancelled() else "已取消"
                    logger.warning(f"响应迟到：echo={repr(echo)}，匹配键={repr(matched_key)}，future状态={future_state}")
                    # 清理已完成或取消的Future
                    if matched_key in self.pending_requests:
                        self.pending_requests.pop(matched_key, None)
                return
            else:
                # 没有对应的 pending 请求，这是正常的 API 响应确认
                logger.debug(f"收到 API 响应确认 echo={repr(echo)}")
                return
        
        # 如果不是API响应，调用对应的处理器
        post_type = message.get('post_type')
        
        if not post_type:
            logger.debug(f"收到无 post_type 的消息：{message}")
            return
        
        # 调用对应的处理器
        for handler_info in self.message_handlers:
            if handler_info['post_type'] == post_type:
                try:
                    await handler_info['handler'](message)
                except Exception as e:
                    logger.error(f"消息处理器错误: {e}")
    
    async def heartbeat_loop(self):
        """心跳循环（如果需要主动发送心跳）"""
        try:
            while self.connected:
                await asyncio.sleep(self.heartbeat_interval / 1000)
                if self.connected:
                    # OneBot V11 通常由服务器发送心跳，客户端只需响应
                    pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"心跳循环错误: {e}")
    
    async def schedule_reconnect(self):
        """计划重连（固定10秒间隔）"""
        if not self.connected:
            # 固定10秒重连间隔
            delay = 10.0
            self.retry_count += 1
            
            logger.info(f"重连尝试 {self.retry_count}，{delay:.1f}秒后重试...")
            logger.info(f"请检查: 1. NapCat是否运行 2. WebSocket服务器端口3001 3. Token是否正确")
            
            await asyncio.sleep(delay)
            if not self.connected:
                await self.connect()
    
    async def run(self):
        """运行连接管理器（主循环）- 持续尝试连接直到成功"""
        try:
            while not self.restarting:
                try:
                    await self.connect()
                    
                    # 连接成功，保持运行直到断开或重启
                    while self.connected and not self.restarting:
                        await asyncio.sleep(1)
                        
                    # 如果连接断开但不是重启，等待10秒后重试
                    if not self.restarting:
                        logger.info("连接断开，10秒后尝试重连...")
                        await asyncio.sleep(10)
                        
                except KeyboardInterrupt:
                    logger.info("收到中断信号，正在关闭...")
                    break
                except Exception as e:
                    logger.error(f"连接过程错误: {e}")
                    if not self.restarting:
                        logger.info("10秒后尝试重连...")
                        await asyncio.sleep(10)
                        
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭...")
        except Exception as e:
            logger.error(f"连接管理器运行错误: {e}")
        finally:
            # 如果不是重启过程，则断开连接
            if not self.restarting:
                await self.disconnect()
    
    async def send_action(self, action: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """发送API动作
        
        Args:
            action: API动作名称
            params: 动作参数
            
        Returns:
            发送的请求数据，或None（发送失败）
        """
        if not self.connected or not self.ws:
            logger.error("无法发送消息：WebSocket未连接")
            return None
        
        if params is None:
            params = {}
        
        request = {
            'action': action,
            'params': params,
            'echo': str(self.echo_counter)  # 使用字符串echo，避免NapCat Issue #950
        }
        self.echo_counter += 1
        
        try:
            logger.debug(f"发送动作: {action}, 参数: {params}")
            await self.ws.send_json(request)
            return request
        except Exception as e:
            logger.error(f"发送动作失败: {e}")
            return None
    
    async def send_action_with_response(self, action: str, params: Optional[Dict[str, Any]] = None, 
                                        timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """发送API动作并等待响应
        
        Args:
            action: API动作名称
            params: 动作参数
            timeout: 超时时间（秒）
            
        Returns:
            API响应数据，或None（超时或错误）
        """
        if not self.connected or not self.ws:
            logger.error("无法发送消息：WebSocket未连接")
            return None
        
        if params is None:
            params = {}
        
        # 创建Future来等待响应
        future = asyncio.Future()
        # 强制使用字符串echo，确保JSON序列化后仍是字符串
        request_echo = f"{self.echo_counter}"  # 使用f-string确保字符串类型
        # 递增计数器用于下一个请求
        self.echo_counter += 1
        
        request = {
            'action': action,
            'params': params,
            'echo': request_echo  # 确保是字符串类型
        }
        
        # 存储Future（使用字符串键）
        self.pending_requests[request_echo] = future
        
        try:
            logger.debug(f"发送动作并等待响应: {action}, 参数: {params}, echo={request_echo}")
            logger.debug(f"完整请求JSON: {json.dumps(request, ensure_ascii=False)}")
            await self.ws.send_json(request)
            
            # 等待响应
            try:
                result = await asyncio.wait_for(future, timeout)
                return result
            except asyncio.TimeoutError:
                logger.error(f"等待响应超时: action={action}, echo={request_echo}")
                # 取消future（如果尚未完成）
                if not future.done():
                    future.cancel()
                # 延迟清理pending_requests，给迟到响应处理机会
                asyncio.create_task(self._delayed_cleanup(request_echo, delay=30.0))
                return None
                
        except Exception as e:
            logger.error(f"发送动作失败: {e}")
            # 移除失败的Future
            self.pending_requests.pop(request_echo, None)
            return None
    
    async def _delayed_cleanup(self, echo_key: Union[int, str], delay: float = 30.0):
        """延迟清理 pending_requests 中的条目
        
        Args:
            echo_key: 要清理的 echo 键（整数或字符串）
            delay: 延迟时间（秒），默认 30 秒
        """
        try:
            await asyncio.sleep(delay)
            
            # 检查键是否仍然存在且future可能未完成
            if echo_key in self.pending_requests:
                future = self.pending_requests[echo_key]
                if future.done():
                    # future已完成（响应已到达），无需清理
                    logger.debug(f"延迟清理时发现future已完成: echo_key={echo_key}, 状态={future}")
                    self.pending_requests.pop(echo_key, None)  # 清理已完成的项目
                else:
                    # future仍未完成（真正的超时），安全清理
                    self.pending_requests.pop(echo_key, None)
                    logger.debug(f"已延迟清理 pending_requests[{echo_key}]（超时未响应）")
            else:
                logger.debug(f"延迟清理时键已不存在: {echo_key}")
        except Exception as e:
            logger.debug(f"延迟清理时发生错误: {e}")
    
    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态
        
        Returns:
            包含连接状态信息的字典
        """
        return {
            'connected': self.connected,
            'retry_count': self.retry_count,
            'ws_url': self.ws_url,
            'has_access_token': bool(self.access_token),
            'pending_requests': len(self.pending_requests),
            'active_tasks': len([t for t in self.tasks if not t.done()])
        }


if __name__ == '__main__':
    # 简单测试
    import logging
    logging.basicConfig(level=logging.INFO)
    
    async def test():
        manager = ConnectionManager()
        try:
            # 注册一个简单的消息处理器
            async def handle_test_message(msg):
                print(f"收到消息: {msg.get('post_type')}")
            
            manager.register_message_handler('message', handle_test_message)
            
            # 运行连接管理器
            await manager.run()
        except KeyboardInterrupt:
            print("测试中断")
        finally:
            await manager.disconnect()
    
    asyncio.run(test())