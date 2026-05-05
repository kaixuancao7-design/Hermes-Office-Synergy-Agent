"""测试 _send_ppt_to_user_async 方法"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.gateway.message_router import MessageRouter

router = MessageRouter()

print("=== 检查 _send_ppt_to_user_async 方法是否存在 ===")
if hasattr(router, '_send_ppt_to_user_async'):
    print("OK: _send_ppt_to_user_async 方法存在")
    import inspect
    sig = inspect.signature(router._send_ppt_to_user_async)
    print(f"方法签名: {sig}")
else:
    print("ERROR: _send_ppt_to_user_async 方法不存在")

print("\n=== 检查 message_router 模块 ===")
import src.gateway.message_router as mr
print(f"模块文件: {mr.__file__}")
