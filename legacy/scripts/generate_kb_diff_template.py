#!/usr/bin/env python3
"""
generate_kb_diff_template.py — KB Diff 半自动模板生成器

从场景规划文件（scene_plan）读取 KB 更新预期，结合当前知识库状态，
输出预填充的 kb_diffs/chapter_NN_diff.json 骨架文件。

用法:
    python generate_kb_diff_template.py --project-dir /path/to/project --chapter 15
    python generate_kb_diff_template.py --project-dir . --chapter 15 --cycle cycle_001
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="从场景规划生成 KB Diff 模板文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        type=Path,
        help="项目根目录（.xushikj/ 所在位置）",
    )
    parser.add_argument(
        "--chapter",
        required=True,
        type=int,
        metavar="N",
        help="目标章节号",
    )
    parser.add_argument(
        "--cycle",
        type=str,
        default=None,
        metavar="CYCLE_ID",
        help="场景规划所在 cycle 目录 ID（如 cycle_001）；不指定时自动探测最新 cycle",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="若输出文件已存在则覆盖",
    )
    return parser


def _load_json(path: Path) -> dict:
    """读取 JSON 文件，自动处理 BOM。"""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return json.loads(raw.decode("utf-8"))


def _find_latest_cycle(scenes_dir: Path) -> str | None:
    """探测 scenes/ 下最新的 cycle 目录。"""
    cycles = sorted(
        [d.name for d in scenes_dir.iterdir() if d.is_dir() and d.name.startswith("cycle_")],
        reverse=True,
    )
    return cycles[0] if cycles else None


def _extract_kb_hints_from_scene_plan(scene_plan_path: Path) -> list[dict]:
    """
    从 scene_plan Markdown 文件提取 KB 更新提示。
    查找 '## 伏笔操作' 和 '## 角色弧光' 两个章节的内容。
    """
    hints: list[dict] = []
    if not scene_plan_path.exists():
        return hints

    content = scene_plan_path.read_text(encoding="utf-8", errors="replace")

    # 提取伏笔操作节
    foreshadow_block = re.search(
        r"## 伏笔操作\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    )
    if foreshadow_block:
        for line in foreshadow_block.group(1).splitlines():
            line = line.strip(" -•*")
            if line:
                hints.append({"type": "foreshadowing_hint", "description": line})

    # 提取角色弧光节
    arc_block = re.search(
        r"## 角色弧光\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    )
    if arc_block:
        for line in arc_block.group(1).splitlines():
            line = line.strip(" -•*")
            if not line:
                continue
            # 格式示例: "**角色名**：当前阶段 → 本场景后阶段"
            m = re.match(r"\*?\*?(.+?)\*?\*?[：:]\s*(.+?)\s*(?:→|->)+\s*(.+)", line)
            if m:
                hints.append({
                    "type": "arc_transition",
                    "character": m.group(1).strip(),
                    "from_stage": m.group(2).strip(),
                    "to_stage": m.group(3).strip(),
                })
            else:
                hints.append({"type": "arc_hint", "description": line})

    return hints


def _build_diff_skeleton(chapter: int, kb: dict, hints: list[dict]) -> dict:
    """构建 KB diff 骨架。"""
    chapter_str = f"{chapter:02d}"
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    diff: dict = {
        "_schema": "kb-diff-v1",
        "_generated_by": "generate_kb_diff_template.py",
        "_note": f"第{chapter}章 KB diff 半自动模板，请补充实际变更内容",
        "chapter": chapter,
        "generated_at": now,
        "entities": {
            "update": [],
            "add": [],
        },
        "relationships": {
            "add": [],
            "update": [],
        },
        "foreshadowing": {
            "plant": [],
            "resolve": [],
            "escalate": [],
        },
        "timeline": {
            "add": [],
        },
    }

    # 用 KB 中存活角色填充 update 骨架（仅提取最多5个作为参考）
    entities = kb.get("entities", {})
    characters = entities.get("characters", [])
    if isinstance(characters, list):
        sample_chars = characters[:5]
    else:
        sample_chars = list(characters.values())[:5]

    for char in sample_chars:
        char_id = char.get("char_id") or char.get("id", "")
        if char_id and char.get("status", "") != "死亡":
            diff["entities"]["update"].append({
                "char_id": char_id,
                "_action": "FILL_OR_DELETE",
                "status": "__unchanged__",
                "arc_stage": "__unchanged__",
                "snapshot": "__fill_if_changed__",
            })

    # 根据场景规划提示预填充伏笔操作
    pending_foreshadows = []
    fs_data = kb.get("foreshadowing", {})
    planted = fs_data.get("planted", []) if isinstance(fs_data, dict) else []
    for fs in planted:
        if isinstance(fs, dict) and fs.get("status") == "pending":
            pending_foreshadows.append(fs.get("id") or fs.get("foreshadow_id", ""))

    for hint in hints:
        h_type = hint.get("type")
        if h_type == "foreshadowing_hint":
            diff["foreshadowing"]["plant"].append({
                "_from_scene_plan": hint["description"],
                "id": "__assign_id__",
                "description": hint["description"],
                "status": "pending",
                "planted_at_chapter": chapter,
            })
        elif h_type == "arc_transition":
            diff["entities"]["update"].append({
                "_from_scene_plan": True,
                "char_id": f"__find_id_for_{hint['character']}__",
                "arc_stage": hint["to_stage"],
                "_previous_arc_stage": hint["from_stage"],
            })

    # 待回收伏笔提示（如果场景规划提到了回收）
    if pending_foreshadows:
        diff["foreshadowing"]["_pending_ids_for_reference"] = pending_foreshadows

    return diff


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = build_arg_parser()
    args = parser.parse_args()

    project_dir = args.project_dir.resolve()
    xushikj = project_dir / ".xushikj"
    chapter: int = args.chapter

    if not xushikj.exists():
        print(f"错误：.xushikj 目录不存在: {xushikj}", file=sys.stderr)
        sys.exit(1)

    # 探测 cycle
    scenes_dir = xushikj / "scenes"
    cycle_id = args.cycle
    if not cycle_id:
        cycle_id = _find_latest_cycle(scenes_dir)
    if not cycle_id:
        print("错误：未找到场景规划 cycle 目录（scenes/ 下无 cycle_* 子目录）", file=sys.stderr)
        sys.exit(1)

    scene_plan_path = scenes_dir / cycle_id / "scene_plans" / f"chapter_{chapter:02d}.md"
    if not scene_plan_path.exists():
        # 尝试不补零格式
        scene_plan_path = scenes_dir / cycle_id / "scene_plans" / f"chapter_{chapter}.md"

    if not scene_plan_path.exists():
        print(f"警告：场景规划文件未找到: {scene_plan_path}，将生成最小骨架", file=sys.stderr)
        hints: list[dict] = []
    else:
        print(f"读取场景规划: {scene_plan_path.relative_to(project_dir)}")
        hints = _extract_kb_hints_from_scene_plan(scene_plan_path)
        print(f"  提取到 {len(hints)} 条 KB 更新提示")

    # 读取当前 KB
    kb_path = xushikj / "knowledge_base.json"
    if kb_path.exists():
        try:
            kb = _load_json(kb_path)
            print(f"读取知识库: {kb_path.relative_to(project_dir)}")
        except Exception as exc:
            print(f"警告：知识库读取失败 ({exc})，将使用空 KB", file=sys.stderr)
            kb = {}
    else:
        print("警告：knowledge_base.json 不存在，将使用空 KB", file=sys.stderr)
        kb = {}

    # 构建 diff 骨架
    diff = _build_diff_skeleton(chapter, kb, hints)

    # 输出路径
    kb_diffs_dir = xushikj / "kb_diffs"
    kb_diffs_dir.mkdir(parents=True, exist_ok=True)
    out_path = kb_diffs_dir / f"chapter_{chapter:02d}_diff.json"

    if out_path.exists() and not args.force:
        print(f"错误：输出文件已存在: {out_path.relative_to(project_dir)}")
        print("  使用 --force 覆盖，或手动删除后重试。")
        sys.exit(1)

    out_path.write_text(
        json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✅ 已生成 KB diff 模板: {out_path.relative_to(project_dir)}")
    print("  请在文件中搜索 '__' 标记，补充实际变更内容后，用 apply_kb_diff.py 应用。")


if __name__ == "__main__":
    main()
