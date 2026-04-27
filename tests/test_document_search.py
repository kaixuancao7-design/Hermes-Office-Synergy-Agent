#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试文档搜索工具功能
"""

import sys
sys.path.insert(0, 'src')

import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 设置标准输出编码
sys.stdout.reconfigure(encoding='utf-8')

def test_document_search_tool():
    """测试 DocumentSearchTool 功能"""
    print("=" * 60)
    print("测试 DocumentSearchTool 文档搜索功能")
    print("=" * 60)
    
    from src.plugins.tool_executors import DocumentSearchTool
    
    tool = DocumentSearchTool()
    
    test_cases = [
        # (参数, 预期成功)
        ({"query": "test"}, True),
        ({"query": "人工智能", "limit": 10}, True),
        ({"query": ""}, False),  # 空查询应该失败
        ({"limit": 5}, False),   # 缺少query参数
        ({"query": "测试搜索", "user_id": "test_user"}, True),
    ]
    
    all_passed = True
    for i, (params, expect_success) in enumerate(test_cases):
        print("\n测试{0}: 参数={1}".format(i+1, params))
        result = tool.execute(params)
        
        success = result.get("success", False)
        status = result.get("status", "")
        
        passed = success == expect_success
        
        if passed:
            print("  [通过] 成功: {0}, 状态: {1}".format(success, status))
        else:
            print("  [失败] 成功: {0}, 状态: {1}".format(success, status))
            all_passed = False
        
        print("  消息: {0}".format(result.get('message', '')))
        print("  结果数: {0}".format(len(result.get('result', []))))
    
    return all_passed


def test_vector_store_search():
    """测试向量存储搜索功能"""
    print("\n" + "=" * 60)
    print("测试向量存储搜索功能")
    print("=" * 60)
    
    try:
        from src.data.vector_store import vector_store
        
        # 测试搜索
        results = vector_store.search("test", k=3)
        
        print("搜索结果数量: {0}".format(len(results)))
        if results:
            for i, r in enumerate(results):
                print("  结果{0}:".format(i+1))
                print("    ID: {0}".format(r.get('id', '')))
                content = r.get('content', '')[:50]
                print("    内容长度: {0}...".format(len(content)))
                print("    距离: {0}".format(r.get('distance', 0)))
        
        return True
    except Exception as e:
        print("[失败] 向量存储测试失败: {0}".format(str(e)))
        return False


def main():
    """主测试函数"""
    print("文档搜索工具测试\n")
    
    results = []
    results.append(("DocumentSearchTool", test_document_search_tool()))
    results.append(("VectorStore搜索", test_vector_store_search()))
    
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "[通过]" if success else "[失败]"
        print("{0}: {1}".format(name, status))
    
    print("\n总计: {0}/{1} 通过".format(passed, total))
    
    if passed == total:
        print("\n测试完成: 所有测试通过！")
        return 0
    else:
        print("\n测试完成: 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
