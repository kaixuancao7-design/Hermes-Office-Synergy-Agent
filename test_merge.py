#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
合并验证测试脚本 - 验证重复模块合并后的功能正确性
"""

import sys
sys.path.insert(0, 'src')

import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

def test_intent_recognition():
    """测试意图识别功能"""
    print("=" * 60)
    print("测试意图识别功能")
    print("=" * 60)
    
    try:
        from src.engine.intent_recognition import intent_recognizer, contextual_analyzer
        
        # 测试基础意图识别
        test_cases = [
            "帮我生成一个PPT大纲",
            "根据这个文件生成PPT",
            "总结一下文档内容",
            "读取这个文件",
            "做个产品介绍ppt"
        ]
        
        for text in test_cases:
            intent = intent_recognizer.recognize(text)
            print(f"输入: {text}")
            print(f"  意图: {intent.type}, 置信度: {intent.confidence:.2f}")
            print(f"  实体: {intent.entities}")
            print()
        
        # 测试上下文感知分析
        context = {
            "recent_files": ["test_document.pdf"],
            "last_upload_time": "2024-01-01 10:00",
            "session_id": "test_session"
        }
        
        analysis = contextual_analyzer.analyze_with_context("读取这个文件", context)
        print("上下文分析测试:")
        print(f"  输入: 读取这个文件")
        print(f"  分析结果: {analysis}")
        print()
        
        return True
    except Exception as e:
        print(f"❌ 意图识别测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_model_router():
    """测试模型路由功能"""
    print("=" * 60)
    print("测试模型路由功能")
    print("=" * 60)
    
    try:
        from src.plugins.model_routers import select_model, call_model, OllamaRouter, OpenAIRouter, MultiModelRouter
        
        # 测试 select_model 函数（兼容旧接口）
        model = select_model("summarization", "simple")
        print(f"选择模型: {model is not None}")
        
        # 测试路由器类
        routers = [
            ("OllamaRouter", OllamaRouter()),
            ("OpenAIRouter", OpenAIRouter()),
            ("MultiModelRouter", MultiModelRouter())
        ]
        
        for name, router in routers:
            try:
                model = router.select_model("general", "simple")
                print(f"{name}.select_model(): {model is not None}")
            except Exception as e:
                print(f"{name}.select_model(): 不可用 ({str(e)})")
        
        return True
    except Exception as e:
        print(f"❌ 模型路由测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_skill_manager():
    """测试技能管理器功能"""
    print("=" * 60)
    print("测试技能管理器功能")
    print("=" * 60)
    
    try:
        from src.skills import skill_manager
        
        # 测试延迟初始化
        print(f"技能管理器已初始化: {skill_manager._internal_skills_loaded}")
        
        # 测试注册外部技能
        skill_manager.register_external_skills()
        print(f"外部技能已注册: {skill_manager._external_skills_registered}")
        
        return True
    except Exception as e:
        print(f"❌ 技能管理器测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_tools_import():
    """测试工具导入"""
    print("=" * 60)
    print("测试工具导入")
    print("=" * 60)
    
    try:
        from src.tools.ppt_generator import PPTGeneratorBase, GeneratePPT, GeneratePPTFromOutline
        from src.tools.file_reader import FeishuFileRead
        from src.tools.content_tools import GenerateSummary
        
        print("PPT生成工具: 已导入")
        print("文件读取工具: 已导入")
        print("内容处理工具: 已导入")
        
        return True
    except Exception as e:
        print(f"❌ 工具导入测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_plugins():
    """测试插件系统"""
    print("=" * 60)
    print("测试插件系统")
    print("=" * 60)
    
    try:
        from src.plugins import (
            initialize_plugins,
            get_tool_executor,
            get_model_router,
            get_im_adapter
        )
        
        # 测试初始化
        initialize_plugins()
        
        # 测试获取工具执行器
        executor = get_tool_executor()
        print(f"工具执行器: {executor is not None}")
        
        # 测试获取模型路由器
        router = get_model_router()
        print(f"模型路由器: {router is not None}")
        
        # 测试获取IM适配器
        adapter = get_im_adapter()
        print(f"IM适配器: {adapter is not None}")
        
        return True
    except Exception as e:
        print(f"❌ 插件系统测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("模块合并验证测试")
    print("=" * 60 + "\n")
    
    results = []
    
    # 运行所有测试
    results.append(("意图识别", test_intent_recognition()))
    results.append(("模型路由", test_model_router()))
    results.append(("技能管理器", test_skill_manager()))
    results.append(("工具导入", test_tools_import()))
    results.append(("插件系统", test_plugins()))
    
    # 输出汇总
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
        print("\n🎉 所有测试通过！模块合并成功！")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
