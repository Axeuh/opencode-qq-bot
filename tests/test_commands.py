#!/usr/bin/env python3
"""
命令功能测试脚本
通过调试接口测试所有机器人命令
"""

import asyncio
import json
import logging
import sys
import time
from typing import Dict, List, Tuple

# 添加项目根目录到路径
sys.path.insert(0, ".")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CommandTester:
    """命令测试器"""
    
    def __init__(self):
        self.debug_interface = None
        self.results = []
    
    async def initialize(self):
        """初始化调试接口"""
        try:
            from debug_interface import DebugInterface
            self.debug_interface = DebugInterface()
            success = await self.debug_interface.initialize()
            if not success:
                logger.error("❌ 初始化调试接口失败")
                return False
            logger.info("✅ 调试接口初始化成功")
            return True
        except Exception as e:
            logger.error(f"❌ 导入调试接口失败: {e}")
            return False
    
    def create_message(self, command: str) -> Dict:
        """创建命令消息JSON
        
        Args:
            command: 命令字符串，如 "/help"
        """
        return {
            "post_type": "message",
            "message_type": "private",
            "user_id": 123456789,
            "raw_message": command,
            "message": [
                {"type": "text", "data": {"text": command}}
            ],
            "self_id": 3938121220,
            "time": int(time.time()),
            "message_id": int(time.time() * 1000) % 1000000,
            "font": 0,
            "sender": {
                "user_id": 123456789,
                "nickname": "命令测试用户",
                "card": ""
            }
        }
    
    async def test_command(self, command: str, description: str) -> Tuple[bool, str]:
        """测试单个命令
        
        Args:
            command: 命令字符串
            description: 命令描述
            
        Returns:
            (是否成功, 结果说明)
        """
        if not self.debug_interface:
            return False, "调试接口未初始化"
        
        try:
            logger.info(f"🧪 测试命令: {command} ({description})")
            message = self.create_message(command)
            
            success = await self.debug_interface.send_test_message(message)
            
            if success:
                return True, "✅ 命令发送成功"
            else:
                return False, "❌ 命令发送失败"
                
        except Exception as e:
            logger.error(f"❌ 测试命令 {command} 时出错: {e}")
            return False, f"❌ 测试出错: {str(e)}"
    
    async def run_tests(self):
        """运行所有命令测试"""
        if not await self.initialize():
            logger.error("❌ 初始化失败，无法继续测试")
            return
        
        # 定义要测试的命令
        test_cases = [
            ("/help", "帮助命令"),
            ("/new", "创建新会话"),
            ("/session ses_test123", "切换会话"),
            ("/agents", "列出智能体"),
            ("/model deepseek/deepseek-reasoner", "切换模型"),
            ("/stop", "停止当前会话"),
            ("/undo", "撤销最后一条消息"),
            ("/redo", "恢复所有撤销消息"),
            ("/reload", "重新加载配置"),
            ("/reload restart", "重启机器人"),
        ]
        
        logger.info("=" * 60)
        logger.info("🚀 开始命令功能测试")
        logger.info(f"共 {len(test_cases)} 个测试用例")
        logger.info("=" * 60)
        
        # 逐个测试命令
        for command, description in test_cases:
            success, result = await self.test_command(command, description)
            self.results.append({
                "command": command,
                "description": description,
                "success": success,
                "result": result
            })
            
            # 等待片刻，避免处理冲突
            await asyncio.sleep(1)
        
        # 生成测试报告
        self.generate_report()
    
    def generate_report(self):
        """生成测试报告"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["success"])
        failed = total - passed
        
        logger.info("=" * 60)
        logger.info("📊 命令功能测试报告")
        logger.info("=" * 60)
        logger.info(f"总计测试: {total}")
        logger.info(f"✅ 通过: {passed}")
        logger.info(f"❌ 失败: {failed}")
        logger.info(f"📈 成功率: {passed/total*100:.1f}%")
        logger.info("=" * 60)
        
        # 详细结果
        for i, result in enumerate(self.results, 1):
            status = "✅" if result["success"] else "❌"
            logger.info(f"{i:2d}. {status} {result['command']:25} - {result['description']:15} - {result['result']}")
        
        # 总结
        if failed == 0:
            logger.info("🎉 所有命令测试通过！")
        else:
            logger.warning(f"⚠️  有 {failed} 个命令测试失败")
            # 列出失败的命令
            failed_commands = [r["command"] for r in self.results if not r["success"]]
            logger.warning(f"失败的命令: {', '.join(failed_commands)}")


async def main():
    """主函数"""
    logger.info("🔧 命令功能测试脚本")
    logger.info("版本: 1.0")
    logger.info("=" * 60)
    
    tester = CommandTester()
    await tester.run_tests()


if __name__ == "__main__":
    asyncio.run(main())