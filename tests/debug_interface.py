#!/usr/bin/env python3
"""
QQ机器人调试接口
用于通过命令行发送测试消息到机器人
支持直接传递JSON字符串或从文件读取JSON
"""

import sys
import os
import json
import asyncio
import logging
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DebugInterface:
    """调试接口类"""
    
    def __init__(self):
        """初始化调试接口"""
        self.client = None
        
    async def initialize(self):
        """初始化机器人客户端"""
        try:
            from src.core.onebot_client import OneBotClient
            self.client = OneBotClient()
            logger.info("✅ 机器人客户端初始化成功")
            return True
        except Exception as e:
            logger.error(f"❌ 初始化机器人客户端失败: {e}")
            return False
    
    async def send_test_message(self, message_data: Dict[str, Any]):
        """发送测试消息到机器人
        
        Args:
            message_data: 消息JSON数据，格式与NapCat WebSocket消息相同
        """
        if not self.client:
            logger.error("❌ 机器人客户端未初始化")
            return False
        
        try:
            # 提取关键信息
            post_type = message_data.get("post_type")
            message_type = message_data.get("message_type")
            user_id = message_data.get("user_id")
            group_id = message_data.get("group_id")
            raw_message = message_data.get("raw_message", "")
            message = message_data.get("message", [])
            
            logger.info(f"📤 发送测试消息:")
            logger.info(f"   消息类型: {post_type}/{message_type}")
            logger.info(f"   用户ID: {user_id}")
            logger.info(f"   群组ID: {group_id}")
            logger.info(f"   原始消息: {raw_message}")
            
            # 根据消息类型调用相应的处理器
            if post_type == "message":
                if message_type in ["private", "group"]:
                    # 调用消息路由器
                    if hasattr(self.client, 'message_router') and self.client.message_router:
                        await self.client.message_router.route_message(message_data)
                        logger.info(f"✅ {message_type}消息已路由")
                        return True
                    else:
                        logger.error("❌ 消息路由器不可用")
                        return False
                else:
                    logger.error(f"❌ 不支持的消息类型: {message_type}")
                    return False
            else:
                logger.error(f"❌ 不支持的post_type: {post_type}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 发送测试消息失败: {e}")
            import traceback
            traceback.print_exc()
            return False

def print_usage():
    """打印使用方法"""
    print("QQ机器人调试接口 - 命令行模式")
    print("=" * 60)
    print("使用方法:")
    print("  python debug_interface.py <消息JSON>")
    print("  python debug_interface.py --file <JSON文件路径>")
    print()
    print("示例:")
    print('  python debug_interface.py \'{"post_type": "message", "message_type": "private", "user_id": 123456789, "raw_message": "测试消息"}\'')
    print("  python debug_interface.py --file test_message.json")
    print()
    print("消息JSON格式:")
    print("  {")
    print('    "post_type": "message",')
    print('    "message_type": "private" (或 "group"),')
    print('    "user_id": 用户QQ号,')
    print('    "raw_message": "消息内容",')
    print('    "self_id": 机器人QQ号 (3938121220),')
    print('    "message_id": 消息ID,')
    print('    "sender": {"user_id": 用户QQ号, "nickname": "用户昵称"}')
    print("  }")

def parse_message_json(input_str: str) -> Dict[str, Any]:
    """解析消息JSON
    
    支持直接JSON字符串或文件路径
    """
    # 尝试作为文件路径解析
    if os.path.exists(input_str):
        try:
            with open(input_str, 'r', encoding='utf-8') as f:
                content = f.read()
            return json.loads(content)
        except Exception as e:
            logger.error(f"❌ 读取文件失败: {e}")
            sys.exit(1)
    
    # 尝试作为JSON字符串解析
    try:
        return json.loads(input_str)
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON解析失败: {e}")
        logger.error(f"输入不是有效的JSON，也不是存在的文件路径: {input_str}")
        sys.exit(1)

async def main_async():
    """主异步函数"""
    if len(sys.argv) < 2:
        print_usage()
        return
    
    # 处理命令行参数
    if sys.argv[1] == "--file" and len(sys.argv) >= 3:
        json_file = sys.argv[2]
        message_data = parse_message_json(json_file)
    elif sys.argv[1] in ["-h", "--help", "help"]:
        print_usage()
        return
    else:
        # 将所有剩余参数合并为JSON字符串
        json_str = " ".join(sys.argv[1:])
        message_data = parse_message_json(json_str)
    
    # 初始化调试接口并发送消息
    debug = DebugInterface()
    
    logger.info("🔄 正在初始化机器人客户端...")
    if not await debug.initialize():
        logger.error("❌ 初始化失败")
        sys.exit(1)
    
    logger.info("✅ 机器人客户端初始化成功")
    
    # 发送消息
    success = await debug.send_test_message(message_data)
    
    if success:
        logger.info("✅ 消息发送成功")
    else:
        logger.error("❌ 消息发送失败")
        sys.exit(1)
    
    # 等待片刻，让消息处理完成
    await asyncio.sleep(1)

def main():
    """主函数"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("👋 用户中断操作")
    except Exception as e:
        logger.error(f"❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()