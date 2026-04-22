"""测试飞书文件读取工具"""
import sys
import os

# 设置Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from src.plugins.tool_executors import FeishuFileReadTool, BasicToolExecutor


class TestFeishuFileRead:
    """飞书文件读取工具测试类"""
    
    def __init__(self):
        self.tool = FeishuFileReadTool()
        self.executor = BasicToolExecutor()
    
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
            
            assert result["success"] == True, "文件读取失败"
            assert "result" in result, "缺少result字段"
            assert "file_key" in result["result"], "缺少file_key"
            assert "content" in result["result"], "缺少content"
            assert "content_length" in result["result"], "缺少content_length"
            
            print(f"  - file_key: {result['result']['file_key']}")
            print(f"  - content_length: {result['result']['content_length']}")
            print(f"  - 内容预览: {result['result']['content'][:50]}...")
            print("[OK] 通过file_key读取文件测试通过")
            
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
            
            assert result["success"] == True, "工具执行失败"
            assert "result" in result, "缺少result字段"
            
            print(f"  - 工具执行成功")
            print(f"  - file_key: {result['result']['file_key']}")
            print("[OK] 工具执行器集成测试通过")
            
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
    
    test = TestFeishuFileRead()
    
    try:
        test.test_read_file_with_file_key()
        test.test_read_file_without_file_key()
        test.test_read_file_empty_file_key()
        test.test_tool_executor_integration()
        test.test_all_tools_registered()
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        sys.exit(1)
