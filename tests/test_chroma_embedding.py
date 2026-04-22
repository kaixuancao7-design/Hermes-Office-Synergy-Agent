#!/usr/bin/env python3
"""测试 Chroma 自动向量化功能"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.plugins.memory_stores import ChromaMemory
from src.types import MemoryEntry
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("test_chroma")

def test_chroma_auto_embedding():
    """测试 Chroma 自动向量化功能"""
    print("=" * 60)
    print("测试 Chroma 自动向量化功能")
    print("=" * 60)
    
    # 创建 Chroma 内存实例
    print("\n创建 ChromaMemory 实例...")
    chroma_memory = ChromaMemory()
    print(f"  - 实例创建成功: {chroma_memory}")
    
    # 创建测试记忆条目（不带 embedding）
    print("\n创建测试记忆条目（不带 embedding）...")
    test_entry = MemoryEntry(
        id=generate_id(),
        user_id="test_user",
        type="long",
        content="这是一段测试文本，用于测试 Chroma 的自动向量化功能。",
        embedding=None,  # 不提供 embedding
        timestamp=get_timestamp(),
        tags=["test", "embedding"]
    )
    print(f"  - 条目创建成功，embedding: {test_entry.embedding}")
    
    # 添加记忆
    print("\n添加记忆到 Chroma...")
    success = chroma_memory.add_memory("test_user", test_entry)
    print(f"  - 添加结果: {'成功' if success else '失败'}")
    
    # 搜索记忆
    print("\n搜索记忆...")
    results = chroma_memory.search_memory("test_user", "测试文本", limit=3)
    print(f"  - 搜索结果数量: {len(results)}")
    
    if results:
        print("\n搜索结果详情:")
        for i, result in enumerate(results):
            print(f"  [{i+1}] ID: {result.id[:10]}...")
            print(f"     内容: {result.content[:50]}...")
            print(f"     Embedding: {'存在' if result.embedding else '不存在'}")
            if result.embedding:
                print(f"     Embedding 维度: {len(result.embedding)}")
    
    # 测试带 embedding 的情况
    print("\n" + "=" * 60)
    print("测试手动提供 embedding...")
    manual_entry = MemoryEntry(
        id=generate_id(),
        user_id="test_user",
        type="long",
        content="这是手动提供 embedding 的测试文本。",
        embedding=[0.1] * 384,  # 手动提供 embedding
        timestamp=get_timestamp(),
        tags=["test", "manual_embedding"]
    )
    
    success = chroma_memory.add_memory("test_user", manual_entry)
    print(f"  - 添加结果: {'成功' if success else '失败'}")
    
    # 搜索验证
    results = chroma_memory.search_memory("test_user", "手动提供", limit=3)
    print(f"  - 搜索结果数量: {len(results)}")
    
    print("\n[OK] Chroma 自动向量化测试通过")

if __name__ == "__main__":
    test_chroma_auto_embedding()