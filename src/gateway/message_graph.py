"""消息路由图 — 基于LangGraph StateGraph的消息处理管道

图结构:
  __start__
      ↓
   setup         ← trace_id, 会话管理, 消息存储
      ↓
   filter        ← 群消息检查 → skip (提前结束)
      ↓
   detect_file   ← 文件上传检测 → 覆盖意图
      ↓
   skill_prematch ← ★ 技能预匹配：高置信度技能直接执行
      ↓
   recognize     ← 意图识别（skill_prematch 未命中时）
      ↓
   route_intent  ← 条件分发
      ├── skill  → handle_skill  → save_response → END
      ├── ppt    → handle_ppt    → save_response → END
      ├── react  → handle_react  → save_response → END
      └── direct → handle_direct → save_response → END

设计原则:
  - 图管理流程控制，具体处理逻辑保留在 MessageRouter 中
  - 与 Stage 1/2 的 ReAct Agent 和 PPT Workflow 无缝集成
"""

from typing import Dict, Any, Optional, List, TypedDict
from datetime import datetime

from src.types import Message, Intent
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger, set_request_context, clear_request_context, log_event
from src.plugins import get_memory_store, get_tool_executor
from src.skills.triggers import trigger_matcher
from src.engine.skill_executor import skill_executor

logger = get_logger("gateway")


# ============================================================================
# Graph State
# ============================================================================

class RouteState(TypedDict, total=False):
    """消息路由状态 — 在节点间传递的所有数据"""
    # ---- 输入 ----
    message: Message  # 原始消息对象（不可序列化，仅传递引用）
    user_id: str
    content: str
    metadata: dict
    trace_id: str

    # ---- 会话 ----
    group_id: str
    group_name: str

    # ---- 流程控制 ----
    skip_processing: bool      # 是否跳过（群消息未提及）
    is_file_upload: bool       # 是否文件上传
    file_name: str             # 上传文件名

    # ---- 意图 ----
    intent_type: str
    intent_confidence: float
    intent_entities: dict
    use_react: bool
    mode: str                  # "ReAct" | "Direct" | "PPT" | "Skill"

    # ---- 技能预匹配 ----
    matched_skill: Any         # 预匹配到的技能对象（Skill），供 handle_skill 节点使用

    # ---- 输出 ----
    response: str
    elapsed_ms: float


# ============================================================================
# MessageGraph
# ============================================================================

