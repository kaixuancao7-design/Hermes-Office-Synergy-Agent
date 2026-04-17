from typing import List, Dict, Any, Optional
from src.types import Skill, SkillStep, UserProfile
from src.data.database import db
from src.utils import generate_id, get_timestamp, setup_logging
from src.engine.memory_manager import memory_manager
from src.config import settings

logger = setup_logging(settings.LOG_LEVEL)


class SkillManager:
    def __init__(self):
        self._load_skills()
    
    def _load_skills(self):
        skills = db.get_all_skills()
        if not skills:
            self._initialize_preset_skills()
    
    def _initialize_preset_skills(self):
        preset_skills = [
            Skill(
                id=generate_id(),
                name="会议纪要生成",
                description="自动生成会议纪要",
                type="preset",
                trigger_patterns=["会议纪要", "meeting minutes", "会议记录"],
                steps=[
                    SkillStep(
                        id=generate_id(),
                        action="execute",
                        parameters={"instruction": "提取会议要点"},
                        next_step_id="step2"
                    ),
                    SkillStep(
                        id="step2",
                        action="execute",
                        parameters={"instruction": "整理讨论内容"},
                        next_step_id="step3"
                    ),
                    SkillStep(
                        id="step3",
                        action="execute",
                        parameters={"instruction": "生成会议纪要文档"}
                    )
                ],
                metadata={},
                created_at=get_timestamp(),
                updated_at=get_timestamp()
            ),
            Skill(
                id=generate_id(),
                name="数据图表绘制",
                description="根据数据生成图表",
                type="preset",
                trigger_patterns=["图表", "chart", "graph", "可视化"],
                steps=[
                    SkillStep(
                        id=generate_id(),
                        action="execute",
                        parameters={"instruction": "分析数据需求"},
                        next_step_id="step2"
                    ),
                    SkillStep(
                        id="step2",
                        action="execute",
                        parameters={"instruction": "选择合适的图表类型"},
                        next_step_id="step3"
                    ),
                    SkillStep(
                        id="step3",
                        action="execute",
                        parameters={"instruction": "生成图表"}
                    )
                ],
                metadata={},
                created_at=get_timestamp(),
                updated_at=get_timestamp()
            ),
            Skill(
                id=generate_id(),
                name="竞品分析",
                description="分析竞争对手信息",
                type="preset",
                trigger_patterns=["竞品分析", "competitive analysis", "竞争对手"],
                steps=[
                    SkillStep(
                        id=generate_id(),
                        action="execute",
                        parameters={"instruction": "收集竞品信息"},
                        next_step_id="step2"
                    ),
                    SkillStep(
                        id="step2",
                        action="execute",
                        parameters={"instruction": "分析竞品优势劣势"},
                        next_step_id="step3"
                    ),
                    SkillStep(
                        id="step3",
                        action="execute",
                        parameters={"instruction": "生成分析报告"}
                    )
                ],
                metadata={},
                created_at=get_timestamp(),
                updated_at=get_timestamp()
            ),
            Skill(
                id=generate_id(),
                name="周报生成",
                description="自动生成工作周报",
                type="preset",
                trigger_patterns=["周报", "weekly report", "工作汇报"],
                steps=[
                    SkillStep(
                        id=generate_id(),
                        action="execute",
                        parameters={"instruction": "收集本周工作内容"},
                        next_step_id="step2"
                    ),
                    SkillStep(
                        id="step2",
                        action="execute",
                        parameters={"instruction": "整理工作成果"},
                        next_step_id="step3"
                    ),
                    SkillStep(
                        id="step3",
                        action="execute",
                        parameters={"instruction": "生成周报文档"}
                    )
                ],
                metadata={},
                created_at=get_timestamp(),
                updated_at=get_timestamp()
            ),
            Skill(
                id=generate_id(),
                name="PPT大纲生成",
                description="生成PPT大纲",
                type="preset",
                trigger_patterns=["ppt", "演示文稿", "presentation"],
                steps=[
                    SkillStep(
                        id=generate_id(),
                        action="execute",
                        parameters={"instruction": "分析演示主题"},
                        next_step_id="step2"
                    ),
                    SkillStep(
                        id="step2",
                        action="execute",
                        parameters={"instruction": "确定内容结构"},
                        next_step_id="step3"
                    ),
                    SkillStep(
                        id="step3",
                        action="execute",
                        parameters={"instruction": "生成PPT大纲"}
                    )
                ],
                metadata={},
                created_at=get_timestamp(),
                updated_at=get_timestamp()
            )
        ]
        
        for skill in preset_skills:
            db.save_skill(skill)
        logger.info("Initialized preset skills")
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        return db.get_skill(skill_id)
    
    def get_all_skills(self) -> List[Skill]:
        return db.get_all_skills()
    
    def create_custom_skill(self, user_id: str, name: str, description: str, steps: List[Dict[str, Any]]) -> Skill:
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
            created_at=get_timestamp(),
            updated_at=get_timestamp()
        )
        
        db.save_skill(skill)
        logger.info(f"Created custom skill: {name}")
        return skill
    
    def find_relevant_skill(self, query: str) -> Optional[Skill]:
        skills = db.get_all_skills()
        
        for skill in skills:
            for pattern in skill.trigger_patterns:
                if pattern.lower() in query.lower():
                    return skill
        
        return None
    
    def apply_user_preferences(self, skill: Skill, user_id: str) -> Skill:
        profile = memory_manager.get_user_profile(user_id)
        
        if profile and profile.writing_style:
            for step in skill.steps:
                if "instruction" in step.parameters:
                    step.parameters["instruction"] += f" (风格: {profile.writing_style})"
        
        return skill


skill_manager = SkillManager()
