#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试napcat WebSocket API
"""

import asyncio
import json
import sys
import uuid
import websockets

TOKEN = "CqC5dDMXWGUu6NVh"
SERVER = "ws://localhost:3002"

async def test_api():
    """测试API基本功能"""
    # 构建带token的URL
    ws_url = f"{SERVER}?access_token={TOKEN}"
    
    print(f"连接: {ws_url}")
    
    try:
        # 连接
        websocket = await asyncio.wait_for(
            websockets.connect(ws_url),
            timeout=10
        )
        
        print("连接成功")
        
        async with websocket:
            # 监听连接事件
            print("等待连接事件...")
            connect_event = await asyncio.wait_for(websocket.recv(), timeout=5)
            print(f"连接事件: {connect_event}")
            
            # 测试get_status
            echo = str(uuid.uuid4())
            status_request = {
                "action": "get_status",
                "params": {},
                "echo": echo
            }
            
            print(f"发送get_status: {json.dumps(status_request)}")
            await websocket.send(json.dumps(status_request))
            
            # 等待响应
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            print(f"get_status响应: {response}")
            
            # 测试send_private_msg使用不同的格式
            test_messages = [
                # 格式1: 纯文本
                {"format": "纯文本", "message": "测试消息"},
                # 格式2: 消息段数组
                {"format": "消息段数组", "message": [
                    {"type": "text", "data": {"text": "测试"}},
                    {"type": "text", "data": {"text": "消息"}}
                ]},
                # 格式3: CQ码字符串
                {"format": "CQ码", "message": "测试消息[CQ:face,id=123]"},
            ]
            
            for test in test_messages:
                print(f"\n测试消息格式: {test['format']}")
                echo = str(uuid.uuid4())
                
                request = {
                    "action": "send_private_msg",
                    "params": {
                        "user_id": "2176284372",
                        "message": test["message"],
                        "auto_escape": False
                    },
                    "echo": echo
                }
                
                print(f"发送请求: {json.dumps(request, ensure_ascii=False)}")
                await websocket.send(json.dumps(request))
                
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    print(f"响应: {response}")
                    
                    # 解析响应
                    try:
                        resp_json = json.loads(response)
                        if resp_json.get("echo") == echo:
                            print(f"匹配的响应: {json.dumps(resp_json, ensure_ascii=False)}")
                        else:
                            print(f"不匹配的响应，继续等待...")
                            # 继续等待匹配的响应
                            for _ in range(3):
                                try:
                                    response2 = await asyncio.wait_for(websocket.recv(), timeout=2)
                                    resp_json2 = json.loads(response2)
                                    if resp_json2.get("echo") == echo:
                                        print(f"匹配的响应: {json.dumps(resp_json2, ensure_ascii=False)}")
                                        break
                                except (asyncio.TimeoutError, json.JSONDecodeError):
                                    continue
                    except json.JSONDecodeError:
                        print("响应不是有效的JSON")
                        
                except asyncio.TimeoutError:
                    print("等待响应超时")
                
                await asyncio.sleep(1)  # 避免过快发送
            
            # 测试获取好友列表
            print(f"\n测试get_friend_list...")
            echo = str(uuid.uuid4())
            friend_request = {
                "action": "get_friend_list",
                "params": {},
                "echo": echo
            }
            
            print(f"发送: {json.dumps(friend_request)}")
            await websocket.send(json.dumps(friend_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"响应: {response}")
            except asyncio.TimeoutError:
                print("等待响应超时")
                
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    print("开始调试napcat WebSocket API...")
    asyncio.run(test_api())
    print("\n调试完成")

if __name__ == "__main__":
    main()