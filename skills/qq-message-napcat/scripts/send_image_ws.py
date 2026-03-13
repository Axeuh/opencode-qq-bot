#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片消息发送脚本（WebSocket版本）- 通过napcat WebSocket API发送图片消息，支持base64编码

用法:
    python send_image_ws.py --type group --target 813729523 --image-file "screenshot.png"
    python send_image_ws.py --type private --target 2176284372 --image-file "photo.jpg" --base64

支持的图片格式：JPEG, PNG, GIF等QQ支持的格式

注意：直接发送图片需要NapCat能访问文件路径，否则需要使用--base64参数
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import websockets
from typing import Dict, Any, Union, List, Optional

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
    """Napcat WebSocket客户端"""
    
    def __init__(self, server: str = DEFAULT_SERVER, token: Optional[str] = DEFAULT_TOKEN, verbose: bool = False):
        self.server = server
        self.token = token
        self.verbose = verbose
        self.websocket = None
        self.pending_responses = {}  # echo -> future
        self._receive_task = None
        
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
        """连接到WebSocket服务器"""
        ws_url = self.build_ws_url()
        
        try:
            self.websocket = await asyncio.wait_for(
                websockets.connect(ws_url),
                timeout=10
            )
            
            # 启动接收任务
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # 等待连接成功事件
            await asyncio.sleep(0.5)
            
            return True
            
        except Exception as e:
            raise ConnectionError(f"连接失败: {e}")
    
    async def _receive_loop(self):
        """接收消息循环"""
        if not self.websocket:
            return
            
        try:
            async for message_raw in self.websocket:
                if isinstance(message_raw, bytes):
                    message = message_raw.decode('utf-8')
                else:
                    message = str(message_raw)
                await self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"接收循环错误: {e}", file=sys.stderr)
    
    async def _handle_message(self, message: str):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            echo = data.get("echo")
            
            if echo and echo in self.pending_responses:
                future = self.pending_responses.pop(echo)
                future.set_result(data)
                
        except json.JSONDecodeError:
            pass  # 忽略非JSON消息（如事件消息）
        except Exception as e:
            print(f"处理消息错误: {e}", file=sys.stderr)
    
    async def send_request(self, action: str, params: Dict[str, Any], timeout: float = 30) -> Dict[str, Any]:
        """发送API请求并等待响应"""
        if not self.websocket:
            raise ConnectionError("未连接到WebSocket服务器")
        
        # 生成唯一echo
        import uuid
        echo = str(uuid.uuid4())
        
        request = {
            "action": action,
            "params": params,
            "echo": echo
        }
        
        # 创建Future
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self.pending_responses[echo] = future
        
        # 发送请求
        await self.websocket.send(json.dumps(request, ensure_ascii=False))
        
        # 等待响应
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            del self.pending_responses[echo]
            raise TimeoutError(f"等待响应超时 ({timeout}秒)")
    
    async def send_private_message(self, user_id: str, message: Union[str, List[Dict[str, Any]]], auto_escape: bool = False) -> Dict[str, Any]:
        """发送私聊消息"""
        params = {
            "user_id": user_id,
            "message": message,
            "auto_escape": auto_escape
        }
        
        return await self.send_request("send_private_msg", params)
    
    async def send_group_message(self, group_id: str, message: Union[str, List[Dict[str, Any]]], auto_escape: bool = False) -> Dict[str, Any]:
        """发送群聊消息"""
        params = {
            "group_id": group_id,
            "message": message,
            "auto_escape": auto_escape
        }
        
        return await self.send_request("send_group_msg", params)
    
    async def send_image_message(self, target_id: str, image_file: str, message_type: str = "group", use_base64: bool = False) -> Dict[str, Any]:
        """
        发送图片消息
        
        Args:
            target_id: 目标ID（QQ号或群号）
            image_file: 图片文件路径
            message_type: "private" 或 "group"
            use_base64: 是否使用base64编码（解决路径访问问题）
        """
        if not os.path.exists(image_file):
            raise FileNotFoundError(f"图片文件不存在: {image_file}")
        
        file_size = os.path.getsize(image_file)
        if self.verbose:
            print(f"图片文件: {image_file}, 大小: {file_size} 字节 ({file_size/1024:.2f} KB)", file=sys.stderr)
        
        if use_base64:
            # 使用base64编码
            with open(image_file, 'rb') as f:
                image_data = f.read()
            b64_str = base64.b64encode(image_data).decode('utf-8')
            file_param = f"base64://{b64_str}"
            
            if self.verbose:
                print(f"使用base64编码，长度: {len(b64_str)} 字符", file=sys.stderr)
        else:
            # 使用文件路径（需要NapCat能访问）
            abs_path = os.path.abspath(image_file)
            # 转换为WSL路径（如果Windows路径）
            wsl_path = NapcatWebSocketClient.win_path_to_wsl(abs_path)
            file_param = f"file:///{wsl_path.replace('\\', '/')}"
        
        # 构建图片消息段
        message = [
            {"type": "image", "data": {"file": file_param}}
        ]
        
        if message_type == "private":
            return await self.send_private_message(target_id, message)
        else:  # group
            return await self.send_group_message(target_id, message)
    
    async def close(self):
        """关闭连接"""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket:
            await self.websocket.close()

