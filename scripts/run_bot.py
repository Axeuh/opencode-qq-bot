#!/usr/bin/env python3
"""
QQ机器人启动脚本
启动主程序，进程管理已集成到 OneBotClient 中
"""

import os
import sys
import asyncio
import time
import atexit

# 添加项目根目录到Python路径，以便导入模块
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_path)

# 切换到项目根目录，确保相对路径正确
os.chdir(root_path)
print(f"工作目录: {os.getcwd()}")

# 创建必要的目录结构
required_dirs = ['logs', 'data', 'downloads']
for dir_name in required_dirs:
    os.makedirs(dir_name, exist_ok=True)
    print(f"确保目录存在: {dir_name}")


def check_napcat_running():
    """检查NapCat是否在运行（简单检查端口3001）"""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', 3001))
        sock.close()
        return result == 0
    except:
        return False


def check_dependencies():
    """检查Python依赖"""
    required_packages = ['aiohttp']
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    return missing


def main():
    """主函数"""
    # 加载配置
    try:
        from src.utils import config
        OPENCODE_PORT = config.OPENCODE_PORT
        BOT_NAME = config.BOT_NAME
    except ImportError:
        OPENCODE_PORT = 4091
        BOT_NAME = "OpenCode Bot"
    
    print("=" * 50)
    print(f"      启动 {BOT_NAME}")
    print(f"      OpenCode 端口: {OPENCODE_PORT}")
    print("=" * 50)
    
    # 检查依赖
    missing = check_dependencies()
    if missing:
        print(f"缺少 Python 依赖包：{', '.join(missing)}")
        print("请先运行：pip install aiohttp")
        sys.exit(1)
    
    # 启动 OneBot 客户端（包含集成的进程管理）
    try:
        from src.core.onebot_client import main as client_main
        asyncio.run(client_main())
        
    except KeyboardInterrupt:
        print("\n程序已退出")
        sys.exit(0)
    except Exception as e:
        print(f"程序错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()