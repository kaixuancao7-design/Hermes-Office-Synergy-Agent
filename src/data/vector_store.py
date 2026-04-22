"""向量存储模块 - 整合文档加载、版本管理、多模态支持和高级检索"""
import os
from typing import List, Dict, Any, Optional

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from src.utils import setup_logging, generate_id
from src.config import settings
from src.plugins.embedding_services import get_embedding_service

from .document_loader import document_pipeline
from .version_manager import version_manager
from .multimodal_processor import multimodal_processor
from .advanced_retrieval import default_retrieval

logger = setup_logging(settings.LOG_LEVEL)


class VectorStore:
    """基于 LangChain + ChromaDB 的向量存储实现"""
    
    def __init__(self):
        self.vector_path = settings.VECTOR_DB_PATH
        self.embedding_model = self._init_embedding_model()
        self._init_chroma()
    
    def _init_embedding_model(self):
        """Initialize embedding model"""
        # 尝试获取配置的嵌入服务
        embedding_service = get_embedding_service()
        
        if embedding_service and embedding_service != "default":
            # 使用自定义嵌入服务
            try:
                from langchain_community.embeddings import OllamaEmbeddings
                
                if settings.EMBEDDING_SERVICE_TYPE == "ollama":
                    return OllamaEmbeddings(
                        model="Mxbai-embed-large",
                        base_url=settings.OLLAMA_HOST
                    )
                elif settings.EMBEDDING_SERVICE_TYPE == "openai" and settings.OPENAI_API_KEY:
                    return OpenAIEmbeddings(
                        model="text-embedding-3-small",
                        api_key=settings.OPENAI_API_KEY
                    )
                else:
                    # 使用Chroma默认嵌入
                    logger.info("Using default Chroma embedding")
                    return None
            except Exception as e:
                logger.warning(f"Failed to initialize custom embedding: {e}, falling back to default")
                return None
        else:
            # 回退到默认行为
            if settings.OPENAI_API_KEY:
                try:
                    return OpenAIEmbeddings(
                        model="text-embedding-3-small",
                        api_key=settings.OPENAI_API_KEY
                    )
                except Exception as e:
                    logger.warning(f"Failed to initialize OpenAI embedding: {e}, falling back to default")
                    return None
            else:
                logger.info("No OpenAI API key configured, using default Chroma embedding")
                return None
    
    def _init_chroma(self):
        """初始化 ChromaDB"""
        os.makedirs(self.vector_path, exist_ok=True)
        
        try:
            chroma_kwargs = {
                "persist_directory": self.vector_path,
                "collection_name": "hermes_documents"
            }
            
            # 如果嵌入模型不为 None，则传入
            if self.embedding_model is not None:
                chroma_kwargs["embedding_function"] = self.embedding_model
            
            self.chroma = Chroma(**chroma_kwargs)
            logger.info("ChromaDB initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise
    
    def add_vector(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """添加向量到存储"""
        doc_id = generate_id()
        document = Document(
            page_content=content,
            metadata={**(metadata or {}), "id": doc_id}
        )
        
        try:
            self.chroma.add_documents([document], ids=[doc_id])
            # 新版本 Chroma 不需要手动 persist
            logger.debug(f"Added vector with id: {doc_id}")
            return doc_id
        except Exception as e:
            logger.error(f"Failed to add vector: {e}")
            raise
    
    def add_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """批量添加文档"""
        langchain_docs = []
        doc_ids = []
        
        for doc in documents:
            doc_id = generate_id()
            langchain_docs.append(Document(
                page_content=doc.get("content", ""),
                metadata={**doc.get("metadata", {}), "id": doc_id}
            ))
            doc_ids.append(doc_id)
        
        try:
            self.chroma.add_documents(langchain_docs, ids=doc_ids)
            # 新版本 Chroma 不需要手动 persist
            logger.info(f"Added {len(doc_ids)} documents")
            return doc_ids
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise
    
    def search(self, query: str, k: int = 5, filter: Optional[Dict[str, Any]] = None,
              use_advanced: bool = False) -> List[Dict[str, Any]]:
        """搜索相似向量"""
        try:
            results = self.chroma.similarity_search_with_score(
                query=query,
                k=k,
                filter=filter
            )
            
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "distance": score,
                    "id": doc.metadata.get("id", "")
                })
            
            # 如果启用高级检索优化
            if use_advanced:
                formatted_results = default_retrieval.process(query, formatted_results)
            
            return formatted_results
        except Exception as e:
            logger.error(f"Failed to search vectors: {e}")
            return []
    
    def delete_vector(self, vector_id: str) -> bool:
        """删除向量"""
        try:
            self.chroma.delete([vector_id])
            # 新版本 Chroma 不需要手动 persist
            logger.debug(f"Deleted vector with id: {vector_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vector: {e}")
            return False
    
    def get_all_vectors(self) -> List[Dict[str, Any]]:
        """获取所有向量"""
        try:
            all_docs = self.chroma.get()
            results = []
            for i, content in enumerate(all_docs["documents"]):
                results.append({
                    "content": content,
                    "metadata": all_docs["metadatas"][i],
                    "id": all_docs["ids"][i]
                })
            return results
        except Exception as e:
            logger.error(f"Failed to get all vectors: {e}")
            return []
    
    def clear(self):
        """清空所有向量"""
        try:
            self.chroma.delete_collection()
            self._init_chroma()
            logger.info("Vector store cleared")
        except Exception as e:
            logger.error(f"Failed to clear vector store: {e}")
            raise
    
    def get_retriever(self, k: int = 5):
        """获取 LangChain Retriever"""
        return self.chroma.as_retriever(search_kwargs={"k": k})


