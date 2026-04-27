from typing import Dict, Any, Optional
from src.logging_config import get_logger
from src.tools.base import BaseTool, ToolSchema
from src.tools.registry import register_tool
from pydantic import Field

logger = get_logger("tool.file")


class ReadFileSchema(ToolSchema):
    """读取文件工具参数Schema"""
    path: str = Field(description="文件路径", default="")


class FeishuFileReadSchema(ToolSchema):
    """读取飞书文件工具参数Schema"""
    file_key: str = Field(description="飞书文件Key", default="")
    user_id: Optional[str] = Field(description="用户ID（用于用户隔离）", default=None)


@register_tool("read_file")
class ReadFile(BaseTool):
    """读取本地文件工具"""
    
    description = "读取本地文件内容"
    schema = ReadFileSchema
    
    def execute(self, params: Dict[str, Any]) -> str:
        file_path = params.get("path", "")
        
        if not file_path:
            return "Error: path is required"
        
        try:
            from src.infrastructure.sandbox import sandbox
            content = sandbox.read_file(file_path)
            return content if content else "Failed to read file"
        except Exception as e:
            logger.error(f"Read file failed: {str(e)}")
            return f"Error reading file: {str(e)}"


@register_tool("feishu_file_read")
class FeishuFileRead(BaseTool):
    """读取飞书文件工具（支持本地存储优先查询）"""
    
    description = "读取飞书文件内容（优先从本地存储获取）"
    schema = FeishuFileReadSchema
    
    def _get_content_from_vector_db(self, file_key: str, user_id: Optional[str] = None) -> Optional[str]:
        """
        从向量数据库中获取文件内容
        
        Args:
            file_key: 文件标识
            user_id: 用户ID（用于用户隔离）
        
        Returns:
            文件内容字符串，如果未找到返回None
        """
        try:
            from src.data.database import db
            
            memories = db.get_memories_by_tag(file_key, user_id)
            
            if memories:
                memories.sort(key=lambda m: m.timestamp, reverse=True)
                logger.info(f"从本地存储获取文件内容成功: {file_key}")
                return memories[0].content
            
            logger.info(f"未在向量数据库中找到文件: {file_key}")
            return None
            
        except Exception as e:
            logger.error(f"从向量数据库获取文件内容失败: {str(e)}")
            return None
    
    def execute(self, params: Dict[str, Any]) -> str:
        file_key = params.get("file_key", "")
        user_id = params.get("user_id", "")
        
        if not file_key:
            return "Error: file_key is required"
        
        # 首先尝试从本地存储获取
        content = self._get_content_from_vector_db(file_key, user_id)
        
        if content:
            logger.info(f"本地存储命中: {file_key}")
            return content
        
        # 如果本地没有，尝试从飞书下载
        logger.info(f"本地存储未命中，尝试从飞书下载: {file_key}")
        try:
            from src.plugins.im_adapters import FeishuAdapter
            feishu_adapter = FeishuAdapter()
            content = feishu_adapter.read_file(file_key)
            
            if content:
                logger.info(f"从飞书下载文件成功，内容长度: {len(content)}")
                return content
            else:
                return "Error: Failed to read file content"
                
        except Exception as e:
            logger.error(f"从飞书读取文件失败: {str(e)}")
            return f"Error: Failed to read file: {str(e)}"
