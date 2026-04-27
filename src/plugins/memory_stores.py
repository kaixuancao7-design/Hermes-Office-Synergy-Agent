"""记忆存储插件实现"""
from typing import Dict, Any, List, Optional

from src.plugins.base import MemoryBase
from src.types import MemoryEntry
from src.config import settings
from src.utils import generate_id, get_timestamp
from src.exceptions import MemoryException
from src.logging_config import get_logger

logger = get_logger("memory")


class ChromaMemory(MemoryBase):
    """Chroma向量数据库记忆存储"""
    
    def __init__(self, embedding_service=None):
        self.client = None
        self.collections = {}
        self.embedding_service = embedding_service
        self._initialize()
    
    def _initialize(self):
        try:
            import chromadb
            from chromadb.config import Settings
            
            self.client = chromadb.Client(Settings(
                persist_directory=settings.VECTOR_DB_PATH,
                anonymized_telemetry=False
            ))
            
            # 如果指定了外部embedding服务，配置给Chroma
            if self.embedding_service and self.embedding_service != "default":
                try:
                    from src.plugins.embedding_services import get_embedding_service
                    embedding_service = get_embedding_service(self.embedding_service)
                    if embedding_service:
                        # 自定义Chroma集合，使用外部embedding函数
                        self.collections = {
                            "short_term": self.client.get_or_create_collection(
                                "short_term",
                                embedding_function=self._create_embedding_function(embedding_service)
                            ),
                            "long_term": self.client.get_or_create_collection(
                                "long_term",
                                embedding_function=self._create_embedding_function(embedding_service)
                            ),
                            "user_preferences": self.client.get_or_create_collection(
                                "user_preferences",
                                embedding_function=self._create_embedding_function(embedding_service)
                            )
                        }
                        logger.info(f"Chroma记忆存储初始化成功，使用外部Embedding服务: {self.embedding_service}")
                    else:
                        self._create_default_collections()
                except Exception as e:
                    logger.warning(f"配置外部Embedding服务失败，使用默认配置: {str(e)}")
                    self._create_default_collections()
            else:
                self._create_default_collections()
                
        except Exception as e:
            logger.error(f"Chroma记忆存储初始化失败: {str(e)}")
            raise MemoryException(
                message="Chroma初始化失败",
                detail=str(e)
            )
    
    def _create_default_collections(self):
        """创建默认集合"""
        self.collections = {
            "short_term": self.client.get_or_create_collection("short_term"),
            "long_term": self.client.get_or_create_collection("long_term"),
            "user_preferences": self.client.get_or_create_collection("user_preferences")
        }
        logger.info("Chroma记忆存储初始化成功，使用默认Embedding")
    
    def _create_embedding_function(self, embedding_service):
        """创建Chroma兼容的embedding函数"""
        def embedding_function(texts: List[str]) -> List[List[float]]:
            return embedding_service.embed(texts)
        return embedding_function
    
    def add_memory(self, user_id: str, entry: MemoryEntry) -> bool:
        try:
            collection = self.collections.get(entry.type, self.collections["long_term"])
            
            # 构建 add 方法的参数
            add_params = {
                "ids": [entry.id],
                "documents": [entry.content],
                "metadatas": [{
                    "user_id": user_id,
                    "type": entry.type,
                    "timestamp": entry.timestamp,
                    "tags": ",".join(entry.tags) if entry.tags else ""
                }]
            }
            
            # 只有当 embedding 存在时才传入，否则让 Chroma 使用配置的embedding服务自动处理
            if entry.embedding:
                add_params["embeddings"] = [entry.embedding]
            
            collection.add(**add_params)
            
            return True
        except Exception as e:
            logger.error(f"添加记忆失败: {str(e)}")
            raise MemoryException(
                message="添加记忆失败",
                detail=str(e),
                context={"user_id": user_id, "memory_type": entry.type}
            )
    
    def update_memory(self, user_id: str, memory_id: str, content: str) -> bool:
        try:
            for collection in self.collections.values():
                try:
                    collection.update(
                        ids=[memory_id],
                        documents=[content],
                        metadatas=[{"user_id": user_id}]
                    )
                    return True
                except:
                    continue
            return False
        except Exception as e:
            logger.error(f"更新记忆失败: {str(e)}")
            return False
    
    def search_memory(self, user_id: str, query: str, limit: int = 5) -> List[MemoryEntry]:
        try:
            results = []
            
            for collection_name, collection in self.collections.items():
                try:
                    result = collection.query(
                        query_texts=[query],
                        n_results=limit,
                        where={"user_id": user_id}
                    )
                    
                    for i, doc in enumerate(result["documents"][0]):
                        entry = MemoryEntry(
                            id=result["ids"][0][i],
                            user_id=user_id,
                            type=collection_name,
                            content=doc,
                            embedding=result["embeddings"][0][i] if result["embeddings"] else None,
                            timestamp=result["metadatas"][0][i].get("timestamp", get_timestamp()),
                            tags=result["metadatas"][0][i].get("tags", "").split(",") if result["metadatas"] else []
                        )
                        results.append(entry)
                except Exception as e:
                    logger.debug(f"搜索集合 {collection_name} 失败: {str(e)}")
            
            results.sort(key=lambda x: x.timestamp, reverse=True)
            return results[:limit]
        except Exception as e:
            logger.error(f"搜索记忆失败: {str(e)}")
            return []
    
    def get_memory(self, user_id: str, memory_id: str) -> Optional[MemoryEntry]:
        try:
            for collection_name, collection in self.collections.items():
                try:
                    result = collection.get(ids=[memory_id])
                    if result["ids"]:
                        return MemoryEntry(
                            id=result["ids"][0],
                            user_id=user_id,
                            type=collection_name,
                            content=result["documents"][0],
                            embedding=result["embeddings"][0] if result["embeddings"] else None,
                            timestamp=result["metadatas"][0].get("timestamp", get_timestamp()),
                            tags=result["metadatas"][0].get("tags", "").split(",") if result["metadatas"] else []
                        )
                except:
                    continue
            return None
        except Exception as e:
            logger.error(f"获取记忆失败: {str(e)}")
            return None
    
    def get_memory_by_type(self, user_id: str, memory_type: str) -> List[MemoryEntry]:
        try:
            collection = self.collections.get(memory_type)
            if not collection:
                return []
            
            result = collection.get(where={"user_id": user_id})
            
            entries = []
            for i, doc in enumerate(result["documents"]):
                entry = MemoryEntry(
                    id=result["ids"][i],
                    user_id=user_id,
                    type=memory_type,
                    content=doc,
                    embedding=result["embeddings"][i] if result["embeddings"] else None,
                    timestamp=result["metadatas"][i].get("timestamp", get_timestamp()),
                    tags=result["metadatas"][i].get("tags", "").split(",") if result["metadatas"] else []
                )
                entries.append(entry)
            
            return entries
        except Exception as e:
            logger.error(f"获取记忆失败: {str(e)}")
            return []
    
    def get_all_memories(self, user_id: str) -> List[MemoryEntry]:
        results = []
        for memory_type in ["short_term", "long_term", "user_preferences"]:
            results.extend(self.get_memory_by_type(user_id, memory_type))
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results
    
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        try:
            for collection in self.collections.values():
                try:
                    collection.delete(ids=[memory_id])
                    return True
                except:
                    continue
            return False
        except Exception as e:
            logger.error(f"删除记忆失败: {str(e)}")
            return False
    
    def clear_memory(self, user_id: str) -> bool:
        try:
            for collection in self.collections.values():
                collection.delete(where={"user_id": user_id})
            return True
        except Exception as e:
            logger.error(f"清空记忆失败: {str(e)}")
            return False
    
    def clear_memory_by_type(self, user_id: str, memory_type: str) -> bool:
        try:
            collection = self.collections.get(memory_type)
            if collection:
                collection.delete(where={"user_id": user_id})
                return True
            return False
        except Exception as e:
            logger.error(f"清空记忆失败: {str(e)}")
            return False
    
    def get_memory_count(self, user_id: str) -> int:
        count = 0
        for collection in self.collections.values():
            try:
                result = collection.count(where={"user_id": user_id})
                count += result
            except:
                continue
        return count
    
    def get_memory_type(self) -> str:
        return "chroma"
    
    def persist(self) -> bool:
        try:
            if self.client:
                self.client.persist()
                return True
            return False
        except Exception as e:
            logger.error(f"持久化失败: {str(e)}")
            return False


