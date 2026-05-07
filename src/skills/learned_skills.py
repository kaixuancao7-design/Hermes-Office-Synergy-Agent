"""学习生成技能管理 - 管理通过学习循环生成的技能（Claude范式增强版）"""

import yaml
from typing import List, Dict, Any, Optional
from pathlib import Path
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
    """学习生成技能管理器 - 管理通过用户反馈学习生成的技能（支持Claude范式）"""

    def __init__(self):
        self._learning_cache = {}

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

    def suggest_skill_structure(self, draft_id: str) -> Dict[str, Any]:
        """为草稿建议技能结构（Claude范式）"""
        draft = db.get_draft(draft_id)
        if not draft:
            return {}

        # 使用学习循环生成建议的技能结构
        suggestions = learning_cycle.suggest_skill_structure(draft.correction)
        
        # 转换为Claude范式格式
        return {
            "name": suggestions.get("name", self._extract_skill_name(draft.correction)),
            "description": suggestions.get("description", draft.correction[:200]),
            "tags": suggestions.get("tags", ["learned", "auto-generated"]),
            "triggers": suggestions.get("triggers", [draft.feedback[:50]]),
            "workflow": suggestions.get("steps", []),
            "input_schema": suggestions.get("input_schema", {}),
            "output_schema": suggestions.get("output_schema", {})
        }

    def create_from_draft(self, user_id: str, draft_id: str, auto_confirm: bool = False) -> Optional[Skill]:
        """从草稿创建正式技能（支持Claude范式）"""
        draft = db.get_draft(draft_id)
        if not draft:
            logger.error(f"Draft {draft_id} not found")
            return None

        user_role = permission_service.get_user_role(user_id)
        if not user_role or user_role.role not in ["admin", "developer", "user"]:
            logger.error(f"User {user_id} does not have permission to create learned skills")
            return None

        # 获取建议的技能结构
        structure = self.suggest_skill_structure(draft_id)
        
        if not structure or not structure.get("workflow"):
            # 如果没有建议结构，使用学习循环生成
            skill_steps = learning_cycle.generate_skill_steps(draft.correction)
            if not skill_steps:
                logger.error(f"Failed to generate skill steps from draft {draft_id}")
                return None
            steps = [SkillStep(**step) for step in skill_steps]
        else:
            # 使用建议的结构（Claude范式）
            steps = []
            workflow = structure.get("workflow", [])
            
            for idx, step_def in enumerate(workflow):
                step_id = step_def.get("id", f"step_{idx + 1}")
                params = step_def.get("parameters", {})
                
                # 处理需要确认的步骤
                if step_def.get("requires_confirmation") and step_def.get("confirmation_prompt"):
                    params["_prompt"] = step_def["confirmation_prompt"]
                
                steps.append(SkillStep(
                    id=step_id,
                    action=step_def.get("tool", step_def.get("action", "execute")),
                    parameters=params,
                    next_step_id=workflow[idx + 1]["id"] if idx < len(workflow) - 1 else None,
                    condition="await_confirmation" if step_def.get("requires_confirmation") else None
                ))

        name = structure.get("name", self._extract_skill_name(draft.correction))
        description = structure.get("description", self._extract_skill_description(draft.correction))

        skill = Skill(
            id=generate_id(),
            name=name,
            description=description,
            type="learned",
            trigger_patterns=structure.get("triggers", [name, draft.feedback[:50]]),
            steps=steps,
            metadata={
                "draft_id": draft_id,
                "user_feedback": draft.feedback,
                "correction": draft.correction,
                "tags": structure.get("tags", ["learned", "auto-generated"]),
                "source": "learned",
                "input_schema": structure.get("input_schema"),
                "output_schema": structure.get("output_schema"),
                "auto_confirm": auto_confirm
            },
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by=user_id
        )

        db.save_skill(skill)
        skill_version_manager.save_version(skill, "create", "从用户反馈学习生成")

        draft.status = "completed"
        draft.skill_id = skill.id
        db.save_draft(draft)

        audit_log_service.log_skill_create(user_id, skill.id, skill.name)

        logger.info(f"Created learned skill: {name} from draft {draft_id}")
        return skill

    def export_learned_skill_to_yaml(self, skill_id: str) -> str:
        """导出学习生成的技能为YAML格式"""
        skill = db.get_skill(skill_id)
        if not skill or skill.type != "learned":
            raise ValueError(f"学习技能不存在: {skill_id}")

        definition = {
            "name": skill.name,
            "description": skill.description,
            "type": "learned",
            "version": skill.version,
            "tags": skill.metadata.get("tags", ["learned", "auto-generated"]),
            "triggers": [{"pattern": p, "confidence": 0.7} for p in skill.trigger_patterns],
            "workflow": [],
            "metadata": {
                "user_feedback": skill.metadata.get("user_feedback", ""),
                "correction": skill.metadata.get("correction", "")
            }
        }

        for step in skill.steps:
            step_def = {
                "id": step.id,
                "tool": step.action,
                "parameters": step.parameters,
                "description": step.parameters.get("_prompt", "")
            }
            
            if step.condition == "await_confirmation":
                step_def["requires_confirmation"] = True
                step_def["confirmation_prompt"] = step.parameters.get("_prompt", "")
                step_def["parameters"] = {k: v for k, v in step.parameters.items() if not k.startswith("_")}

            definition["workflow"].append(step_def)

        if "input_schema" in skill.metadata:
            definition["input_schema"] = skill.metadata["input_schema"]
        if "output_schema" in skill.metadata:
            definition["output_schema"] = skill.metadata["output_schema"]

        return yaml.dump(definition, default_flow_style=False, allow_unicode=True)

    def improve_existing_skill(self, user_id: str, skill_id: str, feedback: str) -> Optional[Skill]:
        """根据用户反馈改进现有技能"""
        skill = db.get_skill(skill_id)
        if not skill:
            return None

        permission = permission_service.check_skill_permission(user_id, skill_id, "edit")
        if not permission.allowed:
            logger.error(f"User {user_id} does not have permission to improve skill {skill_id}")
            return None

        # 使用学习循环分析反馈并生成改进建议
        improvements = learning_cycle.analyze_and_improve(skill, feedback)

        if not improvements:
            logger.warning(f"No improvements suggested for skill {skill_id}")
            return None

        # 应用改进
        if "steps" in improvements:
            new_steps = []
            for step_def in improvements["steps"]:
                new_steps.append(SkillStep(**step_def))
            skill.steps = new_steps

        if "trigger_patterns" in improvements:
            skill.trigger_patterns = improvements["trigger_patterns"]

        if "description" in improvements:
            skill.description = improvements["description"]

        if "metadata" in improvements:
            skill.metadata.update(improvements["metadata"])

        skill.version = self._increment_version(skill.version)
        skill.updated_at = get_timestamp()

        db.save_skill(skill)
        skill_version_manager.save_version(skill, "improve", f"基于用户反馈改进: {feedback[:50]}")
        audit_log_service.log_skill_edit(user_id, skill_id, skill.name, f"基于反馈改进")

        logger.info(f"Improved skill: {skill_id} based on feedback from user {user_id}")
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

    def auto_generate_skill(self, user_id: str, description: str) -> Optional[Skill]:
        """自动根据描述生成技能"""
        # 创建临时草稿
        draft = self.create_draft(user_id, description, description)
        
        # 直接创建技能（跳过假设检查）
        return self.create_from_draft(user_id, draft.id, auto_confirm=True)

    def _extract_skill_name(self, text: str) -> str:
        """从文本中提取技能名称"""
        keywords = ["技能", "功能", "能力", "任务", "流程", "生成", "创建", "处理"]
        for keyword in keywords:
            idx = text.find(keyword)
            if idx > 0:
                start = max(0, idx - 10)
                end = min(len(text), idx + 20)
                return text[start:end].strip()[:50]
        return "学习技能_" + generate_id()[:8]

    def _extract_skill_description(self, text: str) -> str:
        """从文本中提取技能描述"""
        return text[:200]

    def _increment_version(self, current_version: str) -> str:
        """递增版本号"""
        parts = current_version.split('.')
        if len(parts) == 3:
            major, minor, patch = parts
            patch = str(int(patch) + 1)
            return f"{major}.{minor}.{patch}"
        return f"{current_version}.1"


# 全局实例
learned_skills_manager = LearnedSkillsManager()