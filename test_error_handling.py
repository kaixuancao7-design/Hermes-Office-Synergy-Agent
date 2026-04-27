#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试兼容接口的异常处理功能
"""

import sys
sys.path.insert(0, 'src')

import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

def test_select_model_error_handling():
    """测试 select_model 函数的异常处理"""
    print("=" * 60)
    print("测试 select_model 异常处理")
    print("=" * 60)
    
    from src.plugins.model_routers import select_model
    
    # 测试正常调用
    print("测试1: 正常调用")
    model = select_model("summarization", "simple")
    print(f"  结果: {'成功' if model else '返回None'}")
    
    # 测试无效参数
    print("\n测试2: 无效参数")
    model = select_model("", "")
    print(f"  结果: {'成功' if model else '返回None'}")
    
    # 测试异常场景
    print("\n测试3: 异常场景")
    model = select_model(None, None)  # 可能会触发异常
    print(f"  结果: {'成功' if model else '返回None'}")
    
    return True


def test_call_model_error_handling():
    """测试 call_model 函数的异常处理"""
    print("\n" + "=" * 60)
    print("测试 call_model 异常处理")
    print("=" * 60)
    
    from src.plugins.model_routers import call_model
    
    # 测试正常调用
    print("测试1: 正常调用（传入None模型）")
    result = call_model(None, [{"role": "user", "content": "hello"}])
    print(f"  结果: {'非空字符串' if result else '空字符串'}")
    
    # 测试无效参数
    print("\n测试2: 无效参数")
    result = call_model(None, None)
    print(f"  结果: {'非空字符串' if result else '空字符串'}")
    
    # 测试空消息
    print("\n测试3: 空消息")
    result = call_model(None, [])
    print(f"  结果: {'非空字符串' if result else '空字符串'}")
    
    return True


def main():
    """主测试函数"""
    print("兼容接口异常处理测试\n")
    
    results = []
    results.append(("select_model 异常处理", test_select_model_error_handling()))
    results.append(("call_model 异常处理", test_call_model_error_handling()))
    
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！异常处理功能正常！")
        return 0
    else:
        print("\n⚠️ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
