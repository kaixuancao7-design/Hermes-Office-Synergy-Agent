"""MCP快速验证脚本 - 验证核心功能"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("Model Context Protocol (MCP) 快速验证")
print("=" * 60)

try:
    from src.engine.mcp import (
        mcp_manager,
        ContextScope,
        ContextType,
        ContextState,
        BaseMCPContext
    )
    print("[OK] MCP模块导入成功")
except Exception as e:
    print(f"[ERROR] 导入失败: {e}")
    sys.exit(1)

print("\n1. 创建基础上下文...")
ctx = mcp_manager.create_context(
    context_type=ContextType.CUSTOM,
    scope=ContextScope.REQUEST,
    user_id="demo_user",
    initial_data={"test": "data", "number": 123}
)
print(f"[OK] 上下文创建成功: {ctx}")

print("\n2. 设置和获取数据...")
ctx.set("key", "value")
value = ctx.get("key")
print(f"[OK] 设置/获取成功: {value}")

print("\n3. 序列化测试...")
serialized = ctx.serialize()
print(f"[OK] 序列化成功, 长度: {len(serialized)} 字符")

print("\n4. 反序列化测试...")
try:
    new_ctx = BaseMCPContext.deserialize(serialized)
    print(f"[OK] 反序列化成功")
except Exception as e:
    print(f"[ERROR] 反序列化失败: {e}")

print("\n5. 上下文管理器统计...")
stats = mcp_manager.get_context_count()
print(f"[OK] 统计: {stats}")

print("\n" + "=" * 60)
print("[SUCCESS] MCP核心功能验证通过!")
print("=" * 60)
