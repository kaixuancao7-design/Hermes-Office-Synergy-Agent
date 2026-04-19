import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from src.config import settings


def test_feishu_api_connection():
    """测试飞书 API 连接"""
    print("=== 测试飞书 API 连接 ===")
    
    # 检查配置
    if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
        print("[ERROR] 飞书配置未完整设置")
        print("  - FEISHU_APP_ID:", settings.FEISHU_APP_ID or "未配置")
        print("  - FEISHU_APP_SECRET:", "已配置" if settings.FEISHU_APP_SECRET else "未配置")
        return False
    
    print("[INFO] 飞书配置信息:")
    print("  - FEISHU_APP_ID:", settings.FEISHU_APP_ID)
    print("  - FEISHU_APP_SECRET:", "***")
    
    # 尝试获取飞书访问令牌
    try:
        print("\n[INFO] 正在获取飞书访问令牌...")
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": settings.FEISHU_APP_ID,
            "app_secret": settings.FEISHU_APP_SECRET
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if result.get("code") == 0:
            access_token = result.get("tenant_access_token")
            expires_in = result.get("expires_in")
            
            print("[OK] 飞书 API 连接成功！")
            print("  - 访问令牌获取成功")
            print("  - 令牌有效期:", expires_in, "秒")
            print("  - 令牌类型: tenant_access_token")
            
            # 测试调用飞书 API
            test_feishu_api(access_token)
            return True
        else:
            print(f"[ERROR] 飞书 API 调用失败: {result.get('msg')}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 飞书 API 连接失败: {e}")
        return False


def test_feishu_api(access_token):
    """测试飞书 API 调用"""
    print("\n=== 测试飞书 API 调用 ===")
    
    # 获取当前用户信息
    try:
        url = "https://open.feishu.cn/open-apis/contact/v3/users/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        if result.get("code") == 0:
            user_info = result.get("data", {}).get("user", {})
            print("[OK] 获取用户信息成功")
            print("  - 用户ID:", user_info.get("user_id"))
            print("  - 姓名:", user_info.get("name"))
            print("  - 邮箱:", user_info.get("email"))
        else:
            print(f"[WARN] 获取用户信息失败: {result.get('msg')}")
            
    except requests.exceptions.RequestException as e:
        print(f"[WARN] 测试 API 调用失败: {e}")


def main():
    print("=" * 60)
    print("飞书 API 连接验证")
    print("=" * 60)
    
    success = test_feishu_api_connection()
    
    print("\n" + "=" * 60)
    if success:
        print("✓ 飞书连接验证成功！")
    else:
        print("✗ 飞书连接验证失败，请检查配置")
    print("=" * 60)


if __name__ == "__main__":
    main()
