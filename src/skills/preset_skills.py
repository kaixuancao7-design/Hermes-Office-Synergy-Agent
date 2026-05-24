"""预设技能管理器"""
from typing import List, Dict, Any, Optional
from src.types import Skill, SkillStep
from src.data.database import db
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("skill")


class PresetSkillsManager:
    """预设技能管理器"""
    
    def __init__(self):
        self.preset_skills = []
    
    def initialize_preset_skills(self):
        """初始化预设技能"""
        skills = self._get_default_skills()
        
        for skill_data in skills:
            skill = Skill(
                id=skill_data['id'],
                name=skill_data['name'],
                description=skill_data['description'],
                type='preset',
                trigger_patterns=skill_data['trigger_patterns'],
                steps=[SkillStep(**s) for s in skill_data['steps']],
                metadata=skill_data.get('metadata', {}),
                created_at=get_timestamp(),
                updated_at=get_timestamp(),
                created_by='system',
                version='1.0.0'
            )
            
            db.save_skill(skill)
            self.preset_skills.append(skill)
        
        logger.info(f"初始化了 {len(self.preset_skills)} 个预设技能")
    
    def _get_default_skills(self) -> List[Dict[str, Any]]:
        """获取默认技能列表"""
        return [
            {
                'id': 'summarize-meeting',
                'name': '会议总结',
                'description': '总结会议内容，提取关键信息和行动项',
                'trigger_patterns': ['总结会议', '会议要点', '会议记录'],
                'steps': [
                    {
                        'id': 'step-1',
                        'type': 'summarization',
                        'description': '提取会议要点',
                        'parameters': {'instruction': '总结以下会议内容，提取关键要点'}
                    },
                    {
                        'id': 'step-2',
                        'type': 'action_items',
                        'description': '识别行动项',
                        'parameters': {'instruction': '识别会议中的行动项和负责人'}
                    }
                ]
            },
            {
                'id': 'generate-report',
                'name': '生成报告',
                'description': '根据数据生成专业报告',
                'trigger_patterns': ['生成报告', '写报告', '数据分析'],
                'steps': [
                    {
                        'id': 'step-1',
                        'type': 'data_analysis',
                        'description': '分析数据',
                        'parameters': {'instruction': '分析提供的数据'}
                    },
                    {
                        'id': 'step-2',
                        'type': 'report_generation',
                        'description': '生成报告',
                        'parameters': {'instruction': '根据分析结果生成专业报告'}
                    }
                ]
            },
            {
                'id': 'email-draft',
                'name': '邮件草稿',
                'description': '根据内容生成邮件草稿',
                'trigger_patterns': ['写邮件', '邮件草稿', '发送邮件'],
                'steps': [
                    {
                        'id': 'step-1',
                        'type': 'email_generation',
                        'description': '生成邮件',
                        'parameters': {'instruction': '根据内容生成专业邮件'}
                    }
                ]
            }
        ]
    
    def get_preset_skills(self) -> List[Skill]:
        """获取所有预设技能"""
        return self.preset_skills
    
    def create_preset_skill(self, **kwargs) -> Skill:
        """创建预设技能"""
        skill = Skill(
            id=kwargs.get('id', generate_id()),
            name=kwargs['name'],
            description=kwargs.get('description', ''),
            type='preset',
            trigger_patterns=kwargs.get('trigger_patterns', []),
            steps=[SkillStep(**s) for s in kwargs.get('steps', [])],
            metadata=kwargs.get('metadata', {}),
            created_at=get_timestamp(),
            updated_at=get_timestamp(),
            created_by='system',
            version='1.0.0'
        )
        
        db.save_skill(skill)
        self.preset_skills.append(skill)
        
        return skill


# 全局实例
preset_skills_manager = PresetSkillsManager()
