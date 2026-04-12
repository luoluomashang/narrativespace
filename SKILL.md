---
name: narrativespace-lite
description: Lite 版叙事空间创作系统。以 benchmark-lite → 世界观与力量体系讨论 → 章纲讨论 → 正文写作为主线，humanizer 为独立后处理。
metadata:
  version: 11.0.0
  edition: lite
  architecture: 4+1
  triggers:
    - 叙事空间
    - 网文创作
    - 小说续写
---

# 叙事空间 Lite

## 定位
这是一个面向“文风克隆 + 讨论式搭骨架 + 小步续写”的 Lite 创作 Skill：
- 强制 4 模块：benchmark-lite / worldbuilding / chapter-outline / writing
- 可选 1 模块：humanizer
- benchmark-lite 不是外挂，而是后续写作的硬约束来源

## 启动规则
1. 先检查项目根目录下是否存在 `.xushikj/state.json`
2. 若不存在，优先执行 `python scripts/init.py --project-dir <项目根目录> --yes`
3. benchmark-lite 完成前，不得进入 worldbuilding / chapter-outline / writing
4. 在进入 writing 前，必须先向用户确认 `reply_length`（每章最小中文字符数）
5. `target_platform` 改为可选上下文，不再作为主流程硬门禁
6. 初始化完成后，再使用 `python scripts/assemble_prompt.py` 组装当前步骤 Prompt
7. 除 humanizer 外，所有模块都以 `.xushikj/` 为唯一运行时目录
8. 若 `workflow.pending_user_confirmation=true`，不得直接进入下一步骤，必须先等待用户确认并执行 `python scripts/workflow_state.py confirm --project-dir <项目根目录>`

## 主流程
1. Step `benchmark-lite`：对标 / 文风克隆
2. Step `worldbuilding`：世界观与力量体系讨论
3. Step `chapter-outline`：章纲讨论
4. Step `10`：正文写作
5. `humanizer`（可选）：发布前润色 / 去 AI 痕迹

## 边界
- 不再使用 `project_card`、卷纲、轻量知识库、章节卡这条旧 Lite 链路
- 不依赖 scene_type 驱动的 style_snippets 才能写作
- 每次只处理当前步骤，不自动跨步
- 信息不足时先提问，不得擅改用户已确认设定
- Step 10 正文写作结果必须先经 `python scripts/landing.py writing --project-dir <项目根目录> --chapter <N> --input-file <模型输出文件>` 落盘，再执行 `python scripts/validate_state.py --project-dir <项目根目录> --for-step 10 --chapter <N>` 做字数验收
- Step 10 只校验 `reply_length` 对应的最小中文字符数，不再施加平台硬上限
- humanizer 可通过 `python scripts/assemble_prompt.py --project-dir <目录> --step humanizer --chapter-file <章节文件>` 独立使用
- humanizer 结果通过 `python scripts/landing.py humanizer --project-dir <目录> --chapter-file <章节文件> --input-file <模型输出文件>` 落盘到 `.xushikj/humanized/`
- humanizer 输出必须完整保留 `R1/R2/R3/R-DNA` 与 `## 修改说明` / `## 豁免记录` / `## R-DNA校验` 结构
