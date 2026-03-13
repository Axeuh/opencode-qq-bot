#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查机器人状态和诊断网络连接问题
"""

import asyncio
import json
import sys
import uuid
import websockets

TOKEN = "CqC5dDMXWGUu6NVh"
SERVER = "ws://localhost:3002"

async def check_bot_status():
    """检查机器人状态"""
    # 构建带token的URL
    ws_url = f"{SERVER}?access_token={TOKEN}"
    
    print("=== NapCat QQ机器人状态诊断 ===")
    print(f"服务器: {ws_url}")
    
    try:
        # 尝试连接
        print("\n1. 尝试连接到WebSocket服务器...")
        websocket = await asyncio.wait_for(
            websockets.connect(ws_url),
            timeout=10
        )
        
        print("✓ WebSocket连接成功")
        
        async with websocket:
            # 监听连接事件
            print("\n2. 等待连接事件...")
            try:
                connect_event = await asyncio.wait_for(websocket.recv(), timeout=5)
                connect_json = json.loads(connect_event)
                self_id = connect_json.get("self_id", "unknown")
                post_type = connect_json.get("post_type", "")
                sub_type = connect_json.get("sub_type", "")
                
                print(f"✓ 收到连接事件")
                print(f"   机器人ID: {self_id}")
                print(f"   事件类型: {post_type}.{sub_type}")
                
                if post_type == "meta_event" and sub_type == "connect":
                    print("   ✓ 连接状态: 正常")
                else:
                    print(f"   ⚠ 连接状态: 异常事件 - {post_type}.{sub_type}")
                    
            except asyncio.TimeoutError:
                print("✗ 未收到连接事件（可能账号已离线）")
                print("   ℹ 建议: 检查QQ账号是否在线，重新登录NapCat")
                return False
            
            # 3. 检查登录状态
            print("\n3. 检查登录状态...")
            echo = str(uuid.uuid4())
            login_request = {
                "action": "get_login_info",
                "params": {},
                "echo": echo
            }
            
            await websocket.send(json.dumps(login_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                resp_json = json.loads(response)
                
                if resp_json.get("status") == "ok":
                    login_info = resp_json.get('data', {})
                    user_id = login_info.get('user_id')
                    nickname = login_info.get('nickname')
                    
                    print(f"✓ 登录状态正常")
                    print(f"   用户ID: {user_id}")
                    print(f"   昵称: {nickname}")
                else:
                    print(f"✗ 登录状态检查失败: {resp_json.get('message', '未知错误')}")
                    return False
                    
            except asyncio.TimeoutError:
                print("✗ 登录状态检查超时（可能API无响应）")
                return False
            
            # 4. 检查服务状态
            print("\n4. 检查服务状态...")
            echo = str(uuid.uuid4())
            status_request = {
                "action": "get_status",
                "params": {},
                "echo": echo
            }
            
            await websocket.send(json.dumps(status_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                resp_json = json.loads(response)
                
                if resp_json.get("status") == "ok":
                    status_data = resp_json.get('data', {})
                    online = status_data.get('online', False)
                    good = status_data.get('good', False)
                    
                    print(f"✓ 服务状态正常")
                    print(f"   在线状态: {'在线' if online else '离线'}")
                    print(f"   服务健康: {'良好' if good else '异常'}")
                    
                    if not online:
                        print("   ⚠ 警告: 服务显示为离线状态")
                        print("   ℹ 建议: 重新登录QQ账号，重启NapCat服务")
                        return False
                        
                else:
                    print(f"✗ 服务状态检查失败: {resp_json.get('message', '未知错误')}")
                    return False
                    
            except asyncio.TimeoutError:
                print("✗ 服务状态检查超时")
                return False
            
            # 5. 测试简单的API调用（不发送消息）
            print("\n5. 测试API基础功能...")
            echo = str(uuid.uuid4())
            version_request = {
                "action": "get_version_info",
                "params": {},
                "echo": echo
            }
            
            await websocket.send(json.dumps(version_request))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                resp_json = json.loads(response)
                
                if resp_json.get("status") == "ok":
                    version_info = resp_json.get('data', {})
                    app_name = version_info.get('app_name', '')
                    app_version = version_info.get('app_version', '')
                    protocol = version_info.get('protocol_version', '')
                    
                    print(f"✓ API功能正常")
                    print(f"   应用名称: {app_name}")
                    print(f"   应用版本: {app_version}")
                    print(f"   协议版本: {protocol}")
                else:
                    print(f"✗ API功能测试失败: {resp_json.get('message', '未知错误')}")
                    return False
                    
            except asyncio.TimeoutError:
                print("✗ API功能测试超时")
                return False
            
            print("\n=== 诊断总结 ===")
            print("✓ 所有检查项通过")
            print("✓ 机器人状态正常")
            print("✓ 可以尝试发送消息")
            return True
                
    except websockets.exceptions.InvalidURI:
        print(f"✗ 无效的URL: {ws_url}")
        return False
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"✗ HTTP错误: 状态码 {e.status_code}")
        if e.status_code == 401:
            print("   ℹ 建议: 检查认证令牌是否正确")
        elif e.status_code == 404:
            print("   ℹ 建议: 检查服务器地址和端口")
        return False
    except ConnectionRefusedError:
        print("✗ 连接被拒绝")
        print("   ℹ 建议: NapCat服务可能未启动，请检查服务状态")
        return False
    except asyncio.TimeoutError:
        print("✗ 连接超时")
        print("   ℹ 建议: 检查网络连接，确认napcat服务正在运行")
        return False
    except Exception as e:
        print(f"✗ 连接错误: {type(e).__name__}: {e}")
        return False

def main():
    """主函数"""
    print("开始检查NapCat QQ机器人状态...")
    print(f"当前时间: 2026-03-05 16:28")
    
    try:
        result = asyncio.run(check_bot_status())
        
        if result:
            print("\n✅ 机器人状态正常，可以发送消息")
        else:
            print("\n❌ 机器人状态异常，请参考以上建议进行修复")
            print("\n📋 修复建议：")
            print("1. 重新登录QQ账号到NapCat")
            print("2. 重启NapCat服务")
            print("3. 检查网络连接和防火墙设置")
            print("4. 验证认证令牌是否正确")
            print("5. 检查napcat服务日志获取详细信息")
            
    except KeyboardInterrupt:
        print("\n用户中断检查")
        sys.exit(1)

if __name__ == "__main__":
    main()
