"""模型路由插件实现"""
from typing import Dict, Any, Optional
from src.plugins.base import ModelRouterBase
from src.config import settings
from src.logging_config import get_logger

logger = get_logger("model")


class OllamaRouter(ModelRouterBase):
    """Ollama模型路由器"""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_HOST
    
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到Ollama模型"""
        try:
            import requests
            model = model_type or "llama3"
            
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(f"{self.base_url}/api/generate", json=payload)
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            
            logger.error(f"Ollama请求失败: {response.status_code}")
            return ""
        except Exception as e:
            logger.error(f"Ollama路由失败: {str(e)}")
            return ""
    
    def get_router_type(self) -> str:
        return "ollama"


class OpenAIRouter(ModelRouterBase):
    """OpenAI模型路由器"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
    
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到OpenAI模型"""
        try:
            if not self.api_key:
                logger.warning("OpenAI API密钥未配置")
                return ""
            
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            model = model_type or "gpt-3.5-turbo"
            
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI路由失败: {str(e)}")
            return ""
    
    def get_router_type(self) -> str:
        return "openai"


class ClaudeRouter(ModelRouterBase):
    """Claude模型路由器"""
    
    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
    
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到Claude模型"""
        try:
            if not self.api_key:
                logger.warning("Claude API密钥未配置")
                return ""
            
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            model = model_type or "claude-3-sonnet-20240229"
            
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude路由失败: {str(e)}")
            return ""
    
    def get_router_type(self) -> str:
        return "claude"


class ZhipuRouter(ModelRouterBase):
    """智谱AI模型路由器"""
    
    def __init__(self):
        self.api_key = settings.ZHIPU_API_KEY
    
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到智谱AI模型"""
        try:
            if not self.api_key:
                logger.warning("智谱AI API密钥未配置")
                return ""
            
            import requests
            
            payload = {
                "model": model_type or "glm-4",
                "prompt": prompt,
                "stream": False
            }
            
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            logger.error(f"智谱AI请求失败: {response.status_code}")
            return ""
        except Exception as e:
            logger.error(f"智谱AI路由失败: {str(e)}")
            return ""
    
    def get_router_type(self) -> str:
        return "zhipu"


class MoonshotRouter(ModelRouterBase):
    """Moonshot模型路由器"""
    
    def __init__(self):
        self.api_key = settings.MOONSHOT_API_KEY
    
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到Moonshot模型"""
        try:
            if not self.api_key:
                logger.warning("Moonshot API密钥未配置")
                return ""
            
            import openai
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url="https://api.moonshot.cn/v1"
            )
            model = model_type or "moonshot-v1-8k"
            
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Moonshot路由失败: {str(e)}")
            return ""
    
    def get_router_type(self) -> str:
        return "moonshot"


# 模型路由器注册表
MODEL_ROUTER_REGISTRY = {
    "ollama": OllamaRouter,
    "openai": OpenAIRouter,
    "claude": ClaudeRouter,
    "zhipu": ZhipuRouter,
    "moonshot": MoonshotRouter
}


# 便捷函数
async def select_model(model_type: str = None) -> ModelRouterBase:
    """选择模型路由器"""
    router_type = model_type or settings.MODEL_ROUTER_TYPE
    
    if router_type in MODEL_ROUTER_REGISTRY:
        return MODEL_ROUTER_REGISTRY[router_type]()
    else:
        logger.warning(f"未找到模型路由类型: {router_type}，使用默认Ollama")
        return OllamaRouter()


async def call_model(prompt: str, model_type: str = None) -> str:
    """调用模型生成响应"""
    router = await select_model(model_type)
    return await router.route(prompt, model_type)
