"""向量存储模块 — 内存关键词搜索 + 可选的 AdvancedRetrieval 重排序管道

基础搜索：关键词匹配（BM25评分），零外部依赖，始终可用。
高级搜索：通过 use_advanced=True 启用 AdvancedRetrieval 管道（重排序、过滤）。
"""

import re
from typing import List, Dict, Any, Optional
from src.logging_config import get_logger

logger = get_logger("vector")


class VectorStore:
    """向量存储 — 内存文档索引 + 关键词搜索

    对每个查询执行关键词匹配评分，返回按相关性排序的结果。
    当 use_advanced=True 时，将结果送入 AdvancedRetrieval 管道。
    """

    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self._advanced_retrieval = None  # 延迟初始化
        logger.info("[VECTOR] VectorStore initialized (in-memory keyword search)")

    def _get_advanced_retrieval(self):
        """延迟加载 AdvancedRetrieval（避免循环导入）"""
        if self._advanced_retrieval is None:
            try:
                from src.data.advanced_retrieval import default_retrieval
                self._advanced_retrieval = default_retrieval
                logger.info("[VECTOR] AdvancedRetrieval pipeline loaded")
            except ImportError as e:
                logger.warning(f"[VECTOR] AdvancedRetrieval unavailable: {e}")
                self._advanced_retrieval = False  # mark as tried
        return self._advanced_retrieval if self._advanced_retrieval is not False else None

    # ---- 核心搜索 ----

    def search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict] = None,
        use_advanced: bool = False,
    ) -> List[Dict[str, Any]]:
        """搜索文档 — 关键词评分 + 可选高级重排序

        Args:
            query: 搜索查询
            k: 返回结果数
            filter: 可选的元数据过滤条件（如 {"user_id": "xxx"}）
            use_advanced: 是否启用 AdvancedRetrieval 重排序管道

        Returns:
            按相关性排序的文档列表，每个文档包含 content, metadata, score 等字段
        """
        if not self.documents:
            logger.debug(f"[VECTOR] No documents indexed, query='{query[:30]}'")
            return []

        # 1. 关键词评分（简易 BM25-like）
        query_terms = self._tokenize(query)
        scored = []

        for idx, doc in enumerate(self.documents):
            # 元数据过滤
            if filter:
                doc_meta = doc.get("metadata", {})
                if not self._match_filter(doc_meta, filter):
                    continue

            content = doc.get("content", "")
            score = self._score_document(query_terms, content)
            if score > 0:
                scored.append({
                    "id": doc.get("id", str(idx)),
                    "content": content,
                    "metadata": doc.get("metadata", {}),
                    "score": score,
                    "distance": 1.0 / (1.0 + score),  # 转换为距离（越小越相关）
                })

        # 按 score 降序
        scored.sort(key=lambda x: x["score"], reverse=True)

        # 2. 可选：高级检索管道
        if use_advanced and scored:
            pipeline = self._get_advanced_retrieval()
            if pipeline:
                try:
                    scored = pipeline.process(query, scored)
                    logger.debug(f"[VECTOR] Advanced retrieval: {len(scored)} results after pipeline")
                except Exception as e:
                    logger.warning(f"[VECTOR] Advanced retrieval failed: {e}, returning raw results")

        logger.info(f"[VECTOR] Search: query='{query[:30]}' → {min(k, len(scored))}/{len(scored)} results")
        return scored[:k]

    # ---- 文档管理 ----

    def add_document(self, user_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """添加单个文档"""
        meta = dict(metadata or {})
        meta.setdefault("user_id", user_id)
        self.documents.append({
            "id": str(len(self.documents)),
            "content": content,
            "metadata": meta,
        })

    def add_large_document(self, content: str, metadata: Dict[str, Any]):
        """添加大文档（自动分块）"""
        chunks = self._chunk_text(content)
        for i, chunk in enumerate(chunks):
            chunk_meta = dict(metadata or {})
            chunk_meta["chunk_index"] = i
            chunk_meta["total_chunks"] = len(chunks)
            self.documents.append({
                "id": str(len(self.documents)),
                "content": chunk,
                "metadata": chunk_meta,
            })
        logger.info(f"[VECTOR] Added large doc: {len(chunks)} chunks, metadata={list(metadata.keys()) if metadata else 'none'}")

    def add_vector(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """添加向量（兼容函数，等同于 add_document）"""
        self.documents.append({
            "id": str(len(self.documents)),
            "content": content,
            "metadata": dict(metadata or {}),
        })

    def clear(self):
        """清空所有文档"""
        self.documents.clear()

    def count(self) -> int:
        """已索引文档数"""
        return len(self.documents)

    # ---- 内部辅助 ----

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """中文友好分词"""
        if not text:
            return []
        # 提取中文字符、英文单词、数字组合
        return [t.lower() for t in re.findall(r'[\w一-鿿]+', str(text))]

    @staticmethod
    def _score_document(query_terms: List[str], content: str) -> float:
        """计算文档与查询的相关性分数"""
        if not query_terms or not content:
            return 0.0
        content_lower = content.lower()
        score = 0.0
        for term in query_terms:
            # 精确匹配加分
            count = content_lower.count(term)
            if count > 0:
                # IDF-like: 短词匹配权重较低
                term_weight = min(1.0, len(term) / 4.0)
                score += count * term_weight
        return score

    @staticmethod
    def _match_filter(doc_meta: Dict, filter_dict: Dict) -> bool:
        """检查文档元数据是否匹配过滤条件"""
        for key, value in filter_dict.items():
            if doc_meta.get(key) != value:
                return False
        return True

    @staticmethod
    def _chunk_text(text: str, max_chars: int = 2000) -> List[str]:
        """将长文本拆分为多个块（按段落边界）"""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        current = ""
        for para in paragraphs:
            if len(current) + len(para) < max_chars:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    chunks.append(current)
                current = para
        if current:
            chunks.append(current)
        return chunks if chunks else [text]


# 全局实例
vector_store = VectorStore()


# ---- RAG 管理器（兼容导出） ----
class RAGManager:
    """RAG 查询管理器 — 对 vector_store 的薄封装

    保留此类的目的是兼容现有调用方（如在 message_router.py 中通过
    `from src.data.vector_store import rag_manager` 引用）。
    """

    def query(self, query: str, k: int = 5, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        filter_dict = {"user_id": user_id} if user_id else None
        return vector_store.search(query, k=k, filter=filter_dict, use_advanced=False)

    def advanced_query(self, query: str, k: int = 5, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        filter_dict = {"user_id": user_id} if user_id else None
        return vector_store.search(query, k=k, filter=filter_dict, use_advanced=True)


rag_manager = RAGManager()
