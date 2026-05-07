# 会议纪要技能 (Meeting Minutes Skill)

## 基本信息

| 属性 | 值 |
|------|-----|
| **名称** | 会议纪要 |
| **标识符** | meeting-minutes |
| **版本** | 1.0.0 |
| **类型** | preset |
| **描述** | 自动生成会议纪要，支持要点提取、决策记录和行动项跟踪 |

## 触发模式

| 触发词 | 置信度 | 说明 |
|--------|--------|------|
| 会议纪要 | 1.0 | 最直接的触发 |
| 会议记录 | 0.9 | 同义表达 |
| 记录会议 | 0.85 | 同义表达 |
| meeting minutes | 0.8 | 英文触发 |
| 纪要 | 0.95 | 简称触发 |

## 输入参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| content | string | 是 | 会议内容或录音转写文本 |
| participants | string | 否 | 参会人员列表 |
| date | string | 否 | 会议日期 |

## 输出参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| minutes | string | 会议纪要文本 |
| action_items | list | 行动项列表 |
| decisions | list | 决策列表 |

## 工作流定义

```yaml
workflow:
  - id: "extract_key_points"
    name: "提取要点"
    description: "从会议内容中提取要点"
    tool: "key_points_extract"
    parameters:
      content: "{{input.content}}"
    output_key: "points_result"
    next_step: "identify_decisions"
  
  - id: "identify_decisions"
    name: "识别决策"
    description: "识别会议中的决策"
    tool: "decision_identify"
    parameters:
      content: "{{input.content}}"
    output_key: "decision_result"
    next_step: "extract_actions"
  
  - id: "extract_actions"
    name: "提取行动项"
    description: "提取会议中的行动项"
    tool: "action_extract"
    parameters:
      content: "{{input.content}}"
    output_key: "action_result"
    next_step: "generate_minutes"
  
  - id: "generate_minutes"
    name: "生成纪要"
    description: "生成完整的会议纪要"
    tool: "minutes_generate"
    parameters:
      key_points: "{{output.points_result.points}}"
      decisions: "{{output.decision_result.decisions}}"
      actions: "{{output.action_result.actions}}"
      participants: "{{input.participants}}"
      date: "{{input.date}}"
    output_key: "minutes_result"
```

## 标签

```yaml
tags:
  - 会议
  - 纪要
  - 记录
  - 行动项
```

## 工具依赖

| 工具名 | 描述 |
|--------|------|
| key_points_extract | 要点提取工具 |
| decision_identify | 决策识别工具 |
| action_extract | 行动项提取工具 |
| minutes_generate | 纪要生成工具 |