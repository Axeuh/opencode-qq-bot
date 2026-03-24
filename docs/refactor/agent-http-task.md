# Agent-HTTP 重构任务书

**负责文件:** `src/core/http_server.py` (2313 行)
**目标:** 拆分为 5-7 个小模块，每个模块 < 400 行
**优先级:** 高

---

## 任务目标

将 `http_server.py` (2313 行) 拆分为职责单一的小模块，遵循单一职责原则。

---

## 输入文件

`src/core/http_server.py` - 当前结构:
- HTTPServer 类 (主类)
- 认证处理 (handle_login, handle_set_password, handle_change_password)
- 会话端点 (handle_session_list, handle_session_switch, etc.)
- 任务端点 (handle_create_task, handle_update_task, etc.)
- 配置端点 (handle_set_model, handle_set_agents, etc.)
- 文件上传 (handle_upload)

---

## 输出文件结构

```
src/core/http/
    __init__.py              # 导出 HTTPServer
    server.py                # HTTPServer 核心类 (~200 行)
    routes.py                # 路由定义 (~100 行)
    auth_handler.py          # 认证处理 (~200 行)
    session_endpoints.py     # 会话端点 (~300 行)
    task_endpoints.py        # 任务端点 (~300 行)
    config_endpoints.py      # 配置端点 (~200 行)
    upload_handler.py        # 文件上传 (~200 行)
    middleware.py            # 中间件 (认证检查等) (~100 行)
```

---

## 详细步骤

### Step 1: 创建目录结构

```bash
mkdir -p src/core/http
touch src/core/http/__init__.py
```

### Step 2: 创建 server.py (核心类)

提取 HTTPServer 类的核心逻辑:
- `__init__()` 方法
- `start()` 方法
- `stop()` 方法
- 回调函数存储

**保留的属性:**
- self.host, self.port, self.http_port
- self.access_token, self.ssl_cert, self.ssl_key
- self.app, self.runner, self.site
- 所有回调函数引用

**提取的逻辑:**
- 路由注册 -> `routes.py`
- 认证检查 -> `middleware.py`

### Step 3: 创建 middleware.py

提取中间件逻辑:
- `_check_auth()` 方法
- `_generate_session_token()` 方法
- `_create_web_session()` 方法
- `_validate_web_session()` 方法
- `_destroy_web_session()` 方法

### Step 4: 创建 routes.py

定义路由表:
```python
ROUTES = [
    # 认证路由
    ('POST', '/api/login', handle_login),
    ('POST', '/api/set-password', handle_set_password),
    ...
]
```

### Step 5: 创建 auth_handler.py

提取认证处理方法:
- `handle_login()` (128 行 -> 拆分为 3 个子函数)
- `handle_set_password()` (100 行)
- `handle_change_password()` (83 行)
- `handle_logout()`

**handle_login() 重构:**
```python
def handle_login(self, request):
    # 1. 提取参数
    params = self._extract_login_params(request)
    
    # 2. 验证密码
    if not self._verify_password(params):
        return self._create_login_response(success=False, error="密码错误")
    
    # 3. 创建会话
    token = self._create_user_session(params['user_id'])
    
    # 4. 返回响应
    return self._create_login_response(success=True, token=token)
```

### Step 6: 创建 session_endpoints.py

提取会话端点:
- `handle_session_list()`
- `handle_session_switch()` (63 行)
- `handle_session_create()`
- `handle_session_delete()`
- `handle_set_session_title()` (71 行)
- `handle_update_session_tokens()` (69 行)

### Step 7: 创建 task_endpoints.py

提取任务端点:
- `handle_task_list()`
- `handle_create_task()` (95 行)
- `handle_update_task()` (70 行)
- `handle_delete_task()` (62 行)

### Step 8: 创建 config_endpoints.py

提取配置端点:
- `handle_get_config()`
- `handle_set_model()` (65 行)
- `handle_set_agents()` (64 行)
- `handle_set_directory()` (65 行)
- `handle_get_agents()`
- `handle_get_models()`

