import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from src.config import settings
from src.gateway.im_adapter import IMAdapter, IMAdapterConfig, im_adapter_manager
from src.types import Message


def load_env_config():
    """加载环境配置"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print("[INFO] 已加载 .env 配置文件")
        return True
    else:
        print("[WARN] 未找到 .env 文件，请先创建配置")
        return False


def test_feishu_with_env_config():
    """使用环境配置测试飞书适配器"""
    print("\n=== 使用环境配置测试飞书适配器 ===")
    
    # 检查配置是否存在
    if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
        print("[WARN] 飞书配置未完整设置")
        print("  - FEISHU_APP_ID:", settings.FEISHU_APP_ID or "未配置")
        print("  - FEISHU_APP_SECRET:", "已配置" if settings.FEISHU_APP_SECRET else "未配置")
        print("  - FEISHU_BOT_NAME:", settings.FEISHU_BOT_NAME)
        return False
    
    print("[INFO] 飞书配置信息:")
    print("  - FEISHU_APP_ID:", settings.FEISHU_APP_ID)
    print("  - FEISHU_APP_SECRET:", "***" if settings.FEISHU_APP_SECRET else "未配置")
    print("  - FEISHU_BOT_NAME:", settings.FEISHU_BOT_NAME)
    
    # 使用环境配置创建适配器
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
    
    assert adapter is not None, "飞书适配器注册失败"
    assert adapter.enabled == True, "适配器应启用"
    assert adapter.config.config["app_id"] == settings.FEISHU_APP_ID, "配置不正确"
    
    print("[OK] 使用环境配置注册飞书适配器成功")
    return True


def test_message_flow():
    """测试完整消息流程"""
    print("\n=== 测试消息流程 ===")
    
    adapter = im_adapter_manager.get_adapter("feishu")
    if not adapter or not adapter.enabled:
        print("[SKIP] 适配器未启用，跳过消息流程测试")
        return
    
    # 模拟收到飞书消息
    raw_message = {
        "message_id": "test_msg_001",
        "sender": {
            "sender_id": {
                "user_id": "test_user_001"
            },
            "sender_type": "user"
        },
        "content": "{\"text\":\"@Hermes 帮我生成本周周报\"}",
        "create_time": str(int(time.time())),
        "message_type": "text"
    }
    
    message = adapter.receive_message(raw_message)
    assert message is not None, "消息解析失败"
    
    print("[OK] 收到消息:")
    print("  - 用户ID:", message.user_id)
    print("  - 内容:", message.content)
    
    # 模拟回复消息
    response = Message(
        id="response_msg_001",
        user_id=message.user_id,
        content="好的，我来帮您生成本周周报！",
        role="assistant",
        timestamp=int(time.time())
    )
    
    result = adapter.send_message(response)
    assert result == True, "消息发送失败"
    
    print("[OK] 回复消息发送成功")


def main():
    print("=" * 60)
    print("使用 .env 配置测试飞书适配器")
    print("=" * 60)
    
    # 加载环境配置
    load_env_config()
    
    # 使用环境配置测试
    config_ok = test_feishu_with_env_config()
    
    # 如果配置完整，测试消息流程
    if config_ok:
        test_message_flow()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
