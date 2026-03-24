#!/usr/bin/env python3
"""
文件验证器 - 处理文件验证逻辑
从 file_handler.py 中提取的验证逻辑
"""

from __future__ import annotations

import os
import logging
from typing import Dict, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)


class FileValidator:
    """文件验证器，处理文件大小、类型等验证"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化文件验证器
        
        Args:
            config: 配置字典，包含验证相关配置
        """
        self.config = config or {}
        
        # 默认配置
        self.max_file_size = self.config.get("max_file_size", 500 * 1024 * 1024)  # 500MB
        self.max_file_size_mb = self.config.get("max_file_size_mb", 500)
        self.allowed_file_types: Set[str] = set(
            self.config.get("allowed_file_types", ["image", "file", "video", "voice"])
        )
    
    def validate_file_size(self, file_size: int) -> Tuple[bool, Optional[str]]:
        """验证文件大小
        
        Args:
            file_size: 文件大小（字节）
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        if file_size <= 0:
            return True, None  # 未知大小，允许通过
        
        if file_size > self.max_file_size:
            size_mb = file_size / (1024 * 1024)
            error_msg = f"文件过大: {size_mb:.2f}MB > {self.max_file_size_mb}MB 限制"
            logger.warning(error_msg)
            return False, error_msg
        
        return True, None
    
    def validate_file_type(self, file_type: str) -> Tuple[bool, Optional[str]]:
        """验证文件类型
        
        Args:
            file_type: 文件类型（image, file, video, voice 等）
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        if not file_type:
            return True, None  # 未知类型，允许通过
        
        if file_type not in self.allowed_file_types:
            error_msg = f"不支持的文件类型: {file_type}"
            logger.warning(error_msg)
            return False, error_msg
        
        return True, None
    
    def validate_file_exists(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """验证文件是否存在
        
        Args:
            file_path: 文件路径
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        if not file_path:
            return False, "文件路径为空"
        
        if not os.path.exists(file_path):
            error_msg = f"文件不存在: {file_path}"
            logger.warning(error_msg)
            return False, error_msg
        
        return True, None
    
    def validate_file_not_empty(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """验证文件是否非空
        
        Args:
            file_path: 文件路径
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        is_valid, error = self.validate_file_exists(file_path)
        if not is_valid:
            return is_valid, error
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            error_msg = f"文件为空: {file_path}"
            logger.warning(error_msg)
            return False, error_msg
        
        return True, None
    
    def validate_file(
        self, 
        file_path: str, 
        file_size: Optional[int] = None,
        file_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """综合验证文件
        
        Args:
            file_path: 文件路径
            file_size: 文件大小（字节），可选
            file_type: 文件类型，可选
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        # 验证文件大小
        if file_size is not None:
            is_valid, error = self.validate_file_size(file_size)
            if not is_valid:
                return is_valid, error
        
        # 验证文件类型
        if file_type is not None:
            is_valid, error = self.validate_file_type(file_type)
            if not is_valid:
                return is_valid, error
        
        # 验证文件存在
        is_valid, error = self.validate_file_exists(file_path)
        if not is_valid:
            return is_valid, error
        
        return True, None
    
    def validate_file_info(self, file_info: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """验证文件信息字典
        
        Args:
            file_info: 文件信息字典，包含 file_id, filename, file_size 等
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        # 检查必要字段
        file_id = file_info.get("file_id")
        filename = file_info.get("filename")
        url = file_info.get("url") or file_info.get("params", {}).get("url")
        file_type = file_info.get("type", "file")
        
        # 对于图片类型，如果没有 file_id 但有 url，也是有效的
        if not file_id and not url:
            if file_type == "image" and filename:
                # 图片可以只有文件名，使用 get_image API
                pass
            else:
                return False, "文件信息缺少 file_id 和 url"
        
        # 验证文件大小
        file_size_str = file_info.get("file_size", "0")
        try:
            file_size = int(file_size_str)
        except (ValueError, TypeError):
            file_size = 0
        
        is_valid, error = self.validate_file_size(file_size)
        if not is_valid:
            return is_valid, error
        
        # 验证文件类型
        is_valid, error = self.validate_file_type(file_type)
        if not is_valid:
            return is_valid, error
        
        return True, None
    
    @staticmethod
    def is_image(filename: str) -> bool:
        """判断是否为图片文件
        
        Args:
            filename: 文件名
            
        Returns:
            bool: 是否为图片文件
        """
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.ico'}
        if not filename:
            return False
        ext = os.path.splitext(filename)[1].lower()
        return ext in image_extensions
    
    @staticmethod
    def is_video(filename: str) -> bool:
        """判断是否为视频文件
        
        Args:
            filename: 文件名
            
        Returns:
            bool: 是否为视频文件
        """
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
        if not filename:
            return False
        ext = os.path.splitext(filename)[1].lower()
        return ext in video_extensions
    
    @staticmethod
    def is_audio(filename: str) -> bool:
        """判断是否为音频文件
        
        Args:
            filename: 文件名
            
        Returns:
            bool: 是否为音频文件
        """
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'}
        if not filename:
            return False
        ext = os.path.splitext(filename)[1].lower()
        return ext in audio_extensions
    
    @staticmethod
    def get_file_category(filename: str) -> str:
        """根据文件名获取文件类别
        
        Args:
            filename: 文件名
            
        Returns:
            str: 文件类别（image, video, audio, file）
        """
        if FileValidator.is_image(filename):
            return "image"
        if FileValidator.is_video(filename):
            return "video"
        if FileValidator.is_audio(filename):
            return "audio"
        return "file"