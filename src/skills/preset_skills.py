"""预设技能管理 - 管理系统内置的预设技能"""

from typing import List, Dict, Any, Optional
from src.types import Skill, SkillStep
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger
from src.services.skill_management import skill_version_manager

logger = get_logger("skill")


class PresetSkillsManager:
    """预设技能管理器 - 管理系统内置的预设技能"""

    # 预设技能定义
    PRESET_SKILL_DEFINITIONS = [
        {
            "name": "会议纪要生成",
            "description": "自动生成会议纪要",
            "trigger_patterns": ["会议纪要", "meeting minutes", "会议记录"],
            "steps": [
                {"action": "execute", "parameters": {"instruction": "提取会议要点"}, "next_step_id": "step2"},
                {"action": "execute", "parameters": {"instruction": "整理讨论内容"}, "next_step_id": "step3"},
                {"action": "execute", "parameters": {"instruction": "生成会议纪要文档"}}
            ]
        },
        {
            "name": "数据图表绘制",
            "description": "根据数据生成图表",
            "trigger_patterns": ["图表", "chart", "graph", "可视化"],
            "steps": [
                {"action": "execute", "parameters": {"instruction": "分析数据需求"}, "next_step_id": "step2"},
                {"action": "execute", "parameters": {"instruction": "选择合适的图表类型"}, "next_step_id": "step3"},
                {"action": "execute", "parameters": {"instruction": "生成图表"}}
            ]
        },
        {
            "name": "竞品分析",
            "description": "分析竞争对手信息",
            "trigger_patterns": ["竞品分析", "competitive analysis", "竞争对手"],
            "steps": [
                {"action": "execute", "parameters": {"instruction": "收集竞品信息"}, "next_step_id": "step2"},
                {"action": "execute", "parameters": {"instruction": "分析竞品优势劣势"}, "next_step_id": "step3"},
                {"action": "execute", "parameters": {"instruction": "生成分析报告"}}
            ]
        },
        {
            "name": "周报生成",
            "description": "自动生成工作周报",
            "trigger_patterns": ["周报", "weekly report", "工作汇报"],
            "steps": [
                {"action": "execute", "parameters": {"instruction": "收集本周工作内容"}, "next_step_id": "step2"},
                {"action": "execute", "parameters": {"instruction": "整理工作成果"}, "next_step_id": "step3"},
                {"action": "execute", "parameters": {"instruction": "生成周报文档"}}
            ]
        },
        {
            "name": "PPT大纲生成",
            "description": "生成PPT大纲",
            "trigger_patterns": ["ppt", "演示文稿", "presentation"],
            "steps": [
                {"action": "execute", "parameters": {"instruction": "分析演示主题"}, "next_step_id": "step2"},
                {"action": "execute", "parameters": {"instruction": "确定内容结构"}, "next_step_id": "step3"},
                {"action": "execute", "parameters": {"instruction": "生成PPT大纲"}}
            ]
        },
        {
            "name": "PPT生成",
            "description": "完整的PPT生成流程，包括模板匹配、大纲生成、内容生成、质量检查和发送",
            "trigger_patterns": ["生成PPT", "制作PPT", "做个PPT", "生成演示稿", "生成幻灯片"],
            "steps": [
                {
                    "action": "ppt_template_match",
                    "parameters": {"content": "{{content}}", "style_hint": "{{style_hint}}"},
                    "next_step_id": "spec_lock",
                    "output_key": "template_result"
                },
                {
                    "action": "ppt_spec_lock",
                    "parameters": {"template_id": "{{template_result.templates.0.id}}"},
                    "next_step_id": "generate_outline",
                    "output_key": "spec_result"
                },
                {
                    "action": "ppt_generate_outline",
                    "parameters": {"title": "{{title}}", "content": "{{content}}", "style_config": "{{spec_result.spec_lock.design_spec}}"},
                    "next_step_id": "confirm_outline",
                    "condition": "await_confirmation",
                    "_prompt": "请确认生成的大纲是否满意？回复 是 继续，或 重新生成/修改+内容 进行调整",
                    "output_key": "outline_result"
                },
                {
                    "action": "ppt_generate_content",
                    "parameters": {"outline": "{{outline_result.outline}}", "template_id": "{{template_result.templates.0.id}}", "style_config": "{{spec_result.spec_lock.design_spec}}"},
                    "next_step_id": "generate_file",
                    "output_key": "content_result"
                },
                {
                    "action": "ppt_generate_file",
                    "parameters": {"title": "{{title}}", "slides": "{{content_result.slides}}"},
                    "next_step_id": "quality_check",
                    "output_key": "file_result"
                },
                {
                    "action": "ppt_quality_check",
                    "parameters": {"file_path": "{{file_result.file_path}}"},
                    "next_step_id": "send_file",
                    "output_key": "quality_result"
                },
                {
                    "action": "ppt_feishu_send",
                    "parameters": {"file_path": "{{file_result.file_path}}", "user_id": "{{user_id}}"},
                    "output_key": "send_result"
                }
            ]
        }
    ]

    def initialize_preset_skills(self):
        """初始化预设技能（仅在数据库为空时执行）"""
        for skill_def in self.PRESET_SKILL_DEFINITIONS:
            skill = self._create_skill_from_definition(skill_def)
            db.save_skill(skill)
            # 保存初始版本
            skill_version_manager.save_version(skill, "create", "初始版本")

        logger.info("Initialized preset skills")

    def _create_skill_from_definition(self, definition: Dict[str, Any]) -> Skill:
        """从定义创建技能对象"""
        steps = []
        for i, step_def in enumerate(definition["steps"]):
            step_id = f"step{i+1}" if i > 0 else generate_id()
            steps.append(SkillStep(
                id=step_id,
                action=step_def["action"],
                parameters=step_def["parameters"],
                next_step_id=step_def.get("next_step_id"),
                condition=step_def.get("condition")
            ))

        return Skill(
            id=generate_id(),
            name=definition["name"],
            description=definition["description"],
            type="preset",
            trigger_patterns=definition["trigger_patterns"],
            steps=steps,
            metadata={},
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by="system"
        )

    def create_preset_skill(self, name: str, description: str, trigger_patterns: List[str],
                            steps: List[Dict[str, Any]]) -> Skill:
        """创建新的预设技能（需要管理员权限）"""
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
            type="preset",
            trigger_patterns=trigger_patterns,
            steps=skill_steps,
            metadata={},
            version="1.0.0",
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by="system"
        )

        db.save_skill(skill)
        skill_version_manager.save_version(skill, "create", "初始版本")
        logger.info(f"Created preset skill: {name}")

        return skill

    def get_all_preset_skills(self) -> List[Skill]:
        """获取所有预设技能"""
        all_skills = db.get_all_skills()
        return [skill for skill in all_skills if skill.type == "preset"]

    def get_preset_skill_by_name(self, name: str) -> Optional[Skill]:
        """根据名称获取预设技能"""
        for skill in self.get_all_preset_skills():
            if skill.name == name:
                return skill
        return None


# 全局实例
preset_skills_manager = PresetSkillsManager()