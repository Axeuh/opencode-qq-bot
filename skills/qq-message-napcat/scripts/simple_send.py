#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple file sender using NapcatWebSocketClient"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qq_tools_ws import NapcatWebSocketClient

async def send_file():
    client = NapcatWebSocketClient(
        server="ws://localhost:3002",
        token="CqC5dDMXWGUu6NVh",
        verbose=True
    )
    
    print("Connecting...")
    await client.connect()
    print("Connected!")
    
    # Wait a bit for connection to stabilize
    await asyncio.sleep(1)
    
    # Send file
    print("Sending file...")
    result = await client.send_file_message(
        target_id="813729523",
        file_path="D:/opencode/test_file.txt",
        name="test_file.txt",
        message_type="group",
        use_base64=True
    )
    
    print(f"Result: {result}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(send_file())