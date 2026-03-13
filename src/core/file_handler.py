#!/usr/bin/env python3
"""
文件处理模块 - 处理QQ机器人文件上传和下载
从onebot_client.py中提取的文件处理逻辑
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from typing import Dict, List, Optional, Any, Tuple, Callable, Awaitable
from datetime import datetime

# 导入 HTTP 客户端
try:
    from .napcat_http_client import NapCatHttpClient
    HTTP_CLIENT_AVAILABLE = True
except ImportError:
    HTTP_CLIENT_AVAILABLE = False
    NapCatHttpClient = None

logger = logging.getLogger(__name__)


class FileHandler:
    """文件处理器，负责文件下载、保存和管理"""
    
    def __init__(
        self,
        base_download_dir: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        api_callback: Optional[Callable[[str, Dict[str, Any], float], Awaitable[Optional[Dict[str, Any]]]]] = None
):
        """初始化文件处理器
        
        Args:
            base_download_dir: 文件下载的基础目录
            config: 文件配置字典
            api_callback: 可选的API回调函数，用于发送OneBot API请求。
                          签名: async def callback(action: str, params: Dict[str, Any], timeout: float) -> Optional[Dict[str, Any]]
        """
        self.base_download_dir = base_download_dir
        self.config = config or {}
        self.api_callback = api_callback
        
        # 初始化 HTTP 客户端
        self.http_client = NapCatHttpClient() if HTTP_CLIENT_AVAILABLE else None
        
        # 设置默认配置
        self.default_config = {
            "auto_download_files": True,
            "include_file_path_in_message": True,
            "file_message_prefix": "用户发送了一个文件，文件路径: ",
            "continue_on_download_fail": True,
            "max_file_size_mb": 100,
            "max_file_size": 50 * 1024 * 1024,  # 50MB，与onebot_client.py保持一致
            "allowed_file_types": ["image", "file", "video", "voice"],
            "image_download_dir": "images",
            "file_download_dir": "files",
            "video_download_dir": "videos",
            "voice_download_dir": "voice",
            "download_dir": "downloads",
            "naming_strategy": "original",
            "download_wait_time": 2,
            "napcat_temp_dir": r"C:\Users\Administrator\Documents\Tencent Files\NapCat\temp"
        }
        
        # 合并配置
        for key, default_value in self.default_config.items():
            self.config[key] = self.config.get(key, default_value)
        
        # 确保下载目录存在
        download_dir = self.config.get("download_dir", "downloads")
        os.makedirs(download_dir, exist_ok=True)
        
        if self.base_download_dir:
            os.makedirs(self.base_download_dir, exist_ok=True)
            logger.info(f"文件处理器初始化完成，下载目录: {self.base_download_dir}")
        else:
            logger.info(f"文件处理器初始化完成，使用配置下载目录: {download_dir}")
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """更新文件配置
        
    Args:
            config: 新的配置字典
        """
        self.config.update(config)
        logger.debug(f"文件配置已更新: {config}")
    
    async def download_file(
        self,
        file_info: Dict[str, Any],
        group_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Optional[str]:
        """下载文件到本地
        
    Args:
            file_info: 文件信息字典，包含 filename, file_id, file_size 等
            group_id: 群号（如果是群文件），私聊时为 None
            user_id: 发送文件的用户 QQ 号
            
    Returns:
            下载后的本地文件路径，或 None（下载失败）
        """
        file_id = file_info.get("file_id")
        filename = file_info.get("filename", "unknown_file")
        file_type = file_info.get("type", "file")
        
        # 检查是否有 URL 参数（适用于图片等媒体类型）
        url = None
        if "params" in file_info and "url" in file_info["params"]:
            url = file_info["params"]["url"]
        elif "url" in file_info:
            url = file_info["url"]
        
        # 对于图片类型，如果没有 file_id 和 url，使用 get_image API（只需要 filename）
        if not file_id and not url:
            if file_type == "image" and filename:
                logger.info(f"使用 get_image API 下载图片：{filename}")
                # 继续执行，让后面的 get_image API 逻辑处理
            else:
                logger.error(f"文件下载失败：file_id 和 url 都为空，文件信息：{file_info}")
                return None
        
        # 如果只有 url 没有 file_id，标记为 url 下载模式（常见于图片）
        url_only_mode = not file_id and url is not None
        
        # 检查文件大小限制
        file_size_str = file_info.get("file_size", "0")
        try:
            file_size = int(file_size_str)
        except ValueError:
            file_size = 0
        
        max_file_size = self.config.get("max_file_size", 50 * 1024 * 1024)  # 默认50MB
        if file_size > max_file_size:
            logger.warning(f"文件过大，跳过下载：{filename} ({file_size}字节 > {max_file_size}字节限制)")
            if self.config.get("continue_on_download_fail", True):
                return None  # 继续处理消息，但返回None表示未下载
            else:
                return None
        
        # 生成保存路径
        download_dir = self.config.get("download_dir", "downloads")
        naming_strategy = self.config.get("naming_strategy", "original")
        
        # 如果提供了user_id，按QQ号创建子目录
        if user_id:
            user_dir = os.path.join(download_dir, str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            download_dir = user_dir
        
        if naming_strategy == "timestamp":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name, ext = os.path.splitext(filename)
            save_filename = f"{base_name}_{timestamp}{ext}"
        elif naming_strategy == "random":
            import uuid
            base_name, ext = os.path.splitext(filename)
            save_filename = f"{base_name}_{uuid.uuid4().hex[:8]}{ext}"
        else:  # "original"
            save_filename = filename
        
        # 清理文件名中的非法字符
        safe_filename = "".join(c for c in save_filename if c.isalnum() or c in "._- ")
        save_path = os.path.join(download_dir, safe_filename)
        
        # 使用绝对路径（全局路径）返回
        save_path = os.path.abspath(save_path)
        
        # 避免文件名冲突
        counter = 1
        original_save_path = save_path
        while os.path.exists(save_path):
            base_name, ext = os.path.splitext(original_save_path)
            save_path = f"{base_name}_{counter}{ext}"
            counter += 1
        
        # 检查文件是否已存在，并比较文件大小（避免重复下载同名不同内容的文件）
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            # 获取已知的文件大小信息（如果可用）
            file_size_str = file_info.get("file_size", "0")
            try:
                expected_size = int(file_size_str)
                if expected_size > 0:
                    # 获取实际文件大小
                    actual_size = os.path.getsize(save_path)
                    
                    # 检查文件大小是否匹配（允许小误差）
                    size_difference = abs(actual_size - expected_size)
                    size_match_threshold = 1024  # 1KB容忍度
                    
                    if size_difference <= size_match_threshold:
                        logger.debug(f"文件已存在且大小匹配，跳过下载: {filename}")
                        return save_path
                    else:
                        logger.debug(f"文件已存在但大小不匹配，创建新文件: {filename}")
                        # 文件名冲突逻辑会处理新文件名
                else:
                    logger.debug(f"文件已存在但无有效大小信息，继续下载: {filename}")
                    # 文件名冲突逻辑会处理新文件名
            except (ValueError, TypeError):
                logger.debug(f"文件已存在但无法解析大小信息，继续下载: {filename}")
                # 文件名冲突逻辑会处理新文件名
        else:
            logger.debug(f"文件不存在或为空，需要下载: {filename}")
        
        try:
            logger.debug(f"开始下载文件：{filename} (ID: {file_id}, 类型：{file_type})")
            
            # 如果是图片 URL 下载模式（url_only_mode 且类型为 image）
            if url_only_mode and file_type == "image" and url:
                logger.debug(f"使用 HTTP 下载图片：{url}")
                # 尝试使用 URL 下载
                result = await self._download_image_from_url(url, save_path)
                if result:
                    return result
                # URL 下载失败，尝试其他方法
                logger.debug(f"URL 下载失败，尝试其他下载方式")
            
            # 方法1: 使用 get_file API 获取确切路径（推荐）
            if file_id:
                file_info = await self._get_file_info_via_api(file_id)
                if file_info:
                    napcat_path = file_info.get("file", "")
                    if napcat_path:
                        logger.info(f"使用 get_file API 返回的路径下载: {napcat_path}")
                        result = await self._download_from_napcat_path(napcat_path, save_path)
                        if result:
                            return result
                        logger.warning(f"从 get_file API 返回的路径下载失败，尝试回退方法")
            
            # 方法2: 回退到字符匹配方式（从 NapCat 临时目录查找）
            logger.info("使用回退方法：从 NapCat 临时目录查找文件")
            return await self._fallback_file_download(filename, save_path, file_id)
                
        except Exception as e:
            logger.error(f"文件下载过程中出错: {e}")
            if self.config.get("continue_on_download_fail", True):
                return None
            else:
                raise
    
    async def _get_file_info_via_api(self, file_id: str) -> Optional[Dict[str, Any]]:
        """通过 get_file API 获取文件信息（优先 HTTP，回退 WebSocket）
        
        Args:
            file_id: 文件ID
            
        Returns:
            文件信息字典，包含 file, url, file_size, file_name
            或 None（获取失败）
        """
        # 方法1: 优先使用 HTTP API（更可靠）
        if self.http_client:
            try:
                logger.info(f"使用 HTTP API 获取文件信息: {file_id}")
                file_info = await self.http_client.get_file(file_id)
                if file_info:
                    logger.info(f"HTTP get_file 成功: file={file_info.get('file')}")
                    return file_info
                else:
                    logger.warning("HTTP get_file 返回空，尝试 WebSocket")
            except Exception as e:
                logger.warning(f"HTTP get_file 异常: {e}，尝试 WebSocket")
        
        # 方法2: 回退到 WebSocket API
        if self.api_callback:
            try:
                logger.info(f"使用 WebSocket API 获取文件信息: {file_id}")
                
                result = await self.api_callback("get_file", {"file_id": file_id}, 30.0)
                
                # 调试：打印完整响应
                logger.debug(f"get_file API 原始响应: {result}")
                
                if not result:
                    logger.warning("get_file API 返回空响应")
                    return None
                
                # 检查响应格式
                # 格式1: {"status": "ok", "data": {...}}
                # 格式2: {"file": "...", "url": "...", ...} (直接返回数据)
                
                if result.get("status") == "ok":
                    data = result.get("data")
                    if data:
                        logger.info(f"WebSocket get_file API 返回成功: file={data.get('file')}, file_name={data.get('file_name')}")
                        return data
                    else:
                        logger.warning("get_file API 返回空数据")
                elif "file" in result:
                    # 直接返回数据格式
                    logger.info(f"get_file API 返回成功(直接格式): file={result.get('file')}")
                    return result
                else:
                    error_msg = result.get("message", result.get("wording", "未知错误"))
                    logger.warning(f"get_file API 调用失败: {error_msg}, 响应: {result}")
                
                return None
                
            except Exception as e:
                logger.error(f"调用 get_file API 异常: {e}")
                return None
        
        logger.warning("未配置 HTTP 客户端或 api_callback，无法获取文件信息")
        return None
    
    def _convert_wsl_path_to_windows(self, wsl_path: str) -> str:
        """将 WSL 路径转换为 Windows 网络共享路径
        
        Args:
            wsl_path: WSL 路径，如 /root/.config/QQ/NapCat/temp/file.png
            
        Returns:
            Windows UNC 路径，如 \\\\172.27.213.195\\wsl-root\\root\\.config\\QQ\\NapCat\\temp\\file.png
        """
        if not wsl_path:
            return ""
        
        # Windows 访问 WSL 目录的格式: \\172.27.213.195\wsl-root\root\...
        # WSL 路径格式: /root/.config/QQ/NapCat/temp/filename.png
        
        # 移除开头的 /
        if wsl_path.startswith("/"):
            wsl_path = wsl_path[1:]
        
        # 构建网络共享路径: \\172.27.213.195\wsl-root\root\.config\QQ\NapCat\temp\filename.png
        windows_path = os.path.join(r"\\172.27.213.195\wsl-root", wsl_path.replace("/", "\\"))
        
        logger.debug(f"路径转换: WSL={wsl_path} -> Windows={windows_path}")
        return windows_path
    
    async def _download_from_napcat_path(self, napcat_path: str, save_path: str) -> Optional[str]:
        """从 NapCat 返回的路径复制文件到本地
        
        Args:
            napcat_path: NapCat 返回的 WSL 路径
            save_path: 目标保存路径
            
        Returns:
            下载后的文件路径，或 None（失败）
        """
        # 转换 WSL 路径为 Windows 网络共享路径
        windows_path = self._convert_wsl_path_to_windows(napcat_path)
        
        logger.info(f"从 NapCat 路径复制文件: {windows_path} -> {save_path}")
        
        try:
            # 检查源文件是否存在
            if not os.path.exists(windows_path):
                logger.warning(f"源文件不存在: {windows_path}")
                return None
            
            # 复制文件
            shutil.copy2(windows_path, save_path)
            
            # 验证文件
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                logger.info(f"文件复制成功: {save_path} (大小: {os.path.getsize(save_path)} 字节)")
                return save_path
            else:
                logger.warning(f"文件复制后验证失败: {save_path}")
                return None
                
        except FileNotFoundError as e:
            logger.error(f"源文件不存在: {windows_path}, 错误: {e}")
            return None
        except PermissionError as e:
            logger.error(f"权限不足，无法访问文件: {windows_path}, 错误: {e}")
            return None
        except Exception as e:
            logger.error(f"复制文件异常: {e}")
            return None
    
    async def _download_image_from_url(self, url: str, save_path: str) -> Optional[str]:
        """从 URL 下载图片到本地
        
        Args:
            url: 图片 URL 地址
            save_path: 目标保存路径
            
        Returns:
            下载后的文件路径，或 None（失败）
        """
        import aiohttp
        import os
        
        try:
            logger.info(f"开始从 URL 下载图片：{url}")
            
            # 创建临时的 aiohttp 会话
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        logger.error(f"下载图片失败：HTTP {response.status}")
                        return None
                    
                    # 读取图片数据
                    image_data = await response.read()
                    
                    if not image_data:
                        logger.error("下载的图片数据为空")
                        return None
                    
                    # 写入文件
                    with open(save_path, 'wb') as f:
                        f.write(image_data)
                    
                    # 验证文件
                    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                        logger.info(f"图片下载成功：{save_path} (大小：{os.path.getsize(save_path)}字节)")
                        return save_path
                    else:
                        logger.error(f"图片写入失败：{save_path}")
                        return None
                        
        except aiohttp.ClientError as e:
            logger.error(f"aiohttp 下载图片失败：{e}")
            return None
        except Exception as e:
            logger.error(f"下载图片过程中出错：{e}")
            return None
    
    async def _fallback_file_download(self, filename: str, save_path: str, file_id: Optional[str] = None) -> Optional[str]:
        """回退文件下载方法：从 NapCat 临时目录查找并复制文件
        
        Args:
            filename: 文件名
            save_path: 目标保存路径
            file_id: 文件 ID（用于日志）
            
        Returns:
            下载后的文件路径，或 None（失败）
        """
        import os
        import asyncio
        
        logger.debug(f"从 NapCat 临时目录获取文件：{filename} (ID: {file_id if file_id else 'N/A'})")
        
        # 等待一段时间，让 NapCat 下载文件到临时目录
        download_wait_time = self.config.get("download_wait_time", 2)
        await asyncio.sleep(download_wait_time)  # 等待 NapCat 处理下载
        
        # 尝试从 NapCat 的临时目录查找并复制文件
        napcat_temp_dir = self.config.get("napcat_temp_dir", r"C:\Users\Administrator\Documents\Tencent Files\NapCat\temp")
        
        if os.path.exists(napcat_temp_dir):
            # 查找最近修改的文件，可能包含目标文件名
            import glob
            temp_files = glob.glob(os.path.join(napcat_temp_dir, "*"))
            
            # 按修改时间排序，最新的文件可能是刚下载的
            temp_files.sort(key=os.path.getmtime, reverse=True)
            
            # 清理filename用于匹配（移除扩展名，只保留基本名）
            filename_base = os.path.splitext(filename)[0].lower()
            
            # 尝试找到最佳匹配的文件
            best_match = None
            best_match_score = -1
            
            for temp_file in temp_files:
                temp_filename = os.path.basename(temp_file)
                temp_filename_base = os.path.splitext(temp_filename)[0].lower()
                
                # 分数计算：0-100分，分数越高匹配越好
                score = 0
                
                # 获取扩展名用于匹配
                filename_ext = os.path.splitext(filename)[1].lower()
                temp_ext = os.path.splitext(temp_filename)[1].lower()
                
                # 规则0：完整文件名完全一致（包括扩展名）
                if temp_filename.lower() == filename.lower():
                    score = 100
                # 规则1：基本文件名完全一致（最理想的情况）
                elif temp_filename_base == filename_base:
                    score = 90
                # 规则2：清理括号和空格后的基本名匹配
                # NapCat使用"文件名 (数字)"格式，清理括号和空格
                elif temp_filename_base.replace('(', '').replace(')', '').replace(' ', '') == filename_base:
                    score = 85
                # 规则3：文件名前缀匹配（包含关系）- 仅在扩展名相同时使用
                elif filename_base in temp_filename_base or temp_filename_base in filename_base:
                    score = 70
                # 规则4：清理括号和空格后的前缀匹配 - 仅在扩展名相同时使用
                elif filename_base in temp_filename_base.replace('(', '').replace(')', '').replace(' ', ''):
                    score = 60
                
                # 扩展名匹配调整：扩展名相同增加分数，不同减少分数
                if score > 0:
                    if filename_ext and temp_ext:
                        if filename_ext == temp_ext:
                            # 扩展名相同，增加分数（最高不超过100）
                            score = min(100, int(score * 1.2))
                        else:
                            # 扩展名不同，大幅减少分数
                            score = int(score * 0.3)
                    # 如果扩展名为空，不做调整

                # 如果找到匹配，检查是否比当前最佳匹配更好
                if score > 0 and score > best_match_score:
                    best_match = temp_file
                    best_match_score = score
                    logger.debug(f"文件匹配候选: {temp_filename} -> 分数: {score}")
            
            # 如果有最佳匹配，使用它
            if best_match and best_match_score >= 85:  # 至少85分才认为是有效匹配
                found_file = best_match
            else:
                found_file = None
            
            if found_file:
                # 复制文件到目标目录
                try:
                    shutil.copy2(found_file, save_path)
                    logger.debug(f"文件已从NapCat临时目录复制: {found_file} -> {save_path}")
                    
                    # 验证文件已成功复制
                    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                        # 记录复制后的文件大小用于调试
                        copied_size = os.path.getsize(save_path)
                        logger.debug(f"文件复制验证成功: {save_path} (大小: {copied_size}字节)")
                        return save_path
                    else:
                        logger.warning(f"文件复制后验证失败: {save_path}")
                except Exception as copy_error:
                    logger.error(f"复制文件失败: {copy_error}")
                    # 记录详细错误信息
                    logger.error(f"复制失败详情: 源文件: {found_file}, 目标: {save_path}, 错误: {str(copy_error)}")
        
            # 如果无法从临时目录复制，返回 None 表示下载失败
            logger.warning(f"无法从 NapCat 临时目录找到或复制文件：{filename}")
            return None
    
    async def process_file_message(
        self,
        raw_message: str,
        message_type: str,
        group_id: Optional[int] = None,
        user_id: Optional[int] = None,
        original_message: Optional[Dict[str, Any]] = None
    ) -> str:
        """处理文件消息，返回要转发给OpenCode的文本
        
    Args:
            raw_message: 原始消息内容
            message_type: 消息类型（private/group）
            group_id: 群号（如果是群消息）
            user_id: 发送文件的用户QQ号
            original_message: 原始消息字典（可选，用于forward消息等需要访问raw字段的情况）
            
    Returns:
            处理后的消息文本，包含文件信息
        """
        from .cq_code_parser import extract_file_info, extract_plain_text
        
        # 提取文件信息
        file_info_list = extract_file_info(raw_message)
        
        if not file_info_list:
            return extract_plain_text(raw_message)  # 没有文件，返回纯文本
        
        processed_messages = []
        
        # 处理每个文件
        for file_info in file_info_list:
            filename = file_info.get("filename", "unknown_file")
            file_id = file_info.get("file_id", "")
            file_type = file_info.get("type", "file")
            
            # 根据文件类型处理
            if file_type == "image":
                # 图片消息处理 - 先下载到本地，再发送文件路径
                url = file_info.get("params", {}).get("url", "")
                
                # 下载图片到本地
                local_path = await self.download_file(file_info, group_id, user_id)
                
                if local_path:
                    # 下载成功，发送文件路径
                    file_msg = f"{self.config.get('file_message_prefix', '用户发送了一个文件，文件路径：')}{local_path}"
                    logger.info(f"图片下载成功：{filename} -> {local_path}")
                elif self.config.get("continue_on_download_fail", True):
                    # 下载失败但继续处理
                    if url:
                        file_msg = f"用户发送了一张图片：{filename} (URL: {url}) [下载失败]"
                    else:
                        file_msg = f"用户发送了一张图片：{filename} [下载失败]"
                    logger.warning(f"图片下载失败但仍继续处理：{filename}")
                else:
                    # 下载失败且配置为不继续
                    logger.error(f"图片下载失败且配置为不继续处理：{filename}")
                    continue
                
                processed_messages.append(file_msg)
                continue
            
# 处理合并转发消息
            elif file_type == "forward":
                # 获取转发消息ID
                forward_id = file_info.get("file_id", "")
                params = file_info.get("params", {})
                
                # 基础消息文本
                file_msg = f"用户发送了一个合并转发消息 (ID: {forward_id})"
                
                # 方法1: 优先使用 get_forward_msg API 获取消息内容
                forward_messages = None
                
                if forward_id:
                    # 尝试 HTTP API
                    if self.http_client:
                        try:
                            logger.info(f"使用 HTTP API 获取合并转发消息: {forward_id}")
                            forward_data = await self.http_client.get_forward_msg(forward_id)
                            if forward_data:
                                forward_messages = forward_data.get("messages", [])
                                logger.info(f"HTTP get_forward_msg 成功，获取到 {len(forward_messages)} 条消息")
                        except Exception as e:
                            logger.warning(f"HTTP get_forward_msg 异常: {e}")
                    
                    # 回退到 WebSocket API
                    if not forward_messages and self.api_callback:
                        try:
                            logger.info(f"使用 WebSocket API 获取合并转发消息: {forward_id}")
                            result = await self.api_callback("get_forward_msg", {"message_id": forward_id}, 30.0)
                            if result and result.get("status") == "ok":
                                forward_data = result.get("data", {})
                                forward_messages = forward_data.get("messages", [])
                                logger.info(f"WebSocket get_forward_msg 成功，获取到 {len(forward_messages)} 条消息")
                        except Exception as e:
                            logger.warning(f"WebSocket get_forward_msg 异常: {e}")
                
                # 如果成功获取到消息列表，解析并构建消息
                if forward_messages:
                    try:
                        # 解析消息列表，支持文件和图片下载
                        parsed_messages = []
                        downloaded_files = []  # 记录下载的文件
                        
                        for msg_idx, msg in enumerate(forward_messages):
                            # 每条消息包含 sender 信息和 message 数组
                            sender = msg.get("sender", {})
                            nickname = sender.get("nickname", "未知用户")
                            
                            # 消息内容在 message 字段
                            message = msg.get("message", [])
                            raw_message = msg.get("raw_message", "")
                            
                            if isinstance(message, list):
                                # 处理消息中的每个元素
                                text_parts = []
                                for item in message:
                                    if isinstance(item, dict):
                                        item_type = item.get("type", "")
                                        
                                        if item_type == "text":
                                            text_parts.append(item.get("data", {}).get("text", ""))
                                        
                                        elif item_type == "image":
                                            # 下载图片
                                            img_data = item.get("data", {})
                                            img_url = img_data.get("url", "")
                                            img_file = img_data.get("file", "unknown.png")
                                            
                                            if self.config.get("auto_download_files", True) and img_url:
                                                # 构造图片文件信息用于下载
                                                # 注意：不设置 file_id，这样 url_only_mode 会生效，使用 URL 下载
                                                img_file_info = {
                                                    "type": "image",
                                                    "filename": img_file,
                                                    "params": {"url": img_url}
                                                }
                                                
                                                # 下载图片
                                                local_path = await self.download_file(img_file_info, group_id, user_id)
                                                
                                                if local_path:
                                                    text_parts.append(f"[图片: {local_path}]")
                                                    downloaded_files.append(("图片", img_file, local_path))
                                                else:
                                                    text_parts.append(f"[图片: {img_file} (下载失败)]")
                                            else:
                                                text_parts.append(f"[图片: {img_file}]")
                                        
                                        elif item_type == "file":
                                            # 文件消息（合并转发中的文件无法下载）
                                            file_data = item.get("data", {})
                                            file_name = file_data.get("file", "unknown_file")
                                            
                                            # 合并转发消息中的文件无法通过 get_file API 下载
                                            # 原因：NapCat 的 downloadRichMedia 内部超时
                                            # 提示用户单独发送文件
                                            text_parts.append(f"[文件: {file_name} (合并转发消息暂时无法下载文件，请提醒用户单独发送文件)]")
                                            logger.info(f"合并转发消息中的文件无法下载: {file_name}")
                                    
                                    elif isinstance(item, str):
                                        text_parts.append(item)
                                
                                text_content = "".join(text_parts)
                            elif isinstance(message, str):
                                text_content = message
                            else:
                                # 回退到 raw_message
                                text_content = raw_message
                            
                            if text_content.strip():
                                parsed_messages.append(f"{nickname}: {text_content.strip()}")
                        
                        # 构建最终消息
                        if parsed_messages:
                            # 显示所有消息内容
                            file_msg = "用户发送了一个合并转发消息:\n" + "\n".join(f"  {msg}" for msg in parsed_messages)
                            
                            if downloaded_files:
                                file_msg += f"\n\n已下载 {len(downloaded_files)} 个附件:"
                                for ftype, fname, fpath in downloaded_files:
                                    file_msg += f"\n  - {ftype}: {fname} -> {fpath}"
                            
                            logger.info(f"合并转发消息解析成功: {len(parsed_messages)}条消息, 下载{len(downloaded_files)}个文件")
                        else:
                            file_msg = f"用户发送了一个合并转发消息 (ID: {forward_id}) [无有效内容]"
                    except Exception as e:
                        logger.error(f"解析合并转发消息失败: {e}")
                        file_msg = f"用户发送了一个合并转发消息 (ID: {forward_id}) [解析失败]"
                
                # 方法2: 回退到 XML 解析（如果 API 失败）
                else:
                    logger.info(f"get_forward_msg API 不可用，尝试 XML 解析")
                    
                    # 尝试从多个来源获取XML内容
                    xml_content = None
                    
                    # 1. 首先检查params中是否有xml_content
                    if "xml_content" in params:
                        xml_content = params["xml_content"]
                        logger.debug(f"从CQ码params中获取XML内容，长度: {len(xml_content)}")
                    
                    # 2. 如果original_message存在，尝试从raw字段提取
                    elif original_message is not None:
                        try:
                            logger.debug(f"尝试从original_message提取XML内容")
                            raw_data = original_message.get('raw', {})
                            elements = raw_data.get('elements', [])
                            if elements and isinstance(elements, list) and len(elements) > 0:
                                first_element = elements[0]
                                multi_forward = first_element.get('multiForwardMsgElement')
                                if multi_forward and 'xmlContent' in multi_forward:
                                    xml_content = multi_forward['xmlContent']
                                    logger.debug(f"从raw.elements中获取XML内容，长度: {len(xml_content)}")
                        except Exception as e:
                            logger.debug(f"从raw字段提取XML内容失败: {e}")
                    
                    # 如果有XML内容，尝试简单提取文本
                    if xml_content:
                        try:
                            import re
                            
                            # 使用正则表达式提取所有title标签内容
                            titles = []
                            title_pattern = r'<title[^>]*>([^<]+)</title>'
                            matches = re.findall(title_pattern, xml_content)
                            
                            if matches:
                                titles = [match.strip() for match in matches]
                                logger.info(f"从XML中提取到{len(titles)}个标题")
                                
                                # 辅助函数：去除用户名前缀
                                def clean_title_text(text):
                                    cleaned = re.sub(r'^[^:：]+[:：]\s*', '', text)
                                    return cleaned.strip()
                                
                                # 清理所有标题
                                cleaned_titles = [clean_title_text(title) for title in titles]
                                
                                # 构建消息
                                if len(titles) > 1:
                                    main_title = titles[0]
                                    content_preview = [t for t in cleaned_titles[1:] if t]
                                    if content_preview:
                                        preview_text = "; ".join(content_preview)
                                        file_msg = f"用户发送了一个合并转发消息: {main_title} - 内容: {preview_text}"
                                    else:
                                        file_msg = f"用户发送了一个合并转发消息: {main_title}"
                                else:
                                    file_msg = f"用户发送了一个合并转发消息: {titles[0]}"
                                
                                logger.info(f"合并转发消息XML解析成功: 提取到{len(titles)}个标题")
                            else:
                                file_msg = f"用户发送了一个合并转发消息 (ID: {forward_id})"
                        except Exception as e:
                            logger.debug(f"XML解析转发消息失败: {e}")
                    else:
                        logger.info(f"合并转发消息无XML内容可用，forward_id: {forward_id}")
                
                processed_messages.append(file_msg)
                logger.info(f"合并转发消息已处理: {forward_id}")
                continue
            
            # 其他文件类型（file, voice, video等）按配置处理
            if not self.config.get("auto_download_files", True):
                # 不自动下载文件，只记录信息
                file_msg = f"用户发送了一个文件: {filename} (ID: {file_id})"
                processed_messages.append(file_msg)
                logger.info(f"跳过文件下载: {filename} (配置为不自动下载)")
                continue
            
            # 下载文件
            local_path = await self.download_file(file_info, group_id, user_id)
            
            if local_path:
                # 下载成功
                file_msg = f"{self.config.get('file_message_prefix', '用户发送了一个文件，文件路径: ')}{local_path}"
                processed_messages.append(file_msg)
                logger.info(f"文件信息已添加到消息: {filename} -> {local_path}")
            
            elif self.config.get("continue_on_download_fail", True):
                # 下载失败但继续处理
                file_msg = f"用户发送了一个文件: {filename} (文件ID: {file_id}) [下载失败]"
                processed_messages.append(file_msg)
                logger.warning(f"文件下载失败但仍继续处理: {filename}")
            
            else:
                # 下载失败且配置为不继续
                logger.error(f"文件下载失败且配置为不继续处理: {filename}")
        
        # 提取其他文本内容
        plain_text = extract_plain_text(raw_message)
        if plain_text:
            processed_messages.insert(0, plain_text)
        
        # 组合所有消息
        result = " ".join(processed_messages)
        logger.debug(f"处理后的文件消息: {result}")
        return result
    
    def get_file_type_directory(self, file_type: str) -> str:
        """获取文件类型对应的下载目录
        
    Args:
            file_type: 文件类型（image, file, video, voice等）
            
    Returns:
            目录名称
        """
        type_dir_map = {
            "image": self.config.get("image_download_dir", "images"),
            "file": self.config.get("file_download_dir", "files"),
            "video": self.config.get("video_download_dir", "videos"),
            "voice": self.config.get("voice_download_dir", "voice")
        }
        return type_dir_map.get(file_type, file_type + "s")
    
    def cleanup_old_files(self, max_age_days: int = 30) -> int:
        """清理旧文件
        
    Args:
            max_age_days: 最大保留天数
            
    Returns:
            删除的文件数量
        """
        if not self.base_download_dir or not os.path.exists(self.base_download_dir):
            return 0
        
        deleted_count = 0
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
        
        for root, dirs, files in os.walk(self.base_download_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_mtime = os.path.getmtime(file_path)
                    if file_mtime < cutoff_time:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.debug(f"清理旧文件: {file_path}")
                except Exception as e:
                    logger.error(f"清理文件失败 {file_path}: {e}")
        
        logger.info(f"文件清理完成，删除了 {deleted_count} 个旧文件")
        return deleted_count
    
    def get_download_stats(self) -> Dict[str, Any]:
        """获取下载统计信息
        
    Returns:
            统计信息字典
        """
        if not self.base_download_dir or not os.path.exists(self.base_download_dir):
            return {"total_files": 0, "total_size_mb": 0, "by_type": {}}
        
        stats = {
            "total_files": 0,
            "total_size_bytes": 0,
            "by_type": {}
        }
        
        for root, dirs, files in os.walk(self.base_download_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(file_path)
                    stats["total_files"] += 1
                    stats["total_size_bytes"] += file_size
                    
                    # 按目录类型统计
                    rel_path = os.path.relpath(root, self.base_download_dir)
                    dir_parts = rel_path.split(os.sep)
                    file_type = dir_parts[0] if dir_parts else "unknown"
                    
                    if file_type not in stats["by_type"]:
                        stats["by_type"][file_type] = {"count": 0, "size_bytes": 0}
                    
                    stats["by_type"][file_type]["count"] += 1
                    stats["by_type"][file_type]["size_bytes"] += file_size
                except Exception as e:
                    logger.error(f"统计文件失败 {file_path}: {e}")
        
        # 转换字节为MB
        stats["total_size_mb"] = round(stats["total_size_bytes"] / (1024 * 1024), 2)
        for file_type in stats["by_type"]:
            bytes_val = stats["by_type"][file_type]["size_bytes"]
            stats["by_type"][file_type]["size_mb"] = round(bytes_val / (1024 * 1024), 2)
        
        return stats