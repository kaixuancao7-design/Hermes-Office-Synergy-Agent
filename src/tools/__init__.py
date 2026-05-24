"""工具模块 - 提供各种工具的注册和调用能力"""

# 导入核心组件
from src.tools.base import BaseTool, ToolSchema
from src.tools.registry import (
    register_tool,
    get_tool,
    list_tools,
    execute_tool,
    clear_registry,
    register_tools
)

# 导入具体工具
from src.tools.ppt_generator import (
    GeneratePPT,
    PPTGeneratorBase
)
from src.tools.file_reader import (
    ReadFile,
    FeishuFileRead
)
from src.tools.content_tools import (
    GeneratePPTFromContent
)
from src.tools.feishu_doc_tool import (
    FeishuDocTool,
    FeishuDocParams
)
from src.tools.url_reader_tool import (
    UrlReaderTool,
    UrlReaderParams
)

# 导出公共API
__all__ = [
    # 基础类
    "BaseTool",
    "ToolSchema",

    # 注册器
    "register_tool",
    "get_tool",
    "list_tools",
    "execute_tool",
    "clear_registry",
    "register_tools",

    # 工具类
    "GeneratePPT",
    "PPTGeneratorBase",
    "ReadFile",
    "FeishuFileRead",
    "GeneratePPTFromContent",
    "FeishuDocTool",
    "FeishuDocParams",
    "UrlReaderTool",
    "UrlReaderParams"
]
