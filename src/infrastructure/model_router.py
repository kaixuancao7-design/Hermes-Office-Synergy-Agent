import json
import requests
from typing import List, Dict, Optional, Any
from src.types import ModelRoute
from src.config import settings
from src.utils import setup_logging

logger = setup_logging(settings.LOG_LEVEL)

MODEL_ROUTES: List[ModelRoute] = [
    ModelRoute(
        model="qwen3.5:9b",
        provider="ollama",
        endpoint=f"{settings.OLLAMA_HOST}/api/chat",
        api_key=None,
        capabilities=["complex_reasoning", "coding", "ppt_outline", "creative_writing"],
        cost_per_token=0.00001
    ),
    ModelRoute(
        model="qwen3.5:9b",
        provider="ollama",
        endpoint=f"{settings.OLLAMA_HOST}/api/chat",
        api_key=None,
        capabilities=["complex_reasoning", "long_context", "coding"],
        cost_per_token=0.000008
    ),
    ModelRoute(
        model="qwen3.5:9b",
        provider="ollama",
        endpoint=f"{settings.OLLAMA_HOST}/api/chat",
        capabilities=["summarization", "memory整理", "simple_tasks"],
        cost_per_token=0.0
    ),
    ModelRoute(
        model="qwen3.5:9b",
        provider="ollama",
        endpoint=f"{settings.OLLAMA_HOST}/api/chat",
        api_key=None,
        capabilities=["complex_reasoning", "coding"],
        cost_per_token=0.0
    ),
    ModelRoute(
        model="qwen3.5:9b",
        provider="ollama",
        endpoint=f"{settings.OLLAMA_HOST}/api/chat",
        api_key=None,
        capabilities=["creative_writing", "summarization"],
        cost_per_token=0.000005
    ),
    ModelRoute(
        model="qwen3.5:9b",
        provider="ollama",
        endpoint=f"{settings.OLLAMA_HOST}/api/chat",
        api_key=None,
        capabilities=["long_context", "document_analysis"],
        cost_per_token=0.000006
    )
]


def select_model(task_type: str, complexity: str = "medium") -> Optional[ModelRoute]:
    requirements: List[str] = []
    
    task_type_lower = task_type.lower()
    
    if task_type_lower in ["coding", "ppt", "ppt_outline"]:
        requirements.append("complex_reasoning")
    elif task_type_lower in ["summarization", "memory整理"]:
        requirements.append("summarization")
    elif task_type_lower == "document_analysis":
        requirements.append("long_context")
    else:
        requirements.append("general")
    
    suitable_models = [
        route for route in MODEL_ROUTES
        if (route.api_key or route.provider == "ollama") and
           any(req in route.capabilities or "complex_reasoning" in route.capabilities
               for req in requirements)
    ]
    
    if not suitable_models:
        return None
    
    if complexity == "simple":
        simple_model = next(
            (m for m in suitable_models 
             if "summarization" in m.capabilities or "memory整理" in m.capabilities),
            None
        )
        if simple_model:
            return simple_model
    
    best_model = min(
        suitable_models,
        key=lambda m: (
            0 if "complex_reasoning" in m.capabilities else 1,
            m.cost_per_token
        )
    )
    
    return best_model


def call_model(route: ModelRoute, messages: List[Dict[str, str]]) -> str:
    headers: Dict[str, str] = {
        "Content-Type": "application/json"
    }
    
    body: Dict[str, Any]
    response_parser: callable
    
    try:
        if route.provider == "openai":
            headers["Authorization"] = f"Bearer {route.api_key}"
            body = {
                "model": route.model,
                "messages": messages,
                "temperature": 0.7
            }
            response_parser = lambda res: res["choices"][0]["message"]["content"]
        
        elif route.provider == "claude":
            headers["x-api-key"] = route.api_key or ""
            headers["anthropic-version"] = "2023-06-01"
            body = {
                "model": route.model,
                "messages": [
                    {"role": m["role"], "content": m["content"]}
                    for m in messages
                ],
                "max_tokens": 4096
            }
            response_parser = lambda res: res["content"][0]["text"]
        
        elif route.provider == "ollama":
            body = {
                "model": route.model,
                "messages": messages,
                "stream": False
            }
            response_parser = lambda res: res["message"]["content"]
        
        elif route.provider == "zhipu":
            headers["Authorization"] = f"Bearer {route.api_key}"
            body = {
                "model": route.model,
                "messages": messages,
                "temperature": 0.7
            }
            response_parser = lambda res: res["choices"][0]["message"]["content"]
        
        elif route.provider == "kimi":
            headers["Authorization"] = f"Bearer {route.api_key}"
            body = {
                "model": route.model,
                "messages": messages,
                "temperature": 0.7
            }
            response_parser = lambda res: res["choices"][0]["message"]["content"]
        
        else:
            raise ValueError(f"Unsupported provider: {route.provider}")
        
        response = requests.post(route.endpoint, headers=headers, json=body, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        return response_parser(data)
    
    except Exception as e:
        logger.error(f"Model API call failed: {str(e)}")
        raise
