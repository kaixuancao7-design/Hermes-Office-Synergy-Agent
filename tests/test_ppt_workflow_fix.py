"""PPT工作流修复测试 - 验证用户确认响应处理"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import Mock, patch, MagicMock
from src.engine.ppt_workflow import ppt_workflow, WorkflowState
from src.gateway.message_router import MessageRouter, message_router
from src.types import Message, Intent


class TestPPTWorkflowFix:
    """测试PPT工作流修复 - 用户确认响应处理"""
    
    def test_ppt_workflow_confirmation_flow(self):
        """测试PPT工作流确认流程"""
        test_user_id = "test_user_ppt_001"
        
        # 清除之前的上下文
        if hasattr(ppt_workflow, '_contexts') and test_user_id in ppt_workflow._contexts:
            del ppt_workflow._contexts[test_user_id]
        
        # 步骤1: 用户请求生成PPT
        print("=== 步骤1: 用户请求生成PPT ===")
        content = "根据AI Agent智能协同助手课题具体要求生成PPT"
        document_content = "这是测试文档内容\n\n第一部分：项目背景\n第二部分：实施步骤\n第三部分：预期成果"
        
        response, ctx = ppt_workflow.start_workflow(
            user_id=test_user_id,
            intent_type="ppt_generate_from_content",
            content=content,
            document_content=document_content
        )
        
        print("响应消息:", response)
        print("工作流状态:", ctx.state)
        
        # 验证状态是否正确设置为 AWAITING_CONFIRMATION
        assert ctx.state == WorkflowState.AWAITING_CONFIRMATION, "期望状态 AWAITING_CONFIRMATION，实际状态 " + str(ctx.state)
        print("[OK] 状态正确设置为 AWAITING_CONFIRMATION")
        
        # 验证响应消息包含确认提示
        assert "是否使用以上设置生成PPT" in response, "响应消息应包含确认提示"
        assert "回复 `是` 继续" in response, "响应消息应包含继续提示"
        print("[OK] 响应消息包含确认提示")
        
        # 步骤2: 用户回复"是"
        print("\n=== 步骤2: 用户回复'是' ===")
        user_response = "是"
        
        response2, ctx2 = ppt_workflow.continue_workflow(test_user_id, user_response)
        
        if len(response2) > 200:
            print("响应消息:", response2[:200], "...")
        else:
            print("响应消息:", response2)
        print("工作流状态:", ctx2.state)
        
        # 验证状态是否转换为 GENERATING 或 COMPLETED
        assert ctx2.state in [WorkflowState.GENERATING, WorkflowState.COMPLETED, WorkflowState.QUALITY_CHECKING], \
            "期望状态 GENERATING/COMPLETED/QUALITY_CHECKING，实际状态 " + str(ctx2.state)
        print("[OK] 用户确认后状态正确转换")
        
        # 验证 is_awaiting_confirmation 返回 False
        assert ppt_workflow.is_awaiting_confirmation(test_user_id) == False, "确认后不应再处于等待确认状态"
        print("[OK] is_awaiting_confirmation 返回 False")
        
        print("\n=== 测试通过！PPT工作流确认流程正常工作 ===")


if __name__ == "__main__":
    test = TestPPTWorkflowFix()
    test.test_ppt_workflow_confirmation_flow()
