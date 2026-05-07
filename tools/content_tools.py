"""内容工具 - 从内容生成PPT"""

from typing import Dict, Any, List
from src.logging_config import get_logger

logger = get_logger("content.tools")


class GeneratePPTFromContent:
    """从内容生成PPT工具"""
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from src.services.ppt_service import PPTService
            
            content = params.get("content", "")
            title = params.get("title", "演示文稿")
            
            if not content:
                return {"success": False, "error": "内容为空"}
            
            ppt_service = PPTService()
            
            slides = self._generate_slides_from_content(content, title)
            
            file_path = ppt_service.generate_ppt_only(title, slides)
            
            return {
                "success": True,
                "file_path": file_path,
                "slides_count": len(slides),
                "title": title
            }
        
        except Exception as e:
            logger.error(f"从内容生成PPT失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _generate_slides_from_content(self, content: str, title: str) -> List[Dict[str, Any]]:
        slides = []
        
        slides.append({
            "type": "title",
            "title": title,
            "subtitle": "自动生成"
        })
        
        paragraphs = content.split('\n\n')
        
        for idx, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            if paragraph:
                if paragraph.startswith('- ') or paragraph.startswith('• '):
                    items = [item[2:].strip() for item in paragraph.split('\n') if item.strip()]
                    slides.append({
                        "type": "list",
                        "title": f"要点 {idx + 1}",
                        "items": items
                    })
                else:
                    slides.append({
                        "type": "content",
                        "title": f"内容 {idx + 1}",
                        "content": paragraph
                    })
        
        return slides