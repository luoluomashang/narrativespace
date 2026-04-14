---
name: writing-lite
metadata:
  version: 11.0.0
  parent: narrativespace-lite
  step: 10
---

# Writing Lite

## 职责
- 根据《文风特征指南》、世界观设定、人物卡片与当前章章纲组装正文写作 Prompt
- 优先保障语感对齐，再把执行责任交给外部模型
- 约束外部模型产出正文、本章摘要、状态变化、新增设定、未兑现钩子

## 边界
- benchmark-lite 未完成时不得开写
- characters 未完成时不得开写
- 不负责旧 Lite 的章节卡 / KB 流水线
- 只校验最小中文字符数，不再校验平台上限
