import pytest
from unittest.mock import Mock, patch, MagicMock
from src.engine.react_engine import (
    ReActEngine,
    Action,
    Observation,
    ReActState,
    RecoveryAnalysis
)


class TestReActEngineRecovery:
    """ReAct引擎反思和恢复机制测试"""

    def test_analyze_failure_parameter_error(self):
        """测试分析参数错误类型的失败"""
        engine = ReActEngine()
        action = Action(type="document_search", parameters={"query": ""})
        observation = Observation(
            action_id="test-id",
            result="",
            success=False,
            error="参数错误：query不能为空"
        )
        
        analysis = engine._analyze_failure(action, observation)
        
        assert analysis.failure_reason == "参数错误"
        assert "重新生成正确的参数" in analysis.suggested_fix
        assert analysis.can_recover is True

    def test_analyze_failure_tool_not_available(self):
        """测试分析工具不可用类型的失败"""
        engine = ReActEngine()
        action = Action(type="document_search", parameters={"query": "test"})
        observation = Observation(
            action_id="test-id",
            result="",
            success=False,
            error="RAG manager is not initialized"
        )
        
        analysis = engine._analyze_failure(action, observation)
        
        assert analysis.failure_reason == "工具不可用"
        assert "备用工具" in analysis.suggested_fix
        assert analysis.can_recover is True

    def test_analyze_failure_connection_error(self):
        """测试分析连接失败类型的失败"""
        engine = ReActEngine()
        action = Action(type="tool_executor", tool_id="test-tool", parameters={})
        observation = Observation(
            action_id="test-id",
            result="",
            success=False,
            error="连接失败：无法连接到服务器"
        )
        
        analysis = engine._analyze_failure(action, observation)
        
        assert analysis.failure_reason == "连接失败"
        assert analysis.can_recover is True

    def test_analyze_failure_permission_error(self):
        """测试分析权限不足类型的失败（不可恢复）"""
        engine = ReActEngine()
        action = Action(type="tool_executor", tool_id="test-tool", parameters={})
        observation = Observation(
            action_id="test-id",
            result="",
            success=False,
            error="权限不足：没有执行此操作的权限"
        )
        
        analysis = engine._analyze_failure(action, observation)
        
        assert analysis.failure_reason == "权限不足"
        assert analysis.can_recover is False

    def test_analyze_failure_timeout(self):
        """测试分析超时类型的失败"""
        engine = ReActEngine()
        action = Action(type="document_search", parameters={"query": "test"})
        observation = Observation(
            action_id="test-id",
            result="",
            success=False,
            error="操作超时：请求超时"
        )
        
        analysis = engine._analyze_failure(action, observation)
        
        assert analysis.failure_reason == "操作超时"
        assert analysis.can_recover is True

    def test_analyze_failure_resource_not_found(self):
        """测试分析资源不存在类型的失败"""
        engine = ReActEngine()
        action = Action(type="tool_executor", tool_id="test-tool", parameters={"file_path": "/nonexistent"})
        observation = Observation(
            action_id="test-id",
            result="",
            success=False,
            error="资源不存在：文件 /nonexistent 不存在"
        )
        
        analysis = engine._analyze_failure(action, observation)
        
        assert analysis.failure_reason == "资源不存在"
        assert analysis.can_recover is True

    def test_reflect_and_recover_with_backup_tool(self):
        """测试使用备用工具恢复"""
        engine = ReActEngine()
        action = Action(type="document_search", parameters={"query": "test"})
        observation = Observation(
            action_id="test-id",
            result="",
            success=False,
            error="RAG manager is not initialized"
        )
        state = ReActState(user_id="test-user", user_query="test query")
        
        fixed_action = engine._reflect_and_recover(action, observation, state)
        
        assert fixed_action is not None
        assert fixed_action.type == "memory_search"  # 使用备用工具
        assert fixed_action.parameters == {"query": "test"}
        assert state.recovery_attempts == 1

    def test_reflect_and_recover_max_attempts_reached(self):
        """测试达到最大恢复尝试次数后不再恢复"""
        engine = ReActEngine()
        action = Action(type="document_search", parameters={"query": "test"})
        observation = Observation(
            action_id="test-id",
            result="",
            success=False,
            error="工具不可用"
        )
        state = ReActState(user_id="test-user", user_query="test query")
        state.recovery_attempts = 2  # 已达到最大次数
        
        fixed_action = engine._reflect_and_recover(action, observation, state)
        
        assert fixed_action is None

    def test_reflect_and_recover_cannot_recover(self):
        """测试不可恢复的错误不尝试恢复"""
        engine = ReActEngine()
        action = Action(type="tool_executor", tool_id="test-tool", parameters={})
        observation = Observation(
            action_id="test-id",
            result="",
            success=False,
            error="权限不足"
        )
        state = ReActState(user_id="test-user", user_query="test query")
        
        fixed_action = engine._reflect_and_recover(action, observation, state)
        
        assert fixed_action is None
        assert state.recovery_attempts == 0

    def test_generate_fixed_action_switch_backup(self):
        """测试生成修复动作 - 切换备用工具"""
        engine = ReActEngine()
        action = Action(type="document_search", parameters={"query": "test"})
        analysis = RecoveryAnalysis(
            failure_reason="工具不可用",
            suggested_fix="尝试使用备用工具",
            can_recover=True
        )
        state = ReActState(user_id="test-user", user_query="test query")
        
        fixed_action = engine._generate_fixed_action(action, analysis, state)
        
        assert fixed_action is not None
        assert fixed_action.type == "memory_search"

    def test_generate_fixed_action_simplify_parameters(self):
        """测试生成修复动作 - 简化参数"""
        engine = ReActEngine()
        action = Action(type="tool_executor", tool_id="test-tool", parameters={"a": "value", "b": None, "c": ""})
        analysis = RecoveryAnalysis(
            failure_reason="参数错误",
            suggested_fix="简化参数",
            can_recover=True
        )
        state = ReActState(user_id="test-user", user_query="test query")
        
        fixed_action = engine._generate_fixed_action(action, analysis, state)
        
        assert fixed_action is not None
        # 空字符串参数会被保留，只有 None 会被移除
        assert "a" in fixed_action.parameters
        assert "b" not in fixed_action.parameters

    def test_regenerate_parameters_success(self):
        """测试重新生成参数成功"""
        # 使用 MagicMock 创建引擎
        engine = ReActEngine()
        # 替换 llm 为 mock
        mock_llm = MagicMock()
        mock_response = Mock()
        mock_response.content = '{"query": "正确的查询参数"}'
        mock_llm.invoke.return_value = mock_response
        engine.llm = mock_llm
        
        action = Action(type="document_search", parameters={"query": ""})
        state = ReActState(user_id="test-user", user_query="查找文档")
        
        fixed_action = engine._regenerate_parameters(action, state)
        
        assert fixed_action is not None
        assert fixed_action.type == "document_search"
        assert fixed_action.parameters == {"query": "正确的查询参数"}

    def test_regenerate_parameters_failure(self):
        """测试重新生成参数失败"""
        # 使用 MagicMock 创建引擎
        engine = ReActEngine()
        # 替换 llm 为 mock
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("LLM error")
        engine.llm = mock_llm
        
        action = Action(type="document_search", parameters={"query": ""})
        state = ReActState(user_id="test-user", user_query="查找文档")
        
        fixed_action = engine._regenerate_parameters(action, state)
        
        assert fixed_action is None

    def test_backup_tools_mapping(self):
        """测试备用工具映射配置"""
        engine = ReActEngine()
        
        assert "document_search" in engine.backup_tools
        assert "memory_search" in engine.backup_tools["document_search"]
        assert "memory_search" in engine.backup_tools
        assert "document_search" in engine.backup_tools["memory_search"]
        assert engine.backup_tools["tool_executor"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
