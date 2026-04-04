---
name: xushikj-duibiao
description: |
  叙事空间创作系统·对标分析模块。执行步骤0：对标作品学习与风格解析。
  分析对标作品的文风、世界观、情节套路和实体信息，生成风格报告。支持 quick（单段快速）/ standard（12-20章分层采样）/ deep（30章+高精度）三种 sample_scope 模式。
metadata:
  version: 8.2.0
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

对标分析除风格报告外，还必须提取 3-5 个场景化文本切片：
1. 切片覆盖类型：combat / face_slap / daily / emotional / system
2. 每切片 200-500 字，标注 scene_type 标签
3. 存储路径：`.xushikj/benchmark/style_snippets/{scene_type}_{序号}.md`
4. 后续 xushikj-xiezuo 根据当前章节场景类型动态提取匹配切片作为 Few-Shot 注入

## 逆向工程模式（新增）

当用户希望精准克隆某位作者风格时：
1. 用户粘贴 500 字极品文本
2. 系统输出"风格克隆 Prompt"而非风格总结
3. 克隆 Prompt 保存为 `.xushikj/config/style_modules/clone_{name}.yaml`
4. 可被 style_modules/index.yaml 直接引用为 active_module
5. standard/deep 模式下，逆向工程基于双层归纳结果输出，每条风格约束标注置信度（high/medium/low）

## 行文DNA采集系统（v8.0 新增）

### 概述

行文DNA是比逆向工程更深层的风格提取——不仅分析"怎么写"，还量化提取句式节奏基因、词汇指纹、情绪曲线模板等可执行的写作参数。

### 核心升级

1. **逆向工程模式升级为推荐默认**：进入分析流程前必须询问，但推荐回答为"是"（v7.0 为"否"）
2. **支持多作品联合采集**：用户上传 3-5 部参考作品，系统横向对比提取共性DNA，排除个别作品的特异表达
3. **输出行文DNA档案**（`writing_dna_profile.yaml`）：
   - `sentence_rhythm_pattern`：句式节奏基因（长短句交替规律的精确统计）
   - `vocabulary_fingerprint`：词汇指纹（高频词/禁用词/偏好搭配）
   - `emotion_curve_template`：情绪曲线模板（段内情绪走向范式）
   - `dialogue_dna`：对话基因（单轮对话平均字数、轮次节奏、台词密度）
   - `description_density`：描写密度基因（每千字感官词数、动作词比例）
   - `transition_patterns`：场景转换手法（硬切/柔切/蒙太奇使用频率）
   - `paragraph_structure`：段落结构基因（段首句型、收束方式、段间过渡）

### DNA采集路径
- 原始档案：`.xushikj/benchmark/writing_dna_profile.yaml`
- 可执行模块：`.xushikj/config/style_modules/dna_human_{project_name}.yaml`（自动转换）

### 与逆向工程的关系
- 逆向工程 = 单作品语感克隆（输出 `clone_*.yaml`）
- 行文DNA = 多作品共性提取（输出 `dna_human_*.yaml`）
- 二者可共存，DNA 优先级更高

### DNA优先级
行文DNA模块在 write_constraints 编译中优先级**最高**，高于 clone_*.yaml 和所有内置风格模块。
