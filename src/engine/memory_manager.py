from typing import List, Dict, Any, Optional
from src.types import UserProfile, Message, MemoryEntry, Skill
from src.data.database import db
from src.utils import generate_id, get_timestamp, setup_logging, truncate_text
from src.config import settings

logger = setup_logging(settings.LOG_LEVEL)


class MemoryManager:
    def __init__(self):
        self.short_term_memory: Dict[str, List[Message]] = {}
    
    def add_short_term_memory(self, user_id: str, message: Message) -> None:
        if user_id not in self.short_term_memory:
            self.short_term_memory[user_id] = []
        
        self.short_term_memory[user_id].append(message)
        
        if len(self.short_term_memory[user_id]) > 50:
            self._compress_short_term(user_id)
    
    def _compress_short_term(self, user_id: str) -> None:
        messages = self.short_term_memory[user_id]
        if len(messages) <= 30:
            return
        
        compressed = []
        skip_next = False
        
        for i, msg in enumerate(messages):
            if skip_next:
                skip_next = False
                continue
            
            if i + 1 < len(messages) and msg.role == "user":
                next_msg = messages[i + 1]
                if next_msg.role == "assistant":
                    combined = f"User: {truncate_text(msg.content, 100)}\nAssistant: {truncate_text(next_msg.content, 100)}"
                    compressed.append(Message(
                        id=generate_id(),
                        user_id=user_id,
                        content=combined,
                        role="system",
                        timestamp=msg.timestamp,
                        metadata={"compressed": True}
                    ))
                    skip_next = True
                else:
                    compressed.append(msg)
            else:
                compressed.append(msg)
        
        self.short_term_memory[user_id] = compressed[-30:]
    
    def get_short_term_memory(self, user_id: str) -> List[Message]:
        return self.short_term_memory.get(user_id, [])
    
    def save_to_long_term(self, user_id: str) -> None:
        short_term = self.short_term_memory.get(user_id, [])
        
        for msg in short_term:
            if not msg.metadata or not msg.metadata.get("compressed"):
                memory_entry = MemoryEntry(
                    id=generate_id(),
                    user_id=user_id,
                    type="long",
                    content=msg.content,
                    timestamp=msg.timestamp,
                    tags=["conversation"]
                )
                db.save_memory(memory_entry)
        
        self.short_term_memory[user_id] = []
    
    def search_long_term_memory(self, user_id: str, query: str) -> List[MemoryEntry]:
        messages = db.search_messages(user_id, query, limit=10)
        
        return [MemoryEntry(
            id=msg.id,
            user_id=msg.user_id,
            type="long",
            content=msg.content,
            timestamp=msg.timestamp,
            tags=["conversation"]
        ) for msg in messages]
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        return db.get_user(user_id)
    
    def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> None:
        profile = db.get_user(user_id)
        
        if profile:
            for key, value in updates.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            profile.updated_at = get_timestamp()
            db.save_user(profile)
        else:
            new_profile = UserProfile(
                id=user_id,
                name="",
                role="",
                writing_style="",
                preferences=updates.get("preferences", {}),
                created_at=get_timestamp(),
                updated_at=get_timestamp()
            )
            db.save_user(new_profile)
    
    def extract_user_preferences(self, user_id: str, message: str) -> None:
        profile = self.get_user_profile(user_id)
        
        if "markdown" in message.lower() or "Markdown" in message:
            if profile:
                profile.writing_style = "Markdown"
                profile.updated_at = get_timestamp()
                db.save_user(profile)
        
        role_keywords = ["经理", "总监", "工程师", "设计师", "产品"]
        for keyword in role_keywords:
            if keyword in message:
                if profile:
                    profile.role = keyword
                    profile.updated_at = get_timestamp()
                    db.save_user(profile)
                    break


memory_manager = MemoryManager()
