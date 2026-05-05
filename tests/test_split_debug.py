"""测试内容分割"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.engine.ppt_workflow import ppt_workflow

content = """
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

print("原始内容:")
print(repr(content))
print("\n分割结果:")

sections = ppt_workflow._split_content_sections(content)
for i, s in enumerate(sections, 1):
    print(f"\n--- 章节 {i} ---")
    print(repr(s[:100]) + "..." if len(s) > 100 else repr(s))
