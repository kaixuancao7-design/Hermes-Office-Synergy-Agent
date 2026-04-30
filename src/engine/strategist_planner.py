"""策略规划器 - 分析需求并输出设计规格（灵感来自PPT Master的Strategist角色）"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from src.logging_config import get_logger

logger = get_logger("engine.strategist")


class ConfirmationStatus(Enum):
    """确认状态"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    SKIPPED = "skipped"


@dataclass
class DesignSpec:
    """设计规格"""
    canvas_format: str = "16:9"
    page_count: str = "5-10"
    audience: str = ""
    style: str = ""
    color_scheme: Dict[str, str] = field(default_factory=dict)
    font_plan: Dict[str, str] = field(default_factory=dict)
    icon_approach: str = "outline"
    image_approach: str = "realistic"
    content_outline: List[str] = field(default_factory=list)
    requires_confirmation: bool = True
    template_id: str = ""
    template_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canvas_format": self.canvas_format,
            "page_count": self.page_count,
            "audience": self.audience,
            "style": self.style,
            "color_scheme": self.color_scheme,
            "font_plan": self.font_plan,
            "icon_approach": self.icon_approach,
            "image_approach": self.image_approach,
            "content_outline": self.content_outline,
            "requires_confirmation": self.requires_confirmation,
            "template_id": self.template_id,
            "template_name": self.template_name
        }


@dataclass
class ConfirmationItem:
    """确认项"""
    key: str
    question: str
    options: List[str] = field(default_factory=list)
    default: str = ""
    user_value: str = ""
    status: ConfirmationStatus = ConfirmationStatus.PENDING


