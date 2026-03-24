# mybot-web 项目重构计划

**创建时间:** 2026-03-24
**负责人:** Sisyphus (主协调器)
**重构目标:** 优化代码结构，提高可维护性和可测试性

---

## 项目概况

| 指标 | 数值 |
|------|------|
| 总代码量 | 18,105 行 |
| Python 文件 | 55 个 |
| 核心模块 | src/core/ (29 个文件, 63.7%) |
| 测试覆盖率 | ~25% |
| 架构评分 | 3.4/5 |

---

## 重构阶段划分

### Phase 1: 拆分过大文件 (优先级: 高)

**目标:** 将 9 个超过 500 行的文件拆分为职责单一的小模块

| 文件 | 当前行数 | 目标行数 | 负责智能体 |
|------|----------|----------|------------|
| http_server.py | 2313 | ~400 (拆分为 5 个文件) | Agent-HTTP |
| session_manager.py | 1355 | ~400 (拆分为 3 个文件) | Agent-Session |
| opencode_client.py | 1102 | ~400 (拆分为 3 个文件) | Agent-OpenCode |
| command_system.py | 1007 | ~400 (拆分为 4 个文件) | Agent-Command |
| file_handler.py | 932 | ~400 (拆分为 3 个文件) | Agent-File |
| message_router.py | 731 | ~400 (拆分为 2 个文件) | Agent-Router |
| http_callbacks.py | 682 | ~400 (拆分为 2 个文件) | Agent-HTTP |
| opencode_integration.py | 550 | ~400 (拆分为 2 个文件) | Agent-OpenCode |
| connection_manager.py | 533 | 保持不变 | - |

### Phase 2: 重构过长函数 (优先级: 高)

**目标:** 将 13 个超过 100 行的函数拆分为小函数

| 函数 | 当前行数 | 文件 | 目标 |
|------|----------|------|------|
| handle_command_command() | 217 | command_system.py | 拆分为 5 个子函数 |
| forward_to_opencode() | 196 | opencode_integration.py | 拆分为 4 个子函数 |
| load_from_file() | 135 | session_manager.py | 拆分为 3 个子函数 |
| handle_login() | 129 | http_server.py | 拆分为 3 个子函数 |
| handle_upload() | 130 | http_server.py | 拆分为 3 个子函数 |
| start() | 111 | http_server.py | 拆分为 2 个子函数 |
| handle_set_password() | 100 | http_server.py | 拆分为 2 个子函数 |

### Phase 3: 代码质量优化 (优先级: 中)

**目标:** 统一代码风格，消除重复代码

- 消除 11 个重复代码块
- 统一错误处理（使用 logger.exception()）
- 修复 2 个裸 except 子句
- 统一日志格式

### Phase 4: 测试覆盖提升 (优先级: 中)

**目标:** 提高测试覆盖率到 50%+

- 引入 pytest 框架
- 为重构后的模块添加单元测试
- 建立 CI/CD 测试流水线

---

## 智能体分工详情

### Agent-HTTP: 拆分 http_server.py

**输入文件:** `src/core/http_server.py` (2313 行)

**输出文件:**
```
src/core/http/
    __init__.py
    server.py           (~200 行) - HTTPServer 核心类
    routes.py           (~100 行) - 路由定义
    auth_handler.py     (~200 行) - 认证处理 (handle_login, handle_set_password, handle_change_password)
    session_endpoints.py (~300 行) - 会话端点 (handle_session_list, handle_session_switch, handle_session_delete)
    task_endpoints.py   (~300 行) - 任务端点 (handle_create_task, handle_update_task, handle_delete_task)
    config_endpoints.py (~200 行) - 配置端点 (handle_set_model, handle_set_agents, handle_set_directory)
    upload_handler.py   (~200 行) - 文件上传 (handle_upload)
```

**详细任务:**

1. 创建 `src/core/http/` 目录
2. 提取 HTTPServer 类核心逻辑到 `server.py`
3. 提取路由定义到 `routes.py`
4. 按功能拆分处理器:
   - `auth_handler.py`: 登录、密码管理
   - `session_endpoints.py`: 会话 CRUD
   - `task_endpoints.py`: 任务 CRUD
   - `config_endpoints.py`: 配置管理
   - `upload_handler.py`: 文件上传

