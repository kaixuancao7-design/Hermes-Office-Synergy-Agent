"""Embedding服务插件实现"""
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
from src.config import settings
from src.logging_config import get_logger

logger = get_logger("embedding")

# Embedding服务注册表
EMBEDDING_SERVICE_REGISTRY: Dict[str, 'EmbeddingServiceBase'] = {}


def register_embedding_service(name: str, service_class: 'EmbeddingServiceBase') -> None:
    """注册Embedding服务"""
    EMBEDDING_SERVICE_REGISTRY[name] = service_class


def get_embedding_service(name: Optional[str] = None) -> Optional['EmbeddingServiceBase']:
    """获取Embedding服务实例"""
    service_name = name or settings.EMBEDDING_SERVICE_TYPE
    if service_name in EMBEDDING_SERVICE_REGISTRY:
        try:
            return EMBEDDING_SERVICE_REGISTRY[service_name]()
        except Exception as e:
            logger.error(f"创建Embedding服务失败: {service_name}, 错误: {str(e)}")
            return None
    else:
        logger.warning(f"未找到Embedding服务类型: {service_name}")
        return None


class EmbeddingServiceBase(ABC):
    """Embedding服务基类"""
    
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """对文本列表进行向量化"""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """获取向量维度"""
        pass


class DefaultChromaEmbedding(EmbeddingServiceBase):
    """默认Chroma内置Embedding服务"""
    
    def __init__(self):
        self.dimension = 384  # all-MiniLM-L6-v2 的维度
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Chroma会自动处理，这里返回空列表表示使用默认行为"""
        return []
    
    def get_dimension(self) -> int:
        return self.dimension


class OpenAIEmbedding(EmbeddingServiceBase):
    """OpenAI Embedding服务"""
    
    def __init__(self):
        self.client = None
        self.dimension = 1536  # text-embedding-3-small
        self._initialize()
    
    def _initialize(self):
        try:
            from openai import OpenAI
            if settings.OPENAI_API_KEY:
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("OpenAI Embedding服务初始化成功")
            else:
                logger.warning("未配置OPENAI_API_KEY，OpenAI Embedding不可用")
        except ImportError:
            logger.warning("openai库未安装，OpenAI Embedding不可用")
        except Exception as e:
            logger.error(f"OpenAI Embedding初始化失败: {str(e)}")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.client:
            logger.error("OpenAI Embedding客户端未初始化")
            return []
        
        try:
            response = self.client.embeddings.create(
                input=texts,
                model="text-embedding-v4"
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            logger.error(f"OpenAI Embedding调用失败: {str(e)}")
            return []
    
    def get_dimension(self) -> int:
        return self.dimension


class OllamaEmbedding(EmbeddingServiceBase):
    """Ollama本地Embedding服务"""
    
    def __init__(self):
        self.client = None
        self.dimension = 768  # 默认模型维度
        self._initialize()
    
    def _initialize(self):
        try:
            from ollama import Client
            self.client = Client(host=settings.OLLAMA_HOST)
            logger.info("Ollama Embedding服务初始化成功")
        except ImportError:
            logger.warning("ollama库未安装，Ollama Embedding不可用")
        except Exception as e:
            logger.error(f"Ollama Embedding初始化失败: {str(e)}")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.client:
            logger.error("Ollama Embedding客户端未初始化")
            return []
        
        try:
            results = []
            for text in texts:
                response = self.client.embeddings(
                    model="Mxbai-embed-large",
                    prompt=text
                )
                results.append(response["embedding"])
            return results
        except Exception as e:
            logger.error(f"Ollama Embedding调用失败: {str(e)}")
            return []
    
    def get_dimension(self) -> int:
        return self.dimension


class SentenceTransformerEmbedding(EmbeddingServiceBase):
    """Sentence Transformers本地Embedding服务"""
    
    def __init__(self):
        self.model = None
        self.dimension = 384
        self._initialize()
    
    def _initialize(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"SentenceTransformer Embedding服务初始化成功，维度: {self.dimension}")
        except ImportError:
            logger.warning("sentence_transformers库未安装，SentenceTransformer Embedding不可用")
        except Exception as e:
            logger.error(f"SentenceTransformer Embedding初始化失败: {str(e)}")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.model:
            logger.error("SentenceTransformer模型未初始化")
            return []
        
        try:
            embeddings = self.model.encode(texts)
            return embeddings.tolist() if hasattr(embeddings, 'tolist') else embeddings
        except Exception as e:
            logger.error(f"SentenceTransformer Embedding调用失败: {str(e)}")
            return []
    
    def get_dimension(self) -> int:
        return self.dimension


class ZhipuEmbedding(EmbeddingServiceBase):
    """智谱AI Embedding服务"""
    
    def __init__(self):
        self.client = None
        self.dimension = 1024  # text-embedding-1
        self._initialize()
    
    def _initialize(self):
        try:
            from zhipuai import ZhipuAI
            if settings.ZHIPU_API_KEY:
                self.client = ZhipuAI(api_key=settings.ZHIPU_API_KEY)
                logger.info("ZhipuAI Embedding服务初始化成功")
            else:
                logger.warning("未配置ZHIPU_API_KEY，ZhipuAI Embedding不可用")
        except ImportError:
            logger.warning("zhipuai库未安装，ZhipuAI Embedding不可用")
        except Exception as e:
            logger.error(f"ZhipuAI Embedding初始化失败: {str(e)}")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.client:
            logger.error("ZhipuAI Embedding客户端未初始化")
            return []
        
        try:
            response = self.client.embeddings.create(
                model="text-embedding-1",
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"ZhipuAI Embedding调用失败: {str(e)}")
            return []
    
    def get_dimension(self) -> int:
        return self.dimension


class MoonshotEmbedding(EmbeddingServiceBase):
    """Moonshot AI Embedding服务"""
    
    def __init__(self):
        self.client = None
        self.dimension = 1024  # moonshot-embed
        self._initialize()
    
    def _initialize(self):
        try:
            from openai import OpenAI
            if settings.MOONSHOT_API_KEY:
                self.client = OpenAI(
                    api_key=settings.MOONSHOT_API_KEY,
                    base_url="https://api.moonshot.cn/v1"
                )
                logger.info("Moonshot Embedding服务初始化成功")
            else:
                logger.warning("未配置MOONSHOT_API_KEY，Moonshot Embedding不可用")
        except ImportError:
            logger.warning("openai库未安装，Moonshot Embedding不可用")
        except Exception as e:
            logger.error(f"Moonshot Embedding初始化失败: {str(e)}")
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.client:
            logger.error("Moonshot Embedding客户端未初始化")
            return []
        
        try:
            response = self.client.embeddings.create(
                model="moonshot-embed",
                input=texts
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            logger.error(f"Moonshot Embedding调用失败: {str(e)}")
            return []
    
    def get_dimension(self) -> int:
        return self.dimension


# 注册所有Embedding服务
register_embedding_service("default", DefaultChromaEmbedding)
register_embedding_service("openai", OpenAIEmbedding)
register_embedding_service("ollama", OllamaEmbedding)
register_embedding_service("sentence_transformer", SentenceTransformerEmbedding)
register_embedding_service("zhipu", ZhipuEmbedding)
register_embedding_service("moonshot", MoonshotEmbedding)
