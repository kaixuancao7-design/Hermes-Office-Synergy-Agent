"""测试工具执行器修复 - 验证飞书文件读取功能"""
import sys
import os

# 设置Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.plugins.tool_executors import BasicToolExecutor


class TestToolExecutorFix:
    """工具执行器修复测试"""
    
    def __init__(self):
        self.executor = BasicToolExecutor()
    
    def test_feishu_file_read_direct_params(self):
        """测试直接参数格式（LLM常用格式）"""
        print("\n=== 测试直接参数格式 ===")
        
        try:
            # 模拟LLM发送的参数格式
            result = self.executor.execute("file_reader", {
                "file_key": "file_v3_test_key",
                "user_id": "test_user_123",
                "file_name": "test.md"
            })
            
            assert result["success"] == True, "工具执行失败"
            assert "result" in result, "缺少result字段"
            print(f"  - 工具执行成功")
            print(f"  - file_key: {result['result']['file_key']}")
            print("[OK] 直接参数格式测试通过")
            
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            raise
    
    def test_feishu_file_read_nested_params(self):
        """测试嵌套参数格式（标准格式）"""
        print("\n=== 测试嵌套参数格式 ===")
        
        try:
            # 标准参数格式
            result = self.executor.execute("feishu_file_read", {
                "parameters": {
                    "file_key": "file_v3_nested_key",
                    "user_id": "test_user_456"
                }
            })
            
            assert result["success"] == True, "工具执行失败"
            assert "result" in result, "缺少result字段"
            print(f"  - 工具执行成功")
            print(f"  - file_key: {result['result']['file_key']}")
            print("[OK] 嵌套参数格式测试通过")
            
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            raise
    
    def test_tool_name_mapping(self):
        """测试工具名称映射"""
        print("\n=== 测试工具名称映射 ===")
        
        try:
            # 测试不同的工具名称映射到同一个工具
            test_names = ["file_reader", "read_file", "feishu_reader", "feishu_file_read"]
            
            for tool_name in test_names:
                result = self.executor.execute(tool_name, {
                    "file_key": f"file_key_{tool_name}",
                    "user_id": "test_user"
                })
                
                assert result["success"] == True, f"{tool_name} 执行失败"
                print(f"  - {tool_name}: OK")
            
            print("[OK] 工具名称映射测试通过")
            
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            raise
    
    def test_missing_tool_id(self):
        """测试缺少工具ID"""
        print("\n=== 测试缺少工具ID ===")
        
        try:
            result = self.executor.execute(None, {
                "file_key": "test_key"
            })
            
            assert result["success"] == False, "应该失败"
            assert "error" in result, "缺少error字段"
            print(f"  - 错误信息: {result['error']}")
            print("[OK] 缺少工具ID测试通过")
            
        except Exception as e:
            print(f"[FAIL] 测试失败: {e}")
            raise


if __name__ == "__main__":
    print("=" * 60)
    print("工具执行器修复测试")
    print("=" * 60)
    
    test = TestToolExecutorFix()
    
    try:
        test.test_feishu_file_read_direct_params()
        test.test_feishu_file_read_nested_params()
        test.test_tool_name_mapping()
        test.test_missing_tool_id()
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        sys.exit(1)
