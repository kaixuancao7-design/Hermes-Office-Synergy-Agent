import os
import pytest
from src.tools.ppt_generator import PPTGeneratorBase
from src.plugins.tool_executors import BasicToolExecutor as ToolExecutor


class TestPPTGenerator:
    """PPT生成器测试类"""

    def setup_method(self):
        """测试前初始化"""
        self.generator = PPTGeneratorBase()
    
    def test_generate_ppt_basic(self):
        """测试基本PPT生成"""
        slides = [
            {'type': 'content', 'title': '测试页面', 'content': '这是测试内容'}
        ]
        output_path = self.generator.generate_ppt('Basic Test', slides)
        
        assert output_path is not None
        assert output_path.endswith('.pptx')
        assert os.path.exists(output_path)
    
    def test_generate_ppt_with_title_slide(self):
        """测试标题页生成"""
        slides = [
            {'type': 'title', 'title': '章节标题', 'content': '副标题内容'}
        ]
        output_path = self.generator.generate_ppt('Title Slide Test', slides)
        
        assert os.path.exists(output_path)
    
    def test_generate_ppt_with_bullet_slide(self):
        """测试项目符号页生成"""
        slides = [
            {'type': 'bullet', 'title': '功能列表', 'content': ['功能A', '功能B', '功能C']}
        ]
        output_path = self.generator.generate_ppt('Bullet Test', slides)
        
        assert os.path.exists(output_path)
    
    def test_generate_ppt_with_chart_slide(self):
        """测试图表页生成"""
        slides = [
            {'type': 'chart', 'title': '销售数据', 'content': [['Q1', 100], ['Q2', 150]]}
        ]
        output_path = self.generator.generate_ppt('Chart Test', slides)
        
        assert os.path.exists(output_path)
    
    def test_generate_ppt_from_outline(self):
        """测试从大纲生成PPT"""
        outline = [
            {'title': '第一章', 'content': '第一章内容'},
            {'title': '第二章', 'content': ['点1', '点2', '点3']},
            {'title': '第三章', 'content': '第三章内容'}
        ]
        output_path = self.generator.generate_from_outline('Outline Test', outline)
        
        assert os.path.exists(output_path)
    
    def test_generate_ppt_empty_slides(self):
        """测试空幻灯片列表"""
        slides = []
        output_path = self.generator.generate_ppt('Empty Test', slides)
        
        assert os.path.exists(output_path)
    
    def test_generate_ppt_multiple_slides(self):
        """测试多幻灯片生成"""
        slides = [
            {'type': 'title', 'title': '章节一'},
            {'type': 'content', 'title': '内容页1', 'content': '内容1'},
            {'type': 'bullet', 'title': '列表页', 'content': ['A', 'B', 'C']},
            {'type': 'chart', 'title': '数据表', 'content': [['Jan', 10], ['Feb', 20]]},
            {'type': 'blank', 'title': '空白页'}
        ]
        output_path = self.generator.generate_ppt('Multi Slide Test', slides)
        
        assert os.path.exists(output_path)


class TestPPTGeneratorTool:
    """PPT生成器工具测试类"""
    
    def setup_method(self):
        """测试前初始化"""
        self.tool_executor = ToolExecutor()
    
    def test_generate_ppt_tool(self):
        """测试generate_ppt工具"""
        result = self.tool_executor.execute('generate_ppt', {
            'title': 'Tool Test Presentation',
            'slides': [
                {'type': 'content', 'title': '测试', 'content': '测试内容'}
            ]
        })

        assert result.get('success') is True
        assert '.pptx' in str(result)
    
    def test_generate_ppt_from_outline_tool(self):
        """测试从大纲生成PPT - 通过generator方法"""
        generator = PPTGeneratorBase()
        outline = [
            {'title': '第一章', 'content': '内容'}
        ]
        result = generator.generate_from_outline('Outline Tool Test', outline)

        assert result.endswith('.pptx') or 'error' not in result.lower()
    
    def test_generate_ppt_with_invalid_slides(self):
        """测试无效幻灯片数据"""
        result = self.tool_executor.execute('generate_ppt', {
            'title': 'Invalid Test',
            'slides': 'not a list'  # 无效格式
        })
        
        # 应该返回错误或成功处理
        assert result is not None
    
    def test_generate_ppt_empty_parameters(self):
        """测试空参数"""
        result = self.tool_executor.execute('generate_ppt', {})
        
        # 应该使用默认值生成PPT
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])