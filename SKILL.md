---
name: narrativespace-lite
description: Lite 版叙事空间创作系统。以 benchmark-lite → 世界观与力量体系讨论 → 人物卡片设定 → 章纲讨论 → 正文写作为主线，humanizer 为独立后处理。
metadata:
  version: 11.0.0
  edition: lite
  architecture: 5+1
  triggers:
    - 叙事空间
    - 网文创作
    - 小说续写
---

# 叙事空间 Lite

## 定位
这是一个面向“强对标 + 强讨论 + Prompt 编排 + 外部执行”的 Lite 创作 Skill：
- 强制 5 模块：benchmark-lite / worldbuilding / characters / chapter-outline / writing
- 可选 1 模块：humanizer
- benchmark-lite 输出的 `style_notes.md` 是后续人物、章纲、写作 Prompt 的硬约束来源
- Skill 默认只负责组装 Prompt 包、说明回填路径与回填命令；正式内容由外部模型生成后再回写

## 启动规则
1. 先检查项目根目录下是否存在 `.xushikj/state.json`
2. 若不存在，优先执行 `python scripts/init.py --project-dir <项目根目录> --yes`
3. benchmark-lite 完成前，不得进入 worldbuilding / characters / chapter-outline / writing
4. worldbuilding 完成前，不得进入 characters / chapter-outline / writing
5. characters 完成前，不得进入 chapter-outline / writing
6. 在进入 writing 前，必须先向用户确认 `reply_length`（每章最小中文字符数）
7. `target_platform` 改为可选上下文，不再作为主流程硬门禁
8. 初始化完成后，再使用 `python scripts/assemble_prompt.py` 组装当前步骤 Prompt 包
9. 除 humanizer 外，所有模块都以 `.xushikj/` 为唯一运行时目录
10. 若 `workflow.pending_user_confirmation=true`，不得直接进入下一步骤，必须先等待用户确认并执行 `python scripts/workflow_state.py confirm --project-dir <项目根目录>`

## 主流程
1. Step `benchmark-lite`：对标 / 文风克隆
2. Step `worldbuilding`：世界观与力量体系讨论
3. Step `characters`：人物卡片设定
4. Step `chapter-outline`：章纲讨论
5. Step `10`：正文写作 Prompt 组装
6. `humanizer`（可选）：发布前后处理 / 去 AI 痕迹

## 边界
- 不再使用 `project_card`、卷纲、轻量知识库、章节卡这条旧 Lite 链路
- benchmark-lite 必须尽量按原版对标契约输出完整 style_notes，只去掉场景切片 / 风格切片落盘要求
- 对标采样不得只读开头几行；若存在登记原文，必须覆盖前段 / 中段 / 后段多个样本
- 人物卡片负责沉淀主要人物的稳定设定；writing 仅按需加载相关卡片，不回退旧 KB 体系
- `assemble_prompt.py` 默认输出 Prompt 包（含步骤目标、输入上下文摘要、已组装 Prompt、预期输出结构、结果回填说明），供外部模型直接执行
- Step 10 正文写作结果必须先经 `python scripts/landing.py writing --project-dir <项目根目录> --chapter <N> --input-file <模型输出文件>` 落盘，再执行 `python scripts/validate_state.py --project-dir <项目根目录> --for-step 10 --chapter <N>` 做字数验收
- Step 10 只校验 `reply_length` 对应的最小中文字符数，不再施加平台硬上限
- humanizer 可通过 `python scripts/assemble_prompt.py --project-dir <目录> --step humanizer --chapter-file <章节文件>` 独立使用
- humanizer 的规则内容应与 `main` 分支后处理模块保持一致，不再做 Lite 简化
- humanizer 结果通过 `python scripts/landing.py humanizer --project-dir <目录> --chapter-file <章节文件> --input-file <模型输出文件>` 落盘到 `.xushikj/humanized/`
