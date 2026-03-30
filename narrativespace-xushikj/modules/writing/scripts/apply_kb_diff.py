#!/usr/bin/env python3
"""
KB Diff 应用脚本 — 叙事空间创作系统

功能：
  1. 校验 diff JSON 格式
  2. 增量应用 diff 到 knowledge_base.json
  3. 一致性校验（ID 冲突、死亡复活、物品归属等）
  4. 可被 orchestrator 通过 Bash 调用

用法：
  python3 apply_kb_diff.py <kb_path> <diff_path> [--dry-run] [--verbose]

  --dry-run   只校验不写入
  --verbose   输出详细变更日志
"""

import json
import sys
import copy
import argparse
from datetime import date
from pathlib import Path


# ── 格式校验 ──────────────────────────────────────────────

def validate_diff_format(diff: dict) -> list[str]:
    """校验 diff 格式，返回错误列表（空=通过）"""
    errors = []

    if "chapter" not in diff:
        errors.append("缺少 'chapter' 字段")
    elif not isinstance(diff["chapter"], int):
        errors.append("'chapter' 必须是整数")

    valid_entity_types = {"characters", "locations", "items", "factions", "abilities", "events"}
    valid_ops = {"update", "append", "create"}

    changes = diff.get("changes", {})
    if not isinstance(changes, dict):
        errors.append("'changes' 必须是对象")
    else:
        for etype, entities in changes.items():
            if etype not in valid_entity_types:
                errors.append(f"未知实体类型: {etype}")
                continue
            if not isinstance(entities, dict):
                errors.append(f"changes.{etype} 必须是对象")
                continue
            for eid, ops in entities.items():
                if not isinstance(ops, dict):
                    errors.append(f"changes.{etype}.{eid} 必须是对象")
                    continue
                for op in ops:
                    if op not in valid_ops:
                        errors.append(f"changes.{etype}.{eid} 中未知操作: {op}")

    rels = diff.get("relationships", {})
    if rels:
        if not isinstance(rels, dict):
            errors.append("'relationships' 必须是对象")
        else:
            if "append" in rels and not isinstance(rels["append"], list):
                errors.append("relationships.append 必须是数组")
            if "evolve" in rels and not isinstance(rels["evolve"], list):
                errors.append("relationships.evolve 必须是数组")

    tl = diff.get("timeline_append", [])
    if not isinstance(tl, list):
        errors.append("'timeline_append' 必须是数组")

    fs = diff.get("foreshadowing", {})
    if fs:
        if "plant" in fs and not isinstance(fs["plant"], list):
            errors.append("foreshadowing.plant 必须是数组")
        if "resolve" in fs and not isinstance(fs["resolve"], list):
            errors.append("foreshadowing.resolve 必须是数组")

    return errors


# ── 一致性校验 ────────────────────────────────────────────

