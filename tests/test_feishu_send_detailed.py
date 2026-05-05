"""测试飞书文件发送 - 详细日志"""

import sys
import os
import tempfile
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.plugins.im_adapters import FeishuAdapter


async def test_feishu_send_file():
    """测试飞书文件发送详细流程"""
    print("=== Feishu File Send Test - Detailed ===")

    # 创建测试文件
    test_file_path = tempfile.mktemp(suffix='.txt')
    with open(test_file_path, 'w') as f:
        f.write("Test content for Feishu file send\n")
        f.write("Line 2\n")
        f.write("Line 3")

    try:
        # 创建飞书适配器
        adapter = FeishuAdapter()

        print("\n1. Initializing API client...")
        if adapter._api_client is None:
            init_result = adapter._initialize_client()
            print("   Result: " + str(init_result))
            if not init_result:
                print("   FAILED: API client init failed")
                return

        print("   SUCCESS: API client initialized")

        # 测试上传文件
        print("\n2. Uploading file...")
        try:
            upload_result = await adapter._upload_file(test_file_path)
            print("   Upload result: " + str(upload_result))
            if upload_result:
                print("   File key: " + upload_result.get('file_key', 'N/A'))
            else:
                print("   FAILED: File upload failed")
        except Exception as e:
            print("   ERROR during upload: " + str(e))
            return

        # 测试发送消息
        print("\n3. Sending message with file...")
        test_user_id = "12f95277"
        try:
            # 先测试发送文本消息确认用户ID是否正确
            msg_result = await adapter.send_message(test_user_id, "Test message from Python")
            print("   Text message result: " + str(msg_result))
            
            # 测试发送文件消息
            file_result = await adapter.send_file(test_user_id, test_file_path, "test_file.txt")
            print("   File send result: " + str(file_result))
            
            if file_result:
                print("   SUCCESS: File sent!")
            else:
                print("   FAILED: File send failed")
                
        except Exception as e:
            print("   ERROR during send: " + str(e))
            import traceback
            traceback.print_exc()

    finally:
        # Cleanup
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)
            print("\nCleaned test file")


if __name__ == "__main__":
    asyncio.run(test_feishu_send_file())
