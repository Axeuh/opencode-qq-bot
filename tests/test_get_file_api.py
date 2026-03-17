#!/usr/bin/env python3
"""测试 get_file API"""

import asyncio
import json
import time
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.core.napcat_http_client import NapCatHttpClient

# 测试用的 file_id (合并转发消息中的文件)
TEST_FILE_ID = "d476b781f95b09df4de35ea1c783c368_33f34e48-1e7c-11f1-b89f-b98fbb8f4975"


async def test_get_file():
    print("=" * 60)
    print("测试 get_file API")
    print("=" * 60)
    print(f"file_id: {TEST_FILE_ID}")
    print()
    
    async with NapCatHttpClient() as client:
        # 测试连接
        print("1. 测试 HTTP API 连接...")
        if await client.test_connection():
            print("   连接成功")
        else:
            print("   连接失败")
            return
        
        # 测试 get_file
        print(f"\n2. 测试 get_file API...")
        start = time.time()
        print(f"   开始时间: {time.strftime('%H:%M:%S')}")
        
        result = await client.get_file(TEST_FILE_ID)
        
        elapsed = time.time() - start
        print(f"   耗时: {elapsed:.1f}秒")
        print()
        
        if result:
            print("   成功!")
            print("   返回数据:")
            print("-" * 50)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("-" * 50)
            
            # 保存结果
            output_file = os.path.join(project_root, "docs", "get_file_result.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n   结果已保存到: {output_file}")
        else:
            print("   失败或超时")


if __name__ == "__main__":
    asyncio.run(test_get_file())