#!/usr/bin/env python3
"""
测试 HTTP API 文件下载
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.core.napcat_http_client import NapCatHttpClient


async def test_http_file_api():
    """测试 HTTP API 文件下载"""
    
    # 测试文件 ID（使用之前的文件）
    file_id = "d476b781f95b09df4de35ea1c783c368_c134e856-1e69-11f1-9bc8-df8d9abec2e5"
    
    print("=" * 60)
    print("测试 HTTP API 文件下载")
    print("=" * 60)
    
    async with NapCatHttpClient() as client:
        # 测试连接
        print("\n1. 测试 HTTP API 连接...")
        if await client.test_connection():
            print("   HTTP API 连接成功")
        else:
            print("   HTTP API 连接失败")
            return
        
        # 测试 get_file
        print(f"\n2. 测试 get_file API...")
        print(f"   file_id: {file_id}")
        
        file_info = await client.get_file(file_id)
        
        if file_info:
            print("   get_file 成功!")
            print(f"   文件路径: {file_info.get('file')}")
            print(f"   文件名: {file_info.get('file_name')}")
            print(f"   文件大小: {file_info.get('file_size')}")
        else:
            print("   get_file 失败")


if __name__ == "__main__":
    asyncio.run(test_http_file_api())