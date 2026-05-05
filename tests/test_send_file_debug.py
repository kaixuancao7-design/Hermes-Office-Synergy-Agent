"""调试飞书文件发送"""

import sys
import os
import tempfile
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.plugins.im_adapters import FeishuAdapter


async def test_send_file_debug():
    """调试飞书文件发送"""
    print("=== Debug Feishu File Send ===")

    # 创建测试文件
    test_file_path = tempfile.mktemp(suffix='.txt')
    with open(test_file_path, 'w') as f:
        f.write("Test content")

    try:
        adapter = FeishuAdapter()
        
        # 确保客户端已初始化
        if adapter._api_client is None:
            adapter._initialize_client()
        
        test_user_id = "12f95277"
        
        print("\nTesting send_file to user: " + test_user_id)
        print("File path: " + test_file_path)
        
        # 直接调用send_file并捕获详细错误
        try:
            result = await adapter.send_file(test_user_id, test_file_path, "test.txt")
            print("\nResult: " + str(result))
            
        except Exception as e:
            print("\nERROR: " + str(e))
            import traceback
            print("\nFull traceback:")
            traceback.print_exc()

    finally:
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)


if __name__ == "__main__":
    asyncio.run(test_send_file_debug())