class MessageGraph:
    """基于LangGraph的消息路由图。

    负责消息处理管道的流程控制，具体处理逻辑委托给 MessageRouter。
    """

    def __init__(self, router):
        """
        Args:
            router: MessageRouter 实例，提供 handler 方法和会话管理
        """
        self.router = router
        self._graph = self._build_graph()
        logger.info("[MSG_GRAPH] LangGraph消息路由图初始化完成")

    # ========================================================================
    # 图构建
    # ========================================================================

    def _build_graph(self):
        """构建 LangGraph StateGraph"""
        try:
            from langgraph.graph import StateGraph, START, END
            from src.engine.checkpointer import get_checkpointer

            graph = StateGraph(RouteState)

            # 添加节点
            graph.add_node("setup", self._setup_node)
            graph.add_node("filter", self._filter_node)
            graph.add_node("detect_file", self._detect_file_node)
            graph.add_node("skill_prematch", self._skill_prematch_node)
            graph.add_node("recognize", self._recognize_node)
            graph.add_node("handle_skill", self._handle_skill_node)
            graph.add_node("handle_ppt", self._handle_ppt_node)
            graph.add_node("handle_react", self._handle_react_node)
            graph.add_node("handle_direct", self._handle_direct_node)
            graph.add_node("save_response", self._save_response_node)

            # 主线
            graph.add_edge(START, "setup")
            graph.add_edge("setup", "filter")

            # filter → skip 或 继续
            graph.add_conditional_edges(
                "filter",
                self._route_after_filter,
                {"detect_file": "detect_file", "end": END},
            )

            # detect_file → skill_prematch → recognize
            graph.add_edge("detect_file", "skill_prematch")
            graph.add_edge("skill_prematch", "recognize")

            # recognize → skill / ppt / react / direct
            graph.add_conditional_edges(
                "recognize",
                self._route_intent,
                {
                    "handle_skill": "handle_skill",
                    "handle_ppt": "handle_ppt",
                    "handle_react": "handle_react",
                    "handle_direct": "handle_direct",
                },
            )

            # 所有处理器 → save_response
            graph.add_edge("handle_skill", "save_response")
            graph.add_edge("handle_ppt", "save_response")
            graph.add_edge("handle_react", "save_response")
            graph.add_edge("handle_direct", "save_response")
            graph.add_edge("save_response", END)

            return graph.compile(checkpointer=get_checkpointer())

        except ImportError:
            logger.warning("[MSG_GRAPH] langgraph未安装，消息图不可用")
            return None

    # ========================================================================
    # 公开入口
    # ========================================================================

    async def route(self, message: Message) -> str:
        """处理消息并返回响应。与 MessageRouter.route() 签名一致。"""
        start_time = datetime.now()

        if self._graph is None:
            return await self.router.route(message)

        metadata = message.metadata or {}
        trace_id = metadata.get("message_id", generate_id())
        user_id = message.user_id

        set_request_context(request_id=trace_id, user_id=user_id)

        try:
            initial_state: RouteState = {
                "message": message,
                "user_id": user_id,
                "content": message.content,
                "metadata": metadata,
                "trace_id": trace_id,
                "group_id": metadata.get("group_id", "default"),
                "group_name": metadata.get("group_name", "默认会话"),
                "skip_processing": False,
                "is_file_upload": False,
                "file_name": "",
                "intent_type": "unknown",
                "intent_confidence": 0.0,
                "intent_entities": {},
                "use_react": False,
                "mode": "Direct",
                "response": "",
                "elapsed_ms": 0.0,
            }

            config = {"configurable": {"thread_id": f"msg_{trace_id}"}}
            result = await self._graph.ainvoke(initial_state, config)

            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            response = result.get("response", "")

            logger.info(f"[MSG_GRAPH] 路由完成 | trace_id={trace_id} | mode={result.get('mode')} | response_length={len(response)} | elapsed={elapsed_ms:.2f}ms")

            log_event(logger, "message_processed",
                     trace_id=trace_id, user_id=user_id,
                     intent=result.get("intent_type"),
                     mode=result.get("mode"),
                     response_length=len(response),
                     elapsed_ms=elapsed_ms)

            return response

        except Exception as e:
            logger.error(f"[MSG_GRAPH] 路由失败 | trace_id={trace_id} | error={str(e)}", exc_info=True)
            return "处理请求时出现错误，请稍后重试。"
        finally:
            clear_request_context()

    # ========================================================================
    # 图节点实现
    # ========================================================================

    async def _setup_node(self, state: RouteState) -> RouteState:
        """Setup节点 — 会话管理、消息存储、记忆存储"""
        message = state.get("message")
        user_id = state["user_id"]
        group_id = state["group_id"]
        group_name = state["group_name"]
        trace_id = state["trace_id"]

        logger.info(f"[MSG_SETUP] trace_id={trace_id} | user_id={user_id} | content={state['content'][:50]}")

        # 会话管理（委托给 MessageRouter）
        session = self.router._get_or_create_session(user_id, group_id, group_name)
        session.context.append(message)
        session.last_active_at = get_timestamp()
        self.router._persist_session(session)

        # 保存消息
        db.save_message(message)

        # 记忆存储
        memory_store = get_memory_store()
        if memory_store:
            try:
                from src.types import MemoryEntry
                entry = MemoryEntry(
                    id=generate_id(), user_id=user_id, type="short",
                    content=state["content"], timestamp=message.timestamp,
                    tags=["short_term", "message", group_id],
                    group_id=group_id, group_name=group_name,
                )
                memory_store.add_memory(user_id, entry)
            except Exception as e:
                logger.error(f"[MSG_SETUP] 记忆存储失败: {str(e)}")

        return state

    async def _filter_node(self, state: RouteState) -> RouteState:
        """Filter节点 — 群消息检查"""
        message = state.get("message")
        metadata = state.get("metadata", {})

        if metadata.get("group", False):
            content_lower = state.get("content", "").lower()
            if "@hermes-office-synergy-agent" not in content_lower:
                logger.debug(f"[MSG_FILTER] 群消息未提及机器人，跳过 | user_id={state['user_id']}")
                state["skip_processing"] = True
                state["response"] = ""

        return state

    async def _detect_file_node(self, state: RouteState) -> RouteState:
        """DetectFile节点 — 检测文件上传"""
        metadata = state.get("metadata", {})
        if metadata.get("file_key") or metadata.get("file_name"):
            state["is_file_upload"] = True
            state["file_name"] = metadata.get("file_name", "")
            logger.info(f"[MSG_DETECT] 文件上传 | file_name={state['file_name']}")
        return state

    async def _skill_prematch_node(self, state: RouteState) -> RouteState:
        """SkillPrematch节点 — 在意图识别前检查是否有高置信度技能匹配

        如果匹配到技能（score ≥ 0.5），直接设置 intent_type="skill_execute"，
        跳过后续的意图识别。文件上传场景跳过技能匹配。
        """
        if state.get("is_file_upload"):
            return state  # 文件上传跳过技能匹配，走正常文档分析流程

        query = state["content"]
        user_id = state.get("user_id", "unknown")

        matched = trigger_matcher.find_relevant_skill(query, user_id)
        if matched:
            score = trigger_matcher._calculate_match_score(matched, query.lower())
            if score >= skill_executor.SKILL_MATCH_THRESHOLD:
                logger.info(
                    f"[MSG_SKILL_PREMATCH] Skill matched | "
                    f"skill={matched.name} | score={score:.2f} | type={matched.type}"
                )
                state["matched_skill"] = matched
                state["intent_type"] = "skill_execute"
                state["intent_confidence"] = score
                state["mode"] = "Skill"
                state["use_react"] = False
                return state

        return state

    async def _recognize_node(self, state: RouteState) -> RouteState:
        """Recognize节点 — 意图识别 + 路由决策

        如果 skill_prematch 已经匹配到技能（intent_type="skill_execute"），
        则跳过意图识别，直接保留技能匹配结果。
        """
        # 技能预匹配已命中 → 跳过意图识别
        if state.get("intent_type") == "skill_execute":
            logger.info(
                f"[MSG_RECOGNIZE] Skipping intent recognition — "
                f"skill already matched | skill={state.get('matched_skill').name if state.get('matched_skill') else '?'}"
            )
            return state

        from src.engine.intent_recognition import intent_recognizer

        if state.get("is_file_upload"):
            # 文件上传 → 强制文档分析
            state["intent_type"] = "document_analysis"
            state["intent_confidence"] = 0.95
            state["intent_entities"] = {"file_name": state.get("file_name", "")}
            state["use_react"] = False
            state["mode"] = "Direct"
        else:
            intent = await intent_recognizer.recognize(state["content"])
            state["intent_type"] = intent.type
            state["intent_confidence"] = intent.confidence
            state["intent_entities"] = intent.entities

            use_react = self.router.use_react_mode and self.router._should_use_react(intent)
            state["use_react"] = use_react
            state["mode"] = "ReAct" if use_react else "Direct"

        logger.info(f"[MSG_RECOGNIZE] intent={state['intent_type']} | confidence={state['intent_confidence']:.2f} | mode={state['mode']}")
        return state

    async def _handle_skill_node(self, state: RouteState) -> RouteState:
        """HandleSkill节点 — Tier 2 按需加载 + 执行技能步骤链（含渐进式披露）"""
        from src.data.database import db
        from src.skills.triggers import trigger_matcher

        summary = state.get("matched_skill")  # Tier 1: SkillSummary
        user_id = state["user_id"]
        content = state["content"]
        metadata = state.get("metadata")
        match_score = state.get("intent_confidence", 0.0)

        if summary is None:
            logger.warning("[MSG_SKILL] No matched_skill in state, falling back to direct handler")
            state["response"] = "技能匹配数据丢失，请重试。"
            return state

        # Tier 2: 按需加载完整 Skill（仅在确认匹配后）
        full_skill = trigger_matcher.load_full_skill(summary.id)
        if full_skill is None:
            logger.warning(f"[MSG_SKILL] Tier 2 load failed for {summary.id}")
            state["response"] = f"技能「{summary.name}」加载失败，请稍后重试。"
            return state

        logger.info(
            f"[MSG_SKILL] T1 matched, T2 loaded | skill={full_skill.name} | "
            f"steps={len(full_skill.steps)} | type={full_skill.type} | score={match_score:.2f}"
        )

        try:
            result = await skill_executor.execute_skill(
                full_skill, content, user_id, metadata=metadata, match_score=match_score,
            )

            # 渐进式披露：拼接披露头 + 步骤进度 + LLM回复 + 归因页脚
            step_log = "\n".join(result.step_progress) if result.step_progress else ""
            footer = skill_executor.build_footer(full_skill.name, full_skill.type, match_score)
            state["response"] = (
                f"{result.disclosure}\n"
                f"{step_log}\n\n"
                f"{result.response}"
                f"{footer}"
            )

            # 记录技能使用（供 Curator 评分）
            db.record_skill_usage(full_skill.id, user_id)
        except Exception as e:
            logger.error(f"[MSG_SKILL] Skill execution failed | error={str(e)}")
            state["response"] = (
                f"执行技能「{full_skill.name}」时出现错误，已切换到通用模式处理您的请求。\n\n"
                f"错误详情: {str(e)[:200]}"
            )

        return state

    async def _handle_ppt_node(self, state: RouteState) -> RouteState:
        """HandlePPT节点 — PPT工作流"""
        from src.engine.ppt_workflow import ppt_workflow

        user_id = state["user_id"]
        content = state["content"]
        metadata = state.get("metadata", {})

        if ppt_workflow.is_awaiting_confirmation(user_id):
            logger.info("[MSG_PPT] 继续工作流")
            response, _ = ppt_workflow.continue_workflow(user_id, content)
        else:
            document_content = self.router._extract_document_content(user_id, metadata)
            response, _ = ppt_workflow.start_workflow(
                user_id=user_id,
                intent_type=state["intent_type"],
                content=content,
                document_content=document_content,
            )

        state["response"] = response
        return state

    async def _handle_react_node(self, state: RouteState) -> RouteState:
        """HandleReAct节点 — ReAct引擎（使用Stage 1的LangGraph agent）"""
        from src.engine.react_engine import react_engine

        user_id = state["user_id"]
        content = state["content"]
        metadata = state.get("metadata")

        response = await react_engine.run(user_id, content, metadata=metadata)
        state["response"] = response
        return state

    async def _handle_direct_node(self, state: RouteState) -> RouteState:
        """HandleDirect节点 — 意图处理器分发"""
        from src.engine.intent_recognition import intent_recognizer

        user_id = state["user_id"]
        content = state["content"]
        intent_type = state["intent_type"]
        metadata = state.get("metadata")

        intent = Intent(
            type=intent_type,
            confidence=state["intent_confidence"],
            entities=state.get("intent_entities", {}),
        )

        response = await self.router._handle_intent(user_id, intent, content, metadata)
        state["response"] = response
        return state

    async def _save_response_node(self, state: RouteState) -> RouteState:
        """SaveResponse节点 — 保存响应、记忆存储、日志"""
        user_id = state["user_id"]
        response = state.get("response", "")
        group_id = state["group_id"]
        group_name = state["group_name"]
        intent_type = state["intent_type"]

        # 保存响应消息
        response_msg = Message(
            id=generate_id(),
            user_id=user_id,
            content=response,
            role="assistant",
            timestamp=get_timestamp(),
            metadata={"intent": intent_type},
        )
        db.save_message(response_msg)

        # 记忆存储
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
                logger.error(f"[MSG_SAVE] 响应记忆存储失败: {str(e)}")

        return state

    # ========================================================================
    # 条件路由
    # ========================================================================

    def _route_after_filter(self, state: RouteState) -> str:
        """群消息过滤后的路由"""
        if state.get("skip_processing", False):
            return "end"
        return "detect_file"

    def _route_intent(self, state: RouteState) -> str:
        """意图路由: 技能执行 / PPT工作流 / ReAct引擎 / 直接处理器"""
        intent_type = state.get("intent_type", "unknown")

        # 技能执行（预匹配命中）
        if intent_type == "skill_execute" and state.get("matched_skill"):
            return "handle_skill"

        # PPT相关意图
        if intent_type.startswith("ppt_"):
            return "handle_ppt"

        # ReAct模式
        if state.get("use_react", False):
            return "handle_react"

        return "handle_direct"


# 图节点列表（供可视化）
GRAPH_NODES = [
    "setup", "filter", "detect_file", "skill_prematch", "recognize",
    "handle_skill", "handle_ppt", "handle_react", "handle_direct",
    "save_response",
]
