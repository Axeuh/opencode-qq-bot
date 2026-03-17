#!/usr/bin/env python3
"""
测试连接到NapCat WebSocket Server
"""

import asyncio
import json
import sys
import aiohttp

async def test_connection():
    """测试WebSocket连接"""
    ws_url = "ws://127.0.0.1:3001"
    access_token = "CqC5dDMXWGUu6NVh"
    
    headers = {}
    if access_token:
        headers['Authorization'] = f'Bearer {access_token}'
    
    print(f"正在测试连接到 {ws_url}...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                ws_url,
                headers=headers,
                heartbeat=30
            ) as ws:
                print("[OK] 连接成功！")
                print("等待5秒接收消息...")
                
                # 等待消息
                try:
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                print(f"收到消息: {json.dumps(data, ensure_ascii=False, indent=2)}")
                            except json.JSONDecodeError:
                                print(f"收到非JSON消息: {msg.data}")
                        
                        # 5秒后退出
                        await asyncio.sleep(5)
                        break
                        
                except asyncio.TimeoutError:
                    print("未收到消息")
                    
    except aiohttp.ClientConnectorError as e:
        print(f"[ERROR] 连接失败: {e}")
        print("请确保NapCat正在运行并且WebSocket服务器端口3001已打开")
    except Exception as e:
        print(f"[ERROR] 发生错误: {e}")
    
    print("测试完成")

if __name__ == '__main__':
    asyncio.run(test_connection())
