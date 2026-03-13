#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试发送群聊消息
"""

import asyncio
import json
import sys
import uuid
import websockets

TOKEN = "CqC5dDMXWGUu6NVh"
SERVER = "ws://localhost:3002"
GROUP_ID = 813729523  # 从get_group_list获取的群ID

async def test_group_message():
    """测试群聊消息"""
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
            connect_json = json.loads(connect_event)
            self_id = connect_json.get("self_id", "unknown")
            print(f"机器人ID: {self_id}")
            
            # 1. 测试发送群聊消息
            print(f"\n=== 1. 测试发送群聊消息到群 {GROUP_ID} ===")
            echo = str(uuid.uuid4())
            group_request = {
                "action": "send_group_msg",
                "params": {
                    "group_id": GROUP_ID,
                    "message": "测试群聊消息",
                    "auto_escape": False
                },
                "echo": echo
            }
            
            print(f"发送: {json.dumps(group_request, ensure_ascii=False)}")
            await websocket.send(json.dumps(group_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                print(f"响应: {response}")
                resp_json = json.loads(response)
                
                if resp_json.get("status") == "ok":
                    print("✓ 群聊消息发送成功")
                    print(f"消息ID: {resp_json.get('data', {}).get('message_id', '未知')}")
                else:
                    retcode = resp_json.get("retcode")
                    message = resp_json.get("message", "")
                    print(f"✗ 群聊消息发送失败 - retcode: {retcode}")
                    print(f"错误信息: {message[:300]}...")
                    
                    # 检查是否有底层QQ错误
                    if "EventRet" in message:
                        import re
                        eventret_match = re.search(r'EventRet:\s*(\{.*?\})', message, re.DOTALL)
                        if eventret_match:
                            eventret_str = eventret_match.group(1)
                            try:
                                eventret = json.loads(eventret_str)
                                print(f"底层QQ错误: {json.dumps(eventret, ensure_ascii=False, indent=2)}")
                            except:
                                print(f"底层错误原始内容: {eventret_str[:200]}...")
            except asyncio.TimeoutError:
                print("等待响应超时")
            
            # 2. 测试获取群成员列表
            print(f"\n=== 2. 测试获取群 {GROUP_ID} 成员列表 ===")
            echo = str(uuid.uuid4())
            member_request = {
                "action": "get_group_member_list",
                "params": {
                    "group_id": GROUP_ID
                },
                "echo": echo
            }
            
            print(f"发送: {json.dumps(member_request, ensure_ascii=False)}")
            await websocket.send(json.dumps(member_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                print(f"响应: {response}")
                resp_json = json.loads(response)
                
                if resp_json.get("status") == "ok":
                    members = resp_json.get('data', [])
                    print(f"✓ 获取群成员列表成功，共 {len(members)} 个成员")
                    if members:
                        # 显示前几个成员
                        for i, member in enumerate(members[:5]):
                            print(f"  {i+1}. {member.get('user_id')} - {member.get('nickname', '未知')} ({member.get('card', '未知')})")
                else:
                    print(f"✗ 获取群成员列表失败: {resp_json.get('message', '未知错误')}")
            except asyncio.TimeoutError:
                print("等待响应超时")
            
            # 3. 测试给自己发送群聊at消息
            print(f"\n=== 3. 测试发送群聊at消息 ===")
            echo = str(uuid.uuid4())
            at_request = {
                "action": "send_group_msg",
                "params": {
                    "group_id": GROUP_ID,
                    "message": [
                        {"type": "text", "data": {"text": "测试at消息 @"}},
                        {"type": "at", "data": {"qq": self_id}}
                    ],
                    "auto_escape": False
                },
                "echo": echo
            }
            
            print(f"发送: {json.dumps(at_request, ensure_ascii=False)}")
            await websocket.send(json.dumps(at_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                print(f"响应: {response}")
                resp_json = json.loads(response)
                
                if resp_json.get("status") == "ok":
                    print("✓ 群聊at消息发送成功")
                else:
                    print(f"✗ 群聊at消息发送失败: {resp_json.get('message', '未知错误')}")
            except asyncio.TimeoutError:
                print("等待响应超时")
                
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    print("开始测试群聊消息发送...")
    asyncio.run(test_group_message())
    print("\n测试完成")

if __name__ == "__main__":
    main()