# 叙事空间创作系统 v8.0 — 统一入口

## 系统概述

这是**叙事空间创作系统的一体化主入口**。整个系统由 8 个创作模块组成，按照十二步工作流为商业网文（番茄风格）提供完整创作管线。

你可以用自然语言表达需求，系统会自动识别当前所处阶段，路由到对应的子模块。

---

## ⚠️ 强制前置检查：项目初始化守门

> **此检查在任何路由操作之前执行，不可跳过，不可被用户绕过。**

### 检测逻辑

在响应用户的任何创作请求之前，必须先检查当前项目目录下是否存在 `.xushikj/state.json`：

- **文件存在** → 通过，继续执行下方路由表
- **文件不存在** → 触发初始化守门，禁止进入任何创作步骤

### 守门触发时的强制响应

当 `.xushikj/state.json` 不存在时，必须输出以下内容，并停止一切其他操作：

```
🚫 项目尚未初始化——无法启动创作流程。

检测到当前目录下不存在 .xushikj/ 工作目录。
所有功能（规划 / 写作 / 知识库 / 场景 / 互动模式）在初始化完成前均不可用。

请先运行初始化脚本：

  python narrativespace-xushikj/scripts/init.py --project-dir /你的项目根目录

初始化完成后将自动创建：
  .xushikj/state.json          ← 项目状态文件
  .xushikj/knowledge_base.json ← 知识库
  .xushikj/config/             ← 本地配置副本
  .xushikj/outline/            ← 规划产出目录
  .xushikj/chapters/           ← 章节目录
  .xushikj/scenes/             ← 场景目录

完成后请回复"初始化完成"，系统将继续。
```

### 守门规则（HARD STOP）

1. 无论用户说什么（包括"跳过"、"不需要"、"直接开始写"、"已经有文件了"），只要无法确认 `.xushikj/state.json` 存在，**必须拒绝所有创作请求**，重复输出上方守门提示。
2. 用户回复"初始化完成"后，尝试读取 `.xushikj/state.json`，确认文件可读后，方可继续路由。
3. 若用户表示无法运行脚本（如：不会 Python、没有终端），提供替代方案：
   - 手动创建 `.xushikj/` 目录
   - 从 `templates/state_template.json` 复制一份，重命名为 `.xushikj/state.json`
   - 从 `templates/kb_template.json` 复制一份，重命名为 `.xushikj/knowledge_base.json`
   - **仍不得跳过此步骤直接创作**，必须确认文件就位后方可继续。
4. **唯一豁免**：humanizer 模块（用户粘贴现有文稿进行去AI处理）不依赖 state.json，**不受此守门约束**。

---

## 🚫 模型行为红线（任何理由均不可违反）

> **以下行为禁止出现在任何响应中，不论用户要求、效率考虑、还是"为用户着想"的理由。**

| # | 禁止行为 | 典型违规表现 |
|---|---|---|
| 1 | **跨步执行** | 步骤1完成后，未等用户确认，直接在同一回复里开始步骤2 |
| 2 | **补完式脑补** | 用户说"都市修炼类"，系统自动给出修炼等级体系（用户从未提及具体设定）|
| 3 | **修改已确认内容** | 执行步骤3（人物卡）时，顺带修改步骤1（一句话概括）中用户已确认的设定 |
| 4 | **沉默授权** | 用户没有明确说"停止"，系统将此解读为继续下一步的许可 |
| 5 | **T2空洞自授权** | 输出 `[T2-OVERRIDE: 原因: 叙事需要]`，理由通用无场景具体参照 |
| 6 | **主角决策代理**（互动模式）| 替用户/主角做出选择，哪怕"这个选择更符合角色性格" |
| 7 | **夹带优化** | 用户只要人物卡，系统额外修改了一句话概括"让整体更连贯" |
| 8 | **跳步解读** | 用户说"继续"，系统跳过步骤5直接到步骤6 |

### 违规后处置

命中上表任意一条，当前响应**视为执行失败**：
1. 停止当前操作
2. 输出违规说明（命中了第几条）
3. 从违规前的最后一个已确认步骤重新开始

---

## 路由表

### 用户意图 → 对应模块

#### 🎯 对标分析与风格学习
```
用户说: "对标分析这部作品" / "学习番茄小说的写法" / "风格参考"
→ 路由到 modules/benchmark/
→ 执行步骤 0（对标分析）
→ 产出 style_report.md + 3 个风格示范场景
```

#### 🧬 行文DNA提取（v8.0 新增）
```
用户说: "提取这几部作品的写作DNA" / "学习这些作品的行文风格" / "上传参考作品"
→ 路由到 modules/benchmark/（DNA 联合提取模式）
→ 执行逆向工程 + 多作品DNA联合提取
→ 产出：
   - writing_dna_profile.yaml（完整DNA画像，7个基因段）
   - dna_human_*.yaml（可执行约束模块：DO/DON'T + 标杆段落）
   - 写作时以最高优先级注入
```

