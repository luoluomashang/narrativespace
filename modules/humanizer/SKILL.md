---
name: humanizer-lite
metadata:
  version: 11.0.0
  parent: narrativespace-lite
  role: optional-post-process
---

# 小说去AI痕迹模块（Lite 对齐 main）

## 描述
小说专用去 AI 痕迹 Prompt 组装模块。Lite 版本的规则内容与 main 分支后处理模块保持一致，不再做 Lite 简化。

## 核心原则
- 只做减法和替换，不加新内容
- 保护小说叙事与人物声音
- 宁可漏改，不可误伤

## 执行边界
- 后处理不改剧情事实、不改角色关系、不改世界规则
- Skill 默认只组装 Prompt 包，实际润色由外部模型执行
- 推荐输出为正文 + `## 修改清单`
- 为兼容当前 Lite 落盘，旧版 `## 修改说明 / ## 豁免记录 / ## R-DNA校验` 仍可被接收
