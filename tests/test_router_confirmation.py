"""测试路由器对确认消息的处理"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.engine.ppt_workflow import ppt_workflow, WorkflowState
from src.gateway.message_router import MessageRouter


def test_router_with_outline_confirmation():
    """测试路由器是否正确处理大纲确认"""
    test_user_id = "router_test_user"
    
    if hasattr(ppt_workflow, '_contexts') and test_user_id in ppt_workflow._contexts:
        del ppt_workflow._contexts[test_user_id]

    router = MessageRouter()

    print("=== Step 1: 用户请求生成PPT ===")
    document_content = """
AI Agent智能协同助手课题
一、项目背景
IM到演示稿全流程效率提升。
二、具体要求
1. 支持多种文档格式解析
2. 自动生成PPT大纲
"""

    response = router.route_message(
        user_id=test_user_id,
        content=f"根据文档生成PPT给我",
        document_content=document_content
    )
    print(f"Response: {response[:80]}")

    print("\n=== Step 2: 用户确认设置 ===")
    response2 = router.route_message(
        user_id=test_user_id,
        content="是"
    )
    print(f"Response: {response2[:80]}")

    print("\n=== Step 3: 用户确认大纲 ===")
    response3 = router.route_message(
        user_id=test_user_id,
        content="是"
    )
    print(f"Response: {response3[:80]}")

    ctx = ppt_workflow._contexts.get(test_user_id)
    print(f"\nFinal state: {ctx.state if ctx else 'No context'}")
    
    assert ctx.state == WorkflowState.COMPLETED, f"Expected COMPLETED but got {ctx.state}"
    print("\n=== Test PASSED: Router correctly handles outline confirmation ===")


if __name__ == "__main__":
    test_router_with_outline_confirmation()
