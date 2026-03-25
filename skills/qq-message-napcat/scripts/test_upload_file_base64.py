#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试NapCat文件上传API使用base64编码
"""

import asyncio
import json
import sys
import uuid
import websockets
import base64

SERVER = "ws://localhost:3002"
TOKEN = "CqC5dDMXWGUu6NVh"

def file_to_base64(file_path):
    """将文件转换为base64编码"""
    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()
        base64_str = base64.b64encode(file_data).decode('utf-8')
        return f"base64://{base64_str}"
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None

async def test_upload_private_file_base64():
    """测试使用base64上传私聊文件"""
    ws_url = f"{SERVER}?access_token={TOKEN}"
    
    print(f"连接: {ws_url}")
    
    # 读取文件并转换为base64
    file_path = r"D:\Users\Axeuh\Desktop\Axeuh_bot\mybot\downloads\2176284372\耗材申报表.xlsx"
    print(f"读取文件: {file_path}")
    
    file_size = 0
    try:
        import os
        file_size = os.path.getsize(file_path)
        print(f"文件大小: {file_size} 字节 ({file_size/1024:.2f} KB)")
    except:
        pass
    
    if file_size > 10 * 1024 * 1024:  # 10MB限制
        print(f"警告: 文件大小 {file_size/1024/1024:.2f} MB，可能超过QQ文件大小限制")
    
    base64_file = file_to_base64(file_path)
    if not base64_file:
        print("文件转换失败")
        return
    
    # 只显示base64前缀，不打印整个base64字符串
    print(f"Base64前缀: {base64_file[:50]}...")
    
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
            
            # 测试upload_private_file API with base64
            print("\n=== 测试upload_private_file API (base64) ===")
            echo = str(uuid.uuid4())
            
            upload_request = {
                "action": "upload_private_file",
                "params": {
                    "user_id": 2176284372,
                    "file": base64_file,
                    "name": "耗材申报表.xlsx"
                },
                "echo": echo
            }
            
            print(f"发送请求 (已省略base64数据)")
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
    asyncio.run(test_upload_private_file_base64())