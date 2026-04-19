import sys
import os
import requests
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_webhook_flow():
    """测试完整的 Webhook 流程"""
    print("=== 测试飞书 Webhook 完整流程 ===")
    
    # 模拟飞书消息事件
    webhook_payload = {
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
                    "user_id": "12f95277"  # 使用有效的测试用户ID
                },
                "sender_type": "user"
            },
            "event_time": "1704067200"
        }
    }
    
    # 发送到本地 Webhook 端点
    url = "http://localhost:3000/api/v1/im/webhook/feishu"
    
    try:
        print(f"[INFO] 发送请求到: {url}")
        print(f"[INFO] 消息内容: {webhook_payload['event']['message']['content']}")
        
        response = requests.post(url, json=webhook_payload)
        
        print(f"[INFO] 响应状态码: {response.status_code}")
        print(f"[INFO] 响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                print("[OK] Webhook 流程测试成功！")
                print(f"[INFO] 响应消息: {result.get('response')}")
            else:
                print(f"[WARNING] Webhook 处理结果: {result.get('status')}")
        else:
            print(f"[ERROR] 请求失败: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 网络请求失败: {str(e)}")

if __name__ == "__main__":
    test_webhook_flow()
