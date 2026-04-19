import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gateway.im_adapter import IMAdapter, IMAdapterConfig, im_adapter_manager
from src.types import Message


def test_feishu_adapter_registration():
    """测试飞书适配器注册"""
    print("=== 测试飞书适配器注册 ===")
    
    config = IMAdapterConfig(
        type="feishu",
        enabled=True,
        config={
            "app_id": "FEISHU_APP_ID",
            "app_secret": "FEISHU_APP_SECRET",
            "bot_name": "Hermes-Office-Synergy-Agent"
        }
    )
    
    im_adapter_manager.register_adapter(config)
    adapter = im_adapter_manager.get_adapter("feishu")
    
    assert adapter is not None, "飞书适配器注册失败"
    assert adapter.type == "feishu", "适配器类型不正确"
    assert adapter.enabled == True, "适配器未启用"
    
    print("[OK] 飞书适配器注册成功")


def test_feishu_message_parsing():
    """测试飞书消息解析"""
    print("\n=== 测试飞书消息解析 ===")
    
    adapter = im_adapter_manager.get_adapter("feishu")
    assert adapter is not None, "飞书适配器未注册"
    
    # 模拟飞书 Webhook 消息格式
    raw_message = {
        "message_id": "om_4a8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e",
        "sender": {
            "sender_id": {
                "user_id": "u_1234567890abcdef"
            },
            "sender_type": "user"
        },
        "content": "{\"text\":\"@Hermes 帮我生成周报\"}",
        "create_time": "1704067200",
        "message_type": "text"
    }
    
    message = adapter.receive_message(raw_message)
    
    assert message is not None, "消息解析失败"
    assert message.id == "om_4a8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e", "消息ID不正确"
    assert message.user_id == "u_1234567890abcdef", "用户ID不正确"
    assert "帮我生成周报" in message.content, "消息内容不正确"
    assert message.role == "user", "消息角色不正确"
    assert message.metadata == {"source": "feishu"}, "元数据不正确"
    
    print("[OK] 飞书消息解析成功")
    print("  - 消息ID:", message.id)
    print("  - 用户ID:", message.user_id)
    print("  - 内容:", message.content)


def test_feishu_message_sending():
    """测试飞书消息发送"""
    print("\n=== 测试飞书消息发送 ===")
    
    adapter = im_adapter_manager.get_adapter("feishu")
    assert adapter is not None, "飞书适配器未注册"
    
    test_message = Message(
        id="test_msg_id",
        user_id="u_1234567890abcdef",
        content="这是测试回复消息",
        role="assistant",
        timestamp=1704067200
    )
    
    result = adapter.send_message(test_message)
    
    assert result == True, "消息发送失败"
    print("[OK] 飞书消息发送成功（模拟）")


def test_adapter_disabled_without_config():
    """测试未配置时适配器禁用"""
    print("\n=== 测试未配置时适配器禁用 ===")
    
    # 创建禁用状态的适配器
    adapter = IMAdapter(IMAdapterConfig(
        type="feishu",
        enabled=False,
        config={}
    ))
    
    assert adapter.enabled == False, "未配置时适配器应禁用"
    
    raw_message = {
        "message_id": "test_id",
        "sender": {"sender_id": {"user_id": "test_user"}},
        "content": "test content",
        "create_time": "1704067200"
    }
    
    message = adapter.receive_message(raw_message)
    assert message is None, "禁用的适配器不应处理消息"
    
    print("[OK] 未配置时适配器正确禁用")


if __name__ == "__main__":
    print("=" * 60)
    print("飞书适配器测试")
    print("=" * 60)
    
    try:
        test_feishu_adapter_registration()
        test_feishu_message_parsing()
        test_feishu_message_sending()
        test_adapter_disabled_without_config()
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        
    except AssertionError as e:
        print("\n[FAIL] 测试失败:", e)
        sys.exit(1)
    except Exception as e:
        print("\n[ERROR] 测试异常:", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)
