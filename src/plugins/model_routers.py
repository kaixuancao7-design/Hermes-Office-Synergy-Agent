"""模型路由插件实现 - 增强日志版本"""
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from src.plugins.base import ModelRouterBase
from src.config import settings
from src.logging_config import get_logger, log_event, log_performance

logger = get_logger("model")


class OllamaRouter(ModelRouterBase):
    """Ollama模型路由器 - 严格遵循配置文件预设参数"""
    
    def __init__(self):
        self.base_url = settings.OLLAMA_HOST
        self.default_model = settings.OLLAMA_DEFAULT_MODEL
        self.max_tokens = settings.OLLAMA_MAX_TOKENS
        self.temperature = settings.OLLAMA_TEMPERATURE
        self.top_p = settings.OLLAMA_TOP_P
        self.retry_count = settings.OLLAMA_RETRY_COUNT
        self.timeout = settings.OLLAMA_TIMEOUT
        logger.info(f"[INIT] OllamaRouter 初始化 | base_url={self.base_url} | default_model={self.default_model} | max_tokens={self.max_tokens} | temperature={self.temperature}")
    
    @log_performance(logger, "Ollama调用")
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到Ollama模型 - 严格使用配置文件中的预设参数"""
        start_time = datetime.now()
        
        # 使用配置文件中的默认模型，model_type仅作为类型标识而非模型名称
        model = self.default_model
        
        prompt_length = len(prompt)
        
        logger.info(f"[MODEL_CALL] 调用Ollama模型 | model={model} | prompt_length={prompt_length}")
        logger.debug(f"[MODEL_PROMPT] 提示内容预览 | {prompt[:100]}...")
        
        # 使用配置文件中的重试次数设置
        retry_count = self.retry_count
        last_error = None
        
        try:
            import requests
            import time
            
            # 严格使用配置文件中的预设参数构建请求
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p
            }
            
            for attempt in range(retry_count):
                try:
                    # 使用配置文件中的超时设置
                    response = requests.post(
                        f"{self.base_url}/api/generate", 
                        json=payload, 
                        timeout=self.timeout
                    )
                    
                    elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                    
                    if response.status_code == 200:
                        result = response.json()
                        response_text = result.get("response", "")
                        response_length = len(response_text)
                        
                        logger.info(f"[MODEL_SUCCESS] Ollama响应成功 | model={model} | response_length={response_length} | elapsed={elapsed_ms:.2f}ms")
                        log_event(logger, "model_call",
                                 model_type="ollama",
                                 model_name=model,
                                 success=True,
                                 prompt_length=prompt_length,
                                 response_length=response_length,
                                 elapsed_ms=elapsed_ms)
                        
                        return response_text
                    
                    last_error = f"HTTP {response.status_code}"
                    logger.warning(f"[MODEL_RETRY] Ollama请求失败，尝试 {attempt + 1}/{retry_count} | model={model} | status_code={response.status_code}")
                    
                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    logger.warning(f"[MODEL_RETRY] Ollama请求异常，尝试 {attempt + 1}/{retry_count} | model={model} | error={str(e)}")
                
                # 重试间隔
                if attempt < retry_count - 1:
                    time.sleep(1 << attempt)  # 指数退避：1s, 2s, 4s...
            
            # 所有重试失败
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[MODEL_FAILED] Ollama请求失败（已重试{retry_count}次） | model={model} | error={last_error} | elapsed={elapsed_ms:.2f}ms")
            log_event(logger, "model_call",
                     model_type="ollama",
                     model_name=model,
                     success=False,
                     error=last_error,
                     prompt_length=prompt_length,
                     elapsed_ms=elapsed_ms)
            
            return ""
        except Exception as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[MODEL_ERROR] Ollama路由失败 | model={model} | error={str(e)} | elapsed={elapsed_ms:.2f}ms", exc_info=True)
            log_event(logger, "model_call",
                     model_type="ollama",
                     model_name=model,
                     success=False,
                     error=str(e),
                     prompt_length=prompt_length,
                     elapsed_ms=elapsed_ms)
            return ""
    
    def get_router_type(self) -> str:
        return "ollama"


class OpenAIRouter(ModelRouterBase):
    """OpenAI模型路由器"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        if self.api_key:
            logger.info("[INIT] OpenAIRouter 初始化 | API密钥已配置")
        else:
            logger.warning("[INIT] OpenAIRouter 初始化 | API密钥未配置")
    
    @log_performance(logger, "OpenAI调用")
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到OpenAI模型"""
        start_time = datetime.now()
        model = model_type or "gpt-3.5-turbo"
        prompt_length = len(prompt)
        
        if not self.api_key:
            logger.warning(f"[MODEL_CONFIG] OpenAI API密钥未配置 | model={model}")
            return ""
        
        logger.info(f"[MODEL_CALL] 调用OpenAI模型 | model={model} | prompt_length={prompt_length}")
        logger.debug(f"[MODEL_PROMPT] 提示内容预览 | {prompt[:100]}...")
        
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            response_text = response.choices[0].message.content
            response_length = len(response_text)
            
            logger.info(f"[MODEL_SUCCESS] OpenAI响应成功 | model={model} | response_length={response_length} | elapsed={elapsed_ms:.2f}ms")
            log_event(logger, "model_call",
                     model_type="openai",
                     model_name=model,
                     success=True,
                     prompt_length=prompt_length,
                     response_length=response_length,
                     elapsed_ms=elapsed_ms)
            
            return response_text
        except Exception as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[MODEL_ERROR] OpenAI路由失败 | model={model} | error={str(e)} | elapsed={elapsed_ms:.2f}ms", exc_info=True)
            log_event(logger, "model_call",
                     model_type="openai",
                     model_name=model,
                     success=False,
                     error=str(e),
                     prompt_length=prompt_length,
                     elapsed_ms=elapsed_ms)
            return ""
    
    def get_router_type(self) -> str:
        return "openai"


class ClaudeRouter(ModelRouterBase):
    """Claude模型路由器"""
    
    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        if self.api_key:
            logger.info("[INIT] ClaudeRouter 初始化 | API密钥已配置")
        else:
            logger.warning("[INIT] ClaudeRouter 初始化 | API密钥未配置")
    
    @log_performance(logger, "Claude调用")
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到Claude模型"""
        start_time = datetime.now()
        model = model_type or "claude-3-sonnet-20240229"
        prompt_length = len(prompt)
        
        if not self.api_key:
            logger.warning(f"[MODEL_CONFIG] Claude API密钥未配置 | model={model}")
            return ""
        
        logger.info(f"[MODEL_CALL] 调用Claude模型 | model={model} | prompt_length={prompt_length}")
        logger.debug(f"[MODEL_PROMPT] 提示内容预览 | {prompt[:100]}...")
        
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            response_text = response.content[0].text
            response_length = len(response_text)
            
            logger.info(f"[MODEL_SUCCESS] Claude响应成功 | model={model} | response_length={response_length} | elapsed={elapsed_ms:.2f}ms")
            log_event(logger, "model_call",
                     model_type="claude",
                     model_name=model,
                     success=True,
                     prompt_length=prompt_length,
                     response_length=response_length,
                     elapsed_ms=elapsed_ms)
            
            return response_text
        except Exception as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[MODEL_ERROR] Claude路由失败 | model={model} | error={str(e)} | elapsed={elapsed_ms:.2f}ms", exc_info=True)
            log_event(logger, "model_call",
                     model_type="claude",
                     model_name=model,
                     success=False,
                     error=str(e),
                     prompt_length=prompt_length,
                     elapsed_ms=elapsed_ms)
            return ""
    
    def get_router_type(self) -> str:
        return "claude"


