from typing import List, Dict, Any, Optional
from src.types import Intent
from src.infrastructure.model_router import select_model, call_model
from src.logging_config import get_logger

logger = get_logger("engine")

INTENT_TYPES = [
    "summarization",
    "question_answering",
    "task_execution",
    "skill_request",
    "memory_query",
    "document_analysis",
    "code_generation",
    "creative_writing",
    # PPT相关意图（细粒度）
    "ppt_generate_outline",      # 生成PPT大纲
    "ppt_generate_from_outline", # 从大纲生成PPT
    "ppt_generate_from_content", # 从内容直接生成PPT
    "ppt_custom_generate",       # 自定义生成PPT
    "unknown"
]

# 意图→工具映射
INTENT_TO_TOOL_MAP = {
    # 通用意图
    "summarization": None,  # 由引擎直接处理
    "question_answering": None,  # 可能需要搜索
    "task_execution": None,  # 需要进一步分析
    "skill_request": "skill_manager",
    "memory_query": "memory_search",
    "document_analysis": None,  # 可能需要读取文件
    "code_generation": "code_execution",
    "creative_writing": None,  # 由LLM直接处理
    
    # PPT意图
    "ppt_generate_outline": "generate_outline",
    "ppt_generate_from_outline": "generate_ppt_from_outline",
    "ppt_generate_from_content": "generate_ppt_from_content",
    "ppt_custom_generate": "generate_ppt"
}

# 工具→意图反向映射（用于工具选择时的意图确认）
TOOL_TO_INTENT_MAP = {v: k for k, v in INTENT_TO_TOOL_MAP.items() if v}


