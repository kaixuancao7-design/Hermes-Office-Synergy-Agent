"""LangChain工具包装层 — 将现有tool_executor包装为LangChain StructuredTool

本模块提供三个核心功能：
1. 将项目中已有的工具包装为LangChain BaseTool（用于bind_tools模式）
2. 加载并格式化 prompts/react_system_prompt.txt 提示词模板
3. 基于项目settings创建对应LangChain ChatModel实例的工厂函数

两种工具选择模式：
  - JSON模式（默认）：使用提示词文件中的 ReAct JSON 格式，兼容所有模型
  - bind_tools模式：使用ChatModel.bind_tools()原生function calling，仅限支持的模型
"""

import os
import json
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from src.config import settings
from src.logging_config import get_logger

logger = get_logger("engine")

# 提示词文件路径
_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")


# ============================================================================
# Pydantic 参数模式 —— 定义每个工具的输入结构
# LLM 会读取这些 schema 的 description 来决定传什么参数
# ============================================================================

# Compatibility re-exports: callers may keep importing these names here.
from src.tools.schemas import (
    DocumentSearchInput, MemorySearchInput, WebSearchInput, CodeExecutionInput,
    FileOperationsInput, FeishuFileReadInput,
)


# ============================================================================
# 工具包装函数 —— 将LangChain工具调用转换为 tool_executor.execute() 调用
# ============================================================================

def _get_executor():
    """延迟获取tool_executor，避免循环导入"""
    from src.plugins import get_tool_executor
    return get_tool_executor()


def _execute_document_search(query: str, limit: int = 5) -> str:
    """执行文档搜索"""
    return _execute_as_json("document_search", locals())


def _execute_memory_search(query: str, limit: int = 5) -> str:
    """执行记忆搜索"""
    return _execute_as_json("memory_search", locals())


def _execute_web_search(query: str) -> str:
    """执行网页搜索"""
    return _execute_as_json("web_search", locals())


def _execute_code(code: str, language: str = "python") -> str:
    """执行代码"""
    return _execute_as_json("code_execution", locals())


def _execute_file_operations(operation: str, path: str, content: str = "") -> str:
    """执行文件操作"""
    return _execute_as_json("file_operations", locals())


def _execute_feishu_file_read(file_key: str, user_id: str = "") -> str:
    """读取飞书文件内容"""
    return _execute_as_json("feishu_file_read", locals())


# ============================================================================
# 工具定义表 —— 描述每个工具的用途和参数
# ============================================================================

TOOL_DEFINITIONS = {
    "document_search": {
        "name": "document_search",
        "description": (
            "在文档向量库中执行语义搜索。当用户询问文档内容、"
            "需要查找特定资料、或需要从知识库中检索信息时使用此工具。"
        ),
        "func": _execute_document_search,
        "schema": DocumentSearchInput,
    },
    "memory_search": {
        "name": "memory_search",
        "description": (
            "搜索用户的历史对话记忆。当用户问'还记得吗'、'之前讨论过'、"
            "'历史记录'等内容时使用。也适用于需要参考过去对话上下文的场景。"
        ),
        "func": _execute_memory_search,
        "schema": MemorySearchInput,
    },
    "web_search": {
        "name": "web_search",
        "description": (
            "在网上搜索实时信息。当用户需要最新资讯、查找公开资料、"
            "或获取项目知识库之外的信息时使用。"
        ),
        "func": _execute_web_search,
        "schema": WebSearchInput,
    },
    "code_execution": {
        "name": "code_execution",
        "description": (
            "执行Python代码并返回结果。当用户要求运行代码、计算、"
            "数据处理、或验证代码逻辑时使用。"
        ),
        "func": _execute_code,
        "schema": CodeExecutionInput,
    },
    "file_operations": {
        "name": "file_operations",
        "description": (
            "执行文件系统操作：读取、写入、列出目录、删除文件。"
            "当用户需要操作服务器上的文件时使用。"
        ),
        "func": _execute_file_operations,
        "schema": FileOperationsInput,
    },
    "feishu_file_read": {
        "name": "feishu_file_read",
        "description": (
            "读取飞书文档/文件的内容。当用户上传了文件或引用了飞书文档，"
            "需要读取文件内容进行分析、总结或处理时使用。"
            "这是处理用户上传文件的首要工具。"
        ),
        "func": _execute_feishu_file_read,
        "schema": FeishuFileReadInput,
    },
}