class StrategistPlanner:
    """策略规划器 - 分析需求并生成设计规格

    灵感来自PPT Master的Strategist角色，执行"八项确认"流程，
    在用户确认后生成结构化的设计规格。
    """

    EIGHT_CONFIRMATIONS = [
        {
            "key": "canvas_format",
            "question": "请选择画布格式",
            "options": ["16:9 (宽屏)", "4:3 (标准)", "21:9 (超宽屏)"],
            "default": "16:9 (宽屏)"
        },
        {
            "key": "page_count",
            "question": "请选择页数范围",
            "options": ["5-8页 (简短)", "8-15页 (中等)", "15-30页 (详细)", "30页以上 (完整)"],
            "default": "8-15页 (中等)"
        },
        {
            "key": "audience",
            "question": "请描述目标受众",
            "options": [],
            "default": "商务人士"
        },
        {
            "key": "style",
            "question": "请选择演示风格",
            "options": ["商务专业", "学术严谨", "创意活力", "简洁大气"],
            "default": "商务专业"
        },
        {
            "key": "color_scheme",
            "question": "请选择配色方案",
            "options": ["蓝色系 (专业)", "绿色系 (活力)", "橙色系 (温暖)", "紫色系 (创意)", "黑白灰 (极简)"],
            "default": "蓝色系 (专业)"
        },
        {
            "key": "icon_approach",
            "question": "请选择图标风格",
            "options": ["扁平化", "线框图", "彩色图标", "不使用图标"],
            "default": "扁平化"
        },
        {
            "key": "font_plan",
            "question": "请选择字体风格",
            "options": ["现代简洁", "传统正式", "创意个性"],
            "default": "现代简洁"
        },
        {
            "key": "image_approach",
            "question": "请选择图片使用策略",
            "options": ["真实图片", "插画风格", "数据图表", "不使用图片"],
            "default": "真实图片"
        }
    ]

    COLOR_SCHEMES = {
        "蓝色系 (专业)": {
            "primary": "#1A365D",
            "secondary": "#2B6CB0",
            "accent": "#ED8936",
            "background": "#FFFFFF",
            "text": "#2D3748"
        },
        "绿色系 (活力)": {
            "primary": "#276749",
            "secondary": "#38A169",
            "accent": "#F6AD55",
            "background": "#FFFFFF",
            "text": "#2D3748"
        },
        "橙色系 (温暖)": {
            "primary": "#C05621",
            "secondary": "#DD6B20",
            "accent": "#F6E05E",
            "background": "#FFFFFF",
            "text": "#2D3748"
        },
        "紫色系 (创意)": {
            "primary": "#553C9A",
            "secondary": "#805AD5",
            "accent": "#F56565",
            "background": "#1A202C",
            "text": "#F7FAFC"
        },
        "黑白灰 (极简)": {
            "primary": "#000000",
            "secondary": "#4A5568",
            "accent": "#3182CE",
            "background": "#FFFFFF",
            "text": "#1A202C"
        }
    }

    def __init__(self):
        self._current_confirmations: List[ConfirmationItem] = []
        self._current_spec: Optional[DesignSpec] = None

    def start_confirmation_flow(self, intent_type: str = "ppt") -> List[ConfirmationItem]:
        """
        开始确认流程

        Args:
            intent_type: 意图类型

        Returns:
            需要确认的项目列表
        """
        logger.info(f"Strategist: Starting confirmation flow for {intent_type}")

        self._current_confirmations = []
        confirmations_to_use = self.EIGHT_CONFIRMATIONS if intent_type == "ppt" else self.EIGHT_CONFIRMATIONS[:4]

        for conf in confirmations_to_use:
            item = ConfirmationItem(
                key=conf["key"],
                question=conf["question"],
                options=conf["options"],
                default=conf["default"],
                status=ConfirmationStatus.PENDING
            )
            self._current_confirmations.append(item)

        return self._current_confirmations

    def process_user_response(self, responses: Dict[str, str]) -> DesignSpec:
        """
        处理用户响应，生成设计规格

        Args:
            responses: 用户响应字典 {key: value}

        Returns:
            生成的设计规格
        """
        logger.info(f"Strategist: Processing {len(responses)} user responses")

        for item in self._current_confirmations:
            if item.key in responses:
                item.user_value = responses[item.key]
                item.status = ConfirmationStatus.CONFIRMED

        spec = DesignSpec()

        for item in self._current_confirmations:
            if item.key == "canvas_format":
                spec.canvas_format = item.user_value or item.default
            elif item.key == "page_count":
                spec.page_count = item.user_value or item.default
            elif item.key == "audience":
                spec.audience = item.user_value or item.default
            elif item.key == "style":
                spec.style = item.user_value or item.default
            elif item.key == "color_scheme":
                spec.color_scheme = self.COLOR_SCHEMES.get(item.user_value, self.COLOR_SCHEMES["蓝色系 (专业)"])
            elif item.key == "icon_approach":
                spec.icon_approach = item.user_value or item.default
            elif item.key == "font_plan":
                spec.font_plan = {"heading": "Microsoft YaHei", "body": "Arial"}
            elif item.key == "image_approach":
                spec.image_approach = item.user_value or item.default

        spec.requires_confirmation = False
        spec.template_id = self._infer_template_id(spec.style)
        spec.template_name = self._infer_template_name(spec.style)

        self._current_spec = spec
        logger.info(f"Strategist: DesignSpec created, template={spec.template_id}")

        return spec

    def _infer_template_id(self, style: str) -> str:
        """根据风格推断模板ID"""
        style_map = {
            "商务专业": "mckinsey",
            "学术严谨": "academic",
            "创意活力": "creative",
            "简洁大气": "minimalist"
        }
        return style_map.get(style, "mckinsey")

    def _infer_template_name(self, style: str) -> str:
        """根据风格推断模板名称"""
        style_map = {
            "商务专业": "麦肯锡咨询风格",
            "学术严谨": "学术答辩样式",
            "创意活力": "创意演示风格",
            "简洁大气": "极简专业风格"
        }
        return style_map.get(style, "麦肯锡咨询风格")

    def build_confirmation_message(self) -> str:
        """构建确认消息"""
        if not self._current_confirmations:
            return "无需确认"

        lines = ["**请完成以下确认：**\n"]

        for i, item in enumerate(self._current_confirmations, 1):
            lines.append(f"**{i}. {item.question}**")

            if item.options:
                for j, opt in enumerate(item.options, 1):
                    default_marker = " (默认)" if opt == item.default else ""
                    lines.append(f"   {j}. {opt}{default_marker}")
            else:
                lines.append(f"   请回复您的答案（默认: {item.default}）")

            lines.append("")

        lines.append("---")
        lines.append("请按序号回复，例如: `1, 3, 受众描述, 2, 1, 2, 1, 3`")

        return "\n".join(lines)

    def build_quick_confirmation(self) -> str:
        """构建快速确认消息（使用默认值）"""
        if not self._current_confirmations:
            return "无需确认"

        lines = ["**使用默认设置快速开始？**\n"]

        for i, item in enumerate(self._current_confirmations, 1):
            lines.append(f"{i}. {item.question}: **{item.default}**")

        lines.append("\n---")
        lines.append("回复 `是` 使用默认设置，或回复序号更改特定项（如: `3, 自定义受众`）")

        return "\n".join(lines)

    def get_current_spec(self) -> Optional[DesignSpec]:
        """获取当前设计规格"""
        return self._current_spec

    def is_confirmation_complete(self) -> bool:
        """检查确认是否完成"""
        if not self._current_confirmations:
            return True
        return all(item.status != ConfirmationStatus.PENDING for item in self._current_confirmations)

    @classmethod
    def quick_plan(cls, content: str, style_hint: str = None) -> DesignSpec:
        """
        快速规划（无需用户确认）

        Args:
            content: 用户内容
            style_hint: 风格提示

        Returns:
            设计规格
        """
        planner = cls()

        style = style_hint or cls._detect_style_from_content(content)

        spec = DesignSpec(
            canvas_format="16:9",
            page_count="8-15页 (中等)",
            audience="商务人士",
            style=style,
            color_scheme=cls.COLOR_SCHEMES.get(f"{style}系 (专业)", cls.COLOR_SCHEMES["蓝色系 (专业)"]),
            icon_approach="扁平化",
            image_approach="真实图片",
            requires_confirmation=False,
            template_id=cls._style_to_template_id(style),
            template_name=cls._style_to_template_name(style)
        )

        return spec

    @staticmethod
    def _detect_style_from_content(content: str) -> str:
        """从内容检测风格"""
        content_lower = content.lower()

        academic_keywords = ["学术", "研究", "论文", "答辩", "实验", "科学"]
        creative_keywords = ["创意", "设计", "品牌", "提案", "艺术", "创新"]

        if any(kw in content_lower for kw in academic_keywords):
            return "学术严谨"
        if any(kw in content_lower for kw in creative_keywords):
            return "创意活力"

        return "商务专业"

    @staticmethod
    def _style_to_template_id(style: str) -> str:
        style_map = {
            "商务专业": "mckinsey",
            "学术严谨": "academic",
            "创意活力": "creative",
            "简洁大气": "minimalist"
        }
        return style_map.get(style, "mckinsey")

    @staticmethod
    def _style_to_template_name(style: str) -> str:
        style_map = {
            "商务专业": "麦肯锡咨询风格",
            "学术严谨": "学术答辩样式",
            "创意活力": "创意演示风格",
            "简洁大气": "极简专业风格"
        }
        return style_map.get(style, "麦肯锡咨询风格")


strategist_planner = StrategistPlanner()
