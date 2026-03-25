---
name: axeuh-control
description: Axeuh的Bot控制技能。可以设置定时任务、会话、智能体和模型。当用户需要设置定时任务、切换智能体或者切换模型、或者获取当前会话，切换会话，新建会话等时使用，还有获取当前路径，设置路径。
compatibility:
  dependencies: []
mcp:
  axeuh-mcp:
    command: python
    args: ["${USERPROFILE}/.config/opencode/skills/axeuh-control/axeuh_mcp.py"]
---

# Axeuh Control

Bot控制MCP技能，用于管理QQ用户会话、定时任务、智能体和模型。

## 前置要求

- Bot HTTP服务运行在 127.0.0.1:4090

## 可用工具

### 用户会话管理 (QQ用户到OpenCode会话的映射)

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `user_session_list` | 获取用户的会话映射列表 | user_id |
| `user_session_create` | 为用户创建新会话映射 | user_id, title(可选) |
| `user_session_switch` | 切换用户的当前会话 | user_id, session_id |
| `user_session_delete` | 删除用户的会话映射 | user_id, session_id |
| `session_title_set` | 设置会话标题 | user_id, session_id, title |

### 任务管理

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `task_list` | 获取用户任务列表 | user_id |
| `task_create` | 创建定时任务 | user_id, session_id, name, prompt, schedule_type, schedule_config |
| `task_delete` | 删除任务 | user_id, task_id |

### 智能体管理

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `agent_list` | 获取可用智能体列表 | 无 |
| `agent_get` | 获取用户当前智能体 | user_id |
| `agent_set` | 设置用户智能体 | user_id, agent |

### 模型管理

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `model_list` | 获取可用模型列表 | 无 |
| `model_get` | 获取用户当前模型 | user_id |
| `model_set` | 设置用户模型 | user_id, model |

### 系统管理

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `system_health` | 检查Bot服务器健康状态 | 无 |
| `system_restart_opencode` | 重启OpenCode进程 | 无 |
| `system_restart_bot` | 重启Bot进程 | 无 |

### 工作目录管理

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `directory_get` | 获取用户工作目录 | user_id |
| `directory_set` | 设置用户工作目录 | user_id, directory |

## 调用示例

### 获取用户会话映射
```typescript
skill_mcp(
  mcp_name="axeuh-mcp",
  tool_name="user_session_list",
  arguments={"user_id": 2176284372}
)
```

### 切换用户会话
```typescript
skill_mcp(
  mcp_name="axeuh-mcp",
  tool_name="user_session_switch",
  arguments={
    "user_id": 2176284372,
    "session_id": "ses_xxx"
  }
)
```

### 设置会话标题
```typescript
skill_mcp(
  mcp_name="axeuh-mcp",
  tool_name="session_title_set",
  arguments={
    "user_id": 2176284372,
    "session_id": "ses_xxx",
    "title": "新标题"
  }
)
```

### 创建延时任务
```typescript
skill_mcp(
  mcp_name="axeuh-mcp",
  tool_name="task_create",
  arguments={
    "user_id": 2176284372,
    "session_id": "ses_xxx",
    "name": "测试任务",
    "prompt": "你好世界",
    "schedule_type": "delay",
    "schedule_config": {"minutes": 5}
  }
)
```

### 创建定时任务(每工作日9点)
```typescript
skill_mcp(
  mcp_name="axeuh-mcp",
  tool_name="task_create",
  arguments={
    "user_id": 2176284372,
    "session_id": "ses_xxx",
    "name": "每日提醒",
    "prompt": "早上好",
    "schedule_type": "scheduled",
    "schedule_config": {"mode": "weekly", "days": [1,2,3,4,5], "hour": 9, "repeat": true}
  }
)
```

### 设置模型
```typescript
skill_mcp(
  mcp_name="axeuh-mcp",
  tool_name="model_set",
  arguments={"user_id": 2176284372, "model": "glm-5"}
)
```

### 设置智能体
```typescript
skill_mcp(
  mcp_name="axeuh-mcp",
  tool_name="agent_set",
  arguments={"user_id": 2176284372, "agent": "build"}
)
```

### 获取工作目录
```typescript
skill_mcp(
  mcp_name="axeuh-mcp",
  tool_name="directory_get",
  arguments={"user_id": 2176284372}
)
```

### 设置工作目录
```typescript
skill_mcp(
  mcp_name="axeuh-mcp",
  tool_name="directory_set",
  arguments={"user_id": 2176284372, "directory": "/home/user/projects"}
)
```

## Schedule配置说明

### delay (延时任务)

```json
{"minutes": 5}
{"hours": 1, "minutes": 30}
```

### scheduled (定时任务)

```json
{"mode": "weekly", "days": [1,2,3,4,5], "hour": 9, "repeat": true}
{"mode": "monthly", "day": 15, "hour": 10}
{"mode": "yearly", "month": 1, "day": 1, "hour": 0}
```

## 配置

`config.json`:
```json
{
  "bot": {
    "host": "127.0.0.1",
    "port": 4090
  }
}
```

## Available MCP Servers

### axeuh-mcp

**Tools:**

#### `user_session_list`
获取用户的会话映射列表(QQ用户到OpenCode会话的映射)
    
    Args:
        user_id: 用户QQ号
        
    Returns:
        用户会话映射列表

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    }
  },
  "required": [
    "user_id"
  ],
  "title": "user_session_listArguments"
}
```

#### `user_session_create`
为用户创建新会话映射
    
    Args:
        user_id: 用户QQ号
        title: 会话标题(可选)
        
    Returns:
        创建结果

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    },
    "title": {
      "default": null,
      "title": "Title",
      "type": "string"
    }
  },
  "required": [
    "user_id"
  ],
  "title": "user_session_createArguments"
}
```

