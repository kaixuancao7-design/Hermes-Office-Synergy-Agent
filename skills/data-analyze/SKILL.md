# 数据分析技能 (Data Analysis Skill)

## 基本信息

| 属性 | 值 |
|------|-----|
| **名称** | 数据分析 |
| **标识符** | data-analyze |
| **版本** | 1.0.0 |
| **类型** | preset |
| **描述** | 对数据进行分析处理，支持数据导入、清洗、分析和可视化 |

## 触发模式

| 触发词 | 置信度 | 说明 |
|--------|--------|------|
| 数据分析 | 1.0 | 最直接的触发 |
| 分析数据 | 0.9 | 同义表达 |
| 数据报告 | 0.85 | 生成数据报告 |
| 数据可视化 | 0.8 | 数据可视化需求 |
| 统计分析 | 0.75 | 统计分析需求 |

## 输入参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| data_source | string | 是 | 数据源路径或查询语句 |
| analysis_type | string | 否 | 分析类型（描述性/相关性/预测性） |
| output_format | string | 否 | 输出格式（图表/报告/表格） |

## 输出参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| analysis_result | object | 分析结果数据 |
| visualization | string | 可视化图表路径或描述 |
| report | string | 分析报告文本 |

## 工作流定义

```yaml
workflow:
  - id: "load_data"
    name: "加载数据"
    description: "从数据源加载数据"
    tool: "data_load"
    parameters:
      source: "{{input.data_source}}"
    output_key: "data_result"
    next_step: "clean_data"
  
  - id: "clean_data"
    name: "数据清洗"
    description: "清洗和预处理数据"
    tool: "data_clean"
    parameters:
      data: "{{output.data_result.data}}"
    output_key: "clean_result"
    next_step: "analyze_data"
  
  - id: "analyze_data"
    name: "数据分析"
    description: "执行数据分析"
    tool: "data_analyze"
    parameters:
      data: "{{output.clean_result.clean_data}}"
      analysis_type: "{{input.analysis_type}}"
    output_key: "analyze_result"
    next_step: "visualize"
  
  - id: "visualize"
    name: "数据可视化"
    description: "生成可视化图表"
    tool: "data_visualize"
    parameters:
      data: "{{output.analyze_result.result}}"
      format: "{{input.output_format}}"
    output_key: "visualize_result"
    next_step: "generate_report"
  
  - id: "generate_report"
    name: "生成报告"
    description: "生成分析报告"
    tool: "report_generate"
    parameters:
      analysis: "{{output.analyze_result.result}}"
      visualization: "{{output.visualize_result.chart}}"
    output_key: "report_result"
```

## 标签

```yaml
tags:
  - 数据分析
  - 数据可视化
  - 统计分析
  - 数据报告
```

## 工具依赖

| 工具名 | 描述 |
|--------|------|
| data_load | 数据加载工具 |
| data_clean | 数据清洗工具 |
| data_analyze | 数据分析工具 |
| data_visualize | 数据可视化工具 |
| report_generate | 报告生成工具 |