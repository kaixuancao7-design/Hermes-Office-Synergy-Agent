"""Redis混合记忆存储测试用例"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.plugins.memory_stores import RedisHybridMemory
from src.types import MemoryEntry
from src.utils import generate_id, get_timestamp


class TestRedisHybridMemory:
    """Redis混合记忆存储测试"""
    
    def test_add_memory_with_group(self):
        """测试添加带分组的记忆"""
        with patch('redis.Redis') as mock_redis:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client.llen.return_value = 10
            mock_redis.return_value = mock_client
            
            memory = RedisHybridMemory()
            user_id = "test_user"
            
            entry = MemoryEntry(
                id=generate_id(),
                user_id=user_id,
                type="short",
                content="测试消息内容",
                timestamp=get_timestamp(),
                tags=["test"],
                group_id="work",
                group_name="work_session"
            )
            
            result = memory.add_memory(user_id, entry)
            assert result is True
            mock_client.rpush.assert_called_once()
    
    def test_session_grouping(self):
        """测试会话分组功能"""
        with patch('redis.Redis') as mock_redis:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client.llen.return_value = 10
            mock_redis.return_value = mock_client
            
            memory = RedisHybridMemory()
            user_id = "test_user"
            
            entry1 = MemoryEntry(
                id=generate_id(),
                user_id=user_id,
                type="short",
                content="work message",
                timestamp=get_timestamp(),
                tags=["work"],
                group_id="work",
                group_name="work_session"
            )
            
            entry2 = MemoryEntry(
                id=generate_id(),
                user_id=user_id,
                type="short",
                content="home message",
                timestamp=get_timestamp(),
                tags=["home"],
                group_id="home",
                group_name="home_session"
            )
            
            memory.add_memory(user_id, entry1)
            memory.add_memory(user_id, entry2)
            
            assert mock_client.sadd.call_count == 2
    
    def test_get_groups_returns_list(self):
        """测试获取用户分组列表"""
        with patch('redis.Redis') as mock_redis:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client.smembers.return_value = [b"work", b"home"]
            mock_client.hgetall.side_effect = [
                {b"group_id": b"work", b"group_name": b"work_session", b"last_active_at": b"1234567890"},
                {b"group_id": b"home", b"group_name": b"home_session", b"last_active_at": b"1234567891"}
            ]
            mock_client.llen.return_value = 10
            mock_redis.return_value = mock_client
            
            memory = RedisHybridMemory()
            groups = memory.get_groups("test_user")
            
            assert isinstance(groups, list)
            assert len(groups) == 2
            assert groups[0]["group_id"] in ["work", "home"]
    
    def test_auto_migration_trigger(self):
        """测试自动迁移触发条件"""
        with patch('redis.Redis') as mock_redis:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client.llen.return_value = 100
            mock_redis.return_value = mock_client
            
            memory = RedisHybridMemory()
            memory.MIGRATION_THRESHOLD = 100
            
            user_id = "test_user"
            entry = MemoryEntry(
                id=generate_id(),
                user_id=user_id,
                type="short",
                content="test message",
                timestamp=get_timestamp(),
                tags=["test"]
            )
            
            memory.add_memory(user_id, entry)
            mock_client.lrange.assert_called()
    
    def test_search_memory_combines_sources(self):
        """测试搜索从多个来源获取结果"""
        with patch('redis.Redis') as mock_redis:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client.smembers.return_value = [b"default"]
            mock_client.lrange.return_value = []
            mock_redis.return_value = mock_client
            
            memory = RedisHybridMemory()
            
            mock_vector_search = Mock(return_value=[])
            memory.vector_store.search_memory = mock_vector_search
            
            results = memory.search_memory("test_user", "query")
            
            assert isinstance(results, list)
            mock_vector_search.assert_called_once()
    
    def test_fallback_when_redis_unavailable(self):
        """测试Redis不可用时的降级方案"""
        with patch('redis.Redis') as mock_redis:
            mock_redis.side_effect = Exception("Connection refused")
            
            memory = RedisHybridMemory()
            
            assert memory.redis_client is None
            
            user_id = "test_user"
            entry = MemoryEntry(
                id=generate_id(),
                user_id=user_id,
                type="short",
                content="test message",
                timestamp=get_timestamp(),
                tags=["test"]
            )
            
            result = memory.add_memory(user_id, entry)
            assert result is True
    
    def test_key_information_extraction(self):
        """测试关键信息提炼"""
        # 直接测试方法，不创建完整实例
        messages = [
            {"content": "User asks: What's the weather today?"},
            {"content": "Assistant: It's sunny, 25 degrees."},
            {"content": "User: Let's go to the park."},
            {"content": "Assistant: Great idea! 3 PM?"}
        ]
        
        # 测试离线提炼逻辑（不调用LLM）
        result = RedisHybridMemory._extract_key_information(None, messages)
        
        assert "summary" in result
        assert isinstance(result["entities"], list)
        assert isinstance(result["conclusions"], list)
        assert isinstance(result["todos"], list)
    
    def test_memory_entry_with_group_fields(self):
        """测试MemoryEntry分组字段"""
        entry = MemoryEntry(
            id="test_id",
            user_id="test_user",
            type="short",
            content="test content",
            timestamp=1234567890,
            tags=["test"],
            group_id="custom_group",
            group_name="custom_group_name"
        )
        
        assert entry.group_id == "custom_group"
        assert entry.group_name == "custom_group_name"
        assert hasattr(entry, 'group_id')
        assert hasattr(entry, 'group_name')
    
    def test_memory_type(self):
        """测试记忆类型标识"""
        with patch('redis.Redis') as mock_redis:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client
            
            memory = RedisHybridMemory()
            assert memory.get_memory_type() == "redis_hybrid"
    
    def test_persist_delegates_to_vector_store(self):
        """测试持久化委托给向量库"""
        with patch('redis.Redis') as mock_redis:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client
            
            memory = RedisHybridMemory()
            mock_persist = Mock(return_value=True)
            memory.vector_store.persist = mock_persist
            
            result = memory.persist()
            assert result is True
            mock_persist.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])