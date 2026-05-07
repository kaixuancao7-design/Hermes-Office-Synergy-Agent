"""Claude风格的技能加载器"""

import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
from src.types import Skill, SkillStep
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("skill.loader")


class SkillLoader:
    """加载声明式技能定义"""

    def __init__(self, definitions_dir: str = "skills/definitions"):
        self.definitions_dir = Path(definitions_dir)
        self._skills_cache = {}

    def load_all_skills(self) -> List[Skill]:
        """加载所有技能定义"""
        skills = []
        if not self.definitions_dir.exists():
            logger.warning(f"技能定义目录不存在: {self.definitions_dir}")
            return skills

        for file_path in self.definitions_dir.glob("*.yaml"):
            skill = self._load_skill(file_path)
            if skill:
                skills.append(skill)
                self._skills_cache[skill.name] = skill
                logger.info(f"加载技能: {skill.name}")

        return skills

    def _load_skill(self, file_path: Path) -> Optional[Skill]:
        """从YAML文件加载技能"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                definition = yaml.safe_load(f)

            return self._convert_to_skill(definition)
        except Exception as e:
            logger.error(f"加载技能失败 {file_path}: {e}")
            return None

    def _convert_to_skill(self, definition: Dict[str, Any]) -> Skill:
        """将YAML定义转换为Skill对象"""
        steps = []
        workflow = definition.get("workflow", [])

        for idx, step_def in enumerate(workflow):
            # 计算下一步ID
            next_step_id = None
            if idx < len(workflow) - 1:
                next_step_id = workflow[idx + 1]["id"]

            # 构建步骤参数
            params = step_def.get("parameters", {})

            # 添加确认提示到参数中
            if step_def.get("requires_confirmation") and step_def.get("confirmation_prompt"):
                params["_prompt"] = step_def["confirmation_prompt"]

            steps.append(SkillStep(
                id=step_def["id"],
                action=step_def["tool"],
                parameters=params,
                next_step_id=next_step_id,
                condition="await_confirmation" if step_def.get("requires_confirmation") else None
            ))

        return Skill(
            id=generate_id(),
            name=definition["name"],
            description=definition["description"],
            type=definition.get("type", "custom"),
            trigger_patterns=[t["pattern"] for t in definition.get("triggers", [])],
            steps=steps,
            metadata={
                "version": definition.get("version", "1.0.0"),
                "tags": definition.get("tags", []),
                "input_schema": definition.get("input_schema"),
                "output_schema": definition.get("output_schema"),
                "source": "yaml_definition",
                "file_path": str(self.definitions_dir / f"{definition['name']}.yaml")
            },
            version=definition.get("version", "1.0.0"),
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by="system"
        )

    def get_skill_by_name(self, name: str) -> Optional[Skill]:
        """根据名称获取技能"""
        return self._skills_cache.get(name)

    def get_skill_by_tag(self, tag: str) -> List[Skill]:
        """按标签获取技能"""
        return [
            skill for skill in self._skills_cache.values()
            if tag in skill.metadata.get("tags", [])
        ]

    def reload_skills(self):
        """重新加载所有技能"""
        self._skills_cache.clear()
        return self.load_all_skills()


# 全局实例
skill_loader = SkillLoader()