from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from src.config import settings
from src.utils import generate_id, get_timestamp
from src.data.vector_store import rag_manager
from src.plugins import get_tool_executor, get_model_router
from src.logging_config import get_logger

logger = get_logger("engine")


class Thought(BaseModel):
    """思考步骤"""
    id: str
    content: str
    timestamp: int
    is_final: bool = False


class Action(BaseModel):
    """动作"""
    type: Literal['tool_call', 'finish', 'summarize', 'memory_search', 'document_search']
    tool_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class Observation(BaseModel):
    """观察结果"""
    action_id: str
    result: str
    success: bool
    error: Optional[str] = None


class ReActState(BaseModel):
    """ReAct 状态"""
    user_id: str
    user_query: str
    thoughts: List[Thought] = []
    actions: List[Action] = []
    observations: List[Observation] = []
    max_steps: int = 5
    current_step: int = 0
    is_completed: bool = False
    final_response: Optional[str] = None
    recovery_attempts: int = 0  # 恢复尝试次数
    max_recovery_attempts: int = 2  # 最大恢复尝试次数


class RecoveryAnalysis(BaseModel):
    """恢复分析结果"""
    failure_reason: str
    suggested_fix: str
    fixed_action: Optional[Action] = None
    can_recover: bool = False


class ReActOutput(BaseModel):
    """ReAct 输出格式"""
    thought: str
    action: Action


