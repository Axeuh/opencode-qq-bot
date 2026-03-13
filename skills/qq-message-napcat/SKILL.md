---
name: qq-message-napcat
description: |
  通过napcat API发送QQ消息和管理QQ好友。当用户想要发送QQ私聊或群聊消息时使用此技能。
  此技能支持：文本消息和富媒体消息（图片、表情等）发送、获取好友列表、通过名称搜索好友、发送表情包、获取陌生人信息。
  基于OneBot v11协议，使用本地napcat服务（ws://localhost:3002）和令牌认证。
compatibility:
  required_tools: ["bash", "write", "read"]
  dependencies: []
---

# QQ消息与好友管理技能（Napcat API）

此技能通过napcat API发送QQ消息和管理QQ好友，支持私聊和群聊消息发送、好友列表获取、好友搜索、表情包发送等功能。napcat是一个基于OneBot v11协议的QQ机器人框架，通过WebSocket API提供服务。

## 重要说明

经过测试发现：
**napcat主要使用WebSocket协议**
如果连接正常，那就是账号被踢下线了

技能提供了完整的WebSocket实现，但实际使用前需要确保：
- napcat服务正确配置并运行
- 目标用户是机器人的好友（对于私聊消息）
- 机器人有发送消息的权限

## 何时使用此技能

当以下情况时使用此技能：

- 用户想要发送QQ私聊消息
- 用户想要发送QQ群聊消息  
- 用户提到要给QQ好友或QQ群发送消息
- 用户需要在自动化任务中发送QQ通知
- 用户想要发送包含图片、表情等富媒体内容的QQ消息
- 用户想要获取QQ好友列表
- 用户想要通过名称搜索QQ好友
- 用户想要发送表情包（内置表情或图片表情）
- 用户想要查询QQ用户的基本信息

## 脚本选择

根据功能需求，提供四个WebSocket版本脚本：

1. **WebSocket基础版本** - `send_qq_message_ws.py`
   - 仅包含消息发送功能
   - 使用WebSocket连接，支持实时双向通信
   - 适合只发送消息的场景

2. **WebSocket文件发送版本** - `send_file_ws.py`
   - 专门用于发送文件到QQ（私聊或群聊）
   - 支持base64编码上传和file://协议
   - **新增**：自动Windows路径到WSL路径转换，支持跨系统部署（Windows bot + WSL NapCat）
   - 适合发送文件、文档、配置文件等

3. **WebSocket图片发送版本** - `send_image_ws.py`
   - 专门用于发送图片到QQ（私聊或群聊）
   - 支持base64编码和file://协议
   - **新增**：自动Windows路径到WSL路径转换，支持跨系统部署
   - 适合发送图片、截图、照片等

4. **WebSocket工具版本（推荐，功能完整）** - `qq_tools_ws.py`
   - 使用WebSocket连接，支持所有扩展功能
   - 包含消息发送、好友列表获取、好友搜索、表情发送、陌生人信息查询、文件发送、图片发送
   - 向后兼容原消息发送功能
   - 支持多种输出格式（文本、JSON、表格）
   - **新增**：文件发送和图片发送支持Windows到WSL路径转换

根据需求选择脚本：
- 仅发送消息：`send_qq_message_ws.py`
- 发送文件（特别是跨系统场景）：`send_file_ws.py`
- 发送图片（特别是跨系统场景）：`send_image_ws.py`
- 需要完整功能（好友管理、搜索等）：`qq_tools_ws.py`

## 使用WebSocket基础脚本

### 脚本位置
```
C:\Users\Administrator\.config\opencode\skills\qq-message-napcat\scripts\send_qq_message_ws.py
```

### 基本使用
```bash
python C:\Users\Administrator\.config\opencode\skills\qq-message-napcat\scripts\send_qq_message_ws.py --type private --target 123456789 --message "你好，这是一条测试消息"
```

