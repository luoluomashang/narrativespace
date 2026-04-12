---
name: benchmark-lite
metadata:
  version: 11.0.0
  parent: narrativespace-lite
  step: benchmark-lite
  required: true
---

# Benchmark Lite

## 职责
- 尽量按原版 style_notes/style_report 契约完成对标分析
- 输出词汇、句式、标点、叙事视角、情节模式、角色原型等完整分析
- 输出 AI 套话黑名单与小步续写约束

## 关键约束
- benchmark-lite 是 Lite 主流程的强制前置
- 输出必须能直接约束 worldbuilding / characters / chapter-outline / writing
- 若有原文样本，采样必须覆盖前段 / 中段 / 后段多个区域
- 不做 scene_type / style_snippet 切片落盘
