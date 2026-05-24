"""学习循环引擎"""
from typing import Dict, Any, Optional, List
from src.logging_config import get_logger
from src.utils import generate_id, get_timestamp

logger = get_logger("engine")


class LearningCycle:
    """学习循环管理器"""
    
    def __init__(self):
        self.corrections: Dict[str, Dict[str, Any]] = {}
        self.user_patterns: Dict[str, List[Dict[str, Any]]] = {}
    
    def capture_correction(self, user_id: str, original: str, corrected: str, context: str) -> None:
        """捕获用户修正"""
        correction_id = generate_id()
        
        correction = {
            "id": correction_id,
            "user_id": user_id,
            "original": original,
            "corrected": corrected,
            "context": context,
            "timestamp": get_timestamp(),
            "status": "pending"
        }
        
        if user_id not in self.corrections:
            self.corrections[user_id] = {}
        
        self.corrections[user_id][correction_id] = correction
        
        logger.info(f"捕获修正: user_id={user_id}, correction_id={correction_id}")
        
        # 尝试学习模式
        self._learn_pattern(user_id, original, corrected, context)
    
    def _learn_pattern(self, user_id: str, original: str, corrected: str, context: str) -> None:
        """从修正中学习模式"""
        try:
            # 分析修正模式
            pattern = {
                "original": original,
                "corrected": corrected,
                "context": context,
                "timestamp": get_timestamp(),
                "confidence": 0.8
            }
            
            if user_id not in self.user_patterns:
                self.user_patterns[user_id] = []
            
            self.user_patterns[user_id].append(pattern)
            
            # 限制每个用户的模式数量
            if len(self.user_patterns[user_id]) > 100:
                self.user_patterns[user_id] = self.user_patterns[user_id][-50:]
            
            logger.debug(f"学习模式: user_id={user_id}, pattern_count={len(self.user_patterns[user_id])}")
        
        except Exception as e:
            logger.error(f"学习模式失败: {str(e)}")
    
    def suggest_response(self, user_id: str, query: str) -> Optional[str]:
        """基于学习到的模式建议响应"""
        if user_id not in self.user_patterns:
            return None
        
        patterns = self.user_patterns[user_id]
        
        # 查找匹配的模式
        for pattern in patterns:
            if pattern["original"] in query or query in pattern["original"]:
                logger.info(f"匹配学习模式: user_id={user_id}")
                return pattern["corrected"]
        
        return None
    
    def get_corrections(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的修正记录"""
        return list(self.corrections.get(user_id, {}).values())
    
    def approve_correction(self, user_id: str, correction_id: str) -> bool:
        """批准修正"""
        if user_id not in self.corrections:
            return False
        
        if correction_id not in self.corrections[user_id]:
            return False
        
        self.corrections[user_id][correction_id]["status"] = "approved"
        return True


# 全局实例
learning_cycle = LearningCycle()
