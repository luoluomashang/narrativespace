---
name: narrativespace-xushikj
description: 叙事空间创作系统（一体化版）精简入口。保留模块化能力，通过脚本化编排按步骤投喂提示词。
metadata:
  version: 10.0.0
  edition: unified-lite
  skills_included: 8
  triggers:
    - 叙事空间
    - 网文创作
    - 商业小说
---

# 叙事空间创作系统（精简版）

## 定位
统一路由入口，负责把用户请求分发到对应模块，不承载全量执行细则。

## 启动行为
- 启动时优先检查项目根目录下是否存在 `.xushikj/state.json`。
- 若不存在且当前为代理模式（具备工具权限），应自动执行 `scripts/init.py` 完成初始化。
- 若不存在且当前仅为普通聊天模式，则提示用户先初始化；除 `humanizer` 外不进入其他模块。

## 模块
- benchmark: 步骤0 对标分析
- planning: 快速立项、步骤4（一页大纲）、步骤11（书名简介）
- knowledge-base: 步骤7 知识库
- scenes: 步骤8-9 场景
- writing: 步骤10A 流水线写作
- interactive: 步骤10B 互动写作
- humanizer: 后处理

## 使用建议
- 规则与上下文由脚本按步骤组装（scripts/assemble_prompt.py）。
- 模型一次只处理当前步骤的必要约束，避免全量规则过载。
- 历史长版说明见 SKILL_legacy.md。
