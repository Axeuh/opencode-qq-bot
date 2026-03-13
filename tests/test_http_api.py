#!/usr/bin/env python3
"""
测试NapCat HTTP API连接和功能
"""

import asyncio
import json
import sys
import aiohttp
from typing import Optional, Dict, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 从配置文件读取配置
try:
    from src.utils.config import HTTP_API_BASE_URL, HTTP_API_ACCESS_TOKEN, HTTP_API_TIMEOUT
except ImportError:
    # 如果导入失败，使用硬编码配置（与config.yaml一致）
    HTTP_API_BASE_URL = "http://localhost:3001"
    HTTP_API_ACCESS_TOKEN = "fZvJ-zo_TzyAHOoI"
    HTTP_API_TIMEOUT = 30

# 测试用的消息ID（从之前的测试日志中获取）
TEST_MESSAGE_ID = 1822260651  # 群聊图片消息


async def test_http_connection() -> bool:
    """测试HTTP API基本连接"""
    print("=== 测试HTTP API基本连接 ===")
    
    headers = {
        'Content-Type': 'application/json',
    }
    if HTTP_API_ACCESS_TOKEN:
        headers['Authorization'] = f'Bearer {HTTP_API_ACCESS_TOKEN}'
    
    print(f"目标URL: {HTTP_API_BASE_URL}")
    print(f"使用Token: {'是' if HTTP_API_ACCESS_TOKEN else '否'}")
    
    timeout = aiohttp.ClientTimeout(total=HTTP_API_TIMEOUT)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            # 首先尝试访问根路径或状态接口
            status_url = f"{HTTP_API_BASE_URL.rstrip('/')}/get_status"
            print(f"尝试访问: {status_url}")
            
            async with session.post(status_url, json={}) as response:
                print(f"HTTP状态码: {response.status}")
                response_text = await response.text()
                
                if response.status == 200:
                    try:
                        result = json.loads(response_text)
                        print(f"连接成功！响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                        return True
                    except json.JSONDecodeError:
                        print(f"响应不是JSON: {response_text}")
                        # 即使是普通文本响应也视为连接成功
                        return True
                else:
                    print(f"连接失败，状态码: {response.status}")
                    print(f"响应内容: {response_text}")
                    return False
                    
    except aiohttp.ClientConnectorError as e:
        print(f"连接错误: {e}")
        print("请确保NapCat HTTP服务正在运行 (端口 3001)")
        return False
    except asyncio.TimeoutError:
        print(f"请求超时 (超时设置: {HTTP_API_TIMEOUT}秒)")
        return False
    except Exception as e:
        print(f"其他错误: {e}")
        return False


async def test_get_msg_api(message_id: int) -> bool:
    """测试get_msg API"""
    print(f"\n=== 测试get_msg API (消息ID: {message_id}) ===")
    
    headers = {
        'Content-Type': 'application/json',
    }
    if HTTP_API_ACCESS_TOKEN:
        headers['Authorization'] = f'Bearer {HTTP_API_ACCESS_TOKEN}'
    
    timeout = aiohttp.ClientTimeout(total=HTTP_API_TIMEOUT)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            url = f"{HTTP_API_BASE_URL.rstrip('/')}/get_msg"
            data = {
                "message_id": message_id
            }
            
            print(f"发送请求到: {url}")
            print(f"请求数据: {json.dumps(data, ensure_ascii=False)}")
            
            async with session.post(url, json=data) as response:
                print(f"HTTP状态码: {response.status}")
                response_text = await response.text()
                
                if response.status == 200:
                    try:
                        result = json.loads(response_text)
                        print(f"请求成功！响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                        
                        # 检查响应格式
                        if result.get('status') == 'ok':
                            data = result.get('data', result)
                            print(f"\n✅ get_msg API测试成功！")
                            print(f"消息ID: {data.get('message_id')}")
                            print(f"消息类型: {data.get('message_type')}")
                            print(f"发送者: {data.get('sender', {}).get('user_id')}")
                            if 'message' in data:
                                print(f"消息内容预览: {str(data.get('message'))[:200]}...")
                            return True
                        else:
                            print(f"❌ API返回错误状态: {result.get('status')}")
                            print(f"错误信息: {result.get('message')}")
                            return False
                    except json.JSONDecodeError as e:
                        print(f"❌ 响应JSON解析失败: {e}")
                        print(f"原始响应: {response_text}")
                        return False
                else:
                    print(f"❌ HTTP请求失败，状态码: {response.status}")
                    print(f"响应内容: {response_text}")
                    return False
                    
    except aiohttp.ClientConnectorError as e:
        print(f"❌ 连接错误: {e}")
        return False
    except asyncio.TimeoutError:
        print(f"❌ 请求超时 (超时设置: {HTTP_API_TIMEOUT}秒)")
        return False
    except Exception as e:
        print(f"❌ 其他错误: {e}")
        return False


async def test_napcat_http_client():
    """测试我们创建的NapCatHttpClient类"""
    print("\n=== 测试NapCatHttpClient类 ===")
    
    try:
        from src.core.napcat_http_client import NapCatHttpClient
        
        async with NapCatHttpClient() as client:
            # 测试连接
            print("1. 测试连接...")
            connected = await client.test_connection()
            if not connected:
                print("❌ 连接测试失败")
                return False
            
            print("✅ 连接测试成功")
            
            # 测试get_msg
            print(f"\n2. 测试get_msg (消息ID: {TEST_MESSAGE_ID})...")
            result = await client.get_msg(TEST_MESSAGE_ID)
            if result:
                print(f"✅ get_msg测试成功")
                print(f"结果预览: {json.dumps(result, ensure_ascii=False)[:500]}...")
                return True
            else:
                print("❌ get_msg测试失败")
                return False
                
    except ImportError as e:
        print(f"❌ 无法导入NapCatHttpClient: {e}")
        return False
    except Exception as e:
        print(f"❌ NapCatHttpClient测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """运行所有测试"""
    print("开始NapCat HTTP API测试...")
    print(f"配置: URL={HTTP_API_BASE_URL}, Token={'已设置' if HTTP_API_ACCESS_TOKEN else '未设置'}")
    print("=" * 60)
    
    results = {}
    
    # 测试1: 基本HTTP连接
    results['basic_connection'] = await test_http_connection()
    
    # 测试2: get_msg API
    if results['basic_connection']:
        results['get_msg_api'] = await test_get_msg_api(TEST_MESSAGE_ID)
    else:
        print("\n⚠️  基本连接失败，跳过get_msg测试")
        results['get_msg_api'] = False
    
    # 测试3: NapCatHttpClient类
    if results['basic_connection']:
        results['napcat_client'] = await test_napcat_http_client()
    else:
        print("\n⚠️  基本连接失败，跳过NapCatHttpClient测试")
        results['napcat_client'] = False
    
    # 输出总结
    print("\n" + "=" * 60)
    print("测试结果总结:")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name:20} {status}")
    
    total_passed = sum(1 for passed in results.values() if passed)
    total_tests = len(results)
    
    print(f"\n总计: {total_passed}/{total_tests} 个测试通过")
    
    if total_passed == total_tests:
        print("\n🎉 所有测试通过！HTTP API可用")
        return True
    else:
        print("\n⚠️  部分测试失败，请检查NapCat配置和网络连接")
        return False


if __name__ == '__main__':
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)