"""测试飞书文件发送功能 - 简化版"""

import sys
import os
import tempfile
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.plugins.im_adapters import FeishuAdapter


async def test_feishu_send_file():
    """测试飞书文件发送"""
    print("=== Feishu File Send Test ===\n")

    # 创建测试文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is a test file\nFor testing Feishu file send\nTime: May 2026")
        test_file_path = f.name

    try:
        # 创建飞书适配器
        adapter = FeishuAdapter()

        # 检查API客户端是否已初始化
        if adapter._api_client is None:
            print("API client not initialized, trying to init...")
            init_result = adapter._initialize_client()
            if not init_result:
                print("API client init failed, check config")
                return

        print("API client initialized successfully")
        print("Test file: " + test_file_path)
        print("File size: " + str(os.path.getsize(test_file_path)) + " bytes")

        # Send file test
        print("\nSending file...")
        
        # Test user ID from logs
        test_user_id = "12f95277"
        
        try:
            result = await adapter.send_file(test_user_id, test_file_path, "test_file.txt")
            
            if result:
                print("File sent successfully!")
            else:
                print("File send failed")
                
        except Exception as e:
            print("Error sending file: " + str(e))
            import traceback
            traceback.print_exc()

    finally:
        # Cleanup
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)
            print("\nCleaned test file: " + test_file_path)


if __name__ == "__main__":
    print("=" * 60)
    print("Feishu File Send Test")
    print("=" * 60)
    print()

    asyncio.run(test_feishu_send_file())

    print("\n" + "=" * 60)
    print("Test Completed")
    print("=" * 60)