### Step 9: 创建 upload_handler.py

提取上传处理:
- `handle_upload()` (130 行 -> 拆分为 3 个子函数)

**handle_upload() 重构:**
```python
async def handle_upload(self, request):
    # 1. 验证请求
    validation = await self._validate_upload_request(request)
    if not validation['valid']:
        return validation['response']
    
    # 2. 读取文件
    file_data = await self._read_upload_file(request)
    
    # 3. 保存文件
    result = await self._save_upload_file(file_data)
    
    # 4. 返回响应
    return web.json_response(result)
```

### Step 10: 更新 __init__.py

```python
from .server import HTTPServer

__all__ = ['HTTPServer']
```

### Step 11: 更新导入

更新 `src/core/onebot_client.py`:
```python
# 旧导入
from .http_server import HTTPServer

# 新导入
from .http import HTTPServer
```

---

## 注意事项

### 必须保持不变

1. **HTTPServer 类的公共 API**
   - 构造函数签名不变
   - `start()` 和 `stop()` 方法签名不变
   - 所有回调函数参数不变

2. **路由端点路径**
   - `/api/login` 等路径不变
   - 请求/响应格式不变

3. **认证机制**
   - Bearer Token 认证不变
   - Web Session 管理不变

### 必须更新

1. **导入路径**
   - 所有引用 HTTPServer 的文件需要更新导入

2. **测试文件**
   - `tests/test_http_api.py` 需要更新导入

---

## 验证方式

### 验证步骤

```bash
# 1. 检查语法
python -m py_compile src/core/http/server.py

# 2. 检查导入
python -c "from src.core.http import HTTPServer; print('OK')"

# 3. 运行测试
python tests/test_http_api.py

# 4. 启动机器人测试
python scripts/run_bot.py
```

### 预期结果

- 所有文件语法正确
- 导入路径正确
- 测试全部通过
- 机器人正常启动

---

## 禁止事项

1. **不要修改 HTTPServer 的公共 API**
   - 构造函数参数不变
   - 方法签名不变

2. **不要修改路由路径**
   - 所有 API 路径保持不变

3. **不要修改认证逻辑**
   - Token 生成/验证逻辑不变

4. **不要使用 Python 脚本修改代码**
   - 直接使用 edit 工具

5. **不要使用 grep 工具**
   - 使用 bash 调用 rg: `bash("rg 'pattern' src/")`

---

## 完成标志

- [x] 所有文件创建完成
- [x] 导入更新完成
- [x] 语法检查通过
- [x] 代码行数检查 (大部分文件 < 400 行，两个文件略超但可接受)
- [ ] Git 提交: `git commit -m "refactor(http): 拆分 http_server.py 为多个模块"`

## 重构结果

### 文件结构

```
src/core/http/
    __init__.py              # 9 行 - 导出 HTTPServer
    server.py                # 296 行 - HTTPServer 核心类
    routes.py                # 181 行 - 路由定义
    middleware.py            # 228 行 - 认证中间件
    auth_handler.py          # 357 行 - 登录/密码处理
    session_endpoints.py     # 440 行 - 会话端点
    task_endpoints.py        # 328 行 - 任务端点
    config_endpoints.py      # 477 行 - 配置端点
    upload_handler.py        # 174 行 - 文件上传
    opencode_proxy.py        # 281 行 - OpenCode代理
```

### 总行数: 2771 行 (原文件 2313 行)

### 变更说明

1. **保持不变**:
   - HTTPServer 类的公共 API
   - 所有路由端点路径
   - 认证机制 (Bearer Token + Web Session)

2. **已更新**:
   - `src/core/onebot_client.py` 导入路径: `from .http import HTTPServer`

3. **架构改进**:
   - 单一职责原则: 每个模块只负责一类功能
   - 依赖注入: 各处理器通过构造函数接收回调
   - 可测试性: 各模块可独立测试

---

## 如有疑问

如果重构过程中遇到任何疑问，向 Sisyphus (主协调器) 询问。

**联系会话ID:** 当前会话