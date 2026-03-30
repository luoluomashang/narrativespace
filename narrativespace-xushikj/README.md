# 叙事空间创作系统 v7.0 — 完整使用指南

本文档适用于 **narrativespace-xushikj** 一体化版本。该版本将原来的 8 个 Skill 统一打包成1个，安装和使用方式简化如下。

## 快速安装

### 系统要求
- Claude Code 环境
- 一个项目目录

### 安装步骤

1. **复制 Skill 文件夹**

```bash
# 原方式（8个文件夹）
cp -R xushikj-chuangzuo xushikj-guihua xushikj-duibiao \
      xushikj-changjing xushikj-xiezuo xushikj-hudong \
      xushikj-zhishiku humanizer-xiaoshuo \
      /你的项目/.claude/skills/

# 新方式（1个文件夹）✨
cp -R narrativespace-xushikj /你的项目/.claude/skills/
```

2. **项目初始化**

```bash
python narrativespace-xushikj/scripts/init.py --project-dir /your/project/path
```

这会自动：
- 创建 `.xushikj/` 工作目录
- 同步 `config/` 文件到项目本地
- 初始化 `state.json`, `knowledge_base.json`, 等文件

3. **重启 Claude Code**

开一个新的对话，输入 "叙事空间" 或 "写网文" 即可开始。

---

## 系统架构全貌

### 8 个创作模块

整个系统由 8 个高度专业化的模块组成：

```
                    ┌─────────────────────────────────┐
                    │  narrativespace-xushikj (主root) │
                    └──────────────┬──────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
    ┌─────────┐             ┌──────────────┐          ┌──────────────┐
    │benchmark│             │   planning   │          │  knowledge   │
    │(步骤0)│             │ (步骤1-6,11) │          │   -base      │
    │对标分析│             │    规划      │          │  (步骤7)    │
    └─────────┘             └──────────────┘          │    知识库    │
                                                      └──────────────┘
        │
        ▼
    ┌─────────────┐        ┌──────────┐         ┌───────────┐
    │   scenes    │        │ writing  │         │interactive│
    │ (步骤8-9) │        │(步骤10A) │         │(步骤10B) │
    │  场景规划   │        │流水线写作 │         │互动写作  │
    └─────────────┘        └──────────┘         └───────────┘
        │
        └──────────────────────────┬─────────────────────────┘
                                   │
                                   ▼
                           ┌──────────────┐
                           │ humanizer    │
                           │   (后处理)   │
                           │  去AI痕迹   │
                           └──────────────┘
```

### 十二步工作流