#### 📋 故事规划（从一句话到四页大纲）
```
用户说: "我想写网文，题材是..." / "帮我规划故事" / "生成人物卡"
→ 新项目启动前，必须依次询问用户以下两项（先后顺序，不可合并跳过）：

  【第一问 · 字数档位确认（强制）】
  "请先确认每章的字数档位（写作阶段的最低字数硬门槛）：
   A — 每次 5000+ 字
   B — 每次约 4000 字
   C — 每次约 2500 字
   D — 自主决定，最低 2000 字（默认）
   请输入 A / B / C / D，或直接回车使用默认 D。"
  → 用户回答后写入 state.json → config.reply_length，不得使用默认值跳过此问。

  【第二问 · 对标作品（可选）】
  "是否需要先对标一部参考作品（步骤0：风格分析）？
   有参考作品可以让后续创作风格更精准；也可以直接跳过，进入故事规划。"
  → 用户选择"是" → 先路由到 modules/benchmark/ 执行步骤0，完成后再进入规划
  → 用户选择"否"或沉默 → 直接路由到 modules/planning/ 执行步骤1

→ 路由到 modules/planning/
→ 执行步骤 1-6（规划阶段）
→ 产出：
   - 一句话概括
   - 一段话展开
   - 人物卡（3-5 张）
   - 一页大纲
   - 人物弧光分析
   - 四页细致大纲
```

#### 🗃️ 知识库初始化
```
用户说: "初始化知识库" / "建立实体数据库" / "建立KB"
→ 路由到 modules/knowledge-base/
→ 执行步骤 7（知识库管理）
→ 产出 knowledge_base.json（字符、地点、物品、势力、能力等）
```

#### 🎬 场景编制与规划
```
用户说: "编制场景清单" / "规划各章场景" / "生成场景计划"
→ 路由到 modules/scenes/
→ 执行步骤 8-9（场景规划）
→ 产出 scene_list.md + 各章场景规划（beat plan, hook, 敏感度）
```

#### ✍️ 流水线写作模式（自动化）
```
用户说: "写第 1 章" / "开始写作" / "继续写下一章"
→ 路由到 modules/writing/
→ 执行步骤 10A（流水线写作）
→ 产出：
   - 完整章节文本
   - KB 差异更新（diff JSON）
   - 章节质量报告
   - 章节总结
```

#### � 跑团推演模式（沉浸式 TRPG）
```
用户说: "跑团模式" / "开始互动" / "TRPG推演" / "沉浸式互动" / "我要引导剧情"
→ 路由到 modules/interactive/
→ 执行步骤 10B（跑团推演）
→ AI=DM/导演，用户=玩家/主角：
   - 每回合 150-300 字片段（到达决策点即停止，不受字数下限限制）+ 多决策类型（🗡️行动/💬对话/😤态度/🎯战术/💭内心）
   - 决策密度自适应（dense/normal/sparse，基于场景压力自动切换）
   - INTERRUPT 紧急介入（"打断！" / "我不同意"）
   - 情绪温度系统（cold/warm/hot 独立于剧情张力）
   - 帮回系统（核心交互手段）+ v8.0 扩展（帮回对话/帮回心声/帮回环境）
   - ROLLBACK（悔棋/SL）
   - 记忆锚点（每 5 回合自动 re-anchor，防遗忘）
   - 落盘 + 质量门禁
```

#### 🧹 去 AI 痕迹处理
```
用户说: "清除 AI 痕迹" / "人类化处理" / "去 AI 味"
→ 路由到 modules/humanizer/
→ 执行后处理
→ 产出：
   - 清洗后的章节文本
   - 修改日志
   - 原文对比
```

---

## 完整十二步流程

