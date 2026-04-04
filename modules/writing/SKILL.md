---
name: xushikj-xiezuo
description: |
  叙事空间创作系统·写作模块。执行步骤10：逐章创作。
  采用 orchestrator + 2 sub-agents 架构，集成帮回辅助系统、双保险机制、质量评估。
metadata:
  version: 8.2.0
  parent: narrativespace-xushikj
  step: 10
  triggers:
    - 写第N章
    - 开始写作
    - 继续写
---

# 写作模块 (opencode)

本模块是滚动创作中的正文执行器，按当前 cycle 写作，不依赖全书一次性规划。

## 写作入口契约

进入写作前必须执行最小可写门槛（Minimum Writable Threshold）检查。

最小可写包包含：

1. Core Meta：一句话梗概或一段式大纲 + 主角当前核心目标
2. Cycle Context：`cycle_id`、`cycle_size`、`cycle_status`
3. Layer-1 Scene Cards：当前 cycle 每章至少 1 张，且含 `goal` 或 `conflict`
4. Continuity Hint：`next_cycle_hint`

## 门槛判定

1. PASS：允许直接写作
2. FAIL：返回缺失项清单并请求补齐缺项

硬限制：FAIL 时不得要求用户先补完整本大纲或完整深度场景。

## Layer-1 Only 路径（必须支持）

当输入仅包含 Layer-1，且门槛 PASS：

1. 允许正常开写
2. 使用保守生成策略，优先保持剧情连续和角色一致
3. 对高风险段落打标，推送到 `layer2_backlog`，在后续 `deepen` 阶段补强

不允许因为 Layer-2 缺失直接拒写。

## 写作过程规则

1. 逐章消费当前 cycle 的 scene card
2. 每章结束产出 KB 增量建议
3. 更新当前循环进度与章节完成状态
4. 到达 cycle 边界时触发 `continue`

## 章节控制卡（新增）

每章开写前，必须先构造 `chapter_control_card` 并传递给章节写作 sub-agent。最小字段：

1. `carry_in_hook_check`：上一章钩子在本章开头的承接验证
2. `chapter_shuang_plan`：本章爽点类型与落点位置
3. `chapter_hook_plan`：章末钩子类型与悬念目标
4. `emotion_progression`：情绪推进路径（单向前进）
5. `no_repeat_info_list`：禁止重复解释的信息清单

## 强制执行约束（新增）

### 1) 配置生效约束

每章写作前必须显式加载并确认生效：

1. `.xushikj/config/writing_rules.yaml`
2. `.xushikj/config/style_rules.yaml`
3. `.xushikj/config/content_limits.yaml`
4. `.xushikj/config/meta_rules.yaml`
5. `.xushikj/config/quality_dimensions.yaml`
6. `.xushikj/config/self_check_rules.yaml`（写后自查闸门规则，用户可修改）
7. `.xushikj/config/human_touch_rules.yaml`（v8.0 人味注入规则）
8. `.xushikj/config/emotional_temperature.yaml`（v8.0 情绪温度配置）

若任一配置读取失败或为空，必须 HALT 并返回缺失项，禁止带病开写。

运行期不得回退读取 Skill 自带 `config/`。

### 1.1) 写后自查闸门（新增）

章节正文产出后、KB diff 应用前，orchestrator 必须执行写后自查闸门：

1. 规则源固定为 `.xushikj/config/self_check_rules.yaml`
2. 用户可随时修改该文件，下一章执行时必须读取最新版本
3. 命中 `severity=halt` 规则时，章节必须打回重写
4. 自查未通过时，禁止进入 KB diff、summary、state 推进
5. 自查结果写入 `.xushikj/quality_reports/chapter_{N}_self_check.md`

### 2) 字数硬门槛

按 `state.json.config.reply_length` 执行最小字数：

1. `A`：>= 5000
2. `B`：>= 4000
3. `C`：>= 2500
4. `D`：>= 2000（默认档，适合番茄等平台标准章节）

未达标时不得进入总结与质检，必须先补写到达标再继续。

当 `target_platform=fanqie` 时，追加硬门槛：

1. 单章超过 **3500 字** 时触发 HALT，要求拆分为两章后重新进入自查
2. 质量备注中需报告"当前字数 / 建议区间 2000-3500"

### 3) 场景文件路径

必须从按轮次目录读取场景卡：

1. `scene_root=.xushikj/scenes/{cycle_id}`
2. `scene_plan=.xushikj/scenes/{cycle_id}/scene_plans/chapter_{N}.md`

禁止读取或回写到扁平路径 `.xushikj/scenes/scene_plans/`。

### 4) KB 写回保护

