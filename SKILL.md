---
name: narrativespace-xushikj
description: |
  叙事空间创作系统（一体化版）— 包含8个创作模块的完整商业网文创作工具包。
  基于三位一体·叙事空间创作系统 v8.2，将原来的8个并行Skill统一打包成1个。
  十二步工作流 + 动态知识库 + 帮回辅助系统 + 去AI痕迹后处理 + 行文DNA采集 + TRPG沉浸互动 + 记忆锚点防遗忘 + RAG本地向量检索 + 卷级时间线里程碑追踪。
metadata:
  version: 8.2.0
  edition: unified
  skills_included: 8
  triggers:
    - 叙事空间
    - 网文创作
    - 商业小说
    - 爆款小说
    - 叙事空间创作
    - 写网文
---

# 叙事空间创作系统 v8.2（一体化版）

## 这是什么

这是将原来的 **8 个 Skill 统一打包的一体化版本**。原有的功能、架构、质量标准完全保留，只是目录结构和部署方式简化了：

- **简化前**：用户需要复制 8 个文件夹到 `.claude/skills/`
- **简化后**：用户只复制 1 个 `narrativespace-xushikj` 文件夹

内部仍然保持模块化设计，8 个独立的创作模块各自独立演进，通过完整的路由系统进行交互。

## 核心特性

- **十二步工作流**：从对标分析 → 规划 → 知识库 → 场景 → 创作，完整覆盖网文创作全周期
- **两种写作模式**：流水线模式（自动化产出）vs 互动模式（实时引导）
- **动态知识库**：EX3 思想的实体追踪，确保长篇创作的一致性
- **帮回系统**：实时工作流管理和用户干预
- **质量评估**：8 维度质量评分 + HC 健康检查 + 灵敏度控制
- **去 AI 痕迹**：后处理层清除文本中的 AI 生成特征

### v8.0 新增

- **行文DNA采集**：多作品联合提取人类写作DNA，生成可执行风格约束（DO/DON'T + 标杆段落），写作时以最高优先级注入
- **TRPG沉浸式互动**：多决策类型（行动/对话/态度/战术/内心）+ 决策密度自适应 + INTERRUPT紧急介入状态
- **情绪温度系统**：cold/warm/hot 三档独立于剧情张力的叙事体温控制
- **人味注入规则**：ht_01~ht_06 六条强制执行的反AI痕迹生成阶段规则
- **记忆锚点系统**：每章 ≤150 字锚点（关键转折/悬念/情绪快照/债务），解决长上下文遗忘问题
- **三级概括压缩**：summary_index 自动压缩（最近3章完整/4-10章50%/10+章最小化），控制上下文体积

## 快速开始

### 1. 项目初始化

项目目录下运行初始化脚本：

```bash
python narrativespace-xushikj/scripts/init.py --project-dir /your/project/path
```

这会自动：
- 创建 `.xushikj/` 工作目录
- 同步 `config/` 配置到项目本地
- 初始化 `state.json`, `knowledge_base.json` 等

### 2. 开始创作

在 Claude 对话中说：

- **"我想写网文"** → 进入规划模块，开始十二步流程
- **"对标分析这部作品"** → 进入步骤 0（对标模块）
- **"写第 3 章"** → 进入步骤 10（写作模块）
- **"这里我想改剧情"** → 切换到互动模式

系统会根据你的意图自动路由到对应的子模块。

## 8 个创作模块速览

| 模块 | 步骤 | 职责 | 触发词 |
|------|------|------|--------|
| **benchmark** | 0 | 对标作品学习 & 风格分析 | 对标分析, 学习对标 |
| **planning** | 1-6, 11 | 故事规划（一句话→四页大纲）+ 书名简介 | 规划, 故事大纲 |
| **knowledge-base** | 7 | 知识库初始化 & 动态实体追踪 | 知识库, 初始化KB |
| **scenes** | 8-9 | 场景编制 & 场景规划 | 场景规划, 场景清单 |
| **writing** | 10A | 流水线写作模式（自动逐章） | 写第N章, 开始写作 |
| **interactive** | 10B | 互动写作模式（用户实时引导） | 互动写作, 引导剧情 |
| **humanizer** | 后处理 | 清除 AI 痕迹，人类化处理 | 去AI痕迹 |

## 一体化版本的优势

### 用户视角
- ✅ **安装简化**：1 个文件夹 vs 8 个文件夹
- ✅ **路由智能化**：自动识别意图，无需手动切换 Skill
- ✅ **配置统一**：所有共享资源（config/, templates/, scripts/）集中管理

### 开发视角
- ✅ **模块独立**：8 个模块仍然独立迭代，互不干扰
- ✅ **路径明确**：`modules/benchmark/`, `modules/writing/` 等清晰的命名模式
- ✅ **跨引用管理**：所有路径引用自动适配新结构

## 配置与自定义

所有配置文件位于 `/config`：

- `foundational_principles.yaml` — 底层创作原则
- `writing_rules.yaml` — 写作规则（平台特定）
- `style_rules.yaml` — 语言风格
- `benchmark_triggers.yaml` — 对标基准
- `style_modules/` — 章节级风格模块（悬疑/爱情/奇幻等）

修改时优先改项目本地的 `.xushikj/config/`，不要直接改 Skill 里的 `config/`。

## 使用指南

详见 [README.md](README.md)

## 技术架构

### 工作流层次
```
用户输入
  ↓
主路由 (根 prompt.md)
  ↓
子模块识别 (modules/*/SKILL.md + prompt.md)
  ↓
执行 (orchestrator + sub-agents)
  ↓
状态更新 (state.json, knowledge_base.json)
  ↓
质量保证 (8D评分, HC检查, 灵敏度控制)
```

### 文件组织
```
narrativeSpace-xushikj/
├── config/                  # 全局配置种子
├── templates/               # 输出格式模板
├── scripts/                 # 工具脚本
├── modules/                 # 8 个创作模块
├── references/              # 全局参考文档
├── SKILL.md                 # 本身的元数据
├── prompt.md                # 主路由提示词
├── README.md                # 完整使用指南
└── AGENTS.md                # 代理指南（如有）
```

## 其他资源

- 详细的十二步说明见 [README.md](README.md)
- 各模块详细文档见 `modules/*/SKILL.md`
- 原始设计文档见 `references/original-prompt-sections/`

---

**版本**：8.0.0（一体化合并）  
**最后更新**：2026-03-31