class ReActEngine:
    """ReAct 推理引擎"""
    
    def __init__(self):
        self.max_steps = 5  # 最大推理步骤
        self.llm = self._init_llm()
        self.output_parser = PydanticOutputParser(pydantic_object=ReActOutput)
        self.system_prompt = self._get_system_prompt()
        self.current_user_id = None  # 当前用户ID
        
        # 备用工具映射（当主工具失败时使用）
        self.backup_tools = {
            "document_search": ["memory_search"],
            "memory_search": ["document_search"],
            "tool_executor": []
        }
    
    def _init_llm(self):
        """初始化语言模型（优先使用插件系统）"""
        try:
            # 尝试使用插件系统的模型路由
            model_router = get_model_router()
            if model_router:
                return model_router.select_model("react", "complex")
            
            # 降级到传统配置
            if settings.OLLAMA_HOST:
                return ChatOllama(
                    model="qwen3.5:9b",
                    base_url=settings.OLLAMA_HOST,
                    temperature=0.7
                )
            elif settings.OPENAI_API_KEY:
                return ChatOpenAI(
                    model="gpt-4o",
                    api_key=settings.OPENAI_API_KEY,
                    temperature=0.7
                )
            else:
                logger.warning("No LLM configured, using default")
                return ChatOllama(model="qwen3.5:9b")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise
    
    def _get_system_prompt(self):
        """获取系统提示词"""
        return f"""你是一个智能助手，使用 ReAct 模式进行推理。
        
## 核心指令
1. 分析用户问题，决定下一步行动
2. 如果需要外部信息，调用工具获取
3. 根据观察结果继续推理或总结回答

## 可用工具
- document_search: 搜索文档知识库（适用于需要查找特定信息的问题）
- memory_search: 搜索用户记忆（适用于与用户历史对话相关的问题）
- tool_executor: 执行工具（适用于需要执行操作的任务）
- finish: 完成任务并给出最终回答

## 输出格式要求
{self.output_parser.get_format_instructions()}

## 格式示例
### 示例1：需要搜索文档
```json
{{
  "thought": "我需要搜索文档来回答这个问题",
  "action": {{
    "type": "document_search",
    "parameters": {{"query": "用户的问题"}}
  }}
}}
```

### 示例2：直接回答问题（使用 finish）
```json
{{
  "thought": "用户问我是谁，这是一个可以直接回答的问题，不需要调用工具",
  "action": {{
    "type": "finish",
    "parameters": {{"answer": "我是 Hermes Office Synergy Agent，一个智能办公助手，能够帮助你处理各种办公任务。"}}
  }}
}}
```

## 注意事项
- 如果问题可以直接回答，使用 finish 动作，并在 parameters 的 answer 字段中提供具体回答
- 如果需要更多信息，使用适当的工具获取
- 每次只能执行一个动作
- 最多执行 {self.max_steps} 步
- finish 动作必须在 parameters 中包含 answer 字段，否则无法正确回答用户
"""
    
    def _format_history(self, state: ReActState) -> str:
        """格式化历史记录"""
        history = []
        for i, (thought, action, observation) in enumerate(zip(
            state.thoughts, state.actions, state.observations
        )):
            history.append(f"步骤 {i+1}:")
            history.append(f"  思考: {thought.content}")
            if action is not None:
                history.append(f"  动作: {action.type}")
                if action.tool_id:
                    history.append(f"    工具: {action.tool_id}")
                if action.parameters:
                    history.append(f"    参数: {action.parameters}")
            else:
                history.append(f"  动作: None")
            history.append(f"  观察: {observation.result}")
        return "\n".join(history)
    
    def _execute_action(self, action: Action) -> Observation:
        """执行动作"""
        action_id = generate_id()
        try:
            # 记录进入方法和 action 的详细信息
            logger.debug(f"_execute_action called - action_id={action_id}, action={action}")
            logger.debug(f"action type: {type(action).__name__}")
            if action is not None:
                logger.debug(f"action.__dict__: {action.__dict__}")
            
            # 检查 action 是否为 None
            if action is None:
                logger.error(f"Action is None - action_id={action_id}")
                return Observation(
                    action_id=action_id,
                    result="",
                    success=False,
                    error="Action is None"
                )
            
            # 检查 action.type 是否存在
            if not hasattr(action, 'type') or action.type is None:
                logger.error(f"Action type is None - action_id={action_id}, action={action}")
                return Observation(
                    action_id=action_id,
                    result="",
                    success=False,
                    error="Action type is None"
                )
            
            logger.debug(f"Action type: {action.type}")
            
            # 确保 parameters 不是 None
            params = action.parameters or {}
            logger.debug(f"Action parameters: {params}")
            
            if action.type == "document_search":
                query = params.get("query", "")
                # 检查 rag_manager 是否为 None
                if rag_manager is None:
                    return Observation(
                        action_id=action_id,
                        result="",
                        success=False,
                        error="RAG manager is not initialized"
                    )
                results = rag_manager.query(query, k=3)
                # 检查 results 是否为 None
                if results is None:
                    results = []
                # 过滤掉 None 元素并获取内容
                context = "\n\n".join([r.get("content", "") for r in results if r is not None])
                return Observation(
                    action_id=action_id,
                    result=context,
                    success=True
                )
            
            elif action.type == "memory_search":
                query = params.get("query", "")
                # 使用插件系统的记忆存储
                from src.plugins import get_memory_store
                memory_store = get_memory_store()
                if memory_store:
                    results = memory_store.search_memory(self.current_user_id, query, limit=3)
                    # 检查 results 是否为 None
                    if results is None:
                        results = []
                    # 过滤掉 None 元素
                    context = "\n\n".join([str(r) for r in results if r is not None])
                else:
                    context = "Memory store not available"
                return Observation(
                    action_id=action_id,
                    result=context,
                    success=True
                )
            
            elif action.type == "tool_executor":
                tool_id = action.tool_id
                tool_params = params or {}
                # 使用插件系统的工具执行器
                executor = get_tool_executor()
                if executor:
                    result = executor.execute(tool_id, tool_params)
                else:
                    result = {"success": False, "error": "Tool executor not available"}
                return Observation(
                    action_id=action_id,
                    result=str(result),
                    success=True
                )
            
            elif action.type == "finish":
                return Observation(
                    action_id=action_id,
                    result=params.get("answer", ""),
                    success=True
                )
            
            elif action.type == "summarize":
                query = params.get("query", "")
                # 使用插件系统的模型路由
                model_router = get_model_router()
                if model_router:
                    model = model_router.select_model("summarization", "simple")
                    if model:
                        prompt = f"总结以下内容：\n{query}"
                        result = model_router.call_model(model, [{"role": "user", "content": prompt}])
                        return Observation(
                            action_id=action_id,
                            result=result,
                            success=True
                        )
                return Observation(
                    action_id=action_id,
                    result="总结功能暂时不可用",
                    success=False,
                    error="No model available"
                )
            
            else:
                return Observation(
                    action_id=action_id,
                    result=f"未知动作类型: {action.type}",
                    success=False,
                    error="Unknown action type"
                )
        
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            logger.error(f"Action at failure: {action}")
            logger.error(f"Action type at failure: {action.type if action else None}")
            logger.error(f"Action parameters at failure: {action.parameters if action else None}")
            import traceback
            logger.error(f"Stack trace:\n{traceback.format_exc()}")
            return Observation(
                action_id=action_id,
                result="",
                success=False,
                error=str(e)
            )
    
    def _is_completed(self, action: Action, state: ReActState) -> bool:
        """检查是否完成"""
        if action is None or action.type is None:
            return state.current_step >= state.max_steps
        return action.type == "finish" or state.current_step >= state.max_steps
    
    def _analyze_failure(self, action: Action, observation: Observation) -> RecoveryAnalysis:
        """
        分析工具调用失败原因
        
        Args:
            action: 失败的动作
            observation: 观察结果（包含错误信息）
        
        Returns:
            RecoveryAnalysis: 恢复分析结果
        """
        error_message = observation.error or "Unknown error"
        action_type = action.type if action else "unknown"
        
        logger.debug(f"Analyzing failure: action_type={action_type}, error={error_message}")
        
        # 识别失败原因
        failure_reason = "未知错误"
        suggested_fix = ""
        can_recover = False
        fixed_action = None
        
        # 参数错误
        if "parameter" in error_message.lower() or "参数" in error_message:
            failure_reason = "参数错误"
            suggested_fix = "需要重新生成正确的参数"
            can_recover = True
            
        # 工具不可用
        elif "not available" in error_message.lower() or "不可用" in error_message or "未初始化" in error_message:
            failure_reason = "工具不可用"
            suggested_fix = "尝试使用备用工具或跳过此步骤"
            can_recover = True
            
        # 连接错误
        elif "connection" in error_message.lower() or "连接" in error_message:
            failure_reason = "连接失败"
            suggested_fix = "尝试重新连接或使用备用工具"
            can_recover = True
            
        # 超时错误
        elif "timeout" in error_message.lower() or "超时" in error_message:
            failure_reason = "操作超时"
            suggested_fix = "重试操作或使用备用工具"
            can_recover = True
            
        # 权限错误
        elif "permission" in error_message.lower() or "权限" in error_message:
            failure_reason = "权限不足"
            suggested_fix = "检查权限或使用其他方法"
            can_recover = False
            
        # 资源不存在
        elif "not found" in error_message.lower() or "不存在" in error_message:
            failure_reason = "资源不存在"
            suggested_fix = "检查资源路径或使用其他资源"
            can_recover = True
            
        # 格式错误
        elif "format" in error_message.lower() or "格式" in error_message:
            failure_reason = "格式错误"
            suggested_fix = "修正数据格式后重试"
            can_recover = True
            
        logger.info(f"Failure analysis: reason={failure_reason}, fix={suggested_fix}, can_recover={can_recover}")
        
        return RecoveryAnalysis(
            failure_reason=failure_reason,
            suggested_fix=suggested_fix,
            fixed_action=fixed_action,
            can_recover=can_recover
        )
    
    def _reflect_and_recover(self, action: Action, observation: Observation, state: ReActState) -> Optional[Action]:
        """
        反思并尝试恢复
        
        Args:
            action: 失败的动作
            observation: 观察结果
            state: 当前状态
            
        Returns:
            Optional[Action]: 修复后的动作，如果无法修复则返回 None
        """
        if state.recovery_attempts >= state.max_recovery_attempts:
            logger.info(f"Max recovery attempts ({state.max_recovery_attempts}) reached, skipping recovery")
            return None
            
        analysis = self._analyze_failure(action, observation)
        
        if not analysis.can_recover:
            logger.info(f"Cannot recover from failure: {analysis.failure_reason}")
            return None
            
        # 尝试修复
        try:
            fixed_action = self._generate_fixed_action(action, analysis, state)
            if fixed_action:
                state.recovery_attempts += 1
                logger.info(f"Generated fixed action: {fixed_action.type}")
                return fixed_action
        except Exception as e:
            logger.error(f"Failed to generate fixed action: {e}")
            
        return None
    
    def _generate_fixed_action(self, original_action: Action, analysis: RecoveryAnalysis, state: ReActState) -> Optional[Action]:
        """
        根据分析结果生成修复后的动作
        
        Args:
            original_action: 原始失败的动作
            analysis: 恢复分析结果
            state: 当前状态
            
        Returns:
            Optional[Action]: 修复后的动作
        """
        action_type = original_action.type
        params = original_action.parameters or {}
        
        # 策略1：尝试切换备用工具
        if action_type in self.backup_tools and self.backup_tools[action_type]:
            for backup_type in self.backup_tools[action_type]:
                logger.info(f"Trying backup tool: {backup_type} instead of {action_type}")
                return Action(
                    type=backup_type,
                    parameters=params
                )
        
        # 策略2：重新生成参数（针对参数错误）
        if "参数" in analysis.failure_reason or "parameter" in analysis.failure_reason.lower():
            logger.info(f"Regenerating parameters for action: {action_type}")
            return self._regenerate_parameters(original_action, state)
        
        # 策略3：简化参数（移除可选参数）
        logger.info(f"Simplifying parameters for action: {action_type}")
        simplified_params = {k: v for k, v in params.items() if v is not None}
        return Action(
            type=action_type,
            parameters=simplified_params if simplified_params else None
        )
    
    def _regenerate_parameters(self, action: Action, state: ReActState) -> Optional[Action]:
        """
        重新生成参数
        
        Args:
            action: 原始动作
            state: 当前状态
            
        Returns:
            Optional[Action]: 修复后的动作
        """
        # 获取历史上下文
        history_text = "\n".join([t.content for t in state.thoughts[-3:]]) if state.thoughts else ""
        
        prompt = f"""
        以下动作执行失败，需要重新生成参数：
        
        动作类型: {action.type}
        原始参数: {action.parameters}
        错误原因: 参数错误
        
        上下文: {history_text}
        用户问题: {state.user_query}
        
        请分析并生成正确的参数。只返回 JSON 格式的参数对象，不要包含其他内容。
        
        例如:
        {{
            "key1": "value1",
            "key2": "value2"
        }}
        """
        
        try:
            response = self.llm.invoke([
                SystemMessage(content="你是一个参数修复专家，根据上下文生成正确的参数。"),
                HumanMessage(content=prompt)
            ])
            
            import json
            new_params = json.loads(response.content)
            
            return Action(
                type=action.type,
                parameters=new_params
            )
        except Exception as e:
            logger.error(f"Failed to regenerate parameters: {e}")
            return None
    
    def _generate_final_response(self, state: ReActState) -> str:
        """生成最终响应"""
        # 获取最后一个成功的观察结果
        for obs in reversed(state.observations):
            if obs.success and obs.result:
                return obs.result
        
        # 如果没有观察结果，直接总结思考过程
        thoughts_text = "\n".join([t.content for t in state.thoughts])
        return f"基于分析，我的回答是：{thoughts_text}"
    
    def run(self, user_id: str, user_query: str, max_steps: int = 5) -> str:
        """运行 ReAct 推理循环"""
        logger.info(f"Starting ReAct loop for user {user_id}: {user_query}")
        
        # 设置当前用户ID（供 _execute_action 使用）
        self.current_user_id = user_id
        
        # 初始化状态
        state = ReActState(
            user_id=user_id,
            user_query=user_query,
            max_steps=max_steps
        )
        
        # ReAct 循环
        while not state.is_completed and state.current_step < max_steps:
            try:
                # 构建提示词
                history = self._format_history(state)
                prompt = f"""{self.system_prompt}

## 当前问题
{user_query}

## 历史记录
{history}

## 下一步思考和动作
"""
                
                # 调用 LLM 获取思考和动作
                messages = [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=f"问题: {user_query}\n\n历史: {history}\n\n请输出下一步的思考和动作")
                ]
                
                response = self.llm.invoke(messages)
                logger.debug(f"LLM response content: {response.content[:500]}")
                
                output = self.output_parser.parse(response.content)
                logger.debug(f"Parsed output type: {type(output).__name__}")
                logger.debug(f"Parsed output: {output}")
                
                # 记录思考
                thought = Thought(
                    id=generate_id(),
                    content=output.thought,
                    timestamp=get_timestamp()
                )
                state.thoughts.append(thought)
                logger.debug(f"Added thought: {output.thought[:50]}...")
                
                # 记录动作
                logger.debug(f"Action to append: {output.action}")
                logger.debug(f"Action type: {type(output.action).__name__}")
                if output.action is not None:
                    logger.debug(f"Action attributes: {output.action.__dict__}")
                
                state.actions.append(output.action)
                
                # 执行动作
                logger.debug(f"Calling _execute_action with action: {output.action}")
                observation = self._execute_action(output.action)
                logger.debug(f"Observation result: success={observation.success}, error={observation.error}")
                state.observations.append(observation)
                
                # 反思环节：如果动作失败，尝试恢复
                if not observation.success and output.action is not None:
                    logger.info(f"Action failed, attempting recovery...")
                    fixed_action = self._reflect_and_recover(output.action, observation, state)
                    if fixed_action:
                        # 添加反思思考
                        reflect_thought = Thought(
                            id=generate_id(),
                            content=f"反思：工具调用失败，原因是{observation.error}。尝试修复：切换到{fixed_action.type}",
                            timestamp=get_timestamp()
                        )
                        state.thoughts.append(reflect_thought)
                        logger.info(f"Reflecting on failure and trying fixed action: {fixed_action.type}")
                        
                        # 执行修复后的动作
                        fixed_observation = self._execute_action(fixed_action)
                        state.observations.append(fixed_observation)
                        state.actions.append(fixed_action)
                        logger.info(f"Fixed action result: success={fixed_observation.success}")
                
                # 更新步骤计数
                state.current_step += 1
                
                # 检查是否完成
                if self._is_completed(output.action, state):
                    state.is_completed = True
                    if output.action is not None and output.action.type == "finish":
                        action_params = output.action.parameters or {}
                        answer = action_params.get("answer", "")
                        logger.debug(f"finish action parameters: {action_params}")
                        logger.debug(f"finish action answer: '{answer}'")
                        # 如果有具体回答，使用该回答
                        if answer and answer.strip():
                            state.final_response = answer
                        elif state.thoughts:
                            # 如果没有回答但有思考，基于思考生成回答
                            last_thought = state.thoughts[-1].content
                            # 调用 LLM 基于思考生成最终回答
                            messages = [
                                SystemMessage(content="你是一个智能助手，需要根据思考内容给出直接、友好、完整的回答。不要分析问题，不要说'我可以直接回答'之类的话，直接给出答案。"),
                                HumanMessage(content=f"请根据以下思考直接给出最终答案：{last_thought}")
                            ]
                            try:
                                response = self.llm.invoke(messages)
                                state.final_response = response.content.strip() or last_thought
                            except Exception as e:
                                logger.error(f"Failed to generate final response: {e}")
                                state.final_response = last_thought
                        else:
                            state.final_response = "已完成任务"
                    else:
                        state.final_response = self._generate_final_response(state)
                
                # 安全地记录动作类型
                action_type = output.action.type if (output.action is not None and output.action.type) else "unknown"
                logger.info(f"ReAct step {state.current_step}: {action_type}")
                
            except Exception as e:
                logger.error(f"ReAct loop error: {e}")
                logger.error(f"Error type: {type(e).__name__}")
                import traceback
                logger.error(f"Stack trace:\n{traceback.format_exc()}")
                logger.error(f"Current state: user_id={user_id}, step={state.current_step}, observations={len(state.observations)}")
                if 'output' in locals():
                    logger.error(f"Output at failure: {output}")
                    if hasattr(output, 'action'):
                        logger.error(f"Output action at failure: {output.action}")
                state.is_completed = True
                state.final_response = f"处理过程中发生错误: {str(e)}"
        
        # 如果未完成，强制生成总结
        if not state.final_response:
            state.final_response = self._generate_final_response(state)
        
        logger.info(f"ReAct completed: {state.final_response[:50]}...")
        return state.final_response


# 全局实例
react_engine = ReActEngine()