应用 `kb_diff_patch` 后，保存前必须做 JSON 结构校验：

1. 顶层键存在性
2. `entities` 子结构完整性
3. JSON 可解析性

校验失败时禁止覆盖原 KB，必须返回错误并保留旧文件。

## 质量升级协议（新增）

当章节质检不通过时，按三段式升级执行：

1. 第一次失败：按问题清单做整章重写
2. 第二次失败：仅针对失败维度做定向重写
3. 第三次失败：停止盲重写，先定位根因（大纲/角色/节奏/主题承压），再修复

完成润色后必须执行迷你复查：

1. 连续性事实是否保持
2. 主角与关键角色口吻是否回归
3. 关系压力读数是否被削平
4. 章末钩子与残留义务是否仍成立

## v8.0 新增特性

### 行文DNA约束（最高优先级）

当 `.xushikj/config/style_modules/dna_human_*.yaml` 存在时：
- 自动注入 write_constraints，优先级高于 clone_*.yaml 和所有内置模块
- chapter-writer sub-agent 新增 Self_Audit Q8（DNA 合规自检）
- critic sub-agent 新增红线四（DNA 严重偏离 → 退稿）

### 情绪温度系统

读取 `.xushikj/config/emotional_temperature.yaml`，基于场景类型自动匹配温度曲线：
- cold（1-3）：感官削减，叙述拉远
- warm（4-6）：正常情感密度
- hot（7-10）：感官过载，短句爆发

### 人味注入规则

读取 `.xushikj/config/human_touch_rules.yaml`，ht_01~ht_06 六条规则强制执行：
不完美注入 / 节奏打破 / 非视觉感官锚定 / 内心声音真实化 / 微矛盾 / 叙事距离切换。

### 记忆锚点系统

每章完成后自动生成 ≤150 字记忆锚点（关键转折/悬念/情绪快照/债务），保存到 `.xushikj/anchors/`。
下一章开写前自动加载最近 3 章锚点，确保跨章衔接。

## 偏移报警与自动停机（新增）

出现以下信号时触发偏移控制：

1. 连续 2 章无爽点兑现：`WARN`
2. 连续 2 章章末钩子失败：`HALT`
3. 连续 3 章低于番茄推荐字数（当目标平台为 fanqie）：`WARN`
4. 连续 3 章 KB 无有效增量：`WARN`
5. 连续 2 章主角被压制且无反击：`ALERT`

## 硬拒收条件（新增）

命中任一项，章节必须退回重写：

1. 章末 200 字内无有效钩子
2. 本章无爽点兑现且与场景卡 `shuang_type` 不一致
3. 开篇 300 字未进入动态冲突（静态铺垫/设定灌输）
4. 对话占比极端失衡（<20% 或 >80%）
5. 与 KB 或前文事实发生显著冲突

## 输出要求

每章至少输出：

1. chapter_draft
2. quality_notes
3. kb_diff_patch
4. next_chapter_risk_flags

## 自动落盤规则

本模块为流水线模式（pipeline），每章写作完成后**自动触发**以下后处理流程：

1. KB diff 验证与应用（调用 `xushikj-zhishiku` 或 `apply_kb_diff.py`）
2. 章节概括生成 + `summaries/summary_index.md` 更新
3. 八维度质量评估（HC1-HC6）
4. `state.json` 章节号 +1，推进进度

**注**：此自动落盤与互动模式（xushikj-hudong）的"用户说'OK落盤'才触发"形成对比。

## 参考规则接入（新增）

本模块在生成与复盘章节时，新增引用以下规则文档：

1. `references/dialogue-writing-rules.md`
2. `references/chapter-architecture-rules.md`
3. `references/line-heat-continuity.md`

执行顺序建议：

1. 门槛通过后先按 `chapter-architecture-rules` 确认本章 Mission/Turn/Residue
2. 正文生成中按 `dialogue-writing-rules` 约束关键对话
3. 章后复盘时同时检查“中段转折是否成立”与“关系压力是否变化”
4. 章后回写按 `line-heat-continuity` 更新角色线/情节线/伏笔线热度

## 异常与回退

1. 缺章卡：返回缺失章节列表
2. 状态冲突：提示按 `cycle_id` 对齐后重试
3. 旧项目无 rolling 字段：触发迁移补全后再执行门槛检查

## 示例

示例 A：Layer-1 即开写

- 输入：`cycle_size=3`，1-3 章均有 Layer-1，无 Layer-2
- 结果：PASS，正常进入写作

示例 B：缺少第 3 章卡

- 输入：`cycle_size=3`，仅第 1-2 章有 Layer-1
- 结果：FAIL，返回“缺失第3章 Layer-1 场景卡”
