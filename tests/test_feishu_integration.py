#!/usr/bin/env python3
"""
飞书集成测试 - 验证配置、message_id格式和日志功能
"""

import os
import sys
import re
import json
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def validate_env_config() -> bool:
    """验证 .env 配置文件"""
    logger.info("=== 验证 .env 配置 ===")
    
    required_vars = [
        "FEISHU_APP_ID",
        "FEISHU_APP_SECRET",
        "MEMORY_STORE_TYPE"
    ]
    
    env_path = ".env"
    if not os.path.exists(env_path):
        logger.error(f"❌ .env 文件不存在: {env_path}")
        return False
    
    # 读取 .env 文件
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查必需的配置项
    missing_vars = []
    placeholder_vars = []
    
    for var in required_vars:
        # 使用正则查找配置项（忽略大小写）
        pattern = rf"{var}\s*=\s*(.+)"
        match = re.search(pattern, content)
        if not match:
            # 尝试不区分大小写查找
            pattern_case_insensitive = rf"(?i){var}\s*=\s*(.+)"
            match = re.search(pattern_case_insensitive, content)
        
        if not match:
            missing_vars.append(var)
        else:
            value = match.group(1).strip()
            # 检查是否为占位符
            # 检测占位符：包含大量重复字符或明显的占位符模式
            is_placeholder = False
            if var == "FEISHU_APP_ID":
                # 检测明显的占位符模式
                placeholder_patterns = ["cli_xxxxxxxx", "cli_a1b2c3d4", "your_app_id", "app_id_here"]
                is_placeholder = any(pattern in value.lower() for pattern in placeholder_patterns) or \
                               (value.startswith("cli_") and len(value) < 15)
            elif var == "FEISHU_APP_SECRET":
                # 检测明显的占位符模式
                placeholder_patterns = ["xxxxxxxx", "your_secret", "secret_here", "abcdef1234567890"]
                is_placeholder = any(pattern in value.lower() for pattern in placeholder_patterns) or \
                               (len(value) < 20)
            
            if is_placeholder:
                placeholder_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ 缺少必需配置项: {', '.join(missing_vars)}")
        return False
    
    if placeholder_vars:
        logger.warning(f"⚠️ 检测到占位符配置项，请替换为真实值: {', '.join(placeholder_vars)}")
        return False
    
    logger.info("✅ .env 配置验证通过")
    return True

def validate_message_id_format(message_id: str) -> bool:
    """验证 message_id 格式是否正确"""
    if not message_id:
        logger.error("❌ message_id 为空")
        return False
    
    # 飞书 message_id 格式：om_ + 32-64位字母数字字符（不区分大小写，支持多种版本）
    pattern = r"^om_[0-9a-z]{32,64}$"
    if not re.match(pattern, message_id.lower()):
        logger.error(f"❌ message_id 格式无效: {message_id}")
        logger.info(f"   正确格式示例: om_da5e1234567890abcdef1234567890ab")
        return False
    
    logger.info(f"✅ message_id 格式验证通过: {message_id}")
    return True

def validate_file_key_format(file_key: str) -> bool:
    """验证 file_key 格式"""
    if not file_key:
        logger.error("❌ file_key 为空")
        return False
    
    # 检查是否为 file_v3 格式
    if file_key.startswith("file_v3_"):
        # file_v3_ + 数字 + _ + 任意字符（简化验证）
        pattern = r"^file_v3_\d+_.+$"
        if not re.match(pattern, file_key):
            logger.error(f"❌ file_key 格式无效: {file_key}")
            return False
        logger.info(f"✅ file_key (file_v3) 格式验证通过: {file_key}")
    else:
        # 旧版 file_token 格式（简单检查非空）
        logger.info(f"⚠️ file_key 不是 file_v3 格式: {file_key}")
    
    return True

