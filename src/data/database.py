import sqlite3
import os
from typing import Optional, List, Dict, Any
from src.types import UserProfile, Message, Skill, MemoryEntry
from src.utils import get_timestamp, setup_logging
from src.config import settings

logger = setup_logging(settings.LOG_LEVEL)


class Database:
    def __init__(self, db_path: str = settings.DATABASE_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_tables()
    
    def _init_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT,
                    writing_style TEXT,
                    preferences TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    role TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                    content,
                    user_id UNINDEXED,
                    role UNINDEXED,
                    timestamp UNINDEXED
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    type TEXT NOT NULL,
                    trigger_patterns TEXT,
                    steps TEXT,
                    metadata TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding TEXT,
                    timestamp INTEGER NOT NULL,
                    tags TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    context TEXT,
                    created_at INTEGER NOT NULL,
                    last_active_at INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # 消息去重表 - 持久化存储已处理的消息ID
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_messages (
                    message_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    processed_at INTEGER NOT NULL,
                    source TEXT
                )
            """)
            
            # 为消息ID创建索引，加速查询
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_messages_id 
                ON processed_messages(message_id)
            """)
            
            conn.commit()
    
    def save_user(self, user: UserProfile) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO users (
                    id, name, role, writing_style, preferences, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user.id,
                user.name,
                user.role,
                user.writing_style,
                str(user.preferences),
                user.created_at,
                user.updated_at
            ))
            conn.commit()
    
    def get_user(self, user_id: str) -> Optional[UserProfile]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                return UserProfile(
                    id=row[0],
                    name=row[1],
                    role=row[2],
                    writing_style=row[3],
                    preferences=eval(row[4]) if row[4] else {},
                    created_at=row[5],
                    updated_at=row[6]
                )
            return None
    
    def save_message(self, message: Message) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO messages (
                    id, user_id, content, role, timestamp, metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                message.id,
                message.user_id,
                message.content,
                message.role,
                message.timestamp,
                str(message.metadata) if message.metadata else None
            ))
            
            conn.commit()
    
    def search_messages(self, user_id: str, query: str, limit: int = 10) -> List[Message]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.* FROM messages m
                JOIN messages_fts f ON m.id = (
                    SELECT id FROM messages WHERE rowid = f.rowid
                )
                WHERE f.content MATCH ? AND m.user_id = ?
                ORDER BY m.timestamp DESC
                LIMIT ?
            """, (query, user_id, limit))
            
            messages = []
            for row in cursor.fetchall():
                messages.append(Message(
                    id=row[0],
                    user_id=row[1],
                    content=row[2],
                    role=row[3],
                    timestamp=row[4],
                    metadata=eval(row[5]) if row[5] else None
                ))
            return messages
    
    def get_recent_messages(self, user_id: str, limit: int = 20) -> List[Message]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM messages WHERE user_id = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (user_id, limit))
            
            messages = []
            for row in cursor.fetchall():
                messages.append(Message(
                    id=row[0],
                    user_id=row[1],
                    content=row[2],
                    role=row[3],
                    timestamp=row[4],
                    metadata=eval(row[5]) if row[5] else None
                ))
            return messages[::-1]
    
    def save_skill(self, skill: Skill) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO skills (
                    id, name, description, type, trigger_patterns, steps, metadata,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                skill.id,
                skill.name,
                skill.description,
                skill.type,
                str(skill.trigger_patterns),
                str([s.model_dump() for s in skill.steps]),
                str(skill.metadata),
                skill.created_at,
                skill.updated_at
            ))
            conn.commit()
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
            row = cursor.fetchone()
            
            if row:
                from src.types import SkillStep
                steps = [SkillStep(**s) for s in eval(row[5])] if row[5] else []
                return Skill(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    type=row[3],
                    trigger_patterns=eval(row[4]) if row[4] else [],
                    steps=steps,
                    metadata=eval(row[6]) if row[6] else {},
                    created_at=row[7],
                    updated_at=row[8]
                )
            return None
    
    def get_all_skills(self) -> List[Skill]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM skills")
            
            skills = []
            for row in cursor.fetchall():
                from src.types import SkillStep
                steps = [SkillStep(**s) for s in eval(row[5])] if row[5] else []
                skills.append(Skill(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    type=row[3],
                    trigger_patterns=eval(row[4]) if row[4] else [],
                    steps=steps,
                    metadata=eval(row[6]) if row[6] else {},
                    created_at=row[7],
                    updated_at=row[8]
                ))
            return skills
    
    def save_memory(self, entry: MemoryEntry) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memory (
                    id, user_id, type, content, embedding, timestamp, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.user_id,
                entry.type,
                entry.content,
                str(entry.embedding) if entry.embedding else None,
                entry.timestamp,
                str(entry.tags) if entry.tags else None
            ))
            conn.commit()
    
    def get_memory_by_type(self, user_id: str, memory_type: str) -> List[MemoryEntry]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM memory WHERE user_id = ? AND type = ?
                ORDER BY timestamp DESC
            """, (user_id, memory_type))
            
            entries = []
            for row in cursor.fetchall():
                entries.append(MemoryEntry(
                    id=row[0],
                    user_id=row[1],
                    type=row[2],
                    content=row[3],
                    embedding=eval(row[4]) if row[4] else None,
                    timestamp=row[5],
                    tags=eval(row[6]) if row[6] else []
                ))
            return entries
    
    def get_memories_by_tag(self, tag: str, user_id: str = None) -> List[MemoryEntry]:
        """
        根据标签查询记忆记录（支持用户隔离）
        
        Args:
            tag: 标签名称（如 file_key）
            user_id: 用户ID（可选，提供时只返回该用户的记录）
        
        Returns:
            包含该标签的记忆记录列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if user_id:
                # 按用户ID和标签查询（用户隔离）
                cursor.execute("""
                    SELECT * FROM memory 
                    WHERE tags LIKE ? AND user_id = ?
                    ORDER BY timestamp DESC
                """, (f"%{tag}%", user_id))
            else:
                # 仅按标签查询
                cursor.execute("""
                    SELECT * FROM memory 
                    WHERE tags LIKE ?
                    ORDER BY timestamp DESC
                """, (f"%{tag}%",))
            
            entries = []
            for row in cursor.fetchall():
                tags = eval(row[6]) if row[6] else []
                if tag in tags:  # 精确验证标签是否存在
                    entries.append(MemoryEntry(
                        id=row[0],
                        user_id=row[1],
                        type=row[2],
                        content=row[3],
                        embedding=eval(row[4]) if row[4] else None,
                        timestamp=row[5],
                        tags=tags
                    ))
            return entries
    
    def clean_old_memories(self, days_to_keep: int = 30):
        """
        清理指定天数前的记忆记录
        
        Args:
            days_to_keep: 保留天数，默认30天
        
        Raises:
            Exception: 清理失败时重新抛出异常，供调用方处理
        """
        cutoff_time = get_timestamp() - (days_to_keep * 24 * 60 * 60)
        
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.cursor()
                
                # 获取删除前的记录数
                cursor.execute("SELECT COUNT(*) FROM memory WHERE timestamp < ?", (cutoff_time,))
                count = cursor.fetchone()[0]
                
                if count > 0:
                    cursor.execute("DELETE FROM memory WHERE timestamp < ?", (cutoff_time,))
                    conn.commit()
                    logger.info(f"清理了 {count} 条过期记忆记录")
                else:
                    logger.info("没有需要清理的过期记忆记录")
                    
            except Exception as e:
                conn.rollback()
                logger.error(f"清理过期记忆失败: {str(e)}")
                raise
    
    def is_message_processed(self, message_id: str) -> bool:
        """检查消息是否已处理过"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM processed_messages WHERE message_id = ?
            """, (message_id,))
            return cursor.fetchone() is not None
    
    def mark_message_processed(self, message_id: str, user_id: str, source: str = "unknown") -> None:
        """标记消息为已处理"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO processed_messages (
                    message_id, user_id, processed_at, source
                ) VALUES (?, ?, ?, ?)
            """, (message_id, user_id, get_timestamp(), source))
            conn.commit()
    
    def cleanup_old_messages(self, days_to_keep: int = 7) -> int:
        """清理过期的已处理消息记录"""
        cutoff_time = get_timestamp() - (days_to_keep * 24 * 60 * 60)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM processed_messages WHERE processed_at < ?
            """, (cutoff_time,))
            deleted = cursor.rowcount
            conn.commit()
            return deleted


db = Database()
