from typing import Dict, Any, Optional, List
from src.types import Message, Session, Intent
from src.engine.intent_recognition import intent_recognizer
from src.engine.task_planner import task_planner
from src.engine.learning_cycle import learning_cycle
from src.engine.react_engine import react_engine
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger
from src.plugins import get_memory_store, get_skill_manager, get_model_router, get_tool_executor

logger = get_logger("gateway")


class MessageRouter:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Session]] = {}  # user_id -> group_id -> Session
        self.use_react_mode = True  # 启用 ReAct 模式
    
    def route(self, message: Message) -> str:
        # 生成请求追踪ID
        trace_id = message.metadata.get("message_id", generate_id()) if message.metadata else generate_id()
        
        logger.info(f"[ROUTER_INPUT] 开始路由消息: trace_id={trace_id}, user_id={message.user_id}, content={message.content[:50] if len(message.content) > 50 else message.content}")
        
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
            logger.debug(f"[PLUGIN_CHECK] 记忆存储插件可用: memory_store={type(memory_store).__name__}")
            try:
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
                logger.debug(f"[MEMORY_STORE] 消息已存储到记忆: user_id={user_id}, message_id={message.id}")
            except Exception as e:
                logger.error(f"[MEMORY_STORE] 记忆存储失败: {str(e)}")
        else:
            logger.warning("[PLUGIN_CHECK] 记忆存储插件不可用，消息仅保存到数据库")
        
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
            logger.info(f"[INTENT_RECOGNIZED] 意图识别完成: intent={intent.type}, confidence={intent.confidence}, mode=ReAct")
            response = self._handle_with_react(user_id, message.content, message.metadata)
        else:
            logger.info(f"[INTENT_RECOGNIZED] 意图识别完成: intent={intent.type}, confidence={intent.confidence}, mode=Direct")
            response = self._handle_intent(user_id, intent, message.content)
        
        logger.info(f"[ROUTER_OUTPUT] 路由响应生成完成: trace_id={trace_id}, response_length={len(response)}")
        
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
        logger.info(f"[HANDLER_DISPATCH] 分发到意图处理器: intent={intent.type}, user_id={user_id}")
        
        handlers = {
            "summarization": self._handle_summarization,
            "question_answering": self._handle_question_answering,
            "task_execution": self._handle_task_execution,
            "skill_request": self._handle_skill_request,
            "memory_query": self._handle_memory_query,
            "document_analysis": self._handle_document_analysis,
            "code_generation": self._handle_code_generation,
            "creative_writing": self._handle_creative_writing,
            # PPT相关意图 - 降级到ReAct模式（工具已注册在tool_executor中）
            "ppt_generate_outline": self._handle_ppt_generation,
            "ppt_generate_from_outline": self._handle_ppt_generation,
            "ppt_generate_from_content": self._handle_ppt_generation,
            "ppt_custom_generate": self._handle_ppt_generation,
        }
        
        handler = handlers.get(intent.type)
        if handler:
            logger.info(f"[HANDLER_START] 执行处理器: {intent.type}")
            result = handler(user_id, intent, context)
            logger.info(f"[HANDLER_END] 处理器执行完成: {intent.type}, result_length={len(result)}")
            return result
        
        logger.warning(f"[HANDLER_NOT_FOUND] 未找到处理器，使用unknown处理器: {intent.type}")
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
        if not model_router:
            logger.warning("[PLUGIN_CHECK] 模型路由插件不可用，降级到ReAct模式")
            return react_engine.run(user_id, f"总结以下内容：\n{text_to_summarize}")
        
        model = model_router.select_model("summarization", "simple")
        if not model:
            logger.warning("[MODEL_ROUTER] 无法为 summarization 任务选择模型，降级到ReAct模式")
            return react_engine.run(user_id, f"总结以下内容：\n{text_to_summarize}")
        
        prompt = f"总结以下内容：\n{text_to_summarize}"
        response = model_router.call_model(model, [{"role": "user", "content": prompt}])
        if response and response.strip():
            return response
        
        # 模型返回空响应，降级到 ReAct 模式
        logger.warning("[MODEL] 模型返回空响应，降级到ReAct模式")
        return react_engine.run(user_id, f"总结以下内容：\n{text_to_summarize}")
    
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
        logger.info(f"[QA_HANDLER] 开始问答处理: user_id={user_id}")
        
        # 使用插件系统的记忆存储进行检索
        memory_store = get_memory_store()
        context_text = ""
        
        if memory_store:
            results = memory_store.search_memory(user_id, context, limit=3)
            context_text = "\n".join(r.content for r in results)
            logger.info(f"[QA_HANDLER] 记忆搜索完成:找到 {len(results)} 条相关记忆")
        else:
            logger.warning("[PLUGIN_CHECK] 记忆存储插件不可用，跳过记忆检索")
        
        # 使用插件系统的模型路由
        model_router = get_model_router()
        if not model_router:
            logger.warning("[PLUGIN_CHECK] 模型路由插件不可用，降级到ReAct模式")
            return react_engine.run(user_id, context)
        
        model = model_router.select_model("question_answering", "medium")
        if not model:
            logger.warning("[MODEL_ROUTER] 无法为 question_answering 任务选择模型，降级到ReAct模式")
            return react_engine.run(user_id, context)
        
        logger.info(f"[QA_HANDLER] 调用问答模型")
        prompt = f"基于以下上下文回答问题：\n\n上下文：{context_text}\n\n问题：{context}"
        response = model_router.call_model(model, [{"role": "user", "content": prompt}])
        
        if response and response.strip():
            logger.info(f"[QA_HANDLER] 问答完成: response_length={len(response)}")
            return response
        
        # 模型返回空响应，降级到 ReAct 模式
        logger.warning("[MODEL] 模型返回空响应，降级到ReAct模式")
        return react_engine.run(user_id, context)
    
    def _handle_task_execution(self, user_id: str, intent: Intent, context: str) -> str:
        logger.info(f"[TASK_HANDLER] 开始任务执行: user_id={user_id}, intent={intent.type}")
        
        task = task_planner.plan(user_id, intent, context)
        logger.info(f"[TASK_HANDLER] 任务规划完成: task_id={task.id}, steps={len(task.steps)}")
        
        for i, step in enumerate(task.steps):
            task = task_planner.execute_step(task, i)
            if step.status == "failed":
                logger.error(f"[TASK_HANDLER] 任务执行失败: step={i}, error={step.error}")
                return f"任务执行失败：{step.error}"
        
        logger.info(f"[TASK_HANDLER] 任务执行完成: task_id={task.id}")
        return f"任务完成！\n步骤：\n{chr(10).join(f'{i+1}. {s.description}: {s.result}' for i, s in enumerate(task.steps))}"
    
    def _handle_skill_request(self, user_id: str, intent: Intent, context: str) -> str:
        logger.info(f"[SKILL_HANDLER] 开始技能请求处理: user_id={user_id}")
        
        # 使用插件系统的技能管理器
        skill_manager = get_skill_manager()
        
        if skill_manager:
            skill = skill_manager.find_relevant_skill(context)
            if skill:
                logger.info(f"[SKILL_HANDLER] 找到相关技能: skill_name={skill.name}")
                return f"已找到相关技能：{skill.name}\n描述：{skill.description}"
        
        logger.warning("[SKILL_HANDLER] 未找到相关技能，降级到ReAct模式")
        return react_engine.run(user_id, f"查找与以下内容相关的技能：{context}")
    
    def _handle_memory_query(self, user_id: str, intent: Intent, context: str) -> str:
        logger.info(f"[MEMORY_HANDLER] 开始记忆查询: user_id={user_id}, query={context[:50]}")
        
        # 使用插件系统的记忆存储
        memory_store = get_memory_store()
        
        if memory_store:
            results = memory_store.search_memory(user_id, context, limit=5)
            if results:
                logger.info(f"[MEMORY_HANDLER] 记忆查询完成: 找到 {len(results)} 条记忆")
                return "\n\n".join(f"[{r.timestamp}] {r.content[:100]}..." for r in results)
        
        logger.warning("[MEMORY_HANDLER] 记忆存储插件不可用或未找到相关记忆，降级到ReAct模式")
        return react_engine.run(user_id, f"搜索与以下内容相关的记忆：{context}")
    
    def _handle_document_analysis(self, user_id: str, intent: Intent, context: str) -> str:
        logger.info(f"[DOC_HANDLER] 开始文档分析: user_id={user_id}")
        
        # 从数据库获取最近的文件内容进行总结
        from src.data.database import db
        
        # 获取用户最近的消息
        recent_messages = db.get_recent_messages(user_id, 20)
        logger.info(f"[DOC_HANDLER] 获取最近消息: {len(recent_messages)} 条")
        
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
        logger.info(f"[DOC_HANDLER] 提取文档内容: length={len(text_to_summarize)}")
        
        # 如果没有可总结的内容
        if not text_to_summarize.strip():
            logger.warning(f"[DOC_HANDLER] 文档内容为空")
            return "已收到您上传的文件，但暂时没有可分析的内容。您可以提出具体问题，我来帮您分析。"
        
        # 使用插件系统的模型路由进行总结分析
        model_router = get_model_router()
        if not model_router:
            logger.warning("[PLUGIN_CHECK] 模型路由插件不可用，降级到ReAct模式")
            return react_engine.run(user_id, f"分析以下文档内容：\n{text_to_summarize}")
        
        model = model_router.select_model("document_analysis", "complex")
        if not model:
            logger.warning("[MODEL_ROUTER] 无法为 document_analysis 任务选择模型，降级到ReAct模式")
            return react_engine.run(user_id, f"分析以下文档内容：\n{text_to_summarize}")
        
        logger.info(f"[DOC_HANDLER] 调用文档分析模型")
        prompt = f"""请分析并总结以下文档内容：

{text_to_summarize}

请提供：
1. 核心内容总结
2. 关键要点
3. 主要结论或建议
"""
        response = model_router.call_model(model, [{"role": "user", "content": prompt}])
        if response and response.strip():
            logger.info(f"[DOC_HANDLER] 文档分析完成: response_length={len(response)}")
            return response
        
        # 模型返回空响应，降级到 ReAct 模式
        logger.warning("[MODEL] 模型返回空响应，降级到ReAct模式")
        return react_engine.run(user_id, f"分析以下文档内容：\n{text_to_summarize}")
    
    def _handle_code_generation(self, user_id: str, intent: Intent, context: str) -> str:
        logger.info(f"[CODE_HANDLER] 开始代码生成: user_id={user_id}")
        
        # 使用插件系统的模型路由
        model_router = get_model_router()
        if not model_router:
            logger.warning("[PLUGIN_CHECK] 模型路由插件不可用，降级到ReAct模式")
            return react_engine.run(user_id, f"生成代码：\n{context}")
        
        model = model_router.select_model("coding", "complex")
        if not model:
            logger.warning("[MODEL_ROUTER] 无法为 coding 任务选择模型，降级到ReAct模式")
            return react_engine.run(user_id, f"生成代码：\n{context}")
        
        logger.info(f"[CODE_HANDLER] 调用代码生成模型")
        prompt = f"生成代码：\n{context}"
        response = model_router.call_model(model, [{"role": "user", "content": prompt}])
        
        if response and response.strip():
            logger.info(f"[CODE_HANDLER] 代码生成完成: response_length={len(response)}")
            return response
        
        # 模型返回空响应，降级到 ReAct 模式
        logger.warning("[MODEL] 模型返回空响应，降级到ReAct模式")
        return react_engine.run(user_id, f"生成代码：\n{context}")

    def _handle_creative_writing(self, user_id: str, intent: Intent, context: str) -> str:
        logger.info(f"[CREATIVE_HANDLER] 开始创意写作: user_id={user_id}")
        
        # 使用插件系统的模型路由
        model_router = get_model_router()
        if not model_router:
            logger.warning("[PLUGIN_CHECK] 模型路由插件不可用，降级到ReAct模式")
            return react_engine.run(user_id, f"根据以下内容创作：\n{context}")
        
        model = model_router.select_model("creative_writing", "medium")
        if not model:
            logger.warning("[MODEL_ROUTER] 无法为 creative_writing 任务选择模型，降级到ReAct模式")
            return react_engine.run(user_id, f"根据以下内容创作：\n{context}")
        
        logger.info(f"[CREATIVE_HANDLER] 调用创意写作模型")
        prompt = f"创作内容：\n{context}"
        response = model_router.call_model(model, [{"role": "user", "content": prompt}])
        
        if response and response.strip():
            logger.info(f"[CREATIVE_HANDLER] 创意写作完成: response_length={len(response)}")
            return response
        
        # 模型返回空响应，降级到 ReAct 模式
        logger.warning("[MODEL] 模型返回空响应，降级到ReAct模式")
        return react_engine.run(user_id, f"根据以下内容创作：\n{context}")
    
    def _handle_ppt_generation(self, user_id: str, intent: Intent, context: str) -> str:
        """处理PPT生成相关意图 - 降级到ReAct模式以使用工具执行器"""
        logger.info(f"[PPT_HANDLER] 开始PPT生成: user_id={user_id}, intent={intent.type}")
        
        # PPT生成功能已迁移到工具执行器，通过ReAct模式调用
        logger.info("[PPT_HANDLER] PPT生成功能已迁移到工具执行器，降级到ReAct模式")
        
        # 根据不同的意图类型构建不同的提示词
        prompt_mapping = {
            "ppt_generate_outline": f"帮我生成一个PPT大纲，主题：{context}",
            "ppt_generate_from_outline": f"根据以下大纲生成PPT：{context}",
            "ppt_generate_from_content": f"根据以下内容生成PPT：{context}",
            "ppt_custom_generate": f"帮我创建一个PPT，需求：{context}"
        }
        
        prompt = prompt_mapping.get(intent.type, f"帮我创建一个PPT，需求：{context}")
        return react_engine.run(user_id, prompt)
    
    def _handle_unknown(self, user_id: str, context: str) -> str:
        logger.info(f"[UNKNOWN_HANDLER] 开始处理未知意图: user_id={user_id}")
        
        # 使用插件系统的模型路由
        model_router = get_model_router()
        if not model_router:
            logger.warning("[PLUGIN_CHECK] 模型路由插件不可用，降级到ReAct模式")
            return react_engine.run(user_id, context)
        
        model = model_router.select_model("general", "simple")
        if not model:
            logger.warning("[MODEL_ROUTER] 无法为 general 任务选择模型，降级到ReAct模式")
            return react_engine.run(user_id, context)
        
        logger.info(f"[UNKNOWN_HANDLER] 调用通用模型")
        response = model_router.call_model(model, [{"role": "user", "content": context}])
        
        if response and response.strip():
            logger.info(f"[UNKNOWN_HANDLER] 通用处理完成: response_length={len(response)}")
            return response
        
        # 模型返回空响应，降级到 ReAct 模式
        logger.warning("[MODEL] 模型返回空响应，降级到ReAct模式")
        return react_engine.run(user_id, context)
    
    def capture_correction(self, user_id: str, original: str, corrected: str, context: str) -> None:
        learning_cycle.capture_correction(user_id, original, corrected, context)
    
    def _should_use_react(self, intent: Intent) -> bool:
        """判断是否应该使用 ReAct 模式"""
        # 需要复杂推理的意图类型使用 ReAct
        # document_analysis 有独立handler，不在此列表中
        react_intents = [
            "question_answering",
            "task_execution",
            "code_generation",
            "unknown"  # 未知意图使用 ReAct 进行探索
        ]
        # 置信度低于0.8时使用ReAct进行深度推理
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
