---
name: 定时消息
description: 创建定时任务，支持中文提示词。当用户需要设置定时工作任务、定时发送消息、定时提醒时使用。支持延时任务（指定多久后触发）和定时任务。
---

# 定时消息技能

此技能用于创建定时任务，假设你创建一个定时任务在5分钟后执行，那么会在5分钟后自动发送一个消息给你，消息内容就是提示词内容。特别优化了中文输入支持。直接使用curl无法使用中文提示词，请使用py脚本。
当你使用了这个skill你就不需要自己定时了，可以做下一个任务了。
当用户明确了时间点例如13：50，属于定时任务，使用scheduled类型。
如果用户说“半小时后。。。”这种没有明确时间点的情况，属于延时任务，你就应该使用delay类型。

## 何时使用

- 用户需要创建定时任务
- 用户需要定时发送消息或提醒
- 用户需要中文提示词支持
- 用户需要延时或定时触发任务

## 快速使用

### 方法 1：命令行参数（推荐）

```bash
python create_task.py \
  --user-id 123456789 \
  --session-id "ses_xxx" \
  --name "中文任务名" \
  --prompt "你好！这是中文提示词" \
  --type delay \
  --minutes 1
```

### 方法 2：交互式

```bash
python create_task.py --interactive
```

## 参数说明

### 必需参数

- `--user-id`: 用户 QQ 号
- `--session-id`: OpenCode 会话 ID
- `--name`: 任务名称
- `--prompt`: 任务提示词（支持中文）

### 服务器配置

- `--port`: HTTP 服务器端口（默认 8080）

### 定时类型

#### delay（延时任务）

一次性任务，指定时间后触发：

- `--seconds`: 秒数
- `--minutes`: 分钟数
- `--hours`: 小时数
- `--days`: 天数
- `--weeks`: 周数

可组合使用，如 `--hours 1 --minutes 30` 表示 1 小时 30 分钟后。

#### scheduled（定时任务）

可重复的定时任务：

- `--mode`: 模式（weekly/monthly/yearly）
- `--days`: 星期几（weekly 模式，空格分隔如"1 3 5"）
- `--day`: 日期（monthly 模式）
- `--month`: 月份（yearly 模式）
- `--hour`: 小时
- `--minute`: 分钟
- `--repeat`: 是否重复

## 使用示例

### 示例 1：1 分钟后触发的中文任务

```bash
python create_task.py \
  --user-id 123456789 \
  --session-id "ses_320a312deffeOra0e3gAT0y0kL" \
  --name "测试任务" \
  --prompt "你好！这是一条中文定时任务测试消息" \
  --type delay \
  --minutes 1
```

### 示例 2：每工作日 9 点触发

```bash
python create_task.py \
  --user-id 123456789 \
  --session-id "ses_xxx" \
  --name "每日提醒" \
  --prompt "早上好！该开始工作了" \
  --type scheduled \
  --mode weekly \
  --weekdays "1 2 3 4 5" \
  --hour 9 \
  --repeat
```

### 示例 3：每月 15 号提醒

```bash
python create_task.py \
  --user-id 123456789 \
  --session-id "ses_xxx" \
  --name "月度报告提醒" \
  --prompt "该写月度报告了" \
  --type scheduled \
  --mode monthly \
  --day 15 \
  --hour 10 \
  --repeat
```

### 示例 4：指定端口

```bash
python create_task.py \
  --user-id 123456789 \
  --session-id "ses_xxx" \
  --name "测试" \
  --prompt "测试消息" \
  --type delay \
  --minutes 1 \
  --port 9090
```

## 中文编码说明

此脚本已处理 UTF-8 编码，支持：
- ✅ 中文提示词
- ✅ 中文任务名
- ✅ 表情符号
- ✅ 多语言混合

## 输出格式

成功时输出：
```
✅ 任务创建成功！
   任务 ID: task_xxx
   下次运行：2026-03-12 10:00:00
```

失败时输出：
```
❌ 任务创建失败：错误信息
```

