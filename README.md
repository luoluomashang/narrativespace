# 叙事空间 Lite v11.0

以 `benchmark-lite -> 世界观与力量体系讨论 -> 人物卡片设定 -> 章纲讨论 -> 正文写作` 为主干的 Lite 创作系统。

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
- 写作只校验最小中文字符数，不再有番茄等平台硬上限
- humanizer 契约与 `main` 分支后处理模块对齐

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
