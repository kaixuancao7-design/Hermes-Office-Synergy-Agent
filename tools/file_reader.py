"""文件读取工具 - 支持本地文件和飞书文件读取"""

from typing import Dict, Any, Optional
from src.logging_config import get_logger
import os

logger = get_logger("file.reader")


class ReadFile:
    """本地文件读取工具"""
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            file_path = params.get("file_path", "")
            encoding = params.get("encoding", "utf-8")
            
            if not file_path:
                return {"success": False, "error": "文件路径为空"}
            
            if not os.path.exists(file_path):
                return {"success": False, "error": f"文件不存在: {file_path}"}
            
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            return {
                "success": True,
                "content": content,
                "length": len(content),
                "file_path": file_path
            }
        
        except Exception as e:
            logger.error(f"文件读取失败: {str(e)}")
            return {"success": False, "error": str(e)}


class FeishuFileRead:
    """飞书文件读取工具"""
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.gateway.im_adapter import get_im_adapter
            
            file_key = params.get("file_key", "")
            
            if not file_key:
                return {"success": False, "error": "file_key为空"}
            
            adapter = get_im_adapter("feishu")
            if not adapter:
                return {"success": False, "error": "飞书适配器未找到"}
            
            result = adapter.download_file(file_key)
            
            if result.get("success"):
                return {
                    "success": True,
                    "content": result.get("content", ""),
                    "file_name": result.get("file_name", ""),
                    "file_path": result.get("file_path", "")
                }
            else:
                return {"success": False, "error": result.get("error", "下载失败")}
        
        except Exception as e:
            logger.error(f"飞书文件读取失败: {str(e)}")
            return {"success": False, "error": str(e)}