class IntentRecognizer:
    def __init__(self):
        self.intent_patterns: Dict[str, List[str]] = {
            "summarization": [
                "总结", "摘要", "概括", "简述", "整理",
                "summarize", "summary", "brief"
            ],
            "question_answering": [
                "什么是", "如何", "为什么", "怎么样",
                "what", "how", "why", "explain"
            ],
            "task_execution": [
                "帮我", "我需要", "请", "执行", "完成",
                "do", "help", "execute", "complete"
            ],
            "skill_request": [
                "技能", "学习", "保存", "自动化",
                "skill", "learn", "save", "automate"
            ],
            "memory_query": [
                "记得", "之前", "历史", "查找",
                "remember", "history", "find", "search"
            ],
            "document_analysis": [
                "分析", "解读", "理解", "报告",
                "analyze", "analyze", "report", "understand"
            ],
            "code_generation": [
                "代码", "编程", "写程序", "脚本",
                "code", "program", "script", "develop"
            ],
            "creative_writing": [
                "写", "创作", "撰写", "生成",
                "write", "create", "generate", "compose"
            ],
            # PPT细粒度意图
            "ppt_generate_outline": [
                "ppt大纲", "生成ppt大纲", "ppt大纲生成", 
                "做个大纲", "列个提纲", "章节结构",
                "outline", "structure", "summary"
            ],
            "ppt_generate_from_content": [
                "根据内容做ppt", "根据文档做ppt", "根据文件生成ppt",
                "从内容生成", "直接生成ppt", "一键生成",
                "文件内容生成ppt", "内容生成ppt"
            ],
            "ppt_generate_from_outline": [
                "根据大纲做ppt", "从提纲生成ppt", "大纲转ppt",
                "outline to ppt", "from outline", "大纲生成ppt"
            ],
            "ppt_custom_generate": [
                "做个ppt", "制作ppt", "生成ppt", "演示稿",
                "做演示", "汇报ppt", "presentation", "产品介绍ppt"
            ]
        }
    
    def recognize(self, text: str) -> Intent:
        text_lower = text.lower()
        
        # 定义意图优先级（越具体的意图优先级越高）
        intent_priority = [
            "ppt_generate_from_content",  # 最具体：明确提到"根据内容"
            "ppt_generate_from_outline",   # 较具体：明确提到"根据大纲"
            "ppt_generate_outline",        # 较具体：明确提到"生成大纲"
            "summarization",
            "document_analysis",
            "code_generation",
            "memory_query",
            "question_answering",
            "task_execution",
            "skill_request",
            "creative_writing",
            "ppt_custom_generate",         # 通用：简单的"做ppt"，放在最后
            "unknown"
        ]
        
        matched_intent = "unknown"
        max_matches = 0
        
        # 按优先级顺序遍历意图
        for intent in intent_priority:
            if intent not in self.intent_patterns:
                continue
                
            patterns = self.intent_patterns[intent]
            
            # 统计匹配的关键词数量
            matches = 0
            matched_patterns = []
            for pattern in patterns:
                # 确保模式和文本都转为小写进行比较
                if pattern.lower() in text_lower:
                    matches += 1
                    matched_patterns.append(pattern)
            
            # 匹配规则：
            # 1. 如果当前意图匹配数大于之前的最大匹配数，更新
            # 2. 如果匹配数相同，优先级高的意图优先
            # 3. 对于PPT通用意图(ppt_custom_generate)，只有在没有匹配到其他PPT意图时才使用
            if matches > 0:
                if intent == "ppt_custom_generate":
                    # 检查是否已经匹配到更具体的PPT意图
                    has_specific_ppt_intent = any(
                        specific_intent in matched_intent 
                        for specific_intent in ["ppt_generate_from_content", "ppt_generate_from_outline", "ppt_generate_outline"]
                    )
                    if has_specific_ppt_intent:
                        continue  # 跳过通用意图
                
                if matches > max_matches or \
                   (matches == max_matches and intent_priority.index(intent) < intent_priority.index(matched_intent)):
                    max_matches = matches
                    matched_intent = intent
        
        if max_matches > 0:
            confidence = min(0.3 + max_matches * 0.15, 0.95)
        else:
            confidence = self._classify_with_ai(text)
        
        entities = self._extract_entities(text, matched_intent)
        
        return Intent(
            type=matched_intent,
            confidence=confidence,
            entities=entities
        )
    
    def _classify_with_ai(self, text: str) -> float:
        prompt = f"""
        Classify the following user message into one of these intents:
        {', '.join(INTENT_TYPES)}
        
        Message: {text}
        
        Return only the intent name.
        """
        
        model = select_model("intent_classification", "simple")
        if not model:
            return 0.5
        
        try:
            response = call_model(model, [{"role": "user", "content": prompt}])
            response = response.strip()
            
            if response in INTENT_TYPES:
                return 0.7
            return 0.5
        except Exception as e:
            logger.error(f"AI intent classification failed: {str(e)}")
            return 0.5
    
    def _extract_entities(self, text: str, intent_type: str) -> Dict[str, str]:
        entities: Dict[str, str] = {}
        
        if intent_type in ["task_execution", "skill_request"]:
            entities["task"] = text
        
        if intent_type == "memory_query":
            entities["query"] = text
        
        import re
        
        date_pattern = r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"
        date_match = re.search(date_pattern, text)
        if date_match:
            entities["date"] = date_match.group()
        
        number_pattern = r"\d+"
        number_match = re.search(number_pattern, text)
        if number_match:
            entities["number"] = number_match.group()
        
        return entities
    
    def get_tool_for_intent(self, intent_type: str) -> Optional[str]:
        """
        根据意图获取对应的工具名称
        
        Args:
            intent_type: 意图类型
            
        Returns:
            工具名称，如果没有直接映射则返回 None
        """
        return INTENT_TO_TOOL_MAP.get(intent_type)
    
    def get_intent_for_tool(self, tool_id: str) -> Optional[str]:
        """
        根据工具名称获取对应的意图类型（反向映射）
        
        Args:
            tool_id: 工具名称
            
        Returns:
            意图类型，如果没有映射则返回 None
        """
        return TOOL_TO_INTENT_MAP.get(tool_id)
    
    def suggest_tools(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        根据用户输入和上下文建议可用的工具列表
        
        Args:
            text: 用户输入文本
            context: 上下文信息（如是否有文件上传等）
            
        Returns:
            建议的工具列表（按优先级排序）
        """
        intent = self.recognize(text)
        suggested_tools = []
        
        # 1. 根据意图获取直接映射的工具
        direct_tool = self.get_tool_for_intent(intent.type)
        if direct_tool:
            suggested_tools.append(direct_tool)
        
        # 2. 根据上下文添加额外工具建议
        if context:
            # 如果有文件上传，添加文件读取工具
            if context.get("file_key") or context.get("attachments"):
                suggested_tools.append("feishu_file_read")
            
            # 如果有历史对话，添加记忆搜索工具
            if context.get("chat_history"):
                suggested_tools.append("memory_search")
        
        # 3. 添加通用工具作为备选
        suggested_tools.extend([
            "document_search",
            "web_search",
            "file_operations"
        ])
        
        # 去重并返回
        return list(dict.fromkeys(suggested_tools))


intent_recognizer = IntentRecognizer()