# ============================================================================
# 公开API
# ============================================================================

def create_langchain_tools(tool_ids: Optional[List[str]] = None) -> List:
    """
    根据工具ID列表创建LangChain StructuredTool实例。

    Args:
        tool_ids: 需要的工具ID列表。为None时返回所有已定义的工具。

    Returns:
        LangChain StructuredTool 实例列表
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError:
        logger.warning("langchain_core 未安装，无法创建LangChain工具")
        return []

    from src.engine.mcp_client import mcp_client_manager
    remote = {tool["name"]: tool for tool in mcp_client_manager.descriptors()}
    if tool_ids is None:
        tool_ids = list(TOOL_DEFINITIONS.keys()) + list(remote)

    tools = []
    for tool_id in tool_ids:
        if tool_id in remote:
            info = remote[tool_id]
            func, coroutine = _remote_functions(tool_id)
            tools.append(StructuredTool.from_function(func=func, coroutine=coroutine,
                name=tool_id, description=info["description"], args_schema=info["inputSchema"]))
            continue
        if tool_id not in TOOL_DEFINITIONS:
            continue
        info = TOOL_DEFINITIONS[tool_id]
        tool = StructuredTool.from_function(
            func=info["func"],
            name=info["name"],
            description=info["description"],
            args_schema=info["schema"],
        )
        tools.append(tool)

    logger.debug(f"创建了 {len(tools)} 个LangChain工具: {[t.name for t in tools]}")
    return tools


def get_tool_by_name(name: str):
    """按名称获取单个LangChain工具"""
    tools = create_langchain_tools([name])
    return tools[0] if tools else None


def get_all_tool_descriptions() -> str:
    """获取所有工具的简短描述文本（用于prompt中的工具列表展示）"""
    lines = []
    for tool_id, info in TOOL_DEFINITIONS.items():
        schema_fields = info["schema"].model_fields
        params_desc = ", ".join(
            f"{name}: {field.description or 'N/A'}"
            for name, field in schema_fields.items()
        )
        lines.append(f"- **{tool_id}**: {info['description']}\n  参数: {params_desc}")
    return "\n".join(lines)


# ============================================================================
# 主流 Agent 生态对齐 —— OpenAI / Anthropic / MCP 工具描述导出
# 改造 1 + 2：复用 Pydantic schema 生成 JSON Schema，输出三种格式
# ============================================================================

def _clean_pydantic_schema_to_json_schema(schema_cls) -> dict:
    """将 Pydantic 模型转为干净的 JSON Schema 对象。

    去除 Pydantic 内部字段（title/$defs/definitions），
    将 Optional 字段产生的 anyOf:[{type:X},{type:"null"}] 折叠为 {type:X}。

    Returns:
        {type:"object", properties:{...}, required:[...]}
    """
    raw = schema_cls.model_json_schema()

    # 去除 Pydantic 内部顶层字段
    for key in ("title", "$defs", "definitions"):
        raw.pop(key, None)

    properties = raw.get("properties", {})
    cleaned_props: Dict[str, Any] = {}

    for name, prop in properties.items():
        # 折叠 anyOf:[{type:X},{type:"null"}] → {type:X}
        if isinstance(prop, dict) and "anyOf" in prop:
            branches = prop["anyOf"]
            non_null = next(
                (b for b in branches if b.get("type") != "null"), None
            )
            if non_null is not None:
                # 保留 description、default 等元数据
                merged = dict(non_null)
                if "description" in prop:
                    merged["description"] = prop["description"]
                if "default" in prop:
                    merged["default"] = prop["default"]
                cleaned_props[name] = merged
                continue
        # 去除子层级的 title（Pydantic 会给每个属性加 title）
        if isinstance(prop, dict) and "title" in prop and prop.get("title") == name:
            prop = {k: v for k, v in prop.items() if k != "title"}
        cleaned_props[name] = prop

    raw["properties"] = cleaned_props
    # required 保持 Pydantic 给出的（已排除有 default 的字段）
    raw.setdefault("required", [])
    raw["type"] = "object"
    return raw


def get_tool_schemas_openai(tool_ids: Optional[List[str]] = None) -> List[dict]:
    """返回 OpenAI/Anthropic function-calling 格式工具定义列表。

    每项: {"name":..., "description":..., "parameters": {type:"object", properties:{}, required:[]}}

    Args:
        tool_ids: 需要的工具ID列表。None 时返回所有已定义工具。

    Returns:
        OpenAI tools 参数可直接消费的字典列表
    """
    from src.engine.mcp_client import mcp_client_manager
    remote = {tool["name"]: tool for tool in mcp_client_manager.descriptors()}
    if tool_ids is None:
        tool_ids = list(TOOL_DEFINITIONS.keys()) + list(remote)

    schemas: List[dict] = []
    for tool_id in tool_ids:
        if tool_id in remote:
            tool = remote[tool_id]
            schemas.append({"name": tool_id, "description": tool["description"], "parameters": tool["inputSchema"]})
            continue
        if tool_id not in TOOL_DEFINITIONS:
            continue
        info = TOOL_DEFINITIONS[tool_id]
        schemas.append({
            "name": info["name"],
            "description": info["description"],
            "parameters": _clean_pydantic_schema_to_json_schema(info["schema"]),
        })
    return schemas


def get_tool_descriptors_mcp(tool_ids: Optional[List[str]] = None) -> List[dict]:
    """返回 MCP 兼容工具描述符列表。

    每项: {"name":..., "description":..., "inputSchema": {type:"object", properties:{}, required:[]}}

    与 OpenAI 格式同源，仅外层键名 parameters → inputSchema（MCP 工具描述符字段）。

    Args:
        tool_ids: 需要的工具ID列表。None 时返回所有已定义工具。

    Returns:
        MCP tools/list 响应可用的描述符列表
    """
    openai_schemas = get_tool_schemas_openai(tool_ids)
    mcp_descriptors: List[dict] = []
    for item in openai_schemas:
        mcp_item = dict(item)
        mcp_item["inputSchema"] = mcp_item.pop("parameters")
        mcp_descriptors.append(mcp_item)
    return mcp_descriptors


# ============================================================================
# ReAct 系统提示词 —— 从 prompts/react_system_prompt.txt 加载
# ============================================================================

def load_react_system_prompt(
    max_steps: int = 5,
    available_tools: Optional[List[str]] = None,
) -> str:
    """加载并格式化 ReAct 系统提示词模板。

    从 prompts/react_system_prompt.txt 读取模板，替换其中的
    {{ max_steps }} 和 {{ format_instructions }} 占位符。

    Args:
        max_steps: 最大推理步骤数
        available_tools: 当前可用的工具ID列表，用于生成 format_instructions

    Returns:
        格式化后的完整系统提示词字符串
    """
    prompt_path = os.path.join(_PROMPT_DIR, "react_system_prompt.txt")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        logger.error(f"ReAct系统提示词文件不存在: {prompt_path}")
        return _build_fallback_system_prompt(available_tools)
    except Exception as e:
        logger.error(f"读取ReAct系统提示词失败: {str(e)}")
        return _build_fallback_system_prompt(available_tools)

    # 替换 {{ max_steps }}
    template = template.replace("{{ max_steps }}", str(max_steps))

    # 构建 format_instructions：动态注入可用工具列表
    if available_tools:
        tool_types = available_tools + ["finish"]
        format_instructions = (
            f"可用的 action.type 值: {', '.join(tool_types)}\n\n"
            "当 action.type 为工具名时，action.parameters 中需要包含：\n"
            "  - tool_name: 要调用的工具名称\n"
            "  - parameters: 该工具所需的参数字典\n\n"
            "当 action.type 为 finish 时，action.parameters 中需要包含：\n"
            "  - answer: 最终回答内容（字符串）"
        )
    else:
        format_instructions = "可用的 action.type 值: finish"

    template = template.replace("{{ format_instructions }}", format_instructions)
    descriptors = get_tool_schemas_openai(available_tools or [])
    template += "\n\n工具参数定义（严格按 schema 传参）：\n" + json.dumps(descriptors, ensure_ascii=False)

    logger.debug(f"加载ReAct系统提示词 | length={len(template)} | tools={available_tools}")
    return template


def _build_fallback_system_prompt(available_tools: Optional[List[str]] = None) -> str:
    """当提示词文件不可用时的回退系统提示词"""
    tools_text = ", ".join(available_tools) if available_tools else "无"
    return f"""你是一个智能办公协同助手，使用 ReAct 模式进行推理。