**注意事项:**
- 保持 HTTPServer 类的公共 API 不变
- 回调函数列表保持不变
- 导入路径需要更新: `from src.core.http import HTTPServer`
- 测试文件需要更新导入

**验证方式:**
```bash
python -c "from src.core.http import HTTPServer; print('OK')"
python tests/test_http_api.py
```

---

### Agent-Session: 拆分 session_manager.py

**输入文件:** `src/session/session_manager.py` (1355 行)

**输出文件:**
```
src/session/
    __init__.py
    session_manager.py  (~400 行) - SessionManager 核心类
    user_session.py     (~200 行) - UserSession 数据类
    user_config.py      (~200 行) - UserConfig 数据类
    persistence.py      (~300 行) - 文件持久化逻辑
```

**详细任务:**

1. 提取 UserSession 类到 `user_session.py`
2. 提取 UserConfig 类到 `user_config.py`
3. 提取文件持久化逻辑到 `persistence.py`
4. 保留 SessionManager 核心逻辑在 `session_manager.py`

**注意事项:**
- 保持 `get_session_manager()` 单例模式
- 数据文件格式不变 (data/sessions.json)
- 导入路径更新: `from src.session import SessionManager, UserSession, UserConfig`

**验证方式:**
```bash
python -c "from src.session import SessionManager, UserSession, UserConfig; print('OK')"
python tests/test_session_manager_basic.py
```

---

### Agent-OpenCode: 拆分 opencode_client.py 和 opencode_integration.py

**输入文件:**
- `src/opencode/opencode_client.py` (1102 行)
- `src/core/opencode_integration.py` (550 行)

**输出文件:**
```
src/opencode/
    __init__.py
    client.py           (~300 行) - OpenCodeClient 核心类
    session_api.py      (~200 行) - 会话相关 API
    message_api.py      (~200 行) - 消息相关 API
    model_api.py        (~150 行) - 模型/智能体 API

src/core/
    opencode_integration.py (~200 行) - 简化后的集成层
    opencode_forwarder.py   (~200 行) - 消息转发逻辑
```

**详细任务:**

1. 按功能拆分 OpenCodeClient:
   - `client.py`: 基础 HTTP 客户端
   - `session_api.py`: create_session, abort_session, revert_last_message
   - `message_api.py`: send_message, get_models, get_agents
   - `model_api.py`: 模型切换相关
2. 拆分 opencode_integration.py:
   - 提取 forward_to_opencode() 到 `opencode_forwarder.py`

**注意事项:**
- 保持 OpenCodeClient 的公共 API 不变
- 异步方法签名保持不变
- 注意处理异步上下文

**验证方式:**
```bash
python -c "from src.opencode import OpenCodeClient; print('OK')"
```

---

### Agent-Command: 拆分 command_system.py

**输入文件:** `src/core/command_system.py` (1007 行)

**输出文件:**
```
src/core/command/
    __init__.py
    command_system.py   (~200 行) - CommandSystem 核心类
    help_handler.py     (~50 行) - /help 命令
    session_handler.py  (~200 行) - /new, /session, /stop 命令
    model_handler.py    (~150 行) - /model, /agents 命令
    task_handler.py     (~200 行) - /command, /directory 命令
    message_handler.py  (~150 行) - /undo, /redo, /compact 命令
```

**详细任务:**

1. 创建 `src/core/command/` 目录
2. 按命令类型拆分处理器
3. 重构过长函数 `handle_command_command()`:
   - 提取命令解析逻辑
   - 提取错误处理逻辑
   - 提取响应构建逻辑

**注意事项:**
- 命令列表保持不变 (12 个命令)
- 回调函数签名保持不变
- 错误消息格式统一

**验证方式:**
```bash
python tests/test_commands.py
```

---

### Agent-File: 拆分 file_handler.py

**输入文件:** `src/core/file_handler.py` (932 行)

**输出文件:**
```
src/core/file/
    __init__.py
    file_handler.py     (~200 行) - FileHandler 核心类
    downloader.py       (~300 行) - 文件下载逻辑
    path_resolver.py    (~200 行) - 路径解析和 WSL 转换
    validator.py        (~150 行) - 文件验证
```

**详细任务:**

1. 创建 `src/core/file/` 目录
2. 提取文件下载逻辑到 `downloader.py`
3. 提取路径解析逻辑到 `path_resolver.py`
4. 提取文件验证逻辑到 `validator.py`

