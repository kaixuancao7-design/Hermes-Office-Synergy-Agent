"""高级检索优化 - 提供重排序、过滤等高级检索策略"""
import re
from typing import List, Dict, Any, Optional, Callable
from abc import ABC, abstractmethod
from functools import partial

from src.config import settings
from src.logging_config import get_logger

logger = get_logger("retrieval")


class FilterStrategyBase(ABC):
    """过滤策略基类"""
    
    @abstractmethod
    def filter(self, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """过滤文档"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """获取策略名称"""
        pass


class KeywordFilter(FilterStrategyBase):
    """关键词过滤器"""
    
    def __init__(self, keywords: List[str], mode: str = "include"):
        """
        初始化关键词过滤器
        
        Args:
            keywords: 关键词列表
            mode: 过滤模式，"include"包含关键词，"exclude"排除关键词
        """
        self.keywords = [k.lower() for k in keywords]
        self.mode = mode
    
    def filter(self, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        filtered = []
        
        for doc in documents:
            content = doc.get("content", "").lower()
            contains_keyword = any(keyword in content for keyword in self.keywords)
            
            if self.mode == "include" and contains_keyword:
                filtered.append(doc)
            elif self.mode == "exclude" and not contains_keyword:
                filtered.append(doc)
        
        return filtered
    
    def get_name(self) -> str:
        return f"keyword_filter_{self.mode}"


class DateFilter(FilterStrategyBase):
    """日期过滤器"""
    
    def __init__(self, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """
        初始化日期过滤器
        
        Args:
            start_date: 开始日期（格式：YYYY-MM-DD）
            end_date: 结束日期（格式：YYYY-MM-DD）
        """
        self.start_date = start_date
        self.end_date = end_date
    
    def filter(self, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        filtered = []
        
        for doc in documents:
            metadata = doc.get("metadata", {})
            doc_date = metadata.get("date") or metadata.get("timestamp")
            
            if doc_date:
                # 尝试解析日期
                if self.start_date and doc_date < self.start_date:
                    continue
                if self.end_date and doc_date > self.end_date:
                    continue
            
            filtered.append(doc)
        
        return filtered
    
    def get_name(self) -> str:
        return "date_filter"


class SourceFilter(FilterStrategyBase):
    """来源过滤器"""
    
    def __init__(self, sources: List[str], mode: str = "include"):
        """
        初始化来源过滤器
        
        Args:
            sources: 来源列表
            mode: 过滤模式，"include"包含来源，"exclude"排除来源
        """
        self.sources = [s.lower() for s in sources]
        self.mode = mode
    
    def filter(self, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        filtered = []
        
        for doc in documents:
            metadata = doc.get("metadata", {})
            source = (metadata.get("source") or metadata.get("file_name") or "").lower()
            
            contains_source = any(src in source for src in self.sources)
            
            if self.mode == "include" and contains_source:
                filtered.append(doc)
            elif self.mode == "exclude" and not contains_source:
                filtered.append(doc)
        
        return filtered
    
    def get_name(self) -> str:
        return f"source_filter_{self.mode}"


class LengthFilter(FilterStrategyBase):
    """长度过滤器"""
    
    def __init__(self, min_length: int = 0, max_length: int = 10000):
        """
        初始化长度过滤器
        
        Args:
            min_length: 最小长度
            max_length: 最大长度
        """
        self.min_length = min_length
        self.max_length = max_length
    
    def filter(self, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        filtered = []
        
        for doc in documents:
            content = doc.get("content", "")
            length = len(content)
            
            if self.min_length <= length <= self.max_length:
                filtered.append(doc)
        
        return filtered
    
    def get_name(self) -> str:
        return "length_filter"


class ReRankStrategyBase(ABC):
    """重排序策略基类"""
    
    @abstractmethod
    def rerank(self, query: str, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """重排序文档"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """获取策略名称"""
        pass


class BM25ReRank(ReRankStrategyBase):
    """基于BM25的重排序（使用项目自身的BM25实现）"""
    
    def __init__(self):
        self.reranker = None
        self._initialize()
    
    def _initialize(self):
        """初始化BM25重排序器"""
        try:
            from .reranker import BM25Reranker
            self.reranker = BM25Reranker()
            logger.info("BM25重排序器初始化成功（使用项目自身实现）")
        except ImportError as e:
            logger.warning(f"BM25重排序器初始化失败: {str(e)}")
    
    def rerank(self, query: str, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        if self.reranker is None:
            return documents
        
        if not documents:
            return documents
        
        try:
            # 转换格式：[(doc_id, doc_info), ...]
            candidates = [(str(i), doc) for i, doc in enumerate(documents)]
            
            # 使用BM25Reranker进行重排序
            results = self.reranker.rerank(query, candidates, top_k=len(documents))
            
            # 提取结果并转换回原格式
            scored_docs = []
            for doc_id, doc_info in results:
                doc_copy = doc_info.copy()
                doc_copy["bm25_rerank_score"] = doc_info.get("rerank_score", 0)
                scored_docs.append(doc_copy)
            
            return scored_docs
        except Exception as e:
            logger.error(f"BM25重排序失败: {str(e)}")
            return documents
    
    def get_name(self) -> str:
        return "bm25_rerank"


class CrossEncoderReRank(ReRankStrategyBase):
    """基于CrossEncoder的重排序"""
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.initialized = False
        self.model = None
        self.tokenizer = None
        self.model_name = model_name
        self._initialize()
    
    def _initialize(self):
        """初始化CrossEncoder模型"""
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name)
            self.initialized = True
            logger.info("CrossEncoder重排序器初始化成功")
        except ImportError:
            logger.warning("sentence_transformers库未安装，CrossEncoder重排序不可用")
        except Exception as e:
            logger.error(f"CrossEncoder初始化失败: {str(e)}")
    
    def rerank(self, query: str, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        if not self.initialized:
            return documents
        
        if not documents:
            return documents
        
        try:
            # 准备(query, document)对
            pairs = [(query, doc.get("content", "")) for doc in documents]
            
            # 预测分数
            scores = self.model.predict(pairs)
            
            # 添加分数并重排序
            scored_docs = []
            for doc, score in zip(documents, scores):
                doc_copy = doc.copy()
                doc_copy["cross_encoder_score"] = score
                scored_docs.append(doc_copy)
            
            # 按分数降序排序
            scored_docs.sort(key=lambda x: x.get("cross_encoder_score", 0), reverse=True)
            
            return scored_docs
        except Exception as e:
            logger.error(f"CrossEncoder重排序失败: {str(e)}")
            return documents
    
    def get_name(self) -> str:
        return "cross_encoder_rerank"


class HybridReRank(ReRankStrategyBase):
    """混合重排序策略"""
    
    def __init__(self, strategies: List[ReRankStrategyBase], weights: Optional[List[float]] = None):
        """
        初始化混合重排序策略
        
        Args:
            strategies: 重排序策略列表
            weights: 各策略的权重（可选，默认等权重）
        """
        self.strategies = strategies
        self.weights = weights or [1.0 / len(strategies)] * len(strategies)
    
    def rerank(self, query: str, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        if not self.strategies or not documents:
            return documents
        
        try:
            # 收集各策略的分数
            all_scores = []
            
            for strategy in self.strategies:
                scored_docs = strategy.rerank(query, documents.copy(), **kwargs)
                strategy_name = strategy.get_name()
                
                # 提取分数
                scores = []
                for doc in scored_docs:
                    score_key = f"{strategy_name}_score"
                    scores.append(doc.get(score_key, 0))
                
                all_scores.append(scores)
            
            # 计算加权总分
            scored_docs = []
            for doc_idx, doc in enumerate(documents):
                total_score = sum(
                    weight * all_scores[strategy_idx][doc_idx]
                    for strategy_idx, weight in enumerate(self.weights)
                )
                
                doc_copy = doc.copy()
                doc_copy["hybrid_score"] = total_score
                
                # 添加各策略的分数
                for strategy_idx, strategy in enumerate(self.strategies):
                    score_key = f"{strategy.get_name()}_score"
                    doc_copy[score_key] = all_scores[strategy_idx][doc_idx]
                
                scored_docs.append(doc_copy)
            
            # 按混合分数降序排序
            scored_docs.sort(key=lambda x: x.get("hybrid_score", 0), reverse=True)
            
            return scored_docs
        except Exception as e:
            logger.error(f"混合重排序失败: {str(e)}")
            return documents
    
    def get_name(self) -> str:
        return "hybrid_rerank"


class RecencyBoost(ReRankStrategyBase):
    """时效性增强重排序"""
    
    def __init__(self, decay_rate: float = 0.1):
        """
        初始化时效性增强重排序
        
        Args:
            decay_rate: 衰减率（每天的权重衰减）
        """
        self.decay_rate = decay_rate
    
    def rerank(self, query: str, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        from datetime import datetime
        
        if not documents:
            return documents
        
        try:
            now = datetime.now()
            scored_docs = []
            
            for doc in documents:
                metadata = doc.get("metadata", {})
                doc_date_str = metadata.get("date") or metadata.get("timestamp")
                
                # 计算时效性分数
                recency_score = 1.0
                
                if doc_date_str:
                    try:
                        # 尝试解析日期
                        doc_date = datetime.fromisoformat(doc_date_str.replace("Z", "+00:00"))
                        days_diff = (now - doc_date).days
                        recency_score = max(0.1, 1.0 - days_diff * self.decay_rate)
                    except:
                        pass
                
                # 获取原始相似度分数
                original_score = doc.get("distance", 0)
                
                # 混合分数（假设原始分数越小越好）
                hybrid_score = (1.0 - original_score) * recency_score
                
                doc_copy = doc.copy()
                doc_copy["recency_score"] = recency_score
                doc_copy["recency_boosted_score"] = hybrid_score
                
                scored_docs.append(doc_copy)
            
            # 按增强后的分数降序排序
            scored_docs.sort(key=lambda x: x.get("recency_boosted_score", 0), reverse=True)
            
            return scored_docs
        except Exception as e:
            logger.error(f"时效性增强重排序失败: {str(e)}")
            return documents
    
    def get_name(self) -> str:
        return "recency_boost"


class AdvancedRetrieval:
    """高级检索器"""
    
    def __init__(self):
        self.filters: List[FilterStrategyBase] = []
        self.rerank_strategy: Optional[ReRankStrategyBase] = None
    
    def add_filter(self, filter_strategy: FilterStrategyBase):
        """添加过滤器"""
        self.filters.append(filter_strategy)
    
    def set_rerank_strategy(self, strategy: ReRankStrategyBase):
        """设置重排序策略"""
        self.rerank_strategy = strategy
    
    def process(self, query: str, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """
        执行高级检索流程
        
        Args:
            query: 查询文本
            documents: 原始检索结果
            kwargs: 额外参数
        
        Returns:
            处理后的文档列表
        """
        # 1. 应用过滤器
        filtered_docs = documents
        
        for filter_strategy in self.filters:
            filtered_docs = filter_strategy.filter(filtered_docs, **kwargs)
            if not filtered_docs:
                break
        
        # 2. 应用重排序
        if self.rerank_strategy:
            filtered_docs = self.rerank_strategy.rerank(query, filtered_docs, **kwargs)
        
        return filtered_docs
    
    def clear_filters(self):
        """清空所有过滤器"""
        self.filters = []
    
    def create_pipeline(self, filters: Optional[List[FilterStrategyBase]] = None,
                       rerank_strategy: Optional[ReRankStrategyBase] = None):
        """
        创建检索管道
        
        Args:
            filters: 过滤器列表
            rerank_strategy: 重排序策略
        """
        if filters:
            self.filters = filters
        
        if rerank_strategy:
            self.rerank_strategy = rerank_strategy


# 便捷函数和预设配置
def create_default_retrieval_pipeline() -> AdvancedRetrieval:
    """创建默认检索管道"""
    retrieval = AdvancedRetrieval()
    
    # 添加基本过滤器
    retrieval.add_filter(LengthFilter(min_length=10, max_length=10000))
    
    # 设置混合重排序策略
    strategies = [BM25ReRank(), RecencyBoost()]
    retrieval.set_rerank_strategy(HybridReRank(strategies, weights=[0.7, 0.3]))
    
    return retrieval


def create_enterprise_retrieval_pipeline() -> AdvancedRetrieval:
    """创建企业级检索管道"""
    retrieval = AdvancedRetrieval()
    
    # 添加多种过滤器
    retrieval.add_filter(LengthFilter(min_length=20, max_length=5000))
    
    # 设置更高级的重排序策略
    strategies = [BM25ReRank(), CrossEncoderReRank(), RecencyBoost()]
    retrieval.set_rerank_strategy(HybridReRank(strategies, weights=[0.3, 0.5, 0.2]))
    
    return retrieval


# 全局实例
default_retrieval = create_default_retrieval_pipeline()
enterprise_retrieval = create_enterprise_retrieval_pipeline()


# 便捷函数
def advanced_search(query: str, documents: List[Dict[str, Any]],
                   filters: Optional[List[FilterStrategyBase]] = None,
                   rerank_strategy: Optional[ReRankStrategyBase] = None) -> List[Dict[str, Any]]:
    """
    执行高级检索
    
    Args:
        query: 查询文本
        documents: 原始检索结果
        filters: 过滤器列表（可选）
        rerank_strategy: 重排序策略（可选）
    
    Returns:
        处理后的文档列表
    """
    retrieval = AdvancedRetrieval()
    
    if filters:
        for f in filters:
            retrieval.add_filter(f)
    
    if rerank_strategy:
        retrieval.set_rerank_strategy(rerank_strategy)
    
    return retrieval.process(query, documents)
