# 测试架构

**生成时间：** 2026-03-12
**测试文件：** 10 个 Python 测试脚本
**测试模式：** 自定义脚本化测试，集成测试导向，日志驱动

## 测试架构概览

### 无传统测试框架
- 不使用 pytest/unittest/jest
- 无 `conftest.py` 或测试配置文件
- 无断言驱动测试模式

### 自定义测试模式
- 独立可运行脚本 (`python test_xxx.py`)
- 集成测试导向（连接真实服务）
- 异步优先（使用 `asyncio`）
- 日志驱动（通过 logging 输出结果）
- 手动验证（部分测试需人工检查QQ回复）

## 测试文件分类

### 核心测试脚本 (4个文件)
| 文件 | 用途 | 测试内容 |
|------|------|----------|
| `test_commands.py` | **自动化命令测试** | 测试 10 个核心机器人命令 |
| `debug_interface.py` | **调试接口类** | 模拟 QQ 消息，集成测试基础 |
| `test_connection.py` | **连接测试** | WebSocket 连接和基本功能 |
| `test_session_manager_basic.py` | **会话管理器基础测试** | 会话持久化和超时清理验证 |

### API 测试 (4个文件)
| 文件 | 用途 | 测试内容 |
|------|------|----------|
| `test_http_api.py` | HTTP API 集成测试 | NapCat HTTP API 功能 |
| `test_get_msg.py` | get_msg API 测试 | 消息获取功能 |
| `test_get_msg_enhanced.py` | get_msg 增强测试 | 扩展的消息获取测试 |
| `test_get_msg_validation.py` | get_msg 验证测试 | 消息验证逻辑 |

### 代码质量测试 (1个文件)
| 文件 | 用途 | 测试内容 |
|------|------|----------|
| `test_lsp_config.py` | LSP配置测试 | Python类型检查和导入验证 |

## 核心测试组件

### DebugInterface 类 (`debug_interface.py`)
```python
class DebugInterface:
    """调试接口类，用于模拟 QQ 消息测试"""
    
    async def initialize(self):
        """初始化机器人客户端和 OpenCode 集成"""
        self.client = OneBotClient()
        await self.client.initialize()
        
    async def send_private_message(self, user_id: int, message: str):
        """发送模拟私聊消息"""
        return await self.client._handle_private_message(user_id, message)
        
    async def send_group_message(self, group_id: int, user_id: int, message: str):
        """发送模拟群聊消息"""
        return await self.client._handle_group_message(group_id, user_id, message)
```

### 测试运行模式
```bash
# 独立运行测试
python tests/test_commands.py
python tests/test_connection.py
python tests/test_http_api.py

# 使用调试接口
from debug_interface import DebugInterface
debug = DebugInterface()
await debug.initialize()
await debug.send_private_message(123456789, "/help")
```

## 测试覆盖范围

### 命令测试 (10个命令)
`test_commands.py` 自动化测试以下命令：
1. `/help` - 帮助命令
2. `/new` - 创建新会话
3. `/session ses_test123` - 切换会话
4. `/agents` - 列出智能体
5. `/model deepseek/deepseek-reasoner` - 切换模型
6. `/stop` - 停止当前会话（调用 `abort_session`）
7. `/undo` - 撤销最后一条消息（调用 `revert_last_message`）
8. `/redo` - 恢复所有撤销消息（调用 `unrevert_messages`）
9. `/reload` - 重新加载配置
10. `/reload restart` - 重启机器人

### 连接测试
- WebSocket 连接 NapCat 服务器
- HTTP API 连接和认证
- 自动重连机制
- 心跳包功能

### API 测试
- get_msg API 正确性
- 图片消息获取和处理
- 引用消息功能
- 错误处理和超时

## 测试结果报告

### 自动化报告 (`test_commands.py`)
```python
# 测试报告输出示例
logger.info("命令功能测试报告")
logger.info(f"总计测试：{total_tests}")
logger.info(f"通过：{passed_tests}")
logger.info(f"失败：{failed_tests}")
logger.info(f"成功率：{success_rate:.1f}%")
```

### 日志驱动测试
```python
# 测试通过标准：无异常 + 日志输出正确
try:
    result = await debug.send_private_message(user_id, "/help")
    if result:
        logger.info("/help 命令测试通过")
        passed += 1
    else:
        logger.error("/help 命令测试失败")
        failed += 1
except Exception as e:
    logger.error(f"/help 命令测试异常: {e}")
    failed += 1
```

## 测试依赖

### 运行时依赖
```
aiohttp>=3.9.0      # HTTP/WebSocket 客户端
PyYAML>=6.0         # 配置文件解析
requests>=2.31.0    # HTTP 请求库
```

### 服务依赖
- **NapCat WebSocket**: `ws://localhost:3002`
- **NapCat HTTP API**: `http://localhost:3001`
- **OpenCode 服务**: `http://127.0.0.1:4091`

## 测试流程建议

### 1. 基础功能测试
```bash
# 运行所有命令测试（核心功能）
python tests/test_commands.py

# 测试连接功能
python tests/test_connection.py
```

### 2. 特定功能测试
```python
# 自定义测试脚本示例
from debug_interface import DebugInterface

async def test_specific_feature():
    debug = DebugInterface()
    await debug.initialize()
    
    # 测试特定功能
    await debug.send_private_message(123456789, "/new 测试会话")
    await debug.send_private_message(123456789, "测试消息")
    await debug.send_private_message(123456789, "/stop")
    
    # 检查日志输出
    print("测试完成，请检查日志确认结果")
```

### 3. 集成测试
```bash
# 测试 HTTP API 集成
python tests/test_http_api.py

# 测试消息获取功能
python tests/test_get_msg.py
```

## 调试技巧

### 日志分析
```bash
# 查看测试日志
tail -f logs/onebot_client.log

# 过滤测试相关日志
grep -i "test\|debug\|error" logs/onebot_client.log
```

### 服务状态检查
```python
# 检查服务可用性
async def check_services():
    # 检查 NapCat WebSocket
    ws_status = await check_websocket("ws://localhost:3002")
    
    # 检查 NapCat HTTP API
    http_status = await check_http_api("http://localhost:3001")
    
    # 检查 OpenCode 服务
    opencode_status = await check_opencode("http://127.0.0.1:4091")
    
    return all([ws_status, http_status, opencode_status])
```

## 扩展测试

### 添加新测试
1. **复制模板**：参考现有测试脚本结构
2. **使用 DebugInterface**：通过调试接口发送测试消息
3. **日志验证**：通过日志输出判断测试结果
4. **结果报告**：输出清晰的测试报告

### 测试数据管理
```python
# 测试数据示例
TEST_USERS = [123456789, 123456789]
TEST_GROUPS = [123456789, 123456789]
TEST_MESSAGES = [
    ("/help", "帮助命令"),
    ("/new", "创建会话"),
    ("你好", "普通消息"),
]
```

## 注意事项

### 测试环境
- 需要运行中的 NapCat 服务
- 需要运行中的 OpenCode 服务
- 测试用户需要在白名单中
- 避免在生产环境运行测试

### 测试稳定性
- 网络依赖可能导致测试失败
- 服务状态变化影响测试结果
- 部分测试需要人工验证（检查QQ回复）

### 性能考虑
- 测试应避免频繁发送消息（触发QQ风控）
- 合理设置超时时间
- 使用异步避免阻塞