#!/usr/bin/env python3
"""
测试 HTTP get_msg API (端口 3002)
用于获取引用消息内容
"""

import asyncio
import aiohttp
import json
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


async def test_get_msg_http():
    """测试 HTTP get_msg API (端口 3002)"""
    
    # NapCat HTTP 配置 - 使用 3001 端口（HTTP API 端口）
    base_url = "http://localhost:3001"
    access_token = "fZvJ-zo_TzyAHOoI"  # HTTP API token
    timeout = 30
    
    # 测试消息 ID（从模拟引用文件中提取）
    # reply 消息中的 id: 105491474
    test_message_id = 105491474
    
    print("=" * 60)
    print("测试 HTTP get_msg API (端口 3001)")
    print("=" * 60)
    print(f"Base URL: {base_url}")
    print(f"测试消息 ID: {test_message_id}")
    print()
    
    # 创建 HTTP 会话
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}',
        'User-Agent': 'AxeuhBot/1.0'
    }
    
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout),
        headers=headers
    ) as session:
        
        # 测试 1: 获取引用消息内容
        print("1. 测试 get_msg 获取引用消息...")
        url = f"{base_url}/get_msg"
        data = {"message_id": test_message_id}
        
        try:
            async with session.post(url, json=data) as response:
                print(f"   HTTP 状态码: {response.status}")
                response_text = await response.text()
                
                if response.status == 200:
                    try:
                        result = json.loads(response_text)
                        print(f"   响应状态: {result.get('status', 'unknown')}")
                        
                        if result.get('status') == 'ok':
                            msg_data = result.get('data', {})
                            print("   get_msg 成功!")
                            print(f"   消息内容: {msg_data.get('message', 'N/A')}")
                            print(f"   原始消息: {msg_data.get('raw_message', 'N/A')}")
                            print(f"   发送者: {msg_data.get('sender', {}).get('nickname', 'N/A')}")
                            print(f"   完整响应: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
                        else:
                            print(f"   get_msg 失败: {result.get('message', 'unknown error')}")
                            print(f"   完整响应: {response_text[:500]}")
                    except json.JSONDecodeError as e:
                        print(f"   JSON 解析失败: {e}")
                        print(f"   原始响应: {response_text[:500]}")
                else:
                    print(f"   请求失败: {response_text[:500]}")
                    
        except aiohttp.ClientError as e:
            print(f"   HTTP 客户端错误: {e}")
        except asyncio.TimeoutError:
            print("   请求超时")
        except Exception as e:
            print(f"   异常: {e}")
        
        print()
        
        # 测试 2: 获取状态
        print("2. 测试 get_status...")
        url = f"{base_url}/get_status"
        
        try:
            async with session.post(url, json={}) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"   状态: {result.get('status', 'unknown')}")
                    if result.get('status') == 'ok':
                        data = result.get('data', {})
                        print(f"   在线: {data.get('online', False)}")
                        print(f"   状态: {data.get('status', 'unknown')}")
                else:
                    print(f"   失败: {response.status}")
        except Exception as e:
            print(f"   异常: {e}")


async def test_multiple_message_ids():
    """测试多个消息 ID"""
    
    base_url = "http://localhost:3001"
    access_token = "fZvJ-zo_TzyAHOoI"  # HTTP API token
    
    # 从模拟引用文件中提取的消息 ID
    message_ids = [
        105491474,  # reply 消息 ID
        1582933052, # 主消息 ID
    ]
    
    print("\n" + "=" * 60)
    print("测试多个消息 ID")
    print("=" * 60)
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}',
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for msg_id in message_ids:
            print(f"\n消息 ID: {msg_id}")
            
            try:
                async with session.post(
                    f"{base_url}/get_msg",
                    json={"message_id": msg_id}
                ) as response:
                    result = await response.json()
                    
                    if result.get('status') == 'ok':
                        data = result.get('data', {})
                        print(f"   成功! 内容: {data.get('raw_message', 'N/A')[:100]}")
                    else:
                        print(f"   失败: {result.get('message', 'unknown')}")
            except Exception as e:
                print(f"   异常: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("NapCat HTTP API 测试 (端口 3001)")
    print("=" * 60)
    
    asyncio.run(test_get_msg_http())
    asyncio.run(test_multiple_message_ids())