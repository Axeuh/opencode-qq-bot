#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QQ工具脚本（WebSocket版本）- 扩展的QQ机器人功能

功能：
1. 发送私聊和群聊消息
2. 获取好友列表
3. 通过名称搜索QQ好友
4. 发送表情包（内置表情和图片表情）
5. 发送文件（私聊和群聊）

用法:
    # 发送消息（与原脚本兼容）
    python qq_tools_ws.py --action send --type private --target 123456 --message "你好"
    
    # 获取好友列表
    python qq_tools_ws.py --action get-friends --output-format json
    
    # 搜索好友
    python qq_tools_ws.py --action search-friend --name "小明"
    
    # 发送表情
    python qq_tools_ws.py --action send-face --target 123456 --face-id 123
    python qq_tools_ws.py --action send-image --target 123456 --image-url "file:///path/to/image.jpg"
    
    # 发送文件
    python qq_tools_ws.py --action send-file --type private --target 123456 --file "/path/to/file.xlsx"
    
    # 获取陌生人信息
    python qq_tools_ws.py --action get-stranger --user-id 123456789
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import uuid
from typing import Union, Dict, Any, List, Optional
import websockets

# 配置文件路径（技能目录下的config.json）
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

def load_config() -> Dict[str, Any]:
    """从配置文件加载配置"""
    config = {
        "server": "ws://localhost:3002",
        "token": None,
        "timeout": 30
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            print(f"警告: 读取配置文件失败: {e}", file=sys.stderr)
    return config

# 从配置文件加载默认值
_config = load_config()
DEFAULT_SERVER = _config.get("server", "ws://localhost:3002")
DEFAULT_TOKEN = _config.get("token")
DEFAULT_TIMEOUT = _config.get("timeout", 30)

class NapcatWebSocketClient:
    """Napcat WebSocket客户端（扩展版）"""
    
    def __init__(self, server: str = DEFAULT_SERVER, token: Optional[str] = DEFAULT_TOKEN, auto_reconnect: bool = True, max_retries: int = 3, retry_delay: float = 2.0):
        """
        初始化客户端
        
        Args:
            server: WebSocket服务器地址
            token: 认证令牌
            auto_reconnect: 是否自动重连（默认：True）
            max_retries: 最大重试次数（默认：3）
            retry_delay: 重试延迟（秒，默认：2.0）
        """
        self.server = server
        self.token = token
        self.websocket = None
        self.pending_responses = {}  # echo -> future
        self._receive_task = None
        self.verbose = False  # 详细输出标志
        self.is_connected = False
        self.is_connecting = False
        self.auto_reconnect = auto_reconnect
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_count = 0
        self.last_connect_time = None
        self._reconnect_lock = asyncio.Lock()
        # 缓存相关
        self.friend_list_cache = None
        self.friend_list_cache_time = 0
        self.cache_ttl = 60  # 缓存过期时间（秒）
        
    @staticmethod
    def win_path_to_wsl(windows_path: str) -> str:
        """
        将Windows文件路径转换为WSL可访问的路径
        
        Args:
            windows_path: Windows格式的文件路径（如 D:\\Users\\... 或 C:\\path\\to\\file）
            
        Returns:
            WSL格式的路径（如 /mnt/d/Users/... 或 /mnt/c/path/to/file）
            如果不是Windows路径或已经是WSL路径，则返回原路径
        """
        import re
        
        # 检查是否已经是WSL路径（以/mnt/开头）
        if windows_path.startswith('/mnt/'):
            return windows_path
            
        # 检查是否以驱动器盘符开头（如 C:, D: 等）
        drive_pattern = r'^([A-Za-z]):\\(.*)$'
        match = re.match(drive_pattern, windows_path)
        if not match:
            # 不是标准的Windows绝对路径，返回原路径
            return windows_path
            
        drive_letter = match.group(1).lower()
        path_remainder = match.group(2)
        
        # 转换为WSL路径
        wsl_path = f"/mnt/{drive_letter}/{path_remainder.replace('\\', '/')}"
        return wsl_path
        
    def build_ws_url(self) -> str:
        """构建带认证token的WebSocket URL"""
        if "?" in self.server:
            return f"{self.server}&access_token={self.token}"
        else:
            return f"{self.server}?access_token={self.token}"
    
    async def connect(self):
        """连接到WebSocket服务器（支持自动重连）"""
        async with self._reconnect_lock:
            if self.is_connecting:
                # 已经在连接中，等待连接完成
                return await self._wait_for_connection()
            
            self.is_connecting = True
            self.retry_count = 0
            
            try:
                # 尝试连接，支持重试
                success = await self._connect_with_retry()
                return success
            finally:
                self.is_connecting = False
    
    async def _connect_with_retry(self):
        """带重试的连接逻辑"""
        ws_url = self.build_ws_url()
        
        while self.retry_count <= self.max_retries:
            try:
                if self.verbose and self.retry_count > 0:
                    print(f"连接重试 {self.retry_count}/{self.max_retries}...", file=sys.stderr)
                
                self.websocket = await asyncio.wait_for(
                    websockets.connect(ws_url),
                    timeout=10
                )
                
                # 启动接收任务
                self._receive_task = asyncio.create_task(self._receive_loop())
                
                # 等待连接成功事件（可选）
                await asyncio.sleep(0.5)
                
                # 更新状态
                self.is_connected = True
                self.last_connect_time = asyncio.get_event_loop().time()
                self.retry_count = 0
                
                if self.verbose:
                    print(f"[OK] 连接成功: {self.server}", file=sys.stderr)
                
                return True
                
            except Exception as e:
                self.retry_count += 1
                
                if self.retry_count > self.max_retries:
                    self.is_connected = False
                    if self.verbose:
                        print(f"[ERROR] 连接失败，已达最大重试次数: {e}", file=sys.stderr)
                    raise ConnectionError(f"连接失败（重试{self.max_retries}次后）: {e}")
                
                # 指数退避延迟
                delay = self.retry_delay * (2 ** (self.retry_count - 1))
                if self.verbose:
                    print(f"[INFO] 连接失败，{delay:.1f}秒后重试: {e}", file=sys.stderr)
                await asyncio.sleep(delay)
    
    async def _wait_for_connection(self, timeout: float = 30.0):
        """等待连接完成"""
        start_time = asyncio.get_event_loop().time()
        while self.is_connecting:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError("等待连接超时")
            await asyncio.sleep(0.1)
        
        return self.is_connected
    
    async def _receive_loop(self):
        """接收消息循环"""
        if not self.websocket:
            return
            
        try:
            async for message_raw in self.websocket:
                # 将消息转换为字符串（websockets可能返回bytes或str）
                if isinstance(message_raw, bytes):
                    message = message_raw.decode('utf-8')
                else:
                    message = str(message_raw)
                await self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            self.is_connected = False
            if self.verbose:
                print("[INFO] WebSocket连接已关闭", file=sys.stderr)
        except Exception as e:
            print(f"接收循环错误: {e}", file=sys.stderr)
    
    async def _handle_message(self, message: str):
        """处理收到的消息"""
        try:
            data = json.loads(message)
            
            # 检查是否是API响应（有echo字段）
            echo = data.get("echo")
            if echo and echo in self.pending_responses:
                # 设置future结果
                future = self.pending_responses.pop(echo)
                future.set_result(data)
            else:
                # 其他事件（如meta_event, message等）
                if self.verbose:
                    print(f"收到事件: {json.dumps(data, ensure_ascii=False)[:200]}...")
                    
        except json.JSONDecodeError:
            print(f"无法解析JSON消息: {message[:100]}", file=sys.stderr)
    
    async def ensure_connected(self):
        """确保连接正常，如果断开则自动重连"""
        if self.is_connected and self.websocket and not getattr(self.websocket, 'closed', True):
            return True
        
        if not self.auto_reconnect:
            raise ConnectionError("连接已断开，自动重连已禁用")
        
        if self.verbose:
            print("[INFO] 连接已断开，尝试重新连接...", file=sys.stderr)
        
        try:
            # 清理旧连接
            if self._receive_task:
                self._receive_task.cancel()
                self._receive_task = None
            
            if self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass
                self.websocket = None
            
            self.is_connected = False
            
            # 重新连接
            await self.connect()
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"[ERROR] 自动重连失败: {e}", file=sys.stderr)
            raise ConnectionError(f"自动重连失败: {e}")
    
    async def send_request(self, action: str, params: Dict[str, Any], timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """
        发送API请求并等待响应（支持自动重连）
        
        Args:
            action: API动作名称
            params: 参数
            timeout: 超时时间（秒）
            
        Returns:
            API响应
        """
        # 确保连接正常
        await self.ensure_connected()
        
        if not self.websocket:
            raise ConnectionError("未连接到WebSocket服务器")
        
        # 生成唯一的echo标识
        echo = str(uuid.uuid4())
        
        # 创建请求
        request = {
            "action": action,
            "params": params,
            "echo": echo
        }
        
        # 创建future用于等待响应
        future = asyncio.Future()
        self.pending_responses[echo] = future
        
        max_send_retries = 2 if self.auto_reconnect else 0
        send_retry_count = 0
        
        while True:
            try:
                # 发送请求
                await self.websocket.send(json.dumps(request))
                
                # 等待响应
                response = await asyncio.wait_for(future, timeout=timeout)
                
                # 清理
                if echo in self.pending_responses:
                    del self.pending_responses[echo]
                    
                return response
                
            except (websockets.exceptions.ConnectionClosed, ConnectionError) as e:
                # 连接断开，尝试重连
                if send_retry_count >= max_send_retries or not self.auto_reconnect:
                    # 清理
                    if echo in self.pending_responses:
                        del self.pending_responses[echo]
                    raise ConnectionError(f"发送失败（重试{send_retry_count}次后）: {e}")
                
                send_retry_count += 1
                if self.verbose:
                    print(f"[INFO] 发送失败，尝试重新连接并重试 ({send_retry_count}/{max_send_retries}): {e}", file=sys.stderr)
                
                # 清理pending future
                if echo in self.pending_responses:
                    future = self.pending_responses.pop(echo)
                    if not future.done():
                        future.set_exception(e)
                
                # 重新连接
                try:
                    await self.ensure_connected()
                except Exception as reconnect_error:
                    if self.verbose:
                        print(f"[ERROR] 重连失败: {reconnect_error}", file=sys.stderr)
                    raise ConnectionError(f"发送失败且重连失败: {reconnect_error}")
                
                # 重新创建future（因为旧的已被清理）
                future = asyncio.Future()
                self.pending_responses[echo] = future
                continue
                
            except asyncio.TimeoutError:
                # 清理
                if echo in self.pending_responses:
                    del self.pending_responses[echo]
                raise TimeoutError(f"等待响应超时 ({timeout}秒)")
            
            except Exception as e:
                # 其他异常，不重试
                if echo in self.pending_responses:
                    del self.pending_responses[echo]
                raise
    
    async def send_private_message(self, user_id: str, message: Union[str, List[Dict[str, Any]]], auto_escape: bool = False) -> Dict[str, Any]:
        """
        发送私聊消息
        
        Args:
            user_id: QQ用户ID
            message: 消息内容
            auto_escape: 是否自动转义CQ码
            
        Returns:
            API响应
        """
        params = {
            "user_id": user_id,
            "message": message,
            "auto_escape": auto_escape
        }
        
        return await self.send_request("send_private_msg", params)
    
    async def send_group_message(self, group_id: str, message: Union[str, List[Dict[str, Any]]], auto_escape: bool = False) -> Dict[str, Any]:
        """
        发送群聊消息
        
        Args:
            group_id: 群ID
            message: 消息内容
            auto_escape: 是否自动转义CQ码
            
        Returns:
            API响应
        """
        params = {
            "group_id": group_id,
            "message": message,
            "auto_escape": auto_escape
        }
        
        return await self.send_request("send_group_msg", params)
    
    # ========== 新增功能 ==========
    
    async def get_friend_list(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取好友列表（带缓存支持）
        
        Args:
            force_refresh: 是否强制刷新缓存
            
        Returns:
            API响应，包含好友列表数据
        """
        current_time = asyncio.get_event_loop().time()
        
        # 检查缓存是否有效
        if (not force_refresh and 
            self.friend_list_cache is not None and 
            current_time - self.friend_list_cache_time < self.cache_ttl):
            
            if self.verbose:
                print(f"[INFO] 使用缓存的好友列表（{int(current_time - self.friend_list_cache_time)}秒前）", file=sys.stderr)
            
            # 返回缓存数据的副本，防止外部修改
            return {
                "status": "ok",
                "retcode": 0,
                "data": self.friend_list_cache.copy() if isinstance(self.friend_list_cache, list) else self.friend_list_cache,
                "message": "success (cached)"
            }
        
        # 获取新数据
        response = await self.send_request("get_friend_list", {})
        
        # 缓存数据
        if response.get("status") == "ok" and response.get("retcode") == 0:
            self.friend_list_cache = response.get("data", [])
            self.friend_list_cache_time = current_time
            
            if self.verbose:
                print(f"[INFO] 好友列表已缓存（{len(self.friend_list_cache)}个好友）", file=sys.stderr)
        
        return response
    
    async def get_group_list(self) -> Dict[str, Any]:
        """
        获取群列表
        
        Returns:
            API响应，包含群列表数据
        """
        return await self.send_request("get_group_list", {})
    
    async def get_stranger_info(self, user_id: str, no_cache: bool = False) -> Dict[str, Any]:
        """
        获取陌生人信息
        
        Args:
            user_id: 要查询的QQ号
            no_cache: 是否不使用缓存
            
        Returns:
            API响应，包含陌生人信息
        """
        params = {
            "user_id": user_id,
            "no_cache": no_cache
        }
        return await self.send_request("get_stranger_info", params)
    
    async def search_friend_by_name(self, keyword: str, fuzzy: bool = True, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        通过昵称或备注搜索好友
        
        注意：此功能通过获取好友列表后在本地搜索实现，
        因为OneBot v11协议没有直接的昵称搜索API。
        
        Args:
            keyword: 搜索关键词
            fuzzy: 是否使用模糊搜索（包含匹配）
            force_refresh: 是否强制刷新缓存
            
        Returns:
            匹配的好友列表
        """
        # 获取好友列表（支持缓存）
        response = await self.get_friend_list(force_refresh=force_refresh)
        
        if response.get("status") != "ok" or response.get("retcode") != 0:
            raise RuntimeError(f"获取好友列表失败: {response.get('message', '未知错误')}")
        
        friends = response.get("data", [])
        results = []
        
        for friend in friends:
            nickname = friend.get("nickname", "")
            remark = friend.get("remark", "")
            user_id = friend.get("user_id")
            
            # 搜索逻辑
            if fuzzy:
                # 模糊搜索：包含关键词
                if (keyword in nickname) or (keyword in remark):
                    results.append(friend)
            else:
                # 精确匹配
                if keyword == nickname or keyword == remark:
                    results.append(friend)
        
        return results
    
    async def send_face_message(self, target_id: str, face_id: int, message_type: str = "private") -> Dict[str, Any]:
        """
        发送表情消息
        
        Args:
            target_id: 目标ID（QQ号或群号）
            face_id: 表情ID
            message_type: 消息类型，"private" 或 "group"
            
        Returns:
            API响应
        """
        # 构建表情消息段
        message = [
            {"type": "face", "data": {"id": str(face_id)}}
        ]
        
        if message_type == "private":
            return await self.send_private_message(target_id, message)
        else:  # group
            return await self.send_group_message(target_id, message)
    
    async def send_image_message(self, target_id: str, image_url: str, message_type: str = "private") -> Dict[str, Any]:
        """
        发送图片消息
        
        Args:
            target_id: 目标ID（QQ号或群号）
            image_url: 图片URL或文件路径（file://协议）
            message_type: 消息类型，"private" 或 "group"
            
        Returns:
            API响应
        """
        # 处理图片URL路径转换（Windows到WSL）
        processed_image_url = image_url
        
        # 检查是否为file://协议
        if image_url.startswith("file:///"):
            # 提取文件路径部分
            file_path = image_url[8:]  # 移除 "file:///"
            # 转换为WSL路径（如果Windows路径）
            wsl_path = self.win_path_to_wsl(file_path)
            processed_image_url = f"file:///{wsl_path}"
        elif image_url.startswith("file://"):
            # 处理可能缺少第三个斜杠的情况
            file_path = image_url[7:]  # 移除 "file://"
            wsl_path = self.win_path_to_wsl(file_path)
            processed_image_url = f"file:///{wsl_path}"
        else:
            # 检查是否为Windows绝对路径（包含盘符）
            import re
            windows_path_pattern = r'^[A-Za-z]:\\'
            if re.match(windows_path_pattern, image_url):
                # 是Windows路径，直接转换
                processed_image_url = f"file:///{self.win_path_to_wsl(image_url)}"
        
        # 构建图片消息段
        message = [
            {"type": "image", "data": {"file": processed_image_url}}
        ]
        
        if message_type == "private":
            return await self.send_private_message(target_id, message)
        else:  # group
            return await self.send_group_message(target_id, message)
    
    def _file_to_base64(self, file_path: str) -> str:
        """
        将文件转换为base64编码
        
        Args:
            file_path: 文件路径
            
        Returns:
            base64编码字符串（带base64://前缀）
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            base64_str = base64.b64encode(file_data).decode('utf-8')
            return f"base64://{base64_str}"
        except Exception as e:
            raise ValueError(f"读取文件失败: {e}")
    
    async def upload_private_file(self, user_id: str, file: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        上传私聊文件
        
        Args:
            user_id: 目标用户QQ号
            file: 文件路径或base64编码字符串
            name: 文件名（可选，默认使用原始文件名）
            
        Returns:
            API响应
        """
        params = {
            "user_id": user_id,
            "file": file,
            "name": name if name else os.path.basename(file) if not file.startswith("base64://") else "file"
        }
        return await self.send_request("upload_private_file", params, timeout=60)
    
    async def upload_group_file(self, group_id: str, file: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        上传群聊文件
        
        Args:
            group_id: 目标群号
            file: 文件路径或base64编码字符串
            name: 文件名（可选，默认使用原始文件名）
            
        Returns:
            API响应
        """
        params = {
            "group_id": group_id,
            "file": file,
            "name": name if name else os.path.basename(file) if not file.startswith("base64://") else "file"
        }
        return await self.send_request("upload_group_file", params, timeout=60)
    
    async def send_file_message(self, target_id: str, file_path: str, name: Optional[str] = None, 
                                message_type: str = "private", use_base64: bool = True) -> Dict[str, Any]:
        """
        发送文件消息（支持私聊和群聊）
        
        Args:
            target_id: 目标ID（QQ号或群号）
            file_path: 文件路径
            name: 文件名（可选，默认使用原始文件名）
            message_type: 消息类型，"private" 或 "group"
            use_base64: 是否使用base64编码上传（推荐True）
            
        Returns:
            API响应
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        if not name:
            name = os.path.basename(file_path)
        
        file_size = os.path.getsize(file_path)
        if self.verbose:
            print(f"文件: {name}, 大小: {file_size} 字节 ({file_size/1024:.2f} KB)", file=sys.stderr)
        
        if file_size > 50 * 1024 * 1024:  # 50MB限制
            print(f"警告: 文件大小 {file_size/1024/1024:.2f} MB，可能超过QQ文件大小限制", file=sys.stderr)
        
        if use_base64:
            # 使用base64编码上传
            if self.verbose:
                print("使用base64编码上传...", file=sys.stderr)
            base64_file = self._file_to_base64(file_path)
            file_param = base64_file
        else:
            # 使用file://协议
            if self.verbose:
                print("使用file://协议上传...", file=sys.stderr)
            abs_path = os.path.abspath(file_path)
            # 转换为WSL路径（如果Windows路径）
            wsl_path = self.win_path_to_wsl(abs_path)
            file_url = f"file:///{wsl_path.replace('\\', '/')}"
            file_param = file_url
        
        if message_type == "private":
            return await self.upload_private_file(target_id, file_param, name)
        else:  # group
            return await self.upload_group_file(target_id, file_param, name)
    
    async def close(self):
        """关闭连接"""
        self.is_connected = False
        self.is_connecting = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None
        
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
            self.websocket = None
        
        # 清理所有pending的future
        for echo, future in self.pending_responses.items():
            if not future.done():
                future.set_exception(ConnectionError("连接关闭"))
        self.pending_responses.clear()
        
        if self.verbose:
            print("[INFO] 连接已关闭", file=sys.stderr)
    
    def __del__(self):
        """析构函数，确保资源清理"""
        if self.websocket:
            try:
                asyncio.run(self.close())
            except:
                pass

# ========== 辅助函数 ==========

def parse_message(message_str: str) -> Union[str, List[Dict[str, Any]]]:
    """
    解析消息内容
    
    Args:
        message_str: 消息字符串，可以是纯文本或JSON
    
    Returns:
        解析后的消息内容
    """
    # 尝试解析为JSON
    try:
        message_data = json.loads(message_str)
        
        # 如果是列表，假设是消息段数组
        if isinstance(message_data, list):
            return message_data
        # 如果是字典，检查是否为消息段格式
        elif isinstance(message_data, dict):
            # 如果包含type和data字段，包装成列表
            if "type" in message_data and "data" in message_data:
                return [message_data]
            else:
                # 其他字典格式，作为文本处理
                return json.dumps(message_data, ensure_ascii=False)
        else:
            # 其他类型，转为字符串
            return str(message_data)
    except json.JSONDecodeError:
        # 不是JSON，作为纯文本处理
        return message_str

async def run_action_async(args):
    """异步执行动作"""
    client = None
    try:
        # 创建客户端
        client = NapcatWebSocketClient(server=args.server, token=args.token)
        client.verbose = args.verbose
        
        # 连接
        if args.verbose:
            print(f"连接到服务器: {args.server}")
        
        await client.connect()
        
        if args.verbose:
            print("连接成功")
        
        result = None
        
        # 根据action执行不同操作
        if args.action == "send":
            # 发送消息（兼容原功能）
            message = parse_message(args.message)
            
            if args.type == "private":
                result = await client.send_private_message(args.target, message, args.auto_escape)
            else:  # group
                result = await client.send_group_message(args.target, message, args.auto_escape)
                
            # 检查结果
            if result.get("status") == "ok" or result.get("retcode") == 0:
                result["success"] = True
            else:
                result["success"] = False
                result["error"] = result.get("message", "未知错误")
                
        elif args.action == "get-friends":
            # 获取好友列表
            result = await client.get_friend_list(force_refresh=args.force_refresh)
            
            if result.get("status") == "ok" or result.get("retcode") == 0:
                result["success"] = True
                friends = result.get("data", [])
                result["friends_count"] = len(friends)
                result["cached"] = "message" in result and "cached" in result.get("message", "")
            else:
                result["success"] = False
                result["error"] = result.get("message", "未知错误")
                
        elif args.action == "get-groups":
            # 获取群列表
            result = await client.get_group_list()
            
            if result.get("status") == "ok" or result.get("retcode") == 0:
                result["success"] = True
                groups = result.get("data", [])
                result["groups_count"] = len(groups)
            else:
                result["success"] = False
                result["error"] = result.get("message", "未知错误")
                
        elif args.action == "search-friend":
            # 搜索好友
            if not args.name:
                raise ValueError("搜索好友需要 --name 参数")
                
            friends = await client.search_friend_by_name(args.name, fuzzy=not args.exact, force_refresh=args.force_refresh)
            result = {
                "success": True,
                "data": friends,
                "count": len(friends),
                "keyword": args.name
            }
            
        elif args.action == "send-face":
            # 发送表情
            if not args.face_id:
                raise ValueError("发送表情需要 --face-id 参数")
            
            # 如果没有指定消息类型，默认为私聊
            message_type = args.type if args.type else "private"
                
            result = await client.send_face_message(args.target, args.face_id, message_type)
            
            if result.get("status") == "ok" or result.get("retcode") == 0:
                result["success"] = True
            else:
                result["success"] = False
                result["error"] = result.get("message", "未知错误")
                
        elif args.action == "send-image":
            # 发送图片
            if not args.image_url:
                raise ValueError("发送图片需要 --image-url 参数")
            
            # 如果没有指定消息类型，默认为私聊
            message_type = args.type if args.type else "private"
                
            result = await client.send_image_message(args.target, args.image_url, message_type)
            
            if result.get("status") == "ok" or result.get("retcode") == 0:
                result["success"] = True
            else:
                result["success"] = False
                result["error"] = result.get("message", "未知错误")
                
        elif args.action == "send-file":
            # 发送文件
            if not args.file:
                raise ValueError("发送文件需要 --file 参数")
            
            # 如果没有指定消息类型，默认为私聊
            message_type = args.type if args.type else "private"
                
            result = await client.send_file_message(
                target_id=args.target,
                file_path=args.file,
                name=args.file_name,
                message_type=message_type,
                use_base64=not args.no_base64
            )
            
            if result.get("status") == "ok" or result.get("retcode") == 0:
                result["success"] = True
            else:
                result["success"] = False
                result["error"] = result.get("message", "未知错误")
                
        elif args.action == "send-batch":
            # 批量发送消息
            if not args.targets:
                raise ValueError("批量发送需要 --targets 参数")
            if not args.message:
                raise ValueError("批量发送需要 --message 参数")
            if not args.type:
                raise ValueError("批量发送需要 --type 参数")
            
            # 解析目标列表
            target_list = [t.strip() for t in args.targets.split(",") if t.strip()]
            if not target_list:
                raise ValueError("目标列表为空")
            
            message = parse_message(args.message)
            results = []
            success_count = 0
            fail_count = 0
            
            for i, target in enumerate(target_list):
                try:
                    if args.verbose:
                        print(f"[INFO] 发送消息给目标 {i+1}/{len(target_list)}: {target}")
                    
                    if args.type == "private":
                        result = await client.send_private_message(target, message, args.auto_escape)
                    else:  # group
                        result = await client.send_group_message(target, message, args.auto_escape)
                    
                    # 检查结果
                    if result.get("status") == "ok" or result.get("retcode") == 0:
                        success_count += 1
                        results.append({
                            "target": target,
                            "success": True,
                            "message_id": result.get("data", {}).get("message_id"),
                            "response": result.get("message", "success")
                        })
                    else:
                        fail_count += 1
                        results.append({
                            "target": target,
                            "success": False,
                            "error": result.get("message", "未知错误"),
                            "response": result
                        })
                        
                        if args.stop_on_error:
                            raise RuntimeError(f"批量发送在目标 {target} 处失败: {result.get('message', '未知错误')}")
                
                except Exception as e:
                    fail_count += 1
                    results.append({
                        "target": target,
                        "success": False,
                        "error": str(e)
                    })
                    
                    if args.stop_on_error:
                        raise
            
                # 添加延迟（最后一条消息后不需要延迟）
                if i < len(target_list) - 1 and args.delay > 0:
                    await asyncio.sleep(args.delay)
            
            # 汇总结果
            result = {
                "success": success_count == len(target_list),
                "total": len(target_list),
                "success_count": success_count,
                "fail_count": fail_count,
                "results": results,
                "message": f"批量发送完成：成功 {success_count}/{len(target_list)}，失败 {fail_count}/{len(target_list)}"
            }
                
        elif args.action == "get-stranger":
            # 获取陌生人信息
            if not args.user_id:
                raise ValueError("获取陌生人信息需要 --user-id 参数")
                
            result = await client.get_stranger_info(args.user_id, args.no_cache)
            
            if result.get("status") == "ok" or result.get("retcode") == 0:
                result["success"] = True
            else:
                result["success"] = False
                result["error"] = result.get("message", "未知错误")
                
        else:
            raise ValueError(f"未知的action: {args.action}")
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "action": args.action if args else "unknown"
        }
    finally:
        # 关闭连接
        if client:
            await client.close()

def run_action(args):
    """同步执行动作（包装异步函数）"""
    return asyncio.run(run_action_async(args))

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="QQ工具脚本（WebSocket版本）- 扩展的QQ机器人功能",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # 基本参数
    parser.add_argument(
        "--server", "-s",
        type=str,
        default=DEFAULT_SERVER,
        help=f"napcat服务器地址（默认: {DEFAULT_SERVER}）"
    )
    
    parser.add_argument(
        "--token", "-k",
        type=str,
        default=DEFAULT_TOKEN,
        help="认证令牌（可在config.json中配置默认值）"
    )
    
    parser.add_argument(
        "--timeout", "-o",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"超时时间（秒）（默认: {DEFAULT_TIMEOUT}）"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="详细输出模式"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        default=False,
        help="静默模式，只输出错误"
    )
    
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        default=False,
        help="JSON格式输出"
    )
    
    # 动作选择
    parser.add_argument(
        "--action", "-a",
        type=str,
        default="send",
        choices=["send", "get-friends", "search-friend", "send-face", "send-image", "get-stranger", "send-batch", "get-groups", "send-file"],
        help="执行的动作（默认: send）"
    )
    
    # 发送消息相关参数（action=send时使用）
    parser.add_argument(
        "--type", "-t",
        type=str,
        choices=["private", "group"],
        help="消息类型: private(私聊) 或 group(群聊)，action=send时使用"
    )
    
    parser.add_argument(
        "--target", "-T",
        type=str,
        help="目标ID: QQ号(私聊) 或 群号(群聊)，多个action使用"
    )
    
    parser.add_argument(
        "--message", "-m",
        type=str,
        help="消息内容。可以是纯文本，或OneBot消息段数组的JSON字符串，action=send时使用"
    )
    
    parser.add_argument(
        "--auto-escape", "-e",
        action="store_true",
        default=False,
        help="是否自动转义CQ码（默认: False），action=send时使用"
    )
    
    # 批量发送相关参数（action=send-batch时使用）
    parser.add_argument(
        "--targets",
        type=str,
        help="批量发送的目标ID列表，用逗号分隔，action=send-batch时使用"
    )
    
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="批量发送时每条消息之间的延迟（秒，默认: 0.5），action=send-batch时使用"
    )
    
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        default=False,
        help="批量发送时遇到错误是否停止（默认: 继续），action=send-batch时使用"
    )
    
    # 搜索好友相关参数（action=search-friend时使用）
    parser.add_argument(
        "--name", "-n",
        type=str,
        help="搜索关键词（昵称或备注），action=search-friend时使用"
    )
    
    parser.add_argument(
        "--exact",
        action="store_true",
        default=False,
        help="精确匹配（默认模糊匹配），action=search-friend时使用"
    )
    
    # 缓存控制参数（action=get-friends或search-friend时使用）
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        default=False,
        help="强制刷新缓存（忽略缓存，重新从API获取），action=get-friends或search-friend时使用"
    )
    
    # 发送表情相关参数（action=send-face时使用）
    parser.add_argument(
        "--face-id", "-f",
        type=int,
        help="表情ID，action=send-face时使用"
    )
    
    # 发送图片相关参数（action=send-image时使用）
    parser.add_argument(
        "--image-url", "-i",
        type=str,
        help="图片URL或文件路径（file://协议），action=send-image时使用"
    )
    
    # 发送文件相关参数（action=send-file时使用）
    parser.add_argument(
        "--file", "-F",
        type=str,
        help="文件路径，action=send-file时使用"
    )
    parser.add_argument(
        "--file-name",
        type=str,
        help="自定义文件名（可选），action=send-file时使用"
    )
    parser.add_argument(
        "--no-base64",
        action="store_true",
        default=False,
        help="不使用base64编码上传（使用file://协议，不推荐），action=send-file时使用"
    )
    
    # 获取陌生人信息参数（action=get-stranger时使用）
    parser.add_argument(
        "--user-id", "-u",
        type=str,
        help="要查询的QQ号，action=get-stranger时使用"
    )
    
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="不使用缓存，action=get-stranger时使用"
    )
    
    # 输出格式参数
    parser.add_argument(
        "--output-format",
        type=str,
        default="text",
        choices=["text", "json", "table"],
        help="输出格式（默认: text）"
    )
    
    return parser.parse_args()

