"""技能解析器 - 解析SKILL.md中的技能定义（Claude范式）"""

import yaml
import re
from typing import Dict, Any, Optional, List
from pathlib import Path
from src.types import Skill, SkillStep
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("skill.parser")


class SkillParser:
    """技能解析器 - 从SKILL.md文件解析技能定义"""

    def __init__(self):
        self._skills_dir = Path("skills")

    def parse_skill_file(self, skill_dir: str) -> Optional[Skill]:
        """解析单个技能目录"""
        skill_path = Path(skill_dir)
        
        md_file = skill_path / "SKILL.md"
        if not md_file.exists():
            logger.warning(f"SKILL.md not found in {skill_dir}")
            return None

        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            yaml_blocks = self._extract_yaml_blocks(content)
            basic_info = self._extract_basic_info(content)
            workflow_def = yaml_blocks.get("workflow", {})
            steps = self._parse_workflow_steps(workflow_def)
            triggers = self._extract_triggers(content, yaml_blocks)
            tags = yaml_blocks.get("tags", [])
            input_schema = yaml_blocks.get("input_schema", {})
            output_schema = yaml_blocks.get("output_schema", {})

            skill = Skill(
                id=generate_id(),
                name=basic_info.get("name", skill_path.name),
                description=basic_info.get("description", ""),
                type=basic_info.get("type", "preset"),
                trigger_patterns=triggers,
                steps=steps,
                metadata={
                    "version": basic_info.get("version", "1.0.0"),
                    "identifier": basic_info.get("identifier", skill_path.name),
                    "tags": tags,
                    "input_schema": input_schema,
                    "output_schema": output_schema,
                    "source": "skill_md",
                    "skill_dir": str(skill_path)
                },
                version=basic_info.get("version", "1.0.0"),
                created_at=get_timestamp(),
                updated_at=get_timestamp(),
                created_by="system"
            )

            logger.info(f"Parsed skill: {skill.name} from {skill_dir}")
            return skill

        except Exception as e:
            logger.error(f"Failed to parse skill {skill_dir}: {e}")
            return None

    def parse_all_skills(self) -> List[Skill]:
        """解析所有技能目录"""
        skills = []
        
        if not self._skills_dir.exists():
            logger.warning(f"Skills directory not found: {self._skills_dir}")
            return skills

        for skill_dir in self._skills_dir.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith('.'):
                skill = self.parse_skill_file(str(skill_dir))
                if skill:
                    skills.append(skill)

        logger.info(f"Parsed {len(skills)} skills")
        return skills

    def _extract_yaml_blocks(self, content: str) -> Dict[str, Any]:
        """从markdown中提取所有YAML块"""
        result = {}
        yaml_pattern = r'```yaml\s*(.*?)\s*```'
        
        matches = re.findall(yaml_pattern, content, re.DOTALL)
        for match in matches:
            try:
                data = yaml.safe_load(match)
                if isinstance(data, dict):
                    result.update(data)
                elif isinstance(data, list) and "tags" not in result:
                    result["tags"] = data
            except yaml.YAMLError:
                continue
        
        return result

    def _extract_basic_info(self, content: str) -> Dict[str, str]:
        """提取基本信息表格"""
        info = {}
        table_pattern = r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|'
        matches = re.findall(table_pattern, content)
        
        key_map = {
            "名称": "name",
            "标识符": "identifier",
            "版本": "version",
            "类型": "type",
            "描述": "description"
        }
        
        for key, value in matches:
            key = key.strip()
            value = value.strip()
            if key in key_map:
                info[key_map[key]] = value
        
        return info

    def _extract_triggers(self, content: str, yaml_blocks: Dict[str, Any]) -> List[str]:
        """提取触发模式"""
        triggers = []
        
        if "triggers" in yaml_blocks:
            for t in yaml_blocks["triggers"]:
                if isinstance(t, dict):
                    triggers.append(t.get("pattern", ""))
                else:
                    triggers.append(t)
        
        if not triggers:
            table_pattern = r'\|\s*([^|]+?)\s*\|\s*[\d.]+?\s*\|\s*[^|]*?\|'
            matches = re.findall(table_pattern, content)
            triggers = [m.strip() for m in matches if m.strip()]
        
        return triggers

    def _parse_workflow_steps(self, workflow_def: Dict[str, Any]) -> List[SkillStep]:
        """解析工作流步骤"""
        steps = []
        workflow = workflow_def.get("workflow", [])
        
        if not isinstance(workflow, list):
            return steps

        for idx, step_def in enumerate(workflow):
            if not isinstance(step_def, dict):
                continue
            
            step_id = step_def.get("id", f"step_{idx + 1}")
            params = step_def.get("parameters", {})
            
            if step_def.get("requires_confirmation") and step_def.get("confirmation_prompt"):
                params["_prompt"] = step_def["confirmation_prompt"]
            
            steps.append(SkillStep(
                id=step_id,
                action=step_def.get("tool", step_def.get("action", "execute")),
                parameters=params,
                next_step_id=step_def.get("next_step"),
                condition="await_confirmation" if step_def.get("requires_confirmation") else None
            ))
        
        return steps


# 全局实例
skill_parser = SkillParser()