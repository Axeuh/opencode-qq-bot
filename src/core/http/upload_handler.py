#!/usr/bin/env python3
"""
文件上传处理模块
包含文件上传端点处理
"""

from __future__ import annotations

import os
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class UploadHandler:
    """文件上传处理器
    
    负责:
    - 处理文件上传请求
    - 验证文件类型和大小
    - 保存文件到指定目录
    """
    
    # 允许的文件扩展名
    ALLOWED_EXTENSIONS = {
        # 图片
        'jpg', 'jpeg', 'png', 'gif', 'webp',
        # 文档
        'pdf', 'doc', 'docx', 'xlsx', 'txt',
        # 压缩包
        'zip', 'rar'
    }
    
    # 最大文件大小 1GB
    MAX_FILE_SIZE = 1024 * 1024 * 1024
    
    def __init__(self, base_dir: Optional[str] = None):
        """初始化文件上传处理器
        
        Args:
            base_dir: 基础目录路径，默认为项目根目录
        """
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    async def handle_upload(self, request: web.Request) -> web.Response:
        """文件上传端点 (POST /api/upload)
        
        接收 multipart/form-data 请求，保存文件到 downloads/{user_id}/ 目录
        
        字段:
            - file: 上传的文件
            - user_id: 用户QQ号
            
        支持的文件类型:
            - 图片: jpg, png, gif, webp
            - 文档: pdf, doc, docx, xlsx, txt
            - 压缩包: zip, rar
            
        最大文件大小: 1GB
        """
        try:
            # 获取 multipart reader
            reader = await request.multipart()
            
            file_data = None
            file_name = None
            user_id = None
            
            # 解析 multipart 字段
            async for field in reader:
                if field.name == 'user_id':
                    # 读取 user_id 字段
                    user_id_bytes = await field.read()
                    user_id = user_id_bytes.decode('utf-8')
                    
                elif field.name == 'file':
                    # 读取文件字段
                    file_name = field.filename
                    file_data = await field.read()
            
            # 验证必需参数
            if not user_id:
                return web.json_response({
                    "success": False,
                    "error": "Missing required field: user_id"
                }, status=400)
            
            if not file_data or not file_name:
                return web.json_response({
                    "success": False,
                    "error": "Missing required field: file"
                }, status=400)
            
            # 验证 user_id 格式
            try:
                user_id = int(user_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "Invalid user_id, must be an integer"
                }, status=400)
            
            # 检查文件大小
            file_size = len(file_data)
            if file_size > self.MAX_FILE_SIZE:
                return web.json_response({
                    "success": False,
                    "error": f"File size exceeds limit: {file_size} bytes > {self.MAX_FILE_SIZE} bytes (1GB)"
                }, status=400)
            
            # 检查文件类型
            file_ext = os.path.splitext(file_name)[1].lower().lstrip('.')
            if file_ext not in self.ALLOWED_EXTENSIONS:
                return web.json_response({
                    "success": False,
                    "error": f"File type not allowed: {file_ext}. Allowed types: {', '.join(sorted(self.ALLOWED_EXTENSIONS))}"
                }, status=400)
            
            # 创建用户目录
            download_dir = os.path.join(self.base_dir, 'downloads', str(user_id))
            os.makedirs(download_dir, exist_ok=True)
            
            # 处理文件名冲突
            safe_filename = self._sanitize_filename(file_name)
            save_path = os.path.join(download_dir, safe_filename)
            
            # 如果文件已存在，添加时间戳
            if os.path.exists(save_path):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_name, ext = os.path.splitext(safe_filename)
                safe_filename = f"{base_name}_{timestamp}{ext}"
                save_path = os.path.join(download_dir, safe_filename)
            
            # 保存文件
            with open(save_path, 'wb') as f:
                f.write(file_data)
            
            # 构建返回路径
            relative_path = f"downloads/{user_id}/{safe_filename}"
            absolute_path = os.path.abspath(save_path)
            
            logger.info(f"文件上传成功: user_id={user_id}, file={safe_filename}, size={file_size}")
            
            return web.json_response({
                "success": True,
                "file_path": relative_path,
                "absolute_path": absolute_path,
                "file_name": safe_filename,
                "file_size": file_size
            })
            
        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除危险字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            安全的文件名
        """
        return "".join(c for c in filename if c.isalnum() or c in "._- ")