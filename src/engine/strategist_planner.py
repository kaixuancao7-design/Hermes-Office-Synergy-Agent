"""策略规划器模块"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from src.logging_config import get_logger

logger = get_logger("engine")


class ConfirmationStatus(Enum):
    """确认状态"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CUSTOMIZED = "customized"


@dataclass
class DesignSpec:
    """设计规格"""
    canvas_format: str = "16:9"
    style: str = ""
    color_scheme: Dict[str, str] = field(default_factory=dict)
    font_plan: Dict[str, str] = field(default_factory=dict)
    template_id: str = ""
    template_name: str = ""


class StrategistPlanner:
    """策略规划器"""
    
    def __init__(self):
        pass
    
    def build_confirmation_message(self) -> str:
        """构建确认消息"""
        lines = [
            "**PPT生成设置确认**",
            "",
            "以下是当前的PPT生成设置：",
            "",
            "📐 **画布格式**: 16:9",
            "🎨 **风格**: 商务演示",
            "🔤 **字体**: 微软雅黑",
            "",
            "是否确认使用以上设置生成PPT？",
            "",
            "回复 `是` 确认生成",
            "回复 `否` 取消操作",
            "回复 `设置` 进行自定义配置"
        ]
        return "\n".join(lines)
    
    def build_quick_confirmation(self) -> str:
        """构建快速确认消息"""
        lines = [
            "请确认您的选择：",
            "",
            "✅ 回复 `是` 继续生成",
            "❌ 回复 `否` 取消",
            "⚙️ 回复 `设置` 自定义配置"
        ]
        return "\n".join(lines)
    
    def customize_spec(self, params: Dict[str, Any]) -> DesignSpec:
        """自定义设计规格"""
        spec = DesignSpec(
            canvas_format=params.get("canvas_format", "16:9"),
            style=params.get("style", "商务演示"),
            color_scheme=params.get("color_scheme", {}),
            font_plan=params.get("font_plan", {})
        )
        return spec
    
    def validate_spec(self, spec: DesignSpec) -> bool:
        """验证设计规格"""
        valid_formats = ["16:9", "4:3", "1:1"]
        if spec.canvas_format not in valid_formats:
            logger.error(f"无效的画布格式: {spec.canvas_format}")
            return False
        
        if not spec.style:
            logger.warning("风格未设置")
        
        return True