### 所有可用参数
```
--type, -t       必需: 消息类型 (private/group)
--target, -T     必需: 目标ID (QQ号或群号)
--message, -m    必需: 消息内容 (文本或消息段数组的JSON字符串)
--auto-escape, -a 可选: 是否自动转义CQ码 (默认: false)
--server, -s     可选: napcat服务器地址 (默认: ws://127.0.0.1:3001)
--token, -k      可选: 认证令牌
--timeout, -o    可选: 超时时间（秒） (默认: 30)
--verbose, -v    可选: 详细输出
--quiet, -q      可选: 静默模式，只输出错误
--json, -j      可选: JSON格式输出
```

### 消息格式

#### 简单文本消息
对于纯文本消息，可以直接传递字符串：
```bash
python send_qq_message_ws.py --type private --target 123456789 --message "你好，这是一条纯文本消息"
```

#### OneBot消息段格式（推荐）
消息也可以是OneBot v11标准消息段数组的JSON字符串：
```bash
python send_qq_message_ws.py --type private --target 123456789 --message '[{"type":"text","data":{"text":"你好，"}},{"type":"text","data":{"text":"这是一条测试消息"}}]'
```

#### 消息段类型示例
**文本消息**
```json
[{"type": "text", "data": {"text": "Hello, World!"}}]
```

**图片消息**
```json
[
  {"type": "text", "data": {"text": "查看这张图片："}},
  {"type": "image", "data": {"file": "http://example.com/image.jpg"}}
]
```

**At某人（群聊中）**
```json
[
  {"type": "at", "data": {"qq": "123456"}},
  {"type": "text", "data": {"text": "请查看这条消息"}}
]
```

 **表情**
```json
[
  {"type": "text", "data": {"text": "发送一个表情："}},
  {"type": "face", "data": {"id": "123"}}
]
```

## 使用WebSocket文件发送脚本

### 脚本位置
```
C:\Users\Administrator\.config\opencode\skills\qq-message-napcat\scripts\send_file_ws.py
```

### 基本使用
```bash
# 发送私聊文件（使用base64编码，推荐）
python send_file_ws.py --type private --target 123456789 --file "D:\\path\\to\\file.xlsx"

# 发送群聊文件
python send_file_ws.py --type group --target 123456789 --file "D:\\path\\to\\file.xlsx"

# 自定义文件名
python send_file_ws.py --type private --target 123456789 --file "D:\\path\\to\\file.xlsx" --name "自定义文件名.xlsx"

# 使用file://协议（启用WSL路径转换，适合跨系统部署）
python send_file_ws.py --type private --target 123456789 --file "D:\\path\\to\\file.xlsx" --no-base64 --verbose
```

### 所有可用参数
```
--type, -t       必需: 消息类型 (private/group)
--target, -T     必需: 目标ID (QQ号或群号)
--file, -f       必需: 文件路径
--name           可选: 自定义文件名
--no-base64      可选: 不使用base64编码（使用file://协议）
--no-wsl-convert 可选: 禁用Windows路径到WSL路径的自动转换
--server, -s     可选: napcat服务器地址（默认: ws://localhost:3002）
--token, -k      可选: 认证令牌
--timeout, -o    可选: 超时时间（秒）（默认: 30）
--verbose, -v    可选: 详细输出
--quiet, -q      可选: 静默模式，只输出错误
--json, -j      可选: JSON格式输出
```

### Windows到WSL路径转换功能

当NapCat运行在WSL中而bot运行在Windows上时，文件路径访问成为问题。`send_file_ws.py` 脚本提供了自动路径转换功能：

**转换规则**:
- `D:\Users\Axeuh\...` → `/mnt/d/Users/Axeuh/...`
- `C:\Windows\...` → `/mnt/c/Windows/...`
- 其他盘符类似转换

**使用场景**:
1. **跨系统部署**: Windows bot + WSL NapCat
2. **文件共享**: 直接发送Windows上的文件，无需复制到WSL
3. **简化配置**: 用户只需提供Windows路径，脚本自动处理转换

**注意事项**:
- 默认启用路径转换（当使用`--no-base64`时）
- 使用`--no-wsl-convert`可禁用转换（当NapCat可以直接访问Windows路径时）
- 确保WSL中已正确挂载Windows驱动器（`/mnt/c/`, `/mnt/d/`等）

