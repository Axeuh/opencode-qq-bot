#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Client - Bot HTTP客户端 (端口4090)
用于与Bot服务器交互，管理用户配置和定时任务
"""
import json
import os
import requests
from typing import Dict, Any, Optional

# 获取配置文件路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config.get("bot", {"host": "127.0.0.1", "port": 4090, "https": False})
    return {"host": "127.0.0.1", "port": 4090, "https": False}


class BotClient:
    """Bot HTTP客户端 - 管理用户配置和定时任务"""
    
    def __init__(self, host: str = None, port: int = None, https: bool = None):
        config = load_config()
        self.host = host or config.get("host", "127.0.0.1")
        self.port = port or config.get("port", 4090)
        self.https = https if https is not None else config.get("https", False)
        protocol = "https" if self.https else "http"
        self.base_url = f"{protocol}://{self.host}:{self.port}"
    
    def _request(self, method: str, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        
        # HTTPS时禁用SSL证书验证（自签名证书）
        verify_ssl = not self.https
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30, verify=verify_ssl)
            else:
                response = requests.post(url, json=data, headers=headers, timeout=30, verify=verify_ssl)
            
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "无法连接到Bot服务器"}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "请求超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # === 系统管理 ===
    
    def health(self) -> Dict[str, Any]:
        """健康检查"""
        return self._request("GET", "/health")
    
    def restart_opencode(self) -> Dict[str, Any]:
        """重启OpenCode"""
        return self._request("POST", "/api/system/restart/opencode")
    
    def restart_bot(self) -> Dict[str, Any]:
        """重启Bot"""
        return self._request("POST", "/api/system/restart/bot")

    # === 用户会话管理 (QQ用户到OpenCode会话的映射) ===
    
    def list_user_sessions(self, user_id: int) -> Dict[str, Any]:
        """获取用户的会话映射列表"""
        return self._request("POST", "/api/session/list", {"user_id": user_id})
    
    def create_user_session(self, user_id: int, title: str = None) -> Dict[str, Any]:
        """为用户创建新会话映射"""
        data = {"user_id": user_id}
        if title:
            data["title"] = title
        return self._request("POST", "/api/session/new", data)
    
    def switch_user_session(self, user_id: int, session_id: str) -> Dict[str, Any]:
        """切换用户的当前会话"""
        return self._request("POST", "/api/session/switch", {
            "user_id": user_id,
            "session_id": session_id
        })
    
    def delete_user_session(self, user_id: int, session_id: str) -> Dict[str, Any]:
        """删除用户的会话映射"""
        return self._request("POST", "/api/session/delete", {
            "user_id": user_id,
            "session_id": session_id
        })
    
    def set_session_title(self, user_id: int, session_id: str, title: str) -> Dict[str, Any]:
        """设置会话标题"""
        return self._request("POST", "/api/session/title", {
            "user_id": user_id,
            "session_id": session_id,
            "title": title
        })
    
    # === 任务管理 ===
    
    def list_tasks(self, user_id: int) -> Dict[str, Any]:
        """获取用户任务列表"""
        return self._request("POST", "/api/task/get", {"user_id": user_id})
    
    def create_task(self, user_id: int, session_id: str, name: str, 
                    prompt: str, schedule_type: str, schedule_config: Dict) -> Dict[str, Any]:
        """创建定时任务"""
        return self._request("POST", "/api/task/set", {
            "user_id": user_id,
            "session_id": session_id,
            "task_name": name,
            "prompt": prompt,
            "schedule_type": schedule_type,
            "schedule_config": schedule_config
        })
    
    def delete_task(self, user_id: int, task_id: str) -> Dict[str, Any]:
        """删除任务"""
        return self._request("POST", "/api/task/delete", {
            "user_id": user_id,
            "task_id": task_id
        })
    
    # === 智能体管理 ===
    
    def list_agents(self) -> Dict[str, Any]:
        """获取可用智能体列表"""
        return self._request("GET", "/api/agents")
    
    def get_agent(self, user_id: int) -> Dict[str, Any]:
        """获取用户当前智能体"""
        return self._request("POST", "/api/agents/get", {"user_id": user_id})
    
    def set_agent(self, user_id: int, agent: str) -> Dict[str, Any]:
        """设置用户智能体"""
        return self._request("POST", "/api/agents/set", {
            "user_id": user_id,
            "agent": agent
        })
    
    # === 模型管理 ===
    
    def list_models(self) -> Dict[str, Any]:
        """获取可用模型列表"""
        return self._request("GET", "/api/models")
    
    def get_model(self, user_id: int) -> Dict[str, Any]:
        """获取用户当前模型"""
        return self._request("POST", "/api/model/get", {"user_id": user_id})
    
    def set_model(self, user_id: int, model: str) -> Dict[str, Any]:
        """设置用户模型"""
        return self._request("POST", "/api/model/set", {
            "user_id": user_id,
            "model": model
        })
    
    # === 工作目录管理 ===
    
    def get_directory(self, user_id: int) -> Dict[str, Any]:
        """获取用户工作目录"""
        return self._request("POST", "/api/directory/get", {"user_id": user_id})
    
    def set_directory(self, user_id: int, directory: str) -> Dict[str, Any]:
        """设置用户工作目录"""
        return self._request("POST", "/api/directory/set", {
            "user_id": user_id,
            "directory": directory
        })