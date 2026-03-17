#!/usr/bin/env python3
"""
CQ码解析器模块
提供CQ码解析、文件信息提取、纯文本提取等功能
"""

import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def parse_cq_code(cq_code: str) -> Dict[str, Any]:
    """解析CQ码，返回类型和参数字典
    
    示例:
        "[CQ:file,file=test.docx,file_id=abc123]" 
        -> {"type": "file", "params": {"file": "test.docx", "file_id": "abc123"}}
    """
    result = {"type": "", "params": {}}
    if not cq_code or not cq_code.startswith("[CQ:") or not cq_code.endswith("]"):
        return result
    
    # 提取CQ码内容，去除方括号
    content = cq_code[4:-1]  # 移除"[CQ:"和"]"
    
    # 分割类型和参数
    parts = content.split(",", 1)
    result["type"] = parts[0]
    
    # 解析参数
    if len(parts) > 1:
        params_str = parts[1]
        # 分割参数，注意值中可能包含逗号（如base64数据）
        # 简单实现：按逗号分割，然后按等号分割
        param_parts = []
        current_part = ""
        in_quotes = False
        for char in params_str:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                param_parts.append(current_part)
                current_part = ""
                continue
            current_part += char
        if current_part:
            param_parts.append(current_part)
        
        for param in param_parts:
            if "=" in param:
                key, value = param.split("=", 1)
                # 去除值两边的引号（如果有）
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                
                value = value.strip()
                
                # 解码HTML实体（如&amp; -> &）
                try:
                    import html
                    # 检查是否包含HTML实体
                    if '&' in value and ('&amp;' in value or '&lt;' in value or '&gt;' in value or '&quot;' in value or '&#x' in value.lower()):
                        value = html.unescape(value)
                except ImportError:
                    pass  # html模块不可用，跳过解码
                except Exception as e:
                    logger.debug(f"HTML解码失败，使用原始值: {e}")
                
                result["params"][key.strip()] = value
    
    return result


def extract_file_info(raw_message: str) -> List[Dict[str, Any]]:
    """从原始消息中提取文件信息（支持CQ:file和CQ:image等格式）
    
    返回文件信息列表，每个元素包含:
        - type: 媒体类型 ("file", "image", "voice", "video"等)
        - filename: 文件名
        - file_id: 文件ID（如果有）
        - file_size: 文件大小（如果有）
        - original_cq: 原始CQ码字符串
        - params: 所有原始参数的副本
    """
    file_info_list = []
    if not raw_message:
        return file_info_list
    
    # 查找所有CQ码
    cq_pattern = r'\[CQ:[^\]]+\]'
    matches = re.finditer(cq_pattern, raw_message)
    
    for match in matches:
        cq_code = match.group()
        parsed = parse_cq_code(cq_code)
        media_type = parsed["type"]
        
        # 支持多种媒体类型
        if media_type in ["file", "image", "voice", "video", "record", "forward", "poke", "music", "share", "contact", "location", "shake"]:
            # 获取文件名或标识参数（不同CQ码可能使用不同的参数名）
            filename = ""
            if media_type in ["file", "image", "voice", "video", "record"]:
                filename = parsed["params"].get("file", "")
                if not filename:
                    filename = parsed["params"].get("filename", "")
                if not filename:
                    filename = parsed["params"].get("name", "")
            elif media_type == "forward":
                filename = f"forward_{parsed['params'].get('id', 'unknown')}"
            elif media_type == "poke":
                filename = f"poke_{parsed['params'].get('type', 'unknown')}_{parsed['params'].get('id', 'unknown')}"
            elif media_type == "music":
                filename = f"music_{parsed['params'].get('type', 'unknown')}_{parsed['params'].get('id', 'unknown')}"
            elif media_type == "share":
                filename = parsed["params"].get("title", "分享链接")
            elif media_type == "contact":
                filename = f"contact_{parsed['params'].get('type', 'unknown')}_{parsed['params'].get('id', 'unknown')}"
            elif media_type in ["location", "shake"]:
                filename = media_type
            
            file_info = {
                "type": media_type,
                "filename": filename,
                "file_id": parsed["params"].get("file_id", parsed["params"].get("id", "")),
                "file_size": parsed["params"].get("file_size", ""),
                "original_cq": cq_code,
                "params": parsed["params"].copy()  # 包含所有原始参数
            }
            file_info_list.append(file_info)
    
    return file_info_list


def extract_plain_text(raw_message: str) -> str:
    """从原始消息中提取纯文本（去除 CQ 码）"""
    if not raw_message:
        return ""
    
    # 移除 CQ 码，如 [CQ:at,qq=123456]，[CQ:image,file=...]
    plain_text = re.sub(r'\[CQ:[^\]]+\]', '', raw_message)
    
    # 移除多余空格并去除首尾空格
    plain_text = re.sub(r'\s+', ' ', plain_text).strip()
    
    return plain_text


def extract_quoted_message_id(message: Dict) -> Optional[str]:
    """从消息中提取引用消息 ID
    
    Args:
        message: 原始消息字典
        
    Returns:
        引用消息 ID（字符串），或 None（如果不是引用消息）
    """
    try:
        if 'message' in message and isinstance(message['message'], list):
            for segment in message['message']:
                if isinstance(segment, dict) and segment.get('type') == 'reply':
                    data = segment.get('data', {})
                    if isinstance(data, dict) and 'id' in data:
                        return data['id']
        return None
    except Exception as e:
        logger.error(f"提取引用消息 ID 失败：{e}")
        return None


# 兼容性别名，便于从旧代码迁移
parse_cq = parse_cq_code
extract_file = extract_file_info
extract_text = extract_plain_text
extract_quoted_message_id = extract_quoted_message_id