class RAGManager:
    """基于 LangChain 的 RAG 管理器（整合版）"""
    
    def __init__(self):
        self.vector_store = VectorStore()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len
        )
    
    def load_and_add_document(self, file_path: str = None, content: bytes = None, 
                             file_name: str = None, metadata: Optional[Dict[str, Any]] = None,
                             version_note: str = "", created_by: str = "system") -> Dict[str, Any]:
        """
        加载文档并添加到向量存储（完整流程）
        
        Args:
            file_path: 文件路径
            content: 文件内容（字节）
            file_name: 文件名
            metadata: 元数据
            version_note: 版本备注
            created_by: 创建者
        
        Returns:
            处理结果
        """
        # 1. 使用统一文档加载器加载文档
        load_result = document_pipeline.process(file_path, content, file_name)
        
        if not load_result["success"]:
            return {"success": False, "error": load_result["error"]}
        
        # 2. 获取处理后的内容
        content = load_result["processed_content"]
        
        # 3. 如果内容很大，自动分割
        if len(content) > 2000:
            chunks = load_result.get("chunks", self.text_splitter.split_text(content))
        else:
            chunks = [content]
        
        # 4. 添加到向量存储
        doc_ids = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = {
                **(metadata or {}),
                **load_result.get("metadata", {}),
                "chunk_index": i,
                "total_chunks": len(chunks),
                "filename": file_name or file_path
            }
            doc_id = self.vector_store.add_vector(chunk, chunk_metadata)
            doc_ids.append(doc_id)
        
        # 5. 创建版本记录
        if doc_ids:
            version_manager.create_version(
                document_id=doc_ids[0],
                content=content,
                metadata=load_result.get("metadata", {}),
                created_by=created_by,
                change_note=version_note
            )
        
        return {
            "success": True,
            "doc_ids": doc_ids,
            "chunk_count": len(chunks),
            "content_length": len(content),
            "metadata": load_result.get("metadata", {})
        }
    
    def add_document(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """添加文档到向量存储"""
        return self.vector_store.add_vector(content, metadata)
    
    def add_large_document(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> List[str]:
        """添加大文档（自动分割）"""
        chunks = self.text_splitter.split_text(content)
        doc_ids = []
        
        for i, chunk in enumerate(chunks):
            chunk_metadata = {**(metadata or {}), "chunk_index": i, "total_chunks": len(chunks)}
            doc_id = self.vector_store.add_vector(chunk, chunk_metadata)
            doc_ids.append(doc_id)
        
        return doc_ids
    
    def add_multimodal_document(self, data: Any, filename: Optional[str] = None,
                               metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        添加多模态文档
        
        Args:
            data: 数据内容（文本、图片、音频等）
            filename: 文件名
            metadata: 元数据
        
        Returns:
            处理结果
        """
        # 使用多模态处理器处理数据
        result = multimodal_processor.process(data, filename=filename)
        
        if not result["success"]:
            return result
        
        # 如果是文本类型，直接添加到向量存储
        if result["data_type"] == "text":
            doc_id = self.vector_store.add_vector(result["content"], metadata)
            return {
                "success": True,
                "doc_id": doc_id,
                "data_type": "text",
                "metadata": result.get("metadata", {})
            }
        
        # 如果是图片，使用图片描述作为内容
        elif result["data_type"] == "image" and "caption" in result:
            content = f"图片描述: {result['caption']}"
            doc_id = self.vector_store.add_vector(content, {
                **(metadata or {}),
                "data_type": "image",
                "caption": result["caption"],
                **result.get("metadata", {})
            })
            return {
                "success": True,
                "doc_id": doc_id,
                "data_type": "image",
                "caption": result["caption"],
                "metadata": result.get("metadata", {})
            }
        
        # 如果是音频，使用转录文本作为内容
        elif result["data_type"] == "audio" and "transcription" in result:
            doc_id = self.vector_store.add_vector(result["transcription"], {
                **(metadata or {}),
                "data_type": "audio",
                **result.get("metadata", {})
            })
            return {
                "success": True,
                "doc_id": doc_id,
                "data_type": "audio",
                "transcription": result["transcription"],
                "metadata": result.get("metadata", {})
            }
        
        # 如果是视频，使用关键帧描述作为内容
        elif result["data_type"] == "video" and "keyframes" in result:
            content = "\n".join([f"帧 {k['frame_index']} ({k['timestamp']}s): {k['caption']}" 
                                for k in result["keyframes"]])
            doc_id = self.vector_store.add_vector(content, {
                **(metadata or {}),
                "data_type": "video",
                **result.get("metadata", {})
            })
            return {
                "success": True,
                "doc_id": doc_id,
                "data_type": "video",
                "keyframes_count": len(result["keyframes"]),
                "metadata": result.get("metadata", {})
            }
        
        return {"success": False, "error": "无法处理该类型的数据"}
    
    def query(self, query: str, k: int = 5, use_advanced: bool = True) -> List[Dict[str, Any]]:
        """查询相关文档"""
        return self.vector_store.search(query, k, use_advanced=use_advanced)
    
    def get_context(self, query: str, k: int = 5) -> str:
        """获取查询的上下文文本"""
        results = self.query(query, k)
        context = "\n\n".join([doc.get("content", "") for doc in results])
        return context
    
    def get_document_versions(self, document_id: str) -> List[Dict[str, Any]]:
        """获取文档的版本历史"""
        versions = version_manager.get_all_versions(document_id)
        return [v.to_dict() for v in versions]
    
    def restore_document_version(self, document_id: str, version_number: int) -> Optional[Dict[str, Any]]:
        """恢复文档到指定版本"""
        version = version_manager.restore_version(document_id, version_number)
        if version:
            # 将恢复的版本添加到向量存储
            new_doc_id = self.vector_store.add_vector(version.content, version.metadata)
            return {
                "success": True,
                "new_doc_id": new_doc_id,
                "restored_from_version": version_number,
                "version_info": version.to_dict()
            }
        return {"success": False, "error": "版本不存在"}


# 全局实例
vector_store = VectorStore()
rag_manager = RAGManager()
