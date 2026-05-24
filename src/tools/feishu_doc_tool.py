"""飞书文档访问工具 - 通过飞书API获取文档内容"""
from typing import Dict, Any, Optional
import requests
from datetime import datetime, timedelta
from src.tools.base import BaseTool, ToolSchema
from src.config import settings
from src.logging_config import get_logger

logger = get_logger("tool.feishu_doc")


class FeishuDocParams(ToolSchema):
    """飞书文档工具参数Schema"""
    doc_url: str = None
    doc_id: str = None
    type: str = "doc"  # doc, sheet, slide, mindnote


class FeishuDocTool(BaseTool):
    """飞书文档访问工具 - 通过飞书开放平台API获取文档内容"""
    
    name = "feishu_doc_reader"
    description = "用于访问飞书文档内容。支持获取飞书文档、表格、幻灯片等内容。需要提供文档URL或文档ID。"
    schema = FeishuDocParams
    
    def __init__(self):
        self.app_id = settings.FEISHU_APP_ID
        self.app_secret = settings.FEISHU_APP_SECRET
        self.access_token = None
        self.token_expire_time = None
        
    def _get_access_token(self) -> Optional[str]:
        """获取飞书API访问令牌"""
        # 检查令牌是否过期
        if self.access_token and self.token_expire_time and datetime.now() < self.token_expire_time:
            return self.access_token
        
        if not self.app_id or not self.app_secret:
            logger.error("飞书APP_ID或APP_SECRET未配置")
            return None
        
        try:
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            payload = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("code") == 0:
                self.access_token = result.get("tenant_access_token")
                expire_in = result.get("expire_in", 7200)
                self.token_expire_time = datetime.now() + timedelta(seconds=expire_in - 60)  # 提前1分钟过期
                logger.info("成功获取飞书访问令牌")
                return self.access_token
            else:
                logger.error(f"获取飞书访问令牌失败: {result.get('msg')}")
                return None
        except Exception as e:
            logger.error(f"获取飞书访问令牌异常: {str(e)}")
            return None
    
    def _extract_doc_id(self, url: str) -> Optional[str]:
        """从飞书文档URL中提取文档ID"""
        import re
        
        # 匹配飞书文档URL模式
        patterns = [
            r"docs\.feishu\.cn/d/([a-zA-Z0-9_-]+)",        # 标准文档URL
            r"www\.feishu\.cn/drive/folder/([a-zA-Z0-9_-]+)",  # 文件夹URL
            r"open\.feishu\.cn/document/([a-zA-Z0-9_-]+)",     # 开放平台URL
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # 如果URL中没有找到，尝试直接使用URL作为ID（可能已经是ID）
        if re.match(r"^[a-zA-Z0-9_-]+$", url.strip()):
            return url.strip()
        
        return None
    
    def _get_doc_content(self, doc_id: str, doc_type: str = "doc") -> Dict[str, Any]:
        """获取文档内容"""
        token = self._get_access_token()
        if not token:
            return {"success": False, "error": "无法获取飞书访问令牌"}
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            if doc_type == "doc":
                # 获取飞书文档内容
                url = f"https://open.feishu.cn/open-apis/doc/v2/{doc_id}/content"
                params = {"format": "markdown"}
                
                response = requests.get(url, headers=headers, params=params, timeout=60)
                response.raise_for_status()
                
                result = response.json()
                
                if result.get("code") == 0:
                    data = result.get("data", {})
                    return {
                        "success": True,
                        "doc_id": doc_id,
                        "type": "doc",
                        "title": data.get("title", ""),
                        "content": data.get("content", ""),
                        "version": data.get("version", 0)
                    }
                else:
                    return {"success": False, "error": result.get("msg", "获取文档内容失败")}
            
            elif doc_type == "sheet":
                # 获取飞书表格内容
                url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{doc_id}/values"
                
                response = requests.get(url, headers=headers, timeout=60)
                response.raise_for_status()
                
                result = response.json()
                
                if result.get("code") == 0:
                    data = result.get("data", {})
                    return {
                        "success": True,
                        "doc_id": doc_id,
                        "type": "sheet",
                        "title": data.get("title", ""),
                        "content": data.get("valueRange", {}).get("values", []),
                        "version": data.get("version", 0)
                    }
                else:
                    return {"success": False, "error": result.get("msg", "获取表格内容失败")}
            
            elif doc_type == "slide":
                # 获取飞书幻灯片内容
                url = f"https://open.feishu.cn/open-apis/slides/v1/presentations/{doc_id}/pages"
                
                response = requests.get(url, headers=headers, timeout=60)
                response.raise_for_status()
                
                result = response.json()
                
                if result.get("code") == 0:
                    data = result.get("data", {}).get("items", [])
                    slides = []
                    for slide in data:
                        slides.append({
                            "page_id": slide.get("page_id"),
                            "title": slide.get("title", ""),
                            "elements": slide.get("elements", [])
                        })
                    return {
                        "success": True,
                        "doc_id": doc_id,
                        "type": "slide",
                        "slides": slides,
                        "count": len(slides)
                    }
                else:
                    return {"success": False, "error": result.get("msg", "获取幻灯片内容失败")}
            
            elif doc_type == "mindnote":
                # 获取飞书思维笔记内容
                url = f"https://open.feishu.cn/open-apis/mindnote/v1/mindnotes/{doc_id}/nodes"
                
                response = requests.get(url, headers=headers, timeout=60)
                response.raise_for_status()
                
                result = response.json()
                
                if result.get("code") == 0:
                    data = result.get("data", {})
                    return {
                        "success": True,
                        "doc_id": doc_id,
                        "type": "mindnote",
                        "title": data.get("title", ""),
                        "content": data.get("nodes", [])
                    }
                else:
                    return {"success": False, "error": result.get("msg", "获取思维笔记内容失败")}
            
            else:
                return {"success": False, "error": f"不支持的文档类型: {doc_type}"}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"获取文档内容请求失败: {str(e)}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"获取文档内容异常: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _search_docs(self, query: str) -> Dict[str, Any]:
        """搜索飞书文档"""
        token = self._get_access_token()
        if not token:
            return {"success": False, "error": "无法获取飞书访问令牌"}
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            url = "https://open.feishu.cn/open-apis/search/v2"
            payload = {
                "query": query,
                "page_size": 10,
                "search_scope": "doc"
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("code") == 0:
                data = result.get("data", {})
                hits = data.get("hits", [])
                
                docs = []
                for hit in hits:
                    docs.append({
                        "doc_id": hit.get("object_id", ""),
                        "title": hit.get("title", ""),
                        "url": hit.get("url", ""),
                        "type": hit.get("type", ""),
                        "updated_time": hit.get("updated_time", "")
                    })
                
                return {
                    "success": True,
                    "docs": docs,
                    "total": len(docs)
                }
            else:
                return {"success": False, "error": result.get("msg", "搜索失败")}
                
        except Exception as e:
            logger.error(f"搜索文档失败: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def execute(self, params: Dict[str, Any]) -> Any:
        """
        执行飞书文档工具
        
        Args:
            params: 工具参数，包含 doc_url 或 doc_id
            
        Returns:
            文档内容或搜索结果
        """
        logger.info(f"执行飞书文档工具 | params={params}")
        
        # 参数校验
        if not self.validate_params(params):
            return {"success": False, "error": "参数校验失败"}
        
        doc_url = params.get("doc_url")
        doc_id = params.get("doc_id")
        doc_type = params.get("type", "doc")
        
        # 获取文档ID
        if doc_url:
            doc_id = self._extract_doc_id(doc_url)
        
        if not doc_id:
            return {"success": False, "error": "无法从URL中提取文档ID，请提供有效的飞书文档URL"}
        
        # 获取文档内容
        return self._get_doc_content(doc_id, doc_type)
    
    def search(self, query: str) -> Dict[str, Any]:
        """
        搜索飞书文档
        
        Args:
            query: 搜索关键词
            
        Returns:
            搜索结果
        """
        return self._search_docs(query)


# 注册工具
from src.tools.registry import register_tool
register_tool("feishu_doc_reader")(FeishuDocTool)
