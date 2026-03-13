#!/usr/bin/env python3
"""
测试 pyrightconfig.json 配置是否解决了 LSP 导入问题
"""

import sys
import os
from pathlib import Path

# 项目根目录（注意：此文件位于 tests/ 目录下）
project_root = Path(__file__).parent.parent
print(f"项目根目录: {project_root}")

# 将 src 添加到 sys.path（模拟 pyrightconfig.json 的 extraPaths）
if str(project_root / "src") not in sys.path:
    sys.path.insert(0, str(project_root / "src"))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print(f"当前 sys.path 前 3 项:")
for i, path in enumerate(sys.path[:3]):
    print(f"  {i}: {path}")

def test_config_import():
    """测试 config 模块导入"""
    print("\n=== 测试 config 模块导入 ===")
    try:
        from src.utils import config
        print("✅ from src.utils import config - 成功")
        
        # 测试一些配置值
        print(f"✅ WS_URL: {config.WS_URL}")
        print(f"✅ OPENCODE_HOST: {config.OPENCODE_HOST}")
        print(f"✅ OPENCODE_DEFAULT_AGENT: {config.OPENCODE_DEFAULT_AGENT}")
        
        return True
    except ImportError as e:
        print(f"❌ config 导入失败: {e}")
        return False
    except AttributeError as e:
        print(f"❌ config 属性访问失败: {e}")
        return False

def test_session_manager_import():
    """测试 session_manager 模块导入"""
    print("\n=== 测试 session_manager 模块导入 ===")
    try:
        # session_manager 应该能导入 config
        from src.session import session_manager
        print("✅ from src.session import session_manager - 成功")
        
        # 测试创建实例
        from src.session.session_manager import SessionManager
        print("✅ SessionManager 类导入成功")
        
        # 尝试创建实例（使用默认配置）
        sm = SessionManager()
        print("✅ SessionManager 实例创建成功")
        
        return True
    except ImportError as e:
        print(f"❌ session_manager 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ session_manager 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_core_module_import():
    """测试 core 模块导入（使用标准导入模式）"""
    print("\n=== 测试 core 模块导入 ===")
    try:
        from src.core import config_manager
        print("✅ from src.core import config_manager - 成功")
        
        from src.core import api_sender
        print("✅ from src.core import api_sender - 成功")
        
        from src.core import napcat_http_client
        print("✅ from src.core import napcat_http_client - 成功")
        
        return True
    except ImportError as e:
        print(f"❌ core 模块导入失败: {e}")
        return False

def test_pyright_config():
    """验证 pyrightconfig.json 配置"""
    print("\n=== 验证 pyrightconfig.json 配置 ===")
    config_file = project_root / "pyrightconfig.json"
    if config_file.exists():
        print(f"✅ pyrightconfig.json 文件存在: {config_file}")
        try:
            import json
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            extra_paths = config_data.get('executionEnvironments', [{}])[0].get('extraPaths', [])
            print(f"✅ 配置 extraPaths: {extra_paths}")
            
            if 'src' in extra_paths:
                print("✅ 配置中包含 'src' 路径")
            else:
                print("⚠️ 配置中未包含 'src' 路径")
                
            return True
        except Exception as e:
            print(f"❌ 读取配置文件失败: {e}")
            return False
    else:
        print(f"❌ pyrightconfig.json 文件不存在")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("LSP 配置测试脚本")
    print("=" * 60)
    
    tests = [
        ("pyrightconfig.json 配置", test_pyright_config),
        ("config 模块导入", test_config_import),
        ("core 模块导入", test_core_module_import),
        ("session_manager 导入", test_session_manager_import),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n▶ 执行测试: {test_name}")
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！LSP 配置生效。")
    else:
        print("⚠️  部分测试失败，请检查配置。")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)