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
    type: Literal['tool_call', 'finish', 'summarize', 'memory_search', 'document_search', 'tool_executor', 'generate_ppt', 'generate_ppt_from_outline', 'generate_and_send_ppt']
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
        """获取系统提示词（从文件读取）"""
        import os
        
        # 提示词文件路径
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts",
            "react_system_prompt.txt"
        )
        
        # 如果文件存在，从文件读取并渲染模板
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                
                # 使用简单的模板替换
                return template_content.format(
                    format_instructions=self.output_parser.get_format_instructions(),
                    max_steps=self.max_steps
                )
            except Exception as e:
                logger.error(f"Failed to load prompt from file: {e}")
        
        # 如果文件不存在或读取失败，返回默认提示词
        return self._get_default_system_prompt()
    
    def _get_default_system_prompt(self):
        """获取默认系统提示词（作为降级方案）"""
        return f"""你是一个智能助手，使用 ReAct 模式进行推理。
                            
            ## 核心指令
            1. 分析用户问题，决定下一步行动
            2. 如果需要外部信息，调用工具获取
            3. 根据观察结果继续推理或总结回答

            ## 可用工具
            - document_search: 搜索文档知识库（适用于需要查找已入库文档的问题）
            - memory_search: 搜索用户记忆（适用于与用户历史对话相关的问题）
            - tool_executor: 执行工具（适用于需要执行操作的任务，如文件操作、飞书文件读取等）
            - finish: 完成任务并给出最终回答

            ## 工具使用指南
            ### 处理飞书上传的文件
            当用户上传文件时，消息中会包含 file_key、file_name 和 message_id。
            如果需要读取文件内容，请使用 tool_executor 调用 feishu_file_read 工具，参数为：
            {{
                "tool_name": "feishu_file_read",
                "parameters": {{
                    "file_key": "文件的file_key",
                    "user_id": "用户ID",
                    "message_id": "消息ID（用于file_v3格式文件下载）"
                }}
            }}

            ### 搜索文档与读取文件的区别
            - document_search: 用于搜索已经存储在知识库中的文档内容
            - feishu_file_read: 用于读取用户刚上传的飞书文件内容

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

            ### 示例2：读取飞书上传的文件
            ```json
            {{
            "thought": "用户上传了一个文件，我需要先读取文件内容才能分析",
            "action": {{
                "type": "tool_executor",
                "parameters": {{
                    "tool_name": "feishu_file_read",
                    "parameters": {{
                        "file_key": "<从元数据获取的file_key>",
                        "user_id": "<从元数据获取的user_id>",
                        "message_id": "<从元数据获取的message_id>"
                    }}
                }}
            }}
            }}
            ```

            ### 示例3：直接回答问题（使用 finish）
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
            - 用户上传文件时，优先使用 feishu_file_read 工具读取内容，而不是使用 document_search
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
                
                # 判断查询是否看起来像文件名
                import re
                filename_pattern = r'[\u4e00-\u9fa5a-zA-Z0-9_.-]+\.(docx|doc|pdf|txt|md)'
                if re.match(filename_pattern, query):
                    # 如果是文件名，优先尝试按文件名精确搜索
                    results = rag_manager.query_by_filename(query, k=3)
                else:
                    # 否则使用普通的相似性搜索
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
                # 从 parameters 中获取工具名称（LLM可能把工具名放在不同位置）
                tool_id = action.tool_id or params.get("tool_name") or params.get("tool_id")
                
                # 获取工具参数
                # 支持两种格式：
                # 格式1: {"tool_name": "...", "parameters": {...}}
                # 格式2: {"tool_name": "...", "key1": "value1", "key2": "value2"}
                tool_params = params.get("parameters", {})
                
                # 如果没有嵌套的parameters，则直接使用params（去掉tool_name/tool_id）
                if not tool_params:
                    tool_params = {k: v for k, v in params.items() if k not in ["tool_name", "tool_id"]}
                
                # 工具名称映射（处理LLM可能使用的不同名称）
                tool_id_mapping = {
                    "file_reader": "feishu_file_read",
                    "read_file": "feishu_file_read",
                    "feishu_reader": "feishu_file_read"
                }
                if tool_id in tool_id_mapping:
                    tool_id = tool_id_mapping[tool_id]
                
                # 关键修复：当调用 feishu_file_read 工具时，强制使用元数据中的真实参数
                # LLM 可能会生成示例中的占位符（如 om_xxx），需要用真实值覆盖
                if tool_id == "feishu_file_read":
                    # 记录当前元数据状态
                    logger.debug(f"当前元数据: {self.current_metadata}")
                    
                    if self.current_metadata:
                        # 覆盖 file_key
                        if self.current_metadata.get("file_key"):
                            tool_params["file_key"] = self.current_metadata["file_key"]
                        # 覆盖 message_id（最重要：防止 LLM 使用占位符）
                        if self.current_metadata.get("message_id"):
                            tool_params["message_id"] = self.current_metadata["message_id"]
                        # 覆盖 user_id
                        if self.current_metadata.get("user_id"):
                            tool_params["user_id"] = self.current_metadata["user_id"]
                    else:
                        logger.warning("当前元数据为空，无法覆盖工具参数")
                    
                    logger.debug(f"覆盖后的工具参数: {tool_params}")
                
                # 使用插件系统的工具执行器
                executor = get_tool_executor()
                if executor:
                    if tool_id:
                        result = executor.execute(tool_id, tool_params)
                    else:
                        result = {"success": False, "error": "Tool ID is required"}
                else:
                    result = {"success": False, "error": "Tool executor not available"}
                
                # 正确处理工具执行结果
                # 如果工具返回成功，提取实际结果；如果失败，提取错误信息
                action_success = False
                file_content = ""
                if isinstance(result, dict):
                    action_success = result.get("success", False)
                    if action_success:
                        # 提取工具返回的实际结果
                        tool_result = result.get("result", result)
                        # 确保结果是字符串格式
                        if isinstance(tool_result, dict):
                            # 如果是嵌套字典，提取关键信息或转为可读格式
                            content = tool_result.get("content", "")
                            file_content = content  # 保存文件内容用于后续总结
                            if content:
                                observation_result = f"文件读取成功，内容长度: {tool_result.get('content_length', 0)} 字符\n文件内容预览:\n{content[:500]}..."
                            else:
                                observation_result = f"工具执行成功: {str(tool_result)[:500]}"
                        else:
                            observation_result = str(tool_result)
                            file_content = observation_result  # 保存文件内容用于后续总结
                    else:
                        # 工具执行失败，提取错误信息
                        observation_result = f"工具执行失败: {result.get('error', 'Unknown error')}"
                else:
                    observation_result = str(result)
                    file_content = observation_result  # 保存文件内容用于后续总结
                
                # 如果是文件读取工具且成功，自动触发总结
                if action_success and tool_id == "feishu_file_read" and file_content:
                    logger.info(f"文件读取成功，自动触发总结，内容长度: {len(file_content)}")
                    # 使用插件系统的模型路由进行总结
                    model_router = get_model_router()
                    if model_router:
                        model = model_router.select_model("summarization", "simple")
                        if model:
                            prompt = f"""请分析并总结以下文档内容：

