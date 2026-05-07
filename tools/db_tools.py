"""数据库操作工具集 - 提供数据库查询相关的原子操作"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from tools.base import BaseTool
from tools.registry import register_tool
from src.logging_config import get_logger

logger = get_logger("tool.db")


class QuerySchema(BaseModel):
    query: str = Field(description="SQL查询语句")
    params: Optional[List[Any]] = Field(description="查询参数", default=None)


@register_tool("db_query")
class DBQueryTool(BaseTool):
    name = "db_query"
    description = "执行数据库查询"
    schema = QuerySchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.data.database import db

            query = params.get("query")
            query_params = params.get("params", [])

            result = db.execute_query(query, query_params)

            return {
                "success": True,
                "results": result,
                "count": len(result)
            }
        except Exception as e:
            logger.error(f"数据库查询失败: {str(e)}")
            return {"success": False, "error": str(e)}


class InsertSchema(BaseModel):
    table: str = Field(description="表名")
    data: Dict[str, Any] = Field(description="插入数据")


@register_tool("db_insert")
class DBInsertTool(BaseTool):
    name = "db_insert"
    description = "插入数据到数据库"
    schema = InsertSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.data.database import db

            table = params.get("table")
            data = params.get("data", {})

            result = db.insert(table, data)

            return {
                "success": True,
                "inserted_id": result
            }
        except Exception as e:
            logger.error(f"数据库插入失败: {str(e)}")
            return {"success": False, "error": str(e)}


class UpdateSchema(BaseModel):
    table: str = Field(description="表名")
    data: Dict[str, Any] = Field(description="更新数据")
    condition: str = Field(description="更新条件")


@register_tool("db_update")
class DBUpdateTool(BaseTool):
    name = "db_update"
    description = "更新数据库记录"
    schema = UpdateSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.data.database import db

            table = params.get("table")
            data = params.get("data", {})
            condition = params.get("condition", "1=1")

            result = db.update(table, data, condition)

            return {
                "success": True,
                "updated_count": result
            }
        except Exception as e:
            logger.error(f"数据库更新失败: {str(e)}")
            return {"success": False, "error": str(e)}


class DeleteSchema(BaseModel):
    table: str = Field(description="表名")
    condition: str = Field(description="删除条件")


@register_tool("db_delete")
class DBDeleteTool(BaseTool):
    name = "db_delete"
    description = "删除数据库记录"
    schema = DeleteSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.data.database import db

            table = params.get("table")
            condition = params.get("condition", "1=1")

            result = db.delete(table, condition)

            return {
                "success": True,
                "deleted_count": result
            }
        except Exception as e:
            logger.error(f"数据库删除失败: {str(e)}")
            return {"success": False, "error": str(e)}