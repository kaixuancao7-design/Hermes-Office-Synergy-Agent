"""Compatibility plugins delegating skill rules to the domain manager.

No independent skill cache or mutation implementation lives in this layer.
"""
from src.plugins.base import SkillManagerBase
from src.tools.runtime import current_user


def _manager():
    from src.skills.manager import skill_manager
    return skill_manager


def _actor():
    user = current_user.get()
    if not user:
        raise PermissionError("Authenticated skill identity required")
    return user


class DatabaseSkillManager(SkillManagerBase):
    def get_all_skills(self):
        return _manager().get_all_skills(current_user.get())

    def get_skill(self, skill_id):
        return _manager().get_skill(skill_id)

    def find_relevant_skill(self, query, user_id=None):
        actor = current_user.get() or user_id
        if not actor:
            raise PermissionError("Authenticated skill identity required")
        return _manager().find_relevant_skill(query, actor)

    def create_skill(self, skill_data):
        if skill_data.get("type", "custom") != "custom":
            raise ValueError("This interface creates custom skills only")
        name, steps = skill_data.get("name"), skill_data.get("steps")
        if not name or not steps:
            raise ValueError("Skill name and steps are required")
        return _manager().create_custom_skill(_actor(), name,
            skill_data.get("description", ""), steps,
            trigger_patterns=skill_data.get("trigger_patterns", []),
            metadata=skill_data.get("metadata", {}))

    def update_skill(self, skill_id, updates):
        return _manager().update_skill(_actor(), skill_id, updates)

    def delete_skill(self, skill_id):
        return _manager().delete_skill(_actor(), skill_id)

    def get_manager_type(self):
        return "database"


class HybridSkillManager(DatabaseSkillManager):
    """Preset and persisted skills are loaded by the same domain manager."""
    def get_manager_type(self):
        return "hybrid"


SKILL_MANAGER_REGISTRY = {"hybrid": HybridSkillManager, "database": DatabaseSkillManager}