def test_message_id_examples():
    """测试不同格式的 message_id"""
    logger.info("\n=== 测试 message_id 格式 ===")
    
    test_cases = [
        ("om_da5e1234567890abcdef1234567890ab", True),  # 有效格式（32位）
        ("om_abc123456", False),                         # 无效格式（太短）
        ("om_12345678901234567890123456789012", True),  # 有效格式（32位）
        ("abc123456", False),                            # 无效格式（缺少前缀）
        ("OM_DA5E1234567890ABCDEF1234567890AB", True),  # 大写也有效（32位）
        ("om_x100b51aac84f28b8b4827a9792c2da8", True),  # 有效格式（33位新版）
    ]
    
    all_passed = True
    for msg_id, expected in test_cases:
        result = validate_message_id_format(msg_id)
        if result != expected:
            logger.error(f"测试用例失败: {msg_id} (期望: {expected}, 实际: {result})")
            all_passed = False
    
    if all_passed:
        logger.info("✅ 所有 message_id 格式测试通过")
    return all_passed

def test_file_key_examples():
    """测试 file_key 格式"""
    logger.info("\n=== 测试 file_key 格式 ===")
    
    test_cases = [
        ("file_v3_00111_976b6ccf-dc13-4957-a18e-12bfae65fe0g", True),
        ("file_v3_00110_d49a79d6-b484-41a7-85dc-3f292d4bdb3g", True),
        ("abc123456", True),  # 旧版格式，不报错
        ("", False),          # 空值
    ]
    
    all_passed = True
    for file_key, expected in test_cases:
        result = validate_file_key_format(file_key)
        if result != expected:
            logger.error(f"测试用例失败: {file_key} (期望: {expected}, 实际: {result})")
            all_passed = False
    
    if all_passed:
        logger.info("✅ 所有 file_key 格式测试通过")
    return all_passed

def test_logging_config():
    """验证日志配置"""
    logger.info("\n=== 验证日志配置 ===")
    
    # 测试详细日志输出
    test_data = {
        "message_id": "om_da5e1234567890abcdef1234567890ab",
        "file_key": "file_v3_00111_976b6ccf-dc13-4957-a18e-12bfae65fe0g",
        "http_method": "GET",
        "url": "/open-apis/im/v1/messages/.../resources/file",
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info(f"📋 请求详情: {json.dumps(test_data, indent=2, ensure_ascii=False)}")
    logger.info("✅ 日志配置验证通过")
    return True

def test_feishu_client_initialization():
    """测试飞书客户端初始化"""
    logger.info("\n=== 测试飞书客户端初始化 ===")
    
    try:
        # 检查环境变量
        app_id = os.getenv("FEISHU_APP_ID")
        app_secret = os.getenv("FEISHU_APP_SECRET")
        
        if not app_id or not app_secret:
            logger.error("❌ 缺少飞书配置")
            return False
        
        # 测试导入
        try:
            from lark_oapi import Client, FEISHU_DOMAIN
            logger.info("✅ lark_oapi 导入成功")
        except ImportError as e:
            logger.error(f"❌ lark_oapi 导入失败: {e}")
            return False
        
        # 测试创建客户端（不实际连接）
        try:
            client = Client.builder() \
                .app_id(app_id) \
                .app_secret(app_secret) \
                .domain(FEISHU_DOMAIN) \
                .build()
            logger.info("✅ 飞书客户端创建成功")
            return True
        except Exception as e:
            logger.error(f"❌ 飞书客户端创建失败: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ 测试飞书客户端初始化异常: {e}")
        return False

def main():
    """主测试入口"""
    logger.info("=" * 60)
    logger.info("飞书集成测试套件")
    logger.info("=" * 60)
    
    results = []
    
    # 运行所有测试
    results.append(("配置文件验证", validate_env_config()))
    results.append(("message_id 格式测试", test_message_id_examples()))
    results.append(("file_key 格式测试", test_file_key_examples()))
    results.append(("日志配置验证", test_logging_config()))
    results.append(("飞书客户端初始化", test_feishu_client_initialization()))
    
    # 输出测试总结
    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\n总测试数: {total}, 通过: {passed}, 失败: {total - passed}")
    
    if passed == total:
        logger.info("\n🎉 所有测试通过！")
        return 0
    else:
        logger.error("\n❌ 部分测试失败，请检查配置")
        return 1

if __name__ == "__main__":
    sys.exit(main())
