"""简化的文件读取工具测试 - 仅测试错误处理逻辑"""
import sys
import os

# 设置Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接测试工具类，避免初始化其他服务
from src.plugins.tool_executors import FeishuFileReadTool


def test_error_handling():
    """测试错误处理逻辑"""
    print("=" * 60)
    print("飞书文件读取工具 - 错误处理测试")
    print("=" * 60)
    
    tool = FeishuFileReadTool()
    passed = 0
    failed = 0
    
    # 测试1: 缺少file_key参数
    print("\n--- 测试1: 缺少file_key参数 ---")
    try:
        result = tool.execute({"user_id": "test_user"})
        assert result["success"] == False, "应该失败"
        assert "error" in result, "缺少error字段"
        assert "缺少file_key参数" in result["error"], f"错误信息不正确: {result['error']}"
        print(f"  ✓ 错误信息正确: {result['error']}")
        passed += 1
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        failed += 1
    
    # 测试2: 空file_key
    print("\n--- 测试2: 空file_key ---")
    try:
        result = tool.execute({"file_key": "", "user_id": "test_user"})
        assert result["success"] == False, "应该失败"
        assert "error" in result, "缺少error字段"
        print(f"  ✓ 错误信息正确: {result['error']}")
        passed += 1
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        failed += 1
    
    # 测试3: 无效配置（无飞书API配置时）
    print("\n--- 测试3: 无飞书API配置时的错误处理 ---")
    try:
        result = tool.execute({"file_key": "test_file_key", "user_id": "test_user"})
        assert result["success"] == False, "应该失败（无配置）"
        assert "error" in result, "缺少error字段"
        print(f"  ✓ 返回明确的错误信息: {result['error']}")
        passed += 1
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        failed += 1
    
    # 测试4: 验证没有返回模拟数据
    print("\n--- 测试4: 验证没有返回模拟数据 ---")
    try:
        result = tool.execute({"file_key": "test_file_key", "user_id": "test_user"})
        # 检查是否返回了模拟数据
        if result["success"] == False:
            # 失败时不应该包含模拟数据内容
            error_msg = result.get("error", "")
            assert "模拟文件内容" not in error_msg, "不应该包含模拟数据"
            assert "AI Agent智能协同助手" not in error_msg, "不应该包含模拟数据"
            print(f"  ✓ 未返回模拟数据")
            passed += 1
        else:
            # 如果成功（有配置的情况下），检查内容
            content = result["result"].get("content", "")
            assert "模拟文件内容" not in content, "不应该包含模拟数据"
            print(f"  ✓ 未返回模拟数据")
            passed += 1
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        failed += 1
    
    # 测试5: 参数格式验证
    print("\n--- 测试5: 无效参数格式 ---")
    try:
        result = tool.execute({"file_key": 123, "user_id": "test_user"})  # file_key应该是字符串
        # 即使类型不对，也应该优雅处理
        print(f"  ✓ 优雅处理无效参数类型")
        passed += 1
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        failed += 1
    
    # 输出结果
    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = test_error_handling()
    sys.exit(0 if success else 1)