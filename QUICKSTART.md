# 叙事空间创作系统 v8.5 — 快速开始

> **预计读完：10 分钟 | 完成新项目启动：20-30 分钟**

---

## 前置条件

| 项目 | 要求 |
|---|---|
| Python | 3.8+ |
| 模型 | Claude Sonnet 3.5/4.x 或同等级别 |
| Skill 路径 | `narrativespace-xushikj/` 已放入 `.claude/skills/`（参见 §安装） |
| 项目目录 | 在本地创建一个空文件夹作为项目根目录 |

## 二阶段新增（脚本编排模式）

这里同样区分两种环境：

1. 普通聊天模式：用户手动运行脚本。
2. 代理模式（如 Claude Code / VS Code Agent）：代理可代为运行脚本并继续流程。
3. 关键点：是否由模型执行脚本，不取决于模型本身，而取决于运行环境是否授予工具权限。

推荐先用脚本组装每一步 Prompt，再喂给模型执行：

```bash
# 看状态
python narrativespace/scripts/assemble_prompt.py --project-dir .xushikj --status

# 写作前预检（Step10 强校验 + 字数门禁）
python narrativespace/scripts/validate_state.py --project-dir . --for-step10 --chapter 1 --min-chapter-chars 2500 --strict

# 组装步骤1
python narrativespace/scripts/assemble_prompt.py --project-dir .xushikj --step 1 --output file --output-file .xushikj/drafts/step1_prompt.md

# 组装步骤10（显式声明写作模式，避免串模）
python narrativespace/scripts/assemble_prompt.py --project-dir .xushikj --step 10 --chapter 3 --writing-mode pipeline --output file --output-file .xushikj/drafts/ch3_prompt.md
```

如果执行了 Step 0 对标切片分析，还需要手动落盘切片：

```bash
python narrativespace/scripts/slice_library.py write-snippet --project-dir . --scene-type daily --content-file snippet_daily.md
python narrativespace/scripts/slice_library.py write-dna --project-dir . --project-name my_project --dna-json dna_profile.json
```

阶段推进必须遵循：
1. 当前阶段完工
2. 功能自查通过
3. 调用 `#tool:vscode_askQuestions` 让用户确认是否继续
4. 用户确认后再进入下一阶段

### 安装 Skill

```
.claude/skills/
└── narrativespace-xushikj/   ← 将整个 narrativespace/ 文件夹放到这里
    ├── SKILL.md
    ├── config/
    ├── modules/
    └── ...
```

---

## 重要：对话执行边界

⚠️ **每种模式必须在独立的对话中运行。** 不要在同一次对话中连续完成 Mode A 和 Mode B，否则会因 Token 耗尽导致上下文丢失。

- **Mode A（流水线）**：开一个新对话窗口
- **Mode B（交互式 TRPG）**：开另一个新对话窗口

---

## Mode A — 流水线模式（推荐新手）

> 最终产出：3 章正文 + 完整知识库 + 书名简介

### 步骤清单

| 步骤 | 触发词 | 关键操作 | 预期产出 |
|---|---|---|---|
| **Step 0**（可选）| `对标学习` | 粘贴 1-3 部参考书名 | `benchmark/style_report.md` |
| **Step 1** | `叙事空间` 或 `写网文` | 回答：题材、主角、核心任务 | `outline/one_sentence.md` |
| **Step 2** | （Step 1 确认后自动询问）| 回答：本卷落点、长期方向 | `outline/one_paragraph.md` |
| **Step 2.5**（条件）| 含修炼/金手指/科幻题材时触发 | 回答：力量体系、升级规则 | `outline/worldview_and_system.md` |
| **Step 3** | （Step 2 确认后）| 回答：3-5 个核心角色 | `outline/characters/` |
| **Step 4** | （Step 3 确认后）| 回答：第一卷节奏和高潮 | `outline/volume_1_one_page.md` |
| **Step 5**（可选）| 系统会询问是否执行 | 回答：各角色成长路径 | `outline/character_arcs.md` |
| **Step 6**（可选）| 系统会询问是否执行 | 回答：伏笔、章节细节 | `outline/volume_1_four_pages.md` |
| **Step 7** | `初始化知识库` | **推荐用脚本**：编辑 `scripts/kb_init_example.py` 后运行 `python scripts/kb_init_example.py` | `.xushikj/knowledge_base.json` |
| **Step 8** | `场景清单` | 确认本 cycle 章节范围 | `scenes/cycle_1/scene_list.md` |
| **Step 9** | `规划场景` | 确认各章主要冲突 | `scenes/cycle_1/scene_plans/*.md` |
| **Step 10A** | `写第1章` | 每章写完后检查字数和钩子 | `chapters/cycle_1/chapter_N.md` |
| **Humanizer** | `小说去AI` | 粘贴草稿，确认 0 禁用词 | `humanizer_report.md` + 最终版章节 |
| **Step 11** | `书名与简介` | 回答：平台风格、书名偏好 | `outline/title_and_synopsis.md` |

