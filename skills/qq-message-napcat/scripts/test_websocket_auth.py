#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试napcat WebSocket认证
"""

import asyncio
import json
import sys
import websockets

TOKEN = "CqC5dDMXWGUu6NVh"

async def test_websocket_with_auth(uri, auth_method="url"):
    """测试带认证的WebSocket连接"""
    print(f"尝试连接: {uri} (认证方式: {auth_method})")
    
    final_uri = uri
    extra_headers = None
    
    # 根据认证方式准备
    if auth_method == "url":
        # URL参数方式
        if "?" in uri:
            final_uri = f"{uri}&access_token={TOKEN}"
        else:
            final_uri = f"{uri}?access_token={TOKEN}"
    elif auth_method == "header":
        # HTTP头方式（WebSocket握手时）
        extra_headers = {"Authorization": f"Bearer {TOKEN}"}
    
    try:
        # 使用wait_for包装连接，设置10秒超时
        connect_kwargs = {}
        if extra_headers:
            connect_kwargs["extra_headers"] = extra_headers
            
        connect_task = websockets.connect(final_uri, **connect_kwargs)
        websocket = await asyncio.wait_for(connect_task, timeout=10)
        
        async with websocket:
            print("WebSocket连接成功")
            
            # 如果使用消息认证，发送认证消息
            if auth_method == "message":
                auth_msg = {
                    "action": "auth",
                    "params": {"token": TOKEN},
                    "echo": "auth_test"
                }
                print(f"发送认证消息: {json.dumps(auth_msg)}")
                await websocket.send(json.dumps(auth_msg))
                
                # 等待认证响应
                try:
                    auth_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    print(f"认证响应: {auth_response}")
                except asyncio.TimeoutError:
                    print("认证响应超时")
            
            # 发送一个简单的get_status消息
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
                    
                    # 检查是否成功
                    if response_json.get("status") == "ok" or response_json.get("retcode") == 0:
                        print("认证成功!")
                        return True, response_json
                    else:
                        print(f"请求失败: {response_json.get('message', '未知错误')}")
                        return False, response_json
                        
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

async def test_all_auth_methods():
    """测试所有认证方式"""
    base_uri = "ws://localhost:3002"
    auth_methods = ["url", "header", "message"]
    
    results = []
    
    for method in auth_methods:
        print(f"\n{'='*60}")
        print(f"测试认证方式: {method}")
        print('='*60)
        success, response = await test_websocket_with_auth(base_uri, method)
        results.append((method, success, response))
        await asyncio.sleep(0.5)
    
    return results

def main():
    """主函数"""
    print("开始测试napcat WebSocket认证...")
    
    # 运行异步测试
    results = asyncio.run(test_all_auth_methods())
    
    print(f"\n{'='*60}")
    print("认证测试完成")
    
    successful_methods = []
    for method, success, response in results:
        status = "成功" if success else "失败"
        print(f"认证方式 {method}: {status}")
        if success and response:
            print(f"  响应: {json.dumps(response)[:100]}...")
            successful_methods.append(method)
    
    if successful_methods:
        print(f"\n可用的认证方式: {', '.join(successful_methods)}")
        print(f"推荐使用: {successful_methods[0]}")
    else:
        print("\n所有认证方式都失败，请检查token是否正确")
        print("注意：可能需要查看napcat文档了解正确的WebSocket认证方式")

if __name__ == "__main__":
    main()