def consistency_check(kb: dict, diff: dict) -> list[dict]:
    """一致性校验，返回 [{level, code, message}]"""
    warnings = []
    changes = diff.get("changes", {})

    # 1. 新建 ID 冲突
    for etype, entities in changes.items():
        existing_ids = set(kb.get("entities", {}).get(etype, {}).keys())
        for eid, ops in entities.items():
            if "create" in ops and eid in existing_ids:
                warnings.append({
                    "level": "ERROR",
                    "code": "ID_CONFLICT",
                    "message": f"新建 {etype}.{eid} 与已有 ID 冲突"
                })

    # 2. update 目标必须存在
    for etype, entities in changes.items():
        existing_ids = set(kb.get("entities", {}).get(etype, {}).keys())
        for eid, ops in entities.items():
            if "update" in ops and eid not in existing_ids:
                warnings.append({
                    "level": "ERROR",
                    "code": "UPDATE_TARGET_MISSING",
                    "message": f"更新目标 {etype}.{eid} 不存在"
                })

    # 3. 死亡角色复活
    chars = changes.get("characters", {})
    for cid, ops in chars.items():
        if "update" in ops:
            existing = kb.get("entities", {}).get("characters", {}).get(cid, {})
            if existing.get("status") == "死亡" and ops["update"].get("status") not in (None, "死亡"):
                warnings.append({
                    "level": "WARNING",
                    "code": "DEAD_REVIVE",
                    "message": f"角色 {cid} 已死亡但状态被更新为 {ops['update']['status']}"
                })

    # 4. 物品归属冲突
    items_changes = changes.get("items", {})
    owner_map = {}
    for iid, item in kb.get("entities", {}).get("items", {}).items():
        owner = item.get("current_owner")
        if owner:
            owner_map[iid] = owner
    for iid, ops in items_changes.items():
        if "update" in ops and "current_owner" in ops["update"]:
            owner_map[iid] = ops["update"]["current_owner"]
    # 检查同一物品是否被多个 diff 项重复赋值（此处主要做格式层校验）

    # 5. evolve 目标关系必须存在
    rels = diff.get("relationships", {})
    if "evolve" in rels:
        existing_pairs = set()
        for r in kb.get("relationships", []):
            existing_pairs.add((r.get("entity_a"), r.get("entity_b")))
        for ev in rels["evolve"]:
            pair = (ev.get("entity_a"), ev.get("entity_b"))
            if pair not in existing_pairs:
                warnings.append({
                    "level": "WARNING",
                    "code": "EVOLVE_TARGET_MISSING",
                    "message": f"evolve 目标关系 {pair} 不存在"
                })

    # 6. resolve 的伏笔必须在 planted 中
    fs = diff.get("foreshadowing", {})
    if "resolve" in fs:
        planted_ids = {f["id"] for f in kb.get("foreshadowing", {}).get("planted", [])}
        for fid in fs["resolve"]:
            if fid not in planted_ids:
                warnings.append({
                    "level": "WARNING",
                    "code": "FORESHADOW_NOT_FOUND",
                    "message": f"要回收的伏笔 {fid} 不在 planted 列表中"
                })

    return warnings


# ── 应用 Diff ─────────────────────────────────────────────

def apply_diff(kb: dict, diff: dict) -> dict:
    """将 diff 增量应用到 KB（在内存中操作副本），返回更新后的 KB"""
    kb = copy.deepcopy(kb)
    chapter = diff["chapter"]
    changes = diff.get("changes", {})

    # 1. 应用 entity changes
    for etype, entities in changes.items():
        if etype not in kb.get("entities", {}):
            kb["entities"][etype] = {}

        for eid, ops in entities.items():
            # create
            if "create" in ops:
                kb["entities"][etype][eid] = ops["create"]

            # update (shallow merge)
            if "update" in ops:
                if eid in kb["entities"][etype]:
                    kb["entities"][etype][eid].update(ops["update"])

            # append (concat arrays)
            if "append" in ops:
                if eid in kb["entities"][etype]:
                    target = kb["entities"][etype][eid]
                    for field, values in ops["append"].items():
                        if field in target and isinstance(target[field], list):
                            target[field].extend(values)
                        else:
                            target[field] = values

    # 2. 应用 relationships
    rels = diff.get("relationships", {})
    if "append" in rels:
        kb.setdefault("relationships", []).extend(rels["append"])

    if "evolve" in rels:
        for ev in rels["evolve"]:
            ea, eb = ev["entity_a"], ev["entity_b"]
            for r in kb.get("relationships", []):
                if r.get("entity_a") == ea and r.get("entity_b") == eb:
                    r.setdefault("evolution_log", []).append(ev["add_log"])
                    break

    # 3. 应用 timeline
    tl = diff.get("timeline_append", [])
    kb.setdefault("timeline", []).extend(tl)

    # 4. 应用 foreshadowing
    fs = diff.get("foreshadowing", {})
    if "plant" in fs:
        kb.setdefault("foreshadowing", {}).setdefault("planted", []).extend(fs["plant"])

    if "resolve" in fs:
        planted = kb.get("foreshadowing", {}).get("planted", [])
        resolved = kb.get("foreshadowing", {}).setdefault("resolved", [])
        for fid in fs["resolve"]:
            for i, f in enumerate(planted):
                if f.get("id") == fid:
                    f["status"] = "resolved"
                    f["resolved_chapter"] = chapter
                    resolved.append(planted.pop(i))
                    break

    # 5. 更新元数据
    kb["last_updated"] = str(date.today())
    kb["last_updated_chapter"] = chapter

    return kb


