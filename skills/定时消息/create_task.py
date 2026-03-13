#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时消息创建工具
支持中文参数，通过命令行直接传递参数创建定时任务
"""

import requests
import json
import sys
import argparse

# 设置控制台编码为 UTF-8
if sys.platform == 'win32':
    import os
    os.system('chcp 65001 >nul')

DEFAULT_BASE_URL = "http://127.0.0.1:8080"

def create_task(
    user_id: int,
    session_id: str,
    task_name: str,
    prompt: str,
    schedule_type: str = "delay",
    base_url: str = None,
    # delay 参数
    seconds: int = 0,
    minutes: int = 0,
    hours: int = 0,
    days: int = 0,
    weeks: int = 0,
    # scheduled 参数
    mode: str = "weekly",
    day: int = 1,
    month: int = 1,
    hour: int = 9,
    minute: int = 0,
    repeat: bool = False,
    days_of_week: str = "1 2 3 4 5"
):
    """创建定时任务"""
    
    if base_url is None:
        base_url = DEFAULT_BASE_URL
    
    # 构建 schedule_config
    if schedule_type == "delay":
        schedule_config = {}
        if seconds: schedule_config["seconds"] = seconds
        if minutes: schedule_config["minutes"] = minutes
        if hours: schedule_config["hours"] = hours
        if days: schedule_config["days"] = days
        if weeks: schedule_config["weeks"] = weeks
        
        # 默认 1 分钟
        if not schedule_config:
            schedule_config["minutes"] = 1
    
    elif schedule_type == "scheduled":
        schedule_config = {
            "mode": mode,
            "hour": hour,
            "minute": minute,
            "repeat": repeat
        }
        
        if mode == "weekly":
            schedule_config["days"] = [int(d) for d in days_of_week.split()]
        elif mode == "monthly" and day:
            schedule_config["day"] = day
        elif mode == "yearly":
            if month: schedule_config["month"] = month
            if day: schedule_config["day"] = day
    
    # 构建请求数据
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "task_name": task_name,
        "prompt": prompt,
        "schedule_type": schedule_type,
        "schedule_config": schedule_config
    }
    
    try:
        # 发送请求
        response = requests.post(f"{base_url}/api/task/set", json=data)
        result = response.json()
        
        if result.get("success"):
            task = result.get("task", {})
            print("✅ 任务创建成功！")
            print(f"   任务 ID: {task.get('task_id')}")
            print(f"   任务名称：{task.get('task_name')}")
            print(f"   下次运行：{task.get('next_run')}")
            return True
        else:
            print(f"❌ 任务创建失败：{result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ 请求失败：{e}")
        return False

def get_tasks(user_id: int, base_url: str = None):
    """获取任务列表"""
    if base_url is None:
        base_url = DEFAULT_BASE_URL
    
    try:
        response = requests.post(f"{base_url}/api/task/get", json={"user_id": user_id})
        result = response.json()
        
        if result.get("success"):
            tasks = result.get("tasks", [])
            print(f"📋 共有 {len(tasks)} 个任务：\n")
            for task in tasks:
                print(f"任务 ID: {task.get('task_id')}")
                print(f"  名称：{task.get('task_name')}")
                print(f"  类型：{task.get('schedule_type')}")
                print(f"  下次运行：{task.get('next_run')}")
                print(f"  运行次数：{task.get('run_count')}")
                print()
        else:
            print(f"❌ 获取失败：{result.get('error')}")
    except Exception as e:
        print(f"❌ 请求失败：{e}")

def delete_task(user_id: int, task_id: str, base_url: str = None):
    """删除任务"""
    if base_url is None:
        base_url = DEFAULT_BASE_URL
    
    try:
        response = requests.post(f"{base_url}/api/task/delete", json={
            "user_id": user_id,
            "task_id": task_id
        })
        result = response.json()
        
        if result.get("success"):
            print(f"✅ 任务已删除")
        else:
            print(f"❌ 删除失败：{result.get('error')}")
    except Exception as e:
        print(f"❌ 请求失败：{e}")

def main():
    parser = argparse.ArgumentParser(
        description="定时消息创建工具 - 支持中文参数",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 1 分钟后触发的中文任务
  python create_task.py --user-id 123456789 --session-id "ses_xxx" --name "测试" --prompt "你好！" --type delay --minutes 1
  
  # 每工作日 9 点触发
  python create_task.py --user-id 123456789 --name "每日提醒" --prompt "早上好" --type scheduled --mode weekly --days "1 2 3 4 5" --hour 9 --repeat
  
  # 查看任务列表
  python create_task.py --user-id 123456789 --list
  
  # 删除任务
  python create_task.py --user-id 123456789 --delete task_xxx
        """
    )
    
    # 操作模式
    parser.add_argument("--list", action="store_true", help="查看任务列表")
    parser.add_argument("--delete", type=str, metavar="TASK_ID", help="删除指定任务")
    parser.add_argument("--interactive", action="store_true", help="交互式模式")
    
    # 必需参数
    parser.add_argument("--user-id", type=int, required="--list" not in sys.argv and "--delete" not in sys.argv, help="用户 QQ 号")
    parser.add_argument("--session-id", type=str, help="OpenCode 会话 ID")
    parser.add_argument("--name", type=str, help="任务名称")
    parser.add_argument("--prompt", type=str, help="任务提示词（支持中文）")
    
    # 定时类型
    parser.add_argument("--type", type=str, choices=["delay", "scheduled"], default="delay", help="定时类型")
    
    # delay 参数
    parser.add_argument("--seconds", type=int, default=0, help="秒数")
    parser.add_argument("--minutes", type=int, default=0, help="分钟数")
    parser.add_argument("--hours", type=int, default=0, help="小时数")
    parser.add_argument("--days", type=int, default=0, help="天数")
    parser.add_argument("--weeks", type=int, default=0, help="周数")
    
    # scheduled 参数
    parser.add_argument("--mode", type=str, choices=["weekly", "monthly", "yearly"], default="weekly", help="定时模式")
    parser.add_argument("--weekdays", type=str, help="星期几（空格分隔，如'1 3 5'）")
    parser.add_argument("--day", type=int, help="日期（monthly/yearly 模式）")
    parser.add_argument("--month", type=int, help="月份（yearly 模式）")
    parser.add_argument("--hour", type=int, default=9, help="小时")
    parser.add_argument("--minute", type=int, default=0, help="分钟")
    parser.add_argument("--repeat", action="store_true", help="是否重复执行")
    
    # 服务器配置
    parser.add_argument("--port", type=int, default=8080, help="HTTP 服务器端口（默认 8080）")
    
    args = parser.parse_args()
    
    # 构建基础 URL
    base_url = f"http://127.0.0.1:{args.port}"
    
    # 查看任务列表
    if args.list:
        if not args.user_id:
            print("❌ 需要指定 --user-id")
            return
        get_tasks(args.user_id, base_url)
        return
    
    # 删除任务
    if args.delete:
        if not args.user_id:
            print("❌ 需要指定 --user-id")
            return
        delete_task(args.user_id, args.delete, base_url)
        return
    
    # 交互式模式
    if args.interactive:
        print("=" * 50)
        print("定时消息 - 交互式创建")
        print("=" * 50)
        
        user_id = int(input("用户 QQ 号 [123456789]: ").strip() or "123456789")
        session_id = input("会话 ID: ").strip()
        task_name = input("任务名称：").strip()
        prompt = input("任务提示词：").strip()
        
        print("\n选择定时类型:")
        print("1. delay - 延时任务")
        print("2. scheduled - 定时任务")
        choice = input("请选择 [1/2]: ").strip() or "1"
        
        schedule_type = "delay" if choice == "1" else "scheduled"
        
        if schedule_type == "delay":
            minutes = int(input("分钟数 [1]: ").strip() or "1")
            create_task(user_id, session_id, task_name, prompt, schedule_type, base_url, minutes=minutes)
        else:
            mode = input("模式 (weekly/monthly/yearly) [weekly]: ").strip() or "weekly"
            hour = int(input("小时 [9]: ").strip() or "9")
            repeat = input("是否重复？(y/n) [y]: ").strip().lower() != "n"
            create_task(user_id, session_id, task_name, prompt, schedule_type, base_url, mode=mode, hour=hour, repeat=repeat)
        return
    
    # 创建任务
    if not all([args.user_id, args.session_id, args.name, args.prompt]):
        print("❌ 缺少必需参数")
        print("   --user-id, --session-id, --name, --prompt 都是必需的")
        print("\n使用 --help 查看帮助")
        return
    
    create_task(
        user_id=args.user_id,
        session_id=args.session_id,
        task_name=args.name,
        prompt=args.prompt,
        schedule_type=args.type,
        base_url=base_url,
        seconds=args.seconds,
        minutes=args.minutes,
        hours=args.hours,
        days=args.days,
        weeks=args.weeks,
        mode=args.mode,
        day=args.day,
        month=args.month,
        hour=args.hour,
        minute=args.minute,
        repeat=args.repeat,
        days_of_week=args.weekdays if args.weekdays else "1 2 3 4 5"
    )

if __name__ == "__main__":
    main()