{file_content}

请提供：
1. 核心内容总结
2. 关键要点
3. 主要结论或建议
"""
                            summary_result = model_router.call_model(model, [{"role": "user", "content": prompt}])
                            if summary_result and summary_result.strip():
                                # 直接返回总结结果作为观察结果
                                return Observation(
                                    action_id=action_id,
                                    result=f"文件总结完成！\n\n{summary_result}",
                                    success=True
                                )
                
                return Observation(
                    action_id=action_id,
                    result=observation_result,
                    success=action_success
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
            
            elif action.type == "generate_ppt":
                title = params.get("title", "Untitled Presentation")
                slides = params.get("slides", [])
                # 使用工具执行器生成PPT
                executor = get_tool_executor()
                if executor:
                    result = executor.execute("generate_ppt", {"title": title, "slides": slides})
                    success = "successfully" in result.lower()
                else:
                    result = "Tool executor not available"
                    success = False
                return Observation(
                    action_id=action_id,
                    result=str(result),
                    success=success
                )
            
            elif action.type == "generate_ppt_from_outline":
                title = params.get("title", "Untitled Presentation")
                outline = params.get("outline", [])
                # 使用工具执行器从大纲生成PPT
                executor = get_tool_executor()
                if executor:
                    result = executor.execute("generate_ppt_from_outline", {"title": title, "outline": outline})
                    success = "successfully" in result.lower()
                else:
                    result = "Tool executor not available"
                    success = False
                return Observation(
                    action_id=action_id,
                    result=str(result),
                    success=success
                )
            
            elif action.type == "generate_and_send_ppt":
                title = params.get("title", "Untitled Presentation")
                slides = params.get("slides", [])
                user_id = params.get("user_id", "")
                im_type = params.get("im_type", "feishu")
                # 使用工具执行器生成并发送PPT
                executor = get_tool_executor()
                if executor:
                    result = executor.execute("generate_and_send_ppt", {
                        "title": title,
                        "slides": slides,
                        "user_id": user_id,
                        "im_type": im_type
                    })
                    success = "sent successfully" in result.lower() or "generated and sent" in result.lower()
                else:
                    result = "Tool executor not available"
                    success = False
                return Observation(
                    action_id=action_id,
                    result=str(result),
                    success=success
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
        elif "not available" in error_message.lower() or "不可用" in error_message or "未初始化" in error_message or "not initialized" in error_message.lower():
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
        
        # 策略2：简化参数（移除可选参数）
        simplified_params = {k: v for k, v in params.items() if v is not None}
        if simplified_params != params:
            logger.info(f"Simplifying parameters for action: {action_type}")
            return Action(
                type=action_type,
                parameters=simplified_params if simplified_params else None
            )
        
        # 策略3：重新生成参数（针对参数错误，作为最后手段）
        if "参数" in analysis.failure_reason or "parameter" in analysis.failure_reason.lower():
            logger.info(f"Regenerating parameters for action: {action_type}")
            regenerated_action = self._regenerate_parameters(original_action, state)
            if regenerated_action:
                return regenerated_action
        
        # 如果没有可简化的参数且无法重新生成，返回原始动作（会再次失败，但至少不会崩溃）
        return Action(
            type=action_type,
            parameters=params if params else None
        )
    
    def _parse_output_with_fallback(self, content: str) -> ReActOutput:
        """
        解析 LLM 输出，支持多种格式，处理 JSON 解析失败的情况
        
        Args:
            content: LLM 返回的内容
            
        Returns:
            ReActOutput: 解析后的输出对象
        """
        import json
        import re
        
        # 首先尝试使用标准解析器
        try:
            output = self.output_parser.parse(content)
            logger.debug(f"Successfully parsed with PydanticOutputParser")
            return output
        except Exception as e:
            logger.warning(f"PydanticOutputParser failed: {e}")
        
        # 尝试从内容中提取 JSON（处理可能包含额外文本的情况）
        try:
            # 尝试找到 JSON 对象
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    data = json.loads(json_str)
                    return self._build_output_from_data(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed after extraction: {e}")
        except Exception as e:
            logger.warning(f"Failed to extract JSON: {e}")
        
        # 尝试处理 markdown 代码块格式
        try:
            # 移除代码块标记
            cleaned_content = re.sub(r'```(json)?\s*', '', content.strip())
            cleaned_content = re.sub(r'\s*```', '', cleaned_content)
            data = json.loads(cleaned_content)
            return self._build_output_from_data(data)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse cleaned content: {e}")
        
        # 如果所有解析都失败，尝试简单的规则匹配
        try:
            return self._parse_with_simple_rules(content)
        except Exception as e:
            logger.error(f"All parsing methods failed: {e}")
        
        # 最终降级：返回一个默认的 finish 动作
        logger.warning(f"Using fallback output for content: {content[:100]}...")
        return ReActOutput(
            thought="未能正确解析输出格式，将直接总结回答",
            action=Action(
                type="finish",
                parameters={"answer": f"根据分析，我来为您总结：{content[:500]}"}
            )
        )
    
    def _build_output_from_data(self, data: dict) -> ReActOutput:
        """
        从字典数据构建 ReActOutput 对象
        
        Args:
            data: 解析后的字典数据
            
        Returns:
            ReActOutput: 输出对象
        """
        thought = data.get("thought", "")
        action_data = data.get("action", {})
        
        # 处理嵌套的 action
        if isinstance(action_data, dict):
            action_type = action_data.get("type", "finish")
            parameters = action_data.get("parameters", None)
            
            # 确保 parameters 是字典或 None
            if parameters is not None and not isinstance(parameters, dict):
                parameters = None
            
            action = Action(
                type=action_type,
                parameters=parameters
            )
        else:
            # 如果 action 不是字典，使用默认动作
            action = Action(
                type="finish",
                parameters={"answer": thought}
            )
        
        return ReActOutput(
            thought=thought,
            action=action
        )
    
    def _parse_with_simple_rules(self, content: str) -> ReActOutput:
        """
        使用简单规则解析输出（作为最后的降级方案）
        
        Args:
            content: LLM 返回的内容
            
        Returns:
            ReActOutput: 解析后的输出对象
        """
        # 检查是否包含特定关键词来决定动作类型
        content_lower = content.lower()
        
        # 检查是否需要搜索文档
        if any(keyword in content_lower for keyword in ["搜索文档", "document_search", "查找文档", "知识库"]):
            return ReActOutput(
                thought="分析问题需要搜索文档知识库",
                action=Action(
                    type="document_search",
                    parameters={"query": content[:200]}
                )
            )
        
        # 检查是否需要读取文件（优先检查元数据中是否有 file_key）
        has_file_upload = self.current_metadata and self.current_metadata.get("file_key")
        file_keyword_detected = any(keyword in content_lower for keyword in ["读取文件", "file_read", "feishu_file_read", "上传文件", "生成ppt", "制作ppt", "创建ppt", "生成演示稿", "制作演示稿"])
        
        if has_file_upload:
            # 只有在元数据中存在真实的 file_key 时才调用文件读取工具
            tool_params = {"tool_name": "feishu_file_read"}
            if self.current_metadata:
                file_key = self.current_metadata.get("file_key")
                message_id = self.current_metadata.get("message_id")
                user_id = self.current_metadata.get("user_id")
                if file_key:
                    tool_params["parameters"] = {"file_key": file_key}
                    if message_id:
                        tool_params["parameters"]["message_id"] = message_id
                    if user_id:
                        tool_params["parameters"]["user_id"] = user_id
            return ReActOutput(
                thought="用户上传了文件，需要读取文件内容",
                action=Action(
                    type="tool_executor",
                    parameters=tool_params
                )
            )
        elif file_keyword_detected:
            # 用户提到了文件相关关键词但没有上传文件，尝试从知识库中搜索
            import re
            
            # 首先检查是否使用指代性词汇（如"这个文件"、"刚才的文件"等）
            reference_keywords = ["这个文件", "刚才的文件", "刚刚的文件", "那份文件", "该文件", "此文件"]
            is_reference = any(keyword in content for keyword in reference_keywords)
            
            if is_reference:
                # 用户使用指代性词汇，尝试获取最近上传的文件
                return ReActOutput(
                    thought="用户提到了'这个文件'，尝试从知识库中获取最近上传的文件内容",
                    action=Action(
                        type="document_search",
                        parameters={"query": "__recent_upload__"}
                    )
                )
            
            # 提取文件名（假设文件名包含在用户消息中）
            filename_pattern = r'([\u4e00-\u9fa5a-zA-Z0-9_.-]+\.(docx|doc|pdf|txt|md))'
            match = re.search(filename_pattern, content)
            if match:
                filename = match.group(1)
                return ReActOutput(
                    thought="用户提到了文件操作但未上传文件，尝试从知识库中搜索文件内容",
                    action=Action(
                        type="document_search",
                        parameters={"query": filename}
                    )
                )
            else:
                # 用户提到了文件相关关键词但没有上传文件，提示用户上传
                return ReActOutput(
                    thought="用户提到了文件相关操作但未上传文件，需要提示用户上传文件",
                    action=Action(
                        type="finish",
                        parameters={"answer": "请您先上传需要处理的文件，然后我可以帮您读取文件内容或生成PPT。"}
                    )
                )
        
        # 检查是否需要总结
        if any(keyword in content_lower for keyword in ["总结", "summarize", "摘要"]):
            return ReActOutput(
                thought="需要总结内容",
                action=Action(
                    type="summarize",
                    parameters={"query": content[:200]}
                )
            )
        
        # 默认：尝试直接回答
        return ReActOutput(
            thought="尝试直接回答用户问题",
            action=Action(
                type="finish",
                parameters={"answer": content[:500]}
            )
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
    
    def run(self, user_id: str, user_query: str, max_steps: int = 5, metadata: Optional[Dict[str, Any]] = None) -> str:
        """运行 ReAct 推理循环"""
        logger.info(f"Starting ReAct loop for user {user_id}: {user_query}")
        
        # 设置当前用户ID（供 _execute_action 使用）
        self.current_user_id = user_id
        
        # 存储消息元数据
        self.current_metadata = metadata or {}
        
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
                
                # 从元数据中提取文件相关信息
                file_context = ""
                if self.current_metadata:
                    file_key = self.current_metadata.get("file_key")
                    file_name = self.current_metadata.get("file_name")
                    msg_id = self.current_metadata.get("message_id")
                    if file_key or file_name:
                        file_context = f"\n\n## 文件信息"
                        if file_name:
                            file_context += f"\n文件名: {file_name}"
                        if file_key:
                            file_context += f"\n文件标识: {file_key}"
                        if msg_id:
                            file_context += f"\n消息ID: {msg_id}"
                
                prompt = f"""{self.system_prompt}

## 当前问题
{user_query}

## 历史记录
{history}{file_context}

## 下一步思考和动作
"""
                
                # 首先尝试使用简单规则匹配（基于用户查询）
                rule_based_output = self._parse_with_simple_rules(user_query)
                
                # 如果规则匹配成功（不是默认的finish动作），使用规则匹配结果
                if rule_based_output and rule_based_output.action and rule_based_output.action.type != "finish":
                    logger.debug(f"Using rule-based output: {rule_based_output.action.type}")
                    output = rule_based_output
                else:
                    # 否则调用 LLM 获取思考和动作
                    messages = [
                        SystemMessage(content=self.system_prompt),
                        HumanMessage(content=f"问题: {user_query}\n\n历史: {history}\n\n请输出下一步的思考和动作")
                    ]
                    
                    response = self.llm.invoke(messages)
                    logger.debug(f"LLM response content: {response.content[:500]}")
                    
                    # 尝试解析输出，处理可能的 JSON 解析失败
                    output = self._parse_output_with_fallback(response.content)
                
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