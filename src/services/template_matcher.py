"""模板匹配服务"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from src.logging_config import get_logger
from src.config import settings

logger = get_logger("service")


@dataclass
class TemplateMatch:
    """模板匹配结果"""
    template_id: str
    name: str
    description: str
    score: float
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TemplateMatcher:
    """模板匹配器"""
    
    def __init__(self):
        self.templates = self._load_templates()
    
    def _load_templates(self) -> List[Dict[str, Any]]:
        """加载模板定义"""
        return [
            {
                "id": "business-presentation",
                "name": "商务演示",
                "description": "适合企业汇报、产品介绍等正式场合",
                "tags": ["商务", "正式", "汇报", "产品"],
                "canvas": "16:9",
                "color_scheme": {"primary": "#1a73e8", "secondary": "#5f6368"},
                "font_family": {"title": "微软雅黑", "body": "微软雅黑"}
            },
            {
                "id": "tech-report",
                "name": "技术报告",
                "description": "适合技术文档、数据分析报告",
                "tags": ["技术", "数据", "报告", "分析"],
                "canvas": "16:9",
                "color_scheme": {"primary": "#34a853", "secondary": "#5f6368"},
                "font_family": {"title": "思源黑体", "body": "思源黑体"}
            },
            {
                "id": "creative-design",
                "name": "创意设计",
                "description": "适合创意展示、作品集展示",
                "tags": ["创意", "设计", "艺术", "作品"],
                "canvas": "16:9",
                "color_scheme": {"primary": "#9c27b0", "secondary": "#5f6368"},
                "font_family": {"title": "思源黑体", "body": "思源黑体"}
            },
            {
                "id": "education",
                "name": "教育培训",
                "description": "适合教学课件、培训材料",
                "tags": ["教育", "培训", "教学", "课件"],
                "canvas": "4:3",
                "color_scheme": {"primary": "#f57c00", "secondary": "#5f6368"},
                "font_family": {"title": "微软雅黑", "body": "微软雅黑"}
            },
            {
                "id": "minimal",
                "name": "极简风格",
                "description": "简洁大方，适合内容密集型演示",
                "tags": ["极简", "简洁", "专业", "内容"],
                "canvas": "16:9",
                "color_scheme": {"primary": "#212121", "secondary": "#757575"},
                "font_family": {"title": "思源黑体", "body": "思源黑体"}
            }
        ]
    
    def match_layout(self, content: str, style_hint: Optional[str] = None) -> List[TemplateMatch]:
        """匹配布局模板"""
        if not content:
            return []
        
        content_lower = content.lower()
        
        # 关键词匹配权重
        keyword_weights = {
            "business-presentation": ["商务", "汇报", "产品", "企业", "公司", "market", "business"],
            "tech-report": ["技术", "数据", "报告", "分析", "代码", "tech", "data"],
            "creative-design": ["创意", "设计", "艺术", "作品", "展示", "creative", "design"],
            "education": ["教育", "培训", "教学", "课程", "课件", "learn", "teach"],
            "minimal": ["简洁", "简单", "极简", "minimal", "simple"]
        }
        
        matches = []
        
        for template in self.templates:
            score = 0.3  # 基础分数
            
            # 关键词匹配
            keywords = keyword_weights.get(template["id"], [])
            for keyword in keywords:
                if keyword.lower() in content_lower:
                    score += 0.15
            
            # 风格提示匹配
            if style_hint:
                if style_hint.lower() in template["name"].lower() or \
                   style_hint.lower() in template["tags"]:
                    score += 0.2
            
            # 内容长度影响
            if len(content) > 500:
                score += 0.1
            
            if score > 0.4:
                matches.append(TemplateMatch(
                    template_id=template["id"],
                    name=template["name"],
                    description=template["description"],
                    score=min(score, 1.0),
                    tags=template["tags"],
                    metadata={
                        "canvas": template["canvas"],
                        "color_scheme": template["color_scheme"],
                        "font_family": template["font_family"]
                    }
                ))
        
        # 按分数排序
        matches.sort(key=lambda x: x.score, reverse=True)
        
        logger.info(f"模板匹配完成: {len(matches)} 个匹配")
        
        return matches
    
    def get_template_by_id(self, template_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取模板"""
        for template in self.templates:
            if template["id"] == template_id:
                return template
        return None
    
    def apply_template_style(self, template_id: str, slides: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """应用模板样式"""
        template = self.get_template_by_id(template_id)
        if not template:
            return slides
        
        styled_slides = []
        for slide in slides:
            styled_slides.append({
                **slide,
                "style": {
                    "color_scheme": template["color_scheme"],
                    "font_family": template["font_family"],
                    "template_id": template_id
                }
            })
        
        return styled_slides


# 全局实例
template_matcher = TemplateMatcher()
