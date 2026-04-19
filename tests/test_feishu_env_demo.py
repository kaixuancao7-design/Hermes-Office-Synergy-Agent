import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 模拟系统环境变量配置（演示用）
os.environ['FEISHU_APP_ID'] = 'your_actual_feishu_app_id'
os.environ['FEISHU_APP_SECRET'] = 'your_actual_feishu_app_secret'

# 现在导入配置，确保使用新设置的环境变量
from src.config import Settings

def test_env_config():
    """测试环境变量配置"""
    print("=== 测试环境变量配置 ===")
    
    # 读取系统环境变量
    app_id = os.environ.get('FEISHU_APP_ID')
    app_secret = os.environ.get('FEISHU_APP_SECRET')
    
    print("[INFO] 系统环境变量:")
    print("  - FEISHU_APP_ID:", app_id)
    print("  - FEISHU_APP_SECRET:", "***" if app_secret else "未设置")
    
    # 创建新的 Settings 实例来读取环境变量
    settings = Settings()
    
    print("\n[INFO] Pydantic Settings 读取结果:")
    print("  - FEISHU_APP_ID:", settings.FEISHU_APP_ID)
    print("  - FEISHU_APP_SECRET:", "***" if settings.FEISHU_APP_SECRET else "未设置")
    print("  - FEISHU_BOT_NAME:", settings.FEISHU_BOT_NAME)
    
    # 验证配置是否正确读取
    assert settings.FEISHU_APP_ID == app_id, "配置读取不一致"
    assert settings.FEISHU_APP_SECRET == app_secret, "配置读取不一致"
    
    print("\n[OK] 环境变量配置测试通过！")
    
    return settings


def test_adapter_registration(settings):
    """测试适配器注册"""
    print("\n=== 测试适配器注册 ===")
    
    from src.gateway.im_adapter import IMAdapterConfig, im_adapter_manager
    
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
    adapter = im_adapter_manager.get_adapter("feishu")
    
    assert adapter is not None, "适配器注册失败"
    assert adapter.enabled == True, "适配器应启用"
    
    print("[OK] 飞书适配器注册成功")
    return adapter


def test_message_flow(adapter):
    """测试消息流程"""
    print("\n=== 测试消息流程 ===")
    
    from src.types import Message
    
    # 模拟飞书消息
    raw_message = {
        "message_id": "env_demo_msg_001",
        "sender": {
            "sender_id": {"user_id": "demo_user_001"},
            "sender_type": "user"
        },
        "content": "{\"text\":\"@Hermes 测试环境变量配置\"}",
        "create_time": str(int(time.time())),
        "message_type": "text"
    }
    
    message = adapter.receive_message(raw_message)
    assert message is not None, "消息解析失败"
    
    print("[OK] 消息解析成功:")
    print("  - 用户ID:", message.user_id)
    print("  - 内容:", message.content)
    
    # 回复消息
    response = Message(
        id="demo_response_001",
        user_id=message.user_id,
        content="环境变量配置测试成功！",
        role="assistant",
        timestamp=int(time.time())
    )
    
    result = adapter.send_message(response)
    assert result == True, "消息发送失败"
    
    print("[OK] 消息发送成功")


def main():
    print("=" * 60)
    print("飞书环境变量配置演示测试")
    print("=" * 60)
    
    try:
        # 测试环境变量配置
        settings = test_env_config()
        
        # 测试适配器注册
        adapter = test_adapter_registration(settings)
        
        # 测试消息流程
        test_message_flow(adapter)
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
