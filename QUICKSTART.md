# 叙事空间 Lite - Quickstart

## 1. 初始化
```bash
python scripts/init.py --project-dir /your/project --yes
```

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

## 8. 校验写作前置
```bash
python scripts/validate_state.py --project-dir /your/project --for-step 10 --chapter 1
```
