import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.plugins.tool_executors import FeishuFileReadTool

def test_pdf_parsing():
    """测试PDF解析功能"""
    tool = FeishuFileReadTool()
    
    # 测试1：解析一个简单的PDF文件（空文件名）
    test_pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
199
%%EOF
"""
    
    print("=" * 50)
    print("测试1 - 空文件名解析")
    print("=" * 50)
    result = tool._parse_file_content(test_pdf_content, "")
    print(f"结果类型: {type(result)}")
    print(f"结果长度: {len(result) if result else 0}")
    print(f"结果内容: {result[:300] if result else 'None'}")
    
    print("\n" + "=" * 50)
    print("测试2 - PDF文件名解析")
    print("=" * 50)
    try:
        result = tool._parse_file_content(test_pdf_content, "test.pdf")
        print(f"结果类型: {type(result)}")
        print(f"结果长度: {len(result) if result else 0}")
        print(f"结果内容: {result[:300] if result else 'None'}")
    except Exception as e:
        print(f"异常: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 50)
    print("测试3 - 文本文件解析")
    print("=" * 50)
    text_content = b"Hello World! This is a test file."
    result = tool._parse_file_content(text_content, "test.txt")
    print(f"结果类型: {type(result)}")
    print(f"结果内容: {result}")
    
    print("\n" + "=" * 50)
    print("测试4 - 模拟真实PDF内容")
    print("=" * 50)
    # 创建一个包含内容的简单PDF
    real_pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 24 Tf
100 700 Td
(Hello World from PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000180 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
265
%%EOF
"""
    try:
        result = tool._parse_file_content(real_pdf_content, "test_real.pdf")
        print(f"结果类型: {type(result)}")
        print(f"结果长度: {len(result) if result else 0}")
        print(f"结果内容: {result[:500] if result else 'None'}")
    except Exception as e:
        print(f"异常: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_pdf_parsing()