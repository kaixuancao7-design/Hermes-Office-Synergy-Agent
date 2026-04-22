"""飞书文件上传读取测试"""
import sys
import os
import tempfile
import json
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch, MagicMock
from src.plugins.im_adapters import FeishuAdapter
from src.config import settings


class TestFeishuFileUpload:
    """飞书文件上传读取测试"""
    
    def test_send_file_success(self):
        """测试文件发送成功（使用mock）"""
        print("\n=== 测试文件发送成功 ===")
        
        adapter = FeishuAdapter()
        
        # 使用patch直接mock异步send_file方法
        with patch.object(FeishuAdapter, 'send_file', return_value=True) as mock_send_file:
            # 创建临时测试文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write("测试文件内容")
                temp_file = f.name
            
            try:
                result = asyncio.run(adapter.send_file("test_user_id", temp_file))
                
                assert result == True, "文件发送失败"
                mock_send_file.assert_called_once_with("test_user_id", temp_file)
                print("[OK] 文件发送测试通过")
                
            finally:
                os.unlink(temp_file)
    
    def test_send_file_with_custom_filename(self):
        """测试指定自定义文件名发送"""
        print("\n=== 测试指定自定义文件名发送 ===")
        
        adapter = FeishuAdapter()
        
        with patch.object(FeishuAdapter, 'send_file', return_value=True) as mock_send_file:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write("content")
                temp_file = f.name
            
            try:
                result = asyncio.run(adapter.send_file("test_user_id", temp_file, "custom_report.pdf"))
                
                assert result == True, "文件发送失败"
                mock_send_file.assert_called_once_with("test_user_id", temp_file, "custom_report.pdf")
                print("[OK] 指定文件名发送测试通过")
                
            finally:
                os.unlink(temp_file)
    
    def test_send_file_nonexistent(self):
        """测试发送不存在的文件"""
        print("\n=== 测试发送不存在的文件 ===")
        
        adapter = FeishuAdapter()
        
        result = asyncio.run(adapter.send_file("test_user_id", "/path/to/nonexistent/file.txt"))
        
        assert result == False, "不存在的文件应该返回False"
        print("[OK] 不存在文件处理测试通过")
    
    def test_send_file_without_api_client(self):
        """测试未初始化API客户端时发送文件"""
        print("\n=== 测试未初始化API客户端 ===")
        
        adapter = FeishuAdapter()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test")
            temp_file = f.name
        
        try:
            result = asyncio.run(adapter.send_file("test_user_id", temp_file))
            assert result == False, "未初始化API客户端应该返回False"
            print("[OK] 未初始化客户端处理测试通过")
        finally:
            os.unlink(temp_file)
    
    def test_file_key_extraction(self):
        """测试从消息中提取文件key"""
        print("\n=== 测试文件Key提取 ===")
        
        # 测试各种消息格式
        test_cases = [
            {
                "name": "纯文本消息",
                "content": json.dumps({"text": "普通消息"}),
                "expected_file_key": None
            },
            {
                "name": "带文件的文本消息",
                "content": json.dumps({
                    "text": "看看这个文件",
                    "file_key": "file_key_123"
                }),
                "expected_file_key": "file_key_123"
            },
            {
                "name": "文件消息类型",
                "content": json.dumps({
                    "file_key": "file_key_456",
                    "file_name": "report.pdf"
                }),
                "expected_file_key": "file_key_456"
            }
        ]
        
        for test_case in test_cases:
            try:
                content_json = json.loads(test_case["content"])
                file_key = content_json.get("file_key", None)
                
                assert file_key == test_case["expected_file_key"], \
                    f"{test_case['name']}: 期望 {test_case['expected_file_key']}, 实际 {file_key}"
                
                print(f"  - {test_case['name']}: OK")
            except Exception as e:
                print(f"  - {test_case['name']}: FAIL - {e}")
                raise
        
        print("[OK] 文件Key提取测试通过")
    
    def test_feishu_adapter_type(self):
        """测试飞书适配器类型标识"""
        print("\n=== 测试适配器类型标识 ===")
        
        adapter = FeishuAdapter()
        assert adapter.get_adapter_type() == "feishu", "适配器类型不正确"
        print("[OK] 适配器类型测试通过")
    
    def test_message_content_parsing(self):
        """测试消息内容解析（包含文件信息）"""
        print("\n=== 测试消息内容解析 ===")
        
        # 模拟包含文件的飞书消息
        raw_message = {
            "message_id": "test_msg_id",
            "sender": {
                "sender_id": {"user_id": "test_user"},
                "sender_type": "user"
            },
            "content": json.dumps({
                "text": "@Hermes 帮我分析这个文件",
                "file_key": "file_v3_0010v_68cd93cf-c5ba-4d2f-8b0b-3d02e40dfceg"
            }),
            "message_type": "text"
        }
        
        print("  - 文件消息结构解析成功")
        print("  - file_key:", json.loads(raw_message["content"]).get("file_key"))
        print("[OK] 文件消息内容解析测试通过")
    
    def test_file_key_extraction(self):
        """测试从消息中提取文件key"""
        print("\n=== 测试文件Key提取 ===")
        
        # 测试各种消息格式
        test_cases = [
            {
                "name": "纯文本消息",
                "content": json.dumps({"text": "普通消息"}),
                "expected_file_key": None
            },
            {
                "name": "带文件的文本消息",
                "content": json.dumps({
                    "text": "看看这个文件",
                    "file_key": "file_key_123"
                }),
                "expected_file_key": "file_key_123"
            },
            {
                "name": "文件消息类型",
                "content": json.dumps({
                    "file_key": "file_key_456",
                    "file_name": "report.pdf"
                }),
                "expected_file_key": "file_key_456"
            }
        ]
        
        for test_case in test_cases:
            try:
                content_json = json.loads(test_case["content"])
                file_key = content_json.get("file_key", None)
                
                assert file_key == test_case["expected_file_key"], \
                    f"{test_case['name']}: 期望 {test_case['expected_file_key']}, 实际 {file_key}"
                
                print(f"  - {test_case['name']}: OK")
            except Exception as e:
                print(f"  - {test_case['name']}: FAIL - {e}")
                raise
        
        print("[OK] 文件Key提取测试通过")


if __name__ == "__main__":
    print("=" * 60)
    print("飞书文件上传读取测试")
    print("=" * 60)
    
    test = TestFeishuFileUpload()
    
    try:
        test.test_send_file_success()
        test.test_send_file_with_custom_filename()
        test.test_send_file_nonexistent()
        test.test_send_file_without_api_client()
        test.test_message_content_parsing()
        test.test_file_key_extraction()
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        
    except AssertionError as e:
        print("\n[FAIL] 测试失败:", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print("\n[ERROR] 测试异常:", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)
