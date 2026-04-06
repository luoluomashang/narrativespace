#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
叙事空间创作系统 — 知识库初始化示例脚本 (P0-B 优化)

用法：
  1. 在本文件中直接编辑 kb 字典，填入你的项目实体
  2. 运行：python kb_init_example.py
  3. 脚本会将结果写入 knowledge_base.json（当前目录下的 .xushikj/knowledge_base.json）

注意：所有字段值均为示例，替换为你的实际信息即可。
中文字符在本脚本中完全安全，无需担心 Shell 转义问题。
"""

import json
import os
import sys

# ──────────────────────────────────────────────────
# 配置：输出路径
# ──────────────────────────────────────────────────
OUTPUT_PATH = os.path.join(".xushikj", "knowledge_base.json")


# ──────────────────────────────────────────────────
# 知识库内容：直接在下方编辑
# ──────────────────────────────────────────────────
kb = {
    "version": "3.0",
    "last_updated": "",          # 会在每章写作后自动更新
    "last_updated_chapter": 0,

    "entities": {

        # ── 角色 ─────────────────────────────────
        "characters": {
            "char_001": {
                "name": "主角姓名",
                "aliases": ["别名/外号"],
                "identity": "主角",              # 主角 / 女主 / 反派 / 配角 / 灰色
                "age": "25岁",
                "appearance": "外貌特征，1-2句",
                "personality": ["性格特质1", "性格特质2"],
                "goals": {
                    "surface": "表层目标（别人看得到的）",
                    "deep": "深层目标（内心真实驱动）"
                },
                "values": "核心价值观，1句话",
                "behavior_logic": "高压下的惯性行为/执念",
                "abilities": ["核心能力1", "核心能力2"],
                "weaknesses": ["弱点1", "弱点2"],
                "status": "活跃",               # 活跃 / 受伤 / 隐居 / 死亡
                "arc_stage": "触发期",           # 触发期 / 挣扎期 / 蜕变期
                "arc_history": [],
                "last_seen_chapter": 1,
                "dialogue_style": "对话风格，例：话少，用短句，习惯反问",
                "voice_fingerprint": {
                    "under_pressure":   "高压时句子变短，省略主语",
                    "lying_or_hiding":  "撒谎时多补充不必要细节",
                    "deflect":          "用反问岔开话题",
                    "emotional_peak":   "情绪极值时沉默或说不完整的句子",
                    "default_length":   "短"    # 短 / 中 / 长
                },
                "catchphrases": ["口头禅示例"],
                "snapshot": "Chapter 1起始状态：一句话描述当前处境和状态"
            },
            # 添加更多角色：复制上方整个 char_001 块，改为 char_002 ...
        },

        # ── 地点 ─────────────────────────────────
        "locations": {
            "loc_001": {
                "name": "地点名称",
                "description": "地点描述，2-3句",
                "significance": "在故事中的意义",
                "current_state": "繁荣",         # 繁荣 / 废墟 / 封锁 / 隐秘
                "connected_to": []               # 关联地点的 ID 列表
            },
            # 添加更多地点：loc_002, loc_003 ...
        },

        # ── 物品/道具 ─────────────────────────────
        "items": {
            "item_001": {
                "name": "物品名称",
                "description": "物品描述",
                "abilities": ["物品能力/效果"],
                "current_owner": "char_001",     # 持有者角色 ID
                "location": "loc_001",           # 当前所在地点 ID
                "significance": "在故事中的意义"
            },
            # 添加更多物品：item_002 ...
        },

        # ── 势力/组织 ─────────────────────────────
        "factions": {
            "faction_001": {
                "name": "势力名称",
                "description": "势力描述",
                "leader": "char_001",            # 领袖角色 ID
                "members": [],                   # 成员角色 ID 列表
                "goals": "势力核心目标",
                "resources": ["资源/优势1"],
                "relations": ["与其他势力的关系描述"]
            },
            # 添加更多势力：faction_002 ...
        },
    },

    # ── 人物关系 ─────────────────────────────────
    "relationships": [
        {
            "entity_a": "char_001",
            "entity_b": "char_002",
            "type": "敌对",                       # 师徒 / 敌对 / 恋人 / 盟友 / 隶属
            "description": "关系描述",
            "evolution_log": [
                {"chapter": 1, "status": "初始关系状态"}
            ]
        },
        # 添加更多关系...
    ],

    # ── 时间线（关键事件） ───────────────────────
    "timeline": [
        {
            "chapter": 1,
            "event": "故事开篇事件描述",
            "entities_involved": ["char_001"],
            "consequences": "该事件的后续影响"
        },
        # 添加更多时间线事件...
    ],

    # ── 伏笔管理 ─────────────────────────────────
    "foreshadowing": {
        "planted": [
            {
                "id": "fs_001",
                "name": "伏笔简称",
                "planted_chapter": 1,
                "description": "伏笔内容描述",
                "expected_resolution": "预计第N章或第V卷回收",
                "status": "planted",             # planted / to_be_planted / resolved
                "heat_level": "warm"             # hot=本卷回收 / warm=3卷内 / cold=全书后期
            },
            # 添加更多伏笔...
        ],
        "resolved": []
    },

    # ── 风格档案（由 benchmark 模块填充，也可手动设置） ─
    "style_profile": {
        "avg_sentence_length": 18,               # 平均句长（字数）
        "dialogue_ratio": 0.40,                  # 对话占比（0.0-1.0）
        "pov": "第三人称限知",                    # 叙事视角
        "genre_tags": ["都市", "悬疑"],           # 题材标签
        "tone": "紧张、克制",                     # 整体基调
        "banned_words": []                        # 禁用词（由 humanizer 模块使用）
    }
}


# ──────────────────────────────────────────────────
# 写入逻辑（不需要修改）
# ──────────────────────────────────────────────────
def main():
    out_dir = os.path.dirname(OUTPUT_PATH)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
        print(f"创建目录：{out_dir}")

    if os.path.exists(OUTPUT_PATH):
        answer = input(f"{OUTPUT_PATH} 已存在，覆盖？(y/N) ").strip().lower()
        if answer != "y":
            print("已取消。")
            sys.exit(0)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)

    size = os.path.getsize(OUTPUT_PATH)
    chars = sum(1 for section in kb["entities"].values() for _ in section)
    print(f"知识库已写入：{OUTPUT_PATH}（{size} bytes）")
    print(f"实体数量：characters={len(kb['entities']['characters'])}, "
          f"locations={len(kb['entities']['locations'])}, "
          f"items={len(kb['entities']['items'])}, "
          f"factions={len(kb['entities']['factions'])}")
    print(f"伏笔数量：{len(kb['foreshadowing']['planted'])} 条")
    print("完成。")


if __name__ == "__main__":
    main()
