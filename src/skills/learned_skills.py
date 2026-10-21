"""Reviewed, idempotent publication of new skills and patch proposals."""
from typing import Optional
from uuid import uuid5, NAMESPACE_URL
from src.types import Skill, SkillDraft
from src.data.database import db
from src.utils import get_timestamp
from src.logging_config import get_logger

logger = get_logger("skill")


class LearnedSkillsManager:
    def create_from_draft(self, user_id: str, draft_id: str, comments: str = "") -> Optional[Skill]:
        from src.services.permission_service import permission_service
        from src.services.skill_verification import validate_definition
        if permission_service.get_user_role(user_id) != "admin":
            raise PermissionError("Only administrators may approve learning drafts")
        existing = db.get_published_skill_id(draft_id)
        if existing:
            return db.get_skill(existing)
        raw = self._get_draft(draft_id)
        if not raw or raw["status"] == "rejected":
            return None
        draft = SkillDraft.model_validate(raw)
        validate_definition(draft)
        metadata = dict(draft.metadata)
        target = metadata.get("target_skill_id")
        base_version = metadata.get("base_version")
        if target:
            original = db.get_skill(target)
            if not original or not base_version or original.version != base_version:
                raise ValueError("Stale patch proposal")
            parts = original.version.split(".")
            version = f"{parts[0]}.{parts[1]}.{int(parts[2])+1}"
            values = original.model_dump()
            values.update(steps=draft.steps, trigger_patterns=draft.trigger_patterns, version=version,
                updated_at=get_timestamp(), metadata={**original.metadata, "draft_id": draft_id, "reviewed_by": user_id})
            skill = Skill.model_validate(values)
        else:
            skill = Skill(id=uuid5(NAMESPACE_URL, "hermes-published:" + draft_id).hex,
                name=draft.skill_name, description=draft.description, type="learned",
                trigger_patterns=draft.trigger_patterns, steps=draft.steps,
                metadata={**metadata, "draft_id": draft_id, "reviewed_by": user_id},
                created_at=get_timestamp(), updated_at=get_timestamp(), created_by=draft.user_id, version="1.0.0")
        published = db.publish_skill_draft(draft_id, user_id, comments, skill, base_version if target else None)
        skill = db.get_skill(published)
        # The DB is authoritative. Export failure cannot undo or duplicate publication.
        try:
            from src.skills.skill_md import skill_md_manager
            skill_md_manager.write_skill_md(skill)
        except Exception as exc:
            logger.warning(f"Reviewed skill export failed: {exc}")
        return skill

    def _get_draft(self, draft_id):
        return db.get_skill_draft(draft_id)


learned_skills_manager = LearnedSkillsManager()