class ZhipuRouter(ModelRouterBase):
    """智谱AI模型路由器"""
    
    def __init__(self):
        self.api_key = settings.ZHIPU_API_KEY
        if self.api_key:
            logger.info("[INIT] ZhipuRouter 初始化 | API密钥已配置")
        else:
            logger.warning("[INIT] ZhipuRouter 初始化 | API密钥未配置")
    
    @log_performance(logger, "智谱AI调用")
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到智谱AI模型"""
        start_time = datetime.now()
        model = model_type or "glm-4"
        prompt_length = len(prompt)
        
        if not self.api_key:
            logger.warning(f"[MODEL_CONFIG] 智谱AI API密钥未配置 | model={model}")
            return ""
        
        logger.info(f"[MODEL_CALL] 调用智谱AI模型 | model={model} | prompt_length={prompt_length}")
        logger.debug(f"[MODEL_PROMPT] 提示内容预览 | {prompt[:100]}...")
        
        try:
            import requests
            
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False
            }
            
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                json=payload,
                headers=headers
            )
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                response_length = len(response_text)
                
                logger.info(f"[MODEL_SUCCESS] 智谱AI响应成功 | model={model} | response_length={response_length} | elapsed={elapsed_ms:.2f}ms")
                log_event(logger, "model_call",
                         model_type="zhipu",
                         model_name=model,
                         success=True,
                         prompt_length=prompt_length,
                         response_length=response_length,
                         elapsed_ms=elapsed_ms)
                
                return response_text
            
            logger.error(f"[MODEL_FAILED] 智谱AI请求失败 | model={model} | status_code={response.status_code} | elapsed={elapsed_ms:.2f}ms")
            log_event(logger, "model_call",
                     model_type="zhipu",
                     model_name=model,
                     success=False,
                     error=f"HTTP {response.status_code}",
                     prompt_length=prompt_length,
                     elapsed_ms=elapsed_ms)
            
            return ""
        except Exception as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[MODEL_ERROR] 智谱AI路由失败 | model={model} | error={str(e)} | elapsed={elapsed_ms:.2f}ms", exc_info=True)
            log_event(logger, "model_call",
                     model_type="zhipu",
                     model_name=model,
                     success=False,
                     error=str(e),
                     prompt_length=prompt_length,
                     elapsed_ms=elapsed_ms)
            return ""
    
    def get_router_type(self) -> str:
        return "zhipu"


class MoonshotRouter(ModelRouterBase):
    """Moonshot模型路由器"""
    
    def __init__(self):
        self.api_key = settings.MOONSHOT_API_KEY
        if self.api_key:
            logger.info("[INIT] MoonshotRouter 初始化 | API密钥已配置")
        else:
            logger.warning("[INIT] MoonshotRouter 初始化 | API密钥未配置")
    
    @log_performance(logger, "Moonshot调用")
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到Moonshot模型"""
        start_time = datetime.now()
        model = model_type or "moonshot-v1-8k"
        prompt_length = len(prompt)
        
        if not self.api_key:
            logger.warning(f"[MODEL_CONFIG] Moonshot API密钥未配置 | model={model}")
            return ""
        
        logger.info(f"[MODEL_CALL] 调用Moonshot模型 | model={model} | prompt_length={prompt_length}")
        logger.debug(f"[MODEL_PROMPT] 提示内容预览 | {prompt[:100]}...")
        
        try:
            import openai
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url="https://api.moonshot.cn/v1"
            )
            
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            response_text = response.choices[0].message.content
            response_length = len(response_text)
            
            logger.info(f"[MODEL_SUCCESS] Moonshot响应成功 | model={model} | response_length={response_length} | elapsed={elapsed_ms:.2f}ms")
            log_event(logger, "model_call",
                     model_type="moonshot",
                     model_name=model,
                     success=True,
                     prompt_length=prompt_length,
                     response_length=response_length,
                     elapsed_ms=elapsed_ms)
            
            return response_text
        except Exception as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[MODEL_ERROR] Moonshot路由失败 | model={model} | error={str(e)} | elapsed={elapsed_ms:.2f}ms", exc_info=True)
            log_event(logger, "model_call",
                     model_type="moonshot",
                     model_name=model,
                     success=False,
                     error=str(e),
                     prompt_length=prompt_length,
                     elapsed_ms=elapsed_ms)
            return ""
    
    def get_router_type(self) -> str:
        return "moonshot"