class SimpleMemory(MemoryBase):
    """简单内存记忆存储（用于测试和轻量级场景）"""
    
    def __init__(self):
        self.memories: Dict[str, List[MemoryEntry]] = {}
    
    def add_memory(self, user_id: str, entry: MemoryEntry) -> bool:
        if user_id not in self.memories:
            self.memories[user_id] = []
        
        self.memories[user_id].append(entry)
        return True
    
    def update_memory(self, user_id: str, memory_id: str, content: str) -> bool:
        if user_id not in self.memories:
            return False
        
        for entry in self.memories[user_id]:
            if entry.id == memory_id:
                entry.content = content
                entry.timestamp = get_timestamp()
                return True
        return False
    
    def search_memory(self, user_id: str, query: str, limit: int = 5) -> List[MemoryEntry]:
        if user_id not in self.memories:
            return []
        
        results = []
        for entry in self.memories[user_id]:
            if query.lower() in entry.content.lower():
                results.append(entry)
        
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]
    
    def get_memory(self, user_id: str, memory_id: str) -> Optional[MemoryEntry]:
        if user_id not in self.memories:
            return None
        
        for entry in self.memories[user_id]:
            if entry.id == memory_id:
                return entry
        return None
    
    def get_memory_by_type(self, user_id: str, memory_type: str) -> List[MemoryEntry]:
        if user_id not in self.memories:
            return []
        
        results = [entry for entry in self.memories[user_id] if entry.type == memory_type]
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results
    
    def get_all_memories(self, user_id: str) -> List[MemoryEntry]:
        if user_id not in self.memories:
            return []
        
        results = sorted(self.memories[user_id], key=lambda x: x.timestamp, reverse=True)
        return results
    
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        if user_id not in self.memories:
            return False
        
        original_length = len(self.memories[user_id])
        self.memories[user_id] = [entry for entry in self.memories[user_id] if entry.id != memory_id]
        
        return len(self.memories[user_id]) < original_length
    
    def clear_memory(self, user_id: str) -> bool:
        if user_id in self.memories:
            self.memories[user_id] = []
            return True
        return False
    
    def clear_memory_by_type(self, user_id: str, memory_type: str) -> bool:
        if user_id not in self.memories:
            return False
        
        original_length = len(self.memories[user_id])
        self.memories[user_id] = [entry for entry in self.memories[user_id] if entry.type != memory_type]
        
        return len(self.memories[user_id]) < original_length
    
    def get_memory_count(self, user_id: str) -> int:
        return len(self.memories.get(user_id, []))
    
    def get_memory_type(self) -> str:
        return "simple"
    
    def persist(self) -> bool:
        return True


