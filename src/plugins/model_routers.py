"""模型路由插件实现"""
from typing import Dict, Any, List, Optional

from src.plugins.base import ModelRouterBase
from src.config import settings
from src.exceptions import ModelException
from src.logging_config import get_logger

logger = get_logger("model")


class OllamaRouter(ModelRouterBase):
    """Ollama本地模型路由"""
    
    def __init__(self):
        self.models = {
            "simple": "qwen3.5:7b",
            "medium": "qwen3.5:9b",
            "complex": "qwen3.5:14b"
        }
        self.clients = {}
    
    def select_model(self, task_type: str, complexity: str) -> Any:
        """选择Ollama模型"""
        try:
            from langchain_ollama import ChatOllama
            
            model_name = self.models.get(complexity, self.models["medium"])
            
            if model_name not in self.clients:
                self.clients[model_name] = ChatOllama(
                    model=model_name,
                    base_url=settings.OLLAMA_HOST,
                    temperature=0.7
                )
            
            return self.clients[model_name]
        except Exception as e:
            logger.error(f"Ollama模型选择失败: {str(e)}")
            raise ModelException(
                message="Ollama模型选择失败",
                detail=str(e),
                context={
                    "task_type": task_type,
                    "complexity": complexity,
                    "model_name": self.models.get(complexity)
                }
            )
    
    def call_model(self, model: Any, messages: List[Dict[str, str]]) -> str:
        """调用Ollama模型"""
        try:
            response = model.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Ollama模型调用失败: {str(e)}")
            raise ModelException(
                message="Ollama模型调用失败",
                detail=str(e),
                context={"model_type": self.get_model_type()}
            )
    
    def get_model_type(self) -> str:
        return "ollama"


class OpenAIRouter(ModelRouterBase):
    """OpenAI模型路由"""
    
    def __init__(self):
        self.models = {
            "simple": "gpt-4o-mini",
            "medium": "gpt-4o",
            "complex": "gpt-4o"
        }
        self.clients = {}
    
    def select_model(self, task_type: str, complexity: str) -> Any:
        """选择OpenAI模型"""
        try:
            from langchain_openai import ChatOpenAI
            
            model_name = self.models.get(complexity, self.models["medium"])
            
            if model_name not in self.clients:
                self.clients[model_name] = ChatOpenAI(
                    model=model_name,
                    api_key=settings.OPENAI_API_KEY,
                    temperature=0.7
                )
            
            return self.clients[model_name]
        except Exception as e:
            logger.error(f"OpenAI模型选择失败: {str(e)}")
            return None
    
    def call_model(self, model: Any, messages: List[Dict[str, str]]) -> str:
        """调用OpenAI模型"""
        try:
            response = model.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"OpenAI模型调用失败: {str(e)}")
            return ""
    
    def get_model_type(self) -> str:
        return "openai"


class AnthropicRouter(ModelRouterBase):
    """Anthropic Claude模型路由"""
    
    def __init__(self):
        self.models = {
            "simple": "claude-3-haiku-20240307",
            "medium": "claude-3-sonnet-20240229",
            "complex": "claude-3-opus-20240229"
        }
        self.clients = {}
    
    def select_model(self, task_type: str, complexity: str) -> Any:
        """选择Anthropic模型"""
        try:
            from langchain_anthropic import ChatAnthropic
            
            model_name = self.models.get(complexity, self.models["medium"])
            
            if model_name not in self.clients:
                self.clients[model_name] = ChatAnthropic(
                    model=model_name,
                    api_key=settings.ANTHROPIC_API_KEY,
                    temperature=0.7
                )
            
            return self.clients[model_name]
        except Exception as e:
            logger.error(f"Anthropic模型选择失败: {str(e)}")
            return None
    
    def call_model(self, model: Any, messages: List[Dict[str, str]]) -> str:
        """调用Anthropic模型"""
        try:
            response = model.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Anthropic模型调用失败: {str(e)}")
            return ""
    
    def get_model_type(self) -> str:
        return "anthropic"


