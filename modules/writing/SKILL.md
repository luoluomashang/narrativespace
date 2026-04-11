---
name: xushikj-xiezuo
description: 叙事空间创作系统写作模块（精简版），执行步骤10逐章写作。
metadata:
  version: 8.5.0
  parent: narrativespace-xushikj
  step: 10
  triggers:
    - 写第N章
    - 开始写作
    - 继续写
---

# 写作模块（精简版）

## 角色边界
1. 按 scene_card 写当前章节。
2. 保持角色一致性和信息连续性。
3. 章末保留悬念钩子。
4. 不承担跨步骤流程控制。

## 依赖
- .xushikj/state.json
- .xushikj/knowledge_base.json
- .xushikj/scenes/{cycle_id}/scene_plans/chapter_{N}.md
- scripts/assemble_prompt.py 组装的规则包

## 脚本组装前置闸门（HARD STOP）

执行本模块前，必须先通过 `scripts/assemble_prompt.py` 组装步骤10提示词并确认输出已生成。

1. 未确认组装完成时，禁止直接生成章节正文与配套产物。
2. 此时只允许返回应执行的组装命令与必要说明，等待用户确认。
3. 禁止以“已读取部分配置文件”替代步骤组装。

## 运行原则
- 小规则集注入（不全量加载）
- 单章单任务
- 与质检流程解耦
