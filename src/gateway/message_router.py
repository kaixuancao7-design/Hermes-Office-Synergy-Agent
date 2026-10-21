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
from src.skills.triggers import trigger_matcher
from src.engine.skill_executor import skill_executor

logger = get_logger("gateway")


from src.services.file_context import FileContextService
from src.services.presentation_messages import PresentationMessageService


class MessageRouter:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Session]] = {}  # user_id -> group_id -> Session
        self.use_react_mode = True  # 启用 ReAct 模式
        self._sessions_loaded = False
        self._graph = None  # 延迟初始化 LangGraph 消息图
        self._graph_initialization_attempted = False
        logger.info("[INIT] MessageRouter 初始化完成")
    
    def initialize(self):
        if not self._sessions_loaded:
            self._load_persisted_sessions()
            self._sessions_loaded = True

    async def _call_model_with_fallback(
        self, user_id: str, task_type: str, complexity: str,
        primary_prompt: str, fallback_prompt: str = None
    ) -> str:
        """Call model router with fallback to ReAct engine on failure.

        Args:
            user_id: The user ID for the request
            task_type: Task type for logging (e.g. 'summarization')
            complexity: Complexity hint for logging (e.g. 'simple')
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

        # 直接调用 model_router 的 route() 方法（所有路由器的基础接口）
        response = await model_router.route(primary_prompt)
        if response and response.strip():
            return response

        logger.warning(f"[MODEL] Empty response for {task_type}, falling back to ReAct")
        return await react_engine.run(user_id, fallback_prompt)

    async def route(self, message: Message) -> str:
        """Claim once; only choose the manual pipeline before execution starts."""
        from src.data.request_store import RequestStore
        store = RequestStore(db.db_path)
        key, fingerprint = store.identity(message)
        status, saved = store.claim(key, fingerprint)
        if status == "conflict":
            return "消息标识已用于其他内容，请使用新的消息标识。"
        if status == "completed":
            return saved or ""
        if status != "new":
            return saved or f"请求正在处理或执行结果尚未确认，请核查后再操作。参考号：{key[:16]}"
        try:
            response = await self._route_once(message)
            store.finish(key, response)
            return response
        except Exception as exc:
            stage = getattr(exc, "stage", "execution")
            logger.exception("Message failed without replay | request=%s | stage=%s", key[:16], stage)
            response = f"请求处理失败，部分操作可能已完成，已停止自动重试。请核查执行结果。参考号：{key[:16]}"
            store.finish(key, response, "failed", stage)
            return response

    async def _route_once(self, message: Message) -> str:
        if hasattr(self, "_sessions_loaded"):
            self.initialize()
        # 延迟初始化 LangGraph 消息图
        if self._graph is None and not self._graph_initialization_attempted:
            self._graph_initialization_attempted = True
            try:
                from src.gateway.message_graph import MessageGraph
                graph = MessageGraph(self)
                if graph._graph is None:
                    raise RuntimeError("Message graph could not be built")
                self._graph = graph
                logger.info("[ROUTER] LangGraph消息图已启用")
            except Exception as e:
                logger.warning(f"[ROUTER] LangGraph消息图不可用: {str(e)}，使用手写管道")

        if self._graph is not None:
            return await self._graph.route(message)

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

            # 隐式纠正检测：用户是否在纠正上一轮回答？（三闸门 Gate 1）
            self._detect_implicit_correction(user_id, message, session)

            # 群消息过滤
            if self._is_group_message(message) and not self._is_mentioned(message):
                logger.debug(f"[GROUP_FILTER] 群消息未提及机器人，忽略 | user_id={user_id}")
                return ""

            if await ppt_workflow.is_awaiting_confirmation(user_id):
                response, _ = await ppt_workflow.continue_workflow(user_id, message.content)
                self._save_response_to_db(user_id, response, group_id, group_name, "ppt_generation")
                return response

            # =================================================================
            # 技能预匹配：Tier 1 轻量级匹配 → Tier 2 按需加载 → 执行
            # 支持三层渐进式披露：
            #   Layer 1 (score ≥ 0.5): 自动执行技能 + 显示披露头/步骤进度/归因页脚
            #   Layer 2 (0.3 ≤ score < 0.5): 接近匹配 → 建议使用技能
            #   Layer 3 (score < 0.3): 静默跳过，走正常意图识别流程
            #
            # Token 优化: Tier 1 匹配使用 SkillSummary（~500 chars/skill），
            #   仅在确认匹配后通过 load_full_skill() 加载完整 Skill 对象
            # =================================================================
            is_file_upload = bool(metadata.get("file_key") or metadata.get("file_name"))
            matched_summary, near_misses = (None, []) if is_file_upload else trigger_matcher.find_relevant_skill_with_near_misses(
                message.content, user_id
            )

            if matched_summary:
                score = trigger_matcher._calculate_match_score(
                    matched_summary, message.content.lower()
                )
                if score >= skill_executor.SKILL_MATCH_THRESHOLD:
                    logger.info(
                        f"[SKILL_PREMATCH] Tier 1 matched, loading Tier 2 | "
                        f"skill={matched_summary.name} | score={score:.2f} | "
                        f"type={matched_summary.type}"
                    )

                    # Tier 2: 按需加载完整 Skill（仅在确认匹配后）
                    full_skill = trigger_matcher.load_full_skill(matched_summary.id)
                    if full_skill is None:
                        logger.warning(
                            f"[SKILL_PREMATCH] Tier 2 load failed for {matched_summary.id}, "
                            f"falling through to normal routing"
                        )
                    else:
                        try:
                            result = await skill_executor.execute_skill(
                                full_skill, message.content, user_id,
                                metadata=message.metadata,
                                match_score=score,
                            )

                            # 渐进式披露：拼接披露头 + 步骤进度 + LLM回复 + 归因页脚
                            step_log = "\n".join(result.step_progress) if result.step_progress else ""
                            footer = skill_executor.build_footer(
                                full_skill.name, full_skill.type, score
                            )
                            response = (
                                f"{result.disclosure}\n"
                                f"{step_log}\n\n"
                                f"{result.response}"
                                f"{footer}"
                            )

                            # 保存响应和日志
                            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                            log_event(logger, "message_processed", trace_id=trace_id,
                                     user_id=user_id, intent="skill_prematch",
                                     mode="Skill", response_length=len(response),
                                     elapsed_ms=elapsed_ms)
                            self._save_response_to_db(user_id, response, group_id, group_name, "skill_prematch")
                            return response
                        except Exception as e:
                            logger.error(
                                f"[SKILL_PREMATCH] Skill execution failed; replay stopped | error={str(e)}"
                            )
                            raise

            # 接近匹配建议：score 在 0.3-0.5 之间，提示用户但不自动执行
            if near_misses and not matched_summary:
                pending_skill_suggestion = skill_executor.build_near_miss_suggestion(
                    near_misses
                )
            else:
                pending_skill_suggestion = None

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

            # 附加接近匹配的技能建议（渐进式披露 Layer 2）
            if pending_skill_suggestion:
                response += pending_skill_suggestion
                pending_skill_suggestion = None

            # 保存响应
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            log_event(logger, "message_processed", trace_id=trace_id, user_id=user_id,
                     intent=intent.type, mode=mode, response_length=len(response), elapsed_ms=elapsed_ms)

            self._save_response_to_db(user_id, response, group_id, group_name, intent.type)
            return response

        except Exception as e:
            logger.error(f"[ROUTER_ERROR] trace_id={trace_id} | error={str(e)}", exc_info=True)
            raise
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
        return FileContextService(db, get_tool_executor)._get_recent_file_content(user_id)
    
    def _extract_file_content_from_messages(self, user_id: str) -> str:
        return FileContextService(db, get_tool_executor)._extract_file_content_from_messages(user_id)
    
    def _extract_valid_text(self, messages) -> str:
        return FileContextService(db, get_tool_executor)._extract_valid_text(messages)
    
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
        """处理技能请求 — Tier 1 匹配 → Tier 2 加载 → 执行步骤链

        优先使用 SkillStepExecutor 执行完整的技能工作流（工具调用 + LLM 语义动作）。
        如果技能管理器未找到技能，降级使用 TriggerMatcher 直接匹配（Tier 1 摘要匹配）。
        匹配成功后通过 Tier 2 按需加载完整 Skill 对象。
        如果仍未找到，降级到 ReAct 引擎进行自由推理。
        """
        logger.info(f"[SKILL_HANDLER] 开始技能请求处理: user_id={user_id}")

        # 方式 1: 通过插件系统的技能管理器查找
        skill_manager = get_skill_manager()
        summary = None

        if skill_manager:
            try:
                summary = skill_manager.find_relevant_skill(context, user_id)
            except AttributeError:
                # HybridSkillManager 没有 find_relevant_skill 方法
                pass

        # 方式 2: 通过 TriggerMatcher Tier 1 轻量级匹配
        if summary is None:
            summary = trigger_matcher.find_relevant_skill(context, user_id)

        # Tier 2: 按需加载完整 Skill 并执行
        if summary:
            full_skill = trigger_matcher.load_full_skill(summary.id)
            if full_skill:
                logger.info(
                    f"[SKILL_HANDLER] T1 matched, T2 loaded | "
                    f"skill={full_skill.name} | type={full_skill.type} | "
                    f"steps={len(full_skill.steps)}"
                )
                try:
                    result = await skill_executor.execute_skill(
                        full_skill, context, user_id, metadata=metadata,
                        match_score=trigger_matcher._calculate_match_score(
                            summary, context.lower()
                        ),
                    )
                    return result.response
                except Exception as e:
                    logger.error(
                        f"[SKILL_HANDLER] Skill execution failed; replay stopped | error={str(e)}"
                    )
                    raise

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
    
    async def _handle_ppt_generation(self, user_id: str, intent: Intent, context: str, metadata: dict=None):
        handler = PresentationMessageService(ppt_workflow, FileContextService(db, get_tool_executor))
        return await handler._handle_ppt_generation(user_id, intent, context, metadata)

    def _extract_document_content(self, user_id: str, metadata: dict) -> str:
        return FileContextService(db, get_tool_executor)._extract_document_content(user_id, metadata)

    def _clear_ppt_workflow_context(self, user_id: str):
        handler = PresentationMessageService(ppt_workflow, FileContextService(db, get_tool_executor))
        return handler._clear_ppt_workflow_context(user_id)
    
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

    def _detect_implicit_correction(self, user_id: str, message: Message, session: Session) -> None:
        """Gate 1 隐式触发: 检测用户是否在纠正上一轮回答

        关键词匹配用户消息中的纠正意图，自动捕获原始输出与纠正输出，
        送入三闸门学习循环。
        """
        CORRECTION_KEYWORDS = [
            "不对", "应该是", "不是这样的", "错了", "纠正", "改正",
            "应该是这样", "你再看看", "重新来", "不是这个意思",
            "应该是…", "不对吧", "搞错了", "你理解错了",
        ]
        content = message.content.strip()
        if not content:
            return

        # 检测纠正意图
        has_correction = any(kw in content for kw in CORRECTION_KEYWORDS)
        if not has_correction:
            return

        # 获取上一轮 assistant 回复
        assistant_msgs = [m for m in session.context if m.role == "assistant"]
        if not assistant_msgs:
            return

        last_response = assistant_msgs[-1].content
        if not last_response or len(last_response) < 20:
            return

        # 提取真实意图（去除纠正前缀后的内容作为 corrected）
        corrected = content
        for kw in CORRECTION_KEYWORDS:
            corrected = corrected.replace(kw, "").strip("，,。.！!？?：: ")

        if not corrected or len(corrected) < 5:
            return  # 纠正内容太短，跳过

        logger.info(f"[LEARN:G1] 检测到隐式纠正 | user_id={user_id}"
                     f" | original_len={len(last_response)} | corrected_len={len(corrected)}")

        # 送入学习循环
        context = "\n".join(
            m.content for m in session.context[-4:]
            if m.role in ("user", "assistant")
        )
        learning_cycle.capture_correction(
            user_id=user_id,
            original=last_response,
            corrected=corrected,
            context=context,
            intent="implicit_correction",
        )

        # 自动修补：检查纠正是否关联到已有 learned 技能
        import asyncio
        asyncio.create_task(self._auto_patch_if_relevant(
            user_id, context, last_response, corrected
        ))

    def capture_correction(self, user_id: str, original: str, corrected: str, context: str) -> None:
        """显式捕获用户纠正（API调用入口）"""
        learning_cycle.capture_correction(user_id, original, corrected, context)

    async def _auto_generate_skill_if_complex(self, user_id: str, trace) -> None:
        """检查最近一次 ReAct 执行轨迹，如果足够复杂则自动生成技能"""
        try:
            if not trace or trace.user_id != user_id:
                return

            from src.engine.skill_generator import skill_auto_generator
            if skill_auto_generator.should_trigger(trace):
                logger.info(f"[AUTO_SKILL] Complex task detected:"
                             f" {len(trace.tool_sequence)} tool calls"
                             f" | mode={trace.mode}")
                await skill_auto_generator.generate_from_trace(trace)
        except Exception as e:
            logger.warning(f"[AUTO_SKILL] Auto-generation check failed: {e}")

    async def _auto_patch_if_relevant(self, user_id: str, context: str,
                                       original: str, corrected: str) -> None:
        """检查纠正是否关联到已有 learned 技能，如是则自动修补"""
        try:
            from src.engine.skill_patcher import skill_auto_patcher

            related = await skill_auto_patcher.find_related_skill(context, user_id)
            if related:
                logger.info(f"[AUTO_PATCH] Correction relates to skill: {related.name}")
                await skill_auto_patcher.patch_skill(related, original, corrected, context, user_id)
        except Exception as e:
            logger.warning(f"[AUTO_PATCH] Auto-patch check failed: {e}")
    
    def _should_use_react(self, intent: Intent) -> bool:
        """判断是否应该使用 ReAct 模式

        可触发 ReAct 的意图在执行后才能调用 _auto_generate_skill_if_complex，
        因此需要自动技能生成的意图（summarization、creative_writing、
        document_analysis、skill_request 等）也需纳入此列表。
        """
        react_intents = [
            "question_answering",
            "task_execution",
            "code_generation",
            "unknown",  # 未知意图使用 ReAct 进行探索
            # 以下意图虽有独立 handler，但需要 ReAct 执行轨迹来触发自动技能生成
            "summarization",
            "creative_writing",
            "document_analysis",
            "skill_request",
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
            response, trace = await react_engine.run_with_trace(user_id, query, metadata=metadata)
            if trace:
                import asyncio
                asyncio.create_task(self._auto_generate_skill_if_complex(user_id, trace))
            return response
        except Exception as e:
            logger.error(f"ReAct engine failed: {str(e)}")
            raise


message_router = MessageRouter()
