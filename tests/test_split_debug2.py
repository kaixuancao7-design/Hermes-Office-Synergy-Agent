"""测试大纲生成"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.engine.ppt_workflow import ppt_workflow, WorkflowState, PPTWorkflowContext

content = "AI Agent智能协同助手课题"
document_content = """
AI Agent智能协同助手课题
一、项目背景
IM到演示稿全流程效率提升是当前企业办公自动化的重要方向。
二、具体要求
1. 支持多种文档格式解析
2. 自动生成PPT大纲
3. 一键生成演示稿
三、实施步骤
1. 需求分析
2. 技术选型
3. 开发实现
4. 测试验证
四、预期成果
提升办公效率50%以上
"""

test_user_id = "debug_user"

if hasattr(ppt_workflow, '_contexts') and test_user_id in ppt_workflow._contexts:
    del ppt_workflow._contexts[test_user_id]

ctx = ppt_workflow._get_context(test_user_id)
ctx.content = content
ctx.document_content = document_content

print("=== Testing _split_content_sections ===")
sections = ppt_workflow._split_content_sections(document_content)
print(f"Total sections: {len(sections)}")
for i, s in enumerate(sections, 1):
    first_line = s.split('\n')[0][:50]
    print(f"  Section {i}: {first_line}")

print("\n=== Testing _generate_outline_from_content ===")
outline = ppt_workflow._generate_outline_from_content(ctx)
print(f"Total outline items: {len(outline)}")
for i, item in enumerate(outline, 1):
    print(f"  {i}. {item.get('title', '')[:50]}")
