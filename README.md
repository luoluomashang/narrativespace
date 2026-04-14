# 叙事空间 Lite v11.0

以 `benchmark-lite -> 世界观与力量体系讨论 -> 人物卡片设定 -> 章纲讨论 -> 正文 Prompt 组装` 为主干的 Lite 创作系统。

## 强制模块
- benchmark-lite
- worldbuilding
- characters
- chapter-outline
- writing

## 可选模块
- humanizer

## 快速开始
```bash
python scripts/init.py --project-dir /your/project --yes --reply-length 2500
python scripts/assemble_prompt.py --project-dir /your/project --status
python scripts/assemble_prompt.py --project-dir /your/project --step benchmark-lite
```

默认输出为 **Prompt 包**：包含步骤目标、输入上下文摘要、已组装 Prompt、预期输出结构、结果回填说明。把其中的 `已组装 Prompt` 原文交给外部模型执行，再把结果保存回项目目录。

## Lite 主流程
1. `benchmark-lite`
2. `worldbuilding`
3. `characters`
4. `chapter-outline`
5. `10`（正文写作）
6. `humanizer`（可选）

## 关键变化
- benchmark-lite 改为必选前置，不可跳过
- benchmark 输出恢复更完整的 style_notes 契约，但不再要求场景切片 / 风格切片
- 新增人物卡片设定步骤，写作阶段按需加载人物卡片
- 写作主流程不再使用 `project_card / 卷纲 / 轻量 KB / 章节卡`
- `assemble_prompt.py` 默认只产出 Prompt 包，不在 Skill 内直接代写正文
- 写作只校验最小中文字符数，不再有番茄等平台硬上限
- humanizer 契约与 `main` 分支后处理模块对齐

## Prompt-only 执行方式
1. 使用 `python scripts/assemble_prompt.py --project-dir /your/project --step <step>` 组装当前步骤 Prompt 包
2. 将返回内容中的 `## 已组装 Prompt` 原文完整交给外部模型
3. 将外部模型结果写回 Prompt 包指定路径
4. 对 writing / humanizer 使用 `landing.py` 落盘，再用 `validate_state.py` 验证

如需给程序或平台对接，可增加 `--format json` 输出 JSON Prompt 包。

## 写作落盘
```bash
python scripts/landing.py writing --project-dir /your/project --chapter 1 --input-file /your/project/.xushikj/drafts/ch1_output.md
python scripts/validate_state.py --project-dir /your/project --for-step 10 --chapter 1
```

## Humanizer 独立使用
```bash
python scripts/assemble_prompt.py --project-dir /your/workdir --step humanizer --chapter-file /your/workdir/chapter_1.md
python scripts/landing.py humanizer --project-dir /your/workdir --chapter-file /your/workdir/chapter_1.md --input-file /your/workdir/humanizer_output.md
python scripts/validate_state.py --project-dir /your/workdir --for-step humanizer --chapter-file /your/workdir/chapter_1.md
```

Humanizer 当前落盘主契约：
- 正文后追加 `## 修改清单`
- 兼容旧版 `## 修改说明 / ## 豁免记录 / ## R-DNA校验`

## 验证命令
```bash
python scripts/validate_references.py
python scripts/regression_workflow_guards.py --project-dir /tmp/narrativespace-smoke
```
