#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 NapCat 的 get_msg API
用于诊断引用图片下载失败的问题
"""

import asyncio
import aiohttp
import json

# NapCat WebSocket 配置
WS_URL = "ws://localhost:3002"
ACCESS_TOKEN = "CqC5dDMXWGUu6NVh"

# 测试用的消息 ID
# OneBot message_id: 253731392（之前测试成功的消息）
TEST_MESSAGE_ID = 1822260651


async def test_get_msg(message_id: int):
    """测试 get_msg API"""
    print(f"\n{'='*60}")
    print(f"测试 get_msg API")
    print(f"{'='*60}")
    print(f"消息 ID: {message_id}")
    print(f"WebSocket: {WS_URL}")
    print()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(f"{WS_URL}?access_token={ACCESS_TOKEN}") as ws:
                # 等待连接完成
                await asyncio.sleep(0.5)
                
                # 发送 get_msg 请求
                request = {
                    "action": "get_msg",
                    "params": {
                        "message_id": message_id
                    },
                    "echo": "test_1"
                }
                
                print(f"发送请求:")
                print(json.dumps(request, indent=2, ensure_ascii=False))
                print(f"完整请求数据:")
                print(f"- Action: {request['action']}")
                print(f"- Params: {request['params']}")
                print(f"- Echo: {request['echo']} (类型: {type(request['echo']).__name__})")
                print(f"- 消息ID类型: {type(message_id).__name__}")
                print()
                
                # 记录发送时间
                send_time = asyncio.get_event_loop().time()
                print(f"发送时间戳: {send_time}")
                
                await ws.send_json(request)
                
                # 等待响应（最多接收 10 条消息，过滤 meta_event）
                print("等待响应...")
                for i in range(10):
                    try:
                        msg = await asyncio.wait_for(ws.receive_json(), timeout=2.0)
                        
                        # 跳过 meta_event
                        if msg.get('post_type') == 'meta_event':
                            print(f"收到 meta_event，跳过")
                            continue
                        
                        # 检查是否是 API 响应
                        if msg.get('echo') == 'test_1' or ('status' in msg and 'params' not in msg):
                            print(f"\n收到 API 响应:")
                            print(json.dumps(msg, indent=2, ensure_ascii=False, default=str))
                            print()
                            
                            # 分析响应
                            if msg.get('status') == 'ok':
                                print("✓ get_msg API 调用成功！")
                                
                                data = msg.get('data', {})
                                print(f"\n消息内容分析:")
                                print(f"  - 消息类型：{data.get('message_type', 'N/A')}")
                                print(f"  - 发送时间：{data.get('time', 'N/A')}")
                                print(f"  - 发送者：{data.get('sender', {}).get('nickname', 'N/A')}")
                                
                                # 分析 message 数组
                                message_array = data.get('message', [])
                                if isinstance(message_array, list):
                                    print(f"\n  - 消息段数量：{len(message_array)}")
                                    for j, segment in enumerate(message_array):
                                        if isinstance(segment, dict):
                                            seg_type = segment.get('type', 'unknown')
                                            print(f"    [{j}] 类型：{seg_type}")
                                            if seg_type == 'image':
                                                img_data = segment.get('data', {})
                                                print(f"        文件名：{img_data.get('file', 'N/A')}")
                                                url = img_data.get('url', 'N/A')
                                                print(f"        URL: {url[:100] if url and url != 'N/A' else 'N/A'}")
                                                if url and url != 'N/A' and 'rkey=' in url:
                                                    print(f"        ✓ URL 包含 rkey！")
                                                else:
                                                    print(f"        ✗ URL 不包含 rkey")
                                else:
                                    print(f"\n  ✗ message 字段不是数组格式：{type(message_array)}")
                                
                                return True
                            else:
                                print("✗ get_msg API 调用失败！")
                                print(f"  错误：{msg.get('message', 'Unknown error')}")
                                return False
                    except asyncio.TimeoutError:
                        break
                
                print("\n✗ 未收到 API 响应（超时 20 秒）")
                print("  可能原因：")
                print("  1. NapCat 不支持 get_msg API")
                print("  2. 消息 ID 不存在")
                print("  3. NapCat 配置问题")
                return False
                    
    except aiohttp.ClientError as e:
        print(f"\n✗ WebSocket 连接失败：{e}")
        print("  可能原因：")
        print("  1. NapCat 未启动")
        print("  2. WebSocket 地址或端口错误")
        print("  3. 访问令牌错误")
        return False
    except Exception as e:
        print(f"\n✗ 未知错误：{e}")
        return False


async def test_get_image(file_name: str):
    """测试 get_image API"""
    print(f"\n{'='*60}")
    print(f"测试 get_image API")
    print(f"{'='*60}")
    print(f"文件名：{file_name}")
    print(f"WebSocket: {WS_URL}")
    print()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(f"{WS_URL}?access_token={ACCESS_TOKEN}") as ws:
                # 发送 get_image 请求
                request = {
                    "action": "get_image",
                    "params": {
                        "file": file_name
                    },
                    "echo": "test_2"
                }
                
                print(f"发送请求:")
                print(json.dumps(request, indent=2, ensure_ascii=False))
                print()
                
                await ws.send_json(request)
                
                # 等待响应（超时 10 秒）
                print("等待响应...")
                try:
                    response = await asyncio.wait_for(ws.receive_json(), timeout=10.0)
                    
                    print(f"\n收到响应:")
                    print(json.dumps(response, indent=2, ensure_ascii=False, default=str))
                    print()
                    
                    # 分析响应
                    if response.get('status') == 'ok':
                        print("✓ get_image API 调用成功！")
                        data = response.get('data', {})
                        print(f"\n返回数据:")
                        print(f"  - file: {data.get('file', 'N/A')}")
                        print(f"  - url: {data.get('url', 'N/A')[:100] if data.get('url') else 'N/A'}")
                        if data.get('url') and 'rkey=' in data.get('url'):
                            print(f"  ✓ URL 包含 rkey！")
                        else:
                            print(f"  ✗ URL 不包含 rkey")
                        return True
                    else:
                        print("✗ get_image API 调用失败！")
                        print(f"  错误：{response.get('message', 'Unknown error')}")
                        return False
                        
                except asyncio.TimeoutError:
                    print("\n✗ 等待响应超时（10 秒）")
                    print("  可能原因：")
                    print("  1. NapCat 服务未响应")
                    print("  2. 文件名不存在")
                    print("  3. NapCat API 实现有问题")
                    return False
                    
    except aiohttp.ClientError as e:
        print(f"\n✗ WebSocket 连接失败：{e}")
        return False
    except Exception as e:
        print(f"\n✗ 未知错误：{e}")
        return False


async def main():
    """主函数"""
    print("\n" + "="*60)
    print("NapCat API 测试工具")
    print("="*60)
    print("\n用于诊断引用图片下载失败的问题")
    print("测试 get_msg 是否正常工作")
    print()
    
    # 测试 get_msg
    get_msg_result = await test_get_msg(TEST_MESSAGE_ID)
    
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"get_msg API:  {'✓ 成功' if get_msg_result else '✗ 失败'}")

    


if __name__ == "__main__":
    asyncio.run(main())
