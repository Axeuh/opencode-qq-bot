#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试机器人能力和配置
"""

import asyncio
import json
import sys
import uuid
import websockets

TOKEN = "CqC5dDMXWGUu6NVh"
SERVER = "ws://localhost:3002"

async def test_robot_capabilities():
    """测试机器人能力"""
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
            print(f"连接事件: {connect_event[:200]}...")
            
            # 1. 测试get_login_info
            print("\n=== 1. 测试get_login_info ===")
            echo = str(uuid.uuid4())
            login_request = {
                "action": "get_login_info",
                "params": {},
                "echo": echo
            }
            
            print(f"发送: {json.dumps(login_request, ensure_ascii=False)}")
            await websocket.send(json.dumps(login_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"响应: {response}")
                resp_json = json.loads(response)
                if resp_json.get("status") == "ok":
                    print(f"登录信息: {json.dumps(resp_json.get('data', {}), ensure_ascii=False, indent=2)}")
                else:
                    print(f"获取登录信息失败: {resp_json.get('message', '未知错误')}")
            except asyncio.TimeoutError:
                print("等待响应超时")
            
            # 2. 测试get_stranger_info (目标用户2176284372)
            print("\n=== 2. 测试get_stranger_info (目标用户2176284372) ===")
            echo = str(uuid.uuid4())
            stranger_request = {
                "action": "get_stranger_info",
                "params": {
                    "user_id": "2176284372",
                    "no_cache": False
                },
                "echo": echo
            }
            
            print(f"发送: {json.dumps(stranger_request, ensure_ascii=False)}")
            await websocket.send(json.dumps(stranger_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"响应: {response}")
                resp_json = json.loads(response)
                if resp_json.get("status") == "ok":
                    stranger_info = resp_json.get('data', {})
                    print(f"陌生人信息: {json.dumps(stranger_info, ensure_ascii=False, indent=2)}")
                    if stranger_info:
                        print(f"用户昵称: {stranger_info.get('nickname', '未知')}")
                        print(f"用户性别: {stranger_info.get('sex', '未知')}")
                        print(f"用户年龄: {stranger_info.get('age', '未知')}")
                else:
                    print(f"获取陌生人信息失败: {resp_json.get('message', '未知错误')}")
            except asyncio.TimeoutError:
                print("等待响应超时")
            
            # 3. 测试get_group_list
            print("\n=== 3. 测试get_group_list ===")
            echo = str(uuid.uuid4())
            group_request = {
                "action": "get_group_list",
                "params": {},
                "echo": echo
            }
            
            print(f"发送: {json.dumps(group_request, ensure_ascii=False)}")
            await websocket.send(json.dumps(group_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"响应: {response}")
                resp_json = json.loads(response)
                if resp_json.get("status") == "ok":
                    group_list = resp_json.get('data', [])
                    print(f"群组数量: {len(group_list)}")
                    if group_list:
                        print(f"前5个群组: {json.dumps(group_list[:5], ensure_ascii=False, indent=2)}")
                    else:
                        print("机器人未加入任何群组")
                else:
                    print(f"获取群列表失败: {resp_json.get('message', '未知错误')}")
            except asyncio.TimeoutError:
                print("等待响应超时")
            
            # 4. 测试不同的send_private_msg参数组合
            print("\n=== 4. 测试send_private_msg参数组合 ===")
            test_cases = [
                {
                    "name": "基础文本消息",
                    "params": {
                        "user_id": "2176284372",
                        "message": "这是一条测试消息",
                        "auto_escape": False
                    }
                },
                {
                    "name": "带auto_escape=True",
                    "params": {
                        "user_id": "2176284372",
                        "message": "这是一条测试消息[CQ:face,id=123]",
                        "auto_escape": True  # 自动转义CQ码
                    }
                },
                {
                    "name": "消息段数组格式",
                    "params": {
                        "user_id": "2176284372",
                        "message": [
                            {"type": "text", "data": {"text": "测试"}},
                            {"type": "text", "data": {"text": "消息"}}
                        ],
                        "auto_escape": False
                    }
                },
                {
                    "name": "纯文本简单消息",
                    "params": {
                        "user_id": "2176284372",
                        "message": "test",
                        "auto_escape": False
                    }
                }
            ]
            
            for test_case in test_cases:
                print(f"\n测试: {test_case['name']}")
                echo = str(uuid.uuid4())
                request = {
                    "action": "send_private_msg",
                    "params": test_case["params"],
                    "echo": echo
                }
                
                print(f"发送: {json.dumps(request, ensure_ascii=False)}")
                await websocket.send(json.dumps(request))
                
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    print(f"响应: {response}")
                    resp_json = json.loads(response)
                    
                    # 分析错误
                    if resp_json.get("status") == "failed":
                        retcode = resp_json.get("retcode")
                        message = resp_json.get("message", "")
                        print(f"失败 - retcode: {retcode}")
                        print(f"错误信息: {message[:200]}...")
                        
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
                
                await asyncio.sleep(1)  # 避免过快发送
            
            # 5. 测试是否可以给自己发送消息
            print("\n=== 5. 测试给自己发送消息 ===")
            echo = str(uuid.uuid4())
            self_request = {
                "action": "send_private_msg",
                "params": {
                    "user_id": self_id,  # 给自己发
                    "message": "给自己发的测试消息",
                    "auto_escape": False
                },
                "echo": echo
            }
            
            print(f"发送: {json.dumps(self_request, ensure_ascii=False)}")
            await websocket.send(json.dumps(self_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"响应: {response}")
            except asyncio.TimeoutError:
                print("等待响应超时")
            
            # 6. 测试get_version_info
            print("\n=== 6. 测试get_version_info ===")
            echo = str(uuid.uuid4())
            version_request = {
                "action": "get_version_info",
                "params": {},
                "echo": echo
            }
            
            print(f"发送: {json.dumps(version_request, ensure_ascii=False)}")
            await websocket.send(json.dumps(version_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"响应: {response}")
                resp_json = json.loads(response)
                if resp_json.get("status") == "ok":
                    print(f"版本信息: {json.dumps(resp_json.get('data', {}), ensure_ascii=False, indent=2)}")
            except asyncio.TimeoutError:
                print("等待响应超时")
                
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    print("开始测试机器人能力...")
    asyncio.run(test_robot_capabilities())
    print("\n测试完成")

if __name__ == "__main__":
    main()