class MilvusMemory(MemoryBase):
    """Milvus向量数据库记忆存储"""
    
    def __init__(self):
        self.client = None
        self._initialize()
    
    def _initialize(self):
        try:
            from pymilvus import MilvusClient
            
            self.client = MilvusClient(
                uri=settings.MILVUS_URI or "http://localhost:19530",
                token=settings.MILVUS_TOKEN or None
            )
            
            # 创建集合
            collections = ["short_term", "long_term", "user_preferences"]
            for coll_name in collections:
                if not self.client.has_collection(coll_name):
                    self.client.create_collection(
                        collection_name=coll_name,
                        dimension=384,
                        auto_id=False
                    )
            
            logger.info("Milvus记忆存储初始化成功")
        except Exception as e:
            logger.error(f"Milvus记忆存储初始化失败: {str(e)}")
            raise MemoryException(
                message="Milvus初始化失败",
                detail=str(e)
            )
    
    def add_memory(self, user_id: str, entry: MemoryEntry) -> bool:
        try:
            collection_name = entry.type if entry.type in ["short_term", "long_term", "user_preferences"] else "long_term"
            
            if not entry.embedding:
                entry.embedding = [0.0] * 384
            
            self.client.insert(
                collection_name=collection_name,
                data=[{
                    "id": entry.id,
                    "vector": entry.embedding,
                    "content": entry.content,
                    "user_id": user_id,
                    "type": entry.type,
                    "timestamp": entry.timestamp,
                    "tags": ",".join(entry.tags) if entry.tags else ""
                }]
            )
            
            return True
        except Exception as e:
            logger.error(f"添加记忆失败: {str(e)}")
            raise MemoryException(
                message="添加记忆失败",
                detail=str(e),
                context={"user_id": user_id, "memory_type": entry.type}
            )
    
    def update_memory(self, user_id: str, memory_id: str, content: str) -> bool:
        try:
            for coll_name in ["short_term", "long_term", "user_preferences"]:
                if self.client.has_collection(coll_name):
                    try:
                        self.client.update(
                            collection_name=coll_name,
                            data=[{
                                "id": memory_id,
                                "content": content,
                                "timestamp": get_timestamp()
                            }]
                        )
                        return True
                    except:
                        continue
            return False
        except Exception as e:
            logger.error(f"更新记忆失败: {str(e)}")
            return False
    
    def search_memory(self, user_id: str, query: str, limit: int = 5) -> List[MemoryEntry]:
        try:
            import numpy as np
            
            results = []
            for coll_name in ["short_term", "long_term", "user_preferences"]:
                if self.client.has_collection(coll_name):
                    try:
                        res = self.client.search(
                            collection_name=coll_name,
                            data=[[0.0] * 384],
                            limit=limit,
                            filter=f'user_id == "{user_id}"',
                            output_fields=["content", "type", "timestamp", "tags"]
                        )
                        
                        for hit in res[0]:
                            entry = MemoryEntry(
                                id=hit["id"],
                                user_id=user_id,
                                type=hit["entity"].get("type", coll_name),
                                content=hit["entity"].get("content", ""),
                                embedding=None,
                                timestamp=hit["entity"].get("timestamp", get_timestamp()),
                                tags=hit["entity"].get("tags", "").split(",") if hit["entity"].get("tags") else []
                            )
                            results.append(entry)
                    except Exception as e:
                        logger.debug(f"搜索集合 {coll_name} 失败: {str(e)}")
            
            results.sort(key=lambda x: x.timestamp, reverse=True)
            return results[:limit]
        except Exception as e:
            logger.error(f"搜索记忆失败: {str(e)}")
            return []
    
    def get_memory(self, user_id: str, memory_id: str) -> Optional[MemoryEntry]:
        try:
            for coll_name in ["short_term", "long_term", "user_preferences"]:
                if self.client.has_collection(coll_name):
                    try:
                        res = self.client.get(
                            collection_name=coll_name,
                            ids=[memory_id],
                            output_fields=["content", "type", "timestamp", "tags"]
                        )
                        if res:
                            entity = res[0]
                            return MemoryEntry(
                                id=memory_id,
                                user_id=user_id,
                                type=entity.get("type", coll_name),
                                content=entity.get("content", ""),
                                embedding=None,
                                timestamp=entity.get("timestamp", get_timestamp()),
                                tags=entity.get("tags", "").split(",") if entity.get("tags") else []
                            )
                    except:
                        continue
            return None
        except Exception as e:
            logger.error(f"获取记忆失败: {str(e)}")
            return None
    
    def get_memory_by_type(self, user_id: str, memory_type: str) -> List[MemoryEntry]:
        try:
            collection_name = memory_type if memory_type in ["short_term", "long_term", "user_preferences"] else "long_term"
            
            if not self.client.has_collection(collection_name):
                return []
            
            res = self.client.query(
                collection_name=collection_name,
                filter=f'user_id == "{user_id}"',
                output_fields=["content", "type", "timestamp", "tags"]
            )
            
            entries = []
            for entity in res:
                entry = MemoryEntry(
                    id=entity["id"],
                    user_id=user_id,
                    type=entity.get("type", memory_type),
                    content=entity.get("content", ""),
                    embedding=None,
                    timestamp=entity.get("timestamp", get_timestamp()),
                    tags=entity.get("tags", "").split(",") if entity.get("tags") else []
                )
                entries.append(entry)
            
            entries.sort(key=lambda x: x.timestamp, reverse=True)
            return entries
        except Exception as e:
            logger.error(f"获取记忆失败: {str(e)}")
            return []
    
    def get_all_memories(self, user_id: str) -> List[MemoryEntry]:
        results = []
        for coll_name in ["short_term", "long_term", "user_preferences"]:
            results.extend(self.get_memory_by_type(user_id, coll_name))
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results
    
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        try:
            for coll_name in ["short_term", "long_term", "user_preferences"]:
                if self.client.has_collection(coll_name):
                    try:
                        self.client.delete(
                            collection_name=coll_name,
                            ids=[memory_id]
                        )
                        return True
                    except:
                        continue
            return False
        except Exception as e:
            logger.error(f"删除记忆失败: {str(e)}")
            return False
    
    def clear_memory(self, user_id: str) -> bool:
        try:
            for coll_name in ["short_term", "long_term", "user_preferences"]:
                if self.client.has_collection(coll_name):
                    self.client.delete(
                        collection_name=coll_name,
                        filter=f'user_id == "{user_id}"'
                    )
            return True
        except Exception as e:
            logger.error(f"清空记忆失败: {str(e)}")
            return False
    
    def clear_memory_by_type(self, user_id: str, memory_type: str) -> bool:
        try:
            collection_name = memory_type if memory_type in ["short_term", "long_term", "user_preferences"] else "long_term"
            
            if self.client.has_collection(collection_name):
                self.client.delete(
                    collection_name=collection_name,
                    filter=f'user_id == "{user_id}"'
                )
                return True
            return False
        except Exception as e:
            logger.error(f"清空记忆失败: {str(e)}")
            return False
    
    def get_memory_count(self, user_id: str) -> int:
        count = 0
        for coll_name in ["short_term", "long_term", "user_preferences"]:
            if self.client.has_collection(coll_name):
                try:
                    res = self.client.query(
                        collection_name=coll_name,
                        filter=f'user_id == "{user_id}"',
                        output_fields=["id"]
                    )
                    count += len(res)
                except:
                    continue
        return count
    
    def get_memory_type(self) -> str:
        return "milvus"
    
    def persist(self) -> bool:
        return True


