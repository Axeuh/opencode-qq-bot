#!/usr/bin/env python3
"""
文件下载器 - 处理文件下载逻辑
从 file_handler.py 中提取的下载逻辑
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Awaitable, Tuple, List

from .path_resolver import PathResolver
from .validator import FileValidator

# 导入 HTTP 客户端
try:
    from ..napcat_http_client import NapCatHttpClient
    HTTP_CLIENT_AVAILABLE = True
except ImportError:
    HTTP_CLIENT_AVAILABLE = False
    NapCatHttpClient = None

logger = logging.getLogger(__name__)


class FileDownloader:
    """文件下载器，负责文件下载和三层回退机制"""
    
    def __init__(
        self,
        base_download_dir: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        api_callback: Optional[Callable[[str, Dict[str, Any], float], Awaitable[Optional[Dict[str, Any]]]]] = None
    ):
        """初始化文件下载器
        
        Args:
            base_download_dir: 文件下载的基础目录
            config: 文件配置字典
            api_callback: 可选的API回调函数，用于发送OneBot API请求
        """
        self.base_download_dir = base_download_dir
        self.config = config or {}
        self.api_callback = api_callback
        self.path_resolver = PathResolver()
        self.validator = FileValidator(config)
        
        # 初始化 HTTP 客户端
        self.http_client = NapCatHttpClient() if HTTP_CLIENT_AVAILABLE else None
    
    # ==================== 公共方法 ====================
    
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
        
        # 对于图片类型，如果没有 file_id 和 url，使用 get_image API
        if not file_id and not url:
            if file_type == "image" and filename:
                logger.info(f"使用 get_image API 下载图片：{filename}")
            else:
                logger.error(f"文件下载失败：file_id 和 url 都为空，文件信息：{file_info}")
                return None
        
        # 如果只有 url 没有 file_id，标记为 url 下载模式
        url_only_mode = not file_id and url is not None
        
        # 验证文件大小
        file_size_str = file_info.get("file_size", "0")
        try:
            file_size = int(file_size_str)
        except ValueError:
            file_size = 0
        
        is_valid, error = self.validator.validate_file_size(file_size)
        if not is_valid:
            logger.warning(f"文件大小验证失败: {error}")
            if self.config.get("continue_on_download_fail", True):
                return None
            else:
                return None
        
        # 生成保存路径
        save_path = self._generate_save_path(filename, user_id)
        
        # 检查文件是否已存在
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            if self._check_file_size_match(save_path, file_size):
                logger.debug(f"文件已存在且大小匹配，跳过下载: {filename}")
                return save_path
        
        try:
            logger.debug(f"开始下载文件：{filename} (ID: {file_id}, 类型：{file_type})")
            
            # 如果是 URL 下载模式（支持图片、视频、音频等多种类型）
            if url_only_mode and url:
                logger.info(f"使用 HTTP 下载 {file_type}：{url[:100]}...")
                result = await self._download_file_from_url(url, save_path, file_type)
                if result:
                    return result
                logger.debug(f"URL 下载失败，尝试其他下载方式")
            
            # 方法1: 使用 get_file API 获取确切路径（推荐）
            if file_id:
                file_info_result = await self._get_file_info_via_api(file_id)
                if file_info_result:
                    # 优先使用 API 返回的 URL（适用于视频等媒体文件）
                    api_url = file_info_result.get("url", "")
                    napcat_path = file_info_result.get("file", "")
                    
                    # 如果 API 返回了 URL，直接使用 URL 下载
                    if api_url:
                        logger.info(f"使用 get_file API 返回的 URL 下载: {api_url[:80]}...")
                        result = await self._download_file_from_url(api_url, save_path, file_type)
                        if result:
                            return result
                        logger.warning(f"从 get_file API 返回的 URL 下载失败，尝试其他方法")
                    
                    # 如果有本地路径，尝试从本地路径复制
                    if napcat_path:
                        logger.info(f"使用 get_file API 返回的路径下载: {napcat_path}")
                        result = await self._download_from_napcat_path(napcat_path, save_path)
                        if result:
                            return result
                        logger.warning(f"从 get_file API 返回的路径下载失败，尝试回退方法")
            
            # 方法2: 回退到字符匹配方式
            logger.info("使用回退方法：从 NapCat 临时目录查找文件")
            return await self._fallback_file_download(filename, save_path, file_id)
                
        except Exception as e:
            logger.error(f"文件下载过程中出错: {e}")
            if self.config.get("continue_on_download_fail", True):
                return None
            else:
                raise
    
    # ==================== 私有方法 - 路径生成 ====================
    
    def _generate_save_path(self, filename: str, user_id: Optional[int] = None) -> str:
        """生成文件保存路径
        
        Args:
            filename: 文件名
            user_id: 用户 QQ 号
            
        Returns:
            保存路径
        """
        download_dir = self.config.get("download_dir", "downloads")
        naming_strategy = self.config.get("naming_strategy", "original")
        
        # 如果提供了 user_id，按 QQ 号创建子目录
        if user_id:
            user_dir = os.path.join(download_dir, str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            download_dir = user_dir
        
        # 根据命名策略生成文件名
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
        
        # 使用绝对路径
        save_path = os.path.abspath(save_path)
        
        # 避免文件名冲突
        counter = 1
        original_save_path = save_path
        while os.path.exists(save_path):
            base_name, ext = os.path.splitext(original_save_path)
            save_path = f"{base_name}_{counter}{ext}"
            counter += 1
        
        return save_path
    
    def _check_file_size_match(self, file_path: str, expected_size: int) -> bool:
        """检查文件大小是否匹配
        
        Args:
            file_path: 文件路径
            expected_size: 预期大小
            
        Returns:
            是否匹配
        """
        if expected_size <= 0:
            return True
        
        actual_size = os.path.getsize(file_path)
        size_difference = abs(actual_size - expected_size)
        size_match_threshold = 1024  # 1KB 容忍度
        
        return size_difference <= size_match_threshold
    
    # ==================== 私有方法 - API 获取 ====================
    
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
                
                logger.debug(f"get_file API 原始响应: {result}")
                
                if not result:
                    logger.warning("get_file API 返回空响应")
                    return None
                
                # 检查响应格式
                if result.get("status") == "ok":
                    data = result.get("data")
                    if data:
                        logger.info(f"WebSocket get_file API 返回成功: file={data.get('file')}")
                        return data
                    else:
                        logger.warning("get_file API 返回空数据")
                elif "file" in result:
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
    
    # ==================== 私有方法 - 下载实现 ====================
    
    async def _download_from_napcat_path(self, napcat_path: str, save_path: str) -> Optional[str]:
        """从 NapCat 返回的路径复制文件到本地
        
        Args:
            napcat_path: NapCat 返回的 WSL 路径
            save_path: 目标保存路径
            
        Returns:
            下载后的文件路径，或 None（失败）
        """
        # 转换 WSL 路径为 Windows 网络共享路径
        windows_path = self.path_resolver.convert_wsl_to_windows(napcat_path)
        
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
    
    async def _download_file_from_url(self, url: str, save_path: str, file_type: str = "file") -> Optional[str]:
        """从 URL 下载文件到本地（支持图片、视频、音频等多种类型）
        
        Args:
            url: 文件 URL 地址
            save_path: 目标保存路径
            file_type: 文件类型（image, video, audio, file 等）
            
        Returns:
            下载后的文件路径，或 None（失败）
        """
        import aiohttp
        
        try:
            logger.info(f"开始从 URL 下载 {file_type}：{url[:100]}...")
            
            # 设置不同的超时时间：视频文件可能较大
            timeout_seconds = 120 if file_type in ("video", "audio") else 60
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    if response.status != 200:
                        logger.error(f"下载 {file_type} 失败：HTTP {response.status}")
                        return None
                    
                    file_data = await response.read()
                    
                    if not file_data:
                        logger.error(f"下载的 {file_type} 数据为空")
                        return None
                    
                    with open(save_path, 'wb') as f:
                        f.write(file_data)
                    
                    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                        file_size_kb = os.path.getsize(save_path) / 1024
                        logger.info(f"{file_type} 下载成功：{save_path} (大小：{file_size_kb:.1f}KB)")
                        return save_path
                    else:
                        logger.error(f"{file_type} 写入失败：{save_path}")
                        return None
                        
        except aiohttp.ClientError as e:
            logger.error(f"aiohttp 下载 {file_type} 失败：{e}")
            return None
        except Exception as e:
            logger.error(f"下载 {file_type} 过程中出错：{e}")
            return None
    
    # ==================== 私有方法 - 三层回退下载 ====================
    
    async def _fallback_file_download(
        self, 
        filename: str, 
        save_path: str, 
        file_id: Optional[str] = None
    ) -> Optional[str]:
        """回退文件下载方法：三层回退机制
        
        Args:
            filename: 文件名
            save_path: 目标保存路径
            file_id: 文件 ID（用于日志）
            
        Returns:
            下载后的文件路径，或 None（失败）
        """
        logger.debug(f"从 NapCat 临时目录获取文件：{filename} (ID: {file_id if file_id else 'N/A'})")
        
        # 等待一段时间，让 NapCat 下载文件到临时目录
        download_wait_time = self.config.get("download_wait_time", 2)
        await asyncio.sleep(download_wait_time)
        
        # 尝试从 NapCat 的临时目录查找并复制文件
        napcat_temp_dir = self.config.get(
            "napcat_temp_dir", 
            r"C:\Users\Administrator\Documents\Tencent Files\NapCat\temp"
        )
        
        if not os.path.exists(napcat_temp_dir):
            logger.warning(f"NapCat 临时目录不存在: {napcat_temp_dir}")
            return None
        
        # 查找匹配的文件
        found_file = await self._find_matching_file(napcat_temp_dir, filename)
        
        if found_file:
            # 复制文件到目标目录
            return await self._copy_file_to_destination(found_file, save_path)
        
        logger.warning(f"无法从 NapCat 临时目录找到或复制文件：{filename}")
        return None
    
    async def _find_matching_file(self, temp_dir: str, filename: str) -> Optional[str]:
        """在临时目录中查找匹配的文件
        
        Args:
            temp_dir: 临时目录路径
            filename: 目标文件名
            
        Returns:
            匹配的文件路径，或 None
        """
        # 获取所有临时文件
        temp_files = glob.glob(os.path.join(temp_dir, "*"))
        
        # 按修改时间排序，最新的文件可能是刚下载的
        temp_files.sort(key=os.path.getmtime, reverse=True)
        
        # 清理 filename 用于匹配
        filename_base = os.path.splitext(filename)[0].lower()
        filename_ext = os.path.splitext(filename)[1].lower()
        
        # 尝试找到最佳匹配的文件
        best_match = None
        best_match_score = -1
        
        for temp_file in temp_files:
            temp_filename = os.path.basename(temp_file)
            temp_filename_base = os.path.splitext(temp_filename)[0].lower()
            temp_ext = os.path.splitext(temp_filename)[1].lower()
            
            # 计算匹配分数
            score = self._calculate_match_score(
                filename, filename_base, filename_ext,
                temp_filename, temp_filename_base, temp_ext
            )
            
            if score > 0 and score > best_match_score:
                best_match = temp_file
                best_match_score = score
                logger.debug(f"文件匹配候选: {temp_filename} -> 分数: {score}")
        
        # 至少 85 分才认为是有效匹配
        if best_match and best_match_score >= 85:
            return best_match
        
        return None
    
    def _calculate_match_score(
        self,
        filename: str, filename_base: str, filename_ext: str,
        temp_filename: str, temp_filename_base: str, temp_ext: str
    ) -> int:
        """计算文件名匹配分数
        
        Args:
            filename: 目标文件名
            filename_base: 目标文件基本名
            filename_ext: 目标文件扩展名
            temp_filename: 临时文件名
            temp_filename_base: 临时文件基本名
            temp_ext: 临时文件扩展名
            
        Returns:
            匹配分数 (0-100)
        """
        score = 0
        
        # 规则0：完整文件名完全一致（包括扩展名）
        if temp_filename.lower() == filename.lower():
            score = 100
        # 规则1：基本文件名完全一致
        elif temp_filename_base == filename_base:
            score = 90
        # 规则2：清理括号和空格后的基本名匹配
        elif temp_filename_base.replace('(', '').replace(')', '').replace(' ', '') == filename_base:
            score = 85
        # 规则3：文件名前缀匹配（包含关系）
        elif filename_base in temp_filename_base or temp_filename_base in filename_base:
            score = 70
        # 规则4：清理括号和空格后的前缀匹配
        elif filename_base in temp_filename_base.replace('(', '').replace(')', '').replace(' ', ''):
            score = 60
        
        # 扩展名匹配调整
        if score > 0:
            if filename_ext and temp_ext:
                if filename_ext == temp_ext:
                    score = min(100, int(score * 1.2))
                else:
                    score = int(score * 0.3)
        
        return score
    
    async def _copy_file_to_destination(self, source_path: str, dest_path: str) -> Optional[str]:
        """复制文件到目标路径
        
        Args:
            source_path: 源文件路径
            dest_path: 目标文件路径
            
        Returns:
            目标文件路径，或 None（失败）
        """
        try:
            shutil.copy2(source_path, dest_path)
            logger.debug(f"文件已从NapCat临时目录复制: {source_path} -> {dest_path}")
            
            # 验证文件已成功复制
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                copied_size = os.path.getsize(dest_path)
                logger.debug(f"文件复制验证成功: {dest_path} (大小: {copied_size}字节)")
                return dest_path
            else:
                logger.warning(f"文件复制后验证失败: {dest_path}")
                return None
        except Exception as e:
            logger.error(f"复制文件失败: {e}")
            logger.error(f"复制失败详情: 源文件: {source_path}, 目标: {dest_path}")
            return None