async def send_image_async(
    message_type: str,
    target_id: str,
    image_file: str,
    use_base64: bool = False,
    server: str = DEFAULT_SERVER,
    token: Optional[str] = DEFAULT_TOKEN,
    timeout: float = DEFAULT_TIMEOUT,
    verbose: bool = False
) -> Dict[str, Any]:
    """异步发送图片消息"""
    client = NapcatWebSocketClient(server, token, verbose)
    
    try:
        # 连接
        if verbose:
            print(f"正在连接到 {server}...", file=sys.stderr)
        await client.connect()
        
        if verbose:
            print(f"连接成功，正在发送图片...", file=sys.stderr)
        
        # 发送图片消息
        result = await client.send_image_message(
            target_id=target_id,
            image_file=image_file,
            message_type=message_type,
            use_base64=use_base64
        )
        
        return result
        
    finally:
        await client.close()

def send_image(
    message_type: str,
    target_id: str,
    image_file: str,
    use_base64: bool = False,
    server: str = DEFAULT_SERVER,
    token: Optional[str] = DEFAULT_TOKEN,
    timeout: float = DEFAULT_TIMEOUT,
    verbose: bool = False,
    quiet: bool = False
) -> Dict[str, Any]:
    """发送图片消息（同步封装）"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(send_image_async(
            message_type=message_type,
            target_id=target_id,
            image_file=image_file,
            use_base64=use_base64,
            server=server,
            token=token,
            timeout=timeout,
            verbose=verbose
        ))
        
        return result
        
    except Exception as e:
        if not quiet:
            print(f"发送图片失败: {e}", file=sys.stderr)
        raise

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="通过napcat WebSocket API发送图片消息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
    python send_image_ws.py --type group --target 813729523 --image-file screenshot.png
    python send_image_ws.py --type private --target 2176284372 --image-file photo.jpg --base64
    python send_image_ws.py --type group --target 813729523 --image-file image.png --base64 --verbose
    
注意：
    1. 不使用--base64参数时，NapCat需要能访问图片文件路径
    2. 使用--base64参数时，图片数据直接编码在请求中，无路径访问问题
    3. 图片大小建议不超过5MB，避免QQ限制
        """
    )
    
    parser.add_argument(
        "--type", "-t",
        type=str,
        required=True,
        choices=["private", "group"],
        help="消息类型 (private/group)"
    )
    
    parser.add_argument(
        "--target", "-T",
        type=str,
        required=True,
        help="目标ID (QQ号或群号)"
    )
    
    parser.add_argument(
        "--image-file", "-i",
        type=str,
        required=True,
        help="图片文件路径"
    )
    
    parser.add_argument(
        "--base64", "-b",
        action="store_true",
        default=False,
        help="使用base64编码发送（解决路径访问问题）"
    )
    
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
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_arguments()
    
    # 验证token
    if not args.token:
        print("错误: 未提供认证令牌(token)。请通过 --token 参数提供，或在配置文件中设置默认值。", file=sys.stderr)
        print(f"配置文件位置: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)
    
    # 检查图片文件
    if not os.path.exists(args.image_file):
        if not args.quiet:
            print(f"错误: 图片文件不存在: {args.image_file}", file=sys.stderr)
        sys.exit(1)
    
    # 发送图片
    try:
        result = send_image(
            message_type=args.type,
            target_id=args.target,
            image_file=args.image_file,
            use_base64=args.base64,
            server=args.server,
            token=args.token,
            timeout=args.timeout,
            verbose=args.verbose,
            quiet=args.quiet
        )
        
        # 输出结果
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result.get("status") == "ok" or result.get("retcode") == 0:
                print(f"图片发送成功")
                if "data" in result and "message_id" in result["data"]:
                    print(f"消息ID: {result['data']['message_id']}")
            else:
                print(f"图片发送失败: {result.get('message', '未知错误')}")
                sys.exit(1)
                
    except Exception as e:
        if not args.quiet:
            print(f"发送图片失败: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()