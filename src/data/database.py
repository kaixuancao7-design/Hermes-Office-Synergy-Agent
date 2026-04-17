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
                INSERT INTO messages (
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
            
            cursor.execute("""
                INSERT INTO messages_fts (rowid, content, user_id, role, timestamp)
                VALUES ((SELECT last_insert_rowid()), ?, ?, ?, ?)
            """, (message.content, message.user_id, message.role, message.timestamp))
            
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


db = Database()
