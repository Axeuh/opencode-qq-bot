#!/usr/bin/env python3
"""
测试修改后的 FileHandler 类
验证使用 get_file API 获取确切路径的下载功能
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.core.file_handler import FileHandler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# NapCat WebSocket 配置
NAPCAT_WS_URL = "ws://localhost:3002"
WS_ACCESS_TOKEN = "CqC5dDMXWGUu6NVh"


async def create_api_callback():
    """创建 API 回调函数"""
    import websockets
    
    headers = {}
    if WS_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {WS_ACCESS_TOKEN}"
    
    ws = await websockets.connect(
        NAPCAT_WS_URL,
        additional_headers=headers,
        ping_interval=30,
        ping_timeout=10
    )
    
    async def api_callback(action: str, params: Dict[str, Any], timeout: float) -> Optional[Dict[str, Any]]:
        """API 回调函数"""
        import json
        from datetime import datetime
        
        echo_id = f"{action}_{datetime.now().timestamp()}"
        request = {
            "action": action,
            "params": params,
            "echo": echo_id
        }
        
        await ws.send(json.dumps(request))
        
        # 等待匹配 echo 的响应
        while True:
            response = await asyncio.wait_for(ws.recv(), timeout=timeout)
            result = json.loads(response)
            
            # 检查是否是我们的响应
            if result.get("echo", "").startswith(action + "_"):
                logger.info(f"API 响应: {json.dumps(result, ensure_ascii=False)[:500]}")
                return result
            else:
                # 忽略非目标响应（如事件消息）
                logger.debug(f"忽略非目标响应: {result.get('post_type', result.get('echo', 'unknown'))}")
                continue
    
    return ws, api_callback


async def test_file_handler():
    """测试 FileHandler 类"""
    
    # 加载模拟文件消息
    sample_file_path = os.path.join(project_root, "模拟接收文件.json")
    with open(sample_file_path, 'r', encoding='utf-8') as f:
        sample_message = json.load(f)
    
    # 提取文件信息
    file_data = sample_message["message"][0]["data"]
    file_info = {
        "filename": file_data["file"],
        "file_id": file_data["file_id"],
        "file_size": file_data["file_size"],
        "type": "file"
    }
    user_id = sample_message["user_id"]
    
    logger.info("=" * 60)
    logger.info("测试 FileHandler 类 - 使用 get_file API")
    logger.info("=" * 60)
    logger.info(f"文件名: {file_info['filename']}")
    logger.info(f"文件ID: {file_info['file_id']}")
    logger.info(f"用户ID: {user_id}")
    
    # 创建 API 回调
    ws, api_callback = await create_api_callback()
    
    try:
        # 创建 FileHandler 实例
        config = {
            "download_dir": "downloads",
            "napcat_temp_dir": r"\\172.27.213.195\wsl-root\root\.config\QQ\NapCat\temp"
        }
        
        file_handler = FileHandler(
            base_download_dir="downloads",
            config=config,
            api_callback=api_callback
        )
        
        logger.info("\n开始下载文件...")
        
        # 下载文件
        local_path = await file_handler.download_file(
            file_info=file_info,
            group_id=None,
            user_id=user_id
        )
        
        if local_path:
            logger.info("=" * 60)
            logger.info("测试成功!")
            logger.info("=" * 60)
            logger.info(f"本地文件路径: {local_path}")
            logger.info(f"文件大小: {os.path.getsize(local_path)} 字节")
            
            # 验证文件
            if os.path.exists(local_path):
                logger.info("文件验证: 存在且可访问")
            else:
                logger.error("文件验证: 文件不存在")
        else:
            logger.error("=" * 60)
            logger.error("测试失败: 文件下载返回 None")
            logger.error("=" * 60)
    
    finally:
        await ws.close()
        logger.info("WebSocket 连接已关闭")


if __name__ == "__main__":
    asyncio.run(test_file_handler())