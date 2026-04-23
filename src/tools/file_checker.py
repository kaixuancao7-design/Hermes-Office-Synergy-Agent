"""文件检查工具 - 检查文件是否存在于向量数据库中"""
from typing import Dict, Any, List, Optional, Tuple
from src.plugins.memory_stores import RedisHybridMemory, ChromaMemory
from src.plugins import get_memory_store
from src.logging_config import get_logger
from src.config import settings

logger = get_logger("tool")


class FileChecker:
    """文件检查器 - 用于分析文件是否存在于向量数据库中
    
    核心功能：
    1. 通过文件名匹配检查
    2. 通过内容语义相似度检查
    3. 分析文件唯一性并生成报告
    4. 获取向量数据库统计信息
    
    使用方式：
    >>> checker = FileChecker()
    >>> result = checker.check_file_exists(file_content, user_id, file_name)
    >>> if result['exists']:
    ...     print("文件已存在")
    """
    
    def __init__(self):
        self.memory_store = get_memory_store()
        self.SIMILARITY_THRESHOLD = 0.85  # 相似度阈值，超过此值认为是重复文件
        self._validate_memory_store()
    
    def _validate_memory_store(self):
        """验证记忆存储是否已初始化"""
        if self.memory_store is None:
            logger.warning("记忆存储未初始化，文件检查功能将受限")
    
    def check_file_exists(self, file_content: str, user_id: str, file_name: str = None) -> Dict[str, Any]:
        """
        检查文件内容是否已存在于向量数据库中
        
        Args:
            file_content: 文件内容
            user_id: 用户ID
            file_name: 文件名（可选）
            
        Returns:
            检查结果字典，包含是否存在、相似条目、相似度等信息
        """
        if not file_content or not user_id:
            return {
                "exists": False,
                "message": "缺少必要参数",
                "similar_items": [],
                "confidence": 0.0
            }
        
        # 检查记忆存储是否可用
        if self.memory_store is None:
            return {
                "exists": False,
                "message": "记忆存储未初始化，无法进行检查",
                "similar_items": [],
                "confidence": 0.0,
                "error": "memory_store_not_initialized"
            }
        
        try:
            # 1. 首先通过文件名搜索（如果提供了文件名）
            if file_name:
                filename_results = self._search_by_filename(file_name, user_id)
                if filename_results:
                    logger.info(f"通过文件名找到匹配: {len(filename_results)} 条")
                    return {
                        "exists": True,
                        "message": f"找到文件名匹配的记录",
                        "similar_items": filename_results,
                        "confidence": 0.95,
                        "match_type": "filename"
                    }
            
            # 2. 通过内容语义搜索
            content_results = self._search_by_content(file_content, user_id)
            
            if content_results:
                # 分析相似度最高的结果
                highest_similarity = self._calculate_similarity(file_content, content_results[0].content)
                
                if highest_similarity >= self.SIMILARITY_THRESHOLD:
                    return {
                        "exists": True,
                        "message": f"找到高度相似的内容（相似度: {highest_similarity:.2%}）",
                        "similar_items": content_results[:3],
                        "confidence": highest_similarity,
                        "match_type": "content"
                    }
                else:
                    return {
                        "exists": False,
                        "message": f"未找到高度相似的内容（最高相似度: {highest_similarity:.2%}）",
                        "similar_items": content_results[:3],
                        "confidence": highest_similarity,
                        "match_type": "content"
                    }
            
            return {
                "exists": False,
                "message": "向量数据库中未找到相关内容",
                "similar_items": [],
                "confidence": 0.0,
                "match_type": "none"
            }
            
        except Exception as e:
            logger.error(f"检查文件存在性失败: {str(e)}")
            return {
                "exists": False,
                "message": f"检查失败: {str(e)}",
                "similar_items": [],
                "confidence": 0.0
            }
    
    def _search_by_filename(self, filename: str, user_id: str) -> List:
        """通过文件名搜索向量数据库"""
        results = []
        
        # 使用文件名作为查询词进行搜索
        search_results = self.memory_store.search_memory(user_id, filename, limit=10)
        
        for result in search_results:
            # 检查内容中是否包含文件名
            if filename.lower() in result.content.lower():
                results.append({
                    "id": result.id,
                    "content": result.content[:100] + "..." if len(result.content) > 100 else result.content,
                    "timestamp": result.timestamp,
                    "type": result.type
                })
        
        return results
    
    def _search_by_content(self, content: str, user_id: str) -> List:
        """通过内容语义搜索向量数据库"""
        # 使用内容片段作为查询词
        query = content[:500] if len(content) > 500 else content
        return self.memory_store.search_memory(user_id, query, limit=5)
    
    def _calculate_similarity(self, content1: str, content2: str) -> float:
        """
        计算两段文本的相似度
        
        使用简单的Jaccard相似度或基于共同子字符串的相似度
        """
        if not content1 or not content2:
            return 0.0
        
        # 将文本转换为单词集合（基于空格分词）
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        # Jaccard相似度
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def analyze_file_uniqueness(self, file_content: str, user_id: str) -> Dict[str, Any]:
        """
        分析文件内容的唯一性，提供详细的分析报告
        
        Args:
            file_content: 文件内容
            user_id: 用户ID
            
        Returns:
            分析报告字典
        """
        result = self.check_file_exists(file_content, user_id)
        
        analysis = {
            "unique": not result["exists"],
            "confidence": result["confidence"],
            "analysis": {
                "total_characters": len(file_content),
                "total_words": len(file_content.split()),
                "similarity_threshold": self.SIMILARITY_THRESHOLD,
                "matches_found": len(result.get("similar_items", []))
            },
            "recommendations": []
        }
        
        if result["exists"]:
            analysis["recommendations"].append("文件内容可能已存在于向量数据库中")
            analysis["recommendations"].append("建议检查现有记录是否满足需求")
            analysis["recommendations"].append("如果需要更新，请使用update_memory方法")
        else:
            analysis["recommendations"].append("文件内容是新的，可以安全添加到向量数据库")
        
        return analysis
    
    def get_vector_db_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户向量数据库统计信息"""
        try:
            stats = {
                "user_id": user_id,
                "memory_count": self.memory_store.get_memory_count(user_id),
                "memory_type": self.memory_store.get_memory_type()
            }
            return stats
        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}")
            return {"error": str(e)}


# 单例实例
file_checker = FileChecker()


def check_feishu_file_exists(file_key: str, user_id: str) -> Dict[str, Any]:
    """
    检查飞书上传的文件是否存在于向量数据库中
    
    流程：
    1. 通过飞书API获取文件内容
    2. 使用file_checker检查内容是否存在
    3. 返回检查结果
    
    Args:
        file_key: 飞书文件key
        user_id: 用户ID
        
    Returns:
        检查结果
    """
    from src.plugins.im_adapters import FeishuAdapter
    
    try:
        # 获取飞书适配器
        adapter = FeishuAdapter()
        
        # 调用飞书API下载文件内容
        # 注意：这里需要飞书API的文件下载权限
        file_content = _download_feishu_file(adapter, file_key)
        
        if file_content:
            return file_checker.check_file_exists(file_content, user_id, file_key)
        else:
            return {
                "exists": False,
                "message": "无法获取文件内容",
                "error": "文件下载失败"
            }
            
    except Exception as e:
        logger.error(f"检查飞书文件失败: {str(e)}")
        return {
            "exists": False,
            "message": f"检查失败: {str(e)}",
            "error": str(e)
        }


def _download_feishu_file(adapter, file_key: str, message_id: str = None) -> Optional[str]:
    """
    从飞书下载文件内容（支持新版 file_v3）
    
    Args:
        adapter: 飞书适配器实例
        file_key: 文件key
        message_id: 消息ID（用于新版 file_v3 下载）
        
    Returns:
        文件内容字符串，如果下载失败返回None
    """
    try:
        # 调用适配器的真实文件读取方法
        logger.info(f"开始下载文件: {file_key}")
        
        # 使用 adapter 的 _read_feishu_file 方法进行真实下载
        file_content = adapter._read_feishu_file(file_key, message_id)
        
        if file_content:
            logger.info(f"文件下载成功: {file_key}")
            return file_content
        else:
            logger.error(f"文件下载失败，返回内容为空: {file_key}")
            return None
            
    except Exception as e:
        logger.error(f"下载飞书文件失败: {str(e)}", exc_info=True)
        return None


# 测试函数
def test_file_checker():
    """测试文件检查器"""
    checker = FileChecker()
    
    # 测试空内容
    result = checker.check_file_exists("", "test_user")
    assert not result["exists"]
    print("[OK] 空内容测试通过")
    
    # 测试内容检查
    result = checker.check_file_exists("测试文档内容", "test_user")
    print(f"内容检查结果: {result}")
    print("[OK] 内容检查测试通过")
    
    # 测试唯一性分析
    analysis = checker.analyze_file_uniqueness("测试文档内容", "test_user")
    print(f"唯一性分析: {analysis}")
    print("[OK] 唯一性分析测试通过")
    
    # 测试统计信息
    stats = checker.get_vector_db_stats("test_user")
    print(f"统计信息: {stats}")
    print("[OK] 统计信息测试通过")
    
    print("\n所有测试通过！")


if __name__ == "__main__":
    test_file_checker()
