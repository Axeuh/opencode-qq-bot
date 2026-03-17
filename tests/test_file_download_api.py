#!/usr/bin/env python3
"""
NapCat 文件下载 API 测试脚本
用于探索和测试 NapCat 的文件下载相关 API

测试目标:
1. get_file API - 获取文件下载信息
2. get_image API - 获取图片下载信息
3. 其他文件相关 API

使用方法:
python test_file_download_api.py
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 测试配置
NAPCAT_WS_URL = "ws://localhost:3002"
NAPCAT_HTTP_URL = "http://localhost:3001"
ACCESS_TOKEN = "CqC5dDMXWGUu6NVh"
HTTP_ACCESS_TOKEN = "fZvJ-zo_TzyAHOoI"

# 模拟文件消息数据
SAMPLE_FILE_MESSAGE = {
    "self_id": 3938121220,
    "user_id": 123456789,
    "time": 1773357502,
    "message_id": 167210474,
    "message_type": "private",
    "sender": {
        "user_id": 123456789,
        "nickname": "Axeuh_nya (不摆了)",
    },
    "message": [
        {
            "type": "file",
            "data": {
                "file": "Gemini_Generated_Image_n27uk2n27uk2n27u.png",
                "file_id": "d476b781f95b09df4de35ea1c783c368_c134e856-1e69-11f1-9bc8-df8d9abec2e5",
                "file_size": "6820021"
            }
        }
    ],
}


class NapCatAPITester:
    """NapCat API 测试器"""
    
    def __init__(self):
        self.ws = None
        self.http_session = None
        self.results = []
        
    async def connect_websocket(self) -> bool:
        """连接 WebSocket"""
        try:
            import websockets
            
            headers = {}
            if ACCESS_TOKEN:
                headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
            
            self.ws = await websockets.connect(
                NAPCAT_WS_URL,
                additional_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )
            logger.info(f"WebSocket 连接成功: {NAPCAT_WS_URL}")
            return True
            
        except Exception as e:
            logger.error(f"WebSocket 连接失败: {e}")
            return False
    
    async def close_websocket(self):
        """关闭 WebSocket 连接"""
        if self.ws:
            await self.ws.close()
            logger.info("WebSocket 连接已关闭")
    
    async def call_api_ws(self, action: str, params: Dict[str, Any], timeout: float = 30) -> Optional[Dict]:
        """通过 WebSocket 调用 API
        
        Args:
            action: API 动作名称
            params: API 参数
            timeout: 超时时间（秒）
            
        Returns:
            API 响应结果
        """
        if not self.ws:
            logger.error("WebSocket 未连接")
            return None
        
        try:
            # 构造请求
            request = {
                "action": action,
                "params": params,
                "echo": f"{action}_{datetime.now().timestamp()}"
            }
            
            logger.info(f"发送 API 请求: {action}")
            logger.debug(f"请求参数: {json.dumps(params, ensure_ascii=False, indent=2)}")
            
            # 发送请求
            await self.ws.send(json.dumps(request))
            
            # 等待响应
            response = await asyncio.wait_for(
                self.ws.recv(),
                timeout=timeout
            )
            
            result = json.loads(response)
            logger.info(f"收到 API 响应: {action}")
            logger.debug(f"响应内容: {json.dumps(result, ensure_ascii=False, indent=2)}")
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"API 调用超时: {action}")
            return None
        except Exception as e:
            logger.error(f"API 调用异常: {action}, 错误: {e}")
            return None
    
    async def call_api_http(self, action: str, params: Dict[str, Any], timeout: float = 30) -> Optional[Dict]:
        """通过 HTTP 调用 API
        
        Args:
            action: API 动作名称
            params: API 参数
            timeout: 超时时间（秒）
            
        Returns:
            API 响应结果
        """
        try:
            import aiohttp
            
            url = f"{NAPCAT_HTTP_URL}/{action}"
            headers = {}
            if HTTP_ACCESS_TOKEN:
                headers["Authorization"] = f"Bearer {HTTP_ACCESS_TOKEN}"
            
            logger.info(f"发送 HTTP API 请求: {action}")
            logger.debug(f"请求参数: {json.dumps(params, ensure_ascii=False, indent=2)}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    result = await response.json()
                    logger.info(f"收到 HTTP API 响应: {action}")
                    logger.debug(f"响应内容: {json.dumps(result, ensure_ascii=False, indent=2)}")
                    
                    return result
                    
        except asyncio.TimeoutError:
            logger.error(f"HTTP API 调用超时: {action}")
            return None
        except Exception as e:
            logger.error(f"HTTP API 调用异常: {action}, 错误: {e}")
            return None
    
    def save_result(self, test_name: str, result: Dict):
        """保存测试结果"""
        self.results.append({
            "test_name": test_name,
            "timestamp": datetime.now().isoformat(),
            "result": result
        })
    
    async def test_get_file_api(self, file_id: str):
        """测试 get_file API
        
        NapCat API 参考:
        - get_file: 获取文件信息，可能包含下载 URL
        - 参数: file_id (文件ID)
        """
        logger.info("=" * 50)
        logger.info("测试 get_file API")
        logger.info("=" * 50)
        
        # 测试 WebSocket 方式
        result_ws = await self.call_api_ws("get_file", {"file_id": file_id})
        if result_ws:
            self.save_result("get_file_ws", result_ws)
        
        # 测试 HTTP 方式
        result_http = await self.call_api_http("get_file", {"file_id": file_id})
        if result_http:
            self.save_result("get_file_http", result_http)
        
        return result_ws or result_http
    
    async def test_get_image_api(self, file: str):
        """测试 get_image API
        
        NapCat API 参考:
        - get_image: 获取图片信息，可能包含下载 URL
        - 参数: file (文件名或文件路径)
        """
        logger.info("=" * 50)
        logger.info("测试 get_image API")
        logger.info("=" * 50)
        
        # 测试 WebSocket 方式
        result_ws = await self.call_api_ws("get_image", {"file": file})
        if result_ws:
            self.save_result("get_image_ws", result_ws)
        
        # 测试 HTTP 方式
        result_http = await self.call_api_http("get_image", {"file": file})
        if result_http:
            self.save_result("get_image_http", result_http)
        
        return result_ws or result_http
    
    async def test_get_file_private(self, file_id: str, user_id: int):
        """测试私聊文件获取
        
        某些实现可能需要指定 user_id
        """
        logger.info("=" * 50)
        logger.info("测试私聊文件获取 (带 user_id)")
        logger.info("=" * 50)
        
        result = await self.call_api_ws("get_file", {
            "file_id": file_id,
            "user_id": user_id
        })
        
        if result:
            self.save_result("get_file_private", result)
        
        return result
    
    async def test_download_file_api(self, file_id: str):
        """测试 download_file API (如果存在)"""
        logger.info("=" * 50)
        logger.info("测试 download_file API")
        logger.info("=" * 50)
        
        result = await self.call_api_ws("download_file", {
            "file_id": file_id
        })
        
        if result:
            self.save_result("download_file", result)
        
        return result
    
    async def test_ocr_image_api(self, image: str):
        """测试 OCR 图片 API (如果存在)"""
        logger.info("=" * 50)
        logger.info("测试 ocr_image API")
        logger.info("=" * 50)
        
        result = await self.call_api_ws("ocr_image", {
            "image": image
        })
        
        if result:
            self.save_result("ocr_image", result)
        
        return result
    
    async def test_get_msg_api(self, message_id: int):
        """测试 get_msg API - 获取消息详情
        
        可以通过消息ID获取完整的消息内容，包括文件信息
        """
        logger.info("=" * 50)
        logger.info("测试 get_msg API")
        logger.info("=" * 50)
        
        result = await self.call_api_ws("get_msg", {
            "message_id": message_id
        })
        
        if result:
            self.save_result("get_msg", result)
        
        return result
    
    async def test_get_status_api(self):
        """测试 get_status API - 获取机器人状态"""
        logger.info("=" * 50)
        logger.info("测试 get_status API")
        logger.info("=" * 50)
        
        result = await self.call_api_ws("get_status", {})
        
        if result:
            self.save_result("get_status", result)
        
        return result
    
    async def test_get_version_info_api(self):
        """测试 get_version_info API - 获取版本信息"""
        logger.info("=" * 50)
        logger.info("测试 get_version_info API")
        logger.info("=" * 50)
        
        result = await self.call_api_ws("get_version_info", {})
        
        if result:
            self.save_result("get_version_info", result)
        
        return result
    
    def generate_report(self) -> str:
        """生成测试报告"""
        report = []
        report.append("=" * 60)
        report.append("NapCat 文件下载 API 测试报告")
        report.append("=" * 60)
        report.append(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"WebSocket URL: {NAPCAT_WS_URL}")
        report.append(f"HTTP URL: {NAPCAT_HTTP_URL}")
        report.append("")
        
        for item in self.results:
            report.append("-" * 60)
            report.append(f"测试名称: {item['test_name']}")
            report.append(f"时间: {item['timestamp']}")
            report.append(f"结果: {json.dumps(item['result'], ensure_ascii=False, indent=2)}")
            report.append("")
        
        report.append("=" * 60)
        report.append("测试完成")
        report.append("=" * 60)
        
        return "\n".join(report)


async def main():
    """主测试函数"""
    logger.info("开始 NapCat 文件下载 API 测试")
    
    # 加载模拟文件消息
    sample_file_path = os.path.join(project_root, "模拟接收文件.json")
    if os.path.exists(sample_file_path):
        with open(sample_file_path, 'r', encoding='utf-8') as f:
            sample_message = json.load(f)
        logger.info(f"已加载模拟文件消息: {sample_file_path}")
    else:
        sample_message = SAMPLE_FILE_MESSAGE
        logger.info("使用内置模拟文件消息")
    
    # 提取文件信息
    file_data = sample_message["message"][0]["data"]
    file_id = file_data["file_id"]
    filename = file_data["file"]
    file_size = int(file_data["file_size"])
    user_id = sample_message["user_id"]
    message_id = sample_message["message_id"]
    
    logger.info(f"文件信息:")
    logger.info(f"  文件名: {filename}")
    logger.info(f"  文件ID: {file_id}")
    logger.info(f"  文件大小: {file_size / (1024*1024):.2f} MB")
    logger.info(f"  用户ID: {user_id}")
    logger.info(f"  消息ID: {message_id}")
    
    # 创建测试器
    tester = NapCatAPITester()
    
    # 连接 WebSocket
    if not await tester.connect_websocket():
        logger.error("无法连接 WebSocket，测试终止")
        return
    
    try:
        # 测试基本状态 API
        await tester.test_get_status_api()
        await tester.test_get_version_info_api()
        
        # 测试消息获取 API
        await tester.test_get_msg_api(message_id)
        
        # 测试文件相关 API
        await tester.test_get_file_api(file_id)
        await tester.test_get_file_private(file_id, user_id)
        
        # 测试图片 API (虽然文件名是 .png，但它被识别为文件)
        await tester.test_get_image_api(file_id)
        await tester.test_get_image_api(filename)
        
        # 测试其他可能的 API
        await tester.test_download_file_api(file_id)
        await tester.test_ocr_image_api(file_id)
        
    finally:
        # 关闭连接
        await tester.close_websocket()
    
    # 生成并保存报告
    report = tester.generate_report()
    
    # 保存到文件
    report_path = os.path.join(project_root, "logs", "file_download_api_test_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(tester.results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n测试报告已保存到: {report_path}")
    
    # 打印报告
    print("\n" + report)
    
    # 分析结果
    print("\n" + "=" * 60)
    print("API 测试结果分析")
    print("=" * 60)
    
    for item in tester.results:
        test_name = item['test_name']
        result = item['result']
        
        if result:
            status = result.get('status', 'unknown')
            retcode = result.get('retcode', 'N/A')
            
            if status == 'ok':
                print(f"✅ {test_name}: 成功 (retcode: {retcode})")
            else:
                print(f"❌ {test_name}: 失败 (retcode: {retcode})")
                if 'message' in result:
                    print(f"   错误信息: {result['message']}")
        else:
            print(f"⚠️ {test_name}: 无响应")


if __name__ == "__main__":
    asyncio.run(main())