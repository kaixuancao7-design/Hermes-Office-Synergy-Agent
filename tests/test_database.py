import pytest
from src.types import UserProfile, Message, Skill, SkillStep, MemoryEntry
from src.data.database import Database
from src.utils import generate_id, get_timestamp


class TestDatabase:
    """数据库模块测试"""

    def test_init_database(self):
        """测试数据库初始化"""
        import os
        test_db_path = "./data/test_init.db"
        
        # 确保测试文件不存在
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        
        db = Database(test_db_path)
        assert db is not None
        assert db.db_path == test_db_path
        assert os.path.exists(test_db_path)

    def test_save_and_get_user(self, test_database):
        """测试保存和获取用户"""
        user_id = generate_id()
        user = UserProfile(
            id=user_id,
            name="Test User",
            role="user",
            writing_style="formal",
            preferences={"theme": "dark"},
            created_at=get_timestamp(),
            updated_at=get_timestamp()
        )
        
        test_database.save_user(user)
        retrieved = test_database.get_user(user_id)
        
        assert retrieved is not None
        assert retrieved.id == user_id
        assert retrieved.name == "Test User"
        assert retrieved.role == "user"
        assert retrieved.preferences == {"theme": "dark"}

    def test_get_nonexistent_user(self, test_database):
        """测试获取不存在的用户"""
        user = test_database.get_user("nonexistent_user_id")
        assert user is None

    def test_save_and_get_message(self, test_database):
        """测试保存和获取消息"""
        user_id = generate_id()
        message = Message(
            id=generate_id(),
            user_id=user_id,
            content="Hello, World!",
            role="user",
            timestamp=get_timestamp(),
            metadata={"source": "test"}
        )
        
        test_database.save_message(message)
        messages = test_database.get_recent_messages(user_id)
        
        assert len(messages) == 1
        assert messages[0].content == "Hello, World!"
        assert messages[0].role == "user"

    def test_get_recent_messages_empty(self, test_database):
        """测试获取空消息列表"""
        messages = test_database.get_recent_messages("nonexistent_user")
        assert len(messages) == 0

    def test_save_and_get_skill(self, test_database):
        """测试保存和获取技能"""
        skill_id = generate_id()
        steps = [
            SkillStep(id=generate_id(), action="open_app", parameters={"app": "word"}),
            SkillStep(id=generate_id(), action="create_document", parameters={})
        ]
        skill = Skill(
            id=skill_id,
            name="Create Document",
            description="Create a new document",
            type="preset",
            trigger_patterns=["创建文档", "新建文档"],
            steps=steps,
            metadata={"category": "productivity"},
            created_at=get_timestamp(),
            updated_at=get_timestamp()
        )
        
        test_database.save_skill(skill)
        retrieved = test_database.get_skill(skill_id)
        
        assert retrieved is not None
        assert retrieved.id == skill_id
        assert retrieved.name == "Create Document"
        assert len(retrieved.steps) == 2
        assert retrieved.steps[0].action == "open_app"

    def test_get_all_skills(self, test_database):
        """测试获取所有技能"""
        skills = test_database.get_all_skills()
        assert isinstance(skills, list)

    def test_get_nonexistent_skill(self, test_database):
        """测试获取不存在的技能"""
        skill = test_database.get_skill("nonexistent_skill_id")
        assert skill is None

    def test_save_memory(self, test_database):
        """测试保存记忆条目"""
        entry = MemoryEntry(
            id=generate_id(),
            user_id="test_user",
            type="short",
            content="Test memory content",
            embedding=[0.1, 0.2, 0.3],
            timestamp=get_timestamp(),
            tags=["test", "important"]
        )
        
        test_database.save_memory(entry)
        memories = test_database.get_memory_by_type("test_user", "short")
        
        assert len(memories) >= 1
        assert any(m.content == "Test memory content" for m in memories)

    def test_message_processed_tracking(self, test_database):
        """测试消息处理跟踪"""
        message_id = generate_id()
        user_id = generate_id()
        
        # 初始状态未处理
        assert test_database.is_message_processed(message_id) is False
        
        # 标记为已处理
        test_database.mark_message_processed(message_id, user_id, "test")
        
        # 验证已处理
        assert test_database.is_message_processed(message_id) is True

    def test_cleanup_old_messages(self, test_database):
        """测试清理过期消息"""
        # 添加一条旧消息（时间戳设为很久以前）
        old_timestamp = get_timestamp() - (10 * 24 * 60 * 60)  # 10天前
        message_id = generate_id()
        
        # 直接插入过期消息
        import sqlite3
        with sqlite3.connect(test_database.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO processed_messages (message_id, user_id, processed_at, source)
                VALUES (?, ?, ?, ?)
            """, (message_id, "test_user", old_timestamp, "test"))
            conn.commit()
        
        # 清理过期消息（保留7天内的）
        deleted = test_database.cleanup_old_messages(days_to_keep=7)
        assert deleted >= 1
        
        # 验证已删除
        assert test_database.is_message_processed(message_id) is False
