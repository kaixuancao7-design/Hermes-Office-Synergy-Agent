"""PPT工作流大纲生成测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.engine.ppt_workflow import ppt_workflow, WorkflowState


class TestPPTOutlineFlow:
    """测试PPT大纲生成流程"""

    def test_outline_flow(self):
        """测试完整的大纲生成流程"""
        test_user_id = "test_outline_user_002"

        if hasattr(ppt_workflow, '_contexts') and test_user_id in ppt_workflow._contexts:
            del ppt_workflow._contexts[test_user_id]

        print("=== Step 1: Request PPT generation ===")
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

        response, ctx = ppt_workflow.start_workflow(
            user_id=test_user_id,
            intent_type="ppt_generate_from_content",
            content=content,
            document_content=document_content
        )

        print(f"State: {ctx.state}")
        print(f"Response: {response[:150]}...")

        assert ctx.state == WorkflowState.AWAITING_CONFIRMATION
        print("[OK] Step 1: Planning phase, awaiting confirmation\n")

        print("=== Step 2: User confirms settings ===")
        response2, ctx2 = ppt_workflow.continue_workflow(test_user_id, "Yes")

        print(f"State: {ctx2.state}")
        print(f"Outline count: {len(ctx2.outline)}")
        print("Outline preview:")
        for i, item in enumerate(ctx2.outline, 1):
            title = item.get('title', '')[:40]
            print(f"  {i}. {title}")

        assert ctx2.state == WorkflowState.OUTLINE_CONFIRMING
        assert ctx2.outline is not None
        assert len(ctx2.outline) >= 4
        print(f"[OK] Step 2: Generated outline with {len(ctx2.outline)} sections\n")

        print("=== Step 3: User confirms outline ===")
        response3, ctx3 = ppt_workflow.continue_workflow(test_user_id, "Yes")

        print(f"State: {ctx3.state}")
        if ctx3.slides:
            print(f"Slides count: {len(ctx3.slides)}")

        assert ctx3.state in [WorkflowState.GENERATING, WorkflowState.QUALITY_CHECKING, WorkflowState.COMPLETED]
        print("[OK] Step 3: Outline confirmed, entering generation phase")

        print("\n=== Test PASSED ===")


if __name__ == "__main__":
    test = TestPPTOutlineFlow()
    test.test_outline_flow()
