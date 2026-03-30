---
name: xushikj-changjing
description: |
  叙事空间创作系统·场景模块。执行步骤8-9：场景清单编制与场景规划。
  罗列所有场景并为每个场景规划必要信息。
metadata:
  version: 7.0.0
  parent: opencode-xushikj-chuangzuo
  steps: [8, 9]
  triggers:
    - 场景清单
    - 规划场景
---

# 场景模块 (opencode)

本模块负责当前 cycle 的场景规划，采用双层结构：

- Layer-1: Light Scene Card，写作准入必需
- Layer-2: Deep Scene Card，按需触发

目标是保证写作连续性，不再要求先完成全量深度场景。

## 需要加载的配置

| 配置文件 | 用途 | 必须 |
|----------|------|------|
| `.xushikj/config/meta_rules.yaml` | 输出语言与符号标准化 | 是 |
| `.xushikj/config/writing_rules.yaml` | 描写与表达规范（wr_07爽点密度约束） | 是 |
| `.xushikj/config/content_limits.yaml` | 内容门槛与禁限 | 是 |
| `.xushikj/config/quality_dimensions.yaml` | 质检维度参考 | 否 |

运行期配置必须来自 `.xushikj/config/`，不得回退读取 Skill 自带 `config/`。

## 输入状态

执行前读取 `.xushikj/state.json`：

- `rolling_context.cycle_id`
- `rolling_context.cycle_size`
- `rolling_context.cycle_status`
- `rolling_context.granularity`
- `rolling_context.next_cycle_hint`

## 场景目录规范（强制）

场景产物必须按 cycle 独立存放，禁止把多轮场景混写在同一层目录：

1. 根目录：`.xushikj/scenes/`
2. 轮次目录：`.xushikj/scenes/{cycle_id}/`
3. 清单文件：`.xushikj/scenes/{cycle_id}/scene_list.md`
4. 章节场景卡目录：`.xushikj/scenes/{cycle_id}/scene_plans/`
5. 单章场景卡：`.xushikj/scenes/{cycle_id}/scene_plans/chapter_{N}.md`

交接给写作模块时，必须在产出中显式返回 `scene_root=.xushikj/scenes/{cycle_id}`。

## Layer-1 轻量场景卡（必需）

当前 cycle 内每一章必须至少有 1 张 Layer-1 卡，字段最小集如下：

1. `chapter_or_scene_id`
2. `viewpoint_character`
3. `goal`
4. `conflict`
5. `expected_hook`
6. `expected_hook_type`（必填：`剧情反转` / `危机升级` / `悬念抛出` / `身份暗示` / `时间限制`）
7. `shuang_type`（必填：`small` / `big` / `transition`）

通过条件：只要当前 cycle 全章 Layer-1 齐备，即视为场景层面的最小可写条件满足。

密度约束：每连续 5 章至少 1 章 `shuang_type=big`。

## Layer-2 深化场景卡（可选）

Layer-2 仅在触发条件出现时补齐，不作为常规开写前置。

建议字段：

1. `tactical_beats`
2. `reaction_chain`
3. `info_gap_release`
4. `kb_diff_expectation`
5. `sensitivity_tag`

## Layer-2 触发条件（必须明确）

出现以下任一条件时，优先将对应章节升级为 Layer-2：

1. 高风险内容：`sensitivity_tag` 为 YELLOW 或 RED
2. 高复杂冲突：多方势力博弈、反转链、诡计解法
3. 重大叙事节点：卷中高潮、卷末决战、关键伏笔回收
4. 连续失稳迹象：近两章出现因信息不足导致的逻辑断裂
5. 里程碑节点：命中 8万/10万/20万字窗口对应章节
6. 黄金前三章：章节号 <= 3（强制升级）

### Layer-2 量化判定表

满足以下任一项即可直接升级为 Layer-2，无需主观二次判断：

1. `sensitivity_tag in [YELLOW, RED]`
2. 单章涉及 3 个及以上核心实体互动
3. 单章存在 2 次及以上连续反转或博弈链
4. 单章承担伏笔回收、卷中高潮、卷末决战三类节点之一
5. 黄金前三章或命中字数里程碑章节

若仅命中“信息不足导致的失稳迹象”，则先进入 `layer2_backlog`，由 `deepen` 阶段补齐。

## 非阻塞写作规则
## Layer-2 高风险场景三分支 ToT

**触发时机**：本场景已升级为 Layer-2（即命中了任一量化判定条件）。

当触发 Layer-2 时，必须评估以下三个并行分支，选择综合评分最高者后生成 Deep Scene Card：

| 分支 | 核心策略 | 爽感取向 | 风险 |
|------|----------|----------|------|
| 分支 A — 正面强攻 | 主角直接以压倒性优势解决冲突 | 即时多巴胺，爽感峰值高 | 过于顺利可能降低张力 |
| 分支 B — 险中求胜 | 主角在被压制到极限后以智慧/底牌翻盘 | 铺垫爽感，情绪跨度大 | 铺垫过长可能失读者 |
| 分支 C — 延迟爆破 | 本场景不完全释放，留下更大钩子给下一章 | 长线期待感叠加 | 短期爽感不足，需后续补偿 |

评分标准：
- 与当前 `shuang_tracker.consecutive_no_shuang` 联动：连续 0 爽章 ≥ 2 时，优先选分支 A 或 B
- 与 `line_heat.algorithm_tags` 联动：处于 `#爆更点` 的线条必须选 A 或 B
- 默认推荐：根据章节位置（奇数/偶数/卷末）自动给出推荐分支并说明理由

## 非阻塞写作规则

1. Layer-1 全章齐备即可交接写作。
2. Layer-2 未完成不构成全局阻塞。
3. 对已标记触发条件的章节，可采取“先补关键字段后写作”的局部补齐策略。

## 输出结构

本模块输出应包含：

1. `light_scene_cards`: 当前 cycle 的 Layer-1 卡列表
2. `deep_scene_cards`: 当前 cycle 已深化章节列表（可为空）
3. `layer2_backlog`: 尚未深化但建议后续处理的章节队列
4. `handoff_ready`: 是否满足写作交接（布尔值）

## 参考规则接入（新增）

本模块新增引用：`references/scene-execution-patterns.md`。

执行要求：

1. Layer-1 卡除最小字段外，建议补充“压力单元变化点”
2. 高风险章节在 Layer-2 中补全“中段转折”和“后效链条”
3. 场景复盘优先识别“空单元”（仅搬运信息、无净变化）并回退修正

## 与写作模块交接

当 `handoff_ready=true` 时，按 `config.writing_mode` 决定路由：

- `writing_mode=pipeline` → `opencode-xushikj-xiezuo`（流水线，自动逐章生成）
- `writing_mode=interactive` → `opencode-xushikj-hudong`（互动，用户帮回干预）
- 默认（未设置时）：按 `pipeline` 处理

若 `handoff_ready=false`，只返回缺失项，不得要求“先完成全书场景”。

## 典型示例

示例 A：3-5 粒度快速开写

- 输入：`cycle_size=4`
- 产出：4 张 Layer-1 卡，1 张 Layer-2（第4章高潮）
- 结果：`handoff_ready=true`，可直接开写

示例 B：复杂高潮前补深度

- 输入：下一章为卷中反转，且含 RED 标签
- 动作：仅对该章补 Layer-2，不阻塞前序低风险章节
- 结果：局部深化后继续写作
