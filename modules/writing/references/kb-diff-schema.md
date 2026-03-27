# KB Diff 格式规范

章节写作 sub-agent 在完成创作后，生成此格式的 diff 文件，由 orchestrator 增量应用到 `knowledge_base.json`。

## Diff 文件路径

```
.xushikj/kb_diffs/chapter_XX_diff.json
```

## 完整结构

```json
{
  "chapter": 5,
  "changes": {
    "characters": {
      "char_001": {
        "update": {
          "status": "受伤",
          "arc_stage": "挣扎期",
          "last_seen_chapter": 5,
          "snapshot": "在与影魔的战斗中负伤，暂时失去右臂行动能力"
        },
        "append": {
          "abilities": ["暗影感知（觉醒）"]
        }
      },
      "char_new_001": {
        "create": {
          "name": "新角色名",
          "aliases": [],
          "identity": "...",
          "age": "...",
          "appearance": "...",
          "personality": [],
          "goals": {"surface": "...", "deep": "..."},
          "values": "...",
          "behavior_logic": "...",
          "abilities": [],
          "weaknesses": [],
          "status": "活跃",
          "arc_stage": "初始",
          "last_seen_chapter": 5,
          "dialogue_style": "...",
          "catchphrases": [],
          "snapshot": "初次登场的一句话描述"
        }
      }
    },
    "locations": {
      "loc_003": {
        "update": { "current_state": "废墟" }
      }
    },
    "items": {
      "item_002": {
        "update": { "current_owner": "char_003", "location": "loc_005" }
      }
    },
    "events": {
      "event_005": {
        "create": {
          "name": "影魔突袭",
          "chapter": 5,
          "description": "...",
          "entities_involved": ["char_001", "char_003"],
          "consequences": "...",
          "timeline_position": "第一幕·第二节"
        }
      }
    }
  },
  "relationships": {
    "append": [
      {
        "entity_a": "char_001",
        "entity_b": "char_new_001",
        "type": "敌对",
        "description": "...",
        "evolution_log": [{"chapter": 5, "status": "初次交锋"}]
      }
    ],
    "evolve": [
      {
        "entity_a": "char_001",
        "entity_b": "char_002",
        "add_log": {"chapter": 5, "status": "信任加深，共同作战"}
      }
    ]
  },
  "timeline_append": [
    {
      "chapter": 5,
      "event": "影魔突袭学园",
      "entities_involved": ["char_001", "char_003", "loc_002"],
      "consequences": "学园东翼损毁，char_001 负伤"
    }
  ],
  "foreshadowing": {
    "plant": [
      {
        "id": "foreshadow_005",
        "name": "暗影感知的代价",
        "planted_chapter": 5,
        "description": "觉醒暗影感知后开始听到低语声",
        "expected_resolution": "第12章揭示低语来源",
        "status": "pending"
      }
    ],
    "resolve": ["foreshadow_001"]
  }
}
```

## 操作语义

| 操作 | 含义 | 适用层级 |
|------|------|----------|
| `update` | 覆盖指定字段（merge，不替换整个对象） | entities 内的具体实体 |
| `append` | 追加到数组字段（不去重） | entities 内的数组字段、relationships |
| `create` | 新建实体（必须包含模板全部字段） | entities 内的新 ID |
| `evolve` | 向已有关系的 `evolution_log` 追加记录 | relationships |
| `timeline_append` | 追加到 timeline 数组 | 顶层 |
| `plant` | 新增伏笔到 `foreshadowing.planted` | foreshadowing |
| `resolve` | 将指定 ID 的伏笔移入 `foreshadowing.resolved` | foreshadowing |

## 主进程应用逻辑

```
1. 读取 knowledge_base.json 全文（内存中）
2. 按 diff 结构逐项应用：
   a. changes.{entity_type}.{id}.update → 对目标对象做 shallow merge
   b. changes.{entity_type}.{id}.append → 对目标数组字段做 concat
   c. changes.{entity_type}.{id}.create → 新建整个对象
   d. relationships.append → 追加到 relationships 数组
   e. relationships.evolve → 找到匹配的 entity_a + entity_b 对，向其 evolution_log 追加
   f. timeline_append → 追加到 timeline 数组
   g. foreshadowing.plant → 追加到 foreshadowing.planted
   h. foreshadowing.resolve → 将 ID 对应的条目从 planted 移入 resolved，标记 status="resolved"
3. 验证：
   - 新建实体 ID 不与已有 ID 冲突
   - update 目标 ID 必须在 KB 中存在
   - create 的字段数必须 = 模板 _fields 数
   - evolve 的 entity_a + entity_b 对必须在 relationships 中存在
4. 更新元数据：
   - last_updated = 当前日期
   - last_updated_chapter = diff.chapter
5. 一次性 Write 保存 knowledge_base.json
6. 保留 kb_diffs/chapter_XX_diff.json 作为审计记录
```

## 空 Diff

如果本章无任何变更（纯对话/环境描写），diff 为：

```json
{
  "chapter": 5,
  "changes": {},
  "relationships": {},
  "timeline_append": [],
  "foreshadowing": {}
}
```

## 注意事项

- Sub-agent 只生成 diff，不直接修改 `knowledge_base.json`
- 每个 `create` 操作的新 ID 应遵循 `_id_format`（如 `char_NNN`），编号从当前最大 ID + 1 开始
- `snapshot` 字段在每章 diff 中应为出场角色更新（即使内容变化不大，也应反映本章状态）
- Orchestrator 在应用 diff 前会执行一致性校验（参见 zhishiku prompt.md）
