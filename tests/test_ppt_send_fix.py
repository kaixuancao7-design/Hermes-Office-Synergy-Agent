"""测试PPT发送功能"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.engine.ppt_workflow import ppt_workflow, WorkflowState
from src.gateway.message_router import message_router
import asyncio


def test_ppt_send():
    """测试PPT发送流程"""
    test_user_id = "send_test_user"

    if hasattr(ppt_workflow, '_contexts') and test_user_id in ppt_workflow._contexts:
        del ppt_workflow._contexts[test_user_id]

    print("=== Step 1: Start workflow ===")
    content = "AI Agent智能协同助手课题"
    document_content = """
AI Agent智能协同助手课题
一、项目背景
IM到演示稿全流程效率提升。
二、具体要求
1. 支持多种文档格式解析
2. 自动生成PPT大纲
"""

    response, ctx = ppt_workflow.start_workflow(
        user_id=test_user_id,
        intent_type="ppt_generate_from_content",
        content=content,
        document_content=document_content
    )

    print(f"State: {ctx.state}")

    print("\n=== Step 2: Confirm settings ===")
    response2, ctx2 = ppt_workflow.continue_workflow(test_user_id, "是")
    print(f"State: {ctx2.state}")

    print("\n=== Step 3: Confirm outline ===")
    response3, ctx3 = ppt_workflow.continue_workflow(test_user_id, "是")
    print(f"State: {ctx3.state}")
    print(f"Output path: {ctx3.output_path}")

    if ctx3.output_path and os.path.exists(ctx3.output_path):
        print(f"[OK] PPT file exists: {ctx3.output_path}")
    else:
        print(f"[WARN] PPT file not found: {ctx3.output_path}")

    print("\n=== Step 4: Test router with PPT completion ===")
    print(f"is_awaiting_confirmation: {ppt_workflow.is_awaiting_confirmation(test_user_id)}")

    print("\n=== Test completed ===")


if __name__ == "__main__":
    test_ppt_send()