class DeepSeekRouter(ModelRouterBase):
    """DeepSeek模型路由器 — 兼容OpenAI API接口"""

    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.default_model = settings.DEEPSEEK_DEFAULT_MODEL
        if self.api_key:
            logger.info("[INIT] DeepSeekRouter 初始化 | API密钥已配置 | model=%s", self.default_model)
        else:
            logger.warning("[INIT] DeepSeekRouter 初始化 | API密钥未配置")

    @log_performance(logger, "DeepSeek调用")
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到DeepSeek模型"""
        start_time = datetime.now()
        model = model_type or self.default_model
        prompt_length = len(prompt)

        if not self.api_key:
            logger.warning(f"[MODEL_CONFIG] DeepSeek API密钥未配置 | model={model}")
            return ""

        logger.info(f"[MODEL_CALL] 调用DeepSeek模型 | model={model} | prompt_length={prompt_length}")

        try:
            import openai
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com",
            )

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )

            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            response_text = response.choices[0].message.content
            response_length = len(response_text)

            logger.info(f"[MODEL_SUCCESS] DeepSeek响应成功 | model={model} | response_length={response_length} | elapsed={elapsed_ms:.2f}ms")
            log_event(logger, "model_call",
                     model_type="deepseek",
                     model_name=model,
                     success=True,
                     prompt_length=prompt_length,
                     response_length=response_length,
                     elapsed_ms=elapsed_ms)

            return response_text
        except Exception as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"[MODEL_ERROR] DeepSeek路由失败 | model={model} | error={str(e)} | elapsed={elapsed_ms:.2f}ms", exc_info=True)
            log_event(logger, "model_call",
                     model_type="deepseek",
                     model_name=model,
                     success=False,
                     error=str(e),
                     prompt_length=prompt_length,
                     elapsed_ms=elapsed_ms)
            return ""

    def get_router_type(self) -> str:
        return "deepseek"


class MultiModelRouter(ModelRouterBase):
    """多模型路由器 - 可根据需求选择最优模型"""
    
    def __init__(self):
        self.routers = {}
        for router_type, router_class in MODEL_ROUTER_REGISTRY.items():
            self.routers[router_type] = router_class()
        logger.info(f"[INIT] MultiModelRouter 初始化 | registered_models={list(self.routers.keys())}")
    
    @log_performance(logger, "多模型调用")
    async def route(self, prompt: str, model_type: str = None) -> str:
        """路由到指定模型或根据策略选择模型"""
        if model_type and model_type in self.routers:
            logger.info(f"[MODEL_SELECT] 使用指定模型 | model={model_type}")
            return await self.routers[model_type].route(prompt, model_type)
        
        # 策略：根据prompt长度选择模型
        prompt_length = len(prompt)
        
        # 短prompt使用轻量模型，长prompt使用更强大的模型
        if prompt_length < 500:
            selected_model = "ollama"
        elif prompt_length < 2000:
            selected_model = "zhipu"
        else:
            selected_model = "claude"
        
        logger.info(f"[MODEL_SELECT] 根据prompt长度选择模型 | prompt_length={prompt_length} | selected={selected_model}")
        
        return await self.routers[selected_model].route(prompt)
    
    def get_router_type(self) -> str:
        return "multi"


# 模型路由器注册表
MODEL_ROUTER_REGISTRY = {
    "ollama": OllamaRouter,
    "openai": OpenAIRouter,
    "claude": ClaudeRouter,
    "zhipu": ZhipuRouter,
    "moonshot": MoonshotRouter,
    "deepseek": DeepSeekRouter,
    "multi": MultiModelRouter
}


# 便捷函数
async def select_model(model_type: str = None, model_variant: str = None) -> ModelRouterBase:
    """选择模型路由器
    
    Args:
        model_type: 模型类型（如 intent_classification, general）
        model_variant: 模型变体（如 simple, medium, complex）
    """
    router_type = model_type or settings.MODEL_ROUTER_TYPE
    
    if router_type in MODEL_ROUTER_REGISTRY:
        logger.debug(f"[ROUTER_SELECT] 选择模型路由 | type={router_type} | variant={model_variant}")
        return MODEL_ROUTER_REGISTRY[router_type]()
    else:
        logger.warning(f"[ROUTER_SELECT] 未找到模型路由类型: {router_type}，使用默认Ollama")
        return OllamaRouter()


async def call_model(prompt: str, model_type: str = None) -> str:
    """调用模型生成响应"""
    router = await select_model(model_type)
    return await router.route(prompt, model_type)