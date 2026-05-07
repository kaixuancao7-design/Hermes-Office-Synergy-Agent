"""文件操作工具集 - 提供文件读写相关的原子操作"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from tools.base import BaseTool
from tools.registry import register_tool
from src.logging_config import get_logger

logger = get_logger("tool.file")


class ReadFileSchema(BaseModel):
    file_path: str = Field(description="文件路径")
    encoding: Optional[str] = Field(description="文件编码", default="utf-8")


@register_tool("file_read")
class ReadFileTool(BaseTool):
    name = "file_read"
    description = "读取文件内容"
    schema = ReadFileSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            file_path = params.get("file_path")
            encoding = params.get("encoding", "utf-8")

            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()

            return {
                "success": True,
                "content": content,
                "length": len(content)
            }
        except Exception as e:
            logger.error(f"文件读取失败: {str(e)}")
            return {"success": False, "error": str(e)}


class WriteFileSchema(BaseModel):
    file_path: str = Field(description="文件路径")
    content: str = Field(description="文件内容")
    encoding: Optional[str] = Field(description="文件编码", default="utf-8")
    mode: Optional[str] = Field(description="写入模式", default="w")


@register_tool("file_write")
class WriteFileTool(BaseTool):
    name = "file_write"
    description = "写入文件内容"
    schema = WriteFileSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            file_path = params.get("file_path")
            content = params.get("content", "")
            encoding = params.get("encoding", "utf-8")
            mode = params.get("mode", "w")

            with open(file_path, mode, encoding=encoding) as f:
                f.write(content)

            return {"success": True, "file_path": file_path}
        except Exception as e:
            logger.error(f"文件写入失败: {str(e)}")
            return {"success": False, "error": str(e)}


class ListFilesSchema(BaseModel):
    directory: str = Field(description="目录路径")
    pattern: Optional[str] = Field(description="文件匹配模式", default="*")


@register_tool("file_list")
class ListFilesTool(BaseTool):
    name = "file_list"
    description = "列出目录中的文件"
    schema = ListFilesSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import os
            import fnmatch

            directory = params.get("directory", ".")
            pattern = params.get("pattern", "*")

            files = []
            for filename in os.listdir(directory):
                if fnmatch.fnmatch(filename, pattern):
                    filepath = os.path.join(directory, filename)
                    files.append({
                        "name": filename,
                        "path": filepath,
                        "is_directory": os.path.isdir(filepath),
                        "size": os.path.getsize(filepath) if os.path.isfile(filepath) else 0
                    })

            return {"success": True, "files": files}
        except Exception as e:
            logger.error(f"文件列表获取失败: {str(e)}")
            return {"success": False, "error": str(e)}


class DeleteFileSchema(BaseModel):
    file_path: str = Field(description="文件路径")


@register_tool("file_delete")
class DeleteFileTool(BaseTool):
    name = "file_delete"
    description = "删除文件"
    schema = DeleteFileSchema

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import os

            file_path = params.get("file_path")
            
            if os.path.exists(file_path):
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    import shutil
                    shutil.rmtree(file_path)
                return {"success": True}
            else:
                return {"success": False, "error": "文件不存在"}
        except Exception as e:
            logger.error(f"文件删除失败: {str(e)}")
            return {"success": False, "error": str(e)}