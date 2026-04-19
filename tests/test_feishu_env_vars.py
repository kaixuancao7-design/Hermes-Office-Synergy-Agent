import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.gateway.im_adapter import IMAdapter, IMAdapterConfig, im_adapter_manager
from src.types import Message


def test_system_env_variables():
    """测试系统环境变量配置"""
    print("=== 测试系统环境变量配置 ===")
    
    # 直接从 os.environ 获取系统环境变量
    feishu_app_id = os.environ.get('FEISHU_APP_ID')
    feishu_app_secret = os.environ.get('FEISHU_APP_SECRET')
    
    print("[INFO] 从系统环境变量读取:")
    print("  - FEISHU_APP_ID:", feishu_app_id if feishu_app_id else "未设置")
    print("  - FEISHU_APP_SECRET:", "***" if feishu_app_secret else "未设置")
    
    # 验证 Pydantic Settings 是否正确读取
    print("\n[INFO] 从 Pydantic Settings 读取:")
    print("  - settings.FEISHU_APP_ID:", settings.FEISHU_APP_ID if settings.FEISHU_APP_ID else "未设置")
    print("  - settings.FEISHU_APP_SECRET:", "***" if settings.FEISHU_APP_SECRET else "未设置")
    print("  - settings.FEISHU_BOT_NAME:", settings.FEISHU_BOT_NAME)
    
    if not feishu_app_id or not feishu_app_secret:
        print("[WARN] 系统环境变量未完整配置")
        return False
    
    # 验证两者是否一致
    assert feishu_app_id == settings.FEISHU_APP_ID, "环境变量与设置不一致"
    print("[OK] 系统环境变量配置正确")
    return True


def test_adapter_with_env_vars():
    """使用系统环境变量配置适配器"""
    print("\n=== 使用系统环境变量配置适配器 ===")
    
    if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
        print("[SKIP] 环境变量未配置，跳过适配器测试")
        return
    
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
    assert adapter.config.config["app_id"] == settings.FEISHU_APP_ID, "配置不正确"
    
    print("[OK] 使用系统环境变量注册适配器成功")
    
    # 测试消息流程
    test_message_flow(adapter)


def test_message_flow(adapter):
    """测试消息流程"""
    print("\n=== 测试消息流程 ===")
    
    # 模拟收到飞书消息
    raw_message = {
        "message_id": "env_test_msg_001",
        "sender": {
            "sender_id": {
                "user_id": "env_test_user_001"
            },
            "sender_type": "user"
        },
        "content": "{\"text\":\"@Hermes 测试系统环境变量配置\"}",
        "create_time": str(int(time.time())),
        "message_type": "text"
    }
    
    message = adapter.receive_message(raw_message)
    assert message is not None, "消息解析失败"
    
    print("[OK] 收到消息:")
    print("  - 用户ID:", message.user_id)
    print("  - 内容:", message.content)
    print("  - 来源:", message.metadata.get("source"))
    
    # 模拟回复消息
    response = Message(
        id="env_response_msg_001",
        user_id=message.user_id,
        content="系统环境变量配置测试成功！",
        role="assistant",
        timestamp=int(time.time())
    )
    
    result = adapter.send_message(response)
    assert result == True, "消息发送失败"
    
    print("[OK] 回复消息发送成功")


def main():
    print("=" * 60)
    print("测试系统环境变量配置的飞书适配器")
    print("=" * 60)
    
    # 测试系统环境变量
    env_ok = test_system_env_variables()
    
    # 如果环境变量配置完整，测试适配器
    if env_ok:
        test_adapter_with_env_vars()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
