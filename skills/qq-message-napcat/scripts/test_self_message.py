#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试发送消息给自己（机器人）
"""

import asyncio
import json
import uuid
import websockets

TOKEN = "CqC5dDMXWGUu6NVh"
SERVER = "ws://localhost:3002"

async def send_to_self():
    """发送消息给自己（机器人）"""
    ws_url = f"{SERVER}?access_token={TOKEN}"
    
    print(f"连接: {ws_url}")
    
    try:
        websocket = await asyncio.wait_for(
            websockets.connect(ws_url),
            timeout=10
        )
        
        print("连接成功")
        
        async with websocket:
            # 等待连接事件以获取self_id
            connect_event = await asyncio.wait_for(websocket.recv(), timeout=5)
            connect_data = json.loads(connect_event)
            self_id = connect_data.get("self_id")
            
            if not self_id:
                print("无法获取self_id")
                return
            
            print(f"机器人self_id: {self_id}")
            
            # 发送消息给自己
            echo = str(uuid.uuid4())
            request = {
                "action": "send_private_msg",
                "params": {
                    "user_id": str(self_id),
                    "message": "测试发送给自己",
                    "auto_escape": False
                },
                "echo": echo
            }
            
            print(f"发送给自己: {json.dumps(request, ensure_ascii=False)}")
            await websocket.send(json.dumps(request))
            
            # 等待响应
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            print(f"响应: {response}")
            
            # 尝试解析
            try:
                resp_json = json.loads(response)
                if resp_json.get("echo") == echo:
                    print(f"匹配的响应: {json.dumps(resp_json, ensure_ascii=False)}")
                    
                    if resp_json.get("status") == "ok":
                        print("✓ 消息发送成功！")
                    else:
                        print(f"✗ 消息发送失败: {resp_json.get('message', '未知错误')}")
                else:
                    print("响应不匹配，继续等待...")
            except json.JSONDecodeError:
                print("响应不是有效的JSON")
                
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")

def main():
    """主函数"""
    print("测试发送消息给自己...")
    asyncio.run(send_to_self())
    print("\n测试完成")

if __name__ == "__main__":
    main()