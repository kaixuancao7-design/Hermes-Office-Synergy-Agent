from typing import Dict, Any, Optional, List
from datetime import datetime
from src.types import Message, Session, Intent
from src.engine.intent_recognition import intent_recognizer
from src.engine.task_planner import task_planner
from src.engine.learning_cycle import learning_cycle
from src.engine.react_engine import react_engine
from src.engine.ppt_workflow import ppt_workflow
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger, set_request_context, clear_request_context, log_event
from src.plugins import get_memory_store, get_skill_manager, get_model_router, get_tool_executor

logger = get_logger("gateway")


class MessageRouter:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Session]] = {}  # user_id -> group_id -> Session
        self.use_react_mode = True  # 启用 ReAct 模式
        self._load_persisted_sessions()
        self._graph = None  # 延迟初始化 LangGraph 消息图
        logger.info("[INIT] MessageRouter 初始化完成")
    
    async def _call_model_with_fallback(
        self, user_id: str, task_type: str, complexity: str,
        primary_prompt: str, fallback_prompt: str = None
    ) -> str:
        """Call model router with three-tier fallback to ReAct engine.

        Args:
            user_id: The user ID for the request
            task_type: Task type for model selection (e.g. 'summarization')
            complexity: Complexity hint for model selection (e.g. 'simple')
            primary_prompt: The prompt to send to the model
            fallback_prompt: Override prompt for ReAct fallback. Defaults to primary_prompt.

        Returns:
            Model response or ReAct engine fallback result
        """
        if fallback_prompt is None:
            fallback_prompt = primary_prompt

        model_router = get_model_router()
        if not model_router:
            logger.warning(f"[PLUGIN_CHECK] Model router unavailable, falling back to ReAct for {task_type}")
            return await react_engine.run(user_id, fallback_prompt)

        model = model_router.select_model(task_type, complexity)
        if not model:
            logger.warning(f"[MODEL_ROUTER] No model for {task_type}/{complexity}, falling back to ReAct")
            return await react_engine.run(user_id, fallback_prompt)

        response = await model_router.call_model(model, [{"role": "user", "content": primary_prompt}])
        if response and response.strip():
            return response

        logger.warning(f"[MODEL] Empty response for {task_type}, falling back to ReAct")
        return await react_engine.run(user_id, fallback_prompt)

    async def route(self, message: Message) -> str:
        """路由消息 — 优先使用 LangGraph 消息图，失败回退到手写管道"""
        # 延迟初始化 LangGraph 消息图
        if self._graph is None:
            try:
                from src.gateway.message_graph import MessageGraph
                self._graph = MessageGraph(self)
                logger.info("[ROUTER] LangGraph消息图已启用")
            except Exception as e:
                logger.warning(f"[ROUTER] LangGraph消息图不可用: {str(e)}，使用手写管道")

        if self._graph is not None:
            try:
                return await self._graph.route(message)
            except Exception as e:
                logger.error(f"[ROUTER] LangGraph消息图异常: {str(e)}，回退到手写管道")

        # 回退：原始手写管道
        return await self._route_manual(message)

    async def _route_manual(self, message: Message) -> str:
        """手写消息路由管道（LangGraph不可用时的回退）"""
        start_time = datetime.now()
        trace_id = message.metadata.get("message_id", generate_id()) if message.metadata else generate_id()
        user_id = message.user_id
        set_request_context(request_id=trace_id, user_id=user_id)

        try:
            content_preview = message.content[:50] if len(message.content) > 50 else message.content
            logger.info(f"[ROUTER_INPUT] 开始路由消息 | trace_id={trace_id} | user_id={user_id} | content={content_preview}")

            metadata = message.metadata or {}
            group_id = metadata.get("group_id", "default")
            group_name = metadata.get("group_name", "默认会话")

            # 会话管理
            session = self._get_or_create_session(user_id, group_id, group_name)
            session.context.append(message)
            session.last_active_at = get_timestamp()
            self._persist_session(session)
            db.save_message(message)

            # 记忆存储
            self._store_message_memory(user_id, message, group_id, group_name)

            # 群消息过滤
            if self._is_group_message(message) and not self._is_mentioned(message):
                logger.debug(f"[GROUP_FILTER] 群消息未提及机器人，忽略 | user_id={user_id}")
                return ""

            # 意图识别
            metadata = message.metadata or {}
            is_file_upload = bool(metadata.get("file_key") or metadata.get("file_name"))
            if is_file_upload:
                intent = Intent(type="document_analysis", confidence=0.95,
                               entities={"file_name": metadata.get("file_name", "")})
            else:
                intent = await intent_recognizer.recognize(message.content)

            logger.info(f"[INTENT_RECOGNIZE] intent={intent.type} | confidence={intent.confidence:.2f}")

            # 路由
            use_react = self.use_react_mode and self._should_use_react(intent)
            mode = "ReAct" if use_react else "Direct"
            logger.info(f"[MODE_SELECT] mode={mode} | intent={intent.type}")

            if use_react:
                response = await self._handle_with_react(user_id, message.content, message.metadata)
            else:
                response = await self._handle_intent(user_id, intent, message.content, message.metadata)

            # 保存响应
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            log_event(logger, "message_processed", trace_id=trace_id, user_id=user_id,
                     intent=intent.type, mode=mode, response_length=len(response), elapsed_ms=elapsed_ms)

            self._save_response_to_db(user_id, response, group_id, group_name, intent.type)
            return response

        except Exception as e:
            logger.error(f"[ROUTER_ERROR] trace_id={trace_id} | error={str(e)}", exc_info=True)
            return "处理请求时出现错误，请稍后重试。"
        finally:
            clear_request_context()
    
    def _get_or_create_session(self, user_id: str, group_id: str, group_name: str) -> Session:
        """获取或创建会话"""
        if user_id not in self.sessions:
            self.sessions[user_id] = {}
        if group_id not in self.sessions[user_id]:
            session = Session(
                id=generate_id(), user_id=user_id, group_id=group_id,
                group_name=group_name, context=[],
                created_at=get_timestamp(), last_active_at=get_timestamp(), tags=[],
            )
            self.sessions[user_id][group_id] = session
            logger.debug(f"[SESSION_CREATE] 创建新分组会话 | group_id={group_id}")
        return self.sessions[user_id][group_id]

    def _store_message_memory(self, user_id: str, message: Message, group_id: str, group_name: str):
        """将消息存入记忆存储"""
        memory_store = get_memory_store()
        if not memory_store:
            return
        try:
            from src.types import MemoryEntry
            entry = MemoryEntry(
                id=generate_id(), user_id=user_id, type="short",
                content=message.content, timestamp=message.timestamp,
                tags=["short_term", "message", group_id],
                group_id=group_id, group_name=group_name,
            )
            memory_store.add_memory(user_id, entry)
        except Exception as e:
            logger.error(f"[MEMORY_STORE] 消息记忆存储失败: {str(e)}")

    def _save_response_to_db(self, user_id: str, response: str, group_id: str, group_name: str, intent_type: str):
        """保存响应到数据库和记忆"""
        response_msg = Message(
            id=generate_id(), user_id=user_id, content=response,
            role="assistant", timestamp=get_timestamp(), metadata={"intent": intent_type},
        )
        db.save_message(response_msg)

        memory_store = get_memory_store()
        if memory_store and response:
            try:
                from src.types import MemoryEntry
                entry = MemoryEntry(
                    id=generate_id(), user_id=user_id, type="short",
                    content=response, timestamp=response_msg.timestamp,
                    tags=["short_term", "response", group_id],
                    group_id=group_id, group_name=group_name,
                )
                memory_store.add_memory(user_id, entry)
            except Exception as e:
                logger.error(f"[MEMORY_STORE] 响应记忆存储失败: {str(e)}")

    def _is_group_message(self, message: Message) -> bool:
        metadata = message.metadata or {}
        return metadata.get("group", False)
    
    def _is_mentioned(self, message: Message) -> bool:
        content = message.content.lower()
        mentions = ["@hermes-office-synergy-agent"]
        return any(mention in content for mention in mentions)
    
    async def _handle_intent(self, user_id: str, intent: Intent, context: str, metadata: dict = None) -> str:
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
            result = await handler(user_id, intent, context, metadata)
            logger.info(f"[HANDLER_END] 处理器执行完成: {intent.type}, result_length={len(result)}")
            return result
        
        logger.warning(f"[HANDLER_NOT_FOUND] 未找到处理器，使用unknown处理器: {intent.type}")
        return self._handle_unknown(user_id, context)
    
    async def _handle_summarization(self, user_id: str, intent: Intent, context: str, metadata: dict = None) -> str:
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

        prompt = f"总结以下内容：\n{text_to_summarize}"
        return await self._call_model_with_fallback(user_id, "summarization", "simple", prompt)
    
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
    
    async def _handle_question_answering(self, user_id: str, intent: Intent, context: str, metadata: dict = None) -> str:
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

        logger.info(f"[QA_HANDLER] 调用问答模型")
        prompt = f"基于以下上下文回答问题：\n\n上下文：{context_text}\n\n问题：{context}"
        return await self._call_model_with_fallback(
            user_id, "question_answering", "medium", prompt, fallback_prompt=context
        )
    
    async def _handle_task_execution(self, user_id: str, intent: Intent, context: str, metadata: dict = None) -> str:
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
    
    async def _handle_skill_request(self, user_id: str, intent: Intent, context: str, metadata: dict = None) -> str:
        logger.info(f"[SKILL_HANDLER] 开始技能请求处理: user_id={user_id}")
        
        # 使用插件系统的技能管理器
        skill_manager = get_skill_manager()
        
        if skill_manager:
            skill = skill_manager.find_relevant_skill(context)
            if skill:
                logger.info(f"[SKILL_HANDLER] 找到相关技能: skill_name={skill.name}")
                return f"已找到相关技能：{skill.name}\n描述：{skill.description}"
        
        logger.warning("[SKILL_HANDLER] 未找到相关技能，降级到ReAct模式")
        return await react_engine.run(user_id, f"查找与以下内容相关的技能：{context}")
    
    async def _handle_memory_query(self, user_id: str, intent: Intent, context: str, metadata: dict = None) -> str:
        logger.info(f"[MEMORY_HANDLER] 开始记忆查询: user_id={user_id}, query={context[:50]}")
        
        # 使用插件系统的记忆存储
        memory_store = get_memory_store()
        
        if memory_store:
            results = memory_store.search_memory(user_id, context, limit=5)
            if results:
                logger.info(f"[MEMORY_HANDLER] 记忆查询完成: 找到 {len(results)} 条记忆")
                return "\n\n".join(f"[{r.timestamp}] {r.content[:100]}..." for r in results)
        
        logger.warning("[MEMORY_HANDLER] 记忆存储插件不可用或未找到相关记忆，降级到ReAct模式")
        return await react_engine.run(user_id, f"搜索与以下内容相关的记忆：{context}")
    
    async def _handle_document_analysis(self, user_id: str, intent: Intent, context: str, metadata: dict = None) -> str:
        logger.info(f"[DOC_HANDLER] 开始文档分析: user_id={user_id}")
        
        # 获取当前消息的元数据（可能包含文件信息）
        metadata = metadata or {}
        from src.data.database import db
        
        # 首先检查当前消息的元数据中是否有文件信息
        file_key = metadata.get("file_key")
        file_name = metadata.get("file_name")
        
        # 如果当前消息没有文件信息，尝试从最近消息中查找
        if not file_key:
            logger.info("[DOC_HANDLER] 当前消息无文件信息，查找最近消息")
            recent_messages = db.get_recent_messages(user_id, 5)
            for msg in recent_messages:
                if msg.metadata and msg.role == "user":
                    file_key = msg.metadata.get("file_key")
                    file_name = msg.metadata.get("file_name")
                    if file_key:
                        logger.info(f"[DOC_HANDLER] 发现文件上传: file_key={file_key}, file_name={file_name}")
                        break
        
        # 如果有文件上传，尝试直接读取文件内容
        document_content = ""
        if file_key:
            tool_executor = get_tool_executor()
            if tool_executor:
                logger.info(f"[DOC_HANDLER] 使用工具执行器读取文件: {file_key}")
                try:
                    params = {
                        "file_key": file_key,
                        "message_id": metadata.get("message_id", ""),
                        "user_id": user_id
                    }
                    result = tool_executor.execute("feishu_file_read", params)
                    if result.get("success") and result.get("result", {}).get("content"):
                        document_content = result["result"]["content"]
                        logger.info(f"[DOC_HANDLER] 成功读取文件内容: length={len(document_content)}")
                    else:
                        logger.warning(f"[DOC_HANDLER] 文件读取失败: {result.get('error')}")
                except Exception as e:
                    logger.error(f"[DOC_HANDLER] 文件读取异常: {str(e)}")
        
        # 如果文件读取失败或没有文件，使用历史消息内容作为备选
        if not document_content:
            logger.info("[DOC_HANDLER] 文件读取失败或无文件，使用历史消息内容")
            recent_messages = db.get_recent_messages(user_id, 20)
            
            # 过滤出有效内容
            def has_content(content):
                if not content or not content.strip():
                    return False
                content = content.strip()
                if content.startswith('{') and content.endswith('}'):
                    try:
                        import json
                        data = json.loads(content)
                        if 'file_key' in data and 'file_name' in data and len(data) <= 3:
                            return False
                    except:
                        pass
                return True
            
            valid_messages = [m for m in recent_messages if has_content(m.content)]
            file_contents = [m.content for m in valid_messages if m.role == "assistant"]
            
            if not file_contents:
                file_contents = [m.content for m in valid_messages]
            
            document_content = "\n".join(file_contents)
            logger.info(f"[DOC_HANDLER] 提取文档内容: length={len(document_content)}")
        
        # 如果没有可总结的内容
        if not document_content.strip():
            logger.warning(f"[DOC_HANDLER] 文档内容为空")
            return "已收到您上传的文件，但暂时没有可分析的内容。您可以提出具体问题，我来帮您分析。"
        
        logger.info(f"[DOC_HANDLER] 调用文档分析模型")
        prompt = f"""请分析并总结以下文档内容：

{document_content}

请提供：
1. 核心内容总结
2. 关键要点
3. 主要结论或建议
"""
        fallback = f"分析以下文档内容：\n{document_content}"
        return await self._call_model_with_fallback(
            user_id, "document_analysis", "complex", prompt, fallback_prompt=fallback
        )
    
    async def _handle_code_generation(self, user_id: str, intent: Intent, context: str, metadata: dict = None) -> str:
        logger.info(f"[CODE_HANDLER] 开始代码生成: user_id={user_id}")
        prompt = f"生成代码：\n{context}"
        return await self._call_model_with_fallback(user_id, "coding", "complex", prompt)

    async def _handle_creative_writing(self, user_id: str, intent: Intent, context: str, metadata: dict = None) -> str:
        logger.info(f"[CREATIVE_HANDLER] 开始创意写作: user_id={user_id}")
        prompt = f"创作内容：\n{context}"
        fallback = f"根据以下内容创作：\n{context}"
        return await self._call_model_with_fallback(
            user_id, "creative_writing", "medium", prompt, fallback_prompt=fallback
        )
    
    async def _handle_ppt_generation(self, user_id: str, intent: Intent, context: str, metadata: dict = None) -> str:
        """处理PPT生成相关意图 - 使用LangGraph PPT工作流"""
        logger.info(f"[PPT_HANDLER] 开始PPT生产: user_id={user_id}, intent={intent.type}")

        metadata = metadata or {}

        if ppt_workflow.is_awaiting_confirmation(user_id):
            logger.info("[PPT_HANDLER] 检测到等待确认状态，继续工作流")
            response, ctx = ppt_workflow.continue_workflow(user_id, context)
            self._clear_ppt_workflow_context(user_id)
            return response

        document_content = self._extract_document_content(user_id, metadata)
        response, ctx = ppt_workflow.start_workflow(
            user_id=user_id, intent_type=intent.type,
            content=context, document_content=document_content,
        )
        self._clear_ppt_workflow_context(user_id)
        return response

    def _extract_document_content(self, user_id: str, metadata: dict) -> str:
        """提取文档内容"""
        from src.data.database import db

        file_key = metadata.get("file_key")
        file_message_id = metadata.get("message_id", "")

        if not file_key:
            recent_messages = db.get_recent_messages(user_id, 5)
            for msg in recent_messages:
                if msg.metadata and msg.role == "user":
                    file_key = msg.metadata.get("file_key")
                    if file_key:
                        file_message_id = msg.metadata.get("message_id", "") or msg.id or ""
                        break

        if file_key:
            tool_executor = get_tool_executor()
            if tool_executor:
                try:
                    result = tool_executor.execute("feishu_file_read", {
                        "file_key": file_key,
                        "message_id": file_message_id,
                        "user_id": user_id
                    })
                    if result.get("success") and result.get("result", {}).get("content"):
                        return result["result"]["content"]
                except Exception as e:
                    logger.error(f"[PPT_HANDLER] 文件读取异常: {str(e)}")

        recent_messages = db.get_recent_messages(user_id, 20)
        valid_messages = [
            m for m in recent_messages
            if m.content and m.content.strip()
            and not (m.content.strip().startswith('{') and m.content.strip().endswith('}'))
        ]
        file_contents = [m.content for m in valid_messages if m.role == "assistant"]
        if not file_contents:
            file_contents = [m.content for m in valid_messages]

        return "\n".join(file_contents)

    def _clear_ppt_workflow_context(self, user_id: str):
        """清除PPT工作流上下文（LangGraph 版本由 checkpointer 自动管理）"""
        # LangGraph StateGraph 通过 checkpointer 管理状态，无需手动清理内存
        # 保留 _contexts 兼容：移除活跃用户标记
        if hasattr(ppt_workflow, '_contexts') and user_id in ppt_workflow._contexts:
            ppt_workflow._contexts.pop(user_id, None)
            logger.debug(f"[PPT_HANDLER] 清除工作流上下文: user_id={user_id}")
    
    async def _handle_unknown(self, user_id: str, context: str) -> str:
        logger.info(f"[UNKNOWN_HANDLER] 开始处理未知意图: user_id={user_id}")
        return await self._call_model_with_fallback(user_id, "general", "simple", context)
    
    def _load_persisted_sessions(self):
        """从数据库恢复已持久化的会话"""
        import json
        try:
            raw_sessions = db.load_sessions()
            for s in raw_sessions:
                try:
                    user_id = s["user_id"]
                    # 从原始数据重建 session_id 对应的组
                    # 组信息嵌入在上下文消息的元数据中
                    group_id = "default"
                    if user_id not in self.sessions:
                        self.sessions[user_id] = {}
                    # 仅当该组不存在时才创建
                    if group_id not in self.sessions[user_id]:
                        session = Session(
                            id=s["id"],
                            user_id=user_id,
                            group_id=group_id,
                            context=[],
                            created_at=s["created_at"],
                            last_active_at=s["last_active_at"],
                        )
                        self.sessions[user_id][group_id] = session
                except Exception:
                    continue
            count = sum(len(groups) for groups in self.sessions.values())
            logger.info(f"[SESSION_LOAD] 从数据库加载了 {count} 个会话")
        except Exception as e:
            logger.warning(f"[SESSION_LOAD] 会话加载失败: {str(e)}")

    def _persist_session(self, session: Session):
        """将会话持久化到数据库"""
        import json
        try:
            context_json = json.dumps(
                [m.model_dump() for m in session.context],
                ensure_ascii=False
            )
            db.save_session(
                session.id, session.user_id, context_json,
                session.created_at, session.last_active_at
            )
        except Exception as e:
            logger.warning(f"[SESSION_SAVE] 会话持久化失败: {str(e)}")

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
    
    async def _handle_with_react(self, user_id: str, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """使用 ReAct 引擎处理消息"""
        try:
            # 调试日志：检查元数据内容
            logger.debug(f"_handle_with_react - user_id={user_id}, query={query[:100]}..., metadata={metadata}")
            if metadata and "message_id" not in metadata:
                logger.warning(f"元数据中缺少 message_id: {metadata}")
            return await react_engine.run(user_id, query, metadata=metadata)
        except Exception as e:
            logger.error(f"ReAct engine failed: {str(e)}")
            # 降级到普通处理
            return self._handle_unknown(user_id, query)


message_router = MessageRouter()
