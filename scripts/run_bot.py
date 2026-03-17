#!/usr/bin/env python3
"""
QQ机器人启动脚本
直接启动Python客户端
"""

import os
import sys
import asyncio
import subprocess
import threading
import signal
import time
import atexit
from datetime import datetime

# 添加项目根目录到Python路径，以便导入模块
import sys
import os
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_path)

# 加载配置
try:
    from src.utils import config
    OPENCODE_PORT = config.OPENCODE_PORT
except ImportError:
    OPENCODE_PORT = 4091  # 默认端口

# 调试信息
print(f"调试: __file__ = {__file__}")
print(f"调试: 脚本目录 = {os.path.dirname(__file__)}")
print(f"调试: 根路径 = {root_path}")
print(f"调试: OpenCode 端口 = {OPENCODE_PORT}")

class OpenCodeWebMonitor:
    """OpenCode Web服务监控器（简化版，专门用于端口4091）"""
    
    def __init__(self, port=4091):
        """初始化监控器"""
        self.port = port
        self.process = None
        self.running = True
        self.restart_count = 0
        self.max_restart_attempts = 1000  # 最大重启次数
        self.restart_delay = 5  # 重启延迟（秒）
        
        # 设置信号处理
        
    def signal_handler(self, signum, frame):
        """处理终止信号"""
        self.log(f"收到终止信号 {signum}，正在关闭OpenCode监控...")
        self.running = False
        if self.process:
            self.process.terminate()
            
    
    def cleanup(self):
        """清理资源，确保子进程被终止"""
        if hasattr(self, "_cleaned_up") and self._cleaned_up:
            return
        self._cleaned_up = True
        self.running = False
        if self.process:
            self.process.terminate()
            self.process = None
    
    def log(self, message):
        """输出日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [OpenCode监控] {message}")
        
    def is_port_in_use(self, port):
        """检查端口是否被占用"""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', port))
                return result == 0
        except:
            return False
    
    def find_available_port(self, start_port, max_attempts=10):
        """查找可用的端口，从start_port开始尝试"""
        import socket
        for offset in range(max_attempts):
            port = start_port + offset
            if not self.is_port_in_use(port):
                return port
        return None  # 没有找到可用端口
    
    def run_command(self):
        """运行 opencode web 命令"""
        # 检查端口是否被占用，如果是则尝试其他端口
        # 检查端口是否被占用，如果被占用则报错并退出
        current_port = self.port
        if self.is_port_in_use(current_port):
            self.log(f"错误: 端口 {current_port} 已被占用，无法启动OpenCode服务")
            self.log(f"请检查是否有其他OpenCode实例在运行，或修改配置文件中的端口")
            return -3  # 特殊退出码表示端口被占用
        
        cmd = ["opencode", "web", "--port", str(current_port)]
        self.log(f"启动命令: {' '.join(cmd)}")
        
        try:
            # 启动进程，设置UTF-8编码避免解码错误
            env = os.environ.copy()
            # 设置环境变量确保使用UTF-8编码
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                # 使用二进制模式读取，然后手动解码
                universal_newlines=False,  # 禁用自动文本模式
                env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )
            
            # 实时输出日志，过滤掉密码警告
            if self.process and self.process.stdout:
                while True:
                    # 读取二进制数据
                    line_bytes = self.process.stdout.readline()
                    if not line_bytes:
                        break
                    
                    try:
                        # 尝试UTF-8解码
                        line = line_bytes.decode('utf-8', errors='ignore')
                    except UnicodeDecodeError:
                        # 如果UTF-8失败，尝试GBK
                        try:
                            line = line_bytes.decode('gbk', errors='ignore')
                        except UnicodeDecodeError:
                            # 如果都失败，使用replace错误处理
                            line = line_bytes.decode('utf-8', errors='replace')
                    
                    if line:
                        # 忽略密码警告信息
                        if "OPENCODE_SERVER_PASSWORD is not set" in line or "server is unsecured" in line:
                            continue
                        
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        print(f"[{timestamp}] [OpenCode服务] {line.rstrip()}")
                    
            # 等待进程结束
            return_code = self.process.wait() if self.process else -2
            self.process = None
            
            return return_code
            
        except FileNotFoundError:
            self.log(f"错误: 找不到 opencode 命令")
            self.log(f"opencode 应该安装在: {self.find_opencode_path()}")
            return -1
        except Exception as e:
            self.log(f"运行命令时发生异常: {e}")
            import traceback
            self.log(f"异常详情: {traceback.format_exc()}")
            return -2
    
    def find_opencode_path(self):
        """查找 opencode 命令路径"""
        try:
            # Windows系统使用 where 命令
            if sys.platform == "win32":
                result = subprocess.run(['where', 'opencode'], capture_output=True, text=True, shell=True)
            else:
                result = subprocess.run(['which', 'opencode'], capture_output=True, text=True)
            
            if result.stdout:
                return result.stdout.strip()
        except:
            pass
        return "未找到，请确保 opencode 已安装并添加到 PATH"
            
    def start(self):
        """启动监控循环"""
        self.log(f"=== OpenCode Web 监控服务启动 ===")
        self.log(f"端口: {self.port}")
        self.log(f"工作目录: {os.getcwd()}")
        self.log(f"忽略密码警告信息")
        self.log(f"按 Ctrl+C 停止服务")
        
        while self.running and self.restart_count < self.max_restart_attempts:
            return_code = self.run_command()
            
            if return_code == 0:
                self.log(f"程序正常退出，退出码: {return_code}")
                break
            elif return_code == -3:  # 端口被占用
                self.log(f"端口被占用，停止监控")
                break
            elif return_code == -1:  # opencode命令未找到
                self.log(f"致命错误: 找不到 opencode 命令，停止监控")
                break
            else:
                self.restart_count += 1
                self.log(f"程序异常退出，退出码: {return_code}")
                self.log(f"将在 {self.restart_delay} 秒后重启 (第 {self.restart_count} 次重启)")
                
                # 等待一段时间后重启
                for i in range(self.restart_delay):
                    if not self.running:
                        break
                    time.sleep(1)
                    
        if self.restart_count >= self.max_restart_attempts:
            self.log(f"达到最大重启次数 ({self.max_restart_attempts})，停止监控")
            
        self.log("=== OpenCode Web 监控服务停止 ===")


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
    # 切换到项目根目录，确保相对路径正确
    root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    os.chdir(root_path)
    print(f"工作目录: {os.getcwd()}")
    
    # 创建必要的目录结构
    required_dirs = ['logs', 'data', 'downloads']
    for dir_name in required_dirs:
        os.makedirs(dir_name, exist_ok=True)
        print(f"确保目录存在: {dir_name}")
    
    # 启动OpenCode Web服务监控（使用配置端口）
    print("=" * 50)
    print(f"      启动OpenCode Web服务监控 (端口{OPENCODE_PORT})")
    print("=" * 50)
    
    monitor = OpenCodeWebMonitor(port=OPENCODE_PORT)
    monitor_thread = threading.Thread(target=monitor.start)
    monitor_thread.daemon = False  # 非守护线程，我们需要控制它的停止
    monitor_thread.start()
    # 注册退出处理函数，确保程序退出时清理OpenCode进程
    def cleanup_opencode():
        """清理OpenCode进程"""
        monitor.cleanup()
        # 等待监控线程结束（最多3秒）
        monitor_thread.join(timeout=3)
    atexit.register(cleanup_opencode)

    
    # 等待片刻确保 OpenCode 服务启动
    time.sleep(3)
    
    # 检查依赖
    missing = check_dependencies()
    if missing:
        print(f"缺少 Python 依赖包：{', '.join(missing)}")
        print("请先运行：pip install aiohttp")
        sys.exit(1)
    
    # 启动 OneBot 客户端
    try:
        from src.core.onebot_client import main as client_main
        asyncio.run(client_main())
        
    except KeyboardInterrupt:
        print("正在停止 OpenCode 监控...")
        # 使用 cleanup 方法清理 OpenCode 进程
        monitor.cleanup()
        # 等待监控线程结束（最多 5 秒）
        monitor_thread.join(timeout=5)
        sys.exit(0)
if __name__ == '__main__':
    main()