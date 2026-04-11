---
name: xushikj-duibiao
description: |
  叙事空间创作系统·对标分析模块。执行步骤0：对标作品学习与风格解析。
  分析对标作品的文风、世界观、情节套路和实体信息，生成风格报告。支持 quick（单段快速）/ standard（12-20章分层采样）/ deep（30章+高精度）三种 sample_scope 模式。
metadata:
  version: 8.4.0
  parent: narrativespace-xushikj
  step: 0
  triggers:
    - 对标学习
    - 风格分析
    - 学习作品风格
---

# 对标分析模块 (opencode)

本模块在滚动创作中定位为可选强化模块，不是每个 cycle 的强制步骤。

## 角色边界

1. 提供风格锚点、题材节奏锚点、爽点密度参考
2. 为 `guihua/xiezuo` 提供可执行的风格约束
3. 为主入口提供 `benchmark_group` 绑定建议（primary/support）
3. 不直接阻塞写作主流程

## 推荐使用时机

1. 新项目冷启动前（推荐）
2. 连载中段风格漂移时（按需）
3. 准备冲榜或阶段性改稿前（按需）

## 非阻塞规则

1. 若用户跳过对标分析，系统仍可按最小可写门槛进入写作
2. 若已有历史风格样本，可直接复用，无需每轮重做

## 脚本组装前置闸门（HARD STOP）

执行本模块前，必须先通过 `scripts/assemble_prompt.py` 组装步骤0提示词并确认输出已生成。

1. 未确认组装完成时，禁止直接生成对标分析正式产物。
2. 此时只允许返回应执行的组装命令与必要说明，等待用户确认。
3. 禁止以“已读取部分配置文件”替代步骤组装。

## 与写作模式关系

对标分析为可选强化模块，不随 writing_mode 改变触发时机。
pipeline（xushikj-xiezuo）和 interactive（xushikj-hudong）两种模式都可复用同一份对标结果。

## 输出契约（新增）

对标分析结束时，除风格报告外必须额外输出：

1. `benchmark_binding.primary_group`
2. `benchmark_binding.support_group`（可为空）
3. `benchmark_binding.down_weighting`（如慢热/克制/反套路）
4. `benchmark_binding.reason`（简要说明匹配依据）

该结构供 `xushikj-chuangzuo` 写入 `state.json.benchmark_state`，用于后续 cycle 路由与风格模块加载。

## 滚动模式示例

示例 A：首次建书

- 先跑一次对标，提炼风格参数
- 后续多个 cycle 直接复用，不强制每轮调用

示例 B：中途偏风格

- 第 6 轮出现文风偏移
- 触发一次对标校正，再回写到后续 cycle

## 场景化切片提取（新增）

对标分析除风格报告外，还必须提取 5 个场景化文本切片：
1. 切片覆盖类型：combat / face_slap / daily / emotional / system
2. 每切片 200-500 字，标注 scene_type 标签
3. 存储路径：主路径 `~/.narrativespace/style_library/{author_slug}/`；项目内回退路径 `.xushikj/benchmark/style_snippets/`
4. 后续 xushikj-xiezuo 根据当前章节场景类型动态提取匹配切片作为 Few-Shot 注入

### 工具写入方式（新增）

LLM 产出切片后，使用以下命令写入本地库并自动更新 manifest：

```bash
python scripts/slice_library.py write-snippet \
  --project-dir .xushikj \
  --scene-type combat \
  --content-file /path/to/snippet.md
```

该命令会写入 `.xushikj/benchmark/style_snippets/{scene_type}_{timestamp}.md`，并更新本地 manifest；若 `state.json.benchmark_state.linked_author` 已配置，还会同步写入 `~/.narrativespace/style_library/{linked_author}/` 并更新全局 manifest。

## 逆向工程模式（新增）