可用工具: {tools_text}, finish

你必须输出严格的JSON格式：
{{"thought": "你的思考过程", "action": {{"type": "工具名或finish", "parameters": {{...}}}} }}

当可以直接回答时，使用 type=finish，parameters 中包含 answer 字段。"""


def parse_react_response(raw_text: str, available_tools: List[str]) -> Optional[Dict[str, Any]]:
    """解析LLM返回的ReAct JSON响应。

    支持多种格式容错：
    - 纯JSON: {{"thought": "...", "action": {...}}}
    - Markdown代码块: ```json ... ```
    - 前后带额外文本的JSON

    Args:
        raw_text: LLM原始响应文本
        available_tools: 当前可用工具ID列表，用于验证

    Returns:
        {"action": "tool_call", "tool_id": str, "parameters": dict}  或
        {"action": "finish", "answer": str}  或
        None（解析失败时）
    """
    if not raw_text:
        return None

    # 尝试从Markdown代码块中提取
    json_str = raw_text
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
    if code_block_match:
        json_str = code_block_match.group(1).strip()

    # 尝试找到JSON对象的起止位置
    brace_start = json_str.find("{")
    brace_end = json_str.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        json_str = json_str[brace_start:brace_end + 1]

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        logger.debug(f"[ReAct_PARSE] JSON解析失败，原始文本: {raw_text[:200]}")
        return None

    # 验证结构
    if "action" not in data:
        logger.debug("[ReAct_PARSE] 响应中缺少 action 字段")
        return None

    action = data["action"]
    action_type = action.get("type", "")

    # 记录 thought（如果有的话）
    thought = data.get("thought", "")
    if thought:
        logger.debug(f"[ReAct_THOUGHT] {thought[:200]}")

    # 处理 finish 动作
    if action_type == "finish":
        params = action.get("parameters", {})
        answer = params.get("answer", "") if isinstance(params, dict) else str(params)
        logger.info(f"[ReAct_FINISH] LLM决定直接回答 | answer_length={len(answer)}")
        return {"action": "finish", "answer": answer}

    # 处理工具调用
    # 支持两种参数格式：
    # 格式1（标准）: {"type": "tool_name", "parameters": {"tool_name": "...", "parameters": {...}}}
    # 格式2（简化）: {"type": "tool_name", "parameters": {"query": "...", "limit": 5}}
    params = action.get("parameters", {})

    if isinstance(params, str):
        # 参数是字符串的情况（某些模型的输出）
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            params = {"query": params}

    # 如果params中包含嵌套的 tool_name + parameters，展开它
    if isinstance(params, dict) and "tool_name" in params:
        tool_id = params.pop("tool_name")
        inner_params = params.pop("parameters", {}) if isinstance(params, dict) else {}
        if isinstance(inner_params, dict):
            # 合并内层参数到外层
            final_params = {**params, **inner_params}
        else:
            final_params = params
    else:
        tool_id = action_type
        final_params = params if isinstance(params, dict) else {}

    # 如果 action.type 本身就是工具名
    if action_type in available_tools:
        tool_id = action_type

    if tool_id not in available_tools and tool_id != "finish":
        logger.warning(f"[ReAct_PARSE] LLM返回了不可用的工具: {tool_id} | available={available_tools}")
        return None

    logger.info(f"[ReAct_PARSE] 解析出工具调用 | tool={tool_id} | params={final_params}")
    return {"action": "tool_call", "tool_id": tool_id, "parameters": final_params}


# ============================================================================
# ChatModel 工厂 —— 基于项目settings创建对应的LangChain ChatModel
# ============================================================================

def create_chat_model(temperature: float = 0.0):
    """
    根据 settings.MODEL_ROUTER_TYPE 创建对应的 LangChain BaseChatModel。

    支持的模型类型:
      - ollama:   ChatOllama (本地部署)
      - openai:   ChatOpenAI
      - claude:   ChatAnthropic
      - zhipu:    ChatOpenAI (智谱兼容OpenAI接口)
      - moonshot: ChatOpenAI (月之暗面兼容OpenAI接口)
      - deepseek: ChatOpenAI (DeepSeek兼容OpenAI接口)
      - multi:    回退到ollama

    Args:
        temperature: 模型温度，工具调用场景建议设为0（确定性输出）

    Returns:
        LangChain BaseChatModel 实例，如果创建失败则返回 None
    """
    router_type = settings.MODEL_ROUTER_TYPE

    try:
        if router_type == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=settings.OLLAMA_DEFAULT_MODEL,
                base_url=settings.OLLAMA_HOST,
                temperature=temperature or settings.OLLAMA_TEMPERATURE,
                num_predict=settings.OLLAMA_MAX_TOKENS,
            )

        elif router_type == "openai":
            from langchain_openai import ChatOpenAI
            if not settings.OPENAI_API_KEY:
                logger.warning("OpenAI API密钥未配置")
                return None
            return ChatOpenAI(
                api_key=settings.OPENAI_API_KEY,
                model="gpt-4o-mini",
                temperature=temperature,
            )

        elif router_type in ("claude", "anthropic"):
            from langchain_anthropic import ChatAnthropic
            if not settings.ANTHROPIC_API_KEY:
                logger.warning("Anthropic API密钥未配置")
                return None
            return ChatAnthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                model="claude-3-5-haiku-latest",
                temperature=temperature,
            )

        elif router_type == "zhipu":
            from langchain_openai import ChatOpenAI
            if not settings.ZHIPU_API_KEY:
                logger.warning("智谱AI API密钥未配置")
                return None
            return ChatOpenAI(
                api_key=settings.ZHIPU_API_KEY,
                base_url="https://open.bigmodel.cn/api/paas/v4",
                model="glm-4-flash",
                temperature=temperature,
            )

        elif router_type == "moonshot":
            from langchain_openai import ChatOpenAI
            if not settings.MOONSHOT_API_KEY:
                logger.warning("Moonshot API密钥未配置")
                return None
            return ChatOpenAI(
                api_key=settings.MOONSHOT_API_KEY,
                base_url="https://api.moonshot.cn/v1",
                model="moonshot-v1-8k",
                temperature=temperature,
            )

        elif router_type == "deepseek":
            from langchain_openai import ChatOpenAI
            if not settings.DEEPSEEK_API_KEY:
                logger.warning("DeepSeek API密钥未配置")
                return None
            return ChatOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
                model=settings.DEEPSEEK_DEFAULT_MODEL,
                temperature=temperature,
            )

        elif router_type == "multi":
            # MultiModelRouter场景：回退到ollama
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=settings.OLLAMA_DEFAULT_MODEL,
                base_url=settings.OLLAMA_HOST,
                temperature=temperature or settings.OLLAMA_TEMPERATURE,
                num_predict=settings.OLLAMA_MAX_TOKENS,
            )

        else:
            logger.warning(f"未知的模型路由类型: {router_type}，回退到Ollama")
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=settings.OLLAMA_DEFAULT_MODEL,
                base_url=settings.OLLAMA_HOST,
                temperature=temperature or settings.OLLAMA_TEMPERATURE,
                num_predict=settings.OLLAMA_MAX_TOKENS,
            )

    except ImportError as e:
        logger.warning(f"LangChain模型包未安装，无法创建ChatModel: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"创建ChatModel失败 ({router_type}): {str(e)}")
        return None


def _execute_as_json(tool_id, params):
    executor = _get_executor()
    if executor is None:
        return json.dumps({"success": False, "error": "Tool executor unavailable"})
    try:
        result = executor.execute(tool_id, params)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def _remote_functions(tool_id):
    def execute(**parameters):
        return _execute_as_json(tool_id, parameters)

    async def aexecute(**parameters):
        import asyncio
        return await asyncio.to_thread(_execute_as_json, tool_id, parameters)

    return execute, aexecute
