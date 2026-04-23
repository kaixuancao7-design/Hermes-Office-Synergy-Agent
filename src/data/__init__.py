"""数据模块 - 提供文档加载、向量存储、版本管理、多模态处理和高级检索"""

# 向量存储
from .vector_store import VectorStore, vector_store, RAGManager, rag_manager

# 文档加载器
from .document_loader import (
    DocumentLoader, document_loader,
    DocumentPreprocessor, document_preprocessor,
    DocumentPipeline, document_pipeline,
    load_document, process_document
)

# 版本管理
from .version_manager import (
    VersionManager, version_manager,
    VersionInfo,
    create_document_version,
    get_document_version,
    get_document_latest_version,
    compare_document_versions
)

# 多模态处理
from .multimodal_processor import (
    MultimodalProcessor, multimodal_processor,
    ImageProcessor,
    AudioProcessor,
    VideoProcessor,
    TextProcessor,
    process_multimodal,
    detect_data_type
)

# 高级检索
from .advanced_retrieval import (
    AdvancedRetrieval,
    # 过滤器
    KeywordFilter,
    DateFilter,
    SourceFilter,
    LengthFilter,
    # 重排序策略
    BM25ReRank,
    CrossEncoderReRank,
    HybridReRank,
    RecencyBoost,
    # 便捷函数
    create_default_retrieval_pipeline,
    create_enterprise_retrieval_pipeline,
    advanced_search,
    # 全局实例
    default_retrieval,
    enterprise_retrieval
)

# BM25索引
from .bm25_index import (
    BM25Index,
    bm25_index,
    add_bm25_document,
    delete_bm25_document,
    search_bm25,
    save_bm25_index,
    get_bm25_metadata
)

__all__ = [
    # 向量存储
    'VectorStore',
    'vector_store',
    'RAGManager',
    'rag_manager',
    
    # 文档加载器
    'DocumentLoader',
    'document_loader',
    'DocumentPreprocessor',
    'document_preprocessor',
    'DocumentPipeline',
    'document_pipeline',
    'load_document',
    'process_document',
    
    # 版本管理
    'VersionManager',
    'version_manager',
    'VersionInfo',
    'create_document_version',
    'get_document_version',
    'get_document_latest_version',
    'compare_document_versions',
    
    # 多模态处理
    'MultimodalProcessor',
    'multimodal_processor',
    'ImageProcessor',
    'AudioProcessor',
    'VideoProcessor',
    'TextProcessor',
    'process_multimodal',
    'detect_data_type',
    
    # 高级检索
    'AdvancedRetrieval',
    'KeywordFilter',
    'DateFilter',
    'SourceFilter',
    'LengthFilter',
    'BM25ReRank',
    'CrossEncoderReRank',
    'HybridReRank',
    'RecencyBoost',
    'create_default_retrieval_pipeline',
    'create_enterprise_retrieval_pipeline',
    'advanced_search',
    'default_retrieval',
    'enterprise_retrieval',
    
    # BM25索引
    'BM25Index',
    'bm25_index',
    'add_bm25_document',
    'delete_bm25_document',
    'search_bm25',
    'save_bm25_index',
    'get_bm25_metadata'
]
