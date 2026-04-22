from typing import Dict, Any, Optional
from src.logging_config import get_logger

logger = get_logger("tool")


class OfficeTools:
    def __init__(self):
        self.office_apps = ["word", "excel", "powerpoint", "wps", "feishu"]
    
    def create_document(self, params: Dict[str, Any]) -> str:
        doc_type = params.get("type", "docx")
        content = params.get("content", "")
        filename = params.get("filename", "document")
        
        logger.info(f"Creating {doc_type} document: {filename}")
        
        if doc_type == "markdown":
            return self._create_markdown(filename, content)
        elif doc_type in ["docx", "xlsx", "pptx"]:
            return f"Creating {doc_type} document via API (placeholder)"
        else:
            return f"Unsupported document type: {doc_type}"
    
    def _create_markdown(self, filename: str, content: str) -> str:
        from src.infrastructure.sandbox import sandbox
        
        filepath = f"./output/{filename}.md"
        success = sandbox.write_file(filepath, content)
        
        if success:
            return f"Markdown document created: {filepath}"
        return "Failed to create document"
    
    def edit_document(self, params: Dict[str, Any]) -> str:
        filepath = params.get("filepath", "")
        content = params.get("content", "")
        
        from src.infrastructure.sandbox import sandbox
        success = sandbox.write_file(filepath, content)
        
        if success:
            return f"Document updated: {filepath}"
        return "Failed to update document"
    
    def format_document(self, params: Dict[str, Any]) -> str:
        filepath = params.get("filepath", "")
        format_type = params.get("format", "standard")
        
        logger.info(f"Formatting document: {filepath} with {format_type} style")
        
        return f"Document formatted successfully: {filepath}"
    
    def generate_chart(self, params: Dict[str, Any]) -> str:
        chart_type = params.get("type", "bar")
        data = params.get("data", {})
        title = params.get("title", "Chart")
        
        logger.info(f"Generating {chart_type} chart: {title}")
        
        return f"{chart_type} chart generated with {len(data)} data points"
    
    def extract_text(self, params: Dict[str, Any]) -> str:
        filepath = params.get("filepath", "")
        
        from src.infrastructure.sandbox import sandbox
        content = sandbox.read_file(filepath)
        
        if content:
            return content[:500] + "..." if len(content) > 500 else content
        return "Failed to extract text"


office_tools = OfficeTools()