### 发送模式选择

1. **base64编码模式（默认）**:
   - 文件内容编码为base64字符串传输
   - 不依赖文件路径，最可靠
   - 适合中小文件（<50MB）

2. **file://协议模式（配合WSL路径转换）**:
   - 使用`file://`协议引用文件路径
   - 需要NapCat可以访问文件路径
   - 启用`--no-base64`自动进行路径转换
   - 适合大文件或跨系统部署

## 使用WebSocket图片发送脚本

### 脚本位置
```
C:\Users\Administrator\.config\opencode\skills\qq-message-napcat\scripts\send_image_ws.py
```

### 基本使用
```bash
# 发送私聊图片（使用base64编码，推荐）
python send_image_ws.py --type private --target 123456789 --image-file "D:\\path\\to\\image.jpg"

# 发送群聊图片
python send_image_ws.py --type group --target 123456789 --image-file "D:\\path\\to\\image.jpg"

# 使用file://协议（启用WSL路径转换，适合跨系统部署）
python send_image_ws.py --type private --target 123456789 --image-file "D:\\path\\to\\image.jpg" --base64
```

### 所有可用参数
```
--type, -t       必需: 消息类型 (private/group)
--target, -T     必需: 目标ID (QQ号或群号)
--image-file, -i 必需: 图片文件路径
--base64, -b     可选: 使用base64编码发送（解决路径访问问题）
--server, -s     可选: napcat服务器地址（默认: ws://localhost:3002）
--token, -k      可选: 认证令牌
--timeout, -o    可选: 超时时间（秒）（默认: 30）
--verbose, -v    可选: 详细输出
--quiet, -q      可选: 静默模式，只输出错误
--json, -j      可选: JSON格式输出
```

### Windows到WSL路径转换功能

与文件发送脚本类似，`send_image_ws.py` 也支持自动Windows路径到WSL路径转换：

**转换规则**:
- `D:\Users\Axeuh\...` → `/mnt/d/Users/Axeuh/...`
- `C:\Windows\...` → `/mnt/c/Windows/...`
- 其他盘符类似转换

**使用场景**:
1. **跨系统部署**: Windows bot + WSL NapCat
2. **图片共享**: 直接发送Windows上的图片，无需复制到WSL
3. **简化配置**: 用户只需提供Windows路径，脚本自动处理转换

**注意事项**:
- 当不使用`--base64`参数时，默认使用file://协议，自动启用路径转换
- 使用`--base64`参数时，图片内容编码在请求中，无路径访问问题
- 确保WSL中已正确挂载Windows驱动器（`/mnt/c/`, `/mnt/d/`等）

### 发送模式选择

1. **base64编码模式**:
   - 使用`--base64`参数启用
   - 图片内容编码为base64字符串传输
   - 不依赖文件路径，最可靠
   - 适合中小图片（<5MB）

2. **file://协议模式（配合WSL路径转换）**:
   - 默认模式（不使用`--base64`参数）
   - 使用`file://`协议引用图片路径
   - 需要NapCat可以访问文件路径
   - 自动进行Windows到WSL路径转换
   - 适合大图片或跨系统部署

## 使用WebSocket工具脚本

## API直接调用方法

如果你需要在Python代码中直接调用API：

## 使用示例

### 示例1：发送简单私聊消息

```bash
python C:\Users\Administrator\.config\opencode\skills\qq-message-napcat\scripts\send_qq_message_ws.py \
  --type private \
  --target 123456789 \
  --message "任务完成通知：数据处理已完成"
```

### 示例2：发送带图片的群聊消息

```bash
python C:\Users\Administrator\.config\opencode\skills\qq-message-napcat\scripts\send_qq_message_ws.py \
  --type group \
  --target 123456789 \
  --message '[{"type":"text","data":{"text":"今日报表："}},{"type":"image","data":{"file":"http://example.com/report.png"}}]'
```

### 示例3：At群成员

