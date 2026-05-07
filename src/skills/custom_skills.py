"""自定义技能管理 - 管理用户创建的自定义技能（Claude范式增强版）"""

import yaml
from typing import List, Dict, Any, Optional
from pathlib import Path
from src.types import Skill, SkillStep
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger
from src.services.skill_management import skill_version_manager
from src.services.permission_service import permission_service
from src.services.audit_log_service import audit_log_service

logger = get_logger("skill")


class CustomSkillsManager:
    """自定义技能管理器 - 管理用户创建的自定义技能（支持Claude范式）"""

    def __init__(self):
        self._templates_dir = Path("skills/templates")
        self._templates_dir.mkdir(exist_ok=True, parents=True)

    def create_custom_skill(self, user_id: str, name: str, description: str, steps: List[Dict[str, Any]],
                           trigger_patterns: Optional[List[str]] = None, tags: Optional[List[str]] = None) -> Skill:
        """创建自定义技能（支持Claude范式）"""
        # 检查用户是否有权限创建技能
        user_role = permission_service.get_user_role(user_id)
        if not user_role or user_role.role not in ["admin", "developer", "user"]:
            logger.error(f"User {user_id} does not have permission to create skills")
            raise PermissionError("没有创建技能的权限")

        skill_steps = []
        for idx, step in enumerate(steps):
            step_id = step.get("id", f"step_{idx + 1}")
            skill_steps.append(SkillStep(
                id=step_id,
                action=step.get("action", "execute"),
                parameters=step.get("parameters", {}),
                next_step_id=step.get("next_step_id"),
                condition=step.get("condition")
            ))

        # 生成触发模式（如果未提供）
        triggers = trigger_patterns or [name, f"使用{name}", f"运行{name}"]

        skill = Skill(
            id=generate_id(),
            name=name,
            description=description,
            type="custom",
            trigger_patterns=triggers,
            steps=skill_steps,
            metadata={
                "user_id": user_id,
                "tags": tags or [],
                "source": "custom"
            },
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by=user_id
        )

        db.save_skill(skill)
        skill_version_manager.save_version(skill, "create", "初始版本")
        audit_log_service.log_skill_create(user_id, skill.id, skill.name)

        logger.info(f"Created custom skill: {name} by user {user_id}")
        return skill

    def create_skill_from_yaml(self, user_id: str, yaml_content: str) -> Skill:
        """从YAML定义创建自定义技能（Claude范式）"""
        try:
            definition = yaml.safe_load(yaml_content)
            
            # 验证必需字段
            if "name" not in definition:
                raise ValueError("技能定义必须包含name字段")
            if "workflow" not in definition:
                raise ValueError("技能定义必须包含workflow字段")

            # 转换工作流步骤
            steps = []
            workflow = definition.get("workflow", [])
            
            for idx, step_def in enumerate(workflow):
                step_id = step_def.get("id", f"step_{idx + 1}")
                
                # 检查是否需要等待确认
                params = step_def.get("parameters", {})
                if step_def.get("requires_confirmation") and step_def.get("confirmation_prompt"):
                    params["_prompt"] = step_def["confirmation_prompt"]
                
                steps.append({
                    "id": step_id,
                    "action": step_def["tool"],
                    "parameters": params,
                    "next_step_id": workflow[idx + 1]["id"] if idx < len(workflow) - 1 else None,
                    "condition": "await_confirmation" if step_def.get("requires_confirmation") else None
                })

            # 提取触发模式
            triggers = []
            for t in definition.get("triggers", []):
                if isinstance(t, dict):
                    triggers.append(t.get("pattern", ""))
                else:
                    triggers.append(t)

            # 创建技能
            return self.create_custom_skill(
                user_id=user_id,
                name=definition["name"],
                description=definition.get("description", ""),
                steps=steps,
                trigger_patterns=triggers if triggers else None,
                tags=definition.get("tags")
            )

        except yaml.YAMLError as e:
            logger.error(f"YAML解析失败: {e}")
            raise ValueError(f"YAML格式错误: {str(e)}")
        except Exception as e:
            logger.error(f"创建技能失败: {e}")
            raise

    def import_skill_from_file(self, user_id: str, file_path: str) -> Skill:
        """从文件导入技能定义"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
            return self.create_skill_from_yaml(user_id, yaml_content)
        except Exception as e:
            logger.error(f"导入技能文件失败 {file_path}: {e}")
            raise

    def export_skill_to_yaml(self, skill_id: str) -> str:
        """导出技能为YAML格式"""
        skill = db.get_skill(skill_id)
        if not skill:
            raise ValueError(f"技能不存在: {skill_id}")

        # 构建YAML定义
        definition = {
            "name": skill.name,
            "description": skill.description,
            "type": skill.type,
            "version": skill.version,
            "tags": skill.metadata.get("tags", []),
            "triggers": [{"pattern": p, "confidence": 0.8} for p in skill.trigger_patterns],
            "workflow": []
        }

        # 转换步骤
        for step in skill.steps:
            step_def = {
                "id": step.id,
                "tool": step.action,
                "parameters": step.parameters,
                "description": step.parameters.get("_prompt", "")
            }
            
            # 检查是否需要确认
            if step.condition == "await_confirmation":
                step_def["requires_confirmation"] = True
                step_def["confirmation_prompt"] = step.parameters.get("_prompt", "")
                # 移除内部参数
                step_def["parameters"] = {k: v for k, v in step.parameters.items() if not k.startswith("_")}

            definition["workflow"].append(step_def)

        # 添加输入输出schema（如果存在）
        if "input_schema" in skill.metadata:
            definition["input_schema"] = skill.metadata["input_schema"]
        if "output_schema" in skill.metadata:
            definition["output_schema"] = skill.metadata["output_schema"]

        return yaml.dump(definition, default_flow_style=False, allow_unicode=True)

    def update_custom_skill(self, user_id: str, skill_id: str, updates: Dict[str, Any]) -> Optional[Skill]:
        """更新自定义技能"""
        skill = db.get_skill(skill_id)
        if not skill:
            return None

        permission = permission_service.check_skill_permission(user_id, skill_id, "edit")
        if not permission.allowed:
            logger.error(f"User {user_id} does not have permission to edit skill {skill_id}")
            raise PermissionError("没有编辑技能的权限")

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

        skill.version = self._increment_version(skill.version)
        skill.updated_at = get_timestamp()

        db.save_skill(skill)
        change_note = updates.get("change_note", "技能更新")
        skill_version_manager.save_version(skill, "update", change_note)
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
        owner_permission = permission_service.check_skill_permission(owner_id, skill_id, "grant")
        if not owner_permission.allowed:
            logger.error(f"User {owner_id} does not have permission to share skill {skill_id}")
            return False

        success = permission_service.grant_skill_permission(owner_id, skill_id, target_user_id, permission)

        if success:
            audit_log_service.log_permission_grant(owner_id, 'skill', skill_id, target_user_id, permission)
            logger.info(f"User {owner_id} shared skill {skill_id} with {target_user_id} (permission: {permission})")

        return success

    def get_skill_templates(self) -> List[Dict[str, Any]]:
        """获取技能模板列表"""
        templates = []
        for file_path in self._templates_dir.glob("*.yaml"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    template = yaml.safe_load(f)
                    templates.append({
                        "name": template.get("name", file_path.stem),
                        "description": template.get("description", ""),
                        "tags": template.get("tags", []),
                        "path": str(file_path)
                    })
            except Exception as e:
                logger.warning(f"加载模板失败 {file_path}: {e}")
        
        return templates

    def create_from_template(self, user_id: str, template_name: str, customizations: Optional[Dict[str, Any]] = None) -> Skill:
        """从模板创建技能"""
        template_path = self._templates_dir / f"{template_name}.yaml"
        if not template_path.exists():
            raise ValueError(f"模板不存在: {template_name}")

        with open(template_path, 'r', encoding='utf-8') as f:
            definition = yaml.safe_load(f)

        # 应用自定义修改
        if customizations:
            if "name" in customizations:
                definition["name"] = customizations["name"]
            if "description" in customizations:
                definition["description"] = customizations["description"]
            if "tags" in customizations:
                definition["tags"] = customizations["tags"]
            if "triggers" in customizations:
                definition["triggers"] = customizations["triggers"]

        return self.create_skill_from_yaml(user_id, yaml.dump(definition, allow_unicode=True))

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