from typing import List, Dict, Optional, Any
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser

from src.types import ModelRoute
from src.config import settings
from src.logging_config import get_logger

logger = get_logger("model")


def create_langchain_model(route: ModelRoute):
    """根据路由配置创建 LangChain 模型实例"""
    try:
        if route.provider == "openai":
            return ChatOpenAI(
                model=route.model,
                api_key=route.api_key,
                temperature=0.7,
                max_tokens=4096
            )
        
        elif route.provider == "claude":
            return ChatAnthropic(
                model=route.model,
                api_key=route.api_key,
                temperature=0.7,
                max_tokens=4096
            )
        
        elif route.provider == "ollama":
            return ChatOllama(
                model=route.model,
                base_url=settings.OLLAMA_HOST,
                temperature=0.7,
                max_tokens=4096
            )
        
        else:
            raise ValueError(f"Unsupported provider: {route.provider}")
    
    except Exception as e:
        logger.error(f"Failed to create LangChain model: {e}")
        raise


MODEL_ROUTES: List[ModelRoute] = [
    ModelRoute(
        model="gpt-4o",
        provider="openai",
        endpoint="https://api.openai.com/v1/chat/completions",
        api_key=settings.OPENAI_API_KEY,
        capabilities=["complex_reasoning", "coding", "ppt_outline", "creative_writing", "general"],
        cost_per_token=0.00001
    ),
    ModelRoute(
        model="claude-3-5-sonnet",
        provider="claude",
        endpoint="https://api.anthropic.com/v1/messages",
        api_key=settings.ANTHROPIC_API_KEY,
        capabilities=["complex_reasoning", "long_context", "coding", "document_analysis"],
        cost_per_token=0.000008
    ),
    ModelRoute(
        model="qwen3.5:9b",
        provider="ollama",
        endpoint=f"{settings.OLLAMA_HOST}/api/chat",
        api_key=None,
        capabilities=["summarization", "memory整理", "simple_tasks", "general"],
        cost_per_token=0.0
    ),
    ModelRoute(
        model="llama3.3:70b",
        provider="ollama",
        endpoint=f"{settings.OLLAMA_HOST}/api/chat",
        api_key=None,
        capabilities=["complex_reasoning", "coding", "long_context"],
        cost_per_token=0.0
    ),
    ModelRoute(
        model="mixtral:8x7b",
        provider="ollama",
        endpoint=f"{settings.OLLAMA_HOST}/api/chat",
        api_key=None,
        capabilities=["creative_writing", "summarization", "general"],
        cost_per_token=0.000005
    ),
    ModelRoute(
        model="phi3:3.8b",
        provider="ollama",
        endpoint=f"{settings.OLLAMA_HOST}/api/chat",
        api_key=None,
        capabilities=["simple_tasks", "summarization"],
        cost_per_token=0.000001
    )
]


def select_model(task_type: str, complexity: str = "medium") -> Optional[ModelRoute]:
    """根据任务类型选择合适的模型"""
    requirements: List[str] = []
    
    task_type_lower = task_type.lower()
    
    if task_type_lower in ["coding", "ppt", "ppt_outline", "complex"]:
        requirements.append("complex_reasoning")
    elif task_type_lower in ["summarization", "memory整理", "summary"]:
        requirements.append("summarization")
    elif task_type_lower in ["document_analysis", "long_document"]:
        requirements.append("long_context")
    else:
        requirements.append("general")
    
    # 过滤可用模型（有API key或本地模型）
    suitable_models = [
        route for route in MODEL_ROUTES
        if (route.api_key or route.provider == "ollama") and
           any(req in route.capabilities for req in requirements)
    ]
    
    if not suitable_models:
        logger.warning(f"No suitable model found for task type: {task_type}")
        return None
    
    # 根据复杂度选择
    if complexity == "simple":
        simple_model = next(
            (m for m in suitable_models 
             if "simple_tasks" in m.capabilities or "summarization" in m.capabilities),
            None
        )
        if simple_model:
            return simple_model
    
    # 选择最佳模型（优先能力匹配，其次成本）
    best_model = min(
        suitable_models,
        key=lambda m: (
            0 if "complex_reasoning" in m.capabilities and "complex_reasoning" in requirements else 1,
            0 if "long_context" in m.capabilities and "long_context" in requirements else 1,
            m.cost_per_token
        )
    )
    
    logger.info(f"Selected model: {best_model.model} for task: {task_type}")
    return best_model


def call_model(route: ModelRoute, messages: List[Dict[str, str]]) -> str:
    """使用 LangChain 调用模型"""
    try:
        # 创建 LangChain 模型
        llm = create_langchain_model(route)
        
        # 转换消息格式
        langchain_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:
                langchain_messages.append(HumanMessage(content=content))
        
        # 创建链并执行
        chain = llm | StrOutputParser()
        response = chain.invoke(langchain_messages)
        
        return str(response)
    
    except Exception as e:
        logger.error(f"Model API call failed: {str(e)}")
        raise


def call_model_with_prompt(route: ModelRoute, system_prompt: str, user_prompt: str) -> str:
    """使用系统提示和用户提示调用模型"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    return call_model(route, messages)