"""ReAct推理引擎 — 三层策略：LangGraph Agent → LangChain JSON → 关键词回退

策略层级：
  1. LangGraph create_react_agent — 原生 function calling，自动 Think→Act→Observe 循环
     适用于支持 tool calling 的模型（ollama qwen3/llama3.1+, openai, claude, zhipu, moonshot）
  2. LangChain JSON 模式 — prompts/react_system_prompt.txt 驱动
     兼容所有模型，通过解析 JSON 响应提取工具调用
  3. 关键词匹配 — 纯代码回退
     LangChain 不可用时的最后保障
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from src.config import settings
from src.logging_config import get_logger, log_performance, log_event
from src.utils import generate_id, get_timestamp
from src.plugins import get_tool_executor, get_model_router
from src.plugins.model_routers import select_model, call_model

logger = get_logger("engine")


class ReActEngine:
    """ReAct推理引擎

    三层策略（优先级从高到低）：
      1. LangGraph create_react_agent — 原生 tool calling，自动循环
      2. LangChain JSON 模式 — react_system_prompt.txt 驱动，兼容所有模型
      3. 关键词匹配 — 纯代码回退
    """

    def __init__(self):
        self.max_thinking_steps = 5
        self.max_tool_calls = 3
        self._langchain_available = None      # 延迟检测
        self._langgraph_available = None       # 延迟检测
        logger.info("[INIT] ReActEngine 初始化完成 | max_steps=%d | max_tool_calls=%d",
                   self.max_thinking_steps, self.max_tool_calls)

    # ========================================================================
    # 公开入口 — 三层回退
    # ========================================================================

    @log_performance(logger, "ReAct推理")
    async def run(self, user_id: str, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """执行ReAct推理

        优先级: LangGraph agent → LangChain JSON模式 → 关键词回退 → 直接模型调用
        """
        start_time = datetime.now()
        trace_id = metadata.get("message_id", generate_id()) if metadata else generate_id()
        logger.info(f"[ReAct_START] 开始推理 | trace_id={trace_id} | user_id={user_id} | query={query[:50]}")

        try:
            tool_executor = get_tool_executor()
            if not tool_executor:
                logger.warning("[ReAct_WARNING] 工具执行器不可用，降级到直接调用模型")
                return await self._call_model_directly(query)

            available_tools = tool_executor.get_tools()
            logger.info(f"[ReAct_TOOLS] 可用工具列表 | count={len(available_tools)} | tools={available_tools}")

            # ---- 第1层：LangGraph create_react_agent ----
            result = await self._run_with_langgraph(query, available_tools, user_id)
            if result is not None:
                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                log_event(logger, "react_complete", trace_id=trace_id, user_id=user_id,
                         mode="langgraph", response_length=len(result), elapsed_ms=elapsed_ms)
                logger.info(f"[ReAct_COMPLETE] LangGraph推理完成 | trace_id={trace_id} | response_length={len(result)} | elapsed={elapsed_ms:.2f}ms")
                return result

            # ---- 第2层：LangChain JSON 模式 + 第3层：关键词回退 ----
            return await self._run_with_manual_loop(
                query=query,
                available_tools=available_tools,
                user_id=user_id,
                metadata=metadata,
                tool_executor=tool_executor,
                trace_id=trace_id,
                start_time=start_time,
            )

        except Exception as e:
            logger.error(f"[ReAct_ERROR] 推理失败 | trace_id={trace_id} | user_id={user_id} | error={str(e)}", exc_info=True)
            return f"处理请求时出现错误: {str(e)}"

    # ========================================================================
    # 第1层：LangGraph create_react_agent
    # ========================================================================

    async def _run_with_langgraph(
        self,
        query: str,
        available_tools: List[str],
        user_id: str,
    ) -> Optional[str]:
        """使用 LangGraph 的 create_react_agent 进行推理。

        LangGraph 自动处理 Think→Act→Observe 循环：
        - LLM 通过 bind_tools() 原生决定调用哪个工具
        - ToolNode 自动执行工具并回传结果
        - 循环直到 LLM 生成最终回答

        Returns:
            最终响应文本，失败时返回 None（触发回退）
        """
        if not self._check_langgraph_available():
            return None

        try:
            from src.engine.langchain_tools import (
                create_langchain_tools,
                create_chat_model,
            )
            from src.engine.checkpointer import get_checkpointer
            from langchain.agents import create_agent
            from langchain_core.messages import HumanMessage

            # 1. 创建 LangChain 工具（复用已有包装层）
            lc_tools = create_langchain_tools(available_tools)
            if not lc_tools:
                logger.warning("[ReAct_LG] 无可用LangChain工具，回退到JSON模式")
                return None

            # 2. 创建 ChatModel（复用已有工厂）
            chat_model = create_chat_model(temperature=0.0)
            if not chat_model:
                logger.warning("[ReAct_LG] ChatModel创建失败，回退到JSON模式")
                return None

            # 3. 构建精简系统提示（角色 + 规则，不含JSON格式要求）
            system_prompt = self._build_langgraph_prompt(available_tools)

            # 4. 创建 LangGraph agent（使用新 API: langchain.agents.create_agent）
            agent = create_agent(
                model=chat_model,
                tools=lc_tools,
                system_prompt=system_prompt,
                checkpointer=get_checkpointer(),
            )

            # 5. 调用 agent
            logger.info(f"[ReAct_LG] 启动LangGraph agent | model={settings.MODEL_ROUTER_TYPE} | tools={[t.name for t in lc_tools]}")
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=query)]},
                config={"configurable": {"thread_id": user_id}},
            )

            # 6. 提取最终回答（最后一条 AI 消息）
            messages = result.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, "type") and msg.type == "ai":
                    content = msg.content if hasattr(msg, "content") else str(msg)
                    if content and len(content.strip()) > 0:
                        logger.info(f"[ReAct_LG] LangGraph agent返回回答 | length={len(content)}")
                        return content.strip()

            logger.warning("[ReAct_LG] Agent未返回有效AI消息，回退到JSON模式")
            return None

        except ImportError as e:
            logger.info(f"[ReAct_LG] langgraph不可用: {str(e)}，回退到JSON模式")
            return None
        except Exception as e:
            logger.warning(f"[ReAct_LG] LangGraph agent异常: {str(e)}，回退到JSON模式")
            return None

    def _build_langgraph_prompt(self, available_tools: List[str]) -> str:
        """为 LangGraph agent 构建精简系统提示词。

        与 react_system_prompt.txt 不同，这里不需要 JSON 格式指令 —
        LangGraph 的 create_react_agent 通过原生 function calling 处理工具调用。
        这里只提供角色描述和使用指南。
        """
        from src.engine.langchain_tools import TOOL_DEFINITIONS

        tool_lines = []
        for tool_id in available_tools:
            if tool_id in TOOL_DEFINITIONS:
                tool_lines.append(f"- **{tool_id}**: {TOOL_DEFINITIONS[tool_id]['description']}")

        tools_desc = "\n".join(tool_lines) if tool_lines else "无可用工具"

        return f"""你是一个智能办公协同助手（Hermes Office Synergy Agent）。

