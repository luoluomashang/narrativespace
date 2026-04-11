# 叙事空间 Lite v11.0

以 `project_card -> 卷纲 -> 轻量 KB -> 章节卡 -> 正文写作` 为主干的 Lite 创作系统。

## 核心模块
- planning
- knowledge-base
- scenes
- writing

## 可选模块
- benchmark-lite
- humanizer

## 快速开始
```bash
python scripts/init.py --project-dir /your/project --yes
python scripts/assemble_prompt.py --project-dir /your/project --status
python scripts/assemble_prompt.py --project-dir /your/project --step project_card
```

## Lite 主流程
1. `project_card`
2. `4`（当前卷一页纲）
3. `7`（轻量知识库）
4. `8`（当前章/未来 1~3 章章节卡）
5. `10`（正文写作）

## 可选流程
- `0`：benchmark-lite
- `humanizer`：定稿润色

## 验证命令
```bash
python scripts/validate_references.py
python scripts/validate_state.py --project-dir /your/project --for-step 10 --chapter 1
```
