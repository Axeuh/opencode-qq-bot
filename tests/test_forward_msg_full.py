#!/usr/bin/env python3
"""
测试合并转发消息完整处理流程
1. 获取转发消息内容
2. 下载文件（使用 file_id + get_file API 或字符匹配）
3. 下载图片（使用 url 字段直接下载）
"""

import asyncio
import json
import os
import sys
import aiohttp

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 修改配置（在导入 NapCatHttpClient 之前）
os.environ['HTTP_API_BASE_URL'] = 'http://localhost:3001'
os.environ['HTTP_API_ACCESS_TOKEN'] = 'fZvJ-zo_TzyAHOoI'

from src.core.napcat_http_client import NapCatHttpClient

# 配置
DOWNLOAD_DIR = os.path.join(project_root, "downloads", "test_forward")


async def get_forward_msg_test(forward_id: str):
    """获取合并转发消息内容"""
    print("=" * 60)
    print("步骤1: 获取合并转发消息内容")
    print("=" * 60)
    
    async with NapCatHttpClient() as client:
        result = await client.get_forward_msg(forward_id)
        
        if result:
            messages = result.get("messages", [])
            print(f"成功获取 {len(messages)} 条消息\n")
            
            # 保存完整响应
            output_file = os.path.join(project_root, "docs", "forward_msg_detail.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"完整响应已保存到: {output_file}\n")
            
            return messages
        else:
            print("获取失败")
            return None


async def download_file_via_api(file_id: str, filename: str):
    """尝试通过 get_file API 下载文件"""
    print(f"\n尝试通过 get_file API 下载文件: {filename}")
    print(f"  file_id: {file_id[:50]}...")
    
    async with NapCatHttpClient() as client:
        result = await client.get_file(file_id)
        
        if result:
            print(f"  get_file 成功!")
            print(f"  返回数据: {json.dumps(result, ensure_ascii=False)[:200]}...")
            return result
        else:
            print(f"  get_file 失败")
            return None


async def download_image_from_url(url: str, filename: str):
    """从 URL 下载图片"""
    print(f"\n从 URL 下载图片: {filename}")
    print(f"  URL: {url[:80]}...")
    
    # 创建下载目录
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    save_path = os.path.join(DOWNLOAD_DIR, filename)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                if response.status == 200:
                    data = await response.read()
                    with open(save_path, 'wb') as f:
                        f.write(data)
                    print(f"  下载成功: {save_path}")
                    print(f"  文件大小: {len(data)} 字节")
                    return save_path
                else:
                    print(f"  HTTP 错误: {response.status}")
                    return None
    except Exception as e:
        print(f"  下载异常: {e}")
        return None


async def download_file_from_napcat_temp(filename: str):
    """从 NapCat 临时目录复制文件"""
    print(f"\n从 NapCat 临时目录查找文件: {filename}")
    
    napcat_temp = r"\\172.27.213.195\wsl-root\root\.config\QQ\NapCat\temp"
    
    try:
        # 列出临时目录文件
        if os.path.exists(napcat_temp):
            files = os.listdir(napcat_temp)
            print(f"  NapCat 临时目录有 {len(files)} 个文件")
            
            # 查找匹配文件
            for f in files:
                if filename.lower() in f.lower() or f.lower() in filename.lower():
                    src_path = os.path.join(napcat_temp, f)
                    dst_path = os.path.join(DOWNLOAD_DIR, filename)
                    
                    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                    
                    import shutil
                    shutil.copy2(src_path, dst_path)
                    print(f"  复制成功: {src_path} -> {dst_path}")
                    return dst_path
            
            print(f"  未找到匹配文件")
            # 显示目录中的部分文件名
            print(f"  目录中的文件示例: {files[:5]}")
        else:
            print(f"  NapCat 临时目录不存在: {napcat_temp}")
    except Exception as e:
        print(f"  复制失败: {e}")
    
    return None


async def process_forward_messages(messages: list):
    """处理转发消息列表"""
    print("\n" + "=" * 60)
    print("步骤2: 处理消息内容")
    print("=" * 60)
    
    if not messages:
        print("没有消息需要处理")
        return
    
    for i, msg in enumerate(messages, 1):
        sender = msg.get("sender", {})
        nickname = sender.get("nickname", "未知")
        message = msg.get("message", [])
        
        print(f"\n消息 {i}: {nickname}")
        
        for item in message:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                data = item.get("data", {})
                
                if item_type == "text":
                    text = data.get("text", "")
                    print(f"  [文本] {text[:50]}{'...' if len(text) > 50 else ''}")
                
                elif item_type == "file":
                    filename = data.get("file", "unknown")
                    file_id = data.get("file_id", "")
                    file_size = data.get("file_size", "0")
                    
                    print(f"  [文件] {filename}")
                    print(f"    - file_id: {file_id[:40]}...")
                    print(f"    - file_size: {file_size} 字节")
                    
                    # 尝试下载
                    if file_id:
                        api_result = await download_file_via_api(file_id, filename)
                        if not api_result:
                            # 回退到临时目录
                            await download_file_from_napcat_temp(filename)
                
                elif item_type == "image":
                    filename = data.get("file", "unknown.png")
                    url = data.get("url", "")
                    file_size = data.get("file_size", "0")
                    
                    print(f"  [图片] {filename}")
                    print(f"    - url: {url[:60]}..." if url else "    - url: 无")
                    print(f"    - file_size: {file_size} 字节")
                    
                    # 使用 URL 下载
                    if url:
                        await download_image_from_url(url, filename)
                    else:
                        print("    没有 URL，无法下载")


async def main():
    """主测试流程"""
    # 使用模拟文件中的 ID
    forward_id = "7616540702540052011"
    
    print(f"测试合并转发消息处理")
    print(f"forward_id: {forward_id}")
    print(f"下载目录: {DOWNLOAD_DIR}")
    
    # 步骤1: 获取转发消息
    messages = await get_forward_msg_test(forward_id)
    
    if messages:
        # 步骤2: 处理消息（下载文件和图片）
        await process_forward_messages(messages)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())