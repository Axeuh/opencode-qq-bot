#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试napcat WebSocket连接
"""

import asyncio
import json
import sys
import websockets

async def test_websocket_connection(uri):
    """测试WebSocket连接"""
    print(f"尝试连接: {uri}")
    
    try:
        # 使用wait_for包装连接，设置10秒超时
        connect_task = websockets.connect(uri)
        websocket = await asyncio.wait_for(connect_task, timeout=10)
        
        async with websocket:
            print("WebSocket连接成功")
            
            # 发送一个简单的ping消息
            ping_msg = {"action": "get_status", "params": {}, "echo": "test"}
            print(f"发送消息: {json.dumps(ping_msg)}")
            
            await websocket.send(json.dumps(ping_msg))
            
            # 等待响应
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"收到响应: {response}")
                
                # 尝试解析JSON
                try:
                    response_json = json.loads(response)
                    print(f"JSON解析成功: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
                    return True, response_json
                except json.JSONDecodeError:
                    print("响应不是有效的JSON")
                    return True, None
                    
            except asyncio.TimeoutError:
                print("等待响应超时")
                return True, None
                
    except websockets.exceptions.InvalidURI:
        print("无效的URI格式")
        return False, None
    except websockets.exceptions.InvalidHandshake:
        print("WebSocket握手失败")
        return False, None
    except ConnectionRefusedError:
        print("连接被拒绝，服务可能未运行")
        return False, None
    except asyncio.TimeoutError:
        print("连接超时")
        return False, None
    except Exception as e:
        print(f"连接错误: {type(e).__name__}: {e}")
        return False, None

async def test_all_endpoints():
    """测试所有可能的WebSocket端点"""
    base_urls = [
        "ws://localhost:3002",
        "ws://localhost:3002/",
        "ws://localhost:3002/ws",
        "ws://localhost:3002/websocket",
        "ws://localhost:3002/api/ws",
        "ws://localhost:3002/onebot/v11/ws",
        "ws://localhost:3002/onebot/ws",
        "ws://localhost:3002/api",
        "ws://localhost:3002/v11",
        "wss://localhost:3002",  # 也测试HTTPS
        "wss://localhost:3002/ws"
    ]
    
    working_endpoints = []
    
    for uri in base_urls:
        print(f"\n{'='*60}")
        print(f"测试端点: {uri}")
        print('='*60)
        success, response = await test_websocket_connection(uri)
        if success:
            working_endpoints.append((uri, response))
        await asyncio.sleep(0.5)  # 避免过快连接
    
    return working_endpoints

def main():
    """主函数"""
    print("开始测试napcat WebSocket连接...")
    
    # 运行异步测试
    working = asyncio.run(test_all_endpoints())
    
    print(f"\n{'='*60}")
    print("测试完成")
    print(f"找到 {len(working)} 个可用的WebSocket端点:")
    for uri, response in working:
        print(f"  - {uri}")
        if response:
            print(f"    响应示例: {json.dumps(response)[:100]}...")
    
    if working:
        print(f"\n推荐使用: {working[0][0]}")
    else:
        print("\n未找到可用的WebSocket端点，请检查napcat服务配置")

if __name__ == "__main__":
    main()