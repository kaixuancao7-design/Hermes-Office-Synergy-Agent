import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.gateway.im_adapter import IMAdapter, IMAdapterConfig, im_adapter_manager
from src.types import Message


def setup_adapter():
    """设置飞书适配器"""
    print("[INFO] 设置飞书适配器...")
    
    config = IMAdapterConfig(
        type="feishu",
        enabled=True,
        config={
            "app_id": settings.FEISHU_APP_ID,
            "app_secret": settings.FEISHU_APP_SECRET,
            "bot_name": settings.FEISHU_BOT_NAME
        }
    )
    
    im_adapter_manager.register_adapter(config)
    print("[OK] 飞书适配器已注册")


def test_feishu_send_message():
    """测试飞书消息发送"""
    print("\n=== 测试飞书消息发送 ===")
    
    # 获取飞书适配器
    adapter = im_adapter_manager.get_adapter("feishu")
    if not adapter:
        print("[ERROR] 飞书适配器未注册")
        return
    
    if not adapter.enabled:
        print("[ERROR] 飞书适配器未启用")
        return
    
    # 创建测试消息
    test_message = Message(
        id="test_msg_send_001",
        user_id="12f95277",
        content="这是一条测试消息，来自 Hermes Office Synergy Agent",
        role="assistant",
        timestamp=1704067200
    )
    
    print("[INFO] 准备发送消息:")
    print("  - 用户ID:", test_message.user_id)
    print("  - 内容:", test_message.content)
    
    # 发送消息
    result = adapter.send_message(test_message)
    
    if result:
        print("[OK] 消息发送成功！")
    else:
        print("[ERROR] 消息发送失败")


def test_feishu_webhook_flow():
    """测试飞书 Webhook 完整流程"""
    print("\n=== 测试飞书 Webhook 完整流程 ===")
    
    # 模拟飞书事件回调
    mock_webhook_payload = {
        "type": "event",
        "event": {
            "type": "message",
            "message": {
                "message_id": "om_4a8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e",
                "content": "{\"text\":\"@Hermes 你好，测试一下\"}",
                "chat_type": "p2p",
                "create_time": "1704067200"
            },
            "sender": {
                "sender_id": {
                    "user_id": "u_7a9f2e4c6d8b0a1c2e3f4a5b6c7d8e9f"
                },
                "sender_type": "user"
            },
            "event_time": "1704067200"
        }
    }
    
    print("[INFO] 模拟飞书 Webhook 消息...")
    
    # 解析消息
    adapter = im_adapter_manager.get_adapter("feishu")
    if not adapter:
        print("[ERROR] 飞书适配器未注册")
        return
    
    message = adapter.receive_message(mock_webhook_payload)
    if message:
        print("[OK] 消息解析成功:")
        print("  - 消息ID:", message.id)
        print("  - 用户ID:", message.user_id)
        print("  - 内容:", message.content)
        print("  - 来源:", message.metadata.get("source"))
    else:
        print("[ERROR] 消息解析失败")


def main():
    print("=" * 60)
    print("飞书消息发送测试")
    print("=" * 60)
    
    # 设置适配器
    setup_adapter()
    
    # 测试消息发送
    test_feishu_send_message()
    
    # 测试 Webhook 流程
    test_feishu_webhook_flow()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