当用户希望精准克隆某位作者风格时：
1. 用户粘贴 500 字极品文本
2. 系统输出"风格克隆 Prompt"而非风格总结
3. 克隆 Prompt 保存为 `.xushikj/config/style_modules/clone_{name}.yaml`
4. 可被 style_modules/index.yaml 直接引用为 active_module
5. standard/deep 模式下，逆向工程基于双层归纳结果输出，每条风格约束标注置信度（high/medium/low）

## 行文DNA采集系统（v9.0 升级）

> 执行说明（重要）：本章节的微观参数矩阵用于人工分析与归档，不建议直接全量注入模型。
> 运行期应先蒸馏为精简约束（如 5 条 DO + 5 条 DON'T + 1 段标杆文本）再注入写作提示词。

### 概述

行文DNA是比逆向工程更深层的风格提取——从宏观统计维度深化至语法微观层，以主谓宾定状补为切入点分析句子骨架，并新增逻辑结构、信息锚定顺序、话语标记隐性化、衔接与指代、标点停顿5个微观维度，将大神级写手的行文模式提炼为可执行的语法级参数。

### 核心升级

1. **逆向工程模式升级为推荐默认**：进入分析流程前必须询问，但推荐回答为"是"（v7.0 为"否"）
2. **支持多作品联合采集**：用户上传 3-5 部参考作品，系统横向对比提取共性DNA，排除个别作品的特异表达
3. **输出行文DNA档案**（`writing_dna_profile.yaml` v2.0），含 **8个微观核心基因段** + **4个宏观补充段**：

#### 8个微观核心基因段

**① `sentence_architecture`（句子结构基因）**

*A. 语法骨架层（主谓宾定状补）*
- `dominant_sentence_pattern`：主干句型分布占比（SVO标准型 / SV型无宾语 / 倒装型 / 无主句型 / 连动式 / 兼语式）
- `subject_type_preference`：主语类型偏好（人称代词主语 / 名词主语 / 零主语 / 事物主语拟人化频率）
- `predicate_complexity`：谓语复杂度分布（单动词谓语 / 连动谓语 / 动补结构 / 动趋结构 / 状-动组合）
- `object_handling`：宾语处理方式（直接宾语占比 / 省略宾语占比 / 双宾语频率 / 宾语从句频率）
- `modifier_strategy`：修饰语策略（定语平均长度及前置/后置偏好、状语类型偏好及前置频率、补语密度分布、单句最大修饰层数）

*B. 句式节奏层*
- `avg_sentence_length` + `length_variance`：平均句长及方差
- `short_long_alternation`：长短句交替规律（如"三短一长""短-短-长-短"）
- `sentence_opening_types`：句首启动方式占比（名词/动词/状语/对话/感官/转折词）
- `sentence_closure_pattern`：句尾收束偏好（动词收束/名词收束/语气词收束/省略收束）
- `clause_nesting_depth`：复句嵌套深度分布（单句/二层复句/三层复句占比）
- `compound_sentence_style`：复句关系类型偏好（并列/递进/转折/因果/条件/假设分布）

**② `lexical_structure`（词语结构基因）**
- `four_char_idiom_density`：四字格密度（成语/类成语，个/千字）
- `verb_nominalization_freq`：动词名词化使用频率
- `adjective_stacking_pattern`：形容词叠用模式偏好（单叠/双叠/ABB式/AABB式）
- `concrete_vs_abstract_ratio`：具象词与抽象词比例
- `colloquial_vs_literary_ratio`：口语词与书面词比例
- `signature_word_clusters`：标志性词汇簇（高频共现词组）
- `forbidden_words`：作者个人禁用词列表

