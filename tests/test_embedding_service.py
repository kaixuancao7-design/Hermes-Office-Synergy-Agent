#!/usr/bin/env python3
"""测试 Embedding 服务配置"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.plugins.embedding_services import (
    get_embedding_service, 
    EMBEDDING_SERVICE_REGISTRY,
    OpenAIEmbedding,
    OllamaEmbedding,
    SentenceTransformerEmbedding,
    ZhipuEmbedding,
    MoonshotEmbedding
)
from src.logging_config import get_logger

logger = get_logger("test_embedding")

def test_embedding_services():
    """测试所有可用的 Embedding 服务"""
    print("=" * 60)
    print("测试 Embedding 服务配置")
    print("=" * 60)
    
    print(f"\n可用的 Embedding 服务: {list(EMBEDDING_SERVICE_REGISTRY.keys())}")
    
    # 测试获取默认服务
    print("\n1. 测试获取默认服务:")
    default_service = get_embedding_service("default")
    print(f"   - 默认服务: {type(default_service).__name__ if default_service else 'None'}")
    
    # 测试 OpenAI 服务
    print("\n2. 测试 OpenAI Embedding 服务:")
    openai_service = get_embedding_service("openai")
    print(f"   - 服务实例: {'创建成功' if openai_service else '创建失败'}")
    if openai_service:
        print(f"   - 向量维度: {openai_service.get_dimension()}")
    
    # 测试 Ollama 服务
    print("\n3. 测试 Ollama Embedding 服务:")
    ollama_service = get_embedding_service("ollama")
    print(f"   - 服务实例: {'创建成功' if ollama_service else '创建失败'}")
    if ollama_service:
        print(f"   - 向量维度: {ollama_service.get_dimension()}")
    
    # 测试 SentenceTransformer 服务
    print("\n4. 测试 SentenceTransformer Embedding 服务:")
    st_service = get_embedding_service("sentence_transformer")
    print(f"   - 服务实例: {'创建成功' if st_service else '创建失败'}")
    if st_service:
        print(f"   - 向量维度: {st_service.get_dimension()}")
        
        # 测试向量化功能
        print("   - 测试向量化功能:")
        texts = ["这是一段测试文本", "另一段测试文本"]
        embeddings = st_service.embed(texts)
        if embeddings:
            print(f"     [OK] 成功生成 {len(embeddings)} 个向量")
            print(f"     [OK] 向量维度: {len(embeddings[0])}")
        else:
            print("     [FAIL] 向量化失败")
    
    # 测试 Zhipu 服务
    print("\n5. 测试 ZhipuAI Embedding 服务:")
    zhipu_service = get_embedding_service("zhipu")
    print(f"   - 服务实例: {'创建成功' if zhipu_service else '创建失败'}")
    if zhipu_service:
        print(f"   - 向量维度: {zhipu_service.get_dimension()}")
    
    # 测试 Moonshot 服务
    print("\n6. 测试 Moonshot Embedding 服务:")
    moonshot_service = get_embedding_service("moonshot")
    print(f"   - 服务实例: {'创建成功' if moonshot_service else '创建失败'}")
    if moonshot_service:
        print(f"   - 向量维度: {moonshot_service.get_dimension()}")
    
    print("\n" + "=" * 60)
    print("Embedding 服务测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_embedding_services()
