#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强版测试 NapCat 的 get_msg API
提供完整的请求/响应调试信息，基于最佳实践收集的数据
"""

import asyncio
import aiohttp
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

# 配置结构化日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/test_get_msg_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# NapCat WebSocket 配置
WS_URL = "ws://localhost:3002"
ACCESS_TOKEN = "CqC5dDMXWGUu6NVh"

# 测试用的消息 ID
TEST_MESSAGE_ID = 1822260651


@dataclass
class WebSocketEvent:
    """WebSocket事件记录"""
    event_type: str
    timestamp: float
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    duration_ms: Optional[float] = None


@dataclass
class RequestMetadata:
    """请求元数据"""
    action: str
    params: Dict[str, Any]
    echo: str
    send_time: float
    request_size: int
    headers: Optional[Dict[str, str]] = None


@dataclass
class ResponseMetadata:
    """响应元数据"""
    receive_time: float
    response_data: Dict[str, Any]
    latency_ms: float
    response_size: int
    status: Optional[str] = None
    error_message: Optional[str] = None


class WebSocketDebugger:
    """WebSocket调试器"""
    
    def __init__(self):
        self.events: List[WebSocketEvent] = []
        self.start_time = time.time()
        self.requests: Dict[str, RequestMetadata] = {}
        self.responses: Dict[str, ResponseMetadata] = {}
        
    def log_event(self, event_type: str, message: Optional[str] = None, data: Optional[Dict] = None):
        """记录WebSocket事件"""
        event = WebSocketEvent(
            event_type=event_type,
            timestamp=time.time(),
            message=message,
            data=data
        )
        self.events.append(event)
        logger.debug(f"[WebSocket Event] {event_type}: {message}")
        
    def record_request(self, echo: str, action: str, params: Dict, send_time: float, request_str: str):
        """记录请求"""
        self.requests[echo] = RequestMetadata(
            action=action,
            params=params,
            echo=echo,
            send_time=send_time,
            request_size=len(request_str.encode('utf-8')),
            headers={'Content-Type': 'application/json'}
        )
        logger.info(f"[Request Recorded] Echo: {echo}, Action: {action}")
        
    def record_response(self, echo: str, response_data: Dict, receive_time: float):
        """记录响应"""
        if echo not in self.requests:
            logger.warning(f"收到未知echo的响应: {echo}")
            return
            
        request = self.requests[echo]
        latency_ms = (receive_time - request.send_time) * 1000
        
        self.responses[echo] = ResponseMetadata(
            receive_time=receive_time,
            response_data=response_data,
            latency_ms=latency_ms,
            response_size=len(json.dumps(response_data).encode('utf-8')),
            status=response_data.get('status'),
            error_message=response_data.get('message')
        )
        logger.info(f"[Response Recorded] Echo: {echo}, Latency: {latency_ms:.2f}ms, Status: {response_data.get('status')}")
        
    def get_events_summary(self) -> Dict[str, Any]:
        """获取事件摘要"""
        return {
            "total_events": len(self.events),
            "event_types": list(set(e.event_type for e in self.events)),
            "events": [asdict(e) for e in self.events],
            "requests": {k: asdict(v) for k, v in self.requests.items()},
            "responses": {k: asdict(v) for k, v in self.responses.items()},
            "summary_stats": self._calculate_stats()
        }
        
    def _calculate_stats(self) -> Dict[str, Any]:
        """计算统计信息"""
        if not self.responses:
            return {}
            
        latencies = [r.latency_ms for r in self.responses.values()]
        return {
            "total_requests": len(self.requests),
            "total_responses": len(self.responses),
            "avg_latency_ms": sum(latencies) / len(latencies),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "success_rate": sum(1 for r in self.responses.values() if r.status == 'ok') / len(self.responses) * 100
        }
        
    def print_detailed_report(self):
        """打印详细报告"""
        print("\n" + "="*80)
        print("WEBSOCKET 调试详细报告")
        print("="*80)
        
        print(f"\n📊 统计摘要:")
        stats = self._calculate_stats()
        if stats:
            for key, value in stats.items():
                print(f"  {key}: {value}")
        
        print(f"\n📋 事件记录 ({len(self.events)} 个事件):")
        for event in self.events:
            timestamp_str = datetime.fromtimestamp(event.timestamp).strftime('%H:%M:%S.%f')[:-3]
            print(f"  [{timestamp_str}] {event.event_type}: {event.message or ''}")
        
        print(f"\n📤 请求详情:")
        for echo, req in self.requests.items():
            print(f"\n  Echo: {echo}")
            print(f"    Action: {req.action}")
            print(f"    Params: {json.dumps(req.params, ensure_ascii=False)}")
            print(f"    发送时间: {req.send_time:.3f}")
            print(f"    请求大小: {req.request_size} bytes")
        
        print(f"\n📥 响应详情:")
        for echo, resp in self.responses.items():
            if echo in self.requests:
                req = self.requests[echo]
                print(f"\n  Echo: {echo}")
                print(f"    延迟: {resp.latency_ms:.2f} ms")
                print(f"    状态: {resp.status}")
                print(f"    响应大小: {resp.response_size} bytes")
                if resp.error_message:
                    print(f"    错误: {resp.error_message}")


# 简化版TraceConfig，只使用基本功能
class SimpleTraceConfig:
    """简化版跟踪配置，用于记录WebSocket事件"""
    
    def __init__(self, debugger: WebSocketDebugger):
        self.debugger = debugger
    
    async def on_ws_send(self, message: str):
        """WebSocket发送消息时的回调"""
        self.debugger.log_event("WS_MESSAGE_SENT", f"发送消息: {message[:100]}...")
        
    async def on_ws_receive(self, message: str):
        """WebSocket接收消息时的回调"""
        self.debugger.log_event("WS_MESSAGE_RECEIVED", f"收到消息: {message[:100]}...")


async def enhanced_test_get_msg(message_id: int, debugger: WebSocketDebugger):
    """增强版测试 get_msg API"""
    print(f"\n{'='*80}")
    print(f"🎯 增强版测试 get_msg API")
    print(f"{'='*80}")
    print(f"消息 ID: {message_id}")
    print(f"WebSocket: {WS_URL}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    print()
    
    debugger.log_event("TEST_START", f"开始测试 get_msg for message_id={message_id}")
    
    try:
        # 创建会话（不使用TraceConfig，因为它可能不支持WebSocket事件）
        async with aiohttp.ClientSession() as session:
            debugger.log_event("SESSION_CREATED", "aiohttp会话已创建")
            
            # WebSocket连接
            ws_url = f"{WS_URL}?access_token={ACCESS_TOKEN}"
            debugger.log_event("WS_CONNECT_START", f"正在连接到 {ws_url}")
            
            connect_start = time.time()
            async with session.ws_connect(ws_url) as ws:
                connect_time = time.time() - connect_start
                debugger.log_event("WS_CONNECTED", f"WebSocket连接成功，耗时: {connect_time:.2f}秒")
                
                # 等待连接稳定
                await asyncio.sleep(0.5)
                debugger.log_event("CONNECTION_STABILIZED", "连接已稳定")
                
                # 发送 get_msg 请求
                echo_value = f"test_get_msg_{int(time.time())}"
                request = {
                    "action": "get_msg",
                    "params": {
                        "message_id": message_id
                    },
                    "echo": echo_value
                }
                
                request_str = json.dumps(request, ensure_ascii=False)
                send_time = time.time()
                
                print(f"📤 发送请求 (Echo: {echo_value}):")
                print(f"  Action: {request['action']}")
                print(f"  Params: {json.dumps(request['params'], ensure_ascii=False)}")
                print(f"  Echo: {request['echo']} (类型: {type(request['echo']).__name__})")
                print(f"  消息ID类型: {type(message_id).__name__}")
                print(f"  发送时间戳: {send_time:.3f}")
                print(f"  请求JSON大小: {len(request_str)} 字符")
                print()
                
                # 记录请求
                debugger.record_request(echo_value, request['action'], request['params'], send_time, request_str)
                debugger.log_event("REQUEST_SENDING", f"正在发送请求: {request['action']}")
                
                await ws.send_json(request)
                debugger.log_event("REQUEST_SENT", f"请求已发送: {request['action']}")
                
                # 等待响应（最多接收 15 条消息，包含详细的调试信息）
                print("⏳ 等待响应...")
                debugger.log_event("WAITING_RESPONSE", "开始等待响应")
                
                max_attempts = 15
                response_received = False
                
                for attempt in range(1, max_attempts + 1):
                    try:
                        receive_start = time.time()
                        msg = await asyncio.wait_for(ws.receive_json(), timeout=2.0)
                        receive_time = time.time()
                        receive_duration = receive_time - receive_start
                        
                        debugger.log_event("MESSAGE_RECEIVED", 
                                         f"收到消息 (尝试 {attempt}/{max_attempts})", 
                                         {"attempt": attempt, "receive_duration": receive_duration})
                        
                        # 记录原始消息
                        msg_str = json.dumps(msg, ensure_ascii=False)
                        print(f"\n📥 收到原始消息 (尝试 {attempt}):")
                        print(f"  接收时间戳: {receive_time:.3f}")
                        print(f"  接收耗时: {receive_duration:.3f}秒")
                        print(f"  消息类型: {type(msg).__name__}")
                        print(f"  消息大小: {len(msg_str)} 字符")
                        
                        # 跳过 meta_event
                        if msg.get('post_type') == 'meta_event':
                            print(f"  ⏩ 跳过 meta_event")
                            debugger.log_event("META_EVENT_SKIPPED", "跳过meta_event")
                            continue
                        
                        # 检查是否是 API 响应（支持两种echo匹配方式）
                        response_echo = msg.get('echo')
                        is_api_response = False
                        
                        if response_echo == echo_value:
                            is_api_response = True
                            match_type = "完全匹配"
                        elif 'status' in msg and 'params' not in msg:
                            # 检查是否有可能是echo不匹配的情况
                            is_api_response = True
                            match_type = "状态匹配（echo可能不匹配）"
                        else:
                            match_type = "非API响应"
                        
                        print(f"  Echo匹配: {match_type}")
                        print(f"  响应Echo: {response_echo}")
                        print(f"  期望Echo: {echo_value}")
                        
                        if is_api_response:
                            print(f"\n✅ 收到 API 响应:")
                            print(json.dumps(msg, indent=2, ensure_ascii=False, default=str))
                            
                            # 记录响应
                            debugger.record_response(echo_value, msg, receive_time)
                            debugger.log_event("API_RESPONSE_RECEIVED", 
                                             f"收到API响应: {msg.get('status')}")
                            
                            # 分析响应
                            if msg.get('status') == 'ok':
                                print("🎉 get_msg API 调用成功！")
                                
                                data = msg.get('data', {})
                                print(f"\n📊 消息内容分析:")
                                print(f"  - 消息类型：{data.get('message_type', 'N/A')}")
                                print(f"  - 发送时间：{data.get('time', 'N/A')}")
                                print(f"  - 发送者：{data.get('sender', {}).get('nickname', 'N/A')}")
                                
                                # 分析 message 数组
                                message_array = data.get('message', [])
                                if isinstance(message_array, list):
                                    print(f"\n  - 消息段数量：{len(message_array)}")
                                    for j, segment in enumerate(message_array[:5]):  # 只显示前5个
                                        if isinstance(segment, dict):
                                            seg_type = segment.get('type', 'unknown')
                                            print(f"    [{j}] 类型：{seg_type}")
                                            if seg_type == 'image':
                                                img_data = segment.get('data', {})
                                                print(f"        文件名：{img_data.get('file', 'N/A')}")
                                                url = img_data.get('url', 'N/A')
                                                if url and url != 'N/A':
                                                    print(f"        URL: {url[:80]}...")
                                                    if 'rkey=' in url:
                                                        print(f"        ✅ URL 包含 rkey！")
                                                    else:
                                                        print(f"        ❌ URL 不包含 rkey")
                                else:
                                    print(f"\n  ❌ message 字段不是数组格式：{type(message_array)}")
                                
                                response_received = True
                                break
                            else:
                                print("❌ get_msg API 调用失败！")
                                print(f"  错误：{msg.get('message', 'Unknown error')}")
                                debugger.log_event("API_ERROR", f"API错误: {msg.get('message')}")
                                response_received = True
                                break
                        else:
                            print(f"  ⏩ 非目标响应，继续等待...")
                            debugger.log_event("NON_TARGET_RESPONSE", "收到非目标响应，继续等待")
                            
                    except asyncio.TimeoutError:
                        print(f"  ⏱️  尝试 {attempt}/{max_attempts}: 2秒超时")
                        debugger.log_event("TIMEOUT", f"尝试 {attempt} 超时")
                        continue
                
                if not response_received:
                    total_wait_time = max_attempts * 2
                    print(f"\n❌ 未收到 API 响应（总等待时间: {total_wait_time} 秒）")
                    debugger.log_event("NO_RESPONSE", f"等待{total_wait_time}秒后未收到响应")
                    print("  可能原因：")
                    print("  1. NapCat get_msg API 响应时间超过 30 秒")
                    print("  2. 消息 ID 不存在或权限不足")
                    print("  3. NapCat 服务内部错误")
                    print("  4. WebSocket 连接问题")
                
                # 关闭连接
                debugger.log_event("CONNECTION_CLOSING", "正在关闭WebSocket连接")
                await ws.close()
                debugger.log_event("CONNECTION_CLOSED", "WebSocket连接已关闭")
                
                return response_received
                    
    except aiohttp.ClientError as e:
        error_msg = f"WebSocket 连接失败：{e}"
        print(f"\n❌ {error_msg}")
        debugger.log_event("CONNECTION_ERROR", error_msg)
        print("  可能原因：")
        print("  1. NapCat 未启动")
        print("  2. WebSocket 地址或端口错误")
        print("  3. 访问令牌错误")
        return False
    except Exception as e:
        error_msg = f"未知错误：{e}"
        print(f"\n❌ {error_msg}")
        debugger.log_event("UNKNOWN_ERROR", error_msg)
        return False
    finally:
        debugger.log_event("TEST_COMPLETE", "测试完成")


async def main():
    """主函数"""
    print("\n" + "="*80)
    print("🎯 NapCat API 增强调试工具")
    print("="*80)
    print("\n基于WebSocket调试最佳实践，提供完整的请求/响应调试信息")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 初始化调试器
    debugger = WebSocketDebugger()
    
    # 测试 get_msg
    print(f"📌 测试消息ID: {TEST_MESSAGE_ID}")
    get_msg_result = await enhanced_test_get_msg(TEST_MESSAGE_ID, debugger)
    
    # 生成详细报告
    debugger.print_detailed_report()
    
    # 总结
    print("\n" + "="*80)
    print("📊 测试总结")
    print("="*80)
    print(f"get_msg API:  {'✅ 成功' if get_msg_result else '❌ 失败'}")
    print(f"事件总数: {len(debugger.events)}")
    
    # 保存详细报告到文件
    try:
        report = debugger.get_events_summary()
        with open('logs/get_msg_debug_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"详细报告已保存到: logs/get_msg_debug_report.json")
    except Exception as e:
        print(f"保存报告失败: {e}")
    
    return get_msg_result


if __name__ == "__main__":
    # 确保日志目录存在
    import os
    os.makedirs('logs', exist_ok=True)
    
    asyncio.run(main())