**注意事项:**
- 三层回退机制保持不变
- WSL 路径转换逻辑保持不变
- 文件下载目录配置保持不变

**验证方式:**
```bash
python tests/test_file_handler_api.py
```

---

### Agent-Router: 拆分 message_router.py

**输入文件:** `src/core/message_router.py` (731 行)

**输出文件:**
```
src/core/router/
    __init__.py
    message_router.py   (~400 行) - MessageRouter 核心类
    message_processor.py (~300 行) - 消息处理逻辑
```

**详细任务:**

1. 创建 `src/core/router/` 目录
2. 提取消息处理逻辑到 `message_processor.py`
3. 重构过长函数 `_process_files_in_records()`:
   - 提取文件遍历逻辑
   - 提取文件下载逻辑
   - 提取结果构建逻辑

**注意事项:**
- 白名单检查逻辑保持不变
- 命令识别逻辑保持不变
- 消息转发逻辑保持不变

**验证方式:**
```bash
python -c "from src.core.router import MessageRouter; print('OK')"
```

---

## 执行顺序

```
Phase 1 (并行执行):
    ├── Agent-HTTP: 拆分 http_server.py
    ├── Agent-Session: 拆分 session_manager.py
    ├── Agent-OpenCode: 拆分 opencode_client.py + opencode_integration.py
    ├── Agent-Command: 拆分 command_system.py
    ├── Agent-File: 拆分 file_handler.py
    └── Agent-Router: 拆分 message_router.py
         │
         ▼
    验证点: 所有测试通过，导入正常
         │
         ▼
Phase 2 (串行执行):
    ├── 重构过长函数 (13 个)
    └── 消除重复代码 (11 个代码块)
         │
         ▼
    验证点: 所有测试通过，功能正常
         │
         ▼
Phase 3 (并行执行):
    ├── 统一错误处理
    └── 统一日志格式
         │
         ▼
    验证点: 代码审查通过
         │
         ▼
Phase 4:
    └── 添加单元测试，提高覆盖率到 50%+
```

---

## 风险评估

| 风险 | 级别 | 缓解措施 |
|------|------|----------|
| 导入路径变更导致运行失败 | 高 | 更新所有导入语句，运行全量测试 |
| 重构后功能异常 | 高 | 分阶段重构，每阶段验证后再继续 |
| 测试覆盖不足 | 中 | 重构前运行现有测试，重构后补充测试 |
| 代码冲突 | 中 | 分模块重构，避免同时修改同一文件 |

---

## 回滚策略

每个 Phase 完成后:
1. 提交 Git: `git commit -m "refactor(phase-N): 描述"`
2. 创建标签: `git tag refactor-phase-N`
3. 运行全量测试验证

如果出现问题:
```bash
git checkout refactor-phase-N-1  # 回滚到上一个阶段
```

---

## 验证清单

### Phase 1 验证
- [ ] 所有导入正常
- [ ] 现有测试全部通过
- [ ] 手动测试核心功能 (消息转发、命令执行)

### Phase 2 验证
- [ ] 函数行数 < 100 行
- [ ] 无重复代码块
- [ ] 测试全部通过

### Phase 3 验证
- [ ] 无裸 except 子句
- [ ] 所有异常使用 logger.exception()
- [ ] 日志格式统一

### Phase 4 验证
- [ ] 测试覆盖率 >= 50%
- [ ] 所有测试通过
- [ ] CI/CD 流水线正常

---

## 注意事项

### 重要提醒

1. **grep 工具有问题，使用 bash 工具直接调用 rg 来使用 grep**
   ```bash
   # 不要用 grep 工具，用 bash 调用 rg
   bash("rg 'pattern' src/")
   ```

2. **不要使用 python 脚本来修改代码**
   - 直接使用 edit 工具进行文件修改
   - 使用 read 工具读取文件内容

3. **保持向后兼容**
   - 公共 API 签名不变
   - 配置文件格式不变
   - 数据文件格式不变

4. **每完成一个模块，立即验证**
   - 运行相关测试
   - 检查导入是否正常
   - 提交 Git 保存进度

### 如有疑问

如果重构过程中遇到任何疑问，应该向 Sisyphus (主协调器) 询问，而不是自行决定。

---

**文档版本:** 1.0
**最后更新:** 2026-03-24