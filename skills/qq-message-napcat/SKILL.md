---
name: qq-message-napcat
description: |
  通过napcat API发送QQ消息和管理QQ好友。当用户想要发送QQ私聊或群聊消息时使用此技能。
  此技能支持：文本消息和富媒体消息（图片、表情等）发送、获取好友列表、通过名称搜索好友、获取群历史消息。
  基于OneBot v11协议，使用本地napcat服务（ws://localhost:3002）和令牌认证。
compatibility:
  dependencies: []
mcp:
  qq-mcp:
    command: python
    args: ["${USERPROFILE}/.config/opencode/skills/qq-message-napcat/qq_mcp.py"]
---

# QQ消息与好友管理技能（Napcat MCP）

通过MCP服务器调用napcat API发送QQ消息和管理QQ好友。

## 前置要求

- napcat服务正确配置并运行（ws://localhost:3002）
- 目标用户是机器人的好友（对于私聊消息）
- 机器人有发送消息的权限

## 何时使用

- 发送QQ私聊/群聊消息
- 获取QQ好友列表
- 搜索QQ好友
- 发送文件到QQ
- 获取群历史消息
- 获取登录账号信息

## 可用工具

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `qq_send_message` | 发送QQ消息 | message_type, target_id, message |
| `qq_get_friends` | 获取好友列表 | 无 |
| `qq_search_friend` | 搜索好友 | name, exact_match |
| `qq_send_file` | 发送文件 | message_type, target_id, file_path, custom_name, use_base64 |
| `qq_get_group_msg_history` | 获取群历史消息 | group_id, count, message_seq |
| `qq_get_login_info` | 获取登录账号信息 | 无 |
| `qq_send_poke` | 发送戳一戳 | user_id, group_id |
| `qq_get_file` | 获取文件信息 | file_id, file |

## 调用示例

### 发送私聊消息
```typescript
skill_mcp(
  mcp_name="qq-mcp",
  tool_name="qq_send_message",
  arguments={"params": {
    "message_type": "private",
    "target_id": "123456789",
    "message": "你好，这是一条测试消息"
  }}
)
```

### 发送群聊消息
```typescript
skill_mcp(
  mcp_name="qq-mcp",
  tool_name="qq_send_message",
  arguments={"params": {
    "message_type": "group",
    "target_id": "957134103",
    "message": "群聊测试消息"
  }}
)
```

### 发送带@的群聊消息
```typescript
skill_mcp(
  mcp_name="qq-mcp",
  tool_name="qq_send_message",
  arguments={"params": {
    "message_type": "group",
    "target_id": "957134103",
    "message": "[{\"type\":\"at\",\"data\":{\"qq\":\"2176284372\"}},{\"type\":\"text\",\"data\":{\"text\":\" 请查看这条消息\"}}]"
  }}
)
```

### 获取好友列表
```typescript
skill_mcp(
  mcp_name="qq-mcp",
  tool_name="qq_get_friends",
  arguments={}
)
```

### 搜索好友
```typescript
skill_mcp(
  mcp_name="qq-mcp",
  tool_name="qq_search_friend",
  arguments={"params": {
    "name": "Axeuh"
  }}
)
```

### 发送文件
```typescript
skill_mcp(
  mcp_name="qq-mcp",
  tool_name="qq_send_file",
  arguments={"params": {
    "message_type": "private",
    "target_id": "123456789",
    "file_path": "D:\\path\\to\\file.xlsx"
  }}
)
```

### 发送文件（带自定义文件名）
```typescript
skill_mcp(
  mcp_name="qq-mcp",
  tool_name="qq_send_file",
  arguments={"params": {
    "message_type": "group",
    "target_id": "813729523",
    "file_path": "D:\\opencode\\video.mp4",
    "custom_name": "我的视频.mp4",
    "use_base64": true
  }}
)
```

### 获取群历史消息
```typescript
skill_mcp(
  mcp_name="qq-mcp",
  tool_name="qq_get_group_msg_history",
  arguments={"params": {
    "group_id": "123456789",
    "count": 20
  }}
)
```

### 获取登录账号信息
```typescript
skill_mcp(
  mcp_name="qq-mcp",
  tool_name="qq_get_login_info",
  arguments={"params": {}}
)
```

### 发送戳一戳
```typescript
skill_mcp(
  mcp_name="qq-mcp",
  tool_name="qq_send_poke",
  arguments={"params": {
    "user_id": "123456789"
  }}
)
```

### 发送群聊戳一戳
```typescript
skill_mcp(
  mcp_name="qq-mcp",
  tool_name="qq_send_poke",
  arguments={"params": {
    "user_id": "123456789",
    "group_id": "957134103"
  }}
)
```

### 获取文件信息
```typescript
skill_mcp(
  mcp_name="qq-mcp",
  tool_name="qq_get_file",
  arguments={"params": {
    "file_id": "/abc123..."
  }}
)
```

## 消息段格式

支持OneBot v11标准的消息段格式：

| 类型 | 示例 |
|------|------|
| 纯文本 | `"你好"` 或 `"[{\"type\":\"text\",\"data\":{\"text\":\"你好\"}}]"` |
| @某人 | `"[{\"type\":\"at\",\"data\":{\"qq\":\"123456\"}},{\"type\":\"text\",\"data\":{\"text\":\"内容\"}}]"` |
| 图片 | `"[{\"type\":\"image\",\"data\":{\"file\":\"http://example.com/img.jpg\"}}]"` |
| 表情 | `"[{\"type\":\"face\",\"data\":{\"id\":\"123\"}}]"` |

## 参数说明

### qq_send_message
- `message_type`: 消息类型，`private`(私聊) 或 `group`(群聊)
- `target_id`: 目标ID，QQ号或群号
- `message`: 消息内容，纯文本或消息段JSON字符串

### qq_send_file
- `message_type`: 消息类型，`private`(私聊) 或 `group`(群聊)
- `target_id`: 目标ID，QQ号或群号
- `file_path`: 文件绝对路径
- `custom_name`: 自定义文件名（可选）
- `use_base64`: 是否使用base64编码（默认true，推荐）

### qq_search_friend
- `name`: 搜索关键词（昵称或备注）
- `exact_match`: 是否精确匹配（默认false，模糊匹配）

### qq_get_group_msg_history
- `group_id`: 群号（必填）
- `count`: 消息数量（默认20，最大100）
- `message_seq`: 起始消息序号（可选，用于分页）
- `reverse_order`: 是否倒序显示（默认false）

### qq_get_login_info
- 无参数，返回当前登录账号的QQ号和昵称

### qq_send_poke
- `user_id`: 目标用户QQ号（必填）
- `group_id`: 群号（可选，不填则为私聊戳一戳）

### qq_get_file
- `file_id`: 文件ID（二选一）
- `file`: 文件路径或URL（二选一）
- 返回：文件名、大小、下载URL

## 环境配置

- napcat服务器: ws://localhost:3002
- 认证令牌: CqC5dDMXWGUu6NVh
- 机器人QQ: 3938121220

## 参考链接

- NapCat官方文档: https://napcat.apifox.cn/
- OneBot v11协议: https://github.com/botuniverse/onebot-11