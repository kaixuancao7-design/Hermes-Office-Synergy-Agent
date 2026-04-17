import hnswlib
import numpy as np
import os
from typing import List, Dict, Any, Optional, Tuple
from src.utils import setup_logging, generate_id
from src.config import settings

logger = setup_logging(settings.LOG_LEVEL)


class VectorStore:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.index = hnswlib.Index(space="cosine", dim=dimension)
        self.vector_path = settings.VECTOR_DB_PATH
        self.data_store: Dict[int, Dict[str, Any]] = {}
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        os.makedirs(self.vector_path, exist_ok=True)
        index_path = os.path.join(self.vector_path, "index.bin")
        
        if os.path.exists(index_path):
            self.index.load_index(index_path)
            logger.info("Loaded existing vector index")
        else:
            self.index.init_index(max_elements=100000, ef_construction=200, M=16)
            logger.info("Created new vector index")
    
    def add_vector(self, content: str, embedding: List[float], metadata: Dict[str, Any]) -> str:
        vector_id = len(self.data_store)
        
        if len(embedding) != self.dimension:
            raise ValueError(f"Embedding dimension mismatch: expected {self.dimension}, got {len(embedding)}")
        
        self.index.add_items(np.array([embedding]), np.array([vector_id]))
        self.data_store[vector_id] = {
            "content": content,
            "embedding": embedding,
            "metadata": metadata,
            "id": generate_id()
        }
        
        self._save_index()
        return self.data_store[vector_id]["id"]
    
    def search(self, query_embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
        if len(query_embedding) != self.dimension:
            raise ValueError(f"Query embedding dimension mismatch: expected {self.dimension}, got {len(query_embedding)}")
        
        labels, distances = self.index.knn_query(np.array([query_embedding]), k=k)
        
        results = []
        for i, label in enumerate(labels[0]):
            if label in self.data_store:
                results.append({
                    **self.data_store[label],
                    "distance": distances[0][i]
                })
        
        return sorted(results, key=lambda x: x["distance"])
    
    def delete_vector(self, vector_id: str) -> bool:
        for idx, data in self.data_store.items():
            if data["id"] == vector_id:
                self.index.mark_deleted(idx)
                del self.data_store[idx]
                self._save_index()
                return True
        return False
    
    def get_all_vectors(self) -> List[Dict[str, Any]]:
        return list(self.data_store.values())
    
    def _save_index(self):
        index_path = os.path.join(self.vector_path, "index.bin")
        self.index.save_index(index_path)
    
    def clear(self):
        self.index = hnswlib.Index(space="cosine", dim=self.dimension)
        self.index.init_index(max_elements=100000, ef_construction=200, M=16)
        self.data_store = {}
        self._save_index()


class RAGManager:
    def __init__(self):
        self.vector_store = VectorStore()
    
    def add_document(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        embedding = self._generate_embedding(content)
        return self.vector_store.add_vector(content, embedding, metadata or {})
    
    def query(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        embedding = self._generate_embedding(query)
        return self.vector_store.search(embedding, k)
    
    def _generate_embedding(self, text: str) -> List[float]:
        import random
        return [random.random() for _ in range(384)]


vector_store = VectorStore()
rag_manager = RAGManager()
