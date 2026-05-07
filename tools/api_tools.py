"""API调用工具集 - 提供HTTP请求相关的原子操作"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from tools.base import BaseTool
from tools.registry import register_tool
from src.logging_config import get_logger

logger = get_logger("tool.api")


class HttpRequestSchema(BaseModel):
    url: str = Field(description="请求URL")
    method: Optional[str] = Field(description="HTTP方法", default="GET")
    headers: Optional[Dict[str, str]] = Field(description="请求头", default=None)
    params: Optional[Dict[str, Any]] = Field(description="查询参数", default=None)
    data: Optional[Dict[str, Any]] = Field(description="请求体数据", default=None)
    json_data: Optional[Dict[str, Any]] = Field(description="JSON请求体", default=None)
    timeout: Optional[int] = Field(description="超时时间(秒)", default=30)


@register_tool("api_request")
class APIRequestTool(BaseTool):
    name = "api_request"
    description = "发送HTTP请求"
    schema = HttpRequestSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import requests

            url = params.get("url")
            method = params.get("method", "GET").upper()
            headers = params.get("headers", {})
            query_params = params.get("params", {})
            data = params.get("data")
            json_data = params.get("json_data")
            timeout = params.get("timeout", 30)

            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=query_params,
                data=data,
                json=json_data,
                timeout=timeout
            )

            response.raise_for_status()

            try:
                result = response.json()
            except ValueError:
                result = response.text

            return {
                "success": True,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content": result
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {str(e)}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"API请求异常: {str(e)}")
            return {"success": False, "error": str(e)}