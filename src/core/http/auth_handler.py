#!/usr/bin/env python3
"""
认证处理模块
包含登录、密码设置、密码修改等端点处理
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from .middleware import AuthMiddleware

logger = logging.getLogger(__name__)


class AuthHandler:
    """认证处理器
    
    负责:
    - 登录验证
    - 密码设置
    - 密码修改
    """
    
    def __init__(self, auth: "AuthMiddleware"):
        """初始化认证处理器
        
        Args:
            auth: 认证中间件实例
        """
        self.auth = auth
    
    async def handle_login(self, request: web.Request) -> web.Response:
        """登录验证端点
        
        检查:
        1. QQ号是否在白名单中
        2. 用户是否设置了密码
        3. 密码验证
        4. 速率限制（同一设备2秒只能尝试一次，1分钟最多10次）
        """
        try:
            # 获取客户端IP
            client_ip = request.remote or "unknown"
            
            # 检查速率限制
            rate_check = self.auth.check_rate_limit(client_ip)
            if not rate_check["success"]:
                return web.json_response(rate_check, status=429)
            
            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                self.auth.record_login_attempt(client_ip)
                return web.json_response({
                    "success": False,
                    "error": "无效的请求格式"
                }, status=400)
            
            qq_id = body.get("qq_id")
            password = body.get("password", "")
            
            if not qq_id:
                self.auth.record_login_attempt(client_ip)
                return web.json_response({
                    "success": False,
                    "error": "请输入QQ号"
                }, status=400)
            
            try:
                qq_id = int(qq_id)
            except ValueError:
                self.auth.record_login_attempt(client_ip)
                return web.json_response({
                    "success": False,
                    "error": "QQ号必须是数字"
                }, status=400)
            
            # 检查白名单
            if self.auth.whitelist and qq_id not in self.auth.whitelist:
                self.auth.record_login_attempt(client_ip)
                logger.warning(f"非白名单用户尝试登录: QQ={qq_id}, IP={client_ip}")
                return web.json_response({
                    "success": False,
                    "error": "您不在白名单中，无法登录"
                }, status=403)
            
            # 获取会话管理器
            try:
                from ...session.session_manager import get_session_manager
                session_manager = get_session_manager()
            except ImportError:
                session_manager = None
            
            # 检查用户是否设置了密码
            has_password = session_manager.user_has_password(qq_id) if session_manager else False
            
            if not has_password:
                # 用户未设置密码，返回需要设置密码的响应
                self.auth.record_login_attempt(client_ip)
                logger.info(f"用户未设置密码: QQ={qq_id}, IP={client_ip}")
                return web.json_response({
                    "success": False,
                    "need_set_password": True,
                    "error": "请先设置密码"
                }, status=200)
            
            # 用户已设置密码，验证密码
            if not password:
                self.auth.record_login_attempt(client_ip)
                return web.json_response({
                    "success": False,
                    "need_password": True,
                    "error": "请输入密码"
                }, status=200)
            
            # 验证密码
            if session_manager and session_manager.verify_user_password(qq_id, password):
                # 登录成功
                self.auth.record_login_attempt(client_ip)
                logger.info(f"用户登录成功: QQ={qq_id}, IP={client_ip}")
                
                # 创建Web会话token
                session_token = self.auth.create_web_session(qq_id)
                
                response = web.json_response({
                    "success": True,
                    "message": "登录成功",
                    "qq_id": qq_id,
                    "token": session_token
                })
                
                # 设置Cookie
                response.set_cookie(
                    "session_token", 
                    session_token, 
                    max_age=86400 * 7,  # 7天
                    httponly=True,
                    secure=True,  # 仅HTTPS
                    samesite="Lax"
                )
                
                return response
            else:
                # 密码错误
                self.auth.record_login_attempt(client_ip)
                logger.warning(f"密码错误: QQ={qq_id}, IP={client_ip}")
                return web.json_response({
                    "success": False,
                    "need_password": True,
                    "error": "密码错误"
                }, status=200)
            
        except Exception as e:
            logger.error(f"处理登录请求失败: {e}")
            return web.json_response({
                "success": False,
                "error": "服务器错误"
            }, status=500)
    
    async def handle_set_password(self, request: web.Request) -> web.Response:
        """设置密码端点（首次设置）
        
        请求格式: {"qq_id": 123456, "password": "xxx"}
        """
        try:
            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "无效的请求格式"
                }, status=400)
            
            qq_id = body.get("qq_id")
            password = body.get("password", "")
            
            if not qq_id:
                return web.json_response({
                    "success": False,
                    "error": "请输入QQ号"
                }, status=400)
            
            try:
                qq_id = int(qq_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "QQ号必须是数字"
                }, status=400)
            
            # 检查密码长度
            if len(password) < 6:
                return web.json_response({
                    "success": False,
                    "error": "密码长度至少6位"
                }, status=400)
            
            # 检查白名单
            if self.auth.whitelist and qq_id not in self.auth.whitelist:
                logger.warning(f"非白名单用户尝试设置密码: QQ={qq_id}")
                return web.json_response({
                    "success": False,
                    "error": "您不在白名单中"
                }, status=403)
            
            # 获取会话管理器
            try:
                from ...session.session_manager import get_session_manager
                session_manager = get_session_manager()
            except ImportError:
                return web.json_response({
                    "success": False,
                    "error": "服务器配置错误"
                }, status=500)
            
            # 检查用户是否已设置密码
            if session_manager.user_has_password(qq_id):
                return web.json_response({
                    "success": False,
                    "error": "您已设置密码，请使用修改密码功能"
                }, status=400)
            
            # 设置密码
            if session_manager.set_user_password(qq_id, password):
                logger.info(f"用户设置密码成功: QQ={qq_id}")
                
                # 创建Web会话token
                session_token = self.auth.create_web_session(qq_id)
                
                response = web.json_response({
                    "success": True,
                    "message": "密码设置成功",
                    "token": session_token
                })
                
                # 设置Cookie
                response.set_cookie(
                    "session_token", 
                    session_token, 
                    max_age=86400 * 7,  # 7天
                    httponly=True,
                    secure=True,  # 仅HTTPS
                    samesite="Lax"
                )
                
                return response
            else:
                return web.json_response({
                    "success": False,
                    "error": "密码设置失败"
                }, status=500)
            
        except Exception as e:
            logger.error(f"设置密码失败: {e}")
            return web.json_response({
                "success": False,
                "error": "服务器错误"
            }, status=500)
    
    async def handle_change_password(self, request: web.Request) -> web.Response:
        """修改密码端点
        
        请求格式: {"qq_id": 123456, "old_password": "xxx", "new_password": "xxx"}
        """
        try:
            # 解析请求体
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({
                    "success": False,
                    "error": "无效的请求格式"
                }, status=400)
            
            qq_id = body.get("qq_id")
            old_password = body.get("old_password", "")
            new_password = body.get("new_password", "")
            
            if not qq_id:
                return web.json_response({
                    "success": False,
                    "error": "请输入QQ号"
                }, status=400)
            
            try:
                qq_id = int(qq_id)
            except ValueError:
                return web.json_response({
                    "success": False,
                    "error": "QQ号必须是数字"
                }, status=400)
            
            # 检查新密码长度
            if len(new_password) < 6:
                return web.json_response({
                    "success": False,
                    "error": "新密码长度至少6位"
                }, status=400)
            
            # 获取会话管理器
            try:
                from ...session.session_manager import get_session_manager
                session_manager = get_session_manager()
            except ImportError:
                return web.json_response({
                    "success": False,
                    "error": "服务器配置错误"
                }, status=500)
            
            # 检查用户是否设置了密码
            if not session_manager.user_has_password(qq_id):
                return web.json_response({
                    "success": False,
                    "error": "您尚未设置密码，请先设置密码"
                }, status=400)
            
            # 验证旧密码
            if not session_manager.verify_user_password(qq_id, old_password):
                return web.json_response({
                    "success": False,
                    "error": "原密码错误"
                }, status=400)
            
            # 设置新密码
            if session_manager.set_user_password(qq_id, new_password):
                logger.info(f"用户修改密码成功: QQ={qq_id}")
                return web.json_response({
                    "success": True,
                    "message": "密码修改成功"
                })
            else:
                return web.json_response({
                    "success": False,
                    "error": "密码修改失败"
                }, status=500)
            
        except Exception as e:
            logger.error(f"修改密码失败: {e}")
            return web.json_response({
                "success": False,
                "error": "服务器错误"
            }, status=500)
    
    async def handle_health(self, request: web.Request) -> web.Response:
        """健康检查端点"""
        return web.json_response({
            "success": True,
            "status": "healthy",
            "service": "QQ Bot HTTP Server"
        })