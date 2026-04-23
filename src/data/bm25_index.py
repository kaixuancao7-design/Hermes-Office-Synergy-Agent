"""BM25索引模块 - 用于构建和查询BM25倒排索引，支持IDF统计信息"""
import os
import pickle
import math
import sqlite3
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

from src.config import settings
from src.logging_config import get_logger

logger = get_logger("bm25")


class BM25Index:
    def __init__(self, index_path: str = None, use_sqlite: bool = False):
        """
        初始化BM25索引
        
        Args:
            index_path: 索引存储路径
            use_sqlite: 是否使用SQLite存储（默认pickle）
        """
        self.use_sqlite = use_sqlite
        
        if index_path:
            self.index_path = index_path
        elif self.use_sqlite:
            self.index_path = os.path.join(settings.VECTOR_DB_PATH, "bm25_index.db")
        else:
            self.index_path = os.path.join(settings.VECTOR_DB_PATH, "bm25_index.pkl")
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        
        self.inverted_index: Dict[str, List[Tuple[str, int]]] = defaultdict(list)  # term -> [(doc_id, freq), ...]
        self.doc_lengths: Dict[str, int] = {}  # doc_id -> length
        self.doc_contents: Dict[str, str] = {}  # doc_id -> content（用于查询扩展）
        self.doc_count = 0
        self.total_terms = 0
        self.avg_doc_length = 0.0
        self.idf_cache: Dict[str, float] = {}
        
        # BM25参数
        self.k1 = 1.5
        self.b = 0.75
        
        # 尝试加载已存在的索引
        self.load()
    
    def _tokenize(self, text: str) -> List[str]:
        """分词处理，优先使用jieba中文分词"""
        try:
            import jieba
            # 使用精确模式分词，过滤空白字符
            return [word for word in jieba.cut(text.lower()) if word.strip() and len(word) > 1]
        except ImportError:
            # 降级到简单分词
            import re
            # 移除特殊字符，按空白分割
            text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
            return [word for word in text.lower().split() if len(word) > 1]
    
    def add_document(self, doc_id: str, text: str, store_content: bool = False):
        """
        添加文档到索引
        
        Args:
            doc_id: 文档ID
            text: 文档内容
            store_content: 是否存储文档内容（用于查询扩展）
        """
        terms = self._tokenize(text)
        term_freq = defaultdict(int)
        for term in terms:
            term_freq[term] += 1
        
        doc_length = len(terms)
        
        # 更新文档长度和计数
        if doc_id in self.doc_lengths:
            # 如果文档已存在，先移除旧数据
            self._remove_document(doc_id)
        
        self.doc_lengths[doc_id] = doc_length
        self.doc_count += 1
        self.total_terms += doc_length
        
        # 存储内容（可选）
        if store_content:
            self.doc_contents[doc_id] = text
        
        # 更新倒排索引
        for term, freq in term_freq.items():
            self.inverted_index[term].append((doc_id, freq))
        
        # 更新平均文档长度
        self.avg_doc_length = self.total_terms / self.doc_count if self.doc_count > 0 else 0
        self.idf_cache.clear()  # 重置IDF缓存
        
        logger.debug(f"添加文档到BM25索引: doc_id={doc_id}, terms={len(terms)}")
    
    def _remove_document(self, doc_id: str):
        """从索引中移除文档（内部方法）"""
        if doc_id not in self.doc_lengths:
            return
        
        # 从倒排索引中移除
        removed_length = self.doc_lengths[doc_id]
        for term, postings in list(self.inverted_index.items()):
            new_postings = [(d, f) for d, f in postings if d != doc_id]
            if new_postings:
                self.inverted_index[term] = new_postings
            else:
                del self.inverted_index[term]
        
        # 更新元数据
        self.total_terms -= removed_length
        del self.doc_lengths[doc_id]
        if doc_id in self.doc_contents:
            del self.doc_contents[doc_id]
        self.doc_count -= 1
        self.avg_doc_length = self.total_terms / self.doc_count if self.doc_count > 0 else 0
        self.idf_cache.clear()
    
    def delete_document(self, doc_id: str):
        """删除文档"""
        if doc_id not in self.doc_lengths:
            logger.warning(f"文档不存在: {doc_id}")
            return
        
        self._remove_document(doc_id)
        logger.info(f"从BM25索引删除文档: {doc_id}")
    
    def add_documents(self, documents: List[Tuple[str, str]], store_content: bool = False):
        """
        批量添加文档
        
        Args:
            documents: 文档列表 [(doc_id, text), ...]
            store_content: 是否存储文档内容
        """
        try:
            for doc_id, text in documents:
                self.add_document(doc_id, text, store_content)
            logger.info(f"批量添加 {len(documents)} 个文档到BM25索引")
        except Exception as e:
            logger.error(f"批量添加文档失败: {str(e)}")
            raise
    
    def _idf(self, term: str) -> float:
        """计算IDF值（带平滑）"""
        if term in self.idf_cache:
            return self.idf_cache[term]
        
        df = len(self.inverted_index.get(term, []))
        if df == 0:
            idf = 0.0
        else:
            # BM25 IDF公式（带平滑）
            idf = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1.0)
        
        self.idf_cache[term] = idf
        return idf
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        搜索查询，返回(doc_id, score)列表
        
        Args:
            query: 查询文本
            top_k: 返回前k个结果
        
        Returns:
            排序后的结果列表
        """
        if self.doc_count == 0:
            return []
        
        query_terms = self._tokenize(query)
        scores = defaultdict(float)
        
        for term in query_terms:
            if term not in self.inverted_index:
                continue
            
            idf = self._idf(term)
            postings = self.inverted_index[term]
            
            for doc_id, freq in postings:
                # BM25 TF计算
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * (self.doc_lengths[doc_id] / self.avg_doc_length))
                tf = numerator / denominator
                scores[doc_id] += idf * tf
        
        # 排序并返回top_k
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_k]
    
    def search_with_expansion(self, query: str, top_k: int = 10, 
                             expand_top_n: int = 3) -> List[Tuple[str, float]]:
        """
        带查询扩展的搜索
        
        Args:
            query: 查询文本
            top_k: 返回前k个结果
            expand_top_n: 使用前n个结果进行查询扩展
        
        Returns:
            排序后的结果列表
        """
        # 先执行普通搜索
        results = self.search(query, top_k=top_k + expand_top_n)
        
        # 如果结果较少且存储了文档内容，尝试查询扩展
        if len(results) < top_k and self.doc_contents:
            # 从结果文档中提取高频词进行扩展
            expanded_terms = set(self._tokenize(query))
            
            for doc_id, _ in results[:expand_top_n]:
                if doc_id in self.doc_contents:
                    content_terms = self._tokenize(self.doc_contents[doc_id])
                    # 添加内容中的高频词
                    term_freq = defaultdict(int)
                    for term in content_terms:
                        term_freq[term] += 1
                    # 添加前5个高频词
                    for term, _ in sorted(term_freq.items(), key=lambda x: x[1], reverse=True)[:5]:
                        expanded_terms.add(term)
            
            # 使用扩展后的查询重新搜索
            expanded_query = " ".join(expanded_terms)
            results = self.search(expanded_query, top_k=top_k)
        
        return results[:top_k]
    
    def save(self):
        """保存索引到存储介质"""
        if self.use_sqlite:
            self._save_to_sqlite()
        else:
            self._save_to_pickle()
    
    def _save_to_pickle(self):
        """保存索引到pickle文件"""
        data = {
            'inverted_index': dict(self.inverted_index),
            'doc_lengths': self.doc_lengths,
            'doc_contents': self.doc_contents,
            'doc_count': self.doc_count,
            'total_terms': self.total_terms,
            'avg_doc_length': self.avg_doc_length,
            'k1': self.k1,
            'b': self.b
        }
        
        with open(self.index_path, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"BM25索引已保存到pickle: {self.index_path}")
    
    def _save_to_sqlite(self):
        """保存索引到SQLite数据库"""
        conn = sqlite3.connect(self.index_path)
        cursor = conn.cursor()
        
        # 创建表
        cursor.execute('''CREATE TABLE IF NOT EXISTS inverted_index
                          (term TEXT, doc_id TEXT, freq INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS doc_metadata
                          (doc_id TEXT PRIMARY KEY, length INTEGER, content TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS index_stats
                          (key TEXT PRIMARY KEY, value TEXT)''')
        
        # 创建索引以加速查询
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_term ON inverted_index(term)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_doc_id ON inverted_index(doc_id)')
        
        # 清空旧数据
        cursor.execute('DELETE FROM inverted_index')
        cursor.execute('DELETE FROM doc_metadata')
        cursor.execute('DELETE FROM index_stats')
        
        # 插入倒排索引数据
        for term, postings in self.inverted_index.items():
            for doc_id, freq in postings:
                cursor.execute('INSERT INTO inverted_index VALUES (?, ?, ?)', (term, doc_id, freq))
        
        # 插入文档元数据
        for doc_id, length in self.doc_lengths.items():
            content = self.doc_contents.get(doc_id, "")
            cursor.execute('INSERT INTO doc_metadata VALUES (?, ?, ?)', (doc_id, length, content))
        
        # 保存统计信息
        stats = {
            'doc_count': str(self.doc_count),
            'total_terms': str(self.total_terms),
            'avg_doc_length': str(self.avg_doc_length),
            'k1': str(self.k1),
            'b': str(self.b)
        }
        for key, value in stats.items():
            cursor.execute('INSERT INTO index_stats VALUES (?, ?)', (key, value))
        
        conn.commit()
        conn.close()
        logger.info(f"BM25索引已保存到SQLite: {self.index_path}")
    
    def load(self):
        """从存储介质加载索引"""
        if self.use_sqlite:
            self._load_from_sqlite()
        else:
            self._load_from_pickle()
    
    def _load_from_pickle(self):
        """从pickle文件加载索引"""
        if not os.path.exists(self.index_path):
            logger.debug(f"BM25索引文件不存在，创建新索引: {self.index_path}")
            return
        
        try:
            with open(self.index_path, 'rb') as f:
                data = pickle.load(f)
            
            self.inverted_index = defaultdict(list, data['inverted_index'])
            self.doc_lengths = data['doc_lengths']
            self.doc_contents = data.get('doc_contents', {})
            self.doc_count = data['doc_count']
            self.total_terms = data['total_terms']
            self.avg_doc_length = data['avg_doc_length']
            self.k1 = data.get('k1', 1.5)
            self.b = data.get('b', 0.75)
            
            logger.info(f"BM25索引已从pickle加载: {self.index_path}")
        except Exception as e:
            logger.error(f"加载BM25索引失败: {str(e)}")
    
    def _load_from_sqlite(self):
        """从SQLite数据库加载索引"""
        if not os.path.exists(self.index_path):
            logger.debug(f"BM25 SQLite数据库不存在，创建新索引: {self.index_path}")
            return
        
        try:
            conn = sqlite3.connect(self.index_path)
            cursor = conn.cursor()
            
            # 加载倒排索引
            cursor.execute('SELECT term, doc_id, freq FROM inverted_index')
            for term, doc_id, freq in cursor.fetchall():
                self.inverted_index[term].append((doc_id, freq))
            
            # 加载文档元数据
            cursor.execute('SELECT doc_id, length, content FROM doc_metadata')
            for doc_id, length, content in cursor.fetchall():
                self.doc_lengths[doc_id] = length
                if content:
                    self.doc_contents[doc_id] = content
            
            # 加载统计信息
            cursor.execute('SELECT key, value FROM index_stats')
            stats = {row[0]: row[1] for row in cursor.fetchall()}
            
            self.doc_count = int(stats.get('doc_count', '0'))
            self.total_terms = int(stats.get('total_terms', '0'))
            self.avg_doc_length = float(stats.get('avg_doc_length', '0.0'))
            self.k1 = float(stats.get('k1', '1.5'))
            self.b = float(stats.get('b', '0.75'))
            
            conn.close()
            logger.info(f"BM25索引已从SQLite加载: {self.index_path}")
        except Exception as e:
            logger.error(f"加载BM25索引失败: {str(e)}")
    
    def get_metadata(self) -> Dict[str, Any]:
        """获取索引元数据"""
        return {
            'doc_count': self.doc_count,
            'total_terms': self.total_terms,
            'avg_doc_length': self.avg_doc_length,
            'unique_terms': len(self.inverted_index),
            'k1': self.k1,
            'b': self.b,
            'index_path': self.index_path,
            'storage_type': 'sqlite' if self.use_sqlite else 'pickle'
        }
    
    def clear(self):
        """清空所有索引数据"""
        self.inverted_index.clear()
        self.doc_lengths.clear()
        self.doc_contents.clear()
        self.doc_count = 0
        self.total_terms = 0
        self.avg_doc_length = 0.0
        self.idf_cache.clear()
        logger.info("BM25索引已清空")


# 全局BM25索引实例（使用SQLite存储）
bm25_index = BM25Index(use_sqlite=True)


# 便捷函数
def add_bm25_document(doc_id: str, text: str, store_content: bool = False):
    """添加文档到BM25索引"""
    bm25_index.add_document(doc_id, text, store_content)


def delete_bm25_document(doc_id: str):
    """从BM25索引删除文档"""
    bm25_index.delete_document(doc_id)


def search_bm25(query: str, top_k: int = 10, use_expansion: bool = False) -> List[Tuple[str, float]]:
    """搜索BM25索引"""
    if use_expansion:
        return bm25_index.search_with_expansion(query, top_k)
    return bm25_index.search(query, top_k)


def save_bm25_index():
    """保存BM25索引"""
    bm25_index.save()


def get_bm25_metadata() -> Dict[str, Any]:
    """获取BM25索引元数据"""
    return bm25_index.get_metadata()


if __name__ == "__main__":
    # 示例使用
    test_index = BM25Index(use_sqlite=True)
    
    # 添加测试文档
    test_index.add_document("doc1", "人工智能和机器学习是当今最热门的技术领域")
    test_index.add_document("doc2", "机器学习算法可以分为监督学习和无监督学习")
    test_index.add_document("doc3", "深度学习是机器学习的一个分支，使用神经网络")
    
    # 保存索引
    test_index.save()
    
    # 搜索
    results = test_index.search("机器学习")
    print("搜索结果:", results)
    
    # 带扩展的搜索
    results_expanded = test_index.search_with_expansion("AI", top_k=3)
    print("扩展搜索结果:", results_expanded)
    
    # 打印元数据
    print("索引元数据:", test_index.get_metadata())
