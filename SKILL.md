---
name: narrativespace-lite
description: Lite 版叙事空间创作系统。以 project_card → 卷纲 → 轻量 KB → 章节卡 → 正文写作为主线，benchmark-lite 与 humanizer 为可选外挂。
metadata:
  version: 11.0.0
  edition: lite
  architecture: 4+2
  triggers:
    - 叙事空间
    - 网文创作
    - 小说编排
---

# 叙事空间 Lite

## 定位
这是一个可直接落地的 Lite 创作 Skill：
- 核心 4 模块：planning / knowledge-base / scenes / writing
- 可选 2 模块：benchmark-lite / humanizer
- 默认只围绕“当前卷、当前章、最近记忆”展开，不再承载旧版重型状态机

## 启动规则
1. 先检查项目根目录下是否存在 `.xushikj/state.json`
2. 若不存在，优先执行 `python scripts/init.py --project-dir <项目根目录> --yes`
3. 在进入 planning / scenes / writing 前，必须先向用户确认两项：`reply_length`（每章最小中文字符数）与 `target_platform`
4. 初始化完成后，再使用 `python scripts/assemble_prompt.py` 组装当前步骤 Prompt
5. 除 humanizer 外，所有模块都以 `.xushikj/` 为唯一运行时目录
6. 若 `workflow.pending_user_confirmation=true`，不得直接进入下一步骤，必须先等待用户确认并执行 `python scripts/workflow_state.py confirm --project-dir <项目根目录>`

## 主流程
1. Step 0（可选） benchmark-lite
2. Step project_card 立项
3. Step 4 当前卷一页纲
4. Step 7 轻量知识库初始化/更新
5. Step 8 当前章或未来 1~3 章章节卡
6. Step 10 正文写作
7. humanizer（可选）发布前润色

## 边界
- 不包含 interactive/TRPG 主流程
- 不依赖 DNA、Layer-2、复杂 diff、RAG、世界状态机
- 每次只处理当前步骤，不自动跨步
- 信息不足时先提问，不得擅改用户已确认设定
- 正文写作结果必须先经 `python scripts/landing.py writing --project-dir <项目根目录> --chapter <N> --input-file <模型输出文件>` 落盘，再执行 `python scripts/validate_state.py --project-dir <项目根目录> --for-step 10 --chapter <N>` 做字数硬验收
- humanizer 可通过 `python scripts/assemble_prompt.py --project-dir <目录> --step humanizer --chapter-file <章节文件>` 独立使用
- humanizer 结果通过 `python scripts/landing.py humanizer --project-dir <目录> --chapter-file <章节文件> --input-file <模型输出文件>` 落盘到 `.xushikj/humanized/`
