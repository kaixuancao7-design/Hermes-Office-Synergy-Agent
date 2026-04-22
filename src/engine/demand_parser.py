from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from src.utils import generate_id, get_timestamp
from src.logging_config import get_logger

logger = get_logger("engine")


class PPTDemand(BaseModel):
    """PPT需求结构化模型"""
    # 基础属性
    title: str = ""
    page_count: Optional[int] = None
    audience: str = ""
    purpose: str = ""
    style: str = "正式"
    deadline: str = ""
    language: str = "中文"
    
    # 内容要求
    core_topic: str = ""
    required_modules: List[str] = []
    key_data: List[str] = []
    forbidden_content: List[str] = []
    
    # 素材范围
    chat_history_ids: List[str] = []
    attachments: List[str] = []
    document_links: List[str] = []
    cloud_drive_paths: List[str] = []
    
    # 状态
    is_complete: bool = False
    missing_info: List[str] = []
    confirmation_questions: List[str] = []
    
    # 元数据
    demand_id: str = ""
    created_at: int = 0
    user_id: str = ""
    source: str = "im"  # im, voice, file, etc.


class DemandParser:
    """需求解析器 - 从自然语言中提取结构化需求"""
    
    def __init__(self):
        # PPT需求关键词
        self.ppt_keywords = [
            "做个ppt", "做ppt", "制作ppt", "生成ppt", 
            "汇报材料", "演示稿", "幻灯片", "presentation",
            "做个演示", "汇报ppt", "总结ppt"
        ]
        
        # 风格关键词映射
        self.style_keywords = {
            "正式": ["正式", "商务", "严肃", "专业"],
            "简洁": ["简洁", "简约", "清爽", "简单"],
            "活泼": ["活泼", "生动", "有趣", "轻松"],
            "科技": ["科技", "互联网", "现代", "炫酷"],
            "学术": ["学术", "研究", "论文", "报告"]
        }
        
        # 受众关键词
        self.audience_keywords = {
            "领导": ["领导", "老板", "上司", "高管", "管理层"],
            "客户": ["客户", "甲方", "合作伙伴", "外部"],
            "同事": ["同事", "团队", "部门", "内部"],
            "公众": ["公众", "用户", "观众", "听众", "公开"]
        }
        
        # 用途关键词
        self.purpose_keywords = {
            "汇报": ["汇报", "总结", "述职", "报告"],
            "介绍": ["介绍", "展示", "演示", "路演"],
            "培训": ["培训", "教学", "讲解", "教程"],
            "宣传": ["宣传", "推广", "营销", "招商"]
        }
    
    def detect_ppt_demand(self, text: str) -> bool:
        """检测文本中是否包含PPT需求"""
        text_lower = text.lower()
        for keyword in self.ppt_keywords:
            if keyword in text_lower:
                return True
        return False
    
    def extract_demand(self, text: str, context: Optional[Dict[str, Any]] = None) -> PPTDemand:
        """
        从自然语言文本中提取PPT需求
        
        Args:
            text: 用户输入的自然语言指令
            context: 上下文信息（聊天记录、附件等）
        
        Returns:
            PPT需求结构化对象
        """
        demand = PPTDemand(
            demand_id=generate_id(),
            created_at=get_timestamp(),
            source="im"
        )
        
        # 提取基础属性
        demand.page_count = self._extract_page_count(text)
        demand.style = self._extract_style(text)
        demand.audience = self._extract_audience(text)
        demand.purpose = self._extract_purpose(text)
        demand.language = self._extract_language(text)
        demand.deadline = self._extract_deadline(text)
        
        # 提取内容要求
        demand.core_topic = self._extract_core_topic(text)
        demand.required_modules = self._extract_required_modules(text)
        demand.key_data = self._extract_key_data(text)
        
        # 提取素材范围
        if context:
            demand.attachments = context.get("attachments", [])
            demand.chat_history_ids = context.get("chat_history_ids", [])
            demand.document_links = context.get("document_links", [])
        
        # 生成标题
        demand.title = self._generate_title(demand)
        
        # 检查完整性并生成追问
        self._check_completeness(demand)
        
        return demand
    
    def _extract_page_count(self, text: str) -> Optional[int]:
        """提取页数"""
        # 匹配 "10页"、"十页"、"10 slides" 等模式
        patterns = [
            r'(\d+)\s*页',
            r'(\d+)\s*slide',
            r'(\d+)\s*幻灯片',
            r'(\d+)\s*张'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None
    
    def _extract_style(self, text: str) -> str:
        """提取风格"""
        text_lower = text.lower()
        for style, keywords in self.style_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return style
        return "正式"
    
    def _extract_audience(self, text: str) -> str:
        """提取受众"""
        text_lower = text.lower()
        for audience, keywords in self.audience_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return audience
        return ""
    
    def _extract_purpose(self, text: str) -> str:
        """提取用途"""
        text_lower = text.lower()
        for purpose, keywords in self.purpose_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return purpose
        return ""
    
    def _extract_language(self, text: str) -> str:
        """提取语言"""
        text_lower = text.lower()
        if "英文" in text_lower or "english" in text_lower:
            return "英文"
        return "中文"
    
    def _extract_deadline(self, text: str) -> str:
        """提取截止时间"""
        # 简单提取时间相关内容
        patterns = [
            r'(\d+月\d+日)',
            r'(\d+号)',
            r'(\d+天内)',
            r'(\d+小时内)',
            r'今天',
            r'明天',
            r'本周'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""
    
    def _extract_core_topic(self, text: str) -> str:
        """提取核心主题"""
        # 移除PPT相关关键词后提取主题
        topic = text
        for keyword in self.ppt_keywords:
            topic = topic.replace(keyword, "").replace(keyword.upper(), "").replace(keyword.capitalize(), "")
        
        # 移除页数等数字信息
        topic = re.sub(r'\d+\s*页', '', topic)
        topic = re.sub(r'\d+\s*slide', '', topic)
        
        # 提取书名号内的内容作为主题候选
        book_title_match = re.search(r'《([^》]+)》', text)
        if book_title_match:
            return book_title_match.group(1)
        
        return topic.strip()[:50]
    
    def _extract_required_modules(self, text: str) -> List[str]:
        """提取必含模块"""
        modules = []
        module_keywords = {
            "目录": ["目录", "大纲"],
            "前言": ["前言", "引言", "背景"],
            "总结": ["总结", "结论", "结束语"],
            "数据": ["数据", "图表", "统计"],
            "分析": ["分析", "调研", "研究"],
            "竞品": ["竞品", "竞争对手", "对标"],
            "计划": ["计划", "规划", "下一步"],
            "风险": ["风险", "挑战", "问题"]
        }
        
        text_lower = text.lower()
        for module, keywords in module_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    modules.append(module)
                    break
        
        return modules
    
    def _extract_key_data(self, text: str) -> List[str]:
        """提取重点数据"""
        data_points = []
        
        # 提取数字相关内容
        number_patterns = [
            r'(\d+[\d,]*)\s*万',
            r'(\d+[\d,]*)\s*亿',
            r'(\d+[\d,]*)\s*%',
            r'(\d+[\d,]*)\s*元',
            r'(\d+[\d,]*)\s*增长',
            r'(\d+[\d,]*)\s*下降'
        ]
        
        for pattern in number_patterns:
            matches = re.findall(pattern, text)
            data_points.extend(matches)
        
        # 提取区域/部门名称
        region_keywords = ["华东", "华南", "华北", "华中", "西南", "西北", "东北", "海外"]
        for region in region_keywords:
            if region in text:
                data_points.append(region)
        
        return data_points[:10]
    
    def _generate_title(self, demand: PPTDemand) -> str:
        """生成PPT标题"""
        if demand.core_topic:
            return demand.core_topic
        
        parts = []
        if demand.purpose:
            parts.append(demand.purpose)
        if demand.audience:
            parts.append(f"面向{demand.audience}")
        if parts:
            return "".join(parts) + "PPT"
        
        return "演示文稿"
    
    def _check_completeness(self, demand: PPTDemand):
        """检查需求完整性并生成追问"""
        missing = []
        questions = []
        
        # 检查必需字段
        if not demand.core_topic:
            missing.append("核心主题")
            questions.append("请问PPT的核心主题是什么？")
        
        if not demand.audience:
            missing.append("受众")
            questions.append("这份PPT是面向谁展示的呢？（如：领导、客户、同事）")
        
        if not demand.purpose:
            missing.append("用途")
            questions.append("这份PPT的用途是什么？（如：汇报、介绍、培训）")
        
        if not demand.style:
            demand.style = "正式"  # 默认正式风格
        
        # 检查可选字段（根据业务需求决定是否追问）
        if not demand.page_count:
            questions.append("请问需要多少页？（可选）")
        
        if not demand.deadline:
            questions.append("是否有截止时间要求？（可选）")
        
        demand.missing_info = missing
        demand.confirmation_questions = questions
        demand.is_complete = len(missing) == 0
    
    def generate_confirmation_message(self, demand: PPTDemand) -> str:
        """生成需求确认消息"""
        if demand.is_complete:
            return self._generate_summary(demand)
        
        # 生成追问消息
        message = "我已理解您的需求，补充确认以下信息：\n\n"
        message += self._generate_summary(demand) + "\n\n"
        message += "需要补充的信息：\n"
        
        for i, question in enumerate(demand.confirmation_questions, 1):
            message += f"{i}. {question}\n"
        
        return message
    
    def _generate_summary(self, demand: PPTDemand) -> str:
        """生成需求摘要"""
        parts = []
        
        if demand.title:
            parts.append(f"主题：{demand.title}")
        
        if demand.page_count:
            parts.append(f"页数：{demand.page_count}页")
        
        if demand.audience:
            parts.append(f"受众：{demand.audience}")
        
        if demand.purpose:
            parts.append(f"用途：{demand.purpose}")
        
        if demand.style:
            parts.append(f"风格：{demand.style}")
        
        if demand.language:
            parts.append(f"语言：{demand.language}")
        
        if demand.deadline:
            parts.append(f"截止时间：{demand.deadline}")
        
        if demand.key_data:
            parts.append(f"重点数据：{', '.join(demand.key_data)}")
        
        if demand.required_modules:
            parts.append(f"必含模块：{', '.join(demand.required_modules)}")
        
        if demand.attachments:
            parts.append(f"附件：{len(demand.attachments)}个")
        
        return "\n".join(parts)
    
    def aggregate_group_demands(self, demands: List[PPTDemand]) -> PPTDemand:
        """聚合群聊中多人的需求"""
        if not demands:
            return PPTDemand()
        
        # 创建聚合需求
        aggregated = PPTDemand(
            demand_id=generate_id(),
            created_at=get_timestamp(),
            source="group_im"
        )
        
        # 合并标题（取最长或最具体的）
        aggregated.title = max([d.title for d in demands if d.title], key=len, default="")
        
        # 合并页数（取最大值）
        aggregated.page_count = max([d.page_count for d in demands if d.page_count], default=None)
        
        # 合并风格（取最正式的）
        style_order = ["正式", "商务", "学术", "科技", "简洁", "活泼"]
        for style in style_order:
            if any(d.style == style for d in demands):
                aggregated.style = style
                break
        
        # 合并受众和用途（去重）
        audiences = set()
        purposes = set()
        for d in demands:
            if d.audience:
                audiences.add(d.audience)
            if d.purpose:
                purposes.add(d.purpose)
        
        aggregated.audience = "、".join(audiences)[:20]
        aggregated.purpose = "、".join(purposes)[:20]
        
        # 合并内容要求
        all_modules = set()
        all_key_data = set()
        for d in demands:
            all_modules.update(d.required_modules)
            all_key_data.update(d.key_data)
        
        aggregated.required_modules = list(all_modules)[:10]
        aggregated.key_data = list(all_key_data)[:10]
        
        # 合并素材
        all_attachments = set()
        for d in demands:
            all_attachments.update(d.attachments)
        
        aggregated.attachments = list(all_attachments)
        
        # 检查完整性
        self._check_completeness(aggregated)
        
        return aggregated


# 单例实例
demand_parser = DemandParser()