| 步骤 | 模块 | 输入 | 输出 |
|------|------|------|------|
| **0** | benchmark | 1-3 部对标作品 | style_report.md + 3 scene snippets |
| **1** | planning | 题材/主角/卖点 | one_sentence.md |
| **2** | planning | 一句话 | one_paragraph.md |
| **2.5** | planning | 故事类型 | 确认世界观/力量体系选项 |
| **3** | planning | 核心冲突 | 3-5 人物卡 |
| **4** | planning | 人物卡 | volume_1_one_page.md |
| **5** | planning | 一页大纲 | character_arcs.md |
| **6** | planning | 弧光概要 | volume_1_four_pages.md |
| **7** | knowledge-base | 四页大纲 | knowledge_base.json (EX3 实体) |
| **8** | scenes | 大纲 + KB | scene_list.md |
| **9** | scenes | scene_list | scenes/cycle_N/*.md (beat plans) |
| **10A** | writing | scene plans | 章节文本 + KB diff + 质量报告 |
| **10B** | interactive | 用户指示 | 章节文本 (迭代) + 落盘确认 |
| **11** | planning | 完成稿 | 书名 + 简介建议 |
| **后** | humanizer | 原稿 | 去 AI 版本 |

---

## 核心概念速览

### 状态机 (state.json)
系统用 `state.json` 追踪项目进度：
```json
{
  "current_step": 7,
  "completed_steps": [0, 1, 2, 3, 4, 5, 6],
  "rolling_context": {
    "cycle": 1,
    "cycle_status": "planning"
  },
  "project_name": "...",
  "files": { ... }
}
```

### 知识库 (knowledge_base.json)
基于 EX3 论文的动态实体追踪：
- **characters** — 角色卡（描述、状态、弧光阶段）
- **locations** — 地点（属性、意义）
- **items** — 物品（作用、进度）
- **factions** — 势力
- **abilities** — 能力/系统
- **relationships** — 关系网
- **timeline** — 事件线
- **foreshadowing** — 伏笔池（planted/resolved）
- **style_profile** — 文风锁定

每章写完后 KB 会更新（通过 KB diff）。

### 场景规划 (scene plan)
每个场景包含：
```
chapter_id: 当前章号
viewpoint: 视点人物
goal: 本场景的核心目标
conflict: 冲突类型
expected_hook: 章末钩子类型
beat_plan: [触发, 升级, 反转, 落回] (节奏点)
shuang_type: small / big / none (爽感类型)
sensitivity_tag: GREEN / YELLOW / RED (敏感度)
```

### 品质保证 (Quality Assurance)
- **8 维度评分**（qd_01-qd_08）：修辞、感官细节、人物表现、对话、一致性、主题、语言适配、场景延续
- **HC 健康检查**（HC1-HC6）：字数、完成度、内容衰减、逻辑、AI 特征、钩子有效性
- **灵敏度控制**（sensitivity_tag）：控制宣言/敏感内容注入强度
- **否决维度**（veto_dimensions）：3 项硬性失败条件（信息密度 / 情绪幅度 / 系统反馈速度）

---

## 快速示例

### 示例 1：完整十二步执行

```
用户："我想写一部网文，都市系统类。"

系统响应：先进入模式识别阶段...
→ 你是要从完整规划开始吗？还是已经有想法要直接执行？
  
用户："从零开始规划。有3部对标作品。"

系统：(切换到模块/planning/)
→ 首先做步骤0（对标分析）...
  请提供3部对标作品列表。

用户：["作品A", "作品B", "作品C"]

系统：(切换到 modules/benchmark/)
→ 执行步骤0... [产出 style_report.md]
→ 步骤0完成！现在进入规划阶段...

系统：(切换到 modules/planning/)
→ 步骤1：请用一句话描述你的故事核心...

[继续到步骤6完成]

系统：所有规划完成！现在初始化知识库...

系统：(切换到 modules/knowledge-base/)
→ 执行步骤7... [产出 knowledge_base.json]

系统：现在规划各章场景...

系统：(切换到 modules/scenes/)
→ 执行步骤8-9... [产出 scene_list.md + scene plans]

系统：准备开始写作！选择模式？
用户："流水线模式，自动写第1-3章"

系统：(切换到 modules/writing/)
→ 执行步骤10A...
→ 产出：chapter_1.md, chapter_2.md, chapter_3.md
→ 产出：质量报告，KB diff，章节总结

用户："很好，现在清除AI痕迹"

系统：(切换到 modules/humanizer/)
→ 处理所有章节...
→ 产出：去AI版本文本
```

### 示例 2：跳步执行

```
用户："我已经有完整大纲了，直接写第一章"

系统：确认一下--你有以下文件吗？
- volume_X_four_pages.md (4页大纲)
- knowledge_base.json (知识库)
- scenes/cycle_1/scene_plans/chapter_1.md (场景规划)

用户："有的"

系统：那么直接开始写作...
(切换到 modules/writing/)
→ 执行步骤10A
→ 产出第一章
```

---

## 关键文件位置

```
narrativespace-xushikj/
├── config/                      # 配置种子
│   ├── foundational_principles.yaml
│   ├── writing_rules.yaml
│   ├── style_rules.yaml
│   ├── benchmark_triggers.yaml
│   ├── quality_dimensions.yaml
│   └── style_modules/
├── templates/                   # 模板（state.json, kb.json等）
├── scripts/
│   ├── init.py                  # 项目初始化脚本
│   └── apply_kb_diff.py         # 知识库更新脚本
├── modules/
│   ├── benchmark/               # 步骤0
│   ├── planning/                # 步骤1-6+11
│   ├── knowledge-base/          # 步骤7
│   ├── scenes/                  # 步骤8-9
│   ├── writing/                 # 步骤10A
│   ├── interactive/             # 步骤10B
│   └── humanizer/               # 后处理
├── references/                  # 全局参考文档
├── SKILL.md                     # 本身的元数据
└── README.md                    # 完整使用指南
```

---

## 调试与问题排查

### "系统不知道该进入哪个模块"
→ 确保你的表述清晰。系统识别的关键词包括：
   - 对标、学习、风格
   - 规划、大纲、人物卡
   - 知识库、KB、数据库
   - 场景、清单、编制
   - 写章、第N章、写作
   - 互动、引导、干预
   - 去AI、清除、人类化

### "某个模块的产出格式不对"
→ 检查 `config/` 下的对应配置，或修改 `.xushikj/config/` 项目本地副本

### "路径找不到"
→ 确保 narrativespace-xushikj 的所有模块都完整复制到了 `.claude/skills/`

---

谢谢使用叙事空间创作系统！如有问题，请查阅各专用模块的详细文档。
