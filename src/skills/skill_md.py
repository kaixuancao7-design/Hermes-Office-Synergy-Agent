"""SKILL.md 文件管理器 — agentskills.io 兼容的 Markdown 技能文件读写

格式规范：
  - YAML frontmatter (手动解析，无外部依赖)
  - Description 章节
  - Steps 章节（每个 Step 一个子标题）

文件存储路径：skills/learned/{skill_name}.md
"""

import os
import re
from typing import Dict, Any, Optional, List
from src.logging_config import get_logger

logger = get_logger("skill")


class SkillMarkdownManager:
    """读写 agentskills.io 兼容的 SKILL.md 文件"""

    SKILLS_DIR = "skills/learned"

    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or self.SKILLS_DIR
        os.makedirs(self.base_dir, exist_ok=True)

    # ========================================================================
    # Skill → Markdown
    # ========================================================================

    def skill_to_markdown(self, skill) -> str:
        """将 Skill 对象转换为 SKILL.md 字符串"""
        from src.types import Skill

        # YAML frontmatter
        triggers_yaml = "\n".join(f"  - {t}" for t in (skill.trigger_patterns or []))
        if not triggers_yaml:
            triggers_yaml = "  - []"

        lines = [
            "---",
            f"name: {skill.name}",
            f"description: {skill.description or ''}",
            f"version: {skill.version or '1.0.0'}",
            f"type: {skill.type}",
            "triggers:",
            triggers_yaml,
            f"created_by: {skill.created_by or 'system'}",
            f"created_at: {skill.created_at}",
            f"updated_at: {skill.updated_at}",
            "---",
            "",
            f"# {skill.name}",
            "",
            "## Description",
            "",
            skill.description or "",
            "",
            "## Steps",
            "",
        ]

        for i, step in enumerate(skill.steps, 1):
            params_lines = "\n".join(
                f"  - `{k}`: {v}" for k, v in (step.parameters or {}).items()
            )
            lines.extend([
                f"### Step {i}: {step.action}",
                "",
                f"- **Action**: {step.action}",
                f"- **Parameters**:",
                params_lines or "  - (none)",
            ])
            if step.condition:
                lines.append(f"- **Condition**: {step.condition}")
            if step.next_step_id:
                lines.append(f"- **Next Step**: {step.next_step_id}")
            lines.append("")

        return "\n".join(lines)

    # ========================================================================
    # Markdown → Skill
    # ========================================================================

    def markdown_to_skill(self, content: str):
        """从 SKILL.md 字符串解析为 Skill 对象"""
        from src.types import Skill, SkillStep
        from src.utils import generate_id, get_timestamp

        # 1. 解析 YAML frontmatter
        frontmatter = self._parse_frontmatter(content)
        if not frontmatter:
            return None

        # 2. 解析 Steps
        steps = self._parse_steps(content)

        return Skill(
            id=frontmatter.get("id", generate_id()),
            name=frontmatter.get("name", "unnamed-skill"),
            description=frontmatter.get("description", ""),
            type=frontmatter.get("type", "learned"),
            trigger_patterns=frontmatter.get("triggers", []),
            steps=steps,
            metadata=frontmatter.get("metadata", {}),
            version=frontmatter.get("version", "1.0.0"),
            created_at=frontmatter.get("created_at", get_timestamp()),
            updated_at=frontmatter.get("updated_at", get_timestamp()),
            created_by=frontmatter.get("created_by", "system"),
        )

    # ========================================================================
    # 文件系统操作
    # ========================================================================

    def write_skill_md(self, skill) -> str:
        """写入 SKILL.md 文件，返回文件路径"""
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', skill.name)
        filepath = os.path.join(self.base_dir, f"{safe_name}.md")
        content = self.skill_to_markdown(skill)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"[SKILL_MD] Written: {filepath}")
        return filepath

    def read_skill_md(self, filepath: str):
        """读取单个 SKILL.md 文件为 Skill 对象"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            skill = self.markdown_to_skill(content)
            if skill:
                logger.info(f"[SKILL_MD] Read: {filepath} → {skill.name}")
            return skill
        except Exception as e:
            logger.warning(f"[SKILL_MD] Failed to read {filepath}: {e}")
            return None

    def delete_skill_md(self, skill_name: str) -> bool:
        """删除 SKILL.md 文件"""
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', skill_name)
        filepath = os.path.join(self.base_dir, f"{safe_name}.md")
        if os.path.exists(filepath):
            os.unlink(filepath)
            logger.info(f"[SKILL_MD] Deleted: {filepath}")
            return True
        return False

    def sync_from_directory(self) -> list:
        """从文件系统读取所有 SKILL.md 文件，返回 Skill 对象列表

        用于启动时导入文件系统已有的技能文件。
        """
        skills = []
        if not os.path.isdir(self.base_dir):
            return skills

        for filename in os.listdir(self.base_dir):
            if filename.endswith('.md'):
                filepath = os.path.join(self.base_dir, filename)
                skill = self.read_skill_md(filepath)
                if skill:
                    skills.append(skill)

        logger.info(f"[SKILL_MD] Synced {len(skills)} skills from {self.base_dir}")
        return skills

    def list_skill_files(self) -> List[str]:
        """列出所有 SKILL.md 文件路径"""
        if not os.path.isdir(self.base_dir):
            return []
        return [
            os.path.join(self.base_dir, f)
            for f in os.listdir(self.base_dir)
            if f.endswith('.md')
        ]

    # ========================================================================
    # 内部解析器
    # ========================================================================

    @staticmethod
    def _parse_frontmatter(content: str) -> Optional[Dict[str, Any]]:
        """手动解析 YAML frontmatter（无需 pyyaml 依赖）"""
        # 查找 --- 分隔符
        if not content.startswith('---'):
            return None

        end_idx = content.find('---', 3)
        if end_idx == -1:
            return None

        fm_text = content[3:end_idx].strip()
        result: Dict[str, Any] = {}

        current_key = None
        current_list: List[str] = []

        for line in fm_text.split('\n'):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # 列表项 (  - value)
            if line_stripped.startswith('- '):
                value = line_stripped[2:].strip().strip('"').strip("'")
                if current_key:
                    current_list.append(value)
                continue

            # 保存之前的列表
            if current_key and current_list:
                result[current_key] = current_list
                current_list = []

            # 键值对 (key: value)
            if ':' in line_stripped:
                key, _, value = line_stripped.partition(':')
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                # 数字转换
                if value.isdigit():
                    result[key] = int(value)
                elif value in ('true', 'True'):
                    result[key] = True
                elif value in ('false', 'False'):
                    result[key] = False
                elif value == '':
                    current_key = key
                    current_list = []
                    result[key] = []  # 标记为可能列表
                else:
                    result[key] = value
                    current_key = None

        # 保存最后列表
        if current_key and current_list:
            result[current_key] = current_list

        return result if result else None

    @staticmethod
    def _parse_steps(content: str) -> list:
        """从 Markdown 解析 Step 章节"""
        from src.types import SkillStep
        from src.utils import generate_id

        steps = []
        # 按 "### Step N:" 分割
        step_blocks = re.split(r'### Step \d+:', content)

        for block in step_blocks[1:]:  # 跳过第一个（Steps 标题之前的内容）
            action = ""
            parameters: Dict[str, Any] = {}
            condition = None
            next_step_id = None

            # 提取 Action
            action_match = re.search(r'\*\*Action\*\*:\s*(\S+)', block)
            if action_match:
                action = action_match.group(1).strip()

            # 提取 Parameters
            param_matches = re.findall(r'`(\w+)`:\s*(.+)', block)
            for key, val in param_matches:
                parameters[key] = val.strip()

            # 提取 Condition
            cond_match = re.search(r'\*\*Condition\*\*:\s*(.+)', block)
            if cond_match:
                condition = cond_match.group(1).strip()

            # 提取 Next Step
            next_match = re.search(r'\*\*Next Step\*\*:\s*(\S+)', block)
            if next_match:
                next_step_id = next_match.group(1).strip()

            if action:
                steps.append(SkillStep(
                    id=generate_id(),
                    action=action,
                    parameters=parameters,
                    next_step_id=next_step_id,
                    condition=condition,
                ))

        return steps


# 全局实例
skill_md_manager = SkillMarkdownManager()
