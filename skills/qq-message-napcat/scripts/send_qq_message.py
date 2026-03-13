#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QQ消息发送脚本 - 通过napcat API发送私聊和群聊消息

用法:
    python send_qq_message.py --type private --target 123456 --message "你好"
    python send_qq_message.py --type group --target 123456789 --message '[{"type":"text","data":{"text":"群消息"}}]'

支持的参数:
    --type, -t       消息类型 (private/group)
    --target, -T     目标ID (QQ号或群号)
    --message, -m    消息内容 (文本或JSON字符串)
    --auto-escape, -a 自动转义CQ码 (默认: False)
    --server, -s     napcat服务器地址 (默认: http://localhost:3002)
    --token, -k      认证令牌 (默认: CqC5dDMXWGUu6NVh)
    --verbose, -v    详细输出
    --quiet, -q      静默模式
    --json, -j       JSON格式输出
"""

import argparse
import json
import sys
import os
from typing import Union, Dict, Any, List
import requests

# 默认配置
DEFAULT_SERVER = "http://localhost:3002"
DEFAULT_TOKEN = "CqC5dDMXWGUu6NVh"

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="通过napcat API发送QQ消息",
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
        help="认证令牌（默认使用预设令牌）"
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

def send_qq_message(
    message_type: str,
    target_id: str,
    message: Union[str, List[Dict[str, Any]]],
    auto_escape: bool = False,
    server: str = DEFAULT_SERVER,
    token: str = DEFAULT_TOKEN
) -> Dict[str, Any]:
    """
    发送QQ消息到napcat API
    
    Args:
        message_type: "private" 或 "group"
        target_id: 目标ID（QQ号或群号）
        message: 消息内容（字符串或消息段列表）
        auto_escape: 是否自动转义CQ码
        server: napcat服务器地址
        token: 认证令牌
    
    Returns:
        API响应字典
    """
    # 构建API端点
    if message_type == "private":
        endpoint = "/send_private_msg"
    else:  # group
        endpoint = "/send_group_msg"
    
    url = f"{server}{endpoint}"
    
    # 准备请求头
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 准备请求体
    if message_type == "private":
        data = {
            "user_id": target_id,
            "message": message,
            "auto_escape": auto_escape
        }
    else:  # group
        data = {
            "group_id": target_id,
            "message": message,
            "auto_escape": auto_escape
        }
    
    try:
        # 发送请求
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        # 尝试解析JSON响应
        try:
            response_json = response.json()
            if response.status_code == 200:
                result = response_json
                result["success"] = True
                result["status_code"] = response.status_code
            else:
                result = {
                    "success": False,
                    "status_code": response.status_code,
                    "error": f"HTTP错误: {response.status_code}",
                    "response_text": response.text,
                    "response_json": response_json
                }
        except json.JSONDecodeError:
            # 响应不是有效的JSON
            result = {
                "success": False,
                "status_code": response.status_code,
                "error": "响应不是有效的JSON格式",
                "response_text": response.text
            }
            
    except requests.exceptions.ConnectionError:
        result = {
            "success": False,
            "status_code": 0,
            "error": "连接失败，请检查napcat服务是否运行",
            "server": server
        }
    except requests.exceptions.Timeout:
        result = {
            "success": False,
            "status_code": 0,
            "error": "请求超时，请检查网络连接",
            "server": server
        }
    except requests.exceptions.RequestException as e:
        result = {
            "success": False,
            "status_code": 0,
            "error": f"请求异常: {str(e)}",
            "server": server
        }
    
    return result

def main():
    """主函数"""
    args = parse_arguments()
    
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
        token=args.token
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
                print("✓ 消息发送成功")
                if "data" in result and "message_id" in result["data"]:
                    print(f"  消息ID: {result['data']['message_id']}")
                if args.verbose:
                    print(f"  状态码: {result.get('status_code', 'N/A')}")
                    print(f"  响应: {result}")
        else:
            if not args.quiet:
                print("✗ 消息发送失败", file=sys.stderr)
                print(f"  错误: {result.get('error', '未知错误')}", file=sys.stderr)
                if "response_text" in result:
                    print(f"  响应内容: {result['response_text']}", file=sys.stderr)
            sys.exit(1)
    
    return 0 if result.get("success") else 1

if __name__ == "__main__":
    sys.exit(main())