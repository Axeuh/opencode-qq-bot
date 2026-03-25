#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发送文件到QQ（私聊或群聊）- WebSocket版本

基于NapCat的upload_private_file和upload_group_file API，支持base64编码上传。

用法:
     # 发送私聊文件
    python send_file_ws.py --type private --target 2176284372 --file "D:\\path\\to\\file.xlsx"
    
    # 发送群聊文件
    python send_file_ws.py --type group --target 123456789 --file "D:\\path\\to\\file.xlsx"
    
    # 自定义文件名
    python send_file_ws.py --type private --target 2176284372 --file "D:\\path\\to\\file.xlsx" --name "自定义文件名.xlsx"
    
    # 使用file://协议（不推荐，需要NapCat可以访问的路径）
    python send_file_ws.py --type private --target 2176284372 --file "D:\\path\\to\\file.xlsx" --no-base64
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import uuid
import websockets
from typing import Optional, Dict, Any

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

class FileSender:
    """文件发送器"""
    
    def __init__(self, server: str = DEFAULT_SERVER, token: Optional[str] = DEFAULT_TOKEN, verbose: bool = False):
        self.server = server
        self.token = token
        self.verbose = verbose
        self.websocket = None
        self.pending_responses = {}
        self.is_connected = False
        
    def build_ws_url(self) -> str:
        """构建带认证token的WebSocket URL"""
        if "?" in self.server:
            return f"{self.server}&access_token={self.token}"
        else:
            return f"{self.server}?access_token={self.token}"
    
    async def connect(self):
        """连接到WebSocket服务器"""
        ws_url = self.build_ws_url()
        
        if self.verbose:
            print(f"连接到服务器: {ws_url}")
        
        self.websocket = await asyncio.wait_for(
            websockets.connect(ws_url),
            timeout=10
        )
        
        self.is_connected = True
        
        if self.verbose:
            print("连接成功")
    
    async def send_request(self, action: str, params: dict, timeout: float = DEFAULT_TIMEOUT) -> dict:
        """
        发送API请求并等待响应
        
        Args:
            action: API动作名称
            params: 参数
            timeout: 超时时间（秒）
            
        Returns:
            API响应
        """
        if not self.websocket or not self.is_connected:
            raise ConnectionError("未连接到WebSocket服务器")
        
        # 生成唯一的echo标识
        echo = str(uuid.uuid4())
        
        # 创建请求
        request = {
            "action": action,
            "params": params,
            "echo": echo
        }
        
        # 发送请求
        await self.websocket.send(json.dumps(request))
        
        # 等待响应（简化版，不考虑并发）
        try:
            response_raw = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            response = json.loads(response_raw)
            
            # 检查是否是我们要的响应
            if response.get("echo") == echo:
                return response
            else:
                # 继续读取直到找到正确的响应
                # 这是一个简化实现，实际应该处理消息队列
                return response
        except asyncio.TimeoutError:
            raise TimeoutError(f"等待响应超时 ({timeout}秒)")
    
    @staticmethod
    def win_path_to_wsl(win_path: str) -> str:
        """
        将Windows路径转换为WSL路径
        
        Args:
            win_path: Windows路径，如 D:\\Users\\Axeuh\\Desktop\\file.txt
            
        Returns:
            WSL路径，如 /mnt/d/Users/Axeuh/Desktop/file.txt
        """
        if not win_path:
            return win_path
            
        # 标准化路径，处理反斜杠
        normalized = os.path.normpath(win_path)
        
        # 检查是否是绝对路径（包含盘符）
        if len(normalized) >= 2 and normalized[1] == ':':
            drive_letter = normalized[0].lower()
            # 提取盘符后的路径部分
            if len(normalized) == 2:  # 只有盘符，如 "D:"
                path_part = ""
            elif normalized[2] == '\\':
                # 如果第三个字符是反斜杠，跳过它
                path_part = normalized[3:] if len(normalized) > 3 else ""
            else:
                # 没有反斜杠分隔符
                path_part = normalized[2:]
            
            # 转换为WSL路径
            wsl_path = f"/mnt/{drive_letter}/{path_part.replace('\\', '/')}"
            return wsl_path
        
        # 如果不是Windows绝对路径，返回原路径（相对路径或已经是WSL路径）
        return win_path.replace('\\', '/')

    def file_to_base64(self, file_path: str) -> str:
        """将文件转换为base64编码"""
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            base64_str = base64.b64encode(file_data).decode('utf-8')
            return f"base64://{base64_str}"
        except Exception as e:
            raise ValueError(f"读取文件失败: {e}")
    
    async def send_file(self, target: str, file_path: str, name: Optional[str] = None, 
                       message_type: str = "private", use_base64: bool = True,
                       convert_to_wsl: bool = True) -> dict:
        """
        发送文件
        
        Args:
            target: 目标ID（QQ号或群号）
            file_path: 文件路径
            name: 文件名（可选）
            message_type: 消息类型，"private" 或 "group"
            use_base64: 是否使用base64编码上传（推荐True）
            convert_to_wsl: 是否将Windows路径转换为WSL路径（当使用file://协议时）
            
        Returns:
            API响应
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        if not name:
            name = os.path.basename(file_path)
        
        file_size = os.path.getsize(file_path)
        if self.verbose:
            print(f"文件: {name}, 大小: {file_size} 字节 ({file_size/1024:.2f} KB)")
        
        if file_size > 50 * 1024 * 1024:  # 50MB限制
            print(f"警告: 文件大小 {file_size/1024/1024:.2f} MB，可能超过QQ文件大小限制", file=sys.stderr)
        
        if use_base64:
            # 使用base64编码上传
            if self.verbose:
                print("使用base64编码上传...")
            base64_file = self.file_to_base64(file_path)
            file_param = base64_file
        else:
            # 使用file://协议
            if self.verbose:
                print("使用file://协议上传...")
            
            if convert_to_wsl:
                # 将Windows路径转换为WSL路径（用于NapCat访问）
                wsl_path = self.win_path_to_wsl(os.path.abspath(file_path))
                file_url = f"file://{wsl_path}"
                if self.verbose:
                    print(f"  启用WSL路径转换")
                    print(f"  原始路径: {file_path}")
                    print(f"  绝对路径: {os.path.abspath(file_path)}")
                    print(f"  WSL路径: {wsl_path}")
                    print(f"  file:// URL: {file_url}")
            else:
                # 使用原始路径（不转换）
                file_url = f"file:///{os.path.abspath(file_path).replace('\\', '/')}"
                if self.verbose:
                    print(f"  禁用WSL路径转换")
                    print(f"  使用原始路径: {file_url}")
            
            file_param = file_url
        
        # 构建参数
        if message_type == "private":
            action = "upload_private_file"
            params = {
                "user_id": target,
                "file": file_param,
                "name": name if name else os.path.basename(file_path)
            }
        else:  # group
            action = "upload_group_file"
            params = {
                "group_id": target,
                "file": file_param,
                "name": name if name else os.path.basename(file_path)
            }
        
        if self.verbose:
            print(f"调用API: {action}")
            print(f"目标: {target}, 文件: {name}")
        
        # 发送请求
        response = await self.send_request(action, params, timeout=60)  # 文件上传可能需要更长时间
        
        return response
    
    async def close(self):
        """关闭连接"""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            self.is_connected = False

async def main_async(args):
    """异步主函数"""
    sender = None
    try:
        # 创建文件发送器
        sender = FileSender(server=args.server, token=args.token, verbose=args.verbose)
        
        # 连接
        await sender.connect()
        
        # 发送文件
        result = await sender.send_file(
            target=args.target,
            file_path=args.file,
            name=args.name,
            message_type=args.type,
            use_base64=not args.no_base64,
            convert_to_wsl=not getattr(args, 'no_wsl_convert', False)
        )
        
        return result
        
    except Exception as e:
        return {
            "status": "failed",
            "retcode": -1,
            "message": str(e),
            "data": None
        }
    finally:
        if sender:
            await sender.close()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="发送文件到QQ（私聊或群聊）- WebSocket版本",
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
    
    # 必需参数
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
        "--file", "-f",
        type=str,
        required=True,
        help="文件路径"
    )
    
    # 可选参数
    parser.add_argument(
        "--name",
        type=str,
        help="自定义文件名（可选）"
    )
    
    parser.add_argument(
        "--no-base64",
        action="store_true",
        default=False,
        help="不使用base64编码（使用file://协议）"
    )
    
    parser.add_argument(
        "--no-wsl-convert",
        action="store_true",
        default=False,
        help="禁用Windows路径到WSL路径的自动转换（当NapCat可以直接访问Windows路径时使用）"
    )
    
    args = parser.parse_args()
    
    # 验证token
    if not args.token:
        print("错误: 未提供认证令牌(token)。请通过 --token 参数提供，或在配置文件中设置默认值。", file=sys.stderr)
        print(f"配置文件位置: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)
    
    # 执行
    result = asyncio.run(main_async(args))
    
    # 输出结果
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if args.verbose:
            print(f"原始响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        # 检查响应格式
        status = result.get("status")
        retcode = result.get("retcode")
        
        if status == "ok" or (retcode is not None and retcode == 0):
            print("[OK] 文件发送成功")
            if "data" in result and result["data"]:
                if isinstance(result["data"], dict):
                    print(f"  文件ID: {result['data'].get('file_id', '未知')}")
                else:
                    print(f"  响应数据: {result['data']}")
        elif status == "failed" or (retcode is not None and retcode != 0):
            error_msg = result.get("message", result.get("wording", "未知错误"))
            print(f"[ERROR] 文件发送失败: {error_msg}")
            if args.verbose:
                print(f"  状态: {status}, 错误码: {retcode}")
            return 1
        else:
            # 未知响应格式，但文件可能已发送成功
            print("[INFO] 文件发送完成（响应格式未知）")
            if args.verbose:
                print(f"  完整响应: {json.dumps(result, ensure_ascii=False)}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())