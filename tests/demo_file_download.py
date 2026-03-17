#!/usr/bin/env python3
"""
NapCat 文件下载演示脚本
演示如何使用 get_file API 获取文件并下载

使用方法:
python demo_file_download.py [--file-id FILE_ID] [--message-id MESSAGE_ID]
"""

import argparse
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

# NapCat 配置
NAPCAT_WS_URL = "ws://localhost:3002"
NAPCAT_HTTP_URL = "http://localhost:3001"
WS_ACCESS_TOKEN = "CqC5dDMXWGUu6NVh"
HTTP_ACCESS_TOKEN = "fZvJ-zo_TzyAHOoI"

# 网络共享路径（WSL NapCat -> Windows）
# WSL路径 /root/.config/QQ/NapCat/temp 映射到 Windows
NAPCAT_TEMP_SHARE = r"\\172.27.213.195\wsl-root\root\.config\QQ\NapCat\temp"


class NapCatFileDownloader:
    """NapCat 文件下载器"""
    
    def __init__(self):
        self.ws = None
        
    async def connect(self) -> bool:
        """连接 WebSocket"""
        try:
            import websockets
            
            headers = {}
            if WS_ACCESS_TOKEN:
                headers["Authorization"] = f"Bearer {WS_ACCESS_TOKEN}"
            
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
    
    async def close(self):
        """关闭连接"""
        if self.ws:
            await self.ws.close()
            logger.info("WebSocket 连接已关闭")
    
    async def get_file_info(self, file_id: str) -> Optional[Dict]:
        """获取文件信息
        
        Args:
            file_id: 文件ID
            
        Returns:
            文件信息字典，包含:
            - file: 文件路径（NapCat服务器上）
            - url: 下载URL（可能是相对路径）
            - file_size: 文件大小
            - file_name: 文件名
        """
        try:
            echo_id = f"get_file_{datetime.now().timestamp()}"
            request = {
                "action": "get_file",
                "params": {"file_id": file_id},
                "echo": echo_id
            }
            
            logger.info(f"发送 get_file 请求: file_id={file_id}")
            await self.ws.send(json.dumps(request))
            
            # 等待响应（可能需要多次接收）
            max_attempts = 5
            for _ in range(max_attempts):
                response = await asyncio.wait_for(self.ws.recv(), timeout=30)
                result = json.loads(response)
                
                logger.debug(f"收到响应: {json.dumps(result, ensure_ascii=False)[:200]}")
                
                # 检查是否是我们请求的响应
                if result.get("echo", "").startswith("get_file_"):
                    if result.get("status") == "ok":
                        data = result.get("data")
                        logger.info(f"get_file 成功: {json.dumps(data, ensure_ascii=False)[:200]}")
                        return data
                    else:
                        logger.error(f"get_file 失败: {result.get('message', result)}")
                        return None
                else:
                    logger.debug(f"忽略非目标响应: {result.get('echo')}")
                    continue
            
            logger.error("未收到 get_file 响应")
            return None
                
        except asyncio.TimeoutError:
            logger.error("get_file 请求超时")
            return None
        except Exception as e:
            logger.error(f"获取文件信息异常: {e}")
            return None
    
    async def get_image_info(self, file: str) -> Optional[Dict]:
        """获取图片信息
        
        Args:
            file: 文件名或文件ID
            
        Returns:
            图片信息字典
        """
        try:
            request = {
                "action": "get_image",
                "params": {"file": file},
                "echo": f"get_image_{datetime.now().timestamp()}"
            }
            
            await self.ws.send(json.dumps(request))
            response = await asyncio.wait_for(self.ws.recv(), timeout=30)
            result = json.loads(response)
            
            if result.get("status") == "ok":
                return result.get("data")
            else:
                logger.error(f"获取图片信息失败: {result.get('message')}")
                return None
                
        except Exception as e:
            logger.error(f"获取图片信息异常: {e}")
            return None
    
    def convert_wsl_path_to_windows(self, wsl_path: str) -> str:
        """将 WSL 路径转换为 Windows 网络共享路径
        
        Args:
            wsl_path: WSL 路径，如 /root/.config/QQ/NapCat/temp/file.png
            
        Returns:
            Windows UNC 路径，如 \\\\172.27.213.195\\wsl-root\\root\\.config\\QQ\\NapCat\\temp\\file.png
        """
        if not wsl_path:
            return ""
        
        # 移除开头的 /
        if wsl_path.startswith("/"):
            wsl_path = wsl_path[1:]
        
        # 构建网络共享路径
        # WSL IP: 172.27.213.195
        # 共享名: wsl-root
        windows_path = os.path.join(r"\\172.27.213.195\wsl-root", wsl_path.replace("/", "\\"))
        
        return windows_path
    
    def copy_file_from_share(self, source_path: str, dest_dir: str, filename: str) -> Optional[str]:
        """从网络共享复制文件
        
        Args:
            source_path: 源文件路径（Windows UNC路径）
            dest_dir: 目标目录
            filename: 目标文件名
            
        Returns:
            目标文件路径，或 None（失败）
        """
        import shutil
        
        try:
            # 确保目标目录存在
            os.makedirs(dest_dir, exist_ok=True)
            
            # 目标文件路径
            dest_path = os.path.join(dest_dir, filename)
            
            # 避免文件名冲突
            counter = 1
            original_dest_path = dest_path
            while os.path.exists(dest_path):
                base, ext = os.path.splitext(original_dest_path)
                dest_path = f"{base}_{counter}{ext}"
                counter += 1
            
            # 复制文件
            logger.info(f"正在复制文件: {source_path}")
            logger.info(f"目标路径: {dest_path}")
            
            shutil.copy2(source_path, dest_path)
            
            # 验证文件
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                logger.info(f"文件复制成功: {dest_path} (大小: {os.path.getsize(dest_path)} 字节)")
                return dest_path
            else:
                logger.error("文件复制后验证失败")
                return None
                
        except FileNotFoundError as e:
            logger.error(f"源文件不存在: {source_path}")
            logger.error(f"错误详情: {e}")
            return None
        except PermissionError as e:
            logger.error(f"权限不足，无法访问文件: {source_path}")
            logger.error(f"错误详情: {e}")
            return None
        except Exception as e:
            logger.error(f"复制文件异常: {e}")
            return None
    
    async def download_file(
        self,
        file_id: str,
        dest_dir: str = "downloads",
        user_id: Optional[int] = None
    ) -> Optional[str]:
        """下载文件
        
        Args:
            file_id: 文件ID
            dest_dir: 目标目录
            user_id: 用户ID（可选，用于创建用户子目录）
            
        Returns:
            下载后的本地文件路径，或 None（失败）
        """
        # 1. 获取文件信息
        file_info = await self.get_file_info(file_id)
        
        if not file_info:
            logger.error("无法获取文件信息")
            return None
        
        filename = file_info.get("file_name", "unknown")
        file_size = file_info.get("file_size", "0")
        napcat_path = file_info.get("file", "")
        
        logger.info(f"文件信息:")
        logger.info(f"  文件名: {filename}")
        logger.info(f"  大小: {int(file_size) / (1024*1024):.2f} MB")
        logger.info(f"  NapCat路径: {napcat_path}")
        
        # 2. 转换路径
        windows_path = self.convert_wsl_path_to_windows(napcat_path)
        logger.info(f"  Windows路径: {windows_path}")
        
        # 3. 设置目标目录
        if user_id:
            dest_dir = os.path.join(dest_dir, str(user_id))
        
        # 4. 复制文件
        return self.copy_file_from_share(windows_path, dest_dir, filename)
    
    async def process_file_message(
        self,
        message_data: Dict,
        dest_dir: str = "downloads"
    ) -> Dict[str, Any]:
        """处理文件消息
        
        Args:
            message_data: 文件消息数据（从模拟文件或实际消息获取）
            dest_dir: 目标目录
            
        Returns:
            处理结果字典
        """
        result = {
            "success": False,
            "filename": None,
            "local_path": None,
            "error": None
        }
        
        try:
            # 提取文件信息
            user_id = message_data.get("user_id")
            message = message_data.get("message", [])
            
            if not message or len(message) == 0:
                result["error"] = "消息内容为空"
                return result
            
            file_data = None
            for msg in message:
                if msg.get("type") == "file":
                    file_data = msg.get("data", {})
                    break
            
            if not file_data:
                result["error"] = "未找到文件消息"
                return result
            
            file_id = file_data.get("file_id")
            filename = file_data.get("file", "unknown")
            
            # 下载文件
            local_path = await self.download_file(file_id, dest_dir, user_id)
            
            if local_path:
                result["success"] = True
                result["filename"] = filename
                result["local_path"] = local_path
            else:
                result["error"] = "文件下载失败"
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"处理文件消息异常: {e}")
        
        return result


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="NapCat 文件下载演示")
    parser.add_argument("--file-id", help="文件ID")
    parser.add_argument("--message-id", help="消息ID（用于获取消息详情）")
    parser.add_argument("--dest-dir", default="downloads", help="目标目录")
    parser.add_argument("--test-sample", action="store_true", help="使用示例文件测试")
    parser.add_argument("--test-file", help="指定测试文件路径")
    
    args = parser.parse_args()
    
    # 创建下载器
    downloader = NapCatFileDownloader()
    
    # 连接
    if not await downloader.connect():
        logger.error("无法连接，退出")
        return
    
    try:
        if args.test_file:
            # 使用指定文件测试
            if os.path.exists(args.test_file):
                with open(args.test_file, 'r', encoding='utf-8') as f:
                    sample_message = json.load(f)
                
                logger.info(f"使用指定文件测试: {args.test_file}")
                result = await downloader.process_file_message(sample_message, args.dest_dir)
                
                print("\n" + "=" * 60)
                print("处理结果:")
                print("=" * 60)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                
            else:
                logger.error(f"指定文件不存在: {args.test_file}")
        
        elif args.test_sample:
            # 使用示例文件测试
            sample_file_path = os.path.join(project_root, "模拟接收文件.json")
            if os.path.exists(sample_file_path):
                with open(sample_file_path, 'r', encoding='utf-8') as f:
                    sample_message = json.load(f)
                
                logger.info("使用示例文件测试...")
                result = await downloader.process_file_message(sample_message, args.dest_dir)
                
                print("\n" + "=" * 60)
                print("处理结果:")
                print("=" * 60)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                
            else:
                logger.error(f"示例文件不存在: {sample_file_path}")
        
        elif args.file_id:
            # 直接使用文件ID下载
            local_path = await downloader.download_file(args.file_id, args.dest_dir)
            
            if local_path:
                print(f"\n文件下载成功: {local_path}")
            else:
                print("\n文件下载失败")
        
        else:
            # 显示帮助
            parser.print_help()
            print("\n示例:")
            print("  python demo_file_download.py --test-sample")
            print("  python demo_file_download.py --file-id <FILE_ID>")
    
    finally:
        await downloader.close()


if __name__ == "__main__":
    asyncio.run(main())