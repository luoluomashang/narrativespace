---
name: xushikj-hudong
description: |
  叙事空间创作系统·沉浸式跑团推演引擎。
  AI=DM/导演，用户=玩家/主角。每回合 300-600 字片段 + 三选一决策点。
  帮回系统为核心操控手段，支持 ROLLBACK(SL) + 滑动窗口 + 落盘质检。
metadata:
  version: 3.0.0
  parent: opencode-xushikj-chuangzuo
  triggers:
    - 互动写作
    - 开始互动
    - 帮回
    - 跑团模式
    - TRPG推演
    - 沉浸式互动
    - 跑团
---

# 沉浸式跑团推演引擎 (opencode)

本模块将互动式写作从"代笔审稿器"升级为**沉浸式 TRPG 推演引擎**：

- **旧模式**：AI 生成整章 → 用户审阅"改/重写/OK落盘"
- **新模式**：AI=DM 每回合生成 300-600 字片段 → 强制截断在决策点 → 用户选择/输入 → 循环至落盘

核心原则：**Agency Isolation** — AI 负责环境、配角、突发事件；绝对禁止替主角做决策、说核心台词、亮底牌。

## 统一入口规则

跑团模式与流水线模式共享以下底层约束：

1. `granularity` 语义一致，粒度切换遵循"下个 cycle 生效"规则
2. 仍遵循同一套 KB diff（延迟到落盘由 maintenance agent 提取）、质检标准
3. TRPG 下 1 cycle = 1 章，`cycle_size` = 1

跑团模式使用 **Interactive Minimum Writable Threshold**：

1. Core Meta：`one_sentence.md` 或 `one_paragraph.md`
2. Character Baseline：`.xushikj/outline/characters/` 目录中至少包含主角与关键配角
3. Cycle Context：`cycle_id`、`cycle_status`、`granularity`
4. KB Lite：`knowledge_base.json` 已完成精简初始化
5. User Direction：用户明确表示进入跑团/互动模式

**不要求**：Layer-1 场景卡、四页大纲、场景清单、场景规划。

## 前置依赖

| 步骤 | 产出文件 | 是否必须 |
|------|----------|---------|
| 1 | `.xushikj/outline/one_sentence.md` | 是 |
| 2 | `.xushikj/outline/one_paragraph.md` | 是 |
| 2.5 | `.xushikj/outline/worldview_and_system.md` | 条件触发 |
| 3 | `.xushikj/outline/characters/` 目录 | 是 |
| 7 | `knowledge_base.json`（精简初始化） | 是 |

**不需要**：四页大纲（步骤6）、场景清单（步骤8）、场景规划（步骤9）

知识库精简初始化说明：只初始化人物实体 + 基本关系；若步骤 2.5 未触发，则不强制要求 world/system 文件存在；地点/物品在写作中由 KB diff 动态创建。

## 需要加载的配置

| 配置文件 | 用途 | 必须 |
|----------|------|------|
| `.xushikj/config/meta_rules.yaml` | 输出语言与符号标准化 | 是 |
| `.xushikj/config/writing_rules.yaml` | 描写与表达规范 | 是 |
| `.xushikj/config/style_rules.yaml` | 语言风格与去模板化 | 是 |
| `.xushikj/config/content_limits.yaml` | 内容门槛与禁限 | 是 |
| `.xushikj/config/quality_dimensions.yaml` | 质检八维度（HC1-HC6） | 是 |
| `.xushikj/config/bangui_modes.yaml` | 帮回系统配置（触发词、执行模式） | 是 |
| `.xushikj/config/self_check_rules.yaml` | 落盘质量门禁（LANDING 时使用） | 是 |
| `.xushikj/config/golden_opening.yaml` | 黄金前三章特殊规则 | 否 |

运行期配置必须来自 `.xushikj/config/`，不得回退读取 Skill 自带 `config/`。
所有配置在 INIT 阶段一次性编译为 `write_constraints` 摘要（≤500 字），后续每回合只传摘要。

## 必读状态

执行前读取 `.xushikj/state.json`：

