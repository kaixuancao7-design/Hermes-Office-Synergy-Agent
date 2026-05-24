"""URL内容获取工具 - 获取网页或文档内容"""
from typing import Dict, Any, Optional
import requests
from src.tools.base import BaseTool, ToolSchema
from src.logging_config import get_logger

logger = get_logger("tool.url_reader")


class UrlReaderParams(ToolSchema):
    """URL内容获取工具参数Schema"""
    url: str
    method: str = "GET"  # GET, POST
    headers: Optional[dict] = None
    data: Optional[dict] = None


class UrlReaderTool(BaseTool):
    """URL内容获取工具 - 通过HTTP请求获取网页或文档内容"""
    
    name = "url_reader"
    description = "用于获取网页或文档的内容。支持GET和POST请求，可以设置自定义请求头和请求数据。适用于访问公开可访问的网页、文档API等。"
    schema = UrlReaderParams
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br"
        })
    
    def _fetch_content(self, url: str, method: str = "GET", headers: Optional[dict] = None, 
                       data: Optional[dict] = None) -> Dict[str, Any]:
        """获取URL内容"""
        try:
            request_headers = {}
            if headers:
                request_headers.update(headers)
            
            logger.info(f"获取URL内容 | method={method} | url={url[:100]}")
            
            if method.upper() == "GET":
                response = self.session.get(url, headers=request_headers, timeout=60)
            elif method.upper() == "POST":
                response = self.session.post(url, headers=request_headers, json=data, timeout=60)
            else:
                return {"success": False, "error": f"不支持的HTTP方法: {method}"}
            
            response.raise_for_status()
            
            # 根据Content-Type处理响应
            content_type = response.headers.get("content-type", "").lower()
            
            result = {
                "success": True,
                "status_code": response.status_code,
                "url": url,
                "content_type": content_type,
                "headers": dict(response.headers)
            }
            
            # 尝试解析JSON
            if "application/json" in content_type:
                try:
                    result["content"] = response.json()
                    result["content_type"] = "json"
                except Exception:
                    result["content"] = response.text
                    result["content_type"] = "text"
            
            # 处理文本内容
            elif "text/" in content_type:
                result["content"] = response.text
            
            # 处理二进制内容（如PDF、图片等）
            else:
                result["content"] = f"二进制数据，大小: {len(response.content)} bytes"
                result["binary_size"] = len(response.content)
            
            logger.info(f"URL内容获取成功 | status_code={response.status_code} | content_length={len(response.text) if isinstance(result.get('content'), str) else 'binary'}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"获取URL内容失败 | url={url} | error={str(e)}")
            return {"success": False, "error": str(e), "status_code": getattr(e.response, "status_code", 0)}
        except Exception as e:
            logger.error(f"获取URL内容异常 | url={url} | error={str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def _extract_text(self, url: str, content: str) -> Dict[str, Any]:
        """提取网页文本内容"""
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(content, "html.parser")
            
            # 提取标题
            title = soup.title.string if soup.title else ""
            
            # 移除不需要的元素
            for element in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
                element.decompose()
            
            # 获取正文内容
            text_content = soup.get_text(separator="\n", strip=True)
            
            # 提取链接
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                if href and text:
                    links.append({"text": text[:50], "url": href})
            
            return {
                "success": True,
                "title": title,
                "text": text_content,
                "links": links[:10],
                "url": url
            }
            
        except ImportError:
            logger.warning("beautifulsoup4 未安装，返回原始内容")
            return {
                "success": True,
                "title": "",
                "text": content[:3000] if len(content) > 3000 else content,
                "links": [],
                "url": url
            }
        except Exception as e:
            logger.error(f"解析网页失败 | url={url} | error={str(e)}")
            return {"success": False, "error": str(e)}
    
    def execute(self, params: Dict[str, Any]) -> Any:
        """
        执行URL内容获取工具
        
        Args:
            params: 工具参数，包含 url、method、headers、data
            
        Returns:
            URL内容
        """
        logger.info(f"执行URL内容获取工具 | params={params}")
        
        # 参数校验
        if not self.validate_params(params):
            return {"success": False, "error": "参数校验失败"}
        
        url = params.get("url")
        method = params.get("method", "GET")
        headers = params.get("headers")
        data = params.get("data")
        
        if not url:
            return {"success": False, "error": "必须提供URL参数"}
        
        # 获取内容
        result = self._fetch_content(url, method, headers, data)
        
        if result["success"]:
            content = result.get("content", "")
            
            # 如果是文本/html内容，尝试提取正文
            if isinstance(content, str) and len(content) > 0:
                text_result = self._extract_text(url, content)
                if text_result["success"]:
                    result["title"] = text_result["title"]
                    result["text_content"] = text_result["text"]
                    result["links"] = text_result["links"]
        
        return result


# 注册工具
from src.tools.registry import register_tool
register_tool("url_reader")(UrlReaderTool)
