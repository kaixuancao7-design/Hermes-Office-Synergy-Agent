"""工具模块 - 提供原子操作工具（Claude范式）"""

# 导入基础组件
from tools.base import BaseTool, ToolSchema
from tools.registry import (
    register_tool,
    get_tool,
    list_tools,
    execute_tool,
    clear_registry
)

# 导入具体工具集
from tools.ppt_tools import (
    TemplateMatchTool,
    SpecLockTool,
    GenerateOutlineTool,
    GenerateContentTool,
    GeneratePPTTool,
    QualityCheckTool,
    FeishuSendFileTool,
    ContextStoreTool
)

from tools.file_tools import (
    ReadFileTool,
    WriteFileTool,
    ListFilesTool,
    DeleteFileTool
)

from tools.db_tools import (
    DBQueryTool,
    DBInsertTool,
    DBUpdateTool,
    DBDeleteTool
)

from tools.api_tools import (
    APIRequestTool
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

    # PPT工具
    "TemplateMatchTool",
    "SpecLockTool",
    "GenerateOutlineTool",
    "GenerateContentTool",
    "GeneratePPTTool",
    "QualityCheckTool",
    "FeishuSendFileTool",
    "ContextStoreTool",

    # 文件工具
    "ReadFileTool",
    "WriteFileTool",
    "ListFilesTool",
    "DeleteFileTool",

    # 数据库工具
    "DBQueryTool",
    "DBInsertTool",
    "DBUpdateTool",
    "DBDeleteTool",

    # API工具
    "APIRequestTool"
]