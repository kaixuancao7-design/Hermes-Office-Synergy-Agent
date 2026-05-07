# PPT生成技能 (PPT Generation Skill)

## 基本信息

| 属性 | 值 |
|------|-----|
| **名称** | PPT生成 |
| **标识符** | ppt-generation |
| **版本** | 1.0.0 |
| **类型** | preset |
| **描述** | 根据内容自动生成专业PPT演示文稿，支持模板匹配、大纲生成、内容创作和质量检查 |

## 触发模式

| 触发词 | 置信度 | 说明 |
|--------|--------|------|
| 生成PPT | 1.0 | 最直接的触发 |
| 制作PPT | 0.95 | 同义表达 |
| 做个PPT | 0.85 | 口语化表达 |
| 生成演示稿 | 0.8 | 同义词触发 |
| 生成幻灯片 | 0.8 | 同义词触发 |

## 输入参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| title | string | 是 | PPT标题 |
| content | string | 是 | 内容文本或文档内容 |
| style | string | 否 | 风格提示（商务/学术/创意/极简/麦肯锡） |

## 输出参数

| 参数名 | 类型 | 描述 |
|--------|------|------|
| file_path | string | 生成的PPT文件路径 |
| slides_count | integer | 幻灯片数量 |
| quality_score | number | 质量分数 |

## 工作流定义

```yaml
workflow:
  - id: "template_match"
    name: "模板匹配"
    description: "根据内容匹配合适的PPT模板"
    tool: "ppt_template_match"
    parameters:
      content: "{{input.content}}"
      style_hint: "{{input.style}}"
    output_key: "template_result"
    next_step: "spec_lock"
  
  - id: "spec_lock"
    name: "规格锁定"
    description: "锁定PPT的设计规格"
    tool: "ppt_spec_lock"
    parameters:
      template_id: "{{output.template_result.templates.0.id}}"
    output_key: "spec_result"
    next_step: "generate_outline"
  
  - id: "generate_outline"
    name: "生成大纲"
    description: "根据内容生成PPT大纲"
    tool: "ppt_generate_outline"
    parameters:
      title: "{{input.title}}"
      content: "{{input.content}}"
      style_config: "{{output.spec_result.spec_lock.design_spec}}"
    output_key: "outline_result"
    requires_confirmation: true
    confirmation_prompt: |
      已为您生成以下PPT大纲，请确认是否满意？
      
      {{output.outline_result.outline}}
      
      回复 是/确认 继续生成，或 重新生成/修改+内容 进行调整
    next_step: "generate_content"
  
  - id: "generate_content"
    name: "生成内容"
    description: "根据大纲生成幻灯片内容"
    tool: "ppt_generate_content"
    parameters:
      outline: "{{output.outline_result.outline}}"
      template_id: "{{output.template_result.templates.0.id}}"
      style_config: "{{output.spec_result.spec_lock.design_spec}}"
    output_key: "content_result"
    next_step: "generate_file"
  
  - id: "generate_file"
    name: "生成文件"
    description: "生成PPTX文件"
    tool: "ppt_generate_file"
    parameters:
      title: "{{input.title}}"
      slides: "{{output.content_result.slides}}"
    output_key: "file_result"
    next_step: "quality_check"
  
  - id: "quality_check"
    name: "质量检查"
    description: "检查PPT质量"
    tool: "ppt_quality_check"
    parameters:
      file_path: "{{output.file_result.file_path}}"
    output_key: "quality_result"
    next_step: "send_file"
  
  - id: "send_file"
    name: "发送文件"
    description: "发送PPT到飞书"
    tool: "ppt_feishu_send"
    parameters:
      file_path: "{{output.file_result.file_path}}"
      user_id: "{{context.user_id}}"
    output_key: "send_result"
```

## 标签

```yaml
tags:
  - 演示文稿
  - PPT
  - 汇报
  - 演示
  - 幻灯片
```

## 执行流程

```
用户输入 → 模板匹配 → 规格锁定 → 生成大纲 → [用户确认] → 生成内容 → 生成文件 → 质量检查 → 发送文件
```

## 工具依赖

| 工具名 | 描述 |
|--------|------|
| ppt_template_match | PPT模板匹配工具 |
| ppt_spec_lock | PPT规格锁定工具 |
| ppt_generate_outline | PPT大纲生成工具 |
| ppt_generate_content | PPT内容生成工具 |
| ppt_generate_file | PPT文件生成工具 |
| ppt_quality_check | PPT质量检查工具 |
| ppt_feishu_send | 飞书文件发送工具 |

## 错误处理

| 错误类型 | 处理策略 |
|----------|----------|
| 模板匹配失败 | 使用默认模板继续执行 |
| 大纲生成失败 | 提示用户并终止流程 |
| 文件生成失败 | 重试一次，仍失败则通知用户 |
| 质量检查未通过 | 提示用户问题并提供修改建议 |

## 权限要求

| 角色 | 权限 |
|------|------|
| user | 可执行 |
| developer | 可执行、可修改 |
| admin | 全部权限 |

## 扩展说明

### 参数模板语法

支持以下模板变量：

- `{{input.xxx}}` - 输入参数
- `{{output.step_id.xxx}}` - 上一步输出
- `{{context.xxx}}` - 上下文信息

### 用户确认机制

当步骤设置 `requires_confirmation: true` 时：
1. 执行工具获取结果
2. 暂停执行并等待用户确认
3. 用户回复"是"或"确认"继续执行
4. 用户回复"重新生成"或"修改"则重新执行当前步骤

### 状态管理

技能执行状态：
- `pending` - 等待执行
- `running` - 执行中
- `paused` - 等待用户确认
- `completed` - 执行完成
- `failed` - 执行失败