### 每步完成后：保存检查点（推荐）

在项目目录下维护 `session_checkpoint.md`，记录：

```markdown
# 检查点
- 当前步骤：Step X 完成
- 最后创建的文件：xxx.md
- 已写章节数：N
- KB 实体数：N
- 下一步：Step Y
```

---

## Mode B — 交互式 TRPG 模式

> 最终产出：若干 Session（每 session = 1 章）+ 知识库 + Humanizer 版最终章节

### 与 Mode A 的主要差异

| 项目 | Mode A（流水线）| Mode B（交互式）|
|---|---|---|
| 触发词 | `叙事空间` / `写网文` | `跑团模式` / `开始互动` / `TRPG推演` |
| Step 6 | 推荐执行 | **不需要**（无需四页大纲）|
| Steps 8-9 | 必须执行 | **不需要**（无需场景规划）|
| Step 10 | 自动逐章写作 | Ping-Pong 循环（DM叙述 → 你决策 → 循环）|
| 文件区分 | `chapter_N_draft.md` → `chapter_N.md` | `session_N_wip.md` → `session_N_final.md` |

### Mode B 专用步骤清单

| 步骤 | 说明 |
|---|---|
| **Step 0-3** | 同 Mode A：对标（可选）→ 一句话 → 一段话 → 人物卡 |
| **Step 7** | 使用 Lite 初始化（只需人物实体，不需四页大纲）|
| **Step 10B** | 触发词：`跑团模式`；AI=DM，你=玩家；每回合 300-600 字 + 三选一决策点 |
| **落盘** | 当章写完说"落盘"或"本章结束"，系统保存 `session_N_wip.md` |
| **Humanizer** | 对 `_wip.md` 执行去AI处理，产出 `session_N_final.md` |

### WIP vs Final 说明

| 文件 | 说明 |
|---|---|
| `session_N_wip.md` | 原始 Ping-Pong 记录，含 DM/玩家对话轮次，用于归档 |
| `session_N_final.md` | Humanizer 后处理版本，可直接发布 |

---

## 知识库初始化（推荐方式）

**避免在对话中粘贴大段 JSON，改用脚本：**

```bash
# 1. 编辑脚本中的 kb 字典，填入你的角色/地点/物品
#    脚本路径：scripts/kb_init_example.py

# 2. 运行
python scripts/kb_init_example.py

# 3. 脚本会写入 .xushikj/knowledge_base.json
```

脚本支持中文字段，不受 Shell 转义问题影响。

---

## RAG 本地语义检索

RAG 仅在项目累计写到 **30+ 章** 后自动启用。新项目前期不会触发，这是正常行为（L3 静默跳过，不报错）。

需要手动测试 RAG 后端：

```bash
python scripts/rag_index.py --project-dir .xushikj --check-backend
```

---

## 常见问题

**Q：系统不响应触发词？**
确认 `narrativespace-xushikj/SKILL.md` 已放入正确的 `.claude/skills/` 路径。

**Q：KB JSON 写入报错？**
使用 `scripts/kb_init_example.py` 脚本代替在对话中直接粘贴 JSON，彻底规避转义问题。

**Q：对话中途上下文丢失？**
每步完成后保存 `session_checkpoint.md`（见上文）。Mode A 和 Mode B 必须分开对话。

**Q：Humanizer 找到禁用词？**
禁用词命中时必须修改，不允许豁免。检查 `config/human_touch_rules.yaml` 中的 `banned_words` 列表。

**Q：写了 3 章想继续写第 4 章？**
直接说 `写第4章`，系统会自动使用已有的 KB 和场景规划继续。

---

详细文档：[使用手册.md](使用手册.md)