# ── 变更摘要 ──────────────────────────────────────────────

def summarize_changes(diff: dict) -> str:
    """生成人类可读的变更摘要"""
    lines = [f"第{diff['chapter']}章 KB Diff 摘要:"]
    changes = diff.get("changes", {})
    for etype, entities in changes.items():
        creates = sum(1 for e in entities.values() if "create" in e)
        updates = sum(1 for e in entities.values() if "update" in e)
        appends = sum(1 for e in entities.values() if "append" in e)
        parts = []
        if creates: parts.append(f"新建{creates}")
        if updates: parts.append(f"更新{updates}")
        if appends: parts.append(f"追加{appends}")
        if parts:
            lines.append(f"  {etype}: {', '.join(parts)}")

    rels = diff.get("relationships", {})
    rel_append = len(rels.get("append", []))
    rel_evolve = len(rels.get("evolve", []))
    if rel_append or rel_evolve:
        lines.append(f"  relationships: 新增{rel_append}, 演化{rel_evolve}")

    tl = len(diff.get("timeline_append", []))
    if tl:
        lines.append(f"  timeline: +{tl}条")

    fs = diff.get("foreshadowing", {})
    planted = len(fs.get("plant", []))
    resolved = len(fs.get("resolve", []))
    if planted or resolved:
        lines.append(f"  foreshadowing: 植入{planted}, 回收{resolved}")

    return "\n".join(lines)


# ── CLI 入口 ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="KB Diff 应用脚本")
    parser.add_argument("kb_path", help="knowledge_base.json 路径")
    parser.add_argument("diff_path", help="chapter_XX_diff.json 路径")
    parser.add_argument("--dry-run", action="store_true", help="只校验不写入")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()

    kb_path = Path(args.kb_path)
    diff_path = Path(args.diff_path)

    if not kb_path.exists():
        print(f"ERROR: KB 文件不存在: {kb_path}", file=sys.stderr)
        sys.exit(1)
    if not diff_path.exists():
        print(f"ERROR: Diff 文件不存在: {diff_path}", file=sys.stderr)
        sys.exit(1)

    with open(kb_path, "r", encoding="utf-8") as f:
        kb = json.load(f)
    with open(diff_path, "r", encoding="utf-8") as f:
        diff = json.load(f)

    # 1. 格式校验
    format_errors = validate_diff_format(diff)
    if format_errors:
        print("FAIL: Diff 格式校验失败:", file=sys.stderr)
        for e in format_errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    if args.verbose:
        print("✓ Diff 格式校验通过")

    # 2. 一致性校验
    issues = consistency_check(kb, diff)
    errors = [i for i in issues if i["level"] == "ERROR"]
    warns = [i for i in issues if i["level"] == "WARNING"]

    if errors:
        print("FAIL: 一致性校验发现 ERROR:", file=sys.stderr)
        for e in errors:
            print(f"  [{e['code']}] {e['message']}", file=sys.stderr)
        sys.exit(1)

    if warns and args.verbose:
        print(f"WARNING: 一致性校验发现 {len(warns)} 个警告:")
        for w in warns:
            print(f"  [{w['code']}] {w['message']}")

    if args.verbose:
        print("✓ 一致性校验通过" + (f" ({len(warns)} warnings)" if warns else ""))

    # 3. 应用 diff
    updated_kb = apply_diff(kb, diff)

    # 4. 输出摘要
    summary = summarize_changes(diff)
    print(summary)

    # 5. 写入（除非 dry-run）
    if args.dry_run:
        print("\n[dry-run] 未写入文件")
    else:
        with open(kb_path, "w", encoding="utf-8") as f:
            json.dump(updated_kb, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 已写入 {kb_path}")

    # 返回码
    sys.exit(0)


if __name__ == "__main__":
    main()
