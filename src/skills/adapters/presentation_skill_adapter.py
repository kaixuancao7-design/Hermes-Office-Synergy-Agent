"""Presentation技能适配器"""
from src.logging_config import get_logger

logger = get_logger("skill")


class PresentationSkillAdapter:
    """Presentation技能适配器"""
    
    def __init__(self):
        self._available = False
    
    def is_available(self) -> bool:
        """检查Presentation技能是否可用"""
        return self._available
    
    def register_skill(self, skill_manager):
        """注册Presentation技能"""
        logger.info("注册Presentation技能")


# 全局实例
presentation_skill_adapter = PresentationSkillAdapter()
