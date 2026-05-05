"""测试飞书文件发送功能"""

import sys
import os
import tempfile
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.plugins.im_adapters import FeishuAdapter
from src.config import settings


async def test_feishu_send_file():
    """测试飞书文件发送"""
    print("=== 飞书文件发送测试 ===\n")

    # 创建测试文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("这是一个测试文件\n用于测试飞书文件发送功能\n时间：2026年5月")
        test_file_path = f.name

    try:
        # 创建飞书适配器
        adapter = FeishuAdapter()

        # 检查API客户端是否已初始化
        if adapter._api_client is None:
            print("⚠️ 飞书API客户端未初始化，尝试初始化...")
            init_result = adapter._initialize_client()
            if not init_result:
                print("❌ API客户端初始化失败，请检查配置")
                return

        print("✅ API客户端初始化成功")
        print(f"测试文件: {test_file_path}")
        print(f"文件大小: {os.path.getsize(test_file_path)} bytes")

        # 发送文件测试
        print("\n🚀 开始发送文件...")
        
        # 注意：这里需要替换为实际的测试用户ID
        test_user_id = "12f95277"  # 从日志中获取的测试用户ID
        
        try:
            result = await adapter.send_file(test_user_id, test_file_path, "测试文件.txt")
            
            if result:
                print("✅ 文件发送成功！")
            else:
                print("❌ 文件发送失败")
                
        except Exception as e:
            print(f"❌ 文件发送异常: {str(e)}")
            import traceback
            traceback.print_exc()

    finally:
        # 清理测试文件
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)
            print(f"\n清理测试文件: {test_file_path}")


if __name__ == "__main__":
    print("=" * 60)
    print("飞书文件发送功能测试")
    print("=" * 60)
    print()

    asyncio.run(test_feishu_send_file())

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
