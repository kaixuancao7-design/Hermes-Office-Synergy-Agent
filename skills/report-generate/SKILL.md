# 报告生成技能 (Report Generation Skill)

## 基本信息

| 属性 | 值 |
|------|-----|
| **名称** | 报告生成 |
| **标识符** | report-generate |
| **版本** | 1.0.0 |
| **类型** | preset |
| **描述** | 自动生成各种类型的报告文档，支持周报、月报、分析报告等 |

## 触发模式

| 触发词 | 置信度 | 说明 |
|--------|--------|------|
| 生成报告 | 1.0 | 最直接的触发 |
| 写报告 | 0.9 | 同义表达 |
| 周报 | 0.95 | 周报生成 |
| 月报 | 0.95 | 月报生成 |
| 总结报告 | 0.85 | 总结报告 |

## 输入参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| title | string | 是 | 报告标题 |
| content | string | 是 | 报告内容或要点 |
| report_type | string | 否 | 报告类型（周报/月报/分析/总结） |
| format | string | 否 | 输出格式（markdown/pdf/docx） |

## 输出参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| file_path | string | 生成的报告文件路径 |
| content | string | 报告内容文本 |

## 工作流定义

```yaml
workflow:
  - id: "analyze_requirements"
    name: "分析需求"
    description: "分析报告需求和结构"
    tool: "requirement_analyze"
    parameters:
      content: "{{input.content}}"
      report_type: "{{input.report_type}}"
    output_key: "requirement_result"
    next_step: "generate_outline"
  
  - id: "generate_outline"
    name: "生成大纲"
    description: "生成报告大纲"
    tool: "outline_generate"
    parameters:
      title: "{{input.title}}"
      requirements: "{{output.requirement_result.requirements}}"
    output_key: "outline_result"
    requires_confirmation: true
    confirmation_prompt: |
      已为您生成以下报告大纲，请确认是否满意？
      
      {{output.outline_result.outline}}
      
      回复 是/确认 继续，或提出修改意见
    next_step: "generate_content"
  
  - id: "generate_content"
    name: "生成内容"
    description: "生成报告内容"
    tool: "content_generate"
    parameters:
      title: "{{input.title}}"
      outline: "{{output.outline_result.outline}}"
      content: "{{input.content}}"
    output_key: "content_result"
    next_step: "format_report"
  
  - id: "format_report"
    name: "格式化报告"
    description: "格式化报告为指定格式"
    tool: "report_format"
    parameters:
      content: "{{output.content_result.content}}"
      format: "{{input.format}}"
    output_key: "format_result"
```

## 标签

```yaml
tags:
  - 报告
  - 周报
  - 月报
  - 文档生成
```

## 工具依赖

| 工具名 | 描述 |
|--------|------|
| requirement_analyze | 需求分析工具 |
| outline_generate | 大纲生成工具 |
| content_generate | 内容生成工具 |
| report_format | 报告格式化工具 |