- `rolling_context.cycle_id`
- `rolling_context.cycle_status`
- `rolling_context.granularity`
- `rolling_context.pending_granularity`
- `rolling_context.next_cycle_hint`

## 状态机

```
INIT → OPENING → PING_PONG ⇄ ROLLBACK → PACING_ALERT → LANDING → MAINTENANCE → (下一章)
```

- **INIT**：校验准入 + 加载配置 + 编译 write_constraints + 创建 drafts/ 目录 + 断点续做检查
- **OPENING**：用户确认本章方向
- **PING_PONG**：核心循环——DM sub-agent 产出片段 + 用户决策
- **ROLLBACK**：用户"撤回/SL"→ 砍最后片段 → 重新生成分支
- **PACING_ALERT**：≥1500 字后提示收尾，持续到落盘
- **LANDING**：冻结草稿 + self_check 质量门禁 + 写入正式章节
- **MAINTENANCE**：KB diff 提取（时间轴扫描）+ 概括 + 质量评估

## 落盘机制

- **推演中 = 草稿态**，每回合追加写入 WIP 文件（`.xushikj/drafts/chapter_{N}_wip.md`）
- **用户说"落盘"/"本章结束"** 才触发 LANDING → MAINTENANCE：
  1. self_check_rules 质量门禁（HALT 级可退回继续推演）
  2. 写入 `chapters/chapter_{N}.md`
  3. maintenance agent Step 0：从完整 WIP 时间轴扫描提取 KB diff
  4. KB diff 验证与应用
  5. 章节概括 + `summaries/summary_index.md` 更新
  6. 质量评估（HC1-HC6）
  7. `state.json` 章节号 +1

## 帮回系统集成

帮回系统在跑团模式中是**核心交互手段**。三大类指令：

### 甲类（即时行动 / 对话 / 叙事辅助，共 8 个）

| 触发词 | 说明 |
|--------|------|
| `帮回主动1` | 角色果断行动，目标推进，情感外放 |
| `帮回主动2` | 角色策略性主动，语言操控，智慧铺垫 |
| `帮回被动1` | 外部压力导致的犹豫退让或策略性隐忍 |
| `帮回被动2` | 内在情感驱动的依赖、慰藉或消极承受 |
| `帮回黑暗1` | 心理层面：掌控欲、操控、冷漠、病态执念 |
| `帮回黑暗2` | 行动层面：侵略性、占有性或禁忌挑战（受 sensitivity 约束） |
| `帮回推进1` | 第三方叙事旁白：宏大叙事 / 关键转折 |
| `帮回推进2` | 第三方叙事旁白：感官细节深化 / 微表情+心理 |

执行模式：
- **模式一（默认）**：直接作为 DM sub-agent 的 bangui_context 注入
- **模式二（加 `[选项]` 后缀）**：先呈现 2-3 个方向选项，用户选定后执行

快捷语法：`/帮回主动1` 或 `帮回主动1`（斜杠可省略）

### 乙类（章节规划）

触发词：`帮回章节规划`

orchestrator 在主进程内生成当前章节规划方案，不派发 DM sub-agent。

### 丙类（分析诊断）

触发词：`帮回分析`

orchestrator 在主进程内执行分析，输出当前剧情健康度、风险点、改进建议。

## 概要注入策略

| 阶段 | 条件 | 注入方式 |
|------|------|---------|
| 早期 | 已落盘章节 ≤ 3 | 仅前章末尾 500 字衔接 |
| 中期 | 已落盘章节 > 3 且概要总字数 < 4000 | 完整概要 + 前章末尾 |
| 后期 | 概要总字数 ≥ 4000 | 完整概要注入 DM sub-agent，由其自行压缩理解 |

**关键约束**：orchestrator 绝不压缩概要——前文剧情已存在于主进程对话历史，随 compact 自动压缩。

## TRPG 推演执行

