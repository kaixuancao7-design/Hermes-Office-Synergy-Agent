from typing import Dict, Any, Optional, List
from src.types import Message, Session, Intent
from src.engine.intent_recognition import intent_recognizer
from src.engine.task_planner import task_planner
from src.engine.memory_manager import memory_manager
from src.engine.learning_cycle import learning_cycle
from src.engine.react_engine import react_engine
from src.data.database import db
from src.utils import generate_id, get_timestamp, setup_logging
from src.config import settings

logger = setup_logging(settings.LOG_LEVEL)


class MessageRouter:
    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.use_react_mode = True  # 启用 ReAct 模式
    
    def route(self, message: Message) -> str:
        user_id = message.user_id
        
        if user_id not in self.sessions:
            self.sessions[user_id] = Session(
                id=generate_id(),
                user_id=user_id,
                context=[],
                created_at=get_timestamp(),
                last_active_at=get_timestamp()
            )
        
        session = self.sessions[user_id]
        session.context.append(message)
        session.last_active_at = get_timestamp()
        
        db.save_message(message)
        
        memory_manager.add_short_term_memory(user_id, message)
        memory_manager.extract_user_preferences(user_id, message.content)
        
        if self._is_group_message(message):
            if not self._is_mentioned(message):
                return ""
        
        intent = intent_recognizer.recognize(message.content)
        logger.info(f"Recognized intent: {intent.type} (confidence: {intent.confidence})")
        
        # 判断是否使用 ReAct 模式
        if self.use_react_mode and self._should_use_react(intent):
            logger.info(f"Using ReAct mode for intent: {intent.type}")
            response = self._handle_with_react(user_id, message.content)
        else:
            response = self._handle_intent(user_id, intent, message.content)
        
        response_message = Message(
            id=generate_id(),
            user_id=user_id,
            content=response,
            role="assistant",
            timestamp=get_timestamp(),
            metadata={"intent": intent.type}
        )
        
        db.save_message(response_message)
        memory_manager.add_short_term_memory(user_id, response_message)
        
        return response
    
    def _is_group_message(self, message: Message) -> bool:
        metadata = message.metadata or {}
        return metadata.get("group", False)
    
    def _is_mentioned(self, message: Message) -> bool:
        content = message.content.lower()
        mentions = ["@hermes-office-synergy-agent"]
        return any(mention in content for mention in mentions)
    
    def _handle_intent(self, user_id: str, intent: Intent, context: str) -> str:
        handlers = {
            "summarization": self._handle_summarization,
            "question_answering": self._handle_question_answering,
            "task_execution": self._handle_task_execution,
            "skill_request": self._handle_skill_request,
            "memory_query": self._handle_memory_query,
            "document_analysis": self._handle_document_analysis,
            "code_generation": self._handle_code_generation,
            "creative_writing": self._handle_creative_writing
        }
        
        handler = handlers.get(intent.type)
        if handler:
            return handler(user_id, intent, context)
        
        return self._handle_unknown(user_id, context)
    
    def _handle_summarization(self, user_id: str, intent: Intent, context: str) -> str:
        recent_messages = db.get_recent_messages(user_id, 20)
        text_to_summarize = "\n".join(m.content for m in recent_messages)
        
        from src.infrastructure.model_router import select_model, call_model
        model = select_model("summarization", "simple")
        
        if model:
            prompt = f"总结以下内容：\n{text_to_summarize}"
            return call_model(model, [{"role": "user", "content": prompt}])
        
        return "总结功能暂时不可用"
    
    def _handle_question_answering(self, user_id: str, intent: Intent, context: str) -> str:
        from src.data.vector_store import rag_manager
        results = rag_manager.query(context, k=3)
        
        context_text = "\n".join(r.get("content", "") for r in results)
        
        from src.infrastructure.model_router import select_model, call_model
        model = select_model("question_answering", "medium")
        
        if model:
            prompt = f"基于以下上下文回答问题：\n\n上下文：{context_text}\n\n问题：{context}"
            return call_model(model, [{"role": "user", "content": prompt}])
        
        return "问答功能暂时不可用"
    
    def _handle_task_execution(self, user_id: str, intent: Intent, context: str) -> str:
        task = task_planner.plan(user_id, intent, context)
        
        for i, step in enumerate(task.steps):
            task = task_planner.execute_step(task, i)
            if step.status == "failed":
                return f"任务执行失败：{step.error}"
        
        return f"任务完成！\n步骤：\n{chr(10).join(f'{i+1}. {s.description}: {s.result}' for i, s in enumerate(task.steps))}"
    
    def _handle_skill_request(self, user_id: str, intent: Intent, context: str) -> str:
        from src.skills.skill_manager import skill_manager
        
        skill = skill_manager.find_relevant_skill(context)
        if skill:
            return f"已找到相关技能：{skill.name}\n描述：{skill.description}"
        
        return "未找到相关技能，是否需要创建新技能？"
    
    def _handle_memory_query(self, user_id: str, intent: Intent, context: str) -> str:
        results = memory_manager.search_long_term_memory(user_id, context)
        
        if results:
            return "\n\n".join(f"[{r.timestamp}] {r.content[:100]}..." for r in results[:5])
        
        return "未找到相关记忆"
    
    def _handle_document_analysis(self, user_id: str, intent: Intent, context: str) -> str:
        from src.infrastructure.model_router import select_model, call_model
        model = select_model("document_analysis", "complex")
        
        if model:
            prompt = f"分析以下内容：\n{context}"
            return call_model(model, [{"role": "user", "content": prompt}])
        
        return "文档分析功能暂时不可用"
    
    def _handle_code_generation(self, user_id: str, intent: Intent, context: str) -> str:
        from src.infrastructure.model_router import select_model, call_model
        model = select_model("coding", "complex")
        
        if model:
            prompt = f"生成代码：\n{context}"
            return call_model(model, [{"role": "user", "content": prompt}])
        
        return "代码生成功能暂时不可用"
    
    def _handle_creative_writing(self, user_id: str, intent: Intent, context: str) -> str:
        from src.infrastructure.model_router import select_model, call_model
        model = select_model("creative_writing", "medium")
        
        if model:
            prompt = f"创作内容：\n{context}"
            return call_model(model, [{"role": "user", "content": prompt}])
        
        return "创作功能暂时不可用"
    
    def _handle_unknown(self, user_id: str, context: str) -> str:
        try:
            from src.infrastructure.model_router import select_model, call_model
            model = select_model("general", "simple")
            
            if model:
                return call_model(model, [{"role": "user", "content": context}])
            
            return "抱歉，我无法理解您的请求"
        except Exception as e:
            logger.error(f"Model call failed: {str(e)}")
            return f"您好！我已收到您的消息：\"{context}\"\n\n由于语言模型服务暂不可用，我无法为您生成智能回复。请检查 Ollama 服务是否运行，或配置其他模型 API 密钥。"
    
    def capture_correction(self, user_id: str, original: str, corrected: str, context: str) -> None:
        learning_cycle.capture_correction(user_id, original, corrected, context)
    
    def _should_use_react(self, intent: Intent) -> bool:
        """判断是否应该使用 ReAct 模式"""
        # 需要复杂推理的意图类型使用 ReAct
        react_intents = [
            "question_answering",
            "task_execution",
            "document_analysis",
            "code_generation",
            "unknown"  # 未知意图使用 ReAct 进行探索
        ]
        return intent.type in react_intents and intent.confidence < 0.8
    
    def _handle_with_react(self, user_id: str, query: str) -> str:
        """使用 ReAct 引擎处理消息"""
        try:
            return react_engine.run(user_id, query)
        except Exception as e:
            logger.error(f"ReAct engine failed: {str(e)}")
            # 降级到普通处理
            return self._handle_unknown(user_id, query)


message_router = MessageRouter()
