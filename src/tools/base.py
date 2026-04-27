from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel, ValidationError
from src.logging_config import get_logger

logger = get_logger("tool.base")


class ToolSchema(BaseModel):
    """工具参数Schema基类"""
    pass


class BaseTool(ABC):
    """工具基类，定义标准接口"""
    
    name: str = ""
    description: str = ""
    schema: Type[ToolSchema] = None
    
    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Any:
        """
        执行工具
        
        Args:
            params: 工具参数
            
        Returns:
            执行结果
        """
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        参数校验
        
        Args:
            params: 待校验参数
            
        Returns:
            True表示校验通过，False表示校验失败
        """
        if self.schema:
            try:
                self.schema(**params)
                return True
            except ValidationError as e:
                logger.error(f"参数校验失败 [{self.name}]: {e}")
                return False
        return True
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        获取工具元数据
        
        Returns:
            工具元数据字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "schema": self.schema.model_json_schema() if self.schema else {}
        }
