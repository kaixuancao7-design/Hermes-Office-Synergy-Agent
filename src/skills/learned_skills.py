"""学习生成技能管理 - 管理通过学习循环生成的技能"""

from typing import List, Dict, Any, Optional
from src.types import Skill, SkillStep, SkillDraft, AssumptionChecklist
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger
from src.services.skill_management import skill_version_manager
from src.services.permission_service import permission_service
from src.services.audit_log_service import audit_log_service
from src.engine.learning_cycle import learning_cycle

logger = get_logger("skill")


class LearnedSkillsManager:
    """学习生成技能管理器 - 管理通过用户反馈学习生成的技能"""

    def create_draft(self, user_id: str, feedback: str, correction: str) -> SkillDraft:
        """创建技能草稿（从用户反馈）"""
        draft = SkillDraft(
            id=generate_id(),
            user_id=user_id,
            feedback=feedback,
            correction=correction,
            status="draft",
            created_at=get_timestamp(),
            updated_at=get_timestamp()
        )

        db.save_draft(draft)
        logger.info(f"Created skill draft: {draft.id} by user {user_id}")

        return draft

    def process_draft(self, draft_id: str) -> AssumptionChecklist:
        """处理草稿，进行假设澄清检查"""
        draft = db.get_draft(draft_id)
        if not draft:
            return AssumptionChecklist(
                is_valid=False,
                core_need="",
                ambiguities=["草稿不存在"],
                resources=[],
                permissions_needed=[],
                potential_exceptions=[],
                compliance_risks=[],
                confidence_score=0.0
            )

        # 调用学习循环进行假设澄清
        return learning_cycle.clarify_assumptions(draft.correction)

    def refine_draft(self, draft_id: str, assumptions: Dict[str, Any]) -> Optional[SkillDraft]:
        """根据假设检查结果完善草稿"""
        draft = db.get_draft(draft_id)
        if not draft:
            return None

        draft.assumptions = assumptions
        draft.status = "refined"
        draft.updated_at = get_timestamp()

        db.save_draft(draft)
        logger.info(f"Refined skill draft: {draft_id}")

        return draft

    def create_from_draft(self, user_id: str, draft_id: str) -> Optional[Skill]:
        """从草稿创建正式技能"""
        draft = db.get_draft(draft_id)
        if not draft:
            logger.error(f"Draft {draft_id} not found")
            return None

        # 检查用户权限
        user_role = permission_service.get_user_role(user_id)
        if not user_role or user_role.role not in ["admin", "developer"]:
            logger.error(f"User {user_id} does not have permission to create learned skills")
            return None

        # 使用学习循环生成技能步骤
        skill_steps = learning_cycle.generate_skill_steps(draft.correction)

        if not skill_steps:
            logger.error(f"Failed to generate skill steps from draft {draft_id}")
            return None

        # 转换为 SkillStep 对象
        steps = [SkillStep(**step) for step in skill_steps]

        # 从用户反馈中提取名称和描述
        name = self._extract_skill_name(draft.correction)
        description = self._extract_skill_description(draft.correction)

        skill = Skill(
            id=generate_id(),
            name=name,
            description=description,
            type="learned",
            trigger_patterns=[name, draft.feedback[:50]],
            steps=steps,
            metadata={
                "draft_id": draft_id,
                "user_feedback": draft.feedback,
                "correction": draft.correction
            },
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by=user_id
        )

        db.save_skill(skill)
        skill_version_manager.save_version(skill, "create", "从用户反馈学习生成")

        # 更新草稿状态
        draft.status = "completed"
        draft.skill_id = skill.id
        db.save_draft(draft)

        # 记录审计日志
        audit_log_service.log_skill_create(user_id, skill.id, skill.name)

        logger.info(f"Created learned skill: {name} from draft {draft_id}")
        return skill

    def get_user_drafts(self, user_id: str) -> List[SkillDraft]:
        """获取用户的所有草稿"""
        return db.get_user_drafts(user_id)

    def get_draft(self, draft_id: str) -> Optional[SkillDraft]:
        """获取单个草稿"""
        return db.get_draft(draft_id)

    def delete_draft(self, user_id: str, draft_id: str) -> bool:
        """删除草稿"""
        draft = db.get_draft(draft_id)
        if not draft:
            return False

        # 检查权限（只能删除自己的草稿）
        if draft.user_id != user_id:
            logger.error(f"User {user_id} cannot delete draft {draft_id}")
            return False

        db.delete_draft(draft_id)
        logger.info(f"Deleted draft: {draft_id} by user {user_id}")
        return True

    def get_all_learned_skills(self) -> List[Skill]:
        """获取所有学习生成的技能"""
        all_skills = db.get_all_skills()
        return [skill for skill in all_skills if skill.type == "learned"]

    def _extract_skill_name(self, text: str) -> str:
        """从文本中提取技能名称"""
        # 简单的提取逻辑，可以根据需要扩展
        keywords = ["技能", "功能", "能力", "任务", "流程"]
        for keyword in keywords:
            idx = text.find(keyword)
            if idx > 0:
                # 提取关键词前后的内容作为名称
                start = max(0, idx - 10)
                end = min(len(text), idx + 20)
                return text[start:end].strip()[:50]
        return "学习技能_" + generate_id()[:8]

    def _extract_skill_description(self, text: str) -> str:
        """从文本中提取技能描述"""
        return text[:200]


# 全局实例
learned_skills_manager = LearnedSkillsManager()