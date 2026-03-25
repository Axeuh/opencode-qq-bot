#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试NapCat文件上传API
"""

import asyncio
import json
import sys
import uuid
import websockets

SERVER = "ws://localhost:3002"
TOKEN = "CqC5dDMXWGUu6NVh"

async def test_upload_private_file():
    """测试上传私聊文件"""
    ws_url = f"{SERVER}?access_token={TOKEN}"
    
    print(f"连接: {ws_url}")
    
    try:
        websocket = await asyncio.wait_for(
            websockets.connect(ws_url),
            timeout=10
        )
        
        print("连接成功")
        
        async with websocket:
            # 等待连接事件
            print("等待连接事件...")
            connect_event = await asyncio.wait_for(websocket.recv(), timeout=5)
            connect_json = json.loads(connect_event)
            self_id = connect_json.get("self_id", "unknown")
            print(f"机器人ID: {self_id}")
            
            # 测试upload_private_file API
            print("\n=== 测试upload_private_file API ===")
            echo = str(uuid.uuid4())
            # 注意：文件路径需要是NapCat可以访问的路径
            # 尝试使用file://协议
            file_path = "file:///D:/Users/Axeuh/Desktop/Axeuh_bot/mybot/downloads/2176284372/耗材申报表.xlsx"
            
            upload_request = {
                "action": "upload_private_file",
                "params": {
                    "user_id": 2176284372,
                    "file": file_path,
                    "name": "耗材申报表.xlsx"
                },
                "echo": echo
            }
            
            print(f"发送请求: {json.dumps(upload_request, ensure_ascii=False)}")
            await websocket.send(json.dumps(upload_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=30)
                print(f"响应: {response}")
                resp_json = json.loads(response)
                if resp_json.get("status") == "ok":
                    print("文件上传成功!")
                    print(f"响应数据: {json.dumps(resp_json.get('data', {}), ensure_ascii=False, indent=2)}")
                else:
                    print(f"文件上传失败: {resp_json.get('message', '未知错误')}")
            except asyncio.TimeoutError:
                print("等待响应超时")
                
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_upload_private_file())