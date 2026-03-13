#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QQ消息发送脚本（WebSocket版本）- 通过napcat WebSocket API发送私聊和群聊消息

用法:
    python send_qq_message_ws.py --type private --target 123456 --message "你好"
    python send_qq_message_ws.py --type group --target 123456789 --message '[{"type":"text","data":{"text":"群消息"}}]'

支持的参数:
    --type, -t       消息类型 (private/group)
    --target, -T     目标ID (QQ号或群号)
    --message, -m    消息内容 (文本或JSON字符串)
    --auto-escape, -a 自动转义CQ码 (默认: False)
    --server, -s     napcat服务器地址 (默认: ws://localhost:3002)
    --token, -k      认证令牌 (默认: CqC5dDMXWGUu6NVh)
    --timeout, -o    超时时间（秒） (默认: 30)
    --verbose, -v    详细输出
    --quiet, -q      静默模式
    --json, -j       JSON格式输出
"""

import argparse
import asyncio
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
    """Napcat WebSocket客户端"""
    
    def __init__(self, server: str = DEFAULT_SERVER, token: Optional[str] = DEFAULT_TOKEN):
        """
        初始化客户端
        
        Args:
            server: WebSocket服务器地址
            token: 认证令牌
        """
        self.server = server
        self.token = token
        self.websocket = None
        self.pending_responses = {}  # echo -> future
        self._receive_task = None
        self.verbose = False  # 详细输出标志
        
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
            
            # 等待连接成功事件（可选）
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
                # 将消息转换为字符串（websockets可能返回bytes或str）
                if isinstance(message_raw, bytes):
                    message = message_raw.decode('utf-8')
                else:
                    message = str(message_raw)
                await self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            pass  # 连接关闭是正常的
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
    
    async def send_request(self, action: str, params: Dict[str, Any], timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """
        发送API请求并等待响应
        
        Args:
            action: API动作名称
            params: 参数
            timeout: 超时时间（秒）
            
        Returns:
            API响应
        """
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
        
        try:
            # 发送请求
            await self.websocket.send(json.dumps(request))
            
            # 等待响应
            response = await asyncio.wait_for(future, timeout=timeout)
            
            # 清理
            if echo in self.pending_responses:
                del self.pending_responses[echo]
                
            return response
            
        except asyncio.TimeoutError:
            # 清理
            if echo in self.pending_responses:
                del self.pending_responses[echo]
            raise TimeoutError(f"等待响应超时 ({timeout}秒)")
    
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
            self.websocket = None
        
        # 清理所有pending的future
        for echo, future in self.pending_responses.items():
            if not future.done():
                future.set_exception(ConnectionError("连接关闭"))
        self.pending_responses.clear()
    
    def __del__(self):
        """析构函数，确保资源清理"""
        if self.websocket:
            try:
                asyncio.run(self.close())
            except:
                pass

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
        # 处理常见的转义序列：\n, \t, \r
        message_str = message_str.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
        return message_str

async def send_qq_message_async(
    message_type: str,
    target_id: str,
    message: Union[str, List[Dict[str, Any]]],
    auto_escape: bool = False,
    server: str = DEFAULT_SERVER,
    token: Optional[str] = DEFAULT_TOKEN,
    timeout: float = DEFAULT_TIMEOUT,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    异步发送QQ消息
    
    Args:
        message_type: "private" 或 "group"
        target_id: 目标ID（QQ号或群号）
        message: 消息内容（字符串或消息段列表）
        auto_escape: 是否自动转义CQ码
        server: napcat服务器地址
        token: 认证令牌
        timeout: 超时时间（秒）
        verbose: 详细输出
        
    Returns:
        API响应字典
    """
    client = None
    try:
        # 创建客户端
        client = NapcatWebSocketClient(server=server, token=token)
        client.verbose = verbose
        
        # 连接
        if verbose:
            print(f"连接到服务器: {server}")
        
        await client.connect()
        
        if verbose:
            print("连接成功")
        
        # 发送消息
        if message_type == "private":
            if verbose:
                print(f"发送私聊消息给用户 {target_id}")
            result = await client.send_private_message(target_id, message, auto_escape)
        else:  # group
            if verbose:
                print(f"发送群聊消息到群 {target_id}")
            result = await client.send_group_message(target_id, message, auto_escape)
        
        # 检查结果
        if result.get("status") == "ok" or result.get("retcode") == 0:
            result["success"] = True
        else:
            result["success"] = False
            result["error"] = result.get("message", "未知错误")
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "status_code": 0
        }
    finally:
        # 关闭连接
        if client:
            await client.close()

def send_qq_message(
    message_type: str,
    target_id: str,
    message: Union[str, List[Dict[str, Any]]],
    auto_escape: bool = False,
    server: str = DEFAULT_SERVER,
    token: Optional[str] = DEFAULT_TOKEN,
    timeout: float = DEFAULT_TIMEOUT,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    同步发送QQ消息（包装异步函数）
    
    Args:
        message_type: "private" 或 "group"
        target_id: 目标ID（QQ号或群号）
        message: 消息内容（字符串或消息段列表）
        auto_escape: 是否自动转义CQ码
        server: napcat服务器地址
        token: 认证令牌
        timeout: 超时时间（秒）
        verbose: 详细输出
        
    Returns:
        API响应字典
    """
    return asyncio.run(
        send_qq_message_async(
            message_type=message_type,
            target_id=target_id,
            message=message,
            auto_escape=auto_escape,
            server=server,
            token=token,
            timeout=timeout,
            verbose=verbose
        )
    )

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="通过napcat WebSocket API发送QQ消息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--type", "-t",
        type=str,
        required=True,
        choices=["private", "group"],
        help="消息类型: private(私聊) 或 group(群聊)"
    )
    
    parser.add_argument(
        "--target", "-T",
        type=str,
        required=True,
        help="目标ID: QQ号(私聊) 或 群号(群聊)"
    )
    
    parser.add_argument(
        "--message", "-m",
        type=str,
        required=True,
        help="消息内容。可以是纯文本，或OneBot消息段数组的JSON字符串"
    )
    
    parser.add_argument(
        "--auto-escape", "-a",
        action="store_true",
        default=False,
        help="是否自动转义CQ码（默认: False）"
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
    
    # 解析消息
    try:
        message = parse_message(args.message)
    except Exception as e:
        if not args.quiet:
            print(f"错误: 无法解析消息内容 - {str(e)}", file=sys.stderr)
        sys.exit(1)
    
    # 发送消息
    result = send_qq_message(
        message_type=args.type,
        target_id=args.target,
        message=message,
        auto_escape=args.auto_escape,
        server=args.server,
        token=args.token,
        timeout=args.timeout,
        verbose=args.verbose
    )
    
    # 输出结果
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if args.verbose:
            print("请求详情:")
            print(f"  消息类型: {args.type}")
            print(f"  目标ID: {args.target}")
            print(f"  服务器: {args.server}")
            print(f"  消息内容: {message if isinstance(message, str) else '消息段数组'}")
            print()
        
        if result.get("success"):
            if not args.quiet:
                print("消息发送成功")
                if "data" in result and "message_id" in result["data"]:
                    print(f"  消息ID: {result['data']['message_id']}")
                if args.verbose:
                    print(f"  响应: {result}")
        else:
            if not args.quiet:
                print("消息发送失败", file=sys.stderr)
                print(f"  错误: {result.get('error', '未知错误')}", file=sys.stderr)
                if "message" in result:
                    print(f"  错误信息: {result['message']}", file=sys.stderr)
            sys.exit(1)
    
    return 0 if result.get("success") else 1

if __name__ == "__main__":
    sys.exit(main())