#### `user_session_switch`
切换用户的当前会话
    
    Args:
        user_id: 用户QQ号
        session_id: 目标OpenCode会话ID
        
    Returns:
        切换结果

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User_id",
      "type": "integer"
    },
    "session_id": {
      "title": "Session_id",
      "type": "string"
    }
  },
  "required": [
    "user_id",
    "session_id"
  ],
  "title": "user_session_switchArguments"
}
```

#### `user_session_delete`
删除用户的会话映射
    
    Args:
        user_id: 用户QQ号
        session_id: OpenCode会话ID
        
    Returns:
        删除结果

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    },
    "session_id": {
      "title": "Session Id",
      "type": "string"
    }
  },
  "required": [
    "user_id",
    "session_id"
  ],
  "title": "user_session_deleteArguments"
}
```

#### `session_title_set`
设置会话标题
    
    Args:
        user_id: 用户QQ号
        session_id: OpenCode会话ID
        title: 新标题
        
    Returns:
        设置结果

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    },
    "session_id": {
      "title": "Session Id",
      "type": "string"
    },
    "title": {
      "title": "Title",
      "type": "string"
    }
  },
  "required": [
    "user_id",
    "session_id",
    "title"
  ],
  "title": "session_title_setArguments"
}
```

#### `task_list`
获取用户任务列表
    
    Args:
        user_id: 用户QQ号
        
    Returns:
        任务列表

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    }
  },
  "required": [
    "user_id"
  ],
  "title": "task_listArguments"
}
```

#### `task_create`
创建定时任务
    
    Args:
        user_id: 用户QQ号
        session_id: OpenCode会话ID
        name: 任务名称
        prompt: 任务提示词
        schedule_type: 计划类型 (delay/scheduled)
        schedule_config: 计划配置
        
    Returns:
        创建结果

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    },
    "session_id": {
      "title": "Session Id",
      "type": "string"
    },
    "name": {
      "title": "Name",
      "type": "string"
    },
    "prompt": {
      "title": "Prompt",
      "type": "string"
    },
    "schedule_type": {
      "title": "Schedule Type",
      "type": "string"
    },
    "schedule_config": {
      "title": "Schedule Config",
      "type": "object"
    }
  },
  "required": [
    "user_id",
    "session_id",
    "name",
    "prompt",
    "schedule_type",
    "schedule_config"
  ],
  "title": "task_createArguments"
}
```

#### `task_delete`
删除任务
    
    Args:
        user_id: 用户QQ号
        task_id: 任务ID
        
    Returns:
        删除结果

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    },
    "task_id": {
      "title": "Task Id",
      "type": "string"
    }
  },
  "required": [
    "user_id",
    "task_id"
  ],
  "title": "task_deleteArguments"
}
```

#### `agent_list`
获取可用智能体列表
    
    Returns:
        智能体列表

**inputSchema:**
```json
{
  "type": "object",
  "properties": {},
  "title": "agent_listArguments"
}
```

#### `agent_get`
获取用户当前智能体
    
    Args:
        user_id: 用户QQ号
        
    Returns:
        当前智能体名称

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    }
  },
  "required": [
    "user_id"
  ],
  "title": "agent_getArguments"
}
```

#### `agent_set`
设置用户智能体
    
    Args:
        user_id: 用户QQ号
        agent: 智能体名称
        
    Returns:
        设置结果

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    },
    "agent": {
      "title": "Agent",
      "type": "string"
    }
  },
  "required": [
    "user_id",
    "agent"
  ],
  "title": "agent_setArguments"
}
```

#### `model_list`
获取可用模型列表
    
    Returns:
        模型列表

**inputSchema:**
```json
{
  "type": "object",
  "properties": {},
  "title": "model_listArguments"
}
```

#### `model_get`
获取用户当前模型
    
    Args:
        user_id: 用户QQ号
        
    Returns:
        当前模型名称

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    }
  },
  "required": [
    "user_id"
  ],
  "title": "model_getArguments"
}
```

#### `model_set`
设置用户模型
    
    Args:
        user_id: 用户QQ号
        model: 模型名称
        
    Returns:
        设置结果

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    },
    "model": {
      "title": "Model",
      "type": "string"
    }
  },
  "required": [
    "user_id",
    "model"
  ],
  "title": "model_setArguments"
}
```

#### `system_health`
检查Bot服务器健康状态
    
    Returns:
        健康状态

**inputSchema:**
```json
{
  "type": "object",
  "properties": {},
  "title": "system_healthArguments"
}
```

#### `system_restart_opencode`
重启OpenCode进程
    
    Returns:
        重启结果

**inputSchema:**
```json
{
  "type": "object",
  "properties": {},
  "title": "system_restart_opencodeArguments"
}
```

#### `system_restart_bot`
重启Bot进程
    
    Returns:
        重启结果

**inputSchema:**
```json
{
  "type": "object",
  "properties": {},
  "title": "system_restart_botArguments"
}
```

#### `directory_get`
获取用户工作目录
    
    Args:
        user_id: 用户QQ号
        
    Returns:
        用户当前工作目录

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    }
  },
  "required": [
    "user_id"
  ],
  "title": "directory_getArguments"
}
```

#### `directory_set`
设置用户工作目录
    
    Args:
        user_id: 用户QQ号
        directory: 工作目录路径
        
    Returns:
        设置结果

**inputSchema:**
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "title": "User Id",
      "type": "integer"
    },
    "directory": {
      "title": "Directory",
      "type": "string"
    }
  },
  "required": [
    "user_id",
    "directory"
  ],
  "title": "directory_setArguments"
}
```

Use `skill_mcp` tool with `mcp_name="axeuh-mcp"` to invoke.