class FAISSMemory(MemoryBase):
    """FAISS向量数据库记忆存储"""
    
    def __init__(self):
        self.indexes: Dict[str, Any] = {}
        self.metadata: Dict[str, List[Dict[str, Any]]] = {}
        self._initialize()
    
    def _initialize(self):
        try:
            import faiss
            
            self.indexes = {
                "short_term": faiss.IndexFlatL2(384),
                "long_term": faiss.IndexFlatL2(384),
                "user_preferences": faiss.IndexFlatL2(384)
            }
            self.metadata = {
                "short_term": [],
                "long_term": [],
                "user_preferences": []
            }
            
            logger.info("FAISS记忆存储初始化成功")
        except Exception as e:
            logger.error(f"FAISS记忆存储初始化失败: {str(e)}")
            raise MemoryException(
                message="FAISS初始化失败",
                detail=str(e)
            )
    
    def add_memory(self, user_id: str, entry: MemoryEntry) -> bool:
        try:
            import numpy as np
            
            collection_name = entry.type if entry.type in ["short_term", "long_term", "user_preferences"] else "long_term"
            
            if not entry.embedding:
                entry.embedding = [0.0] * 384
            
            vector = np.array([entry.embedding], dtype=np.float32)
            self.indexes[collection_name].add(vector)
            
            self.metadata[collection_name].append({
                "id": entry.id,
                "user_id": user_id,
                "content": entry.content,
                "type": entry.type,
                "timestamp": entry.timestamp,
                "tags": entry.tags
            })
            
            return True
        except Exception as e:
            logger.error(f"添加记忆失败: {str(e)}")
            raise MemoryException(
                message="添加记忆失败",
                detail=str(e),
                context={"user_id": user_id, "memory_type": entry.type}
            )
    
    def update_memory(self, user_id: str, memory_id: str, content: str) -> bool:
        try:
            for coll_name in ["short_term", "long_term", "user_preferences"]:
                for meta in self.metadata[coll_name]:
                    if meta["id"] == memory_id:
                        meta["content"] = content
                        meta["timestamp"] = get_timestamp()
                        return True
            return False
        except Exception as e:
            logger.error(f"更新记忆失败: {str(e)}")
            return False
    
    def search_memory(self, user_id: str, query: str, limit: int = 5) -> List[MemoryEntry]:
        try:
            import numpy as np
            
            results = []
            query_vector = np.array([[0.0] * 384], dtype=np.float32)
            
            for coll_name in ["short_term", "long_term", "user_preferences"]:
                index = self.indexes[coll_name]
                if index.ntotal > 0:
                    try:
                        distances, indices = index.search(query_vector, min(limit, index.ntotal))
                        
                        for i in indices[0]:
                            if i >= 0 and i < len(self.metadata[coll_name]):
                                meta = self.metadata[coll_name][i]
                                if meta["user_id"] == user_id:
                                    entry = MemoryEntry(
                                        id=meta["id"],
                                        user_id=user_id,
                                        type=meta["type"],
                                        content=meta["content"],
                                        embedding=None,
                                        timestamp=meta["timestamp"],
                                        tags=meta["tags"]
                                    )
                                    results.append(entry)
                    except Exception as e:
                        logger.debug(f"搜索集合 {coll_name} 失败: {str(e)}")
            
            results.sort(key=lambda x: x.timestamp, reverse=True)
            return results[:limit]
        except Exception as e:
            logger.error(f"搜索记忆失败: {str(e)}")
            return []
    
    def get_memory(self, user_id: str, memory_id: str) -> Optional[MemoryEntry]:
        try:
            for coll_name in ["short_term", "long_term", "user_preferences"]:
                for meta in self.metadata[coll_name]:
                    if meta["id"] == memory_id and meta["user_id"] == user_id:
                        return MemoryEntry(
                            id=meta["id"],
                            user_id=user_id,
                            type=meta["type"],
                            content=meta["content"],
                            embedding=None,
                            timestamp=meta["timestamp"],
                            tags=meta["tags"]
                        )
            return None
        except Exception as e:
            logger.error(f"获取记忆失败: {str(e)}")
            return None
    
    def get_memory_by_type(self, user_id: str, memory_type: str) -> List[MemoryEntry]:
        try:
            collection_name = memory_type if memory_type in ["short_term", "long_term", "user_preferences"] else "long_term"
            
            results = []
            for meta in self.metadata[collection_name]:
                if meta["user_id"] == user_id:
                    entry = MemoryEntry(
                        id=meta["id"],
                        user_id=user_id,
                        type=meta["type"],
                        content=meta["content"],
                        embedding=None,
                        timestamp=meta["timestamp"],
                        tags=meta["tags"]
                    )
                    results.append(entry)
            
            results.sort(key=lambda x: x.timestamp, reverse=True)
            return results
        except Exception as e:
            logger.error(f"获取记忆失败: {str(e)}")
            return []
    
    def get_all_memories(self, user_id: str) -> List[MemoryEntry]:
        results = []
        for coll_name in ["short_term", "long_term", "user_preferences"]:
            results.extend(self.get_memory_by_type(user_id, coll_name))
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results
    
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        try:
            import numpy as np
            
            for coll_name in ["short_term", "long_term", "user_preferences"]:
                indices_to_keep = []
                new_metadata = []
                
                for idx, meta in enumerate(self.metadata[coll_name]):
                    if meta["id"] != memory_id:
                        indices_to_keep.append(idx)
                        new_metadata.append(meta)
                
                if len(new_metadata) < len(self.metadata[coll_name]):
                    self.metadata[coll_name] = new_metadata
                    
                    if len(indices_to_keep) > 0:
                        old_index = self.indexes[coll_name]
                        new_index = type(old_index)(384)
                        vectors = faiss.vector_to_array(old_index.reconstruct_n(0, old_index.ntotal))
                        vectors = vectors.reshape(old_index.ntotal, 384)
                        new_index.add(vectors[indices_to_keep])
                        self.indexes[coll_name] = new_index
                    else:
                        self.indexes[coll_name] = type(self.indexes[coll_name])(384)
                    
                    return True
            
            return False
        except Exception as e:
            logger.error(f"删除记忆失败: {str(e)}")
            return False
    
    def clear_memory(self, user_id: str) -> bool:
        try:
            for coll_name in ["short_term", "long_term", "user_preferences"]:
                self.metadata[coll_name] = [meta for meta in self.metadata[coll_name] if meta["user_id"] != user_id]
                
                if len(self.metadata[coll_name]) == 0:
                    self.indexes[coll_name] = type(self.indexes[coll_name])(384)
                else:
                    pass
            
            return True
        except Exception as e:
            logger.error(f"清空记忆失败: {str(e)}")
            return False
    
    def clear_memory_by_type(self, user_id: str, memory_type: str) -> bool:
        try:
            collection_name = memory_type if memory_type in ["short_term", "long_term", "user_preferences"] else "long_term"
            
            self.metadata[collection_name] = [meta for meta in self.metadata[collection_name] if meta["user_id"] != user_id]
            
            if len(self.metadata[collection_name]) == 0:
                self.indexes[collection_name] = type(self.indexes[collection_name])(384)
            
            return True
        except Exception as e:
            logger.error(f"清空记忆失败: {str(e)}")
            return False
    
    def get_memory_count(self, user_id: str) -> int:
        count = 0
        for coll_name in ["short_term", "long_term", "user_preferences"]:
            count += len([meta for meta in self.metadata[coll_name] if meta["user_id"] == user_id])
        return count
    
    def get_memory_type(self) -> str:
        return "faiss"
    
    def persist(self) -> bool:
        try:
            import faiss
            import os
            
            os.makedirs(settings.VECTOR_DB_PATH, exist_ok=True)
            
            for coll_name, index in self.indexes.items():
                faiss.write_index(index, os.path.join(settings.VECTOR_DB_PATH, f"{coll_name}.index"))
            
            return True
        except Exception as e:
            logger.error(f"持久化失败: {str(e)}")
            return False


