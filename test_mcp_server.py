"""MCP Server 测试脚本 - 验证官方 MCP SDK 集成"""

import asyncio
import sys


async def test_mcp_server():
    """测试 MCP Server"""
    print("=" * 60)
    print("MCP Server 测试")
    print("=" * 60)

    try:
        import sys
        sys.path.insert(0, '.')

        from src.engine.mcp_server import mcp, document_search, memory_search, generate_ppt

        print("\n1. 检查 MCP Server 实例")
        print(f"   MCP Server: {mcp}")
        print(f"   类型: {type(mcp)}")

        print("\n2. 检查已注册的工具")
        print(f"   document_search: {document_search}")
        print(f"   memory_search: {memory_search}")
        print(f"   generate_ppt: {generate_ppt}")

        print("\n3. 测试工具调用 - document_search")
        result = await document_search(
            query="测试查询",
            limit=3
        )
        print(f"   结果: {result}")

        print("\n4. 测试工具调用 - memory_search")
        result = await memory_search(
            user_id="test_user",
            query="测试记忆"
        )
        print(f"   结果: {result}")

        print("\n5. 获取 MCP Server 信息")
        print(f"   Server Name: {mcp.name if hasattr(mcp, 'name') else 'N/A'}")
        print(f"   工具数量: {len(mcp._tool_manager.list_tools()) if hasattr(mcp, '_tool_manager') else 'N/A'}")

        print("\n" + "=" * 60)
        print("测试完成!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def list_mcp_tools():
    """列出 MCP Server 中的所有工具"""
    print("\n" + "=" * 60)
    print("MCP Server 工具列表")
    print("=" * 60)

    try:
        from src.engine.mcp_server import mcp

        if hasattr(mcp, '_tool_manager'):
            tools = mcp._tool_manager.list_tools()
            print(f"\n共 {len(tools)} 个工具:\n")
            for i, tool in enumerate(tools, 1):
                print(f"  {i}. {tool}")
        else:
            print("工具管理器不可用")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"错误: {str(e)}")


if __name__ == "__main__":
    print("启动 MCP Server 测试...")

    result = asyncio.run(test_mcp_server())

    if result and "--list" in sys.argv:
        list_mcp_tools()

    sys.exit(0 if result else 1)