"""工具基础类 - 定义工具的基本结构和接口"""

from typing import Dict, Any, Optional
from pydantic import BaseModel
from abc import ABC, abstractmethod


class ToolSchema(BaseModel):
    """工具参数Schema基类"""
    pass


class BaseTool(ABC):
    """工具基类"""
    
    name: str = ""
    description: str = ""
    schema: Optional[type] = None
    
    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """验证参数"""
        if self.schema:
            try:
                self.schema(**params)
                return True
            except Exception:
                return False
        return True
    
    def get_metadata(self) -> Dict[str, Any]:
        """获取工具元数据"""
        return {
            "name": self.name,
            "description": self.description,
            "schema": self.schema.model_json_schema() if self.schema else {}
        }