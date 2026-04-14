# 叙事空间 Lite - Quickstart

## 1. 初始化
```bash
python scripts/init.py --project-dir /your/project --yes --reply-length 2500
```

> `reply_length` 是唯一硬字数门槛；`target_platform` 可选，不再影响上限校验。

## 2. 查看状态
```bash
python scripts/assemble_prompt.py --project-dir /your/project --status
```

## 3. 组装 benchmark-lite Prompt
```bash
python scripts/assemble_prompt.py --project-dir /your/project --step benchmark-lite --output file --output-file /your/project/.xushikj/drafts/benchmark_prompt.md
```

## 4. 组装世界观与力量体系讨论 Prompt
```bash
python scripts/assemble_prompt.py --project-dir /your/project --step worldbuilding --output file --output-file /your/project/.xushikj/drafts/worldbuilding_prompt.md
```

## 5. 组装人物卡片设定 Prompt
```bash
python scripts/assemble_prompt.py --project-dir /your/project --step characters --output file --output-file /your/project/.xushikj/drafts/characters_prompt.md
```

## 6. 组装章纲讨论 Prompt
```bash
python scripts/assemble_prompt.py --project-dir /your/project --step chapter-outline --chapter 1 --output file --output-file /your/project/.xushikj/drafts/ch1_outline_prompt.md
```

## 7. 组装正文 Prompt
```bash
python scripts/assemble_prompt.py --project-dir /your/project --step 10 --chapter 1 --output file --output-file /your/project/.xushikj/drafts/ch1_writing_prompt.md
```

## 8. 落盘正文并等待确认
```bash
python scripts/landing.py writing --project-dir /your/project --chapter 1 --input-file /your/project/.xushikj/drafts/ch1_output.md
python scripts/validate_state.py --project-dir /your/project --for-step 10 --chapter 1
python scripts/workflow_state.py status --project-dir /your/project
python scripts/workflow_state.py confirm --project-dir /your/project
```

## 9. 独立使用 Humanizer
```bash
python scripts/assemble_prompt.py --project-dir /your/workdir --step humanizer --chapter-file /your/workdir/chapter_1.md
python scripts/landing.py humanizer --project-dir /your/workdir --chapter-file /your/workdir/chapter_1.md --input-file /your/workdir/humanizer_output.md
python scripts/validate_state.py --project-dir /your/workdir --for-step humanizer --chapter-file /your/workdir/chapter_1.md
```

Humanizer 推荐输出 `## 修改清单`；落盘兼容旧版 `## 修改说明 / ## 豁免记录 / ## R-DNA校验`。