**③ `paragraph_architecture`（段落结构基因）**
- `internal_logic_pattern`：段内逻辑推进模式（因果链 / 并列铺陈 / 递进升级 / 对比翻转 / 时序流动）
- `opening_sentence_function`：段首句功能（承接 / 转折 / 设置场景 / 抛出悬念 / 直接行动）
- `closing_sentence_function`：段尾句功能（悬念留白 / 情绪锚定 / 行动延续 / 总结收束）
- `avg_paragraph_length` + `length_variance`：平均段落行数及方差
- `paragraph_rhythm_pattern`：段落长度交替节奏（长-短-长 / 渐长 / 渐短 / 不规则）
- `density_modulation`：信息密度调控（高密度动作段 vs 低密度留白段的比例及切换规律）

**④ `logic_structure`（逻辑结构基因）**
- `causal_chain_style`：因果链呈现方式（显式因果词"因此/所以" vs 隐式因果动作结果自现）
- `argument_progression`：论证/推理递进方式（层层剥笋 / 先结论后补证 / 类比迁移 / 归谬反证）
- `contrast_deployment`：对比手法类型（明对比 / 暗对比 / 时间对比 / 期望与现实对比）
- `information_layering`：同一事件多层呈现偏好（单层直叙 / 双层套叠 / 三层递进揭示）

**⑤ `information_anchoring`（信息锚定顺序基因）**
- `result_first_vs_process_first`：先给结果再补过程 vs 先铺过程再揭结果 的比例
- `sensory_before_cognitive`：感官描写前置于认知判断 vs 认知判断前置的偏好
- `known_to_unknown_gradient`：信息梯度方向（正向递进 / 反向揭示 / 螺旋式）
- `detail_zoom_direction`：细节聚焦方向（宏观→微观下钻 / 微观→宏观上拉 / 交替）
- `exposition_embedding`：设定/背景信息嵌入策略（动作中夹叙 / 对话中透露 / 内心独白补充 / 旁白直叙）

**⑥ `discourse_marker_stealth`（话语标记隐性化基因）**
- `explicit_marker_density`：显性话语标记词密度（"但是/然而/因此/不过/况且"等，个/千字）
- `implicit_transition_ratio`：无标记转折/转换占全部转折的比例（隐性化程度指标）
- `marker_stealth_techniques`：隐性化替代手法（动作切断 / 场景跳切 / 节奏变化代替逻辑词 / 标点停顿代替关联词）
- `paragraph_bridge_style`：段间衔接风格（关联词桥接 / 意象呼应 / 动作接力 / 无桥硬切）

**⑦ `cohesion_and_reference`（衔接与指代结构基因）**
- `zero_anaphora_frequency`：零指代（省略主语/宾语）使用频率
- `pronoun_vs_noun_repetition`：代词替代 vs 名词重复 vs 同义替换的比例
- `reference_chain_length`：指代链平均长度（同一实体连续几个分句后必须重新具名）
- `synonym_substitution_richness`：同义替换丰富度（同一实体使用几种不同称呼）
- `lexical_cohesion_pattern`：词汇衔接模式（重复 / 同义 / 上下义 / 搭配衔接的偏好分布）
- `thematic_progression`：主位推进模式（主位一致 / 主位递进 / 述位→主位链 / 跳跃式）

**⑧ `punctuation_and_pause`（标点与停顿控制基因）**
- `comma_rhythm_function`：逗号的节奏控制功能（呼吸切分 / 列举分隔 / 插入语隔断 的比例）
- `dash_usage_pattern`：破折号使用模式（解释补充 / 话语中断 / 情绪延伸 / 场景切换 的偏好）
- `ellipsis_function`：省略号功能分布（未完之意 / 沉默停顿 / 思维断裂 / 时间流逝）
- `exclamation_density`：感叹号密度与使用场景约束（高潮限定 / 日常对话可用 / 严格克制）
- `question_mark_rhetoric`：问号修辞用法比例（真疑问 vs 反问 vs 自问自答 vs 内心质疑）
- `sentence_break_vs_comma`：断句偏好（短句断开用句号 vs 逗号连接长句 的倾向）
- `paragraph_ending_punctuation`：段尾标点偏好统计（句号/省略号/感叹号/引号 占比）

#### 4个宏观补充段（保留兼容，降级为辅助参考）

