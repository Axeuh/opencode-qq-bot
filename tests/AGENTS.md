# 测试架构

**生成日期:** 2026-03-25
**文件数:** 17 Python 测试脚本
**框架:** 自定义 (无 pytest/unittest)

## 目录结构

```
tests/
├── test_commands.py           # 命令测试 (10 个命令)
├── test_connection.py         # WebSocket 连接测试
├── test_http_api.py           # HTTP API 测试
├── test_session_manager_basic.py
├── debug_interface.py         # 测试工具类
├── test_get_msg*.py           # 消息 API 测试 (4 个文件)
├── test_file*.py              # 文件处理测试 (2 个文件)
├── test_get_forward_msg.py    # 转发消息测试
└── test_lsp_config.py         # LSP 配置测试
```

## 测试模式

### 无传统框架
- 不使用 pytest、unittest 或 jest
- 每个文件独立运行: `python test_xxx.py`
- 集成测试 (连接真实服务)
- 基于日志的验证

### DebugInterface 类

```python
from debug_interface import DebugInterface

debug = DebugInterface()
await debug.initialize()
await debug.send_private_message(user_id, "/help")
await debug.close()
```

## 查找指南

| 任务 | 位置 |
|------|----------|
| 测试命令 | test_commands.py |
| 测试连接 | test_connection.py |
| 模拟 QQ 消息 | debug_interface.py |
| 测试文件处理 | test_file*.py |
| 测试 HTTP API | test_http_api.py |

## 服务依赖

测试需要运行以下服务:
- NapCat WebSocket: `ws://localhost:3002`
- NapCat HTTP API: `http://localhost:3001`
- OpenCode 服务: `http://127.0.0.1:4091`

## 运行测试

```bash
python tests/test_commands.py
python tests/test_connection.py
python tests/test_http_api.py
```

## 编码规范

- 所有测试使用 `asyncio.run()`
- 使用 `logging` 模块记录结果
- 返回 `(success, message)` 元组
- 部分测试需要人工验证 (检查 QQ 回复)

## 测试覆盖

| 模块 | 测试文件 |
|--------|-----------|
| 命令 | test_commands.py |
| 连接 | test_connection.py |
| HTTP API | test_http_api.py |
| 会话 | test_session_manager_basic.py |
| 文件处理 | test_file_download_api.py |
| 转发消息 | test_get_forward_msg.py |
| 进程管理 | 通过 HTTP 端点手动测试 |

## 进程管理测试

```bash
# 检查系统状态
curl http://localhost:8080/api/system/status

# 重启 OpenCode
curl -X POST http://localhost:8080/api/system/restart/opencode

# 重启 Bot (触发会话保存/恢复)
curl -X POST http://localhost:8080/api/system/restart/bot
```

### 测试检查清单

- [ ] OpenCode 重启后保持会话状态
- [ ] Bot 重启保存活跃会话
- [ ] PID 文件正确追踪 OpenCode 进程
- [ ] 异步会话恢复向所有会话发送 "继续"
- [ ] SSE 监听在重启前停止 (端口释放)