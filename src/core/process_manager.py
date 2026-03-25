#!/usr/bin/env python3
"""
进程管理器模块
管理 OpenCode 和 Bot 进程的生命周期
"""

from __future__ import annotations

import aiohttp
import asyncio
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Callable, Awaitable

if TYPE_CHECKING:
    from src.session.session_manager import SessionManager
    from src.opencode.opencode_client import OpenCodeClient

logger = logging.getLogger(__name__)


class ProcessManager:
    """进程管理器
    
    负责:
    - OpenCode 进程的启动/停止/重启
    - 进程健康监控
    - 会话保存与恢复
    - 进程状态报告
    """
    
    def __init__(
        self,
        opencode_port: int = 4091,
        session_manager: Optional["SessionManager"] = None,
        opencode_client: Optional["OpenCodeClient"] = None,
        on_opencode_restart: Optional[Callable[[], Awaitable[None]]] = None,
        on_before_opencode_stop: Optional[Callable[[], Awaitable[None]]] = None,
        pid_file: Optional[str] = None
    ):
        """初始化进程管理器
        
        Args:
            opencode_port: OpenCode 服务端口
            session_manager: 会话管理器实例
            opencode_client: OpenCode 客户端实例
            on_opencode_restart: OpenCode 重启后的回调
            on_before_opencode_stop: OpenCode 停止前的回调（用于停止 SSE 监听等）
            pid_file: OpenCode PID 文件路径
        """
        self.opencode_port = opencode_port
        self.session_manager = session_manager
        self.opencode_client = opencode_client
        self.on_opencode_restart = on_opencode_restart
        self.on_before_opencode_stop = on_before_opencode_stop
        
        # PID 文件路径
        self.pid_file = pid_file or os.path.join(os.getcwd(), "data", "opencode.pid")
        
        # OpenCode 进程
        self.opencode_process: Optional[subprocess.Popen] = None
        self.opencode_running = False
        self.opencode_restart_count = 0
        self.max_restart_attempts = 1000
        self.restart_delay = 5
        
        # 尝试从 PID 文件恢复进程引用
        self._restore_process_from_pid()
        
        # 活跃会话跟踪
        self._active_sessions: Dict[int, str] = {}  # user_id -> session_id
        
        # 状态
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        logger.info(f"进程管理器初始化完成，OpenCode端口: {opencode_port}")
    
    def _restore_process_from_pid(self):
        """从 PID 文件恢复 OpenCode 进程引用"""
        try:
            if os.path.exists(self.pid_file):
                with open(self.pid_file, 'r') as f:
                    data = json.load(f)
                pid = data.get("pid")
                started_at = data.get("started_at")
                
                if pid:
                    # 检查进程是否仍在运行
                    try:
                        if sys.platform == "win32":
                            # Windows: 使用 tasklist 检查进程
                            result = subprocess.run(
                                ['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            if str(pid) in result.stdout:
                                logger.info(f"从 PID 文件恢复 OpenCode 进程引用: PID={pid}")
                                # 创建一个虚拟的 Popen 对象用于管理
                                self._saved_pid = pid
                                self.opencode_running = True
                            else:
                                logger.info(f"PID {pid} 进程已不存在，清理 PID 文件")
                                self._delete_pid_file()
                        else:
                            # Linux/Mac: 使用 kill -0 检查进程
                            os.kill(pid, 0)
                            logger.info(f"从 PID 文件恢复 OpenCode 进程引用: PID={pid}")
                            self._saved_pid = pid
                            self.opencode_running = True
                    except (ProcessLookupError, PermissionError):
                        logger.info(f"PID {pid} 进程已不存在，清理 PID 文件")
                        self._delete_pid_file()
                    except Exception as e:
                        logger.warning(f"检查 PID {pid} 失败: {e}")
        except Exception as e:
            logger.warning(f"从 PID 文件恢复进程引用失败: {e}")
    
    def _save_pid_to_file(self, pid: int):
        """保存 PID 到文件"""
        try:
            os.makedirs(os.path.dirname(self.pid_file), exist_ok=True)
            with open(self.pid_file, 'w') as f:
                json.dump({
                    "pid": pid,
                    "started_at": datetime.now().isoformat(),
                    "port": self.opencode_port
                }, f)
            logger.debug(f"已保存 OpenCode PID 到文件: {pid}")
        except Exception as e:
            logger.warning(f"保存 PID 文件失败: {e}")
    
    def _delete_pid_file(self):
        """删除 PID 文件"""
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
                logger.debug("已删除 PID 文件")
        except Exception as e:
            logger.warning(f"删除 PID 文件失败: {e}")
    
    def find_opencode_executable(self) -> Optional[str]:
        """查找 opencode 可执行文件路径"""
        possible_paths = [
            os.path.expandvars(r"C:\Users\Administrator\AppData\Roaming\npm\opencode.cmd"),
            os.path.expandvars(r"C:\Users\Administrator\AppData\Roaming\npm\opencode"),
            os.path.expanduser(r"AppData\Roaming\npm\opencode.cmd"),
            os.path.expanduser(r"AppData\Roaming\npm\opencode"),
        ]
        
        for path in possible_paths:
            if os.path.isfile(path):
                return path
        
        # 尝试使用 where/which 查找
        try:
            if sys.platform == "win32":
                result = subprocess.run(['where', 'opencode'], capture_output=True, text=True, shell=True)
            else:
                result = subprocess.run(['which', 'opencode'], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split('\n')[0]
        except Exception:
            pass
        
        return None
    
    def is_port_in_use(self, port: int) -> bool:
        """检查端口是否被占用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', port))
                return result == 0
        except Exception:
            return False
    
    async def start_opencode(self, force: bool = False) -> Dict[str, Any]:
        """启动 OpenCode 进程
        
        Args:
            force: 如果端口被占用，是否强制释放
        
        Returns:
            启动结果
        """
        if self.opencode_process and self.opencode_process.poll() is None:
            logger.warning("OpenCode 进程已在运行")
            return {"success": True, "message": "OpenCode already running"}
        
        # 检查端口
        if self.is_port_in_use(self.opencode_port):
            if force:
                logger.warning(f"端口 {self.opencode_port} 被占用，强制释放...")
                await self._kill_process_on_port(self.opencode_port)
                # 等待端口释放
                for i in range(10):
                    await asyncio.sleep(1)
                    if not self.is_port_in_use(self.opencode_port):
                        logger.info(f"端口 {self.opencode_port} 已释放")
                        break
                    logger.info(f"等待端口释放... ({i+1}/10)")
                else:
                    return {
                        "success": False,
                        "error": f"Port {self.opencode_port} still in use after force kill"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Port {self.opencode_port} is already in use"
                }
        
        # 查找可执行文件
        opencode_path = self.find_opencode_executable()
        if opencode_path:
            cmd = [opencode_path, "web", "--port", str(self.opencode_port)]
        else:
            cmd = ["npx", "opencode", "web", "--port", str(self.opencode_port)]
        
        logger.info(f"启动 OpenCode: {' '.join(cmd)}")
        
        try:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            
            self.opencode_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=False,
                env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )
            
            self.opencode_running = True
            logger.info(f"OpenCode 进程已启动，PID: {self.opencode_process.pid}")
            
            # 注意：日志输出已禁用，因为会导致阻塞
            # 如需日志，请直接查看 OpenCode 控制台输出
            
            # 等待端口可用
            for i in range(30):  # 最多等待30秒
                await asyncio.sleep(1)
                if self.is_port_in_use(self.opencode_port):
                    logger.info("OpenCode 端口已就绪，检查 API...")
                    break
            
            # 调用 OpenCode API 确认服务可用
            api_ready = await self._check_opencode_api_ready()
            if api_ready:
                logger.info("OpenCode API 已就绪")
                # 保存 PID 到文件
                self._save_pid_to_file(self.opencode_process.pid)
                return {"success": True, "pid": self.opencode_process.pid}
            else:
                logger.warning("OpenCode API 未就绪，但端口已开放")
                # 保存 PID 到文件
                self._save_pid_to_file(self.opencode_process.pid)
                return {"success": True, "pid": self.opencode_process.pid, "warning": "API check failed"}
            
        except FileNotFoundError:
            return {"success": False, "error": "opencode executable not found"}
        except Exception as e:
            logger.error(f"启动 OpenCode 失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _check_opencode_api_ready(self) -> bool:
        """检查 OpenCode API 是否就绪"""
        try:
            # 使用不需要认证的 /session/status 端点
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://127.0.0.1:{self.opencode_port}/session/status",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        logger.info("OpenCode API 已就绪")
                        return True
                    else:
                        logger.warning(f"OpenCode API 返回状态码: {resp.status}")
                        return False
        except Exception as e:
            logger.debug(f"OpenCode API 检查失败: {e}")
            return False
    
    async def stop_opencode(self) -> Dict[str, Any]:
        """停止 OpenCode 进程
        
        使用缓存的 PID 或进程句柄停止进程
        
        Returns:
            停止结果
        """
        pid_to_kill = None
        
        # 优先使用进程句柄
        if self.opencode_process:
            pid_to_kill = self.opencode_process.pid
        # 否则使用缓存的 PID
        elif hasattr(self, '_saved_pid') and self._saved_pid:
            pid_to_kill = self._saved_pid
        
        # 杀死进程
        if pid_to_kill:
            try:
                logger.info(f"正在停止 OpenCode 进程 PID: {pid_to_kill}...")
                
                if sys.platform == "win32":
                    result = subprocess.run(
                        ['taskkill', '/F', '/T', '/PID', str(pid_to_kill)],
                        capture_output=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        logger.info(f"已杀死进程 {pid_to_kill}")
                    else:
                        logger.warning(f"杀死进程 {pid_to_kill} 失败: {result.stderr.decode()}")
                else:
                    try:
                        os.kill(pid_to_kill, signal.SIGTERM)
                        await asyncio.sleep(2)
                        # 检查是否仍在运行
                        os.kill(pid_to_kill, 0)
                        # 如果还在运行，强制杀死
                        os.kill(pid_to_kill, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                
                # 等待端口释放
                for i in range(5):
                    await asyncio.sleep(1)
                    if not self.is_port_in_use(self.opencode_port):
                        logger.info(f"端口 {self.opencode_port} 已释放")
                        break
                
            except Exception as e:
                logger.error(f"停止 OpenCode 进程失败: {e}")
        
        # 清理状态
        self.opencode_process = None
        self.opencode_running = False
        self._saved_pid = None
        self._delete_pid_file()
        
        logger.info("OpenCode 进程已停止")
        return {"success": True}
    
    async def _kill_process_on_port(self, port: int) -> bool:
        """杀死占用指定端口的进程"""
        try:
            if sys.platform == "win32":
                # Windows: 使用 netstat 找到占用端口的 PID
                result = subprocess.run(
                    ['netstat', '-ano'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                for line in result.stdout.split('\n'):
                    if f':{port}' in line and 'LISTENING' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            logger.info(f"找到占用端口 {port} 的进程 PID: {pid}")
                            
                            # 杀死进程
                            kill_result = subprocess.run(
                                ['taskkill', '/F', '/PID', pid],
                                capture_output=True,
                                timeout=10
                            )
                            
                            if kill_result.returncode == 0:
                                logger.info(f"已杀死进程 {pid}")
                                await asyncio.sleep(2)  # 等待端口释放
                                return True
                            else:
                                logger.warning(f"杀死进程 {pid} 失败")
            else:
                # Linux/Mac: 使用 lsof 或 fuser
                subprocess.run(['fuser', '-k', f'{port}/tcp'], timeout=10)
                await asyncio.sleep(2)
                return True
                
        except Exception as e:
            logger.error(f"杀死占用端口 {port} 的进程失败: {e}")
            
        return False
    
    async def restart_opencode(self) -> Dict[str, Any]:
        """重启 OpenCode 进程
        
        包括:
        1. 保存活跃会话
        2. 停止 SSE 监听
        3. 停止进程
        4. 启动新进程
        5. 恢复会话（发送"继续"消息）
        
        Returns:
            重启结果
        """
        logger.info("开始重启 OpenCode...")
        
        try:
            # 1. 保存活跃会话
            logger.info("步骤1: 保存活跃会话...")
            saved_sessions = await self._save_active_sessions()
            logger.info(f"已保存 {len(saved_sessions)} 个活跃会话")
            
            # 2. 停止 SSE 监听（释放连接）
            if self.on_before_opencode_stop:
                logger.info("步骤2: 停止 SSE 监听...")
                try:
                    await self.on_before_opencode_stop()
                    logger.info("SSE 监听已停止")
                except Exception as e:
                    logger.warning(f"停止 SSE 监听失败: {e}")
            
            # 3. 停止进程
            logger.info("步骤3: 停止 OpenCode 进程...")
            try:
                stop_result = await self.stop_opencode()
                logger.info(f"停止结果: {stop_result}")
            except Exception as e:
                logger.warning(f"停止 OpenCode 时出现异常（继续重启）: {e}")
            
            # 等待端口释放（最多 3 秒）
            logger.info("等待端口释放...")
            for i in range(3):
                await asyncio.sleep(1)
                if not self.is_port_in_use(self.opencode_port):
                    logger.info(f"端口 {self.opencode_port} 已释放")
                    break
                logger.info(f"等待端口释放中... ({i+1}/3)")
            
            # 4. 启动新进程
            logger.info("步骤4: 启动新 OpenCode 进程...")
            start_result = await self.start_opencode(force=True)  # 强制释放端口
            logger.info(f"启动结果: {start_result}")
            
            if not start_result.get("success"):
                return start_result
            
            # 5. 恢复会话（等待 API 就绪）
            logger.info("步骤5: 恢复会话...")
            # 等待 API 就绪而不是固定等待
            for i in range(10):
                if await self._check_opencode_api_ready():
                    logger.info("OpenCode API 已就绪，开始恢复会话")
                    break
                await asyncio.sleep(0.5)
            
            recovery_result = await self._recover_sessions(saved_sessions)
            logger.info(f"恢复结果: {recovery_result}")
            
            # 6. 调用回调
            if self.on_opencode_restart:
                try:
                    await self.on_opencode_restart()
                except Exception as e:
                    logger.error(f"OpenCode 重启回调失败: {e}")
            
            logger.info("OpenCode 重启完成")
            return {
                "success": True,
                "pid": start_result.get("pid"),
                "recovered_sessions": len(saved_sessions),
                "recovery_result": recovery_result
            }
            
        except Exception as e:
            logger.error(f"重启 OpenCode 失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    async def _save_active_sessions(self) -> List[Dict[str, Any]]:
        """保存活跃会话（正在进行的会话）
        
        通过调用 OpenCode 的 GET /session/status API 获取会话状态
        然后从本地 session_manager 获取 agent/model 配置
        
        Returns:
            活跃会话列表
        """
        saved = []
        
        if not self.opencode_client:
            logger.warning("OpenCode 客户端不可用，无法获取会话状态")
            return saved
        
        try:
            # 使用 opencode_client 的内部方法发送请求
            data, error = await self.opencode_client._send_request(
                method="GET",
                endpoint="/session/status"
            )
            
            if error:
                logger.warning(f"获取 OpenCode 会话状态失败: {error}")
                return saved
            
            if not data:
                logger.info("OpenCode 返回空会话列表")
                return saved
            
            # data 格式: { [sessionID: string]: { type: "busy" | "idle" } }
            session_ids = []
            for session_id, status in data.items():
                if isinstance(status, dict):
                    session_type = status.get("type", "")
                    # 只保存 busy 类型的会话（正在进行的）
                    if session_type == "busy":
                        session_ids.append(session_id)
                        logger.debug(f"发现活跃会话: session={session_id}, type={session_type}")
            
            logger.info(f"发现 {len(session_ids)} 个活跃会话")
            
            # 对每个活跃会话获取详细信息
            for session_id in session_ids:
                try:
                    # 获取会话详情（directory 等）
                    session_data, session_error = await self.opencode_client._send_request(
                        method="GET",
                        endpoint=f"/session/{session_id}"
                    )
                    
                    if session_error:
                        logger.warning(f"获取会话 {session_id} 详情失败: {session_error}")
                        continue
                    
                    if session_data:
                        title = session_data.get("title", "")
                        # 优先使用 OpenCode API 返回的 directory（这是最准确的）
                        api_directory = session_data.get("directory")
                        
                        # 从本地 session_manager 获取 agent/model/provider
                        # 遍历所有用户会话找到匹配的 session_id
                        # 可能有多个用户共享同一个会话，选择最近活跃的用户
                        agent = None
                        model = None
                        provider = None
                        user_id = None
                        user_name = None
                        latest_access = 0
                        
                        if self.session_manager:
                            for uid, user_session in self.session_manager.user_sessions.items():
                                if user_session.session_id == session_id:
                                    # 选择最近活跃的用户
                                    if user_session.last_accessed > latest_access:
                                        latest_access = user_session.last_accessed
                                        user_id = uid
                                        agent = user_session.agent
                                        model = user_session.model
                                        provider = user_session.provider
                            
                            if user_id:
                                # 从配置获取用户名
                                user_config = self.session_manager.user_configs.get(user_id, {})
                                user_name = user_config.get("nickname", "") if isinstance(user_config, dict) else getattr(user_config, "nickname", "") if user_config else ""
                                logger.debug(f"选择最近活跃用户: user_id={user_id}, last_accessed={latest_access}, agent={agent}, model={model}")
                        
                        # 如果没有找到，使用配置的默认值
                        if not agent:
                            agent = self.opencode_client.default_agent
                        if not model:
                            model = self.opencode_client.default_model
                        if not provider:
                            provider = self.opencode_client.default_provider
                        
                        # directory: 优先使用 OpenCode API 返回的值（最准确）
                        directory = api_directory
                        if not directory or directory == "/" or directory == "C:\\":
                            # 如果 API 返回无效值，尝试从本地存储获取
                            if self.session_manager and user_id:
                                user_session = self.session_manager.get_user_session(user_id)
                                if user_session and user_session.directory:
                                    directory = user_session.directory
                            # 最后使用默认值
                            if not directory:
                                directory = self.opencode_client.directory or "/"
                        
                        session_info = {
                            "session_id": session_id,
                            "agent": agent,
                            "model": model,
                            "provider": provider,
                            "directory": directory,
                            "title": title,
                            "user_id": user_id,
                            "user_name": user_name,
                        }
                        saved.append(session_info)
                        logger.info(f"保存会话详情: session={session_id}, agent={agent}, model={model}, directory={directory}")
                        
                except Exception as e:
                    logger.error(f"获取会话 {session_id} 详情异常: {e}")
            
            logger.info(f"成功保存 {len(saved)} 个活跃会话的详细信息")
                        
        except Exception as e:
            logger.error(f"获取 OpenCode 会话状态失败: {e}")
        
        return saved
    
    async def _recover_sessions(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """恢复会话（异步并发发送"继续"消息）
        
        Args:
            sessions: 保存的会话列表
            
        Returns:
            恢复结果
        """
        if not self.opencode_client:
            return {"success": False, "error": "OpenCode client not available"}
        
        async def recover_single_session(session_info: Dict[str, Any]) -> Dict[str, Any]:
            """恢复单个会话"""
            session_id = session_info.get("session_id")
            directory = session_info.get("directory", "/")
            agent = session_info.get("agent")
            model = session_info.get("model")
            provider = session_info.get("provider")
            user_qq = session_info.get("user_id", "")
            user_name = session_info.get("user_name", "")
            
            if not session_id:
                return {"session_id": None, "success": False, "error": "No session_id"}
            
            try:
                # 先验证会话是否仍然存在
                session_data, check_error = await self.opencode_client._send_request(
                    method="GET",
                    endpoint=f"/session/{session_id}"
                )
                
                if check_error or not session_data:
                    logger.warning(f"会话 {session_id} 在重启后已不存在，跳过恢复")
                    return {"session_id": session_id, "success": False, "error": "Session not found after restart"}
                
                # 不使用 OpenCode API 返回的 directory（重启后可能被重置）
                # 优先使用保存的 session_info 中的 directory
                if not directory or directory == "/" or directory == "C:\\":
                    # 只有当保存的 directory 无效时才使用 API 返回的
                    api_directory = session_data.get("directory")
                    if api_directory:
                        directory = api_directory
                
                logger.info(f"正在恢复会话 {session_id}: directory={directory}, agent={agent}, model={model}")
                
                # 发送重启恢复消息
                import json
                recovery_data = {
                    "type": "system_message",
                    "user_qq": str(user_qq) if user_qq else "",
                    "user_name": user_name or "",
                    "session_id": session_id,
                    "system": "opencode已成功重启，请继续"
                }
                recovery_message = f'<Axeuh_bot>\n{json.dumps(recovery_data, ensure_ascii=False)}\n</Axeuh_bot>\nopencode已成功重启，请继续'
                
                result, error = await self.opencode_client.send_message(
                    message_text=recovery_message,
                    session_id=session_id,
                    directory=directory,
                    agent=agent,
                    model=model,
                    provider=provider
                )
                
                if error:
                    logger.warning(f"恢复会话 {session_id} 失败: {error}")
                    return {"session_id": session_id, "success": False, "error": error}
                else:
                    logger.info(f"已恢复会话 {session_id}")
                    return {"session_id": session_id, "success": True}
                    
            except Exception as e:
                logger.error(f"恢复会话 {session_id} 异常: {e}")
                return {"session_id": session_id, "success": False, "error": str(e)}
        
        # 并发恢复所有会话
        tasks = [recover_single_session(session_info) for session_info in sessions]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"恢复会话异常: {result}")
                final_results.append({"session_id": sessions[i].get("session_id"), "success": False, "error": str(result)})
            else:
                final_results.append(result)
        
        success_count = sum(1 for r in final_results if r.get("success"))
        
        return {
            "total": len(sessions),
            "recovered": success_count,
            "details": final_results
        }
    
    def get_status(self) -> Dict[str, Any]:
        """获取进程状态
        
        Returns:
            进程状态信息
        """
        return {
            "opencode": {
                "running": self.opencode_running and self.opencode_process and self.opencode_process.poll() is None,
                "pid": self.opencode_process.pid if self.opencode_process else None,
                "port": self.opencode_port,
                "restart_count": self.opencode_restart_count
            },
            "active_sessions": len(self._active_sessions),
            "timestamp": datetime.now().isoformat()
        }
    
    async def start_monitoring(self):
        """启动 OpenCode 进程监控"""
        if self._monitoring:
            logger.warning("监控已在运行")
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("OpenCode 进程监控已启动")
    
    async def stop_monitoring(self):
        """停止监控"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("OpenCode 进程监控已停止")
    
    async def _monitor_loop(self):
        """监控循环"""
        while self._monitoring:
            try:
                # 检查进程状态
                if self.opencode_process and self.opencode_process.poll() is not None:
                    # 进程已退出
                    exit_code = self.opencode_process.returncode
                    logger.warning(f"OpenCode 进程已退出，退出码: {exit_code}")
                    
                    self.opencode_running = False
                    self.opencode_restart_count += 1
                    
                    if self.opencode_restart_count < self.max_restart_attempts:
                        logger.info(f"将在 {self.restart_delay} 秒后重启 OpenCode")
                        await asyncio.sleep(self.restart_delay)
                        
                        result = await self.start_opencode()
                        if result.get("success"):
                            logger.info("OpenCode 重启成功")
                        else:
                            logger.error(f"OpenCode 重启失败: {result.get('error')}")
                    else:
                        logger.error("达到最大重启次数，停止监控")
                        break
                
                await asyncio.sleep(5)  # 每5秒检查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(5)
    
    def cleanup(self):
        """清理资源"""
        self._monitoring = False
        
        if self.opencode_process:
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ['taskkill', '/F', '/T', '/PID', str(self.opencode_process.pid)],
                        capture_output=True,
                        timeout=5
                    )
                else:
                    self.opencode_process.terminate()
                    self.opencode_process.wait(timeout=5)
            except Exception as e:
                logger.error(f"清理 OpenCode 进程失败: {e}")
            finally:
                self.opencode_process = None
                self.opencode_running = False
        
        logger.info("进程管理器已清理")


# 单例实例
_process_manager: Optional[ProcessManager] = None


def get_process_manager() -> Optional[ProcessManager]:
    """获取进程管理器单例"""
    return _process_manager


def init_process_manager(
    opencode_port: int = 4091,
    session_manager: Optional["SessionManager"] = None,
    opencode_client: Optional["OpenCodeClient"] = None,
    on_opencode_restart: Optional[Callable[[], Awaitable[None]]] = None
) -> ProcessManager:
    """初始化进程管理器单例"""
    global _process_manager
    _process_manager = ProcessManager(
        opencode_port=opencode_port,
        session_manager=session_manager,
        opencode_client=opencode_client,
        on_opencode_restart=on_opencode_restart
    )
    return _process_manager