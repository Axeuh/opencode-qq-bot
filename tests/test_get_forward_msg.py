#!/usr/bin/env python3
"""
测试合并转发消息 API
使用 get_forward_msg HTTP API 获取合并转发消息内容
"""

import asyncio
import json
import os
import sys

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.core.napcat_http_client import NapCatHttpClient

# 从模拟文件加载测试数据
SAMPLE_FILE = os.path.join(project_root, "docs", "私聊合并转发消息.json")


async def test_get_forward_msg():
    """测试 get_forward_msg HTTP API"""
    
    # 加载模拟文件
    with open(SAMPLE_FILE, 'r', encoding='utf-8') as f:
        sample_data = json.load(f)
    
    # 提取转发消息 ID
    forward_id = sample_data["message"][0]["data"]["id"]
    
    print("=" * 60)
    print("测试 get_forward_msg HTTP API")
    print("=" * 60)
    print(f"转发消息 ID: {forward_id}")
    print()
    
    async with NapCatHttpClient() as client:
        # 测试连接
        print("1. 测试 HTTP API 连接...")
        if await client.test_connection():
            print("   HTTP API 连接成功")
        else:
            print("   HTTP API 连接失败")
            return
        
        # 测试 get_forward_msg
        print(f"\n2. 测试 get_forward_msg API...")
        print(f"   message_id: {forward_id}")
        
        result = await client.get_forward_msg(forward_id)
        
        if result:
            print("   get_forward_msg 成功!")
            messages = result.get("messages", [])
            print(f"   消息数量: {len(messages)}")
            print()
            
            # 显示消息内容
            print("   消息内容:")
            print("-" * 50)
            for i, msg in enumerate(messages, 1):
                sender = msg.get("sender", {})
                nickname = sender.get("nickname", "未知")
                
                content = msg.get("content", [])
                if isinstance(content, list):
                    # 提取文本
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_parts.append(item.get("data", {}).get("text", ""))
                            elif item.get("type") == "image":
                                text_parts.append("[图片]")
                            elif item.get("type") == "file":
                                text_parts.append(f"[文件: {item.get('data', {}).get('file', '')}]")
                        elif isinstance(item, str):
                            text_parts.append(item)
                    text = "".join(text_parts)
                else:
                    text = str(content)
                
                print(f"   [{i}] {nickname}: {text[:100]}{'...' if len(text) > 100 else ''}")
            print("-" * 50)
            
            # 保存完整响应
            output_file = os.path.join(project_root, "docs", "get_forward_msg_response.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n   完整响应已保存到: {output_file}")
        else:
            print("   get_forward_msg 失败")


async def test_with_mock_id():
    """使用模拟 ID 测试（如果无法获取真实消息）"""
    
    # 使用模拟文件中的 ID
    mock_id = "7616536919042887682"
    
    print("=" * 60)
    print("测试 get_forward_msg (模拟 ID)")
    print("=" * 60)
    
    async with NapCatHttpClient() as client:
        result = await client.get_forward_msg(mock_id)
        
        if result:
            print("成功!")
            print(json.dumps(result, ensure_ascii=False, indent=2)[:500])
        else:
            print("失败或无数据")


if __name__ == "__main__":
    print("选择测试模式:")
    print("1. 使用模拟文件中的 ID 测试")
    print("2. 使用指定 ID 测试")
    
    choice = input("请选择 (1/2): ").strip()
    
    if choice == "2":
        asyncio.run(test_get_forward_msg())
    else:
        asyncio.run(test_with_mock_id())