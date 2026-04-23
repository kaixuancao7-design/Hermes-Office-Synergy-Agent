"""
重排器模块：支持多种重排策略

重排是检索流程的最后一步，用于对召回结果进行精排，提升最终相关性。
支持的重排方法：
1. Cross-Encoder：使用专门的重排模型（如BAAI/bge-reranker）
2. LLM Reranking：使用大语言模型进行精排
3. Linear Reranking：线性融合分数（基线方法）
"""

import asyncio
from typing import List, Dict, Tuple, Optional, Any

try:
    from utils.logger_handler import logger
except ImportError:
    from src.logging_config import get_logger
    logger = get_logger("reranker")


class BaseReranker:
    """重排器抽象基类"""
    
    def rerank(self, query: str, candidates: List[Tuple[str, Any]], top_k: int = 5) -> List[Tuple[str, Any]]:
        """
        对候选文档进行重排
        
        :param query: 用户查询
        :param candidates: 候选文档列表，格式为[(doc_id, {'score': float, 'content': str, ...}), ...]
        :param top_k: 返回前K个结果
        :return: 重排后的文档列表
        """
        raise NotImplementedError


class LinearReranker(BaseReranker):
    """线性重排器：基于预定义规则的线性融合"""
    
    def __init__(self, original_weight: float = 0.7, length_weight: float = 0.2, keyword_weight: float = 0.1):
        """
        :param original_weight: 原始分数权重
        :param length_weight: 文档长度权重（偏好适中长度）
        :param keyword_weight: 关键词匹配权重
        """
        self.original_weight = original_weight
        self.length_weight = length_weight
        self.keyword_weight = keyword_weight
    
    def rerank(self, query: str, candidates: List[Tuple[str, Any]], top_k: int = 5) -> List[Tuple[str, Any]]:
        """基于规则的线性重排"""
        if not candidates:
            return []
        
        query_keywords = set(query.lower().split())
        results = []
        
        for doc_id, doc_info in candidates:
            # 原始分数
            original_score = doc_info.get('score', 0.0)
            
            # 长度分数：偏好长度适中的文档（200-500字）
            content = doc_info.get('content', '')
            length = len(content)
            if 200 <= length <= 500:
                length_score = 1.0
            elif length < 200:
                length_score = length / 200
            else:
                length_score = 500 / length
            
            # 关键词匹配分数
            content_lower = content.lower()
            keyword_matches = sum(1 for kw in query_keywords if kw in content_lower)
            keyword_score = keyword_matches / max(len(query_keywords), 1)
            
            # 线性融合
            final_score = (self.original_weight * original_score +
                         self.length_weight * length_score +
                         self.keyword_weight * keyword_score)
            
            results.append((doc_id, {**doc_info, 'rerank_score': final_score}))
        
        # 按重排分数排序
        results.sort(key=lambda x: x[1].get('rerank_score', 0.0), reverse=True)
        
        return results[:top_k]


class CrossEncoderReranker(BaseReranker):
    """Cross-Encoder重排器：使用专门的重排模型"""
    
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        """
        :param model_name: Cross-Encoder模型名称
        """
        self.model_name = model_name
        self._model = None
        self._tokenizer = None
        self._load_model()
    
    def _load_model(self):
        """延迟加载模型"""
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            logger.info(f"[CrossEncoderReranker] 加载模型: {self.model_name}")
        except ImportError:
            logger.warning("[CrossEncoderReranker] sentence_transformers 未安装，将使用线性重排")
            self._model = None
        except Exception as e:
            logger.error(f"[CrossEncoderReranker] 加载模型失败: {e}")
            self._model = None
    
    def rerank(self, query: str, candidates: List[Tuple[str, Any]], top_k: int = 5) -> List[Tuple[str, Any]]:
        """使用Cross-Encoder模型进行重排"""
        if not candidates or self._model is None:
            # 降级到线性重排
            return LinearReranker().rerank(query, candidates, top_k)
        
        try:
            # 构建配对数据
            pairs = [(query, doc_info.get('content', '')) for _, doc_info in candidates]
            
            # 预测相关性分数
            scores = self._model.predict(pairs)
            
            # 组合结果
            results = []
            for i, (doc_id, doc_info) in enumerate(candidates):
                results.append((doc_id, {**doc_info, 'rerank_score': float(scores[i])}))
            
            # 按分数排序
            results.sort(key=lambda x: x[1].get('rerank_score', 0.0), reverse=True)
            
            return results[:top_k]
        
        except Exception as e:
            logger.error(f"[CrossEncoderReranker] 重排失败: {e}")
            return LinearReranker().rerank(query, candidates, top_k)


