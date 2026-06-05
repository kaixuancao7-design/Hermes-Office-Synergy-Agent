"""重排序器 — BM25 / 混合评分实现

为 AdvancedRetrieval 管道提供 BM25 重排序能力。
BM25Reranker 使用纯 Python 实现，无需外部依赖。
"""

import math
from typing import List, Dict, Any, Tuple
from src.logging_config import get_logger

logger = get_logger("retrieval")


class BM25Reranker:
    """BM25 重排序器 — 对召回文档按关键词相关性重新排序

    使用 BM25 算法评估 query 与每个文档的相关性分数，
    按分数降序排列返回。
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        if not text:
            return []
        # 按空格和常见标点分词
        import re
        return [t.lower() for t in re.findall(r'[\w一-鿿]+', str(text))]

    def rerank(
        self, query: str, candidates: List[Tuple[str, Dict[str, Any]]],
        top_k: int = 10
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """对候选文档进行 BM25 重排序

        Args:
            query: 查询文本
            candidates: [(doc_id, doc_info), ...], doc_info 需含 "content" 字段
            top_k: 返回的最大文档数

        Returns:
            按 BM25 分数降序排列的 (doc_id, doc_info) 列表
        """
        if not candidates:
            return []

        query_terms = self._tokenize(query)
        if not query_terms:
            return candidates[:top_k]

        # 构建文档语料
        docs = []
        for doc_id, doc_info in candidates:
            content = doc_info.get("content", "")
            terms = self._tokenize(content)
            docs.append({"id": doc_id, "info": doc_info, "terms": terms})

        if not docs:
            return candidates[:top_k]

        # 计算 IDF
        N = len(docs)
        avgdl = sum(len(d["terms"]) for d in docs) / N if N > 0 else 1
        idf = {}
        for term in set(query_terms):
            df = sum(1 for d in docs if term in d["terms"])
            idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1)

        # 计算每个文档的 BM25 分数
        scored = []
        for d in docs:
            dl = len(d["terms"])
            score = 0.0
            term_freq = {}
            for t in d["terms"]:
                term_freq[t] = term_freq.get(t, 0) + 1

            for term in query_terms:
                if term in idf:
                    tf = term_freq.get(term, 0)
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * dl / avgdl)
                    score += idf[term] * numerator / denominator if denominator > 0 else 0

            d["info"]["bm25_score"] = score
            d["info"]["rerank_score"] = score
            scored.append((d["id"], d["info"]))

        scored.sort(key=lambda x: x[1].get("bm25_score", 0), reverse=True)
        return scored[:top_k]
