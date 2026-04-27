"""意图识别模块 - 分析用户输入的意图"""

from typing import Dict, Any, Optional, List
from src.logging_config import get_logger

logger = get_logger("skill.intent")


class IntentModel:
    """意图识别模型"""
    
    def __init__(self):
        # 意图模式映射
        self.intent_patterns = {
            "generate_ppt": [
                "生成PPT", "制作PPT", "创建演示文稿", "做个幻灯片",
                "根据文件生成PPT", "根据内容生成PPT", "生成演示文稿",
                "这个文件生成PPT", "那个文件生成PPT", "上传的文件生成PPT"
            ],
            "read_file": [
                "读取文件", "查看文件", "打开文件", "获取文件内容",
                "读取文档", "查看文档", "读取这个文件", "查看这个文件",
                "这个文件内容", "文档内容", "文件内容"
            ],
            "summarize": [
                "总结", "概括", "摘要", "简述", "总结一下", "概括一下",
                "总结内容", "概括内容"
            ],
            "search": [
                "搜索", "查找", "查询", "搜索一下", "查找一下"
            ],
            "help": [
                "帮助", "帮助我", "怎么用", "使用说明", "功能介绍"
            ],
            "file_upload": [
                "上传文件", "发送文件", "提交文件", "上传文档"
            ]
        }
        
        # 指代性词汇
        self.referential_phrases = [
            "这个文件", "那个文件", "刚才的文件", "上传的文件",
            "这份文档", "那个文档", "刚刚的文档"
        ]
    
    def predict(self, user_input: str) -> str:
        """
        预测用户意图
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            意图类型字符串
        """
        input_lower = user_input.lower()
        
        # 匹配意图模式
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if pattern.lower() in input_lower:
                    logger.info(f"识别意图: {intent}")
                    return intent
        
        # 默认意图
        return "unknown"
    
    def extract_entities(self, user_input: str) -> Dict[str, Any]:
        """
        提取实体信息
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            实体信息字典
        """
        entities = {
            "filename": None,
            "has_referential": False,
            "referential_phrase": None
        }
        
        input_lower = user_input.lower()
        
        # 检查是否包含指代性词汇
        for phrase in self.referential_phrases:
            if phrase.lower() in input_lower:
                entities["has_referential"] = True
                entities["referential_phrase"] = phrase
                break
        
        # 尝试提取文件名（简单实现：匹配常见文件扩展名）
        file_extensions = [".md", ".txt", ".docx", ".pdf", ".pptx", ".xlsx"]
        for ext in file_extensions:
            if ext.lower() in input_lower:
                # 提取文件名
                parts = input_lower.split(ext)[0]
                # 取最后一个空格后的内容作为文件名
                filename = parts.split()[-1] + ext
                entities["filename"] = filename
                break
        
        return entities
    
    def analyze(self, user_input: str) -> Dict[str, Any]:
        """
        完整分析用户输入
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            分析结果字典，包含意图和实体信息
        """
        return {
            "intent": self.predict(user_input),
            "entities": self.extract_entities(user_input),
            "confidence": self._calculate_confidence(user_input)
        }
    
    def _calculate_confidence(self, user_input: str) -> float:
        """
        计算意图识别置信度
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            置信度（0-1）
        """
        input_lower = user_input.lower()
        matched_count = 0
        total_patterns = sum(len(patterns) for patterns in self.intent_patterns.values())
        
        for patterns in self.intent_patterns.values():
            for pattern in patterns:
                if pattern.lower() in input_lower:
                    matched_count += 1
        
        if matched_count == 0:
            return 0.0
        
        # 简单置信度计算：匹配模式数/总模式数
        return min(matched_count / total_patterns * 2, 1.0)


class ContextualIntentAnalyzer:
    """上下文感知意图分析器"""
    
    def __init__(self):
        self.intent_model = IntentModel()
    
    def analyze_with_context(self, 
                            user_input: str, 
                            context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        结合上下文分析用户意图
        
        Args:
            user_input: 用户输入文本
            context: 上下文信息
            
        Returns:
            分析结果字典
        """
        result = self.intent_model.analyze(user_input)
        
        # 如果检测到指代性词汇，尝试从上下文中获取相关信息
        if result["entities"]["has_referential"] and context:
            # 获取最近上传的文件
            recent_files = context.get("recent_files", [])
            if recent_files:
                result["entities"]["referenced_file"] = recent_files[-1]
                logger.info(f"解析指代性词汇，关联文件: {result['entities']['referenced_file']}")
        
        # 检查是否有文件上传历史
        if context:
            result["context_info"] = {
                "has_recent_upload": len(context.get("recent_files", [])) > 0,
                "last_upload_time": context.get("last_upload_time"),
                "session_id": context.get("session_id")
            }
        
        return result
    
    def suggest_next_action(self, 
                           analysis: Dict[str, Any], 
                           context: Dict[str, Any]) -> Optional[str]:
        """
        根据分析结果和上下文建议下一步操作
        
        Args:
            analysis: 意图分析结果
            context: 上下文信息
            
        Returns:
            建议的下一步操作
        """
        intent = analysis["intent"]
        
        # 如果用户提到"这个文件"但没有明确意图，建议询问具体需求
        if analysis["entities"]["has_referential"] and intent == "unknown":
            return "询问用户对文件的具体操作需求"
        
        # 如果意图是生成PPT但没有文件内容，建议读取文件
        if intent == "generate_ppt" and not context.get("file_content"):
            return "读取文件内容"
        
        # 如果意图是总结但没有文件内容，建议读取文件
        if intent == "summarize" and not context.get("file_content"):
            return "读取文件内容"
        
        return None


# 全局实例
intent_model = IntentModel()
contextual_analyzer = ContextualIntentAnalyzer()
