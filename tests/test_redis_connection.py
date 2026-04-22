"""Redis连接测试用例"""
import pytest
import redis
from src.config import settings
from src.plugins.memory_stores import RedisHybridMemory


class TestRedisConnection:
    """Redis连接测试"""
    
    def test_redis_ping(self):
        """测试Redis连接是否正常"""
        try:
            client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
            result = client.ping()
            assert result is True
            print(f"✓ Redis连接成功: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except redis.ConnectionError as e:
            print(f"✗ Redis连接失败: {str(e)}")
            pytest.skip("Redis服务器未运行或连接失败")
    
    def test_redis_set_get(self):
        """测试Redis基本操作（set/get）"""
        try:
            client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
            
            test_key = "test_connection_key"
            test_value = "test_connection_value"
            
            # 设置值
            client.set(test_key, test_value)
            
            # 获取值
            result = client.get(test_key)
            assert result == test_value
            
            # 清理测试数据
            client.delete(test_key)
            
            print("✓ Redis基本操作测试通过")
        except redis.ConnectionError as e:
            pytest.skip(f"Redis连接失败: {str(e)}")
    
    def test_redis_hybrid_memory_initialization(self):
        """测试RedisHybridMemory初始化"""
        memory = RedisHybridMemory()
        
        # 检查初始化状态
        if memory.redis_client is not None:
            print("✓ RedisHybridMemory初始化成功，已连接到Redis")
        else:
            print("✓ RedisHybridMemory初始化成功（使用备选存储）")
        
        # 验证向量库已初始化
        assert memory.vector_store is not None
    
    def test_redis_configuration(self):
        """测试Redis配置参数"""
        # 验证配置存在
        assert settings.REDIS_HOST is not None
        assert settings.REDIS_PORT is not None
        assert settings.REDIS_DB is not None
        
        # 验证端口范围
        assert 0 <= settings.REDIS_PORT <= 65535
        
        print(f"✓ Redis配置验证通过: {settings.REDIS_HOST}:{settings.REDIS_PORT}/db{settings.REDIS_DB}")
    
    def test_redis_list_operations(self):
        """测试Redis列表操作"""
        try:
            client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
            
            test_key = "test_list_key"
            
            # 清理可能存在的旧数据
            client.delete(test_key)
            
            # 测试列表操作
            client.rpush(test_key, "item1", "item2", "item3")
            length = client.llen(test_key)
            assert length == 3
            
            items = client.lrange(test_key, 0, -1)
            assert items == ["item1", "item2", "item3"]
            
            # 清理测试数据
            client.delete(test_key)
            
            print("✓ Redis列表操作测试通过")
        except redis.ConnectionError as e:
            pytest.skip(f"Redis连接失败: {str(e)}")
    
    def test_redis_hash_operations(self):
        """测试Redis哈希操作"""
        try:
            client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
            
            test_key = "test_hash_key"
            
            # 清理可能存在的旧数据
            client.delete(test_key)
            
            # 测试哈希操作
            client.hset(test_key, mapping={
                "user_id": "test_user",
                "group_name": "test_group",
                "last_active_at": "1234567890"
            })
            
            result = client.hgetall(test_key)
            assert result["user_id"] == "test_user"
            assert result["group_name"] == "test_group"
            
            # 清理测试数据
            client.delete(test_key)
            
            print("✓ Redis哈希操作测试通过")
        except redis.ConnectionError as e:
            pytest.skip(f"Redis连接失败: {str(e)}")
    
    def test_redis_set_operations(self):
        """测试Redis集合操作"""
        try:
            client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
            
            test_key = "test_set_key"
            
            # 清理可能存在的旧数据
            client.delete(test_key)
            
            # 测试集合操作
            client.sadd(test_key, "group1", "group2", "group3")
            members = client.smembers(test_key)
            assert members == {"group1", "group2", "group3"}
            
            # 清理测试数据
            client.delete(test_key)
            
            print("✓ Redis集合操作测试通过")
        except redis.ConnectionError as e:
            pytest.skip(f"Redis连接失败: {str(e)}")
    
    def test_redis_error_handling(self):
        """测试Redis错误处理"""
        # 使用无效配置测试连接失败情况
        invalid_client = redis.Redis(
            host="invalid_host",
            port=6380,
            db=0,
            socket_timeout=1
        )
        
        with pytest.raises(redis.ConnectionError):
            invalid_client.ping()
        
        print("✓ Redis错误处理测试通过")


if __name__ == "__main__":
    print("\n=== Redis连接测试 ===")
    print(f"测试目标: {settings.REDIS_HOST}:{settings.REDIS_PORT}/db{settings.REDIS_DB}")
    print("=" * 40)
    
    pytest.main([__file__, "-v"])
