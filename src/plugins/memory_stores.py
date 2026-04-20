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
    
    def __init__(self):
        self.client = None
        self.collections = {}
        self._initialize()
    
    def _initialize(self):
        try:
            import chromadb
            from chromadb.config import Settings
            
            self.client = chromadb.Client(Settings(
                persist_directory=settings.VECTOR_DB_PATH,
                anonymized_telemetry=False
            ))
            
            self.collections = {
                "short_term": self.client.get_or_create_collection("short_term"),
                "long_term": self.client.get_or_create_collection("long_term"),
                "user_preferences": self.client.get_or_create_collection("user_preferences")
            }
            
            logger.info("Chroma记忆存储初始化成功")
        except Exception as e:
            logger.error(f"Chroma记忆存储初始化失败: {str(e)}")
            raise MemoryException(
                message="Chroma初始化失败",
                detail=str(e)
            )
    
    def add_memory(self, user_id: str, entry: MemoryEntry) -> bool:
        try:
            collection = self.collections.get(entry.type, self.collections["long_term"])
            
            if not entry.embedding:
                entry.embedding = [0.0] * 384
            
            collection.add(
                ids=[entry.id],
                documents=[entry.content],
                embeddings=[entry.embedding],
                metadatas=[{
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


# 记忆存储注册表
MEMORY_STORE_REGISTRY = {
    "chroma": ChromaMemory,
    "simple": SimpleMemory,
    "milvus": MilvusMemory,
    "faiss": FAISSMemory,
    "hybrid": HybridMemory
}
