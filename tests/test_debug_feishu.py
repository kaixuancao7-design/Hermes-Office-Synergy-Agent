import sys
import os
import requests
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings

def test_feishu_api_connection():
    """测试飞书 API 连接"""
    print("=== 测试飞书 API 连接 ===")
    
    # 测试获取 access token
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    
    payload = {
        "app_id": settings.FEISHU_APP_ID,
        "app_secret": settings.FEISHU_APP_SECRET
    }
    
    try:
        print(f"[INFO] 测试获取飞书 access token")
        print(f"[INFO] app_id: {settings.FEISHU_APP_ID}")
        
        response = requests.post(url, json=payload)
        print(f"[INFO] 响应状态码: {response.status_code}")
        print(f"[INFO] 响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                token = result.get("tenant_access_token")
                print(f"[OK] 获取 access token 成功")
                print(f"[INFO] token: {token[:20]}...")
                return token
            else:
                print(f"[ERROR] 获取 token 失败: {result.get('msg')}")
                return None
        else:
            print(f"[ERROR] HTTP 请求失败: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"[ERROR] 请求异常: {str(e)}")
        return None

def test_send_message_to_user(token):
    """测试发送消息到飞书用户"""
    print("\n=== 测试发送消息到飞书用户 ===")
    
    if not token:
        print("[ERROR] 没有有效的 access token")
        return False
    
    # 使用测试用户 ID
    test_user_id = "u_7a9f2e4c6d8b0a1c2e3f4a5b6c7d8e9f"
    
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=user_id"
    
    payload = {
        "receive_id": test_user_id,
        "content": json.dumps({"text": "这是一条测试消息"}),
        "msg_type": "text"
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"[INFO] 发送消息到用户: {test_user_id}")
        response = requests.post(url, json=payload, headers=headers)
        print(f"[INFO] 响应状态码: {response.status_code}")
        print(f"[INFO] 响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                print("[OK] 消息发送成功")
                return True
            else:
                print(f"[ERROR] 消息发送失败: {result.get('msg')}")
                return False
        else:
            print(f"[ERROR] HTTP 请求失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] 请求异常: {str(e)}")
        return False

def test_webhook_endpoint():
    """测试 Webhook 端点"""
    print("\n=== 测试 Webhook 端点 ===")
    
    url = "http://localhost:3000/api/v1/im/webhook/feishu"
    
    # 模拟飞书消息事件
    payload = {
        "type": "event",
        "event": {
            "type": "message",
            "message": {
                "message_id": "om_test_message_id",
                "content": "{\"text\":\"@Hermes-Office-Synergy-Agent 你好，测试一下\"}",
                "chat_type": "p2p",
                "create_time": "1704067200"
            },
            "sender": {
                "sender_id": {
                    "user_id": "u_test_user_id"
                },
                "sender_type": "user"
            },
            "event_time": "1704067200"
        }
    }
    
    try:
        print(f"[INFO] 发送请求到 Webhook 端点")
        print(f"[INFO] 消息内容包含 @Hermes-Office-Synergy-Agent")
        
        response = requests.post(url, json=payload)
        print(f"[INFO] 响应状态码: {response.status_code}")
        
        try:
            print(f"[INFO] 响应内容: {response.text}")
        except:
            print(f"[INFO] 响应内容长度: {len(response.text)}")
            
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                print("[OK] Webhook 端点测试成功")
                print(f"[INFO] 响应消息: {result.get('response', '')[:100]}")
                return True
            else:
                print(f"[WARNING] Webhook 处理结果: {result.get('status')}")
                return False
        else:
            print(f"[ERROR] 请求失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] 请求异常: {str(e)}")
        return False

if __name__ == "__main__":
    print("="*50)
    print("飞书集成调试测试")
    print("="*50)
    
    # 测试1: 检查配置
    print("\n=== 检查配置 ===")
    print(f"FEISHU_APP_ID: {settings.FEISHU_APP_ID}")
    print(f"FEISHU_APP_SECRET: {'已配置' if settings.FEISHU_APP_SECRET else '未配置'}")
    
    # 测试2: 测试飞书 API 连接
    token = test_feishu_api_connection()
    
    # 测试3: 测试发送消息
    # if token:
    #     test_send_message_to_user(token)
    
    # 测试4: 测试 Webhook 端点
    test_webhook_endpoint()