- `emotion_curve_template`：情绪曲线模板（段内情绪走向范式、情绪高点位置）
- `dialogue_dna`：对话基因（单轮对话平均字数、轮次节奏、台词密度）
- `description_density`：描写密度基因（每千字感官词数、动作词比例、非视觉感官占比）
- `transition_patterns`：场景转换手法（硬切/柔切/蒙太奇使用频率）

### DNA采集路径
- 原始档案：`.xushikj/benchmark/writing_dna_profile.yaml`（v2.0）
- 可执行模块：`.xushikj/config/style_modules/dna_human_{project_name}.yaml`（自动转换）

### DNA 工具写入方式（新增）

LLM 产出 DNA 字段 JSON 后，使用以下命令写入 DNA 模块：

```bash
python scripts/slice_library.py write-dna \
  --project-dir .xushikj \
  --project-name frequency_watcher \
  --dna-json /path/to/dna_output.json
```

该命令会写入 `.xushikj/config/style_modules/dna_human_{project_name}.yaml`。若文件已存在，仅追加缺失字段，不覆盖已有 key。

`scripts/dna_to_constraints.py` 的 `load_dna_constraints()` 先扫描 `dna_human_*.yaml`，若不存在则自动 fallback 扫描 `clone_*.yaml`。

### 与逆向工程的关系
- 逆向工程 = 单作品语感克隆（输出 `clone_*.yaml`）
- 行文DNA = 多作品共性提取，语法微观层（输出 `dna_human_*.yaml`）
- 二者可共存，DNA 优先级更高

### DNA优先级
行文DNA模块在 write_constraints 编译中优先级 **supreme（最高）**，高于 clone_*.yaml 和所有内置风格模块。每章写作前必须扫描加载，不可跳过。

## 基准复用判断标准（v8.5 新增）

在多项目创作或 Mode A/B 混用场景中，系统有时可以复用已有的基准分析结果，以下规则明确判断标准。

### 可以复用（使用 benchmark_shared.md）

满足以下**全部**条件时，允许复用上一个项目的基准分析：

1. 两个项目的**题材分类距离 ≤ 1 个一级分类**（如：都市悬疑 → 都市特工，距离=1，可复用）
2. 基准作品仍然适用（同类平台、同类读者群）
3. 两个项目目标平台相同（如都是番茄；若一个番茄一个起点，不建议复用）

### 必须重新执行（独立分析）

命中以下**任一**条件时，必须重新对新项目独立执行基准分析：

1. **题材分类距离 ≥ 2 个一级分类**（如：都市悬疑 → 修仙末世，距离=2，必须重做）
2. 两个项目的节奏预期显著不同（如：快节奏爽文 vs 慢热情感向）
3. 新项目有明确的风格超越目标（如：刻意对标某位特定作者的写法）
4. 用户明确要求独立分析

### 题材分类距离参考

| 一级分类 | 下属二级示例 |
|---|---|
| 都市 | 悬疑、特工、商战、日常、言情 |
| 修仙/奇幻 | 修仙、末世修炼、异能、高武 |
| 科幻 | 末世、星际、机甲、赛博朋克 |
| 历史 | 古代言情、宫廷权谋、架空历史 |
| 现实 | 职场、家庭、校园、农村 |

> 示例：都市悬疑 → 都市商战 = 同一级分类内，距离=1，**可复用**
> 示例：都市悬疑 → 修仙末世 = 跨两个一级分类，距离=2，**必须重做**

### 复用时的必要调整

使用 `benchmark_shared.md` 复用基准结果时，**仍需**在 benchmark 输出中补充：

1. 针对新项目题材的特异参数调整（如：修仙题材平均句长调整为 20-25 字）
2. 对标作品名单更新（即使分析结论相同，也要记录实际对标的是哪些作品）
3. 在 `benchmark_binding.reason` 中注明"复用自 XXX 项目，调整：YYY"