def format_output(result, args):
    """格式化输出"""
    if args.json or args.output_format == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    # 文本输出
    output_lines = []
    
    if not result.get("success"):
        output_lines.append(f"错误: {result.get('error', '未知错误')}")
        return "\n".join(output_lines)
    
    # 根据不同action格式化输出
    action = args.action
    
    if action == "send":
        output_lines.append("[OK] 消息发送成功")
        if "data" in result and "message_id" in result["data"]:
            output_lines.append(f"  消息ID: {result['data']['message_id']}")
            
    elif action == "get-friends":
        friends = result.get("data", [])
        count = result.get("friends_count", len(friends))
        cached = result.get("cached", False)
        cache_status = " (缓存)" if cached else ""
        output_lines.append(f"[OK] 获取好友列表成功{cache_status}，共 {count} 个好友")
        
        if args.output_format == "table" and friends:
            # 简单表格输出
            output_lines.append("\n好友列表:")
            output_lines.append("  QQ号        昵称             备注")
            output_lines.append("  " + "-" * 40)
            for friend in friends[:20]:  # 限制显示前20个
                user_id = str(friend.get("user_id", ""))
                nickname = friend.get("nickname", "")[:10]
                remark = friend.get("remark", "")[:10]
                output_lines.append(f"  {user_id:12s} {nickname:15s} {remark:15s}")
            if count > 20:
                output_lines.append(f"  ... 还有 {count - 20} 个好友未显示")
        elif friends:
            # 简单列表输出
            for i, friend in enumerate(friends[:10], 1):
                user_id = friend.get("user_id")
                nickname = friend.get("nickname", "未知")
                remark = friend.get("remark", "")
                remark_text = f" (备注: {remark})" if remark else ""
                output_lines.append(f"  {i}. {user_id} - {nickname}{remark_text}")
            if count > 10:
                output_lines.append(f"  ... 还有 {count - 10} 个好友未显示")
                
    elif action == "get-groups":
        groups = result.get("data", [])
        count = result.get("groups_count", len(groups))
        output_lines.append(f"[OK] 获取群列表成功，共 {count} 个群")
        
        if args.output_format == "table" and groups:
            # 简单表格输出
            output_lines.append("\n群列表:")
            output_lines.append("  群号        群名")
            output_lines.append("  " + "-" * 30)
            for group in groups[:20]:  # 限制显示前20个
                group_id = str(group.get("group_id", ""))
                group_name = group.get("group_name", "")[:20]
                output_lines.append(f"  {group_id:12s} {group_name}")
            if count > 20:
                output_lines.append(f"  ... 还有 {count - 20} 个群未显示")
        elif groups:
            # 简单列表输出
            for i, group in enumerate(groups[:10], 1):
                group_id = group.get("group_id")
                group_name = group.get("group_name", "未知")
                output_lines.append(f"  {i}. {group_id} - {group_name}")
            if count > 10:
                output_lines.append(f"  ... 还有 {count - 10} 个群未显示")
                
    elif action == "search-friend":
        friends = result.get("data", [])
        count = result.get("count", 0)
        keyword = result.get("keyword", "")
        output_lines.append(f"[OK] 搜索好友成功，找到 {count} 个匹配 '{keyword}' 的好友")
        
        if friends:
            for i, friend in enumerate(friends, 1):
                user_id = friend.get("user_id")
                nickname = friend.get("nickname", "未知")
                remark = friend.get("remark", "")
                remark_text = f" (备注: {remark})" if remark else ""
                output_lines.append(f"  {i}. {user_id} - {nickname}{remark_text}")
                
    elif action == "send-face":
        output_lines.append("[OK] 表情发送成功")
        if "data" in result and "message_id" in result["data"]:
            output_lines.append(f"  消息ID: {result['data']['message_id']}")
            
    elif action == "send-image":
        output_lines.append("[OK] 图片发送成功")
        if "data" in result and "message_id" in result["data"]:
            output_lines.append(f"  消息ID: {result['data']['message_id']}")
            
    elif action == "send-file":
        output_lines.append("[OK] 文件发送成功")
        if "data" in result and "file_id" in result["data"]:
            output_lines.append(f"  文件ID: {result['data']['file_id']}")
        elif "data" in result and "message_id" in result["data"]:
            output_lines.append(f"  消息ID: {result['data']['message_id']}")
            
    elif action == "send-batch":
        total = result.get("total", 0)
        success_count = result.get("success_count", 0)
        fail_count = result.get("fail_count", 0)
        results = result.get("results", [])
        
        if result.get("success"):
            output_lines.append(f"[OK] 批量发送成功，全部 {total} 条消息发送成功")
        else:
            output_lines.append(f"[OK] 批量发送完成，成功 {success_count}/{total}，失败 {fail_count}/{total}")
        
        # 显示失败详情（如果有）
        if fail_count > 0:
            output_lines.append("\n失败详情:")
            for i, item in enumerate(results):
                if not item.get("success"):
                    target = item.get("target", "未知")
                    error = item.get("error", "未知错误")
                    output_lines.append(f"  {i+1}. 目标 {target}: {error}")
        
        # 显示成功统计
        if success_count > 0 and args.verbose:
            output_lines.append(f"\n成功发送给 {success_count} 个目标")
            
    elif action == "get-stranger":
        stranger_info = result.get("data", {})
        output_lines.append("[OK] 获取陌生人信息成功")
        if stranger_info:
            user_id = stranger_info.get("user_id", "未知")
            nickname = stranger_info.get("nickname", "未知")
            sex = stranger_info.get("sex", "未知")
            age = stranger_info.get("age", "未知")
            output_lines.append(f"  QQ号: {user_id}")
            output_lines.append(f"  昵称: {nickname}")
            output_lines.append(f"  性别: {sex}")
            output_lines.append(f"  年龄: {age}")
    
    return "\n".join(output_lines)

