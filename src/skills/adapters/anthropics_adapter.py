"""Anthropics技能适配器"""
from src.logging_config import get_logger

logger = get_logger("skill")


class AnthropicsAdapter:
    """Anthropics技能适配器"""
    
    def __init__(self):
        self._available = False
    
    def is_available(self) -> bool:
        """检查Anthropics技能是否可用"""
        return self._available
    
    def register_skill(self, skill_manager, skill_type: str = "pptx"):
        """注册Anthropics技能"""
        logger.info(f"注册Anthropics技能: {skill_type}")


# 全局实例
anthropics_adapter = AnthropicsAdapter()
