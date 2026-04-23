"""测试文件名编码解码功能"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.plugins.tool_executors import decode_filename


def test_decode_filename():
    """测试文件名解码功能"""
    print("=" * 60)
    print("测试文件名编码解码功能")
    print("=" * 60)
    
    test_cases = [
        # (content_disposition, expected_filename, description)
        (
            'attachment; filename="AI Agent热点文章周报_26_4_8-_4_14.docx"',
            'AI Agent热点文章周报_26_4_8-_4_14.docx',
            "普通中文文件名"
        ),
        (
            'attachment; filename*=UTF-8\'\'AI%20Agent%E7%83%AD%E7%82%B9%E6%96%87%E7%AB%A0%E5%91%A8%E6%8A%A5_26_4_8-_4_14.docx',
            'AI Agent热点文章周报_26_4_8-_4_14.docx',
            "RFC 5987 编码格式"
        ),
        (
            'attachment; filename="test.pdf"',
            'test.pdf',
            "简单英文文件名"
        ),
        (
            '',
            '',
            "空字符串"
        ),
        (
            'attachment; name="file"',
            '',
            "没有filename字段"
        ),
        (
            'attachment; filename="Document_2024年.pdf"',
            'Document_2024年.pdf',
            "包含中文年份的文件名"
        ),
    ]
    
    passed = 0
    failed = 0
    
    for i, (content_disposition, expected, description) in enumerate(test_cases):
        result = decode_filename(content_disposition)
        status = "PASS" if result == expected else "FAIL"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"\n测试用例 {i+1}: {description}")
        print(f"输入: {repr(content_disposition)[:60]}...")
        print(f"期望: {repr(expected)}")
        print(f"实际: {repr(result)}")
        print(f"状态: {status}")
    
    print("\n" + "=" * 60)
    print(f"测试结果: 通过 {passed} / {len(test_cases)}")
    
    if failed > 0:
        print(f"失败 {failed} 个测试用例")
        return False
    else:
        print("所有测试通过！")
        return True


if __name__ == "__main__":
    success = test_decode_filename()
    sys.exit(0 if success else 1)
