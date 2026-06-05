import ast
import json
import sqlite3
import os
from typing import Optional, List, Dict, Any
from src.types import UserProfile, Message, Skill, MemoryEntry
from src.utils import get_timestamp
from src.logging_config import get_logger
from src.config import settings

logger = get_logger("data")


def _safe_deserialize(value: str, default=None):
    """安全反序列化 — 先尝试 json.loads()，失败则回退到 ast.literal_eval()

    新数据使用 json.dumps() 序列化 → json.loads() 反序列化
    旧数据使用 str() 序列化（Python repr）→ ast.literal_eval() 兼容读取
    """
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            logger.warning(f"无法反序列化: {str(value)[:100]}")
            return default


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

            # 权限系统表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL DEFAULT 'guest',
                    department TEXT,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS permissions (
                    id TEXT PRIMARY KEY,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    granted_by TEXT NOT NULL,
                    granted_at INTEGER NOT NULL,
                    scope_type TEXT DEFAULT 'user',
                    scope_value TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_permissions_user
                ON permissions(user_id, resource_type)
            """)

            # 学习循环 — 技能草稿表（三闸门：捕获→学习→应用）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skill_drafts (
                    id TEXT PRIMARY KEY,
                    skill_name TEXT NOT NULL DEFAULT '',
                    description TEXT DEFAULT '',
                    trigger_patterns TEXT DEFAULT '[]',
                    steps TEXT DEFAULT '[]',
                    original_context TEXT DEFAULT '',
                    original_output TEXT DEFAULT '',
                    corrected_output TEXT DEFAULT '',
                    user_intent TEXT DEFAULT '',
                    user_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    review_comments TEXT,
                    reviewed_by TEXT,
                    reviewed_at INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_skill_drafts_user
                ON skill_drafts(user_id, status)
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
                json.dumps(user.preferences, ensure_ascii=False),
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
                    preferences=_safe_deserialize(row[4], {}),
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
                json.dumps(message.metadata, ensure_ascii=False) if message.metadata else None
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
                    metadata=_safe_deserialize(row[5])
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
                    metadata=_safe_deserialize(row[5])
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
                json.dumps(skill.trigger_patterns, ensure_ascii=False),
                json.dumps([s.model_dump() for s in skill.steps], ensure_ascii=False),
                json.dumps(skill.metadata, ensure_ascii=False),
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
                steps_raw = _safe_deserialize(row[5], [])
                steps = [SkillStep(**s) for s in steps_raw] if steps_raw else []
                return Skill(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    type=row[3],
                    trigger_patterns=_safe_deserialize(row[4], []),
                    steps=steps,
                    metadata=_safe_deserialize(row[6], {}),
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
                steps_raw = _safe_deserialize(row[5], [])
                steps = [SkillStep(**s) for s in steps_raw] if steps_raw else []
                skills.append(Skill(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    type=row[3],
                    trigger_patterns=_safe_deserialize(row[4], []),
                    steps=steps,
                    metadata=_safe_deserialize(row[6], {}),
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
                json.dumps(entry.embedding) if entry.embedding else None,
                entry.timestamp,
                json.dumps(entry.tags, ensure_ascii=False) if entry.tags else None
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
                    embedding=_safe_deserialize(row[4]),
                    timestamp=row[5],
                    tags=_safe_deserialize(row[6], [])
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
                tags = _safe_deserialize(row[6], [])
                if tag in tags:  # 精确验证标签是否存在
                    entries.append(MemoryEntry(
                        id=row[0],
                        user_id=row[1],
                        type=row[2],
                        content=row[3],
                        embedding=_safe_deserialize(row[4]),
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


    # ==================== 权限管理方法 ====================

    def set_user_role(self, user_id: str, role: str, department: str = None) -> bool:
        """设置用户角色"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO user_roles (user_id, role, department, created_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, role, department, get_timestamp()))
            conn.commit()
            return True

    def get_user_role(self, user_id: str) -> Optional[str]:
        """获取用户角色"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT role FROM user_roles WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_user_department(self, user_id: str) -> Optional[str]:
        """获取用户部门"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT department FROM user_roles WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row and row[0] else None

    def grant_permission(self, perm_id: str, resource_type: str, resource_id: str,
                         user_id: str, permission: str, granted_by: str,
                         scope_type: str = "user", scope_value: str = None) -> bool:
        """授予权限"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO permissions
                (id, resource_type, resource_id, user_id, permission, granted_by, granted_at, scope_type, scope_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (perm_id, resource_type, resource_id, user_id, permission, granted_by, get_timestamp(), scope_type, scope_value))
            conn.commit()
            return True

    def revoke_permission(self, resource_type: str, resource_id: str,
                          user_id: str, permission: str) -> bool:
        """撤销权限"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM permissions
                WHERE resource_type = ? AND resource_id = ? AND user_id = ? AND permission = ?
            """, (resource_type, resource_id, user_id, permission))
            deleted = cursor.rowcount
            conn.commit()
            return deleted > 0

    def check_permission(self, user_id: str, resource_type: str,
                         resource_id: str, permission: str) -> bool:
        """检查用户是否有指定权限"""
        user_role = self.get_user_role(user_id)
        if user_role == "admin":
            return True
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM permissions
                WHERE user_id = ? AND resource_type = ? AND resource_id = ? AND permission = ?
            """, (user_id, resource_type, resource_id, permission))
            return cursor.fetchone() is not None

    def get_user_permissions(self, user_id: str) -> list:
        """获取用户所有权限"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT resource_type, resource_id, permission, scope_type, scope_value
                FROM permissions WHERE user_id = ?
            """, (user_id,))
            return [
                {"resource_type": r[0], "resource_id": r[1],
                 "permission": r[2], "scope_type": r[3], "scope_value": r[4]}
                for r in cursor.fetchall()
            ]


    # ==================== 会话持久化方法 ====================

    def save_session(self, session_id: str, user_id: str, context_json: str,
                     created_at: int, last_active_at: int) -> None:
        """持久化保存会话"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (id, user_id, context, created_at, last_active_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, user_id, context_json, created_at, last_active_at))
            conn.commit()

    def load_sessions(self) -> list:
        """加载所有已持久化的会话"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_id, context, created_at, last_active_at FROM sessions")
            return [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "context": row[2],
                    "created_at": row[3],
                    "last_active_at": row[4],
                }
                for row in cursor.fetchall()
            ]

    def delete_session(self, session_id: str) -> None:
        """删除指定会话"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()

    # ==================== 技能草稿方法（三闸门学习循环） ====================

    def save_skill_draft(self, draft: dict) -> None:
        """保存或更新技能草稿"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO skill_drafts (
                    id, skill_name, description, trigger_patterns, steps,
                    original_context, original_output, corrected_output,
                    user_intent, user_id, created_at, status,
                    review_comments, reviewed_by, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                draft["id"],
                draft.get("skill_name", ""),
                draft.get("description", ""),
                json.dumps(draft.get("trigger_patterns", []), ensure_ascii=False),
                json.dumps([s if isinstance(s, dict) else s.model_dump() for s in draft.get("steps", [])], ensure_ascii=False),
                draft.get("original_context", ""),
                draft.get("original_output", ""),
                draft.get("corrected_output", ""),
                draft.get("user_intent", ""),
                draft["user_id"],
                draft.get("created_at", get_timestamp()),
                draft.get("status", "draft"),
                draft.get("review_comments"),
                draft.get("reviewed_by"),
                draft.get("reviewed_at"),
            ))
            conn.commit()

    def get_skill_draft(self, draft_id: str) -> Optional[dict]:
        """获取单个技能草稿"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM skill_drafts WHERE id = ?", (draft_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_draft_dict(row)
            return None

    def get_pending_skill_drafts(self) -> list:
        """获取所有待审核的技能草稿"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM skill_drafts WHERE status IN ('pending_review', 'draft') ORDER BY created_at DESC"
            )
            return [self._row_to_draft_dict(row) for row in cursor.fetchall()]

    def get_skill_drafts_by_user(self, user_id: str, status: str = None) -> list:
        """获取指定用户的技能草稿"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM skill_drafts WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                    (user_id, status),
                )
            else:
                cursor.execute(
                    "SELECT * FROM skill_drafts WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,),
                )
            return [self._row_to_draft_dict(row) for row in cursor.fetchall()]

    def update_skill_draft_status(self, draft_id: str, status: str,
                                   reviewer_id: str = None, comments: str = None) -> bool:
        """更新技能草稿审核状态"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE skill_drafts
                SET status = ?, reviewed_by = ?, review_comments = ?, reviewed_at = ?
                WHERE id = ?
            """, (status, reviewer_id, comments, get_timestamp(), draft_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_learning_stats(self, user_id: str = None) -> dict:
        """获取学习统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    "SELECT status, COUNT(*) FROM skill_drafts WHERE user_id = ? GROUP BY status",
                    (user_id,),
                )
            else:
                cursor.execute(
                    "SELECT status, COUNT(*) FROM skill_drafts GROUP BY status"
                )
            status_counts = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) FROM skills WHERE type = 'learned'")
            learned_count = cursor.fetchone()[0]

            return {
                "drafts": status_counts.get("draft", 0),
                "pending_review": status_counts.get("pending_review", 0),
                "approved": status_counts.get("approved", 0),
                "rejected": status_counts.get("rejected", 0),
                "learned_skills_created": learned_count,
                "total_corrections_captured": sum(status_counts.values()),
            }

    @staticmethod
    def _row_to_draft_dict(row) -> dict:
        """将数据库行转换为草稿字典"""
        return {
            "id": row[0],
            "skill_name": row[1],
            "description": row[2],
            "trigger_patterns": _safe_deserialize(row[3], []),
            "steps": _safe_deserialize(row[4], []),
            "original_context": row[5],
            "original_output": row[6],
            "corrected_output": row[7],
            "user_intent": row[8],
            "user_id": row[9],
            "created_at": row[10],
            "status": row[11],
            "review_comments": row[12],
            "reviewed_by": row[13],
            "reviewed_at": row[14],
        }


db = Database()
