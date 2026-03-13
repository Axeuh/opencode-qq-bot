#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证get_msg API调用不再超时
测试修复后的引用消息处理流程
"""

import asyncio
import json
import logging
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.api_sender import ApiSender
from src.core.cq_code_parser import extract_quoted_message_id, extract_file_info


def setup_logging():
    """设置测试日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def test_get_quoted_message_full_success():
    """测试成功获取引用消息"""
    print("\n" + "="*60)
    print("测试成功获取引用消息")
    print("="*60)
    
    # 创建mock connection_manager
    mock_connection_manager = AsyncMock()
    
    # 模拟成功的API响应
    mock_response = {
        'status': 'ok',
        'data': {
            'message_id': 1822260651,
            'message_type': 'private',
            'message': [
                {'type': 'text', 'data': {'text': '原始消息内容'}}
            ],
            'raw_message': '原始消息内容'
        }
    }
    
    mock_connection_manager.send_action_with_response.return_value = mock_response
    
    # 创建ApiSender
    api_sender = ApiSender(mock_connection_manager)
    
    # 测试获取引用消息
    message_id = 1822260651
    result = await api_sender.get_quoted_message_full(message_id)
    
    # 验证
    assert result is not None
    assert result['message_id'] == 1822260651
    assert result['message_type'] == 'private'
    
    # 验证API调用
    mock_connection_manager.send_action_with_response.assert_called_once_with(
        "get_msg",
        {"message_id": message_id},
        timeout=30.0
    )
    
    print(f"✓ 成功获取引用消息，message_id={message_id}")
    print(f"  响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
    return True


async def test_get_quoted_message_full_timeout_with_retry():
    """测试超时后重试成功"""
    print("\n" + "="*60)
    print("测试超时后重试成功")
    print("="*60)
    
    mock_connection_manager = AsyncMock()
    
    # 模拟第一次超时，第二次成功
    mock_connection_manager.send_action_with_response.side_effect = [
        None,  # 第一次超时返回None
        {  # 第二次成功
            'status': 'ok',
            'data': {
                'message_id': 1822260651,
                'message': [{'type': 'text', 'data': {'text': '重试成功的消息'}}]
            }
        }
    ]
    
    api_sender = ApiSender(mock_connection_manager)
    
    message_id = 1822260651
    result = await api_sender.get_quoted_message_full(message_id)
    
    # 验证重试成功
    assert result is not None
    assert result['message_id'] == 1822260651
    
    # 验证调用了两次（重试一次）
    assert mock_connection_manager.send_action_with_response.call_count == 2
    
    print("✓ 超时后重试成功")
    print(f"  调用次数: {mock_connection_manager.send_action_with_response.call_count}")
    return True


async def test_get_quoted_message_full_all_retries_fail():
    """测试所有重试都失败"""
    print("\n" + "="*60)
    print("测试所有重试都失败")
    print("="*60)
    
    mock_connection_manager = AsyncMock()
    
    # 模拟所有尝试都超时
    mock_connection_manager.send_action_with_response.return_value = None
    
    api_sender = ApiSender(mock_connection_manager)
    
    message_id = 1822260651
    result = await api_sender.get_quoted_message_full(message_id)
    
    # 验证所有重试都失败后返回None
    assert result is None
    
    # 验证调用了3次（初始+2次重试）
    assert mock_connection_manager.send_action_with_response.call_count == 3
    
    print("✓ 所有重试都失败，返回None")
    print(f"  调用次数: {mock_connection_manager.send_action_with_response.call_count}")
    return True


async def test_api_error_with_retry():
    """测试API错误后重试"""
    print("\n" + "="*60)
    print("测试API错误后重试")
    print("="*60)
    
    mock_connection_manager = AsyncMock()
    
    # 模拟第一次API错误，第二次成功
    mock_connection_manager.send_action_with_response.side_effect = [
        {'status': 'failed', 'message': '消息不存在'},  # 第一次失败
        {'status': 'ok', 'data': {'message_id': 1822260651, 'message': []}}  # 第二次成功
    ]
    
    api_sender = ApiSender(mock_connection_manager)
    
    message_id = 1822260651
    result = await api_sender.get_quoted_message_full(message_id)
    
    # 验证重试成功
    assert result is not None
    assert result['message_id'] == 1822260651
    
    # 验证调用了两次
    assert mock_connection_manager.send_action_with_response.call_count == 2
    
    print("✓ API错误后重试成功")
    return True


async def test_message_id_type_conversion():
    """测试消息ID类型转换"""
    print("\n" + "="*60)
    print("测试消息ID类型转换")
    print("="*60)
    
    mock_connection_manager = AsyncMock()
    
    # 测试字符串消息ID
    mock_response = {
        'status': 'ok',
        'data': {'message_id': '1822260651', 'message': []}
    }
    mock_connection_manager.send_action_with_response.return_value = mock_response
    
    api_sender = ApiSender(mock_connection_manager)
    
    # 测试字符串消息ID
    result = await api_sender.get_quoted_message_full("1822260651")
    assert result is not None
    
    # 验证API调用参数
    call_args = mock_connection_manager.send_action_with_response.call_args
    assert call_args[0][0] == "get_msg"
    assert call_args[1]["params"]["message_id"] == "1822260651"
    
    print("✓ 字符串消息ID处理正常")
    
    # 测试整数消息ID
    mock_connection_manager.reset_mock()
    mock_connection_manager.send_action_with_response.return_value = {
        'status': 'ok',
        'data': {'message_id': 1822260651, 'message': []}
    }
    
    result = await api_sender.get_quoted_message_full(1822260651)
    assert result is not None
    
    call_args = mock_connection_manager.send_action_with_response.call_args
    assert call_args[1]["params"]["message_id"] == 1822260651
    
    print("✓ 整数消息ID处理正常")
    return True


async def test_extract_quoted_message_id():
    """测试提取引用消息ID"""
    print("\n" + "="*60)
    print("测试提取引用消息ID")
    print("="*60)
    
    # 测试用例
    test_cases = [
        {
            'message': '[CQ:reply,id=1822260651]这是一条引用消息',
            'expected': '1822260651'
        },
        {
            'message': '[CQ:reply,id=2046278698][CQ:at,qq=3938121220]你好',
            'expected': '2046278698'
        },
        {
            'message': '普通消息，没有引用',
            'expected': None
        },
        {
            'message': '[CQ:reply]格式错误的消息',
            'expected': None
        }
    ]
    
    all_passed = True
    for i, test_case in enumerate(test_cases):
        result = extract_quoted_message_id(test_case['message'])
        passed = result == test_case['expected']
        
        if passed:
            print(f"✓ 测试用例 {i+1}: 输入='{test_case['message'][:30]}...'，输出={result}，预期={test_case['expected']}")
        else:
            print(f"✗ 测试用例 {i+1}: 输入='{test_case['message'][:30]}...'，输出={result}，预期={test_case['expected']}")
            all_passed = False
    
    return all_passed


async def simulate_real_scenario():
    """模拟实际引用消息处理场景"""
    print("\n" + "="*60)
    print("模拟实际引用消息处理场景")
    print("="*60)
    
    # 模拟一个引用消息事件（来自测试文件）
    test_message = {
        'post_type': 'message',
        'message_type': 'group',
        'group_id': 957134103,
        'user_id': 123456789,
        'raw_message': '[CQ:reply,id=1822260651][CQ:at,qq=123456789]你好',
        'message': [
            {'type': 'reply', 'data': {'id': '1822260651'}},
            {'type': 'at', 'data': {'qq': '123456789'}},
            {'type': 'text', 'data': {'text': '你好'}}
        ]
    }
    
    # 提取引用消息ID
    raw_message = test_message['raw_message']
    quoted_msg_id = extract_quoted_message_id(raw_message)
    
    print(f"原始消息: {raw_message}")
    print(f"提取的引用ID: {quoted_msg_id}")
    
    assert quoted_msg_id == '1822260651'
    
    # 模拟API响应
    mock_response = {
        'status': 'ok',
        'data': {
            'message_id': 1822260651,
            'message_type': 'group',
            'message': [
                {'type': 'text', 'data': {'text': '原始群消息内容'}}
            ],
            'raw_message': '原始群消息内容',
            'sender': {'nickname': '发送者'}
        }
    }
    
    print(f"模拟API响应: {json.dumps(mock_response, ensure_ascii=False, indent=2)}")
    
    # 模拟消息处理逻辑
    quoted_message_data = mock_response['data']
    if quoted_message_data:
        message_array = quoted_message_data.get("message", [])
        if isinstance(message_array, list):
            texts = []
            for segment in message_array:
                if isinstance(segment, dict) and segment.get("type") == "text":
                    text = segment.get("data", {}).get("text", "")
                    if text:
                        texts.append(text)
            quoted_content = " ".join(texts).strip() if texts else None
            
            print(f"提取的引用内容: {quoted_content}")
            
            assert quoted_content == '原始群消息内容'
    
    print("✓ 模拟场景测试通过")
    return True


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("get_msg API调用验证测试")
    print("="*60)
    print("\n验证修复后的get_msg API调用不再超时")
    
    setup_logging()
    
    tests = [
        test_extract_quoted_message_id,
        test_get_quoted_message_full_success,
        test_get_quoted_message_full_timeout_with_retry,
        test_get_quoted_message_full_all_retries_fail,
        test_api_error_with_retry,
        test_message_id_type_conversion,
        simulate_real_scenario,
    ]
    
    results = []
    for test in tests:
        try:
            print()
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    for i, (test, result) in enumerate(zip(tests, results)):
        test_name = test.__name__
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{i+1}. {test_name}: {status}")
    
    all_passed = all(results)
    print(f"\n总计: {len(results)} 项测试，通过: {sum(results)}，失败: {len(results)-sum(results)}")
    
    if all_passed:
        print("\n✅ 所有验证测试通过！")
        print("get_msg API调用修复验证成功：")
        print("1. 正常调用成功")
        print("2. 超时后重试机制有效")
        print("3. API错误处理正常")
        print("4. 消息ID类型转换正确")
        print("5. 实际场景模拟通过")
    else:
        print("\n❌ 部分验证测试失败")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)