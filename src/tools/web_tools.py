"""网络请求工具 - 提供HTTP请求、网页解析等功能"""
from typing import Dict, Any, Optional, List
import requests
from src.logging_config import get_logger

logger = get_logger("tool")


class WebTools:
    """网络工具 - 提供HTTP请求和网页处理功能"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"
        })
    
    def get(self, url: str, params: Optional[Dict[str, str]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> Dict[str, Any]:
        """
        发送GET请求
        
        Args:
            url: 请求URL
            params: 请求参数
            headers: 请求头
            timeout: 超时时间
        
        Returns:
            响应结果字典
        """
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            return {
                "success": True,
                "status_code": response.status_code,
                "content": response.text,
                "headers": dict(response.headers),
                "encoding": response.encoding
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"GET请求失败 {url}: {str(e)}")
            return {"success": False, "error": str(e), "status_code": 0}
    
    def post(self, url: str, data: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None, 
             headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> Dict[str, Any]:
        """
        发送POST请求
        
        Args:
            url: 请求URL
            data: 表单数据
            json: JSON数据
            headers: 请求头
            timeout: 超时时间
        
        Returns:
            响应结果字典
        """
        try:
            response = self.session.post(url, data=data, json=json, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            return {
                "success": True,
                "status_code": response.status_code,
                "content": response.text,
                "headers": dict(response.headers)
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"POST请求失败 {url}: {str(e)}")
            return {"success": False, "error": str(e), "status_code": 0}
    
    def download_file(self, url: str, save_path: str, timeout: int = 60) -> Dict[str, Any]:
        """
        下载文件
        
        Args:
            url: 文件URL
            save_path: 保存路径
            timeout: 超时时间
        
        Returns:
            下载结果
        """
        try:
            response = self.session.get(url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return {"success": True, "path": save_path, "size": len(response.content)}
        except requests.exceptions.RequestException as e:
            logger.error(f"下载文件失败 {url}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def fetch_webpage(self, url: str) -> Dict[str, Any]:
        """
        获取网页内容并提取信息
        
        Args:
            url: 网页URL
        
        Returns:
            包含页面标题、正文、链接等信息的字典
        """
        result = self.get(url)
        
        if not result["success"]:
            return result
        
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(result["content"], "html.parser")
            
            # 提取标题
            title = soup.title.string if soup.title else ""
            
            # 提取正文（去除脚本和样式）
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            
            # 获取所有段落文本
            paragraphs = soup.find_all("p")
            text_content = "\n\n".join([p.get_text(strip=True) for p in paragraphs])
            
            # 提取链接
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # 转换为绝对URL
                if href.startswith("/"):
                    from urllib.parse import urljoin
                    href = urljoin(url, href)
                links.append({
                    "text": a.get_text(strip=True),
                    "url": href
                })
            
            return {
                "success": True,
                "url": url,
                "title": title,
                "content": text_content,
                "links": links[:20],  # 最多返回20个链接
                "status_code": result["status_code"]
            }
        except ImportError:
            logger.warning("beautifulsoup4 未安装")
            return {
                "success": True,
                "url": url,
                "title": "",
                "content": result["content"][:2000] if len(result["content"]) > 2000 else result["content"],
                "links": [],
                "status_code": result["status_code"]
            }
        except Exception as e:
            logger.error(f"解析网页失败 {url}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def search_web(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        模拟网页搜索（占位符实现）
        
        Args:
            query: 搜索关键词
            limit: 返回结果数量
        
        Returns:
            搜索结果列表
        """
        logger.info(f"执行网页搜索: {query}")
        
        # 模拟搜索结果
        mock_results = [
            {"title": f"搜索结果1: {query}", "url": f"https://example.com/search?q={query}", "snippet": "这是搜索结果1的摘要内容..."},
            {"title": f"搜索结果2: {query}", "url": f"https://example.org/article/{query}", "snippet": "这是搜索结果2的摘要内容..."},
            {"title": f"搜索结果3: {query}", "url": f"https://example.net/post/{query}", "snippet": "这是搜索结果3的摘要内容..."},
        ]
        
        return mock_results[:limit]
    
    def validate_url(self, url: str) -> bool:
        """
        验证URL是否有效
        
        Args:
            url: 待验证的URL
        
        Returns:
            是否有效
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return all([parsed.scheme, parsed.netloc])
        except Exception:
            return False
    
    def get_url_metadata(self, url: str) -> Dict[str, Any]:
        """
        获取URL的元数据
        
        Args:
            url: URL
        
        Returns:
            元数据字典
        """
        result = self.get(url)
        
        if not result["success"]:
            return {"success": False, "error": result["error"]}
        
        headers = result["headers"]
        
        return {
            "success": True,
            "url": url,
            "content_type": headers.get("content-type", ""),
            "content_length": headers.get("content-length", 0),
            "server": headers.get("server", ""),
            "last_modified": headers.get("last-modified", "")
        }
    
    def make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """
        通用请求方法
        
        Args:
            method: HTTP方法 (GET, POST, PUT, DELETE, HEAD)
            url: 请求URL
            **kwargs: 其他参数
        
        Returns:
            响应结果
        """
        method = method.upper()
        
        try:
            if method == "GET":
                return self.get(url, **kwargs)
            elif method == "POST":
                return self.post(url, **kwargs)
            elif method == "PUT":
                response = self.session.put(url, **kwargs)
                return {"success": True, "status_code": response.status_code, "content": response.text}
            elif method == "DELETE":
                response = self.session.delete(url, **kwargs)
                return {"success": True, "status_code": response.status_code, "content": response.text}
            elif method == "HEAD":
                response = self.session.head(url, **kwargs)
                return {"success": True, "status_code": response.status_code, "headers": dict(response.headers)}
            else:
                return {"success": False, "error": f"不支持的HTTP方法: {method}"}
        except Exception as e:
            logger.error(f"请求失败 {method} {url}: {str(e)}")
            return {"success": False, "error": str(e)}


# 单例实例
web_tools = WebTools()


def fetch_webpage(url: str) -> Dict[str, Any]:
    """获取网页内容（便捷函数）"""
    return web_tools.fetch_webpage(url)


def download_file(url: str, save_path: str) -> Dict[str, Any]:
    """下载文件（便捷函数）"""
    return web_tools.download_file(url, save_path)


def search_web(query: str, limit: int = 10) -> List[Dict[str, str]]:
    """网页搜索（便捷函数）"""
    return web_tools.search_web(query, limit)


def make_request(method: str, url: str, **kwargs) -> Dict[str, Any]:
    """发送HTTP请求（便捷函数）"""
    return web_tools.make_request(method, url, **kwargs)
