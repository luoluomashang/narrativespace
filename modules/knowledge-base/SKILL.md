---
name: xushikj-zhishiku
description: |
  叙事空间创作系统·知识库模块。执行步骤7：动态实体知识库管理。
  管理和演进基于 EX3 思想的知识库。
metadata:
  version: 8.4.0
  parent: narrativespace-xushikj
  step: 7
  triggers:
    - 初始化知识库
    - 更新知识库
---

# 知识库模块 (opencode)

本模块在滚动创作模式下按 cycle 增量更新知识库，不依赖全书规划完成。

## 需要加载的配置

| 配置文件 | 用途 | 必须 |
|----------|------|------|
| `.xushikj/config/meta_rules.yaml` | 输出语言与符号标准化 | 是 |
| `.xushikj/config/content_limits.yaml` | 内容门槛与禁限 | 是 |

运行期配置必须来自 `.xushikj/config/`，不得回退读取 Skill 自带 `config/`。

## 两种写作模式适配

本模块与写作模式无关，在 pipeline（xiezuo）和 interactive（hudong）两种模式下都有相同的 KB 更新节点：
- pipeline：每章写作完成后自动触发
- interactive：用户确认"OK落盤"时触发

两种模式共享同一套 KB diff schema 和应用规则。

## 更新时机

以下节点应触发 KB 增量更新：

1. 每章写作完成后
2. 每个 cycle 收尾时
3. `deepen` 阶段完成高风险场景细化后

## 输入来源

1. `xiezuo/hudong` 输出的 `kb_diff_patch`
2. `changjing` 输出的 `kb_diff_expectation`
3. 当前 `rolling_context` 与章节进度信息

## 增量更新流程

1. 收集本章或本轮 diff
2. 执行 schema 校验
3. 应用到 `knowledge_base.json`
4. 记录 `applied_cycle_id` 与 `applied_chapter_ids`
5. 输出一致性检查结果

## 一致性检查点

每次更新后至少检查：

1. 实体存在性：引用实体必须可解析
2. 时间线一致性：事件顺序不得逆转
3. 状态连续性：角色/物品关键状态变化可追踪
4. 场景对齐：本轮场景卡中的关键事件与 KB 变更一致
5. 跨轮自洽：本轮 cycle KB 变更不得与两轮前已归档的状态产生矛盾（如已死亡角色不得在无复活说明时重新出现）。

## 失败处理

1. diff 非法：拒绝写入并返回字段级错误
2. 引用断裂：进入修复队列，标注阻塞级别
3. 时间线冲突：保留原值并生成人工确认提示

禁止因为未完成全书规划而暂停 KB 增量更新。

## 与滚动生命周期协同

1. `plan_light`：允许初始化或补全基础实体；根据写作模式执行 full / lite 两种初始化
2. `write`：章节级持续增量
3. `deepen`：对高风险章节做二次修正
4. `continue`：轮次收口并产出下轮校验基线

## 初始化模式（强制区分）
## 归档记忆（archive_memory）

当知识库实体超过 80 个或 knowledge_base.json 超过 200KB 时，触发归档：

1. 将"已死亡/已解决/已永久消失"的实体移入 `.xushikj/archive_memory.json`
2. 主 KB 保留该实体的简短"归档条目"（id/name/status=archived/archive_ref）
3. 归档后 `.xushikj/knowledge_base.json` 中不再展开此实体的全部字段
4. 若后续剧情引用已归档实体，从 archive_memory.json 按需加载

归档不等于删除：归档实体随时可被引用，只是不占用滚动上下文的常驻槽位。

## 初始化模式（强制区分）

### Full 初始化（pipeline）

适用：`writing_mode=pipeline`

输入优先级：

1. `.xushikj/outline/one_sentence.md`
2. `.xushikj/outline/one_paragraph.md`
3. `.xushikj/outline/characters/`
4. `.xushikj/outline/volume_{V}_one_page.md`
5. `.xushikj/outline/character_arcs.md`（如存在）
6. `.xushikj/outline/volume_{V}_four_pages.md`（如存在）

### Lite 初始化（interactive）

适用：`writing_mode=interactive`

输入优先级：

1. `.xushikj/outline/one_sentence.md`
2. `.xushikj/outline/one_paragraph.md`
3. `.xushikj/outline/characters/`
4. `.xushikj/outline/worldview_and_system.md`（仅步骤 2.5 触发时）

Lite 初始化只要求建立人物实体、核心关系、必要背景常量，禁止因为缺少四页大纲或场景卡阻塞互动写作启动。

## 示例

示例 A：单章增量

- 输入：第 12 章 `kb_diff_patch`
- 输出：成功写入角色关系变化，记录 `applied_chapter_ids=[12]`

示例 B：轮次收尾校验

- 输入：cycle 完成，累计 4 个 diff
- 输出：合并写入 + 一致性报告，若冲突则返回冲突清单
