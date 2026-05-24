"""规格锁定模块"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from src.logging_config import get_logger

logger = get_logger("engine")


@dataclass
class SpecLock:
    """规格锁定对象"""
    template_id: str
    canvas_format: str = "16:9"
    color_scheme: Dict[str, str] = field(default_factory=dict)
    font_plan: Dict[str, str] = field(default_factory=dict)
    slide_count: Optional[int] = None
    locked: bool = True
    
    @classmethod
    def from_template(cls, template_id: str, template_spec: Dict[str, Any]) -> 'SpecLock':
        """从模板创建规格锁定"""
        return cls(
            template_id=template_id,
            canvas_format=template_spec.get("canvas", "16:9"),
            color_scheme=template_spec.get("color_scheme", {}),
            font_plan=template_spec.get("font_family", {})
        )
    
    def update(self, updates: Dict[str, Any]) -> None:
        """更新规格"""
        if "canvas_format" in updates:
            self.canvas_format = updates["canvas_format"]
        if "color_scheme" in updates:
            self.color_scheme.update(updates["color_scheme"])
        if "font_plan" in updates:
            self.font_plan.update(updates["font_plan"])
        if "slide_count" in updates:
            self.slide_count = updates["slide_count"]
    
    def validate(self) -> bool:
        """验证规格"""
        valid_formats = ["16:9", "4:3", "1:1"]
        if self.canvas_format not in valid_formats:
            logger.error(f"无效的画布格式: {self.canvas_format}")
            return False
        
        if not self.color_scheme.get("primary"):
            logger.warning("缺少主色配置")
        
        return True


class SpecLockManager:
    """规格锁定管理器"""
    
    def __init__(self):
        self.locks: Dict[str, SpecLock] = {}
    
    def create_lock(self, user_id: str, template_id: str, template_spec: Dict[str, Any]) -> SpecLock:
        """创建规格锁定"""
        spec_lock = SpecLock.from_template(template_id, template_spec)
        self.locks[user_id] = spec_lock
        return spec_lock
    
    def get_lock(self, user_id: str) -> Optional[SpecLock]:
        """获取规格锁定"""
        return self.locks.get(user_id)
    
    def update_lock(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """更新规格锁定"""
        spec_lock = self.locks.get(user_id)
        if not spec_lock:
            return False
        
        spec_lock.update(updates)
        return True
    
    def release_lock(self, user_id: str) -> None:
        """释放规格锁定"""
        if user_id in self.locks:
            del self.locks[user_id]


# 全局实例
spec_lock_manager = SpecLockManager()
