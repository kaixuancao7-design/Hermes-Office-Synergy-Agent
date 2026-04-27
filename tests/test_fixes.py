#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试修复后的功能
"""

import sys
sys.path.insert(0, 'src')

import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

def test_contextual_analyzer():
    """测试 ContextualIntentAnalyzer.suggest_next_action 方法"""
    print("=" * 60)
    print("测试 ContextualIntentAnalyzer.suggest_next_action")
    print("=" * 60)
    
    from src.engine.intent_recognition import contextual_analyzer
    
    test_cases = [
        # (分析结果, 上下文, 预期建议)
        (
            {"intent": "unknown", "has_referential": True},
            {},
            "询问用户对文件的具体操作需求"
        ),
        (
            {"intent": "ppt_generate_outline", "has_referential": False},
            {},
            "读取文件内容"
        ),
        (
            {"intent": "summarization", "has_referential": False},
            {},
            "读取文件内容"
        ),
        (
            {"intent": "document_analysis", "has_referential": False},
            {},
            "读取文件内容"
        ),
        (
            {"intent": "memory_query", "has_referential": False},
            {},
            "执行记忆搜索"
        ),
        (
            {"intent": "question_answering", "has_referential": False},
            {"chat_history": ["msg1", "msg2"]},
            "先搜索历史对话记忆"
        ),
        (
            {"intent": "code_generation", "has_referential": False, "entities": {}},
            {},
            "询问用户目标编程语言"
        ),
        (
            {"intent": "creative_writing", "has_referential": False},
            {},
            None  # 没有特别建议
        ),
    ]
    
    all_passed = True
    for i, (analysis, context, expected) in enumerate(test_cases):
        result = contextual_analyzer.suggest_next_action(analysis, context)
        passed = result == expected
        status = "✅" if passed else "❌"
        if not passed:
            all_passed = False
        print(f"测试{i+1}: {status}")
        print(f"  意图: {analysis['intent']}")
        print(f"  预期: {expected}")
        print(f"  实际: {result}")
        print()
    
    return all_passed


def test_document_search_tool():
    """测试 DocumentSearchTool 待实现标记"""
    print("=" * 60)
    print("测试 DocumentSearchTool 待实现标记")
    print("=" * 60)
    
    from src.plugins.tool_executors import DocumentSearchTool
    
    tool = DocumentSearchTool()
    result = tool.execute({"query": "test", "limit": 10})
    
    print(f"success: {result.get('success')}")
    print(f"result: {result.get('result')}")
    print(f"message: {result.get('message')}")
    print(f"status: {result.get('status')}")
    
    # 验证返回结构
    has_message = "message" in result
    has_status = "status" in result
    is_pending = result.get("status") == "pending_implementation"
    
    print(f"\n验证结果:")
    print(f"  ✅ 包含 message 字段: {has_message}")
    print(f"  ✅ 包含 status 字段: {has_status}")
    print(f"  ✅ status 为 pending_implementation: {is_pending}")
    
    return has_message and has_status and is_pending


def main():
    """主测试函数"""
    print("修复验证测试\n")
    
    results = []
    results.append(("ContextualIntentAnalyzer", test_contextual_analyzer()))
    results.append(("DocumentSearchTool", test_document_search_tool()))
    
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
        print("\n🎉 所有测试通过！修复验证成功！")
        return 0
    else:
        print("\n⚠️ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
