---
name: benchmark-lite
metadata:
  version: 11.0.0
  parent: narrativespace-lite
  step: 0
---

# Benchmark Lite

## 职责
- 提炼参考作品的节奏、语气、题材套路偏好
- 可选保留少量风格片段供写作参考

## 关键约束
- 若已生成 `scene_type_coverage.json`，必须以其为准覆盖全部 `source_available=true` 类型
- 每个 active scene_type 至少保留 3 个不重复的合格切片；未满足时不得宣称达标
- 禁止只凭开头样本猜 scene_type，禁止编造命令参数或未验证的数据

## 边界
- 不做 DNA 提取
- 不做 clone prompt
- 不阻塞主流程
