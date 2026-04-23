"""测试错误消息处理 - 不导入完整工具"""
import sys
import os

# 设置Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置标准输出编码
sys.stdout.reconfigure(encoding='utf-8')

# 只导入需要的部分，避免触发不必要的初始化
from src.config import settings


def test_error_messages():
    """测试错误消息处理"""
    print("=" * 60)
    print("错误消息处理测试")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    # 测试1: 检查飞书配置状态
    print("\n--- 测试1: 检查飞书配置状态 ---")
    has_config = settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET
    if has_config:
        print("  OK 飞书API配置已设置")
    else:
        print("  OK 飞书API配置未设置（预期状态）")
    passed += 1
    
    # 测试2: 验证配置字段存在
    print("\n--- 测试2: 验证配置字段 ---")
    try:
        assert hasattr(settings, 'FEISHU_APP_ID'), "缺少FEISHU_APP_ID配置"
        assert hasattr(settings, 'FEISHU_APP_SECRET'), "缺少FEISHU_APP_SECRET配置"
        print("  OK 配置字段存在")
        passed += 1
    except Exception as e:
        print(f"  FAIL 测试失败: {e}")
        failed += 1
    
    # 测试3: 验证错误消息格式
    print("\n--- 测试3: 验证错误消息格式 ---")
    try:
        import inspect
        from src.plugins import tool_executors
        
        source_code = inspect.getsource(tool_executors.FeishuFileReadTool)
        
        # 检查关键错误消息是否存在
        assert "缺少file_key参数" in source_code, "缺少预期的错误消息"
        assert "文件下载失败" in source_code, "缺少预期的错误消息"
        assert "请检查飞书配置" in source_code, "缺少预期的错误消息"
        assert "exc_info=True" in source_code, "缺少exc_info=True参数"
        
        print("  OK 错误消息格式正确")
        passed += 1
    except Exception as e:
        print(f"  FAIL 测试失败: {e}")
        failed += 1
    
    # 测试4: 验证没有模拟数据
    print("\n--- 测试4: 验证没有模拟数据返回 ---")
    try:
        import inspect
        from src.plugins import tool_executors
        
        source_code = inspect.getsource(tool_executors.FeishuFileReadTool)
        
        # 检查是否删除了模拟数据
        assert "模拟文件内容" not in source_code, "不应该包含模拟数据"
        assert "AI Agent智能协同助手" not in source_code, "不应该包含模拟数据"
        
        # 检查im_adapters中的方法
        from src.plugins import im_adapters
        adapter_source = inspect.getsource(im_adapters.FeishuAdapter)
        assert "模拟文件内容" not in adapter_source, "不应该包含模拟数据"
        
        print("  OK 已移除模拟数据返回")
        passed += 1
    except Exception as e:
        print(f"  FAIL 测试失败: {e}")
        failed += 1
    
    # 测试5: 验证日志增强
    print("\n--- 测试5: 验证日志增强 ---")
    try:
        import inspect
        from src.plugins import tool_executors
        
        source_code = inspect.getsource(tool_executors.FeishuFileReadTool)
        
        # 检查日志增强
        assert 'logger.error(f"' in source_code, "缺少增强的日志记录"
        assert 'exc_info=True' in source_code, "缺少exc_info=True参数"
        
        print("  OK 日志增强已实现")
        passed += 1
    except Exception as e:
        print(f"  FAIL 测试失败: {e}")
        failed += 1
    
    # 输出结果
    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = test_error_messages()
    sys.exit(0 if success else 1)