class BM25Reranker(BaseReranker):
    """BM25重排器：使用项目自身的BM25索引实现重排序"""
    
    def __init__(self):
        """初始化BM25重排器"""
        self._bm25_index = None
        self._load_bm25_index()
    
    def _load_bm25_index(self):
        """加载BM25索引模块"""
        try:
            from .bm25_index import BM25Index
            self._bm25_index = BM25Index()
            logger.info("[BM25Reranker] BM25索引加载成功")
        except ImportError:
            logger.warning("[BM25Reranker] BM25索引模块未找到")
            self._bm25_index = None
        except Exception as e:
            logger.error(f"[BM25Reranker] 加载BM25索引失败: {e}")
            self._bm25_index = None
    
    def rerank(self, query: str, candidates: List[Tuple[str, Any]], top_k: int = 5) -> List[Tuple[str, Any]]:
        """使用BM25算法进行重排序"""
        if not candidates or self._bm25_index is None:
            # 降级到线性重排
            return LinearReranker().rerank(query, candidates, top_k)
        
        try:
            # 导入BM25Index（延迟导入避免循环依赖）
            from .bm25_index import BM25Index
            
            # 临时将候选文档添加到BM25索引进行重排序
            temp_index = BM25Index()
            for doc_id, doc_info in candidates:
                content = doc_info.get('content', '')
                temp_index.add_document(doc_id, content)
            
            # 搜索并获取BM25分数
            results = temp_index.search(query, top_k=len(candidates))
            
            # 构建分数映射
            score_map = {doc_id: score for doc_id, score in results}
            
            # 重新排序候选文档
            scored_docs = []
            for doc_id, doc_info in candidates:
                bm25_score = score_map.get(doc_id, 0.0)
                scored_docs.append((doc_id, {**doc_info, 'rerank_score': bm25_score}))
            
            # 按BM25分数排序
            scored_docs.sort(key=lambda x: x[1].get('rerank_score', 0.0), reverse=True)
            
            return scored_docs[:top_k]
        
        except Exception as e:
            logger.error(f"[BM25Reranker] 重排失败: {e}")
            return LinearReranker().rerank(query, candidates, top_k)


class LLM_Reranker(BaseReranker):
    """LLM重排器：使用大语言模型进行精排"""
    
    def __init__(self, llm_client=None):
        """
        :param llm_client: LLM客户端实例（如果为None，将使用默认客户端）
        """
        self.llm_client = llm_client
        if llm_client is None:
            self._init_default_client()
    
    def _init_default_client(self):
        """初始化默认LLM客户端"""
        try:
            from model.factory import chat_model
            self.llm_client = chat_model
            logger.info("[LLM_Reranker] 使用默认LLM客户端")
        except Exception as e:
            logger.error(f"[LLM_Reranker] 初始化客户端失败: {e}")
            self.llm_client = None
    
    def _build_rerank_prompt(self, query: str, candidates: List[Tuple[str, Any]]) -> str:
        """构建重排提示词"""
        prompt = f"""
你是一个文档重排专家。请根据与查询的相关性对以下文档进行排序。

查询：{query}

文档列表：
"""
        for i, (doc_id, doc_info) in enumerate(candidates, 1):
            content = doc_info.get('content', '')[:500]  # 限制长度
            prompt += f"{i}. 文档ID: {doc_id}\n内容摘要: {content}\n\n"
        
        prompt += """
请按照与查询的相关性从高到低返回文档ID列表，用逗号分隔。只需返回ID列表，不要添加其他内容。
例如：doc1, doc3, doc2
"""
        return prompt.strip()
    
    def rerank(self, query: str, candidates: List[Tuple[str, Any]], top_k: int = 5) -> List[Tuple[str, Any]]:
        """使用LLM进行重排"""
        if not candidates or self.llm_client is None:
            # 降级到线性重排
            return LinearReranker().rerank(query, candidates, top_k)
        
        try:
            # 构建提示词
            prompt = self._build_rerank_prompt(query, candidates)
            
            # 调用LLM
            if hasattr(self.llm_client, 'generate'):
                response = self.llm_client.generate(prompt)
            elif hasattr(self.llm_client, 'chat'):
                response = self.llm_client.chat([{"role": "user", "content": prompt}])
            else:
                # 尝试直接调用（兼容langchain等）
                response = str(self.llm_client.invoke(prompt))
            
            # 解析结果
            ranked_ids = [id.strip() for id in response.split(',')]
            
            # 重新排序
            id_to_doc = {doc_id: doc_info for doc_id, doc_info in candidates}
            results = []
            for doc_id in ranked_ids:
                doc_id = doc_id.strip()
                if doc_id in id_to_doc:
                    results.append((doc_id, {**id_to_doc[doc_id], 'rerank_score': 1.0}))
            
            # 补充未在结果中的文档
            for doc_id, doc_info in candidates:
                if doc_id not in [r[0] for r in results]:
                    results.append((doc_id, {**doc_info, 'rerank_score': 0.5}))
            
            return results[:top_k]
        
        except Exception as e:
            logger.error(f"[LLM_Reranker] 重排失败: {e}")
            return LinearReranker().rerank(query, candidates, top_k)


class RerankerFactory:
    """重排器工厂类"""
    
    @staticmethod
    def create(method: str = "linear", **kwargs) -> BaseReranker:
        """
        创建重排器实例
        
        :param method: 重排方法 (linear/cross_encoder/llm/bm25)
        :param kwargs: 额外参数
        :return: 重排器实例
        """
        method = method.lower().strip()
        
        if method == "cross_encoder":
            model_name = kwargs.get("model_name", "BAAI/bge-reranker-base")
            return CrossEncoderReranker(model_name)
        elif method == "llm":
            llm_client = kwargs.get("llm_client", None)
            return LLM_Reranker(llm_client)
        elif method == "bm25":
            return BM25Reranker()
        elif method == "linear":
            return LinearReranker()
        else:
            logger.warning(f"未知重排方法: {method}，使用线性重排")
            return LinearReranker()


# 全局重排器实例
_global_reranker = None


def get_reranker(method: str = "linear", **kwargs) -> BaseReranker:
    """获取全局重排器实例"""
    global _global_reranker
    if _global_reranker is None:
        _global_reranker = RerankerFactory.create(method, **kwargs)
    return _global_reranker
