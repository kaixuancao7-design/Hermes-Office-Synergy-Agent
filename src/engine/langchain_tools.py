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

class DocumentSearchInput(BaseModel):
    """文档搜索参数"""
    query: str = Field(description="要在文档向量库中搜索的关键词或问题")
    limit: int = Field(default=5, description="返回结果的最大数量")


class MemorySearchInput(BaseModel):
    """记忆搜索参数"""
    query: str = Field(description="要搜索的记忆关键词或问题")
    limit: int = Field(default=5, description="返回结果的最大数量")


class WebSearchInput(BaseModel):
    """网页搜索参数"""
    query: str = Field(description="要在网上搜索的关键词")


class CodeExecutionInput(BaseModel):
    """代码执行参数"""
    code: str = Field(description="要执行的完整代码")
    language: str = Field(default="python", description="编程语言，默认python")


class FileOperationsInput(BaseModel):
    """文件操作参数"""
    operation: str = Field(description="操作类型: read(读取), write(写入), list(列出文件), delete(删除)")
    path: str = Field(description="文件或目录的路径")
    content: str = Field(default="", description="要写入的内容（仅write操作需要）")


class FeishuFileReadInput(BaseModel):
    """飞书文件读取参数"""
    file_key: str = Field(description="飞书文件的唯一标识key")
    user_id: str = Field(default="", description="当前用户ID")


# ============================================================================
# 工具包装函数 —— 将LangChain工具调用转换为 tool_executor.execute() 调用
# ============================================================================

def _get_executor():
    """延迟获取tool_executor，避免循环导入"""
    from src.plugins import get_tool_executor
    return get_tool_executor()


def _execute_document_search(query: str, limit: int = 5) -> str:
    """执行文档搜索"""
    executor = _get_executor()
    if not executor:
        return "错误：工具执行器不可用"
    result = executor.execute("document_search", {"query": query, "limit": limit})
    if result.get("success"):
        docs = result.get("result", [])
        if not docs:
            return "未找到相关文档"
        return "\n\n".join(
            f"[文档{i+1}] {d.get('content', str(d))[:500]}"
            for i, d in enumerate(docs)
        )
    return f"文档搜索失败: {result.get('error', '未知错误')}"


def _execute_memory_search(query: str, limit: int = 5) -> str:
    """执行记忆搜索"""
    executor = _get_executor()
    if not executor:
        return "错误：工具执行器不可用"
    result = executor.execute("memory_search", {"query": query, "limit": limit})
    if result.get("success"):
        memories = result.get("result", [])
        if not memories:
            return "未找到相关记忆"
        return "\n\n".join(
            f"[记忆{i+1}] {str(m)[:500]}"
            for i, m in enumerate(memories)
        )
    return f"记忆搜索失败: {result.get('error', '未知错误')}"


def _execute_web_search(query: str) -> str:
    """执行网页搜索"""
    executor = _get_executor()
    if not executor:
        return "错误：工具执行器不可用"
    result = executor.execute("web_search", {"query": query})
    if result.get("success"):
        items = result.get("result", [])
        if not items:
            return "未找到相关网页"
        return "\n\n".join(
            f"[{i+1}] {item.get('title', 'N/A')}\n    {item.get('summary', '')}\n    {item.get('url', '')}"
            for i, item in enumerate(items)
        )
    return f"网页搜索失败: {result.get('error', '未知错误')}"


def _execute_code(code: str, language: str = "python") -> str:
    """执行代码"""
    executor = _get_executor()
    if not executor:
        return "错误：工具执行器不可用"
    result = executor.execute("code_execution", {"code": code, "language": language})
    if result.get("success"):
        r = result.get("result", {})
        stdout = r.get("stdout", "")
        stderr = r.get("stderr", "")
        parts = []
        if stdout:
            parts.append(f"标准输出:\n{stdout}")
        if stderr:
            parts.append(f"错误输出:\n{stderr}")
        return "\n".join(parts) if parts else "代码执行完成，无输出"
    return f"代码执行失败: {result.get('error', '未知错误')}"


def _execute_file_operations(operation: str, path: str, content: str = "") -> str:
    """执行文件操作"""
    executor = _get_executor()
    if not executor:
        return "错误：工具执行器不可用"
    result = executor.execute("file_operations", {
        "operation": operation,
        "path": path,
        "content": content,
    })
    if result.get("success"):
        r = result.get("result", "")
        return str(r) if r else f"{operation} 操作成功"
    return f"文件操作失败: {result.get('error', '未知错误')}"


def _execute_feishu_file_read(file_key: str, user_id: str = "") -> str:
    """读取飞书文件内容"""
    executor = _get_executor()
    if not executor:
        return "错误：工具执行器不可用"
    result = executor.execute("feishu_file_read", {
        "file_key": file_key,
        "user_id": user_id,
    })
    if result.get("success"):
        content = result.get("result", {}).get("content", str(result.get("result", "")))
        # 截断过长内容，避免超出模型上下文窗口
        if len(content) > 8000:
            content = content[:8000] + "\n...(内容已截断)"
        return content
    return f"飞书文件读取失败: {result.get('error', '未知错误')}"


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

    if tool_ids is None:
        tool_ids = list(TOOL_DEFINITIONS.keys())

    tools = []
    for tool_id in tool_ids:
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