| 步 | 模块 | 描述 | 输入 | 输出 |
|----|------|------|------|------|
| **0** | benchmark | 对标作品学习 | 1-3部对标作品 | style_report.md + 场景示范 |
| **1** | planning | 一句话概括 | 题材/主角 | one_sentence.md |
| **2** | planning | 一段话展开 | 核心设定 | one_paragraph.md |
| **2.5** | planning | 机制确认 | 故事类型 | 选项列表确认 |
| **3** | planning | 人物设定 | 核心冲突 | 3-5 人物卡 |
| **4** | planning | 一页大纲 | 人物卡 | volume_1_one_page.md |
| **5** | planning | 弧光充实 | 一页大纲 | character_arcs.md |
| **6** | planning | 四页大纲 | 弧光分析 | volume_1_four_pages.md |
| **7** | knowledge-base | KB初始化 | 四页大纲 | knowledge_base.json |
| **8** | scenes | 场景清单 | 大纲 | scene_list.md |
| **9** | scenes | 场景规划 | 场景清单 | scenes/*/beat_plans |
| **10A** | writing | 流水线写作 | 场景规划 | 章节 + KB diff + 质量报告 |
| **10B** | interactive | 互动写作 | 用户指示 | 章节 (迭代) |
| **11** | planning | 书名简介 | 完成稿 | 标题 + 简介 |
| **后** | humanizer | 去AI痕迹 | 原稿 | 去AI版本 |

---

## 使用方式

### 模式 1：完整创作流程（从零开始）

```
你: "我想写网文，都市系统类。"
系统: 那我们一步步来。先做对标分析吗？或直接规划？

你: "有3部对标作品。"
系统: [进入步骤0，对标分析]
      [输出style_report.md]
      现在开始规划阶段...

你: 一句话描述你的故事。
系统: [进入步骤1-6，完整规划]
      [输出所有规划文件]
      
你: 规划看起来不错。
系统: 现在初始化知识库...
      [进入步骤7]
      [输出knowledge_base.json]
      
系统: 现在规划各章场景...
      [进入步骤8-9]
      [输出scene_list.md + 场景规划]
      
你: 准备好写了。
系统: 选择流水线还是互动模式？

你: 流水线，自动写第1-3章。
系统: [进入步骤10A]
      [输出3章完整文本 + 质量报告]
```

### 模式 2：跳步执行

如果你已经有完整大纲，可以直接跳到某一步：

```
你: "我已经有四页大纲了，直接初始化知识库。"
系统: 确认你有这些文件...
      [进入步骤7]
      [输出knowledge_base.json]
      
你: "现在写第一章。"
系统: [进入步骤10A]
      [输出chapter_1.md]
```

### 模式 3：切换写作方式

两种写作模式可以随时切换：

```
你: "用流水线模式写第1-3章。"
系统: [进入步骤10A，写作3章]

你: "现在我要互动写第4章。"
系统: [切换到步骤10B，互动模式]
      现在由你引导...
      
你: "让主角在这里背叛。"
系统: [实时修改剧情]

你: "好，这章就这样了，进行下一章。"
系统: [落盤确认，继续下一章]

你: "第5章继续用流水线吧。"
系统: [切换回步骤10A]
```

---

## 关键文件说明

### 项目结构

创建项目后，你的目录会是这样：

```
你的网文项目/
├── .claude/skills/
│   └── narrativespace-xushikj/       # ← Skill根目录（从此处复制）
│       ├── config/                   # 配置文件
│       ├── templates/                # 输出格式模板
│       ├── modules/                  # 8个创作模块
│       ├── scripts/                  # 工具脚本
│       └── ...
│
└── .xushikj/                         # ← 项目本地工作目录（init.py创建）
    ├── config/                       # 项目专用配置（from template）
    ├── state.json                    # 当前进度
    ├── knowledge_base.json           # 实体库
    ├── outline/
    │   ├── characters/
    │   ├── one_sentence.md
    │   ├── one_paragraph.md
    │   └── ...
    ├── benchmark/
    │   └── style_report.md
    ├── scenes/
    │   ├── cycle_1/
    │   │   ├── scene_list.md
    │   │   └── scene_plans/
    │   └── ...
    └── chapters/                     # 写好的章节
        ├── chapter_1.md
        ├── chapter_2.md
        └── ...
```

### 配置文件（config/）

新项目会自动同步这些配置到 `.xushikj/config/`：

- `foundational_principles.yaml` — 底层创作原则（因果、人物、主题）
- `writing_rules.yaml` — 写作强约束（平台打法）
- `style_rules.yaml` — 语言风格和去模板化
- `benchmark_triggers.yaml` — 对标基准和降权策略
- `quality_dimensions.yaml` — 8维质量评分标准
- `style_modules/` — 风格模块（悬疑/爱情/奇幻等）

**重要**：修改时优先改 `.xushikj/config/` 下的项目本地副本，不要直接改 Skill 的`config/`。前者只影响当前项目，后者影响所有新项目。

### 模板文件（templates/）

定义各步骤的输出格式：

- `state_template.json` — 项目状态模板
- `kb_template.json` — 知识库模板
- `memory_template.md` — 回忆录模板
- `summary_index_template.md` — 总结索引
- `user_settings_template.md` — 用户设置

---

## 规划阶段的交互方式

**重要规则**：规划阶段必须是强交互式的。系统不会一次性生成完整设定，而是逐步了解你的需求。

### 正确的执行顺序

1. **第一步**：系统先问关键信息（题材、主角、平台、禁区等）
2. **每个小步骤前**：系统再问该步骤本身的具体需求
3. **信息足够后**：系统才生成当前步骤的草案
4. **草案生成后**：等待你确认或修改，不自动往下跑
5. **你确认后**：才进入下一步

### 示例

```
你: "写网文"

系统: 我需要了解几个关键信息：
    1. 想写什么类型？(都市/奇幻/悬疑等)
    2. 主角是什么身份？
    3. 目标读者平台？(番茄/起点等)
    4. 有没有内容禁区？

你: "都市，打工仔，番茄，无特殊禁区"

系统: 好的。现在开始规划--请用一句话概括这个故事的核心卖点。

你: [给出一句话]

系统: [生成 one_sentence.md]
      确认这个一句话概括吗？需要修改吗？

你: "改一下，加上系统元素"

系统: [修改后重新生成]
      这样可以吗？

你: "可以"

系统: 现在词在写开头，需要进一步展开。故事的主线矛盾是什么？爽点偏什么方向？

你: [详细描述]

系统: [生成 one_paragraph.md]
```

**关键**：如果你希望某部分由系统自由发挥，可以直接说 "这部分你先提案"。系统会先给方案，但仍需你确认。

---

## 两种写作模式详解

### 流水线模式（脚本执行）

**适合场景**：已有清晰大纲，想高效产出

**特点**：
- 系统自动按场景规划逐章生成
- 你在章间审阅、批注修改意见
- 自动落盤进入下一章
- 支持子 agent 架构（章节写手 + 总结官）
- 内置帮回辅助系统和双保险质量控制

**流程**：
```
场景规划 → 自动写作 → 质量评分 → 你审阅 → 通过/修改 → 落盤 → 下一章
```

### 互动模式（用户驾驶）

**适合场景**：想深度参与故事走向，实时调整

**特点**：
- 章内可随时干预（"让这里改成背叛"）
- 帮回系统辅助用户指示
- 需要你主动说 "OK落盤" 才推进
- 更适合关键剧情节点

**流程**：
```
你的指示 → 帮回理解 → 系统执行 → 生成片段 → 你确认/修改 → 帮回反馈 → 循环 → 最终落盤
```

---

## 去 AI 痕迹处理 (humanizer)

完成写作后，可以一键清除 AI 生成痕迹。

**处理层次**：
1. **主规则层**（R1-R7+可选R8）：小说场景的快速清洗
   - 去除宣传性语言
   - 修复象征意义夸大
   - 消除 AI 问候式讨好语
   
2. **二级扫描层**（吸收humanizer-zh）：24类AI痕迹模式补漏
   - 内容模式（空泛展望、模糊归因）
   - 语言模式（AI词簇、否定排比滥用）
   - 风格模式（破折号/粗体过多）
   - 聊天痕迹（知识截止声明残留）

**安全边界**：不修改情节事实、人物关系、世界规则。仅处理表达层和可读性层。

---

## 常见问题

**Q: 系统说找不到 state.json？**  
A: 正常现象。state.json会在你第一次开始创作时自动生成。

**Q: 可以跳过某些步骤吗？**  
A: 可以。但系统会先确认你已有相應输入（比如跳过规划要有完整大纲）。不会擅自补写关键设定。

**Q: 写到一半想改大纲怎么办？**  
A: 直接改对应的文件，告诉系统 "大纲已更新"。知识库和场景规划可能需要同步更新。

**Q: humanizer 会改我的情节吗？**  
A: 不会。它只处理表达层面的 AI 痕迹（句式、用词、排版）。不触碰情节和人物行为。R8规则会删除无用细节，但默认关闭。

**Q: 两种写作模式可以混用吗？**  
A: 可以。任何时刻都能切换。前几章流水线快速推进，关键节点切换互动精雕细琢，再切回流水线。

**Q: 8个模块是怎么交互的？**  
A: 通过state.json追踪进度，各模块读取当前状态，执行对应步骤，输出结果保存到.xushikj/，自動更新state。完全解耦，无直接调用。

---

## 目录结构速览

```
narrativespace-xushikj/
├── SKILL.md                        # 本Skill的元数据
├── prompt.md                       # 主路由提示词（内含路由逻辑）
├── README.md                       # 本文档
│
├── config/                         # 全局配置种子（被 init.py 同步）
│   ├── foundational_principles.yaml
│   ├── writing_rules.yaml
│   ├── style_rules.yaml
│   ├── benchmark_triggers.yaml
│   ├── quality_dimensions.yaml
│   ├── safety_guard.yaml
│   └── style_modules/              # 按需加载的风格模块
│       ├── suspense.yaml
│       ├── romance.yaml
│       ├── mystery.yaml
│       └── ...
│
├── templates/                      # 项目初始化用的模板
│   ├── state_template.json
│   ├── kb_template.json
│   ├── memory_template.md
│   ├── summary_index_template.md
│   └── user_settings_template.md
│
├── scripts/                        # 工具脚本
│   ├── init.py                     # 项目初始化
│   └── apply_kb_diff.py            # KB更新脚本
│
├── modules/                        # 8个创作模块
│   ├── benchmark/                  # 步骤0：对标分析
│   │   ├── SKILL.md
│   │   └── prompt.md
│   │
│   ├── planning/                   # 步骤1-6+11：规划
│   │   ├── SKILL.md
│   │   ├── prompt.md
│   │   └── references/
│   │       └── character-construction-rules.md
│   │
│   ├── knowledge-base/             # 步骤7：知识库
│   │   ├── SKILL.md
│   │   └── prompt.md
│   │
│   ├── scenes/                     # 步骤8-9：场景规划
│   │   ├── SKILL.md
│   │   ├── prompt.md
│   │   └── references/
│   │       └── scene-execution-patterns.md
│   │
│   ├── writing/                    # 步骤10A：流水线写作
│   │   ├── SKILL.md
│   │   ├── prompt.md
│   │   ├── references/             # 8份增强文档
│   │   │   ├── chapter-writer-sub-agent-prompt.md
│   │   │   ├── summary-sub-agent-prompt.md
│   │   │   ├── kb-diff-schema.md
│   │   │   ├── dialogue-writing-rules.md
│   │   │   ├── chapter-architecture-rules.md
│   │   │   └── line-heat-continuity.md
│   │   └── scripts/
│   │       └── apply_kb_diff.py
│   │
│   ├── interactive/                # 步骤10B：互动写作
│   │   ├── SKILL.md
│   │   ├── prompt.md
│   │   └── references/
│   │       └── maintenance-agent-prompt.md
│   │
│   └── humanizer/                  # 后处理：去AI痕迹
│       ├── SKILL.md
│       └── prompt.md
│
└── references/                     # 全局参考文档
    └── original-prompt-sections/   # 系统设计原始文档
        ├── part1-methodology.md
        ├── part2-workflow.md
        ├── part3-writing-engine.md
        ├── part4-settings.md
        └── appendix-a-genres.md
```

---

## 技术细节

### 状态机（State Machine）

系统用 `state.json` 追踪创作进度：

```json
{
  "current_step": 7,
  "completed_steps": [0, 1, 2, 3, 4, 5, 6],
  "rolling_context": {
    "cycle": 1,
    "cycle_status": "planning",
    "granularity": "3-5 chapters per cycle"
  },
  "project_name": "裂隙倒计时",
  "config": { ... },
  "files": { ... }
}
```

### 知识库（Knowledge Base）

基于 EX3 论文的动态实体追踪：

```json
{
  "characters": [
    {
      "id": "char_001",
      "name": "林默",
      "description": "...", 
      "arc_stage": "触发期",
      "relationships": {...}
    }
  ],
  "locations": [...],
  "items": [...],
  "abilities": [...],
  "timeline": [...],
  "foreshadowing": {...}
}
```

每章写完后，系统会生成 KB diff，更新实体状态。

### 质量保证栈

- **8维度评分**（qd_01-qd_08）—— 修辞、感官、角色、对话、一致、主题、语言、场景
- **HC检查**（HC1-HC6）—— 字数、完成、衰减、逻辑、AI特征、钩子
- **灵敏度控制**（sensitivity_tag）—— GREEN/YELLOW/RED，控制敏感内容注入
- **否决维度**（veto_dimensions）—— 3项硬性失败条件

---

## 联系与反馈

Questions? Issues? 查看各模块的详细文档：

- `modules/benchmark/SKILL.md` — 对标分析
- `modules/planning/SKILL.md` — 规划模块  
- `modules/knowledge-base/SKILL.md` — 知识库
- `modules/scenes/SKILL.md` — 场景规划
- `modules/writing/SKILL.md` — 写作模块
- `modules/interactive/SKILL.md` — 互动模块
- `modules/humanizer/SKILL.md` — 去AI处理

---

**版本**：7.0.0（一体化合并）  
**最后更新**：2026-03-31  
**状态**：生产就绪 ✅
