"""自定义技能管理 - 管理用户创建的自定义技能"""

from typing import List, Dict, Any, Optional
from src.types import Skill, SkillStep
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger
from src.services.skill_management import skill_version_manager
from src.services.permission_service import permission_service
from src.services.audit_log_service import audit_log_service

logger = get_logger("skill")


class CustomSkillsManager:
    """自定义技能管理器 - 管理用户创建的自定义技能"""

    def create_custom_skill(self, user_id: str, name: str, description: str, steps: List[Dict[str, Any]]) -> Skill:
        """创建自定义技能（需要检查权限）"""
        # 检查用户是否有权限创建技能
        user_role = permission_service.get_user_role(user_id)
        if not user_role or user_role.role not in ["admin", "developer", "user"]:
            logger.error(f"User {user_id} does not have permission to create skills")
            raise PermissionError("没有创建技能的权限")

        skill_steps = [
            SkillStep(
                id=generate_id(),
                action=step.get("action", "execute"),
                parameters=step.get("parameters", {}),
                next_step_id=step.get("next_step_id"),
                condition=step.get("condition")
            ) for step in steps
        ]

        skill = Skill(
            id=generate_id(),
            name=name,
            description=description,
            type="custom",
            trigger_patterns=[name],
            steps=skill_steps,
            metadata={"user_id": user_id},
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by=user_id
        )

        db.save_skill(skill)
        # 保存初始版本
        skill_version_manager.save_version(skill, "create", "初始版本")

        # 记录审计日志
        audit_log_service.log_skill_create(user_id, skill.id, skill.name)

        logger.info(f"Created custom skill: {name} by user {user_id}")
        return skill

    def update_custom_skill(self, user_id: str, skill_id: str, updates: Dict[str, Any]) -> Optional[Skill]:
        """更新自定义技能（需要检查权限）"""
        skill = db.get_skill(skill_id)
        if not skill:
            return None

        # 检查权限
        permission = permission_service.check_skill_permission(user_id, skill_id, "edit")
        if not permission.allowed:
            logger.error(f"User {user_id} does not have permission to edit skill {skill_id}")
            raise PermissionError("没有编辑技能的权限")

        # 更新字段
        if "name" in updates:
            skill.name = updates["name"]
        if "description" in updates:
            skill.description = updates["description"]
        if "trigger_patterns" in updates:
            skill.trigger_patterns = updates["trigger_patterns"]
        if "steps" in updates:
            skill.steps = [SkillStep(**s) for s in updates["steps"]]
        if "metadata" in updates:
            skill.metadata.update(updates["metadata"])

        # 递增版本号
        skill.version = self._increment_version(skill.version)
        skill.updated_at = get_timestamp()

        db.save_skill(skill)
        # 保存新版本
        change_note = updates.get("change_note", "技能更新")
        skill_version_manager.save_version(skill, "update", change_note)

        # 记录审计日志
        audit_log_service.log_skill_edit(user_id, skill_id, skill.name, change_note)

        logger.info(f"Updated skill: {skill_id} v{skill.version} by user {user_id}")
        return skill

    def get_user_custom_skills(self, user_id: str) -> List[Skill]:
        """获取用户创建的所有自定义技能"""
        all_skills = db.get_all_skills()
        return [skill for skill in all_skills if skill.type == "custom" and skill.created_by == user_id]

    def get_all_custom_skills(self) -> List[Skill]:
        """获取所有自定义技能（管理员可用）"""
        all_skills = db.get_all_skills()
        return [skill for skill in all_skills if skill.type == "custom"]

    def share_custom_skill(self, owner_id: str, skill_id: str, target_user_id: str, permission: str) -> bool:
        """分享自定义技能给其他用户"""
        # 检查所有者权限
        owner_permission = permission_service.check_skill_permission(owner_id, skill_id, "grant")
        if not owner_permission.allowed:
            logger.error(f"User {owner_id} does not have permission to share skill {skill_id}")
            return False

        # 授予权限
        success = permission_service.grant_skill_permission(owner_id, skill_id, target_user_id, permission)

        if success:
            audit_log_service.log_permission_grant(owner_id, 'skill', skill_id, target_user_id, permission)
            logger.info(f"User {owner_id} shared skill {skill_id} with {target_user_id} (permission: {permission})")

        return success

    def _increment_version(self, current_version: str) -> str:
        """递增版本号"""
        parts = current_version.split('.')
        if len(parts) == 3:
            major, minor, patch = parts
            patch = str(int(patch) + 1)
            return f"{major}.{minor}.{patch}"
        return f"{current_version}.1"


# 全局实例
custom_skills_manager = CustomSkillsManager()