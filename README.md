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
python scripts/init.py --project-dir /your/project --yes --reply-length 2500 --target-platform fanqie
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

## Lite Pro 补强
- Step 0 支持 `benchmark/style_notes.md` + 本地 `style_snippets/manifest.yaml`
- Step 10 会读取 `summary_index.md` + `memory.md` + 场景类型驱动的风格切片
- 正文落盘后需执行：
  ```bash
  python scripts/validate_state.py --project-dir /your/project --for-step 10 --chapter 1
  ```
  该脚本会调用 `scripts/chinese_char_count.py` 做最小中文字符数强校验

## 历史资产
- 已退出 Lite 主流程的旧模板、旧配置、旧脚本会迁入 `legacy/`，避免继续污染当前运行时入口

## 验证命令
```bash
python scripts/validate_references.py
python scripts/validate_state.py --project-dir /your/project --for-step 10 --chapter 1
```