class HybridMemory(MemoryBase):
    """混合记忆存储（短期用内存，长期用向量库）"""
    
    def __init__(self):
        self.short_term = SimpleMemory()
        self.long_term = ChromaMemory()
        self.SHORT_TERM_LIMIT = 100
    
    def add_memory(self, user_id: str, entry: MemoryEntry) -> bool:
        if entry.type == "short":
            self.short_term.add_memory(user_id, entry)
            
            memories = self.short_term.get_memory_by_type(user_id, "short")
            if len(memories) > self.SHORT_TERM_LIMIT:
                memories.sort(key=lambda x: x.timestamp)
                to_move = memories[:len(memories) // 2]
                
                for mem in to_move:
                    mem.type = "long"
                    self.long_term.add_memory(user_id, mem)
                    self.short_term.delete_memory(user_id, mem.id)
            
            return True
        else:
            return self.long_term.add_memory(user_id, entry)
    
    def update_memory(self, user_id: str, memory_id: str, content: str) -> bool:
        if self.short_term.update_memory(user_id, memory_id, content):
            return True
        return self.long_term.update_memory(user_id, memory_id, content)
    
    def search_memory(self, user_id: str, query: str, limit: int = 5) -> List[MemoryEntry]:
        short_results = self.short_term.search_memory(user_id, query, limit)
        remaining = limit - len(short_results)
        
        if remaining > 0:
            long_results = self.long_term.search_memory(user_id, query, remaining)
            short_results.extend(long_results)
        
        return short_results[:limit]
    
    def get_memory(self, user_id: str, memory_id: str) -> Optional[MemoryEntry]:
        result = self.short_term.get_memory(user_id, memory_id)
        if result:
            return result
        return self.long_term.get_memory(user_id, memory_id)
    
    def get_memory_by_type(self, user_id: str, memory_type: str) -> List[MemoryEntry]:
        if memory_type == "short":
            return self.short_term.get_memory_by_type(user_id, memory_type)
        else:
            return self.long_term.get_memory_by_type(user_id, memory_type)
    
    def get_all_memories(self, user_id: str) -> List[MemoryEntry]:
        short_memories = self.short_term.get_all_memories(user_id)
        long_memories = self.long_term.get_all_memories(user_id)
        all_memories = short_memories + long_memories
        all_memories.sort(key=lambda x: x.timestamp, reverse=True)
        return all_memories
    
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        if self.short_term.delete_memory(user_id, memory_id):
            return True
        return self.long_term.delete_memory(user_id, memory_id)
    
    def clear_memory(self, user_id: str) -> bool:
        self.short_term.clear_memory(user_id)
        self.long_term.clear_memory(user_id)
        return True
    
    def clear_memory_by_type(self, user_id: str, memory_type: str) -> bool:
        if memory_type == "short":
            return self.short_term.clear_memory_by_type(user_id, memory_type)
        else:
            return self.long_term.clear_memory_by_type(user_id, memory_type)
    
    def get_memory_count(self, user_id: str) -> int:
        return self.short_term.get_memory_count(user_id) + self.long_term.get_memory_count(user_id)
    
    def get_memory_type(self) -> str:
        return "hybrid"
    
    def persist(self) -> bool:
        return self.long_term.persist()


class RedisHybridMemory(MemoryBase):
    """Redis + 向量库混合记忆存储
    
    架构设计：
    - Redis层：存储短期会话窗口（最近N条消息），支持会话分组
    - 向量库层：存储长期记忆和关键信息，支持语义检索
    - 自动提炼：当会话窗口超过阈值时，自动提炼关键信息
    
    Redis Key 设计：
    - {prefix}session:{user_id}:{group_id}:messages -> List[Message]
    - {prefix}session:{user_id}:{group_id}:metadata -> Hash
    - {prefix}user:{user_id}:groups -> Set[group_id]
    """
    
    def __init__(self):
        self.redis_client = None
        self.vector_store = None
        self.WINDOW_SIZE = 50  # 会话窗口大小
        self.MIGRATION_THRESHOLD = 100  # 迁移阈值
        self.SUMMARY_INTERVAL = 20  # 每20条消息生成一次摘要
        self._initialize()
    
    def _initialize(self):
        try:
            import redis
            from src.config import settings
            
            # 初始化Redis客户端
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=False  # 保持二进制模式用于JSON序列化
            )
            
            # 测试连接
            self.redis_client.ping()
            
            # 初始化向量库（支持自定义embedding服务）
            self.vector_store = ChromaMemory(embedding_service=settings.EMBEDDING_SERVICE_TYPE)
            
            logger.info("RedisHybridMemory初始化成功")
        except ImportError:
            logger.warning("redis库未安装，将使用向量库作为备选")
            self.redis_client = None
            self.vector_store = ChromaMemory(embedding_service=settings.EMBEDDING_SERVICE_TYPE)
        except Exception as e:
            logger.error(f"RedisHybridMemory初始化失败: {str(e)}")
            logger.warning("Redis连接失败，将使用向量库作为备选存储")
            self.redis_client = None
            # 即使Redis失败，也要初始化向量库作为备选
            try:
                self.vector_store = ChromaMemory(embedding_service=settings.EMBEDDING_SERVICE_TYPE)
                logger.info("向量库备选初始化成功")
            except Exception as vec_e:
                logger.error(f"向量库初始化也失败: {str(vec_e)}")
                self.vector_store = None
    
    def _get_session_key(self, user_id: str, group_id: str = "default") -> str:
        """生成会话消息Key"""
        from src.config import settings
        return f"{settings.REDIS_PREFIX}session:{user_id}:{group_id}:messages".encode()
    
    def _get_group_key(self, user_id: str) -> str:
        """生成用户分组Key"""
        from src.config import settings
        return f"{settings.REDIS_PREFIX}user:{user_id}:groups".encode()
    
    def _get_metadata_key(self, user_id: str, group_id: str) -> str:
        """生成会话元数据Key"""
        from src.config import settings
        return f"{settings.REDIS_PREFIX}session:{user_id}:{group_id}:metadata".encode()
    
    def _extract_key_information(self, messages: list) -> dict:
        """从消息列表中提炼关键信息"""
        from src.plugins.model_routers import select_model, call_model
        
        if not messages:
            return {"summary": "", "entities": [], "conclusions": [], "todos": []}
        
        # 合并消息内容
        content = "\n".join([m.get("content", "") for m in messages])
        
        try:
            model = select_model("summarization", "simple")
            if model:
                prompt = f"""
                从以下对话中提取关键信息：
                
                {content}
                
                请输出JSON格式：
                {{
                    "summary": "对话摘要（不超过100字）",
                    "entities": ["实体1", "实体2"],
                    "conclusions": ["结论1", "结论2"],
                    "todos": ["待办1", "待办2"]
                }}
                """
                response = call_model(model, [{"role": "user", "content": prompt}])
                import json
                return json.loads(response)
        except Exception as e:
            logger.error(f"关键信息提炼失败: {str(e)}")
        
        # 降级方案：简单摘要
        return {
            "summary": content[:200] + "..." if len(content) > 200 else content,
            "entities": [],
            "conclusions": [],
            "todos": []
        }
    
    def add_memory(self, user_id: str, entry: MemoryEntry) -> bool:
        # 如果Redis不可用，尝试使用向量库
        if not self.redis_client:
            if self.vector_store:
                return self.vector_store.add_memory(user_id, entry)
            else:
                logger.error("Redis和向量库都不可用，无法添加记忆")
                return False
        
        try:
            # 获取或设置分组ID
            group_id = entry.group_id if hasattr(entry, 'group_id') else "default"
            group_name = entry.group_name if hasattr(entry, 'group_name') else "默认会话"
            
            session_key = self._get_session_key(user_id, group_id)
            group_key = self._get_group_key(user_id)
            metadata_key = self._get_metadata_key(user_id, group_id)
            
            # 添加到Redis会话窗口
            import json
            entry_dict = entry.model_dump()
            self.redis_client.rpush(session_key, json.dumps(entry_dict).encode())
            
            # 更新分组集合
            self.redis_client.sadd(group_key, group_id.encode())
            
            # 更新会话元数据
            self.redis_client.hset(metadata_key, mapping={
                b"group_id": group_id.encode(),
                b"group_name": group_name.encode(),
                b"last_active_at": str(entry.timestamp).encode(),
                b"user_id": user_id.encode()
            })
            
            # 检查是否需要迁移和生成摘要
            count = self.redis_client.llen(session_key)
            
            if count >= self.MIGRATION_THRESHOLD:
                self._migrate_to_vector_store(user_id, session_key, group_id)
            
            # 定期生成摘要
            if count % self.SUMMARY_INTERVAL == 0:
                self._generate_summary(user_id, session_key, group_id)
            
            # 关键信息直接写入向量库
            if hasattr(entry, 'tags') and ("key_info" in entry.tags or "summary" in entry.tags):
                self.vector_store.add_memory(user_id, entry)
            
            return True
        except Exception as e:
            logger.error(f"添加记忆失败: {str(e)}")
            return False
    
    def _migrate_to_vector_store(self, user_id: str, session_key: bytes, group_id: str):
        """将旧消息迁移到向量库"""
        try:
            # 获取需要迁移的消息（最早的一半）
            old_messages = self.redis_client.lrange(session_key, 0, self.WINDOW_SIZE)
            
            import json
            for msg_json in old_messages:
                try:
                    msg_dict = json.loads(msg_json.decode())
                    msg_dict['type'] = 'long'
                    msg_dict['group_id'] = group_id
                    entry = MemoryEntry(**msg_dict)
                    self.vector_store.add_memory(user_id, entry)
                except Exception as e:
                    logger.debug(f"迁移消息失败: {str(e)}")
            
            # 保留最近 WINDOW_SIZE 条
            self.redis_client.ltrim(session_key, -self.WINDOW_SIZE, -1)
        except Exception as e:
            logger.error(f"迁移失败: {str(e)}")
    
    def _generate_summary(self, user_id: str, session_key: bytes, group_id: str):
        """生成会话摘要"""
        try:
            # 获取最近消息
            messages = self.redis_client.lrange(session_key, -self.SUMMARY_INTERVAL, -1)
            
            import json
            message_dicts = [json.loads(m.decode()) for m in messages]
            
            # 提炼关键信息
            key_info = self._extract_key_information(message_dicts)
            
            # 创建摘要记忆条目
            from src.utils import generate_id, get_timestamp
            summary_entry = MemoryEntry(
                id=generate_id(),
                user_id=user_id,
                type='long',
                content=key_info['summary'],
                timestamp=get_timestamp(),
                tags=['summary', 'auto_generated', group_id],
                group_id=group_id,
                group_name=f"分组_{group_id}"
            )
            
            self.vector_store.add_memory(user_id, summary_entry)
            
            # 存储实体和待办
            if key_info['entities']:
                entities_entry = MemoryEntry(
                    id=generate_id(),
                    user_id=user_id,
                    type='long',
                    content=str(key_info['entities']),
                    timestamp=get_timestamp(),
                    tags=['entities', group_id],
                    group_id=group_id
                )
                self.vector_store.add_memory(user_id, entities_entry)
            
        except Exception as e:
            logger.error(f"生成摘要失败: {str(e)}")
    
    def search_memory(self, user_id: str, query: str, limit: int = 5) -> List[MemoryEntry]:
        results = []
        
        try:
            # 1. 从Redis获取所有会话组
            if self.redis_client:
                group_key = self._get_group_key(user_id)
                group_ids = self.redis_client.smembers(group_key)
                
                for gid in group_ids:
                    group_id = gid.decode()
                    session_key = self._get_session_key(user_id, group_id)
                    
                    # 获取最近消息
                    messages = self.redis_client.lrange(session_key, -limit, -1)
                    
                    import json
                    for msg_json in messages:
                        try:
                            msg_dict = json.loads(msg_json.decode())
                            if query.lower() in msg_dict.get('content', '').lower():
                                entry = MemoryEntry(**msg_dict)
                                results.append(entry)
                        except Exception as e:
                            logger.debug(f"解析消息失败: {str(e)}")
            
            # 2. 从向量库检索语义相似内容（检查vector_store是否可用）
            if self.vector_store:
                vector_results = self.vector_store.search_memory(user_id, query, limit)
                results.extend(vector_results)
            else:
                logger.debug("向量库不可用，跳过语义检索")
            
            # 3. 去重并排序
            unique_results = list({r.id: r for r in results}.values())
            unique_results.sort(key=lambda x: x.timestamp, reverse=True)
            
            return unique_results[:limit]
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            # 返回已获取的结果（如果有的话）
            return results[:limit]
    
    def get_memory(self, user_id: str, memory_id: str) -> Optional[MemoryEntry]:
        # 先从Redis查找
        if self.redis_client:
            group_key = self._get_group_key(user_id)
            group_ids = self.redis_client.smembers(group_key)
            
            import json
            for gid in group_ids:
                group_id = gid.decode()
                session_key = self._get_session_key(user_id, group_id)
                messages = self.redis_client.lrange(session_key, 0, -1)
                
                for msg_json in messages:
                    try:
                        msg_dict = json.loads(msg_json.decode())
                        if msg_dict.get('id') == memory_id:
                            return MemoryEntry(**msg_dict)
                    except Exception as e:
                        pass
        
        # 从向量库查找
        return self.vector_store.get_memory(user_id, memory_id)
    
    def get_memory_by_type(self, user_id: str, memory_type: str) -> List[MemoryEntry]:
        if memory_type == 'short' and self.redis_client:
            results = []
            group_key = self._get_group_key(user_id)
            group_ids = self.redis_client.smembers(group_key)
            
            import json
            for gid in group_ids:
                group_id = gid.decode()
                session_key = self._get_session_key(user_id, group_id)
                messages = self.redis_client.lrange(session_key, 0, -1)
                
                for msg_json in messages:
                    try:
                        msg_dict = json.loads(msg_json.decode())
                        if msg_dict.get('type') == 'short':
                            entry = MemoryEntry(**msg_dict)
                            results.append(entry)
                    except Exception as e:
                        pass
            
            results.sort(key=lambda x: x.timestamp, reverse=True)
            return results
        else:
            return self.vector_store.get_memory_by_type(user_id, memory_type)
    
    def get_all_memories(self, user_id: str) -> List[MemoryEntry]:
        results = []
        
        # 从Redis获取
        if self.redis_client:
            group_key = self._get_group_key(user_id)
            group_ids = self.redis_client.smembers(group_key)
            
            import json
            for gid in group_ids:
                group_id = gid.decode()
                session_key = self._get_session_key(user_id, group_id)
                messages = self.redis_client.lrange(session_key, 0, -1)
                
                for msg_json in messages:
                    try:
                        msg_dict = json.loads(msg_json.decode())
                        entry = MemoryEntry(**msg_dict)
                        results.append(entry)
                    except Exception as e:
                        pass
        
        # 从向量库获取
        vector_results = self.vector_store.get_all_memories(user_id)
        results.extend(vector_results)
        
        # 去重排序
        unique_results = list({r.id: r for r in results}.values())
        unique_results.sort(key=lambda x: x.timestamp, reverse=True)
        
        return unique_results
    
    def get_groups(self, user_id: str) -> List[dict]:
        """获取用户的所有会话分组"""
        if not self.redis_client:
            return [{"group_id": "default", "group_name": "默认会话"}]
        
        try:
            groups = []
            group_key = self._get_group_key(user_id)
            group_ids = self.redis_client.smembers(group_key)
            
            for gid in group_ids:
                group_id = gid.decode()
                metadata_key = self._get_metadata_key(user_id, group_id)
                metadata = self.redis_client.hgetall(metadata_key)
                
                groups.append({
                    "group_id": group_id,
                    "group_name": metadata.get(b"group_name", b"default_session").decode(),
                    "last_active_at": int(metadata.get(b"last_active_at", b"0").decode()),
                    "message_count": self.redis_client.llen(self._get_session_key(user_id, group_id))
                })
            
            return sorted(groups, key=lambda x: x['last_active_at'], reverse=True)
        except Exception as e:
            logger.error(f"获取分组失败: {str(e)}")
            return [{"group_id": "default", "group_name": "default_session"}]
    
    def update_memory(self, user_id: str, memory_id: str, content: str) -> bool:
        # 更新Redis中的记忆
        if self.redis_client:
            group_key = self._get_group_key(user_id)
            group_ids = self.redis_client.smembers(group_key)
            
            import json
            for gid in group_ids:
                group_id = gid.decode()
                session_key = self._get_session_key(user_id, group_id)
                messages = self.redis_client.lrange(session_key, 0, -1)
                
                for i, msg_json in enumerate(messages):
                    try:
                        msg_dict = json.loads(msg_json.decode())
                        if msg_dict.get('id') == memory_id:
                            msg_dict['content'] = content
                            msg_dict['timestamp'] = get_timestamp()
                            self.redis_client.lset(session_key, i, json.dumps(msg_dict).encode())
                            return True
                    except Exception as e:
                        pass
        
        # 更新向量库中的记忆
        return self.vector_store.update_memory(user_id, memory_id, content)
    
    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        # 从Redis删除
        if self.redis_client:
            group_key = self._get_group_key(user_id)
            group_ids = self.redis_client.smembers(group_key)
            
            import json
            for gid in group_ids:
                group_id = gid.decode()
                session_key = self._get_session_key(user_id, group_id)
                messages = self.redis_client.lrange(session_key, 0, -1)
                
                new_messages = []
                deleted = False
                for msg_json in messages:
                    try:
                        msg_dict = json.loads(msg_json.decode())
                        if msg_dict.get('id') != memory_id:
                            new_messages.append(msg_json)
                        else:
                            deleted = True
                    except Exception as e:
                        new_messages.append(msg_json)
                
                if deleted:
                    self.redis_client.delete(session_key)
                    for msg in new_messages:
                        self.redis_client.rpush(session_key, msg)
                    return True
        
        # 从向量库删除
        return self.vector_store.delete_memory(user_id, memory_id)
    
    def clear_memory(self, user_id: str) -> bool:
        try:
            # 清空Redis中的会话
            if self.redis_client:
                group_key = self._get_group_key(user_id)
                group_ids = self.redis_client.smembers(group_key)
                
                for gid in group_ids:
                    group_id = gid.decode()
                    session_key = self._get_session_key(user_id, group_id)
                    metadata_key = self._get_metadata_key(user_id, group_id)
                    
                    self.redis_client.delete(session_key)
                    self.redis_client.delete(metadata_key)
                
                self.redis_client.delete(group_key)
            
            # 清空向量库
            self.vector_store.clear_memory(user_id)
            
            return True
        except Exception as e:
            logger.error(f"清空记忆失败: {str(e)}")
            return False
    
    def clear_memory_by_type(self, user_id: str, memory_type: str) -> bool:
        if memory_type == 'short' and self.redis_client:
            try:
                group_key = self._get_group_key(user_id)
                group_ids = self.redis_client.smembers(group_key)
                
                for gid in group_ids:
                    group_id = gid.decode()
                    session_key = self._get_session_key(user_id, group_id)
                    
                    # 删除Redis中的短期记忆
                    self.redis_client.delete(session_key)
                
                return True
            except Exception as e:
                logger.error(f"清空短期记忆失败: {str(e)}")
                return False
        else:
            return self.vector_store.clear_memory_by_type(user_id, memory_type)
    
    def get_memory_count(self, user_id: str) -> int:
        count = 0
        
        # Redis中的消息数
        if self.redis_client:
            group_key = self._get_group_key(user_id)
            group_ids = self.redis_client.smembers(group_key)
            
            for gid in group_ids:
                group_id = gid.decode()
                session_key = self._get_session_key(user_id, group_id)
                count += self.redis_client.llen(session_key)
        
        # 向量库中的消息数
        count += self.vector_store.get_memory_count(user_id)
        
        return count
    
    def get_memory_type(self) -> str:
        return "redis_hybrid"
    
    def persist(self) -> bool:
        return self.vector_store.persist()


# 记忆存储注册表
MEMORY_STORE_REGISTRY = {
    "chroma": ChromaMemory,
    "simple": SimpleMemory,
    "milvus": MilvusMemory,
    "faiss": FAISSMemory,
    "hybrid": HybridMemory,
    "redis_hybrid": RedisHybridMemory
}