```bash
python C:\Users\Administrator\.config\opencode\skills\qq-message-napcat\scripts\send_qq_message_ws.py \
  --type group \
  --target 123456789 \
  --message '[{"type":"at","data":{"qq":"123456789"}},{"type":"text","data":{"text":"请查看最新通知"}}]'
```

### 示例4：发送复合消息（文本+表情）

```bash
python C:\Users\Administrator\.config\opencode\skills\qq-message-napcat\scripts\send_qq_message_ws.py \
  --type private \
  --target 123456789 \
  --message '[{"type":"text","data":{"text":"任务完成"}},{"type":"face","data":{"id":"123"}}]'
```

## 扩展功能（QQ工具脚本）

除了基本的消息发送功能外，此技能还提供了一个功能更全面的QQ工具脚本 `qq_tools_ws.py`，支持以下扩展功能：

1. **发送私聊和群聊消息** - 与原脚本兼容
2. **获取好友列表** - 查看所有QQ好友信息（支持缓存）
3. **通过名称搜索QQ好友** - 根据昵称或备注搜索好友（支持缓存）
4. **发送表情包** - 发送内置表情或图片表情
5. **获取陌生人信息** - 查询任意QQ用户的基本信息
6. **批量消息发送** - 一次发送消息给多个目标
7. **获取群列表** - 查看机器人加入的所有群组
8. **自动重连机制** - 连接断开时自动重连，提高稳定性
9. **好友列表缓存** - 减少API调用，提高响应速度（默认60秒缓存）
10. **发送文件** - 支持私聊和群聊文件发送，支持base64编码和file://协议，**自动Windows到WSL路径转换**
11. **发送图片** - 支持私聊和群聊图片发送，支持base64编码和file://协议，**自动Windows到WSL路径转换**

### 脚本位置

```
C:\Users\Administrator\.config\opencode\skills\qq-message-napcat\scripts\qq_tools_ws.py
```

### 基本使用

```bash
# 查看帮助
python C:\Users\Administrator\.config\opencode\skills\qq-message-napcat\scripts\qq_tools_ws.py --help
```

### 功能示例

#### 1. 发送消息（与原脚本兼容）

```bash
# 发送私聊消息
python qq_tools_ws.py --action send --type private --target 123456789 --message "测试消息"

# 发送群聊消息  
python qq_tools_ws.py --action send --type group --target 123456789 --message "群聊测试"
```

#### 2. 获取好友列表

```bash
# 获取好友列表（文本格式）
python qq_tools_ws.py --action get-friends --verbose

# 获取好友列表（JSON格式）
python qq_tools_ws.py --action get-friends --output-format json

# 获取好友列表（表格格式）
python qq_tools_ws.py --action get-friends --output-format table
```

输出示例：
```
[OK] 获取好友列表成功，共 3 个好友
  1. 123456789 - Axeuh_nya (备注名)
  2. 123456789 - Axeuh
  3. 123456789 - AӨo
```

#### 3. 通过名称搜索好友

```bash
# 模糊搜索（默认）
python qq_tools_ws.py --action search-friend --name "Axeuh"

# 精确匹配
python qq_tools_ws.py --action search-friend --name "Axeuh" --exact
```

输出示例：
```
[OK] 搜索好友成功，找到 2 个匹配 'Axeuh' 的好友
  1. 123456789 - Axeuh_nya (备注名)
  2. 123456789 - Axeuh
```

#### 4. 发送表情包

```bash
# 发送内置表情（face_id为表情ID）
python qq_tools_ws.py --action send-face --target 123456789 --face-id 14

# 发送图片表情（file://协议）
python qq_tools_ws.py --action send-image --target 123456789 --image-url "file:///path/to/image.jpg"

# 发送群聊表情
python qq_tools_ws.py --action send-face --type group --target 123456789 --face-id 123
```

> **注意**：表情发送功能依赖于napcat的CQ码支持。某些face_id可能不被支持，或需要特定的napcat版本。
>
> **群聊权限说明**：发送群聊消息和表情需要机器人在该群聊中有发送消息的权限。如果机器人被移出群聊或权限受限，会返回错误码110。

#### 5. 获取陌生人信息