## 可用工具
{tools_desc}

## 使用规则
1. 分析用户问题，只在确实需要时调用工具。
2. 简单问答、闲聊可直接回答，无需调用工具。
3. 每次优先调用最相关的工具。
4. 用户上传文件时，优先用 feishu_file_read 读取内容。
5. 获取足够信息后，用自然语言给出专业、友好的回答。
"""

    # ========================================================================
    # 第2层 + 第3层：LangChain JSON 模式 + 关键词回退（原有逻辑）
    # ========================================================================

    async def _run_with_manual_loop(
        self,
        query: str,
        available_tools: List[str],
        user_id: str,
        metadata: Optional[Dict[str, Any]],
        tool_executor,
        trace_id: str,
        start_time: datetime,
    ) -> str:
        """手动 ReAct 循环：LangChain JSON 模式 → 关键词回退"""
        context = query
        tool_call_count = 0

        for step in range(self.max_thinking_steps):
            logger.info(f"[ReAct_STEP] 推理步骤 {step+1}/{self.max_thinking_steps}")

            decision = await self._decide_next_action(
                query=query, context=context,
                available_tools=available_tools, user_id=user_id,
                tool_call_count=tool_call_count, metadata=metadata,
            )

            if decision["action"] == "tool_call" and tool_call_count < self.max_tool_calls:
                tool_call_count += 1
                tool_id = decision["tool_id"]
                params = decision["parameters"]

                logger.info(f"[ReAct_TOOL_CALL] 调用工具 | step={step+1} | tool={tool_id} | count={tool_call_count}")
                logger.debug(f"[ReAct_TOOL_PARAMS] 工具参数 | tool={tool_id} | params={params}")

                result = await self._execute_tool(tool_executor, tool_id, query, user_id, metadata, params)

                if result.get("success"):
                    tool_result = result.get("result", "")
                    context = f"{context}\n\n工具 [{tool_id}] 执行结果:\n{tool_result}"
                    logger.debug(f"[ReAct_TOOL_SUCCESS] 工具执行成功 | tool={tool_id} | result_length={len(str(tool_result))}")
                else:
                    error_msg = result.get("error", "未知错误")
                    context = f"{context}\n\n工具 [{tool_id}] 执行失败: {error_msg}"
                    logger.warning(f"[ReAct_TOOL_FAILED] 工具执行失败 | tool={tool_id} | error={error_msg}")

            elif decision["action"] == "finish":
                answer = decision.get("answer", "")
                if answer:
                    logger.info(f"[ReAct_FINISH] LLM在JSON中直接给出回答 | length={len(answer)}")
                    return answer
                logger.info("[ReAct_FINISH] finish动作但answer为空，继续生成回答")
                break

            elif decision["action"] == "tool_call":
                logger.info(f"[ReAct_STOP] 达到最大工具调用次数 | max={self.max_tool_calls}")
                break
            else:
                logger.info("[ReAct_STOP] LLM判断无需调用工具")
                break

        # 生成最终回答
        logger.debug(f"[ReAct_FINAL_CONTEXT] 最终上下文长度 | length={len(context)}")
        final_response = await self._generate_final_response(query, context)

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        log_event(logger, "react_complete", trace_id=trace_id, user_id=user_id,
                 mode="manual_loop", steps=step + 1, tool_calls=tool_call_count,
                 response_length=len(final_response), elapsed_ms=elapsed_ms)
        logger.info(f"[ReAct_COMPLETE] 手动循环完成 | trace_id={trace_id} | steps={step+1} | tool_calls={tool_call_count} | response_length={len(final_response)}")

        return final_response

    # ========================================================================
    # 工具决策（LangChain JSON → 关键词回退）
    # ========================================================================

    async def _decide_next_action(
        self, query: str, context: str, available_tools: List[str],
        user_id: str, tool_call_count: int, metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """决定下一步：调用工具 或 回答。优先LangChain JSON模式，失败回退关键词。"""
        if self._check_langchain_available():
            llm_decision = await self._decide_with_langchain(query, context, available_tools, user_id)
            if llm_decision is not None:
                return llm_decision
            logger.info("[ReAct_DECISION] LangChain未返回工具调用，回退到关键词匹配")

        tool_id = self._decide_tool_call(query, context, available_tools)
        if tool_id:
            params = self._build_params_for_tool(tool_id, query, user_id, metadata)
            return {"action": "tool_call", "tool_id": tool_id, "parameters": params}
        return {"action": "final_response"}

    async def _decide_with_langchain(
        self, query: str, context: str, available_tools: List[str], user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """LangChain ChatModel + prompts/react_system_prompt.txt → JSON解析"""
        try:
            from src.engine.langchain_tools import (
                load_react_system_prompt, parse_react_response, create_chat_model,
            )
            from langchain_core.messages import HumanMessage, SystemMessage

            chat_model = create_chat_model(temperature=0.0)
            if not chat_model:
                logger.warning("[ReAct_LC] ChatModel创建失败，回退到关键词匹配")
                return None

            system_prompt = load_react_system_prompt(
                max_steps=self.max_thinking_steps, available_tools=available_tools,
            )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"当前上下文：\n{context}\n\n用户最新请求：{query}"),
            ]

            logger.debug(f"[ReAct_LC] 调用LLM | model={settings.MODEL_ROUTER_TYPE} | tools={available_tools}")
            response = await chat_model.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)
            logger.debug(f"[ReAct_LC] LLM响应 | content_preview={content[:200]}")

            decision = parse_react_response(content, available_tools)
            if decision is not None:
                return decision

            if content and len(content.strip()) > 10:
                logger.info("[ReAct_LC] JSON解析失败，将文本回答作为finish处理")
                return {"action": "finish", "answer": content.strip()}

            logger.warning("[ReAct_LC] 无法解析LLM响应，回退到关键词匹配")
            return None

        except ImportError as e:
            logger.info(f"[ReAct_LC] LangChain包不可用: {str(e)}")
            return None
        except Exception as e:
            logger.warning(f"[ReAct_LC] LLM工具选择异常: {str(e)}")
            return None

    # ========================================================================
    # 关键词匹配（第3层回退）
    # ========================================================================

    def _decide_tool_call(self, query: str, context: str, available_tools: List[str]) -> Optional[str]:
        """基于中文关键词匹配决定调用哪个工具（最后回退路径）。"""
        query_lower = query.lower()
        tool_keywords = {
            "feishu_file_read": ["文件", "文档", "读取", "内容"],
            "web_search": ["搜索", "查找", "信息", "新闻", "最新"],
            "memory_search": ["记得", "历史", "之前", "查找"],
            "document_search": ["文档", "资料", "文件"],
            "code_execution": ["运行", "执行", "代码"],
            "vector_migration": ["迁移", "升级"],
        }
        for tool_id, keywords in tool_keywords.items():
            if tool_id in available_tools and any(kw in query_lower for kw in keywords):
                logger.debug(f"[ReAct_KEYWORD] 匹配到工具 | tool={tool_id}")
                return tool_id
        logger.debug("[ReAct_KEYWORD] 未匹配到任何工具")
        return None

    def _build_params_for_tool(
        self, tool_id: str, query: str, user_id: str, metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """关键词回退路径的参数构建"""
        params: Dict[str, Any] = {"user_id": user_id, "query": query}
        if metadata:
            for key in ("file_key", "message_id", "file_name", "limit"):
                if key in metadata:
                    params[key] = metadata[key]
        return params

    # ========================================================================
    # 工具执行
    # ========================================================================

    async def _execute_tool(
        self, tool_executor, tool_id: str, query: str, user_id: str,
        metadata: Optional[Dict[str, Any]], llm_params: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """执行工具调用（异步包装同步执行）"""
        start_time = datetime.now()
        logger.info(f"[TOOL_EXECUTE] 开始执行工具 | tool={tool_id} | user_id={user_id}")

        if llm_params:
            params = dict(llm_params)
            params.setdefault("user_id", user_id)
            if metadata:
                for key in ("message_id", "file_key", "file_name"):
                    if key in metadata and key not in params:
                        params[key] = metadata[key]
        else:
            params = self._build_params_for_tool(tool_id, query, user_id, metadata)

        try:
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: tool_executor.execute(tool_id, params))
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            if result.get("success"):
                logger.info(f"[TOOL_SUCCESS] 工具执行成功 | tool={tool_id} | elapsed={elapsed_ms:.2f}ms")
            else:
                logger.warning(f"[TOOL_FAILED] 工具执行失败 | tool={tool_id} | elapsed={elapsed_ms:.2f}ms | error={result.get('error')}")
            return result
        except Exception as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[TOOL_EXCEPTION] 工具执行异常 | tool={tool_id} | elapsed={elapsed_ms:.2f}ms | error={str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    # ========================================================================
    # 最终回答生成
    # ========================================================================

    async def _call_model_directly(self, query: str) -> str:
        """直接调用模型生成回答（无工具场景）"""
        logger.info("[MODEL_DIRECT] 直接调用模型 | query_length=%d", len(query))
        try:
            response = await call_model(query, settings.MODEL_ROUTER_TYPE)
            if response and response.strip():
                return response
            return "抱歉，当前无法处理您的请求。"
        except Exception as e:
            logger.error(f"[MODEL_DIRECT] 模型调用失败 | error={str(e)}", exc_info=True)
            return "抱歉，当前无法处理您的请求。"

    async def _generate_final_response(self, query: str, context: str) -> str:
        """基于推理上下文生成最终回答"""
        logger.info("[RESPONSE_GENERATE] 生成最终回答 | context_length=%d", len(context))
        try:
            prompt = f"基于以下上下文回答问题：\n\n上下文：{context}\n\n问题：{query}"
            response = await call_model(prompt, settings.MODEL_ROUTER_TYPE)
            if response and response.strip():
                return response
            return "根据分析，我已处理您的请求。"
        except Exception as e:
            logger.error(f"[RESPONSE_GENERATE] 模型调用失败 | error={str(e)}", exc_info=True)
            return "根据分析，我已处理您的请求。"

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def _check_langchain_available(self) -> bool:
        """延迟检测LangChain是否可用"""
        if self._langchain_available is not None:
            return self._langchain_available
        try:
            import langchain_core  # noqa: F401
            self._langchain_available = True
        except ImportError:
            self._langchain_available = False
            logger.info("[ReAct_LC] langchain_core未安装，将使用关键词匹配模式")
        return self._langchain_available

    def _check_langgraph_available(self) -> bool:
        """延迟检测LangGraph是否可用"""
        if self._langgraph_available is not None:
            return self._langgraph_available
        try:
            from langchain.agents import create_agent  # noqa: F401
            from src.engine.checkpointer import get_checkpointer  # noqa: F401
            self._langgraph_available = True
            logger.info("[ReAct_LG] langgraph可用，优先使用 create_agent")
        except ImportError:
            self._langgraph_available = False
            logger.info("[ReAct_LG] langgraph未安装，使用 LangChain JSON模式")
        return self._langgraph_available

    def _build_system_prompt(self, available_tools: List[str]) -> str:
        """构建系统提示词（JSON模式使用）"""
        from src.engine.langchain_tools import load_react_system_prompt
        return load_react_system_prompt(
            max_steps=self.max_thinking_steps,
            available_tools=available_tools,
        )


# 全局实例
react_engine = ReActEngine()
