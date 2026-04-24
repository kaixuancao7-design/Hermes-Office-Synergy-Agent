from typing import Dict, Any, Optional, List
from src.types import Message, Session, Intent
from src.engine.intent_recognition import intent_recognizer
from src.engine.task_planner import task_planner
from src.engine.learning_cycle import learning_cycle
from src.engine.react_engine import react_engine
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger
from src.plugins import get_memory_store, get_skill_manager, get_model_router

logger = get_logger("gateway")


class MessageRouter:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Session]] = {}  # user_id -> group_id -> Session
        self.use_react_mode = True  # 启用 ReAct 模式
    
    def route(self, message: Message) -> str:
        user_id = message.user_id
        
        # 从metadata获取分组信息
        metadata = message.metadata or {}
        group_id = metadata.get("group_id", "default")
        group_name = metadata.get("group_name", "默认会话")
        tags = metadata.get("tags", [])
        
        # 初始化用户会话字典
        if user_id not in self.sessions:
            self.sessions[user_id] = {}
        
        # 创建或获取会话
        if group_id not in self.sessions[user_id]:
            self.sessions[user_id][group_id] = Session(
                id=generate_id(),
                user_id=user_id,
                group_id=group_id,
                group_name=group_name,
                context=[],
                created_at=get_timestamp(),
                last_active_at=get_timestamp(),
                tags=tags
            )
        
        session = self.sessions[user_id][group_id]
        session.context.append(message)
        session.last_active_at = get_timestamp()
        session.group_name = group_name  # 更新分组名称
        
        db.save_message(message)
        
        # 使用插件系统的记忆存储
        memory_store = get_memory_store()
        if memory_store:
            from src.types import MemoryEntry
            memory_entry = MemoryEntry(
                id=generate_id(),
                user_id=user_id,
                type="short",
                content=message.content,
                timestamp=message.timestamp,
                tags=["short_term", "message", group_id],
                group_id=group_id,
                group_name=group_name
            )
            memory_store.add_memory(user_id, memory_entry)
        
        if self._is_group_message(message):
            if not self._is_mentioned(message):
                return ""
        
        # 检查是否是文件上传
        metadata = message.metadata or {}
        is_file_upload = metadata.get("file_key") is not None or metadata.get("file_name") is not None
        
        # 如果是文件上传，强制使用文档分析意图
        if is_file_upload:
            logger.info("检测到文件上传，强制使用文档分析意图")
            intent = Intent(
                type="document_analysis",
                confidence=0.95,
                entities={"file_name": metadata.get("file_name", "")}
            )
        else:
            intent = intent_recognizer.recognize(message.content)
            logger.info(f"Recognized intent: {intent.type} (confidence: {intent.confidence})")
        
        # 判断是否使用 ReAct 模式
        if self.use_react_mode and self._should_use_react(intent):
            logger.info(f"Using ReAct mode for intent: {intent.type}")
            response = self._handle_with_react(user_id, message.content, message.metadata)
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
        
        # 使用插件系统的记忆存储
        memory_store = get_memory_store()
        if memory_store:
            from src.types import MemoryEntry
            memory_entry = MemoryEntry(
                id=generate_id(),
                user_id=user_id,
                type="short",
                content=response_message.content,
                timestamp=response_message.timestamp,
                tags=["short_term", "response", group_id],
                group_id=group_id,
                group_name=group_name
            )
            memory_store.add_memory(user_id, memory_entry)
        
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
        # 检查用户是否提到"文件"
        mentions_file = any(keyword in context.lower() for keyword in ["文件", "这个文件", "文档"])
        
        if mentions_file:
            # 用户提到文件，优先查找最近上传的文件内容
            file_content = self._get_recent_file_content(user_id)
            if file_content:
                logger.info("总结最近上传的文件内容")
                text_to_summarize = file_content
            else:
                # 没有找到最近的文件内容，回退到历史消息总结
                recent_messages = db.get_recent_messages(user_id, 20)
                text_to_summarize = self._extract_valid_text(recent_messages)
        else:
            # 用户没有提到文件，直接总结历史消息
            recent_messages = db.get_recent_messages(user_id, 20)
            text_to_summarize = self._extract_valid_text(recent_messages)
        
        # 如果没有可总结的内容，返回友好提示
        if not text_to_summarize.strip():
            logger.info("没有可总结的文本内容")
            return "当前没有可总结的文本内容。您可以上传文件或发送文本消息，我会帮您总结。"
        
        logger.info(f"总结内容长度: {len(text_to_summarize)} 字符")
        
        # 使用插件系统的模型路由
        model_router = get_model_router()
        if model_router:
            model = model_router.select_model("summarization", "simple")
            if model:
                prompt = f"总结以下内容：\n{text_to_summarize}"
                response = model_router.call_model(model, [{"role": "user", "content": prompt}])
                if response and response.strip():
                    return response
                else:
                    logger.warning("模型返回空响应，降级到ReAct模式")
        
        # 如果插件不可用或返回空，尝试使用 ReAct 模式
        logger.info("总结功能降级到 ReAct 模式")
        response = react_engine.run(user_id, f"总结以下内容：\n{text_to_summarize}")
        
        # 如果仍然为空，返回默认提示
        if not response or not response.strip():
            return "抱歉，暂时无法生成总结。请稍后重试或提供更多内容。"
        
        return response
    
    def _get_recent_file_content(self, user_id: str) -> str:
        """获取最近上传的文件内容"""
        from src.data.vector_store import rag_manager
        
        try:
            # 搜索最近添加的文档（基于时间戳或元数据）
            # 使用特殊查询词搜索最近上传的文件
            results = rag_manager.query("__recent_upload__", k=3)
            
            if results:
                # 按时间排序，获取最新的
                sorted_results = sorted(results, 
                                      key=lambda x: x.get("metadata", {}).get("timestamp", 0),
                                      reverse=True)
                # 合并内容
                contents = []
                for result in sorted_results[:2]:  # 最多取2个最近的文件
                    content = result.get("content", "")
                    if content and len(content) > 50:  # 确保是有效内容
                        contents.append(content)
                
                if contents:
                    return "\n\n---\n\n".join(contents)
        
        except Exception as e:
            logger.error(f"获取最近文件内容失败: {str(e)}")
        
        # 如果向量库中没有找到，尝试从最近消息中提取文件内容
        return self._extract_file_content_from_messages(user_id)
    
    def _extract_file_content_from_messages(self, user_id: str) -> str:
        """从最近消息中提取文件内容"""
        recent_messages = db.get_recent_messages(user_id, 10)
        
        # 查找助手回复中包含文件内容的消息（通常文件上传后助手会回复文件内容）
        file_contents = []
        for msg in recent_messages:
            if msg.role == "assistant" and msg.content:
                content = msg.content.strip()
                # 检查是否是文件内容（不是简单的"收到文件"回复）
                if len(content) > 100 and not content.startswith("{"):
                    file_contents.append(content)
        
        if file_contents:
            return "\n\n---\n\n".join(file_contents[:2])
        
        return ""
    
    def _extract_valid_text(self, messages) -> str:
        """从消息列表中提取有效文本内容"""
        def is_valid_text(content):
            if not content or not content.strip():
                return False
            # 检查是否是文件上传的JSON格式
            content = content.strip()
            if content.startswith('{') and content.endswith('}'):
                # 可能是文件上传消息，检查是否包含file_key
                try:
                    import json
                    data = json.loads(content)
                    if 'file_key' in data or 'file_name' in data:
                        return False
                except:
                    pass
            return True
        
        valid_messages = [m for m in messages if is_valid_text(m.content)]
        return "\n".join(m.content for m in valid_messages)
    
    def _handle_question_answering(self, user_id: str, intent: Intent, context: str) -> str:
        # 使用插件系统的记忆存储进行检索
        memory_store = get_memory_store()
        context_text = ""
        
        if memory_store:
            results = memory_store.search_memory(user_id, context, limit=3)
            context_text = "\n".join(r.content for r in results)
        
        # 使用插件系统的模型路由
        model_router = get_model_router()
        if model_router:
            model = model_router.select_model("question_answering", "medium")
            if model:
                prompt = f"基于以下上下文回答问题：\n\n上下文：{context_text}\n\n问题：{context}"
                return model_router.call_model(model, [{"role": "user", "content": prompt}])
        
        return "问答功能暂时不可用"
    
    def _handle_task_execution(self, user_id: str, intent: Intent, context: str) -> str:
        task = task_planner.plan(user_id, intent, context)
        
        for i, step in enumerate(task.steps):
            task = task_planner.execute_step(task, i)
            if step.status == "failed":
                return f"任务执行失败：{step.error}"
        
        return f"任务完成！\n步骤：\n{chr(10).join(f'{i+1}. {s.description}: {s.result}' for i, s in enumerate(task.steps))}"
    
    def _handle_skill_request(self, user_id: str, intent: Intent, context: str) -> str:
        # 使用插件系统的技能管理器
        skill_manager = get_skill_manager()
        
        if skill_manager:
            skill = skill_manager.find_relevant_skill(context)
            if skill:
                return f"已找到相关技能：{skill.name}\n描述：{skill.description}"
        
        return "未找到相关技能，是否需要创建新技能？"
    
    def _handle_memory_query(self, user_id: str, intent: Intent, context: str) -> str:
        # 使用插件系统的记忆存储
        memory_store = get_memory_store()
        
        if memory_store:
            results = memory_store.search_memory(user_id, context, limit=5)
            if results:
                return "\n\n".join(f"[{r.timestamp}] {r.content[:100]}..." for r in results)
        
        return "未找到相关记忆"
    
    def _handle_document_analysis(self, user_id: str, intent: Intent, context: str) -> str:
        # 从数据库获取最近的文件内容进行总结
        from src.data.database import db
        
        # 获取用户最近的消息
        recent_messages = db.get_recent_messages(user_id, 20)
        
        # 过滤出文件上传后的助手回复（包含文件内容）
        def has_content(content):
            if not content or not content.strip():
                return False
            # 检查是否包含有效内容（不是纯JSON文件上传消息）
            content = content.strip()
            if content.startswith('{') and content.endswith('}'):
                try:
                    import json
                    data = json.loads(content)
                    # 如果只是文件上传的JSON，跳过
                    if 'file_key' in data and 'file_name' in data and len(data) <= 3:
                        return False
                except:
                    pass
            return True
        
        valid_messages = [m for m in recent_messages if has_content(m.content)]
        
        # 优先获取助手回复（包含文件内容）
        file_contents = [m.content for m in valid_messages if m.role == "assistant"]
        
        # 如果没有助手回复，使用所有有效消息
        if not file_contents:
            file_contents = [m.content for m in valid_messages]
        
        text_to_summarize = "\n".join(file_contents)
        
        # 如果没有可总结的内容
        if not text_to_summarize.strip():
            logger.info("文档分析：没有可总结的内容")
            return "已收到您上传的文件，但暂时没有可分析的内容。您可以提出具体问题，我来帮您分析。"
        
        logger.info(f"文档分析：总结内容长度: {len(text_to_summarize)} 字符")
        
        # 使用插件系统的模型路由进行总结分析
        model_router = get_model_router()
        if model_router:
            model = model_router.select_model("document_analysis", "complex")
            if model:
                prompt = f"""请分析并总结以下文档内容：

{text_to_summarize}

请提供：
1. 核心内容总结
2. 关键要点
3. 主要结论或建议
"""
                response = model_router.call_model(model, [{"role": "user", "content": prompt}])
                if response and response.strip():
                    return response
                else:
                    logger.warning("模型返回空响应，降级到总结模式")
        
        # 降级到简单总结
        logger.info("文档分析降级到简单总结模式")
        return self._handle_summarization(user_id, intent, text_to_summarize)
    
    def _handle_code_generation(self, user_id: str, intent: Intent, context: str) -> str:
        # 使用插件系统的模型路由
        model_router = get_model_router()
        if model_router:
            model = model_router.select_model("coding", "complex")
            if model:
                prompt = f"生成代码：\n{context}"
                return model_router.call_model(model, [{"role": "user", "content": prompt}])
        
        return "代码生成功能暂时不可用"
    
    def _handle_creative_writing(self, user_id: str, intent: Intent, context: str) -> str:
        # 使用插件系统的模型路由
        model_router = get_model_router()
        if model_router:
            model = model_router.select_model("creative_writing", "medium")
            if model:
                prompt = f"创作内容：\n{context}"
                return model_router.call_model(model, [{"role": "user", "content": prompt}])
            else:
                logger.warning("无法选择创作模型")
        else:
            logger.warning("模型路由不可用")
        
        # 如果插件不可用，尝试使用 ReAct 模式
        logger.info("创作功能降级到 ReAct 模式")
        return react_engine.run(user_id, f"根据以下内容创作或生成PPT：\n{context}")
    
    def _handle_unknown(self, user_id: str, context: str) -> str:
        try:
            # 使用插件系统的模型路由
            model_router = get_model_router()
            if model_router:
                model = model_router.select_model("general", "simple")
                if model:
                    return model_router.call_model(model, [{"role": "user", "content": context}])
            
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
        # document_analysis 总是使用 ReAct（需要调用工具读取文件），其他意图需要置信度低于0.8
        if intent.type == "document_analysis":
            return True
        return intent.type in react_intents and intent.confidence < 0.8
    
    def _handle_with_react(self, user_id: str, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """使用 ReAct 引擎处理消息"""
        try:
            # 调试日志：检查元数据内容
            logger.debug(f"_handle_with_react - user_id={user_id}, query={query[:100]}..., metadata={metadata}")
            if metadata and "message_id" not in metadata:
                logger.warning(f"元数据中缺少 message_id: {metadata}")
            return react_engine.run(user_id, query, metadata=metadata)
        except Exception as e:
            logger.error(f"ReAct engine failed: {str(e)}")
            # 降级到普通处理
            return self._handle_unknown(user_id, query)


message_router = MessageRouter()
