"""工具模块 - 向后兼容导入（已迁移到项目根目录tools/）"""

# 直接从新位置导入所有工具
from tools import *
from tools.registry import (
    register_tool,
    get_tool,
    list_tools,
    execute_tool,
    clear_registry
)

# 导出公共API（保持与之前一致）
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
    "APIRequestTool",

    # 额外工具（向后兼容）
    "GeneratePPT",
    "PPTGeneratorBase",
    "ReadFile",
    "FeishuFileRead",
    "GeneratePPTFromContent"
]