```bash
# 获取陌生人信息
python qq_tools_ws.py --action get-stranger --user-id 123456789

# 不使用缓存
python qq_tools_ws.py --action get-stranger --user-id 123456789 --no-cache
```

输出示例：
```
[OK] 获取陌生人信息成功
  QQ号: 123456789
  昵称: Axeuh_nya (备注名)
  性别: unknown
  年龄: 18
```

### 所有可用参数

```
--action, -a        执行的动作: send, get-friends, search-friend, send-face, send-image, get-stranger
--type, -t          消息类型: private(私聊) 或 group(群聊) - action=send时使用
--target, -T        目标ID: QQ号(私聊) 或 群号(群聊) - 多个action使用
--message, -m       消息内容: 可以是纯文本或OneBot消息段数组的JSON字符串 - action=send时使用
--auto-escape, -e   是否自动转义CQ码（默认: False）- action=send时使用
--name, -n          搜索关键词（昵称或备注）- action=search-friend时使用
--exact             精确匹配（默认模糊匹配）- action=search-friend时使用
--face-id, -f       表情ID - action=send-face时使用
--image-url, -i     图片URL或文件路径（file://协议）- action=send-image时使用
--user-id, -u       要查询的QQ号 - action=get-stranger时使用
--no-cache          不使用缓存 - action=get-stranger时使用
--output-format     输出格式: text, json, table（默认: text）
--server, -s        napcat服务器地址（默认: ws://localhost:3002）
--token, -k         认证令牌（默认: CqC5dDMXWGUu6NVh）
--timeout, -o       超时时间（秒）（默认: 30）
--verbose, -v       详细输出
--quiet, -q         静默模式，只输出错误
--json, -j          JSON格式输出
```

### 技术实现

扩展功能基于OneBot v11 API实现：

- `get_friend_list` - 获取好友列表
- `get_stranger_info` - 获取陌生人信息
- `send_private_msg` / `send_group_msg` - 发送消息（支持表情CQ码）

搜索功能在获取好友列表后在本地实现，因为OneBot v11没有直接的名称搜索API。

## 错误处理

常见错误及解决方法：

- **401 Unauthorized**: 认证令牌错误或缺失 - 检查Authorization头
- **404 Not Found**: API端点不存在 - 检查服务器地址和端口
- **400 Bad Request**: 请求参数错误 - 检查消息格式和目标ID
- **500 Internal Server Error**: 服务器内部错误 - napcat服务可能未运行
- **连接拒绝**: napcat服务未启动或端口被占用 - 检查napcat服务状态
- **错误码1006514 (网络连接异常)**: napcat的QQ端被腾讯踢下线或网络断开 - 重新登录QQ账号，重启napcat服务
- **错误码1006514 (参数异常)**: 消息参数格式错误或目标用户限制 - 检查参数格式，确认目标用户是否为好友
- **错误码110**: 群聊消息发送失败，机器人被移出群聊 - 重新将机器人加入群聊或检查群聊权限
- **表情发送失败**: 某些表情ID可能不被支持或需要特定napcat版本 - 尝试不同的face_id或检查napcat版本
- **群聊功能受限**: 机器人可能没有群聊消息发送权限或被限制 - 检查机器人权限和群聊设置
- **API响应超时**: WebSocket连接超时或napcat服务响应慢 - 增加timeout参数或检查网络连接

### 检查napcat服务状态

```bash
# 检查服务是否运行
curl -H "Authorization: Bearer CqC5dDMXWGUu6NVh" http://localhost:3002/get_status
```

## 最佳实践

1. **消息频率控制**: 避免过快发送消息，以免被QQ风控
2. **错误重试**: 对于临时性错误，建议实现重试机制
3. **日志记录**: 记录所有发送的消息和结果，便于排查问题
4. **异步发送**: 对于大量消息，考虑使用异步方式发送
5. **内容安全**: 确保发送的内容符合法律法规和QQ平台规则

## 参考链接

- NapCat官方文档: https://napcat.apifox.cn/
- OneBot v11协议: https://github.com/botuniverse/onebot-11
- NapCat GitHub: https://github.com/NapNeko/NapCatQQ
