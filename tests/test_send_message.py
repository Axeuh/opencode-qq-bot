#!/usr/bin/env python3
"""测试发送消息到 OpenCode"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.opencode import OpenCodeClient


async def test_send_with_defaults():
    """测试使用默认参数发送消息"""
    client = OpenCodeClient()
    
    try:
        # 使用现有会话
        session_id = "ses_2e044af11ffe0oMkJx6BnKnJnu"
        
        print(f"测试会话: {session_id}")
        print(f"默认 agent: {client.default_agent}")
        print(f"默认 model: {client.default_model}")
        print(f"默认 provider: {client.default_provider}")
        print(f"默认 directory: {client.directory}")
        print()
        
        # 测试1: 不传任何参数
        print("=== 测试1: 不传递 agent/model/provider ===")
        result, error = await client.send_message(
            message_text="测试消息1: 使用默认参数",
            session_id=session_id
        )
        if error:
            print(f"失败: {error}")
        else:
            print(f"成功: {result}")
        print()
        
        # 测试2: 只传 directory
        print("=== 测试2: 只传递 directory ===")
        result, error = await client.send_message(
            message_text="测试消息2: 只传递 directory",
            session_id=session_id,
            directory="C:\\"
        )
        if error:
            print(f"失败: {error}")
        else:
            print(f"成功: {result}")
        print()
        
        # 测试3: 传递完整参数
        print("=== 测试3: 传递完整参数 ===")
        result, error = await client.send_message(
            message_text="测试消息3: 完整参数",
            session_id=session_id,
            directory="C:\\",
            agent="Sisyphus (Ultraworker)",
            model="alibaba-coding-plan-cn/qwen3.5-plus"
        )
        if error:
            print(f"失败: {error}")
        else:
            print(f"成功: {result}")
        
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_send_with_defaults())