1. 校验 Interactive Minimum Writable Threshold → INIT
2. 用户确认本章方向 → OPENING
3. 每回合：解析用户决策 → 构建 KB 切片 + 滑动窗口 → 启动 DM sub-agent → 拼接片段 → 写入 WIP → PING_PONG
4. 可选：用户"撤回" → ROLLBACK → 重新生成 → 回到 PING_PONG
5. 字数 ≥1500 → PACING_ALERT（提示收尾但不强制）
6. 用户"落盘" → LANDING（self_check 质量门禁） → 写入正式章节
7. → MAINTENANCE（时间轴扫描 KB diff + 概括 + 评估）
8. 下一章循环

## 滑动窗口机制

- 累积 ≤1000 字：DM sub-agent 接收全量 draft
- 累积 >1000 字：传入"固定模板摘要（≤200 字）+ 最近 800 字原文"
- WIP 文件始终保存完整草稿（唯一真实来源）

## ROLLBACK 机制

- 触发词："撤回"/"重骰"/"退回上一步"/"SL"
- 砍掉最后一个回合片段 → 更新 WIP → 重新调用 DM sub-agent 生成新分支
- 限制：单次只能退 1 个回合；连续第二次需确认

## 偏航反馈回路

当用户要求临时改线、插支线或改人物动机时：

1. 当前章优先满足用户即时意图
2. 记录 `deviation_log`
3. 生成 `planning_backlog_updates`
4. 在 `continue` 或 `deepen` 阶段将偏航回写给 `guihua/changjing`

## 产出文件

```
.xushikj/
├── drafts/chapter_{N}_wip.md       ← TRPG 新增：推演中草稿
├── chapters/chapter_*.md
├── kb_diffs/chapter_*_diff.json
├── summaries/
│   ├── chapter_*_summary.md
│   └── summary_index.md
└── quality_reports/chapter_*_quality.md
```

## 专属资源

| 资源 | 路径 |
|------|------|
| DM sub-agent 提示词 | `modules/interactive/references/interactive-writer-sub-agent-prompt.md` |
| maintenance agent 提示词 | `modules/interactive/references/maintenance-agent-prompt.md` |
| KB diff schema | `xushikj-xiezuo/references/kb-diff-schema.md` |
| KB diff 应用脚本 | `xushikj-xiezuo/scripts/apply_kb_diff.py` |
| 全部运行时 config 文件 | `.xushikj/config/*.yaml` |

## 与流水线模式的关键差异

| | 流水线（xushikj-xiezuo） | 跑团推演（xushikj-hudong） |
|--|--|--|
| 交互范式 | 单向管道：场景规划→整章生成→落盘 | TRPG 循环：DM 推演→用户决策→追加片段 |
| 单次产出 | 整章（2000-5000 字） | 片段（300-600 字） |
| sub-agent | chapter-writer sub-agent | **DM sub-agent**（专用） |
| 场景规划来源 | 预写文件 | 用户实时决策 |
| KB diff 生成 | writer sub-agent 同步生成 | **maintenance agent 落盘时提取**（时间轴扫描） |
| 草稿管理 | 内存中 | **WIP 文件持久化** + 滑动窗口 |
| 落盘时机 | 自动 | **用户触发** |
| 概要注入 | 固定最近 3 章 | 阶梯式（早/中/后期） |
| 帮回系统 | 挂载但无自然触发点 | **核心交互手段** |
| 回退能力 | 重写整章 | **ROLLBACK**（回退单回合 + 重新分支） |
| self_check | 每章同步检查 | **LANDING 阶段质量门禁** |

## 与粒度切换协同

1. 当前 cycle 内：继续按当前 `granularity` 执行
2. 用户请求切换：仅写入 `pending_granularity`
3. 下一轮 cycle 启动：应用挂起切换

## 备注

1. 跑团推演与流水线写作地位平等，在完成前置依赖后由用户选择（或由 `config.writing_mode` 决定）
2. `state.json` 中 `config.writing_mode=interactive` 标记跑团模式，断点续做时自动路由
3. 跑团模式不要求预写 Layer-1 场景卡，但仍遵循 cycle 滚动语义和质检标准
4. `current_sensitivity` 在章内只升不降（GREEN→YELLOW→RED），落盘后随新章重置
