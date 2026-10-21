"""Memory and user-profile services sharing the configured store and SQLite database."""
from src.plugins import get_memory_store
from src.types import MemoryEntry, UserProfile
from src.data.database import db
from src.utils import generate_id, get_timestamp


class MemoryManager:
    def store_memory(self, user_id, content, memory_type="short"):
        store = get_memory_store()
        if store is None:
            return False
        entry = MemoryEntry(id=generate_id(), user_id=user_id, type=memory_type, content=content,
            timestamp=get_timestamp(), tags=[memory_type])
        return store.add_memory(user_id, entry) if hasattr(store, "add_memory") else store.store(f"memory:{user_id}:{entry.id}", entry.model_dump())

    def retrieve_memory(self, user_id, query, limit=5):
        store = get_memory_store()
        return store.search_memory(user_id, query, limit) if store and hasattr(store, "search_memory") else []

    def search_long_term_memory(self, user_id, query, limit=5):
        store = get_memory_store()
        if store is None:
            return []
        if store.get_memory_type() == "simple":
            return store.search_memory(user_id, query, limit, memory_type="long")
        return [entry for entry in self.retrieve_memory(user_id, query, 100) if entry.type == "long"][:limit]

    def delete_memory(self, user_id, memory_id):
        store = get_memory_store()
        return store.delete_memory(user_id, memory_id) if store and hasattr(store, "delete_memory") else False

    def get_user_memories(self, user_id, memory_type=None):
        store = get_memory_store()
        return store.get_user_memories(user_id, memory_type) if store and hasattr(store, "get_user_memories") else []

    def get_user_profile(self, user_id):
        return db.get_user(user_id)

    def update_user_profile(self, user_id, updates):
        allowed = {"name", "writing_style", "preferences"}
        if not updates or set(updates) - allowed:
            raise ValueError("Only name, writing_style and preferences may be updated")
        profile = db.get_user(user_id)
        if profile is None:
            profile = UserProfile(id=user_id, name=user_id, role=db.get_user_role(user_id) or "guest",
                writing_style="", preferences={}, created_at=get_timestamp(), updated_at=get_timestamp())
        data = {**profile.model_dump(), **updates, "updated_at": get_timestamp()}
        profile = UserProfile.model_validate(data)
        db.save_user(profile)
        return profile


memory_manager = MemoryManager()