def main():
    """主函数"""
    args = parse_arguments()
    
    # 验证token
    if not args.token:
        print("错误: 未提供认证令牌(token)。请通过 --token 参数提供，或在配置文件中设置默认值。", file=sys.stderr)
        print(f"配置文件位置: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)
    
    # 参数验证
    if args.action == "send":
        if not args.type:
            print("错误: action=send 时需要 --type 参数", file=sys.stderr)
            sys.exit(1)
        if not args.target:
            print("错误: 需要 --target 参数", file=sys.stderr)
            sys.exit(1)
        if not args.message:
            print("错误: action=send 时需要 --message 参数", file=sys.stderr)
            sys.exit(1)
    
    elif args.action == "send-batch":
        if not args.type:
            print("错误: action=send-batch 时需要 --type 参数", file=sys.stderr)
            sys.exit(1)
        if not args.targets:
            print("错误: action=send-batch 时需要 --targets 参数", file=sys.stderr)
            sys.exit(1)
        if not args.message:
            print("错误: action=send-batch 时需要 --message 参数", file=sys.stderr)
            sys.exit(1)
    
    elif args.action == "send-file":
        if not args.type:
            print("错误: action=send-file 时需要 --type 参数", file=sys.stderr)
            sys.exit(1)
        if not args.target:
            print("错误: action=send-file 时需要 --target 参数", file=sys.stderr)
            sys.exit(1)
        if not args.file:
            print("错误: action=send-file 时需要 --file 参数", file=sys.stderr)
            sys.exit(1)
    
    # 执行动作
    result = run_action(args)
    
    # 输出结果
    if args.json or args.output_format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        output = format_output(result, args)
        if not args.quiet or not result.get("success"):
            print(output)
    
    # 返回退出码
    return 0 if result.get("success") else 1

if __name__ == "__main__":
    sys.exit(main())