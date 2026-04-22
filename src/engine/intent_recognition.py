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
    "unknown"
]


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
            ]
        }
    
    def recognize(self, text: str) -> Intent:
        text_lower = text.lower()
        
        matched_intent = "unknown"
        max_matches = 0
        
        for intent, patterns in self.intent_patterns.items():
            matches = sum(1 for pattern in patterns if pattern in text_lower)
            if matches > max_matches:
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


intent_recognizer = IntentRecognizer()
