---
name: xushikj-duibiao
description: |
  叙事空间创作系统·对标分析模块。执行步骤0：对标作品学习与风格解析。
  分析对标作品的文风、世界观、情节套路和实体信息，生成风格报告。支持 quick（单段快速）/ standard（12-20章分层采样）/ deep（30章+高精度）三种 sample_scope 模式。
metadata:
  version: 3.0.0
  parent: opencode-xushikj-chuangzuo
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
