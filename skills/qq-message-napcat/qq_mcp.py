#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QQ MCP Server

MCP server for sending QQ messages and managing QQ contacts via napcat WebSocket API.
Provides tools for sending private/group messages, getting friend lists, searching friends, etc.
Based on OneBot v11 protocol using local napcat service (ws://localhost:3002).
"""

import os
import sys
import json
import asyncio
import subprocess
import shutil
from typing import Optional, List, Dict, Any
from enum import Enum
from pathlib import Path

# Add scripts directory to path to import NapcatWebSocketClient
scripts_dir = Path(__file__).parent / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

try:
    from qq_tools_ws import NapcatWebSocketClient
except ImportError as e:
    print(f"Error importing NapcatWebSocketClient: {e}", file=sys.stderr)
    # Fallback: try relative import
    import importlib.util
    spec = importlib.util.spec_from_file_location("qq_tools_ws", scripts_dir / "qq_tools_ws.py")
    qq_tools_ws = importlib.util.module_from_spec(spec)
    sys.modules["qq_tools_ws"] = qq_tools_ws
    spec.loader.exec_module(qq_tools_ws)
    from qq_tools_ws import NapcatWebSocketClient

import httpx
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("qq_mcp")

# Constants from config
DEFAULT_SERVER = "ws://localhost:3002"
DEFAULT_TOKEN = ""
DEFAULT_TIMEOUT = 30

# Load configuration from config.json
def load_config() -> Dict[str, Any]:
    """Load configuration from config.json."""
    config_path = Path(__file__).parent / "config.json"
    config = {
        "server": DEFAULT_SERVER,
        "token": DEFAULT_TOKEN,
        "timeout": DEFAULT_TIMEOUT
    }
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            print(f"Warning: Failed to load config: {e}", file=sys.stderr)
    return config

config = load_config()
SERVER_URL = config.get("server", DEFAULT_SERVER)
TOKEN = config.get("token", DEFAULT_TOKEN)
TIMEOUT = config.get("timeout", DEFAULT_TIMEOUT)


# Enums
class MessageType(str, Enum):
    """Message type: private or group."""
    PRIVATE = "private"
    GROUP = "group"


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# Pydantic Models
class SendMessageInput(BaseModel):
    """Input model for sending QQ message.
    
    Note: message field is placed last for JSON parsing stability
    when it contains escaped characters.
    """
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    message_type: MessageType = Field(
        ...,
        description="Message type: 'private' for direct message or 'group' for group message"
    )
    target_id: str = Field(
        ...,
        description="Target QQ number (for private) or group number (for group)",
        min_length=5,
        max_length=20
    )
    auto_escape: bool = Field(
        default=False,
        description="Whether to automatically escape CQ codes (default: false)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for structured data"
    )
    # message field placed LAST for JSON parsing stability
    message: str = Field(
        ...,
        description="Message content. Can be plain text or OneBot message segment array in JSON format.",
        min_length=1
    )


class GetFriendsInput(BaseModel):
    """Input model for getting friend list."""
    model_config = ConfigDict(
        str_strip_whitespace=True
    )

    use_cache: bool = Field(
        default=True,
        description="Use cached friend list (cache TTL: 60 seconds)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class SearchFriendInput(BaseModel):
    """Input model for searching friends by name."""
    model_config = ConfigDict(
        str_strip_whitespace=True
    )

    name: str = Field(
        ...,
        description="Name to search for (nickname or remark)",
        min_length=1,
        max_length=50
    )
    exact_match: bool = Field(
        default=False,
        description="Exact match (default: fuzzy match)"
    )
    use_cache: bool = Field(
        default=True,
        description="Use cached friend list for search"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class SendFileInput(BaseModel):
    """Input model for sending file."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    message_type: MessageType = Field(
        ...,
        description="Message type: 'private' or 'group'"
    )
    target_id: str = Field(
        ...,
        description="Target QQ number or group number"
    )
    file_path: str = Field(
        ...,
        description="Local file path to send"
    )
    custom_name: Optional[str] = Field(
        default=None,
        description="Custom file name (optional)"
    )
    use_base64: bool = Field(
        default=True,
        description="Use base64 encoding (recommended for small files)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )

    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Validate file exists."""
        if not os.path.exists(v):
            raise ValueError(f"File not found: {v}")
        return v


class GetGroupMsgHistoryInput(BaseModel):
    """Input model for getting group message history."""
    model_config = ConfigDict(
        str_strip_whitespace=True
    )

    group_id: str = Field(
        ...,
        description="Group ID to get message history from",
        min_length=5,
        max_length=20
    )
    message_seq: Optional[str] = Field(
        default=None,
        description="Start message sequence number (optional, for pagination)"
    )
    count: int = Field(
        default=20,
        description="Number of messages to retrieve (default: 20, max: 100)",
        ge=1,
        le=100
    )
    reverse_order: bool = Field(
        default=False,
        description="Return messages in reverse order (oldest first)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetLoginInfoInput(BaseModel):
    """Input model for getting login account info."""
    model_config = ConfigDict(
        str_strip_whitespace=True
    )

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class SendPokeInput(BaseModel):
    """Input model for sending poke (nudge)."""
    model_config = ConfigDict(
        str_strip_whitespace=True
    )

    user_id: str = Field(
        ...,
        description="Target user QQ number",
        min_length=5,
        max_length=20
    )
    group_id: Optional[str] = Field(
        default=None,
        description="Group ID (optional, if not provided, sends private poke)"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )


class GetFileInput(BaseModel):
    """Input model for getting file info."""
    model_config = ConfigDict(
        str_strip_whitespace=True
    )

    file_id: Optional[str] = Field(
        default=None,
        description="File ID (one of file_id or file is required)"
    )
    file: Optional[str] = Field(
        default=None,
        description="File path or URL (one of file_id or file is required)"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="QQ user ID for organizing downloads into user-specific folders"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format"
    )

    @field_validator('file', 'file_id')
    @classmethod
    def validate_at_least_one(cls, v: Optional[str], info) -> Optional[str]:
        """Ensure at least one of file_id or file is provided."""
        return v


# Shared client instance
_client_instance = None

def get_client() -> NapcatWebSocketClient:
    """Get shared NapcatWebSocketClient instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = NapcatWebSocketClient(
            server=SERVER_URL,
            token=TOKEN if TOKEN else None,
            auto_reconnect=True,
            max_retries=3,
            retry_delay=2.0
        )
    return _client_instance


async def ensure_client_connected() -> NapcatWebSocketClient:
    """Ensure client is connected."""
    client = get_client()
    await client.ensure_connected()
    return client


def _handle_error(e: Exception) -> str:
    """Format error messages consistently."""
    error_msg = str(e)
    if "Connection refused" in error_msg or "无法连接到" in error_msg:
        return "Error: Cannot connect to napcat service. Please ensure napcat is running on ws://localhost:3002 and QQ account is logged in."
    elif "认证失败" in error_msg or "Unauthorized" in error_msg:
        return "Error: Authentication failed. Check the token in config.json."
    elif "不是好友" in error_msg or "not a friend" in error_msg:
        return "Error: Target user is not a friend of the bot."
    elif "被移出群聊" in error_msg or "group permission" in error_msg:
        return "Error: Bot has been removed from the group or lacks permission to send messages."
    return f"Error: {type(e).__name__}: {error_msg}"


# MCP Tools
@mcp.tool(
    name="qq_send_message",
    annotations={
        "title": "Send QQ Message",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def qq_send_message(params: SendMessageInput) -> str:
    """Send a private or group message via QQ.

    This tool sends messages through napcat WebSocket API to QQ contacts or groups.
    Supports text messages and OneBot message segment format for rich content.

    Args:
        params (SendMessageInput): Validated input parameters containing:
            - message_type (MessageType): 'private' or 'group'
            - target_id (str): QQ number or group number
            - message (str): Message content (text or JSON message segments)
            - auto_escape (bool): Auto-escape CQ codes
            - response_format (ResponseFormat): Output format

    Returns:
        str: Success or error message

    Examples:
        - Send private text: message_type="private", target_id="123456789", message="Hello!"
        - Send group message: message_type="group", target_id="123456789", message="Group announcement"
        - Send with message segments: message='[{"type":"text","data":{"text":"Hello "}},{"type":"face","data":{"id":"123"}}]'
    """
    try:
        client = await ensure_client_connected()

        # Try to parse message as JSON array, fallback to string
        import json as json_module
        parsed_message = params.message
        try:
            # Attempt to parse as JSON
            parsed = json_module.loads(params.message)
            if isinstance(parsed, list):
                # Valid JSON array - use parsed structure
                parsed_message = parsed
            # If not a list, keep as string (might be plain JSON string)
        except (json_module.JSONDecodeError, TypeError):
            # Not valid JSON, keep as string
            pass

        # Use appropriate client method if available, otherwise fallback to send_request
        if params.message_type == MessageType.PRIVATE:
            if hasattr(client, 'send_private_message'):
                response = await client.send_private_message(
                    user_id=params.target_id,
                    message=parsed_message,
                    auto_escape=params.auto_escape
                )
            else:
                # Fallback to send_request
                response = await client.send_request(
                    "send_private_msg",
                    {
                        "user_id": params.target_id,
                        "message": parsed_message,
                        "auto_escape": params.auto_escape
                    },
                    timeout=TIMEOUT
                )
        else:  # group
            if hasattr(client, 'send_group_message'):
                response = await client.send_group_message(
                    group_id=params.target_id,
                    message=parsed_message,
                    auto_escape=params.auto_escape
                )
            else:
                # Fallback to send_request
                response = await client.send_request(
                    "send_group_msg",
                    {
                        "group_id": params.target_id,
                        "message": parsed_message,
                        "auto_escape": params.auto_escape
                    },
                    timeout=TIMEOUT
                )

        # Determine action for response
        action = "send_private_msg" if params.message_type == MessageType.PRIVATE else "send_group_msg"
        
        if params.response_format == ResponseFormat.JSON:
            result = {
                "success": response.get("status") == "ok",
                "message_id": response.get("data", {}).get("message_id"),
                "action": action,
                "target": params.target_id,
                "response": response
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        # Markdown format
        if response.get("status") == "ok":
            message_id = response.get("data", {}).get("message_id", "unknown")
            lines = [
                f"# QQ Message Sent Successfully",
                "",
                f"- **Type**: {params.message_type.value}",
                f"- **Target**: {params.target_id}",
                f"- **Message ID**: {message_id}",
                f"- **Status**: OK"
            ]
            return "\n".join(lines)
        else:
            error_msg = response.get("wording", "Unknown error")
            return f"# Failed to Send QQ Message\n\n**Error**: {error_msg}\n\n**Response**: {json.dumps(response, ensure_ascii=False, indent=2)}"

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="qq_get_friends",
    annotations={
        "title": "Get QQ Friend List",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def qq_get_friends(params: GetFriendsInput) -> str:
    """Get list of QQ friends for the bot.

    This tool retrieves all friends from the bot's QQ account.
    Results are cached for 60 seconds to improve performance.

    Args:
        params (GetFriendsInput): Validated input parameters containing:
            - use_cache (bool): Use cached friend list
            - response_format (ResponseFormat): Output format

    Returns:
        str: Formatted friend list or error message

    Examples:
        - Get friend list: use_cache=True (default)
        - Force refresh: use_cache=False
    """
    try:
        client = await ensure_client_connected()

        # Check cache if requested
        import time
        current_time = time.time()
        if params.use_cache and client.friend_list_cache:
            if current_time - client.friend_list_cache_time < client.cache_ttl:
                friends = client.friend_list_cache
                cached = True
            else:
                # Cache expired
                response = await client.get_friend_list()
                friends = response.get("data", []) if isinstance(response, dict) else []
                cached = False
        else:
            response = await client.get_friend_list()
            friends = response.get("data", []) if isinstance(response, dict) else []
            cached = False

        if not friends:
            return "No friends found or friend list is empty."

        if params.response_format == ResponseFormat.JSON:
            result = {
                "count": len(friends),
                "cached": cached,
                "friends": friends
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        # Markdown format
        lines = [
            f"# QQ Friend List",
            "",
            f"**Total**: {len(friends)} friends" + (" (cached)" if cached else ""),
            ""
        ]

        for i, friend in enumerate(friends, 1):
            user_id = friend.get("user_id", "unknown")
            nickname = friend.get("nickname", "unknown")
            remark = friend.get("remark", "")
            
            display_name = nickname
            if remark:
                display_name = f"{nickname} (备注: {remark})"
            
            lines.append(f"{i}. **{display_name}** (QQ: {user_id})")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="qq_search_friend",
    annotations={
        "title": "Search QQ Friend by Name",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def qq_search_friend(params: SearchFriendInput) -> str:
    """Search for QQ friends by nickname or remark.

    This tool searches through the bot's friend list for matching names.
    Supports both fuzzy and exact matching.

    Args:
        params (SearchFriendInput): Validated input parameters containing:
            - name (str): Name to search for
            - exact_match (bool): Exact or fuzzy match
            - use_cache (bool): Use cached friend list
            - response_format (ResponseFormat): Output format

    Returns:
        str: Search results or error message

    Examples:
        - Fuzzy search: name="小明", exact_match=False
        - Exact search: name="张三", exact_match=True
    """
    try:
        client = await ensure_client_connected()

        # Get friend list (with caching)
        import time
        current_time = time.time()
        if params.use_cache and client.friend_list_cache:
            if current_time - client.friend_list_cache_time < client.cache_ttl:
                friends = client.friend_list_cache
                cached = True
            else:
                response = await client.get_friend_list()
                friends = response.get("data", []) if isinstance(response, dict) else []
                cached = False
        else:
            response = await client.get_friend_list()
            friends = response.get("data", []) if isinstance(response, dict) else []
            cached = False

        if not friends:
            return "No friends found to search."

        # Search logic
        search_name = params.name.lower()
        matches = []
        
        for friend in friends:
            nickname = friend.get("nickname", "").lower()
            remark = friend.get("remark", "").lower()
            
            if params.exact_match:
                # Exact match on nickname or remark
                if nickname == search_name or remark == search_name:
                    matches.append(friend)
            else:
                # Fuzzy match (contains)
                if (search_name in nickname) or (search_name in remark):
                    matches.append(friend)

        if params.response_format == ResponseFormat.JSON:
            result = {
                "search_query": params.name,
                "exact_match": params.exact_match,
                "cached": cached,
                "match_count": len(matches),
                "matches": matches
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        # Markdown format
        if not matches:
            return f"No friends found matching '{params.name}' (exact match: {params.exact_match})."

        lines = [
            f"# QQ Friend Search Results",
            "",
            f"**Search**: '{params.name}' (exact match: {params.exact_match})",
            f"**Found**: {len(matches)} matches" + (" (cached)" if cached else ""),
            ""
        ]

        for i, friend in enumerate(matches, 1):
            user_id = friend.get("user_id", "unknown")
            nickname = friend.get("nickname", "unknown")
            remark = friend.get("remark", "")
            
            display_name = nickname
            if remark:
                display_name = f"{nickname} (备注: {remark})"
            
            lines.append(f"{i}. **{display_name}** (QQ: {user_id})")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="qq_send_file",
    annotations={
        "title": "Send File via QQ",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def qq_send_file(params: SendFileInput) -> str:
    """Send a file to QQ contact or group.

    This tool sends files (documents, images, etc.) through napcat.
    Supports base64 encoding for reliable transmission and file:// protocol for large files.

    Args:
        params (SendFileInput): Validated input parameters containing:
            - message_type (MessageType): 'private' or 'group'
            - target_id (str): QQ number or group number
            - file_path (str): Local file path
            - custom_name (Optional[str]): Custom file name
            - use_base64 (bool): Use base64 encoding
            - response_format (ResponseFormat): Output format

    Returns:
        str: Success or error message

    Examples:
        - Send private file: message_type="private", target_id="123456789", file_path="/path/to/document.pdf"
        - Send with custom name: custom_name="报告.pdf"
        - Use file:// protocol: use_base64=False (for large files or WSL paths)
    """
    try:
        client = await ensure_client_connected()

        # Use the client's send_file_message method (NapcatWebSocketClient)
        try:
            # NapcatWebSocketClient has send_file_message method
            if hasattr(client, 'send_file_message'):
                result = await client.send_file_message(
                    target_id=params.target_id,
                    file_path=params.file_path,
                    name=params.custom_name,
                    message_type=params.message_type.value,
                    use_base64=params.use_base64
                )
            else:
                # Fallback to using send_request for file upload
                action = "upload_private_file" if params.message_type == MessageType.PRIVATE else "upload_group_file"
                
                # Read file content
                with open(params.file_path, 'rb') as f:
                    file_content = f.read()
                
                # Base64 encode if requested
                if params.use_base64:
                    import base64
                    file_data = f"base64://{base64.b64encode(file_content).decode('utf-8')}"
                    file_param = file_data
                else:
                    # Use file:// protocol
                    # Convert Windows path to WSL path if needed
                    file_path = params.file_path
                    if hasattr(client, 'win_path_to_wsl'):
                        file_path = client.win_path_to_wsl(file_path)
                    file_param = f"file://{file_path}"
                
                file_name = params.custom_name or os.path.basename(params.file_path)
                
                request_params = {
                    "user_id" if params.message_type == MessageType.PRIVATE else "group_id": params.target_id,
                    "file": file_param,
                    "name": file_name
                }
                
                result = await client.send_request(action, request_params, timeout=TIMEOUT)
        
        except AttributeError as ae:
            # Client doesn't have file sending capability
            return f"Error: File sending not supported by current client implementation. AttributeError: {ae}"

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "success": result.get("status") == "ok",
                "action": "send_file",
                "target": params.target_id,
                "file": os.path.basename(params.file_path),
                "response": result
            }, ensure_ascii=False, indent=2)

        # Markdown format
        if result.get("status") == "ok":
            lines = [
                f"# File Sent Successfully",
                "",
                f"- **Type**: {params.message_type.value}",
                f"- **Target**: {params.target_id}",
                f"- **File**: {os.path.basename(params.file_path)}",
                f"- **Encoding**: {'base64' if params.use_base64 else 'file://'}",
                f"- **Status**: OK"
            ]
            if params.custom_name:
                lines.append(f"- **Custom Name**: {params.custom_name}")
            return "\n".join(lines)
        else:
            # 收集所有可能的错误信息
            error_parts = []
            if result.get("wording"):
                error_parts.append(f"wording: {result.get('wording')}")
            if result.get("message"):
                error_parts.append(f"message: {result.get('message')}")
            if result.get("msg"):
                error_parts.append(f"msg: {result.get('msg')}")
            # 检查 data 中的错误
            data = result.get("data", {})
            if isinstance(data, dict):
                if data.get("Error"):
                    error_parts.append(f"Error: {data.get('Error')}")
                if data.get("error"):
                    error_parts.append(f"error: {data.get('error')}")
            
            if error_parts:
                error_msg = "\n".join([f"  - {p}" for p in error_parts])
                return f"# Failed to Send File\n\n**Status**: {result.get('status', 'failed')}\n\n**Errors**:\n{error_msg}"
            else:
                # 返回完整的result以便调试
                return f"# Failed to Send File\n\n**Status**: {result.get('status', 'failed')}\n\n**Full Response**:\n```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```"

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="qq_get_group_msg_history",
    annotations={
        "title": "Get Group Message History",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def qq_get_group_msg_history(params: GetGroupMsgHistoryInput) -> str:
    """Get message history from a QQ group.

    This tool retrieves historical messages from a specified QQ group.
    Supports pagination via message_seq and configurable message count.

    Args:
        params (GetGroupMsgHistoryInput): Validated input parameters containing:
            - group_id (str): Group ID to get messages from
            - message_seq (Optional[str]): Start sequence for pagination
            - count (int): Number of messages to retrieve (1-100)
            - reverse_order (bool): Return in reverse order
            - response_format (ResponseFormat): Output format

    Returns:
        str: Formatted message history or error message

    Examples:
        - Get recent 20 messages: group_id="123456789"
        - Get 50 messages: group_id="123456789", count=50
        - Pagination: group_id="123456789", message_seq="12345"
    """
    try:
        client = await ensure_client_connected()

        # Build request parameters
        request_params = {
            "group_id": params.group_id,
            "count": params.count,
            "reverseOrder": params.reverse_order
        }

        # Add optional message_seq for pagination
        if params.message_seq:
            request_params["message_seq"] = params.message_seq

        # Call the API
        response = await client.send_request(
            "get_group_msg_history",
            request_params,
            timeout=TIMEOUT
        )

        if response.get("status") != "ok":
            error_msg = response.get("wording", response.get("message", "Unknown error"))
            return f"# Failed to Get Group History\n\n**Error**: {error_msg}"

        # Extract messages
        data = response.get("data", {})
        messages = data.get("messages", [])

        if not messages:
            return f"# Group Message History\n\n**Group**: {params.group_id}\n\nNo messages found."

        if params.response_format == ResponseFormat.JSON:
            result = {
                "group_id": params.group_id,
                "count": len(messages),
                "messages": messages
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        # Markdown format
        lines = [
            f"# Group Message History",
            "",
            f"**Group ID**: {params.group_id}",
            f"**Messages**: {len(messages)}",
            ""
        ]

        for i, msg in enumerate(messages, 1):
            sender = msg.get("sender", {})
            nickname = sender.get("nickname", "Unknown")
            user_id = sender.get("user_id", "Unknown")
            card = sender.get("card", "")
            display_name = card if card else nickname

            # Get message time
            timestamp = msg.get("time", 0)
            from datetime import datetime
            try:
                time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            except:
                time_str = str(timestamp)

            # Get message content
            raw_message = msg.get("raw_message", "")
            message_segments = msg.get("message", [])

            # Build message text
            message_text = raw_message if raw_message else ""
            if not message_text and message_segments:
                # Extract text from message segments
                for seg in message_segments:
                    if seg.get("type") == "text":
                        message_text += seg.get("data", {}).get("text", "")
                    elif seg.get("type") == "image":
                        message_text += "[图片]"
                    elif seg.get("type") == "face":
                        message_text += "[表情]"
                    elif seg.get("type") == "at":
                        qq = seg.get("data", {}).get("qq", "")
                        message_text += f"[:@{qq}]"
                    elif seg.get("type") == "file":
                        message_text += "[文件]"

            # Truncate long messages
            if len(message_text) > 200:
                message_text = message_text[:200] + "..."

            lines.append(f"### {i}. {display_name} (QQ: {user_id})")
            lines.append(f"- **Time**: {time_str}")
            lines.append(f"- **Content**: {message_text}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="qq_get_login_info",
    annotations={
        "title": "Get Login Account Info",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def qq_get_login_info(params: GetLoginInfoInput) -> str:
    """Get information about the logged-in QQ account.

    This tool retrieves the current login account's user ID and nickname.

    Args:
        params (GetLoginInfoInput): Validated input parameters containing:
            - response_format (ResponseFormat): Output format

    Returns:
        str: Formatted account info or error message

    Examples:
        - Get login info: (no parameters required)
    """
    try:
        client = await ensure_client_connected()

        # Call the API
        response = await client.send_request(
            "get_login_info",
            {},
            timeout=TIMEOUT
        )

        if response.get("status") != "ok":
            error_msg = response.get("wording", response.get("message", "Unknown error"))
            return f"# Failed to Get Login Info\n\n**Error**: {error_msg}"

        # Extract data
        data = response.get("data", {})
        user_id = data.get("user_id", "Unknown")
        nickname = data.get("nickname", "Unknown")

        if params.response_format == ResponseFormat.JSON:
            result = {
                "user_id": user_id,
                "nickname": nickname
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        # Markdown format
        lines = [
            f"# Login Account Info",
            "",
            f"- **QQ Number**: {user_id}",
            f"- **Nickname**: {nickname}"
        ]

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="qq_send_poke",
    annotations={
        "title": "Send Poke (Nudge)",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def qq_send_poke(params: SendPokeInput) -> str:
    """Send a poke (nudge) to a QQ user.

    This tool sends a poke notification to a user, either in private chat or in a group.

    Args:
        params (SendPokeInput): Validated input parameters containing:
            - user_id (str): Target user QQ number
            - group_id (Optional[str]): Group ID for group poke (optional)
            - response_format (ResponseFormat): Output format

    Returns:
        str: Success or error message

    Examples:
        - Private poke: user_id="123456789"
        - Group poke: user_id="123456789", group_id="987654321"
    """
    try:
        client = await ensure_client_connected()

        # Build request parameters
        request_params = {
            "user_id": params.user_id
        }

        # Add group_id if provided
        if params.group_id:
            request_params["group_id"] = params.group_id

        # Call the API
        response = await client.send_request(
            "send_poke",
            request_params,
            timeout=TIMEOUT
        )

        if response.get("status") != "ok":
            error_msg = response.get("wording", response.get("message", "Unknown error"))
            return f"# Failed to Send Poke\n\n**Error**: {error_msg}"

        # Success
        poke_type = "group" if params.group_id else "private"
        target_info = f"user {params.user_id}"
        if params.group_id:
            target_info += f" in group {params.group_id}"

        if params.response_format == ResponseFormat.JSON:
            result = {
                "success": True,
                "user_id": params.user_id,
                "group_id": params.group_id,
                "poke_type": poke_type
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        # Markdown format
        lines = [
            f"# Poke Sent Successfully",
            "",
            f"- **Type**: {poke_type}",
            f"- **Target User**: {params.user_id}"
        ]
        if params.group_id:
            lines.append(f"- **Group**: {params.group_id}")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="qq_get_file",
    annotations={
        "title": "Get File Info",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def qq_get_file(params: GetFileInput) -> str:
    """Get file information from QQ.

    This tool retrieves file metadata including download URL, size, and name.

    Args:
        params (GetFileInput): Validated input parameters containing:
            - file_id (Optional[str]): File ID
            - file (Optional[str]): File path or URL
            - response_format (ResponseFormat): Output format

    Returns:
        str: File information or error message

    Examples:
        - Get by file_id: file_id="/abc123..."
        - Get by file: file="http://example.com/file.jpg"
    """
    try:
        # Validate at least one parameter
        if not params.file_id and not params.file:
            return "# Error\n\nPlease provide either file_id or file parameter."

        client = await ensure_client_connected()

        # Build request parameters
        request_params = {}
        if params.file_id:
            request_params["file_id"] = params.file_id
        if params.file:
            request_params["file"] = params.file

        # Call the API
        response = await client.send_request(
            "get_file",
            request_params,
            timeout=TIMEOUT
        )

        if response.get("status") != "ok":
            error_msg = response.get("wording", response.get("message", "Unknown error"))
            return f"# Failed to Get File Info\n\n**Error**: {error_msg}"

        # Extract data
        data = response.get("data", {})
        file_path = data.get("file", "Unknown")
        url = data.get("url", "Unknown")
        file_size = data.get("file_size", "Unknown")
        file_name = data.get("file_name", "Unknown")

        # Copy file from WSL to local downloads directory
        local_file_path = None
        copy_error = None
        
        if file_path and file_path.startswith("/root/.config/QQ/NapCat"):
            try:
                # Create downloads directory with user_id subdirectory
                skill_dir = Path(__file__).parent
                downloads_dir = skill_dir / "downloads"
                
                # Add user_id subdirectory if provided
                if params.user_id:
                    downloads_dir = downloads_dir / params.user_id
                
                downloads_dir.mkdir(parents=True, exist_ok=True)
                
                # Local file path
                local_file_path = downloads_dir / file_name
                
                # Use wsl cp to copy file from WSL to Windows
                # wsl cp /root/.config/QQ/NapCat/temp/xxx /mnt/c/Users/.../downloads/
                # Convert Windows path to WSL mount path
                local_file_win = str(local_file_path).replace("\\", "/")
                if ":" in local_file_win:
                    # C:/path -> /mnt/c/path
                    drive = local_file_win[0].lower()
                    path_part = local_file_win[2:]  # Remove "C:"
                    wsl_dest_path = f"/mnt/{drive}{path_part}"
                else:
                    wsl_dest_path = local_file_win
                
                # Execute wsl cp command
                result = subprocess.run(
                    ["wsl", "cp", file_path, wsl_dest_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    copy_error = result.stderr or "Unknown copy error"
                    local_file_path = None
            except Exception as e:
                copy_error = str(e)
                local_file_path = None

        if params.response_format == ResponseFormat.JSON:
            result = {
                "file": file_path,
                "url": url,
                "file_size": file_size,
                "file_name": file_name
            }
            # Add local file path if available
            if local_file_path:
                result["local_path"] = str(local_file_path)
            # Only include base64 if present
            if "base64" in data:
                result["base64"] = data["base64"]
            return json.dumps(result, ensure_ascii=False, indent=2)

        # Markdown format
        lines = [
            f"# File Info",
            "",
            f"- **File Name**: {file_name}",
            f"- **File Size**: {file_size}",
            f"- **Linux Path**: {file_path}",
        ]
        # Add local file path if copy was successful
        if local_file_path:
            lines.append(f"- **Local Path**: {local_file_path}")
        elif copy_error:
            lines.append(f"- **Copy Error**: {copy_error}")
        lines.append(f"- **URL**: {url}")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


# Run the server
if __name__ == "__main__":
    mcp.run()