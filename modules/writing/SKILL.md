---
name: writing-lite
metadata:
  version: 11.0.0
  parent: narrativespace-lite
  step: 10
---

# Writing Lite

## 职责
- 根据当前章节卡写正文
- 读取最近摘要与 KB 切片维持连续性
- 产出正文、本章摘要、状态变化

## 边界
- 不负责多 sub-agent 写作链
- 不负责复杂质检流水线
- 不自动推进下一章
