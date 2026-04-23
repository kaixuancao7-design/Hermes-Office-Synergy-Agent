"""测试飞书文件读取工具"""
import sys
import os

# 设置Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from src.plugins.tool_executors import FeishuFileReadTool, BasicToolExecutor
from src.config import settings


class TestFeishuFileRead:
    """飞书文件读取工具测试类"""
    
    tool = FeishuFileReadTool()
    executor = BasicToolExecutor()
    
    def has_feishu_config(self):
        """检查是否有飞书配置"""
        return settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET
    
    def test_read_file_with_file_key(self):
        """测试通过file_key读取文件"""
        print("\n=== 测试通过file_key读取文件 ===")
        
        try:
            # 测试参数
            parameters = {
                "file_key": "file_v3_00110_d49a79d6-b484-41a7-85dc-3f292d4bdb3g",
                "user_id": "test_user_123"
            }
            
            result = self.tool.execute(parameters)
            
            if self.has_feishu_config():
                # 如果有配置，期望成功
                assert result["success"] == True, "文件读取失败"
                assert "result" in result, "缺少result字段"
                assert "file_key" in result["result"], "缺少file_key"
                assert "content" in result["result"], "缺少content"
                assert "content_length" in result["result"], "缺少content_length"
                
                print(f"  - file_key: {result['result']['file_key']}")
                print(f"  - content_length: {result['result']['content_length']}")
                print(f"  - 内容预览: {result['result']['content'][:50]}...")
                print("[OK] 通过file_key读取文件测试通过")
            else:
                # 如果没有配置，期望失败并返回明确的错误信息
                assert result["success"] == False, "应该失败（未配置飞书API）"
                assert "error" in result, "缺少error字段"
                print(f"  - 预期失败（未配置飞书API）")
                print(f"  - 错误信息: {result['error']}")
                print("[OK] 通过file_key读取文件测试通过（预期失败）")
            
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            raise
    
    def test_read_file_with_message_id(self):
        """测试使用message_id参数读取文件（推荐接口）"""
        print("\n=== 测试使用message_id参数读取文件 ===")
        
        try:
            # 测试参数（包含message_id）
            parameters = {
                "file_key": "file_v3_00111_64032db0-8bc3-4aa6-972d-1b4d844e4e7g",
                "message_id": "om_abc123456",
                "user_id": "test_user_123"
            }
            
            result = self.tool.execute(parameters)
            
            if self.has_feishu_config():
                # 如果有配置，期望成功
                assert result["success"] == True, "文件读取失败"
                assert "result" in result, "缺少result字段"
                assert "file_key" in result["result"], "缺少file_key"
                assert "content" in result["result"], "缺少content"
                
                print(f"  - file_key: {result['result']['file_key']}")
                print(f"  - content_length: {result['result']['content_length']}")
                print(f"  - 内容预览: {result['result']['content'][:50]}...")
                print("[OK] 使用message_id参数读取文件测试通过")
            else:
                # 如果没有配置，期望失败并返回明确的错误信息
                assert result["success"] == False, "应该失败（未配置飞书API）"
                assert "error" in result, "缺少error字段"
                print(f"  - 预期失败（未配置飞书API）")
                print(f"  - 错误信息: {result['error']}")
                print("[OK] 使用message_id参数读取文件测试通过（预期失败）")
            
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            raise
    
    def test_read_file_without_file_key(self):
        """测试缺少file_key参数"""
        print("\n=== 测试缺少file_key参数 ===")
        
        try:
            parameters = {
                "user_id": "test_user_123"
            }
            
            result = self.tool.execute(parameters)
            
            assert result["success"] == False, "应该失败"
            assert "error" in result, "缺少error字段"
            assert "缺少file_key参数" in result["error"], "错误信息不正确"
            
            print(f"  - 错误信息: {result['error']}")
            print("[OK] 缺少file_key参数测试通过")
            
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            raise
    
    def test_read_file_empty_file_key(self):
        """测试空file_key"""
        print("\n=== 测试空file_key ===")
        
        try:
            parameters = {
                "file_key": "",
                "user_id": "test_user_123"
            }
            
            result = self.tool.execute(parameters)
            
            assert result["success"] == False, "应该失败"
            assert "error" in result, "缺少error字段"
            
            print(f"  - 错误信息: {result['error']}")
            print("[OK] 空file_key测试通过")
            
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            raise
    
    def test_tool_executor_integration(self):
        """测试工具执行器集成"""
        print("\n=== 测试工具执行器集成 ===")
        
        try:
            # 使用工具执行器调用飞书文件读取工具
            result = self.executor.execute("feishu_file_read", {
                "file_key": "file_v3_test_key",
                "user_id": "test_user_456"
            })
            
            if self.has_feishu_config():
                # 如果有配置，期望成功
                assert result["success"] == True, "工具执行失败"
                assert "result" in result, "缺少result字段"
                
                print(f"  - 工具执行成功")
                print(f"  - file_key: {result['result']['file_key']}")
                print("[OK] 工具执行器集成测试通过")
            else:
                # 如果没有配置，期望失败并返回明确的错误信息
                assert result["success"] == False, "应该失败（未配置飞书API）"
                assert "error" in result, "缺少error字段"
                print(f"  - 预期失败（未配置飞书API）")
                print(f"  - 错误信息: {result['error']}")
                print("[OK] 工具执行器集成测试通过（预期失败）")
            
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            raise
    
    def test_all_tools_registered(self):
        """测试所有工具是否已注册"""
        print("\n=== 测试工具注册 ===")
        
        try:
            tools = self.executor.get_tools()
            
            assert "feishu_file_read" in tools, "feishu_file_read工具未注册"
            assert "document_search" in tools, "document_search工具未注册"
            assert "memory_search" in tools, "memory_search工具未注册"
            assert "file_operations" in tools, "file_operations工具未注册"
            
            print(f"  - 已注册工具: {tools}")
            print("[OK] 工具注册测试通过")
            
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            raise


if __name__ == "__main__":
    print("=" * 60)
    print("飞书文件读取工具测试")
    print("=" * 60)
    
    # 检查飞书配置状态
    has_config = settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET
    if has_config:
        print(f"  - 飞书API配置: 已配置")
    else:
        print(f"  - 飞书API配置: 未配置（部分测试将预期失败）")
    print("-" * 60)
    
    test = TestFeishuFileRead()
    
    passed = 0
    failed = 0
    
    tests = [
        ("test_read_file_with_file_key", test.test_read_file_with_file_key),
        ("test_read_file_with_message_id", test.test_read_file_with_message_id),
        ("test_read_file_without_file_key", test.test_read_file_without_file_key),
        ("test_read_file_empty_file_key", test.test_read_file_empty_file_key),
        ("test_tool_executor_integration", test.test_tool_executor_integration),
        ("test_all_tools_registered", test.test_all_tools_registered),
    ]
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n[ERROR] {test_name} 测试失败: {e}")
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    if failed > 0:
        sys.exit(1)