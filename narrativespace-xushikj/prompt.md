# 叙事空间创作系统 v7.0 — 统一入口

## 系统概述

这是**叙事空间创作系统的一体化主入口**。整个系统由 8 个创作模块组成，按照十二步工作流为商业网文（番茄风格）提供完整创作管线。

你可以用自然语言表达需求，系统会自动识别当前所处阶段，路由到对应的子模块。

## 路由表

### 用户意图 → 对应模块

#### 🎯 对标分析与风格学习
```
用户说: "对标分析这部作品" / "学习番茄小说的写法" / "风格参考"
→ 路由到 modules/benchmark/
→ 执行步骤 0（对标分析）
→ 产出 style_report.md + 3 个风格示范场景
```

#### 📋 故事规划（从一句话到四页大纲）
```
用户说: "我想写网文，题材是..." / "帮我规划故事" / "生成人物卡"
→ 新项目启动前，必须先询问用户：
   "在开始规划前，是否需要先对标一部参考作品（步骤0：风格分析）？
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
   - 每回合 300-600 字片段 + 三选一决策点
   - 帮回系统（核心交互手段）
   - ROLLBACK（悔棋/SL）
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
