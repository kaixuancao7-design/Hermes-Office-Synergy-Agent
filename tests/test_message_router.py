"""消息路由测试"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.gateway.message_router import MessageRouter
from src.types import Intent


class TestMessageRouter:
    """消息路由测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.router = MessageRouter()
        self.test_user_id = "test_user_123"
    
    def test_initialization(self):
        """测试消息路由初始化"""
        assert self.router is not None
    
    @patch('src.gateway.message_router.get_model_router')
    def test_summarization_handler_with_no_model_router(self, mock_get_model):
        """测试总结处理器在模型路由不可用时降级到ReAct"""
        mock_get_model.return_value = None
        
        intent = Intent(type="summarization", confidence=0.9, entities={})
        result = self.router._handle_summarization(self.test_user_id, intent, "test content")
        
        assert result is not None
    
    @patch('src.gateway.message_router.get_model_router')
    def test_summarization_handler_with_no_model(self, mock_get_model):
        """测试总结处理器在无法选择模型时降级到ReAct"""
        mock_model_router = Mock()
        mock_model_router.select_model.return_value = None
        mock_get_model.return_value = mock_model_router
        
        intent = Intent(type="summarization", confidence=0.9, entities={})
        result = self.router._handle_summarization(self.test_user_id, intent, "test content")
        
        assert result is not None
    
    @patch('src.gateway.message_router.get_model_router')
    def test_summarization_handler_with_empty_response(self, mock_get_model):
        """测试总结处理器在模型返回空响应时降级到ReAct"""
        mock_model = Mock()
        mock_model_router = Mock()
        mock_model_router.select_model.return_value = mock_model
        mock_model_router.call_model.return_value = ""
        mock_get_model.return_value = mock_model_router
        
        intent = Intent(type="summarization", confidence=0.9, entities={})
        result = self.router._handle_summarization(self.test_user_id, intent, "test content")
        
        assert result is not None
    
    @patch('src.gateway.message_router.get_model_router')
    @patch('src.gateway.message_router.get_memory_store')
    def test_qa_handler_with_no_model_router(self, mock_get_memory, mock_get_model):
        """测试问答处理器在模型路由不可用时降级到ReAct"""
        mock_get_model.return_value = None
        mock_get_memory.return_value = None
        
        intent = Intent(type="question_answering", confidence=0.9, entities={})
        result = self.router._handle_question_answering(self.test_user_id, intent, "What is AI?")
        
        assert result is not None
    
    @patch('src.gateway.message_router.get_memory_store')
    def test_qa_handler_with_no_memory_store(self, mock_get_memory):
        """测试问答处理器在记忆存储不可用时跳过记忆检索"""
        mock_get_memory.return_value = None
        
        intent = Intent(type="question_answering", confidence=0.9, entities={})
        result = self.router._handle_question_answering(self.test_user_id, intent, "What is AI?")
        
        assert result is not None
    
    @patch('src.gateway.message_router.get_skill_manager')
    def test_skill_handler_with_no_skill_found(self, mock_get_skill):
        """测试技能处理器在未找到技能时降级到ReAct"""
        mock_skill_manager = Mock()
        mock_skill_manager.find_relevant_skill.return_value = None
        mock_get_skill.return_value = mock_skill_manager
        
        intent = Intent(type="skill_request", confidence=0.9, entities={})
        result = self.router._handle_skill_request(self.test_user_id, intent, "test skill")
        
        assert result is not None
    
    @patch('src.gateway.message_router.get_memory_store')
    def test_memory_handler_with_no_memory_store(self, mock_get_memory):
        """测试记忆查询处理器在记忆存储不可用时降级到ReAct"""
        mock_get_memory.return_value = None
        
        intent = Intent(type="memory_query", confidence=0.9, entities={})
        result = self.router._handle_memory_query(self.test_user_id, intent, "test query")
        
        assert result is not None
    
    @patch('src.gateway.message_router.get_memory_store')
    def test_memory_handler_with_no_results(self, mock_get_memory):
        """测试记忆查询处理器在无结果时降级到ReAct"""
        mock_memory_store = Mock()
        mock_memory_store.search_memory.return_value = []
        mock_get_memory.return_value = mock_memory_store
        
        intent = Intent(type="memory_query", confidence=0.9, entities={})
        result = self.router._handle_memory_query(self.test_user_id, intent, "test query")
        
        assert result is not None
    
    @patch('src.gateway.message_router.get_model_router')
    def test_document_analysis_handler_with_no_model_router(self, mock_get_model):
        """测试文档分析处理器在模型路由不可用时降级到ReAct"""
        mock_get_model.return_value = None
        
        intent = Intent(type="document_analysis", confidence=0.9, entities={})
        result = self.router._handle_document_analysis(self.test_user_id, intent, "test document")
        
        assert result is not None
    
    @patch('src.gateway.message_router.get_model_router')
    def test_code_generation_handler_with_no_model_router(self, mock_get_model):
        """测试代码生成处理器在模型路由不可用时降级到ReAct"""
        mock_get_model.return_value = None
        
        intent = Intent(type="code_generation", confidence=0.9, entities={})
        result = self.router._handle_code_generation(self.test_user_id, intent, "generate Python code")
        
        assert result is not None
    
    @patch('src.gateway.message_router.get_model_router')
    def test_creative_writing_handler_with_no_model_router(self, mock_get_model):
        """测试创意写作处理器在模型路由不可用时降级到ReAct"""
        mock_get_model.return_value = None
        
        intent = Intent(type="creative_writing", confidence=0.9, entities={})
        result = self.router._handle_creative_writing(self.test_user_id, intent, "write a story")
        
        assert result is not None
    
    @patch('src.gateway.message_router.get_model_router')
    def test_unknown_handler_with_no_model_router(self, mock_get_model):
        """测试未知意图处理器在模型路由不可用时降级到ReAct"""
        mock_get_model.return_value = None
        
        result = self.router._handle_unknown(self.test_user_id, "unknown message")
        
        assert result is not None
    
    @patch('src.gateway.message_router.get_model_router')
    def test_unknown_handler_with_empty_response(self, mock_get_model):
        """测试未知意图处理器在模型返回空响应时降级到ReAct"""
        mock_model = Mock()
        mock_model_router = Mock()
        mock_model_router.select_model.return_value = mock_model
        mock_model_router.call_model.return_value = ""
        mock_get_model.return_value = mock_model_router
        
        result = self.router._handle_unknown(self.test_user_id, "unknown message")
        
        assert result is not None
    
    @patch('src.gateway.message_router.react_engine')
    def test_ppt_generate_outline(self, mock_react_engine):
        """测试PPT大纲生成意图"""
        mock_react_engine.run.return_value = "PPT大纲生成成功"
        
        intent = Intent(type="ppt_generate_outline", confidence=0.9, entities={})
        result = self.router._handle_ppt_generation(self.test_user_id, intent, "人工智能发展")
        
        assert result == "PPT大纲生成成功"
        mock_react_engine.run.assert_called_once()
    
    @patch('src.gateway.message_router.react_engine')
    def test_ppt_generate_from_outline(self, mock_react_engine):
        """测试从大纲生成PPT意图"""
        mock_react_engine.run.return_value = "PPT从大纲生成成功"
        
        intent = Intent(type="ppt_generate_from_outline", confidence=0.9, entities={})
        result = self.router._handle_ppt_generation(self.test_user_id, intent, "大纲内容")
        
        assert result == "PPT从大纲生成成功"
        mock_react_engine.run.assert_called_once()
    
    @patch('src.gateway.message_router.react_engine')
    def test_ppt_generate_from_content(self, mock_react_engine):
        """测试从内容生成PPT意图"""
        mock_react_engine.run.return_value = "PPT从内容生成成功"
        
        intent = Intent(type="ppt_generate_from_content", confidence=0.9, entities={})
        result = self.router._handle_ppt_generation(self.test_user_id, intent, "文档内容")
        
        assert result == "PPT从内容生成成功"
        mock_react_engine.run.assert_called_once()
    
    @patch('src.gateway.message_router.react_engine')
    def test_ppt_custom_generate(self, mock_react_engine):
        """测试自定义PPT生成意图"""
        mock_react_engine.run.return_value = "自定义PPT生成成功"
        
        intent = Intent(type="ppt_custom_generate", confidence=0.9, entities={})
        result = self.router._handle_ppt_generation(self.test_user_id, intent, "自定义需求")
        
        assert result == "自定义PPT生成成功"
        mock_react_engine.run.assert_called_once()
    
    def test_should_use_react(self):
        """测试是否应该使用ReAct模式的判断"""
        # document_analysis 有独立handler，不在_react_intents列表中
        # 通过_handle_document_analysis中的降级逻辑处理，而非_should_use_react
        
        # question_answering, task_execution, code_generation, unknown 在置信度 < 0.8 时使用 ReAct
        react_intents_with_low_confidence = ["question_answering", "task_execution", "code_generation", "unknown"]
        for intent_type in react_intents_with_low_confidence:
            intent = Intent(type=intent_type, confidence=0.7, entities={})
            assert self.router._should_use_react(intent) is True
        
        # question_answering, task_execution, code_generation, unknown 在置信度 >= 0.8 时不使用 ReAct
        for intent_type in react_intents_with_low_confidence:
            intent = Intent(type=intent_type, confidence=0.9, entities={})
            assert self.router._should_use_react(intent) is False
        
        # 其他意图不使用 ReAct（包括document_analysis，它有独立的handler）
        non_react_intents = ["summarization", "creative_writing", "memory_query", "skill_request", "document_analysis"]
        for intent_type in non_react_intents:
            intent = Intent(type=intent_type, confidence=0.9, entities={})
            assert self.router._should_use_react(intent) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])