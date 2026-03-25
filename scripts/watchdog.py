#!/usr/bin/env python3
"""
Bot 看门狗脚本
监控 Bot 进程状态，在需要时重启 Bot
"""

import os
import sys
import time
import subprocess
import signal
import json
from datetime import datetime

# 添加项目根目录到Python路径
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_path)

# 配置
BOT_SCRIPT = os.path.join(root_path, "scripts", "run_bot.py")
RESTART_FLAG_FILE = os.path.join(root_path, "data", "bot_restart.flag")
CHECK_INTERVAL = 5  # 检查间隔（秒）


class BotWatchdog:
    """Bot 看门狗"""
    
    def __init__(self):
        self.process = None
        self.running = True
        self.restart_count = 0
        self.max_restart_attempts = 10
        self.restart_delay = 5
        
    def log(self, message):
        """输出日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [Watchdog] {message}")
    
    def check_restart_flag(self):
        """检查重启标志文件"""
        if os.path.exists(RESTART_FLAG_FILE):
            try:
                with open(RESTART_FLAG_FILE, 'r') as f:
                    data = json.load(f)
                self.log(f"检测到重启请求: {data.get('reason', 'unknown')}")
                # 删除标志文件
                os.remove(RESTART_FLAG_FILE)
                return True
            except Exception as e:
                self.log(f"读取重启标志失败: {e}")
        return False
    
    def start_bot(self):
        """启动 Bot 进程"""
        self.log(f"启动 Bot: {BOT_SCRIPT}")
        
        try:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            
            self.process = subprocess.Popen(
                [sys.executable, BOT_SCRIPT],
                env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )
            
            self.log(f"Bot 进程已启动，PID: {self.process.pid}")
            return True
            
        except Exception as e:
            self.log(f"启动 Bot 失败: {e}")
            return False
    
    def stop_bot(self):
        """停止 Bot 进程"""
        if not self.process:
            return
        
        try:
            self.log("正在停止 Bot 进程...")
            
            if sys.platform == "win32":
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(self.process.pid)],
                    capture_output=True,
                    timeout=10
                )
            else:
                try:
                    import os
                    import signal
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
            
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            
            self.process = None
            self.log("Bot 进程已停止")
            
        except Exception as e:
            self.log(f"停止 Bot 失败: {e}")
    
    def restart_bot(self):
        """重启 Bot 进程"""
        self.log("正在重启 Bot...")
        self.stop_bot()
        time.sleep(2)
        return self.start_bot()
    
    def run(self):
        """运行看门狗"""
        self.log("=" * 50)
        self.log("Bot 看门狗已启动")
        self.log(f"Bot 脚本: {BOT_SCRIPT}")
        self.log(f"重启标志文件: {RESTART_FLAG_FILE}")
        self.log("=" * 50)
        
        # 首次启动 Bot
        if not self.start_bot():
            self.log("首次启动 Bot 失败，退出看门狗")
            return
        
        # 监控循环
        while self.running:
            try:
                # 检查进程状态
                if self.process and self.process.poll() is not None:
                    exit_code = self.process.returncode
                    self.log(f"Bot 进程已退出，退出码: {exit_code}")
                    
                    # 检查是否需要重启
                    if self.restart_count < self.max_restart_attempts:
                        self.restart_count += 1
                        self.log(f"将在 {self.restart_delay} 秒后重启 (第 {self.restart_count} 次)")
                        time.sleep(self.restart_delay)
                        
                        if self.start_bot():
                            self.log("Bot 重启成功")
                        else:
                            self.log("Bot 重启失败")
                    else:
                        self.log("达到最大重启次数，停止看门狗")
                        break
                
                # 检查重启标志
                if self.check_restart_flag():
                    self.restart_count = 0  # 重置计数
                    if self.restart_bot():
                        self.log("Bot 已通过 API 请求重启")
                    else:
                        self.log("Bot 重启失败")
                
                time.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                self.log("收到中断信号，停止看门狗")
                self.running = False
            except Exception as e:
                self.log(f"监控异常: {e}")
                time.sleep(CHECK_INTERVAL)
        
        # 清理
        self.stop_bot()
        self.log("看门狗已停止")


def main():
    """主函数"""
    # 确保数据目录存在
    os.makedirs(os.path.dirname(RESTART_FLAG_FILE), exist_ok=True)
    
    watchdog = BotWatchdog()
    watchdog.run()


if __name__ == '__main__':
    main()