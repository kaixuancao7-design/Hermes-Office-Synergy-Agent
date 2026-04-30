"""模板匹配服务 - 根据内容推荐合适的PPT模板"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from src.logging_config import get_logger

logger = get_logger("services.template_matcher")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


@dataclass
class TemplateMatch:
    """模板匹配结果"""
    template_id: str
    name: str
    description: str
    tags: List[str]
    score: float
    color_scheme: Dict[str, str]
    font_family: Dict[str, str]


class TemplateMatcher:
    """模板匹配器 - 根据内容推荐模板"""

    CONTENT_KEYWORDS = {
        "mckinsey": ["战略", "咨询", "企业", "分析", "市场", "竞争", "商业", "投资", "规划", "方案", "报告", "决策"],
        "academic": ["学术", "研究", "论文", "答辩", "实验", "科学", "理论", "分析", "方法", "数据", "结论", "教育"],
        "creative": ["创意", "设计", "品牌", "提案", "展示", "视觉", "时尚", "艺术", "创新", "概念", "灵感"],
        "minimalist": ["汇报", "总结", "高管", "简洁", "大气", "重要", "正式", "简洁", "精华", "提纲"]
    }

    def __init__(self):
        self._layouts_index = None
        self._charts_index = None
        self._icons_index = None

    def _load_json(self, file_path: str) -> Optional[dict]:
        """加载JSON文件"""
        try:
            full_path = os.path.join(TEMPLATES_DIR, file_path)
            if not os.path.exists(full_path):
                logger.warning(f"模板索引文件不存在: {full_path}")
                return None
            with open(full_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载模板索引失败: {file_path}, error: {str(e)}")
            return None

    @property
    def layouts_index(self) -> List[Dict[str, Any]]:
        """获取布局模板索引"""
        if self._layouts_index is None:
            data = self._load_json("layouts/layouts_index.json")
            self._layouts_index = data.get("templates", []) if data else []
        return self._layouts_index

    @property
    def charts_index(self) -> List[Dict[str, Any]]:
        """获取图表模板索引"""
        if self._charts_index is None:
            data = self._load_json("charts/charts_index.json")
            self._charts_index = data.get("charts", []) if data else []
        return self._charts_index

    @property
    def icons_index(self) -> Dict[str, Any]:
        """获取图标模板索引"""
        if self._icons_index is None:
            data = self._load_json("icons/icons_index.json")
            self._icons_index = data if data else {}
        return self._icons_index

    def match_layout(self, content: str, style_hint: str = None) -> List[TemplateMatch]:
        """
        根据内容匹配布局模板

        Args:
            content: 用户内容/描述
            style_hint: 风格提示（可选）

        Returns:
            匹配的模板列表，按分数排序
        """
        content_lower = content.lower()
        matches = []

        for template in self.layouts_index:
            score = 0.0
            matched_tags = []

            template_tags = template.get("tags", [])
            template_id = template.get("id", "")

            if style_hint and style_hint.lower() in [t.lower() for t in template_tags]:
                score += 5.0
                matched_tags.append(style_hint)

            for tag in template_tags:
                if tag.lower() in content_lower:
                    score += 2.0
                    matched_tags.append(tag)

            if template_id in self.CONTENT_KEYWORDS:
                for keyword in self.CONTENT_KEYWORDS[template_id]:
                    if keyword in content_lower:
                        score += 1.5

            if score > 0:
                matches.append(TemplateMatch(
                    template_id=template_id,
                    name=template.get("name", ""),
                    description=template.get("description", ""),
                    tags=matched_tags,
                    score=score,
                    color_scheme=template.get("color_scheme", {}),
                    font_family=template.get("font_family", {})
                ))

        matches.sort(key=lambda x: x.score, reverse=True)
        return matches[:3]

    def match_chart(self, content: str, data_type: str = None) -> List[Dict[str, Any]]:
        """
        根据内容匹配图表模板

        Args:
            content: 用户内容/描述
            data_type: 数据类型提示（可选）

        Returns:
            匹配的图表列表
        """
        content_lower = content.lower()
        matches = []

        for chart in self.charts_index:
            score = 0.0
            matched_tags = []

            chart_tags = chart.get("tags", [])

            if data_type and data_type.lower() in [t.lower() for t in chart_tags]:
                score += 5.0
                matched_tags.append(data_type)

            for tag in chart_tags:
                if tag.lower() in content_lower:
                    score += 2.0
                    matched_tags.append(tag)

            if score > 0:
                chart_copy = chart.copy()
                chart_copy["score"] = score
                chart_copy["matched_tags"] = matched_tags
                matches.append(chart_copy)

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:5]

    def get_template_by_id(self, template_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取布局模板"""
        for template in self.layouts_index:
            if template.get("id") == template_id:
                return template
        return None

    def get_chart_by_id(self, chart_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取图表模板"""
        for chart in self.charts_index:
            if chart.get("id") == chart_id:
                return chart
        return None

    def build_recommendation_message(self, matches: List[TemplateMatch]) -> str:
        """构建模板推荐消息"""
        if not matches:
            return "未找到匹配的模板，将使用默认模板生成。"

        lines = ["**推荐模板：**\n"]
        for i, m in enumerate(matches, 1):
            lines.append(f"{i}. **{m.name}** (匹配度: {m.score:.1f})")
            lines.append(f"   - {m.description}")
            if m.tags:
                lines.append(f"   - 匹配关键词: {', '.join(m.tags)}")

        return "\n".join(lines)

    def apply_template_style(self, template_id: str, slides: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        应用模板样式到幻灯片

        Args:
            template_id: 模板ID
            slides: 原始幻灯片列表

        Returns:
            应用样式后的幻灯片列表
        """
        template = self.get_template_by_id(template_id)
        if not template:
            logger.warning(f"未找到模板: {template_id}, 使用默认样式")
            return slides

        color_scheme = template.get("color_scheme", {})
        font_family = template.get("font_family", {})

        styled_slides = []
        for slide in slides:
            styled_slide = slide.copy()
            styled_slide["_style"] = {
                "color_scheme": color_scheme,
                "font_family": font_family,
                "template_id": template_id
            }
            styled_slides.append(styled_slide)

        return styled_slides


template_matcher = TemplateMatcher()
