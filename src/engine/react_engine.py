from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from src.config import settings
from src.utils import setup_logging, generate_id, get_timestamp
from src.data.vector_store import rag_manager
from src.plugins import get_tool_executor, get_model_router

logger = setup_logging(settings.LOG_LEVEL)


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
    thought: str


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
```json
{{
  "thought": "我需要搜索文档来回答这个问题",
  "action": {{
    "type": "document_search",
    "parameters": {{"query": "用户的问题"}}
  }}
}}
```

## 注意事项
- 如果问题可以直接回答，使用 finish 动作给出最终答案
- 如果需要更多信息，使用适当的工具获取
- 每次只能执行一个动作
- 最多执行 {self.max_steps} 步
"""
    
    def _format_history(self, state: ReActState) -> str:
        """格式化历史记录"""
        history = []
        for i, (thought, action, observation) in enumerate(zip(
            state.thoughts, state.actions, state.observations
        )):
            history.append(f"步骤 {i+1}:")
            history.append(f"  思考: {thought.content}")
            history.append(f"  动作: {action.type}")
            if action.tool_id:
                history.append(f"    工具: {action.tool_id}")
            if action.parameters:
                history.append(f"    参数: {action.parameters}")
            history.append(f"  观察: {observation.result}")
        return "\n".join(history)
    
    def _execute_action(self, action: Action) -> Observation:
        """执行动作"""
        action_id = generate_id()
        try:
            if action.type == "document_search":
                query = action.parameters.get("query", "")
                results = rag_manager.query(query, k=3)
                context = "\n\n".join([r.get("content", "") for r in results])
                return Observation(
                    action_id=action_id,
                    result=context,
                    success=True
                )
            
            elif action.type == "memory_search":
                query = action.parameters.get("query", "")
                # 使用插件系统的记忆存储
                from src.plugins import get_memory_store
                memory_store = get_memory_store()
                if memory_store:
                    results = memory_store.search_memory(state.user_id, query, limit=3)
                    context = "\n\n".join([str(r) for r in results])
                else:
                    context = "Memory store not available"
                return Observation(
                    action_id=action_id,
                    result=context,
                    success=True
                )
            
            elif action.type == "tool_executor":
                tool_id = action.tool_id
                params = action.parameters or {}
                # 使用插件系统的工具执行器
                executor = get_tool_executor()
                if executor:
                    result = executor.execute(tool_id, params)
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
                    result=action.parameters.get("answer", ""),
                    success=True
                )
            
            elif action.type == "summarize":
                query = action.parameters.get("query", "")
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
            return Observation(
                action_id=action_id,
                result="",
                success=False,
                error=str(e)
            )
    
    def _is_completed(self, action: Action, state: ReActState) -> bool:
        """检查是否完成"""
        return action.type == "finish" or state.current_step >= state.max_steps
    
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
                output = self.output_parser.parse(response.content)
                
                # 记录思考
                thought = Thought(
                    id=generate_id(),
                    content=output.thought,
                    timestamp=get_timestamp()
                )
                state.thoughts.append(thought)
                
                # 记录动作
                state.actions.append(output.action)
                
                # 执行动作
                observation = self._execute_action(output.action)
                state.observations.append(observation)
                
                # 更新步骤计数
                state.current_step += 1
                
                # 检查是否完成
                if self._is_completed(output.action, state):
                    state.is_completed = True
                    if output.action.type == "finish":
                        state.final_response = output.action.parameters.get("answer", "")
                    else:
                        state.final_response = self._generate_final_response(state)
                
                logger.info(f"ReAct step {state.current_step}: {output.action.type}")
                
            except Exception as e:
                logger.error(f"ReAct loop error: {e}")
                state.is_completed = True
                state.final_response = f"处理过程中发生错误: {str(e)}"
        
        # 如果未完成，强制生成总结
        if not state.final_response:
            state.final_response = self._generate_final_response(state)
        
        logger.info(f"ReAct completed: {state.final_response[:50]}...")
        return state.final_response


# 全局实例
react_engine = ReActEngine()