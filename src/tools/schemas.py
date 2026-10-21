"""Shared tool input schemas, independent of agent orchestration."""
from pydantic import BaseModel, Field


class DocumentSearchInput(BaseModel):
    """文档搜索参数"""
    query: str = Field(description="要在文档向量库中搜索的关键词或问题")
    limit: int = Field(default=5, description="返回结果的最大数量")


class MemorySearchInput(BaseModel):
    """记忆搜索参数"""
    query: str = Field(description="要搜索的记忆关键词或问题")
    limit: int = Field(default=5, description="返回结果的最大数量")


class WebSearchInput(BaseModel):
    """网页搜索参数"""
    query: str = Field(description="要在网上搜索的关键词")


class CodeExecutionInput(BaseModel):
    """代码执行参数"""
    code: str = Field(description="要执行的完整代码")
    language: str = Field(default="python", description="编程语言，默认python")


class FileOperationsInput(BaseModel):
    """文件操作参数"""
    operation: str = Field(description="操作类型: read(读取), write(写入), list(列出文件), delete(删除)")
    path: str = Field(description="文件或目录的路径")
    content: str = Field(default="", description="要写入的内容（仅write操作需要）")


class FeishuFileReadInput(BaseModel):
    """飞书文件读取参数"""
    file_key: str = Field(description="飞书文件的唯一标识key")
    user_id: str = Field(default="", description="当前用户ID")
