#!/usr/bin/env python3
"""
路径解析器 - 处理路径转换和规范化
从 file_handler.py 中提取的路径处理逻辑
"""

from __future__ import annotations

import os
import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class PathResolver:
    """路径解析器，处理 WSL 路径转换和文件名规范化"""
    
    # WSL 网络共享路径前缀
    WSL_NETWORK_PREFIX = r"\\172.27.213.195\wsl-root"
    
    # Windows 文件名非法字符
    INVALID_FILENAME_CHARS = r'[<>:"/\\|?*\x00-\x1f]'
    
    @staticmethod
    def is_wsl_path(path: str) -> bool:
        """判断是否为 WSL 路径
        
        Args:
            path: 待检查的路径
            
        Returns:
            bool: 是否为 WSL 路径
        """
        if not path:
            return False
        return path.startswith('/root/') or path.startswith('/home/')
    
    @staticmethod
    def convert_wsl_to_windows(wsl_path: str) -> str:
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
        windows_path = os.path.join(
            PathResolver.WSL_NETWORK_PREFIX, 
            wsl_path.replace("/", "\\")
        )
        
        logger.debug(f"路径转换: WSL={wsl_path} -> Windows={windows_path}")
        return windows_path
    
    @staticmethod
    def normalize_path(path: str) -> str:
        """规范化路径
        
        Args:
            path: 待规范化的路径
            
        Returns:
            规范化后的绝对路径
        """
        if not path:
            return ""
        
        # 转换为绝对路径
        normalized = os.path.abspath(path)
        
        # 规范化路径分隔符
        normalized = os.path.normpath(normalized)
        
        return normalized
    
    @staticmethod
    def get_safe_filename(filename: str, replacement: str = "_") -> str:
        """获取安全的文件名，移除非法字符
        
        Args:
            filename: 原始文件名
            replacement: 替换非法字符的字符串，默认为下划线
            
        Returns:
            安全的文件名
        """
        if not filename:
            return "unknown_file"
        
        # 移除 Windows 文件名中的非法字符
        safe_name = re.sub(PathResolver.INVALID_FILENAME_CHARS, replacement, filename)
        
        # 移除开头和结尾的空格和点
        safe_name = safe_name.strip(' .')
        
        # 如果文件名为空，使用默认名称
        if not safe_name:
            safe_name = "unknown_file"
        
        return safe_name
    
    @staticmethod
    def get_unique_filepath(directory: str, filename: str) -> Tuple[str, bool]:
        """获取唯一的文件路径，避免文件名冲突
        
        Args:
            directory: 目标目录
            filename: 文件名
            
        Returns:
            Tuple[str, bool]: (唯一文件路径, 是否已存在)
        """
        safe_filename = PathResolver.get_safe_filename(filename)
        filepath = os.path.join(directory, safe_filename)
        filepath = os.path.abspath(filepath)
        
        # 如果文件不存在，直接返回
        if not os.path.exists(filepath):
            return filepath, False
        
        # 文件已存在，添加序号
        base_name, ext = os.path.splitext(filepath)
        counter = 1
        
        while os.path.exists(filepath):
            filepath = f"{base_name}_{counter}{ext}"
            counter += 1
        
        return filepath, True
    
    @staticmethod
    def split_filename(filename: str) -> Tuple[str, str]:
        """分割文件名为基本名和扩展名
        
        Args:
            filename: 文件名
            
        Returns:
            Tuple[str, str]: (基本名, 扩展名，包含点)
        """
        if not filename:
            return "", ""
        
        base_name, ext = os.path.splitext(filename)
        return base_name, ext.lower()
    
    @staticmethod
    def is_image_file(filename: str) -> bool:
        """判断是否为图片文件
        
        Args:
            filename: 文件名
            
        Returns:
            bool: 是否为图片文件
        """
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.ico'}
        _, ext = PathResolver.split_filename(filename)
        return ext in image_extensions
    
    @staticmethod
    def is_video_file(filename: str) -> bool:
        """判断是否为视频文件
        
        Args:
            filename: 文件名
            
        Returns:
            bool: 是否为视频文件
        """
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
        _, ext = PathResolver.split_filename(filename)
        return ext in video_extensions
    
    @staticmethod
    def is_audio_file(filename: str) -> bool:
        """判断是否为音频文件
        
        Args:
            filename: 文件名
            
        Returns:
            bool: 是否为音频文件
        """
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'}
        _, ext = PathResolver.split_filename(filename)
        return ext in audio_extensions