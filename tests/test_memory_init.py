#!/usr/bin/env python3
"""测试记忆存储初始化"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.plugins import init_plugins, get_memory_store
from src.config import settings
from src.logging_config import get_logger

logger = get_logger("test_memory")

def test_memory_store_init():
    """测试记忆存储初始化"""
    print("=" * 60)
    print("测试记忆存储初始化")
    print("=" * 60)
    
    print(f"\n当前配置的记忆存储类型: {settings.MEMORY_STORE_TYPE}")
    
    # 初始化插件
    print("\n初始化插件...")
    success = init_plugins()
    
    if not success:
        print("[FAIL] 插件初始化失败")
        return
    
    # 获取记忆存储
    memory_store = get_memory_store()
    
    print(f"\n记忆存储实例: {memory_store}")
    print(f"记忆存储类型: {type(memory_store).__name__ if memory_store else 'None'}")
    
    if memory_store:
        print("\n检查内部组件:")
        
        # 检查 Redis 客户端
        if hasattr(memory_store, 'redis_client'):
            print(f"  - Redis客户端: {'可用' if memory_store.redis_client else '不可用'}")
        
        # 检查向量库
        if hasattr(memory_store, 'vector_store'):
            print(f"  - 向量库: {'可用' if memory_store.vector_store else '不可用'}")
        
        # 测试搜索功能
        print("\n测试搜索功能...")
        try:
            results = memory_store.search_memory("test_user", "测试查询", limit=3)
            print(f"  - 搜索结果: {'成功' if results is not None else '失败'}")
            print(f"  - 结果数量: {len(results) if results else 0}")
        except Exception as e:
            print(f"  - 搜索失败: {str(e)}")
        
        print("\n[OK] 记忆存储测试通过")
    else:
        print("\n[FAIL] 记忆存储为 None")

if __name__ == "__main__":
    test_memory_store_init()