class ZhipuRouter(ModelRouterBase):
    """智谱GLM模型路由"""
    
    def __init__(self):
        self.models = {
            "simple": "glm-4-flash",
            "medium": "glm-4",
            "complex": "glm-4"
        }
        self.clients = {}
    
    def select_model(self, task_type: str, complexity: str) -> Any:
        """选择智谱模型"""
        try:
            from langchain_community.chat_models import ChatZhipuAI
            
            model_name = self.models.get(complexity, self.models["medium"])
            
            if model_name not in self.clients:
                self.clients[model_name] = ChatZhipuAI(
                    model=model_name,
                    api_key=settings.ZHIPU_API_KEY,
                    temperature=0.7
                )
            
            return self.clients[model_name]
        except Exception as e:
            logger.error(f"智谱模型选择失败: {str(e)}")
            return None
    
    def call_model(self, model: Any, messages: List[Dict[str, str]]) -> str:
        """调用智谱模型"""
        try:
            response = model.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"智谱模型调用失败: {str(e)}")
            return ""
    
    def get_model_type(self) -> str:
        return "zhipu"


class MoonshotRouter(ModelRouterBase):
    """Moonshot Kimi模型路由"""
    
    def __init__(self):
        self.models = {
            "simple": "moonshot-v1-8k",
            "medium": "moonshot-v1-32k",
            "complex": "moonshot-v1-128k"
        }
        self.clients = {}
    
    def select_model(self, task_type: str, complexity: str) -> Any:
        """选择Moonshot模型"""
        try:
            from langchain_openai import ChatOpenAI
            
            model_name = self.models.get(complexity, self.models["medium"])
            
            if model_name not in self.clients:
                self.clients[model_name] = ChatOpenAI(
                    model=model_name,
                    api_key=settings.MOONSHOT_API_KEY,
                    base_url="https://api.moonshot.cn/v1",
                    temperature=0.7
                )
            
            return self.clients[model_name]
        except Exception as e:
            logger.error(f"Moonshot模型选择失败: {str(e)}")
            return None
    
    def call_model(self, model: Any, messages: List[Dict[str, str]]) -> str:
        """调用Moonshot模型"""
        try:
            response = model.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Moonshot模型调用失败: {str(e)}")
            return ""
    
    def get_model_type(self) -> str:
        return "moonshot"


class MultiModelRouter(ModelRouterBase):
    """多模型路由（根据任务类型自动选择最优模型）"""
    
    def __init__(self):
        self.routers = {}
        self._init_routers()
    
    def _init_routers(self):
        if settings.OLLAMA_HOST:
            self.routers["ollama"] = OllamaRouter()
        if settings.OPENAI_API_KEY:
            self.routers["openai"] = OpenAIRouter()
        if settings.ANTHROPIC_API_KEY:
            self.routers["anthropic"] = AnthropicRouter()
        if settings.ZHIPU_API_KEY:
            self.routers["zhipu"] = ZhipuRouter()
        if settings.MOONSHOT_API_KEY:
            self.routers["moonshot"] = MoonshotRouter()
    
    def select_model(self, task_type: str, complexity: str) -> Any:
        """根据任务类型选择最优模型"""
        # 任务类型到模型类型的映射
        task_model_map = {
            "coding": "openai",
            "document_analysis": "anthropic",
            "creative_writing": "moonshot",
            "summarization": "ollama",
            "question_answering": "zhipu"
        }
        
        preferred_model = task_model_map.get(task_type, "ollama")
        
        if preferred_model in self.routers:
            return self.routers[preferred_model].select_model(task_type, complexity)
        
        # 回退到第一个可用的路由器
        for router in self.routers.values():
            model = router.select_model(task_type, complexity)
            if model:
                return model
        
        return None
    
    def call_model(self, model: Any, messages: List[Dict[str, str]]) -> str:
        """调用模型（通过底层路由器）"""
        for router in self.routers.values():
            try:
                return router.call_model(model, messages)
            except:
                continue
        return ""
    
    def get_model_type(self) -> str:
        return "multi"


# 模型路由注册表
MODEL_ROUTER_REGISTRY = {
    "ollama": OllamaRouter,
    "openai": OpenAIRouter,
    "anthropic": AnthropicRouter,
    "zhipu": ZhipuRouter,
    "moonshot": MoonshotRouter,
    "multi": MultiModelRouter
}
