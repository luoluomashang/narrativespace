# 叙事空间 Lite - Quickstart

## 1. 初始化
```bash
python scripts/init.py --project-dir /your/project --yes --reply-length 2500 --target-platform fanqie
```

> 如果还没有确定参数，先问清用户期望的每章最小中文字符数与目标平台，再初始化。

## 2. 查看状态
```bash
python scripts/assemble_prompt.py --project-dir /your/project --status
```

## 3. 组装 project_card Prompt
```bash
python scripts/assemble_prompt.py --project-dir /your/project --step project_card --output file --output-file /your/project/.xushikj/drafts/project_card_prompt.md
```

## 4. 组装当前卷一页纲 Prompt
```bash
python scripts/assemble_prompt.py --project-dir /your/project --step 4 --output file --output-file /your/project/.xushikj/drafts/volume_one_page_prompt.md
```

## 5. 组装 KB Prompt
```bash
python scripts/assemble_prompt.py --project-dir /your/project --step 7 --output file --output-file /your/project/.xushikj/drafts/kb_prompt.md
```

## 6. 组装章节卡 Prompt
```bash
python scripts/assemble_prompt.py --project-dir /your/project --step 8 --chapter 1 --output file --output-file /your/project/.xushikj/drafts/ch1_scene_prompt.md
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

## 10. 校验写作前置 / 写后验收
```bash
python scripts/validate_state.py --project-dir /your/project --for-step 10 --chapter 1
```

当 `chapters/chapter_1.md` 已存在时，上述命令会自动调用 `scripts/chinese_char_count.py` 做正文中文字符数验收。
