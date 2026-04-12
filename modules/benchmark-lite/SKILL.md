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
- 提炼参考文本的《文风特征指南》
- 输出词汇、句式、标点、情感、修辞偏好
- 输出 AI 套话黑名单与小步续写约束

## 关键约束
- benchmark-lite 是 Lite 主流程的强制前置
- 输出必须能直接约束 writing，不再只是风格备忘
- 优先服务语感对齐，不再围绕 scene_type 切片建模
