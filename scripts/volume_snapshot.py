#!/usr/bin/env python3
"""
volume_snapshot.py — 卷末状态快照生成器

在一卷写作完成后，提取存活角色状态、待兑现伏笔、卷内情节摘要，
写入 .xushikj/timelines/volume_{N}_snapshot.json，
同时更新 state.json → volume_timeline.volume_snapshots。

用法:
    python volume_snapshot.py --project-dir /path/to/project --volume 1
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="生成卷末状态快照",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        type=Path,
        help="项目根目录（.xushikj/ 所在位置）",
    )
    parser.add_argument(
        "--volume",
        required=True,
        type=int,
        metavar="N",
        help="卷号（从 1 开始）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="若快照文件已存在则覆盖",
    )
    return parser


def _load_json_bom_safe(path: Path) -> dict:
    """读取 JSON，自动处理 BOM。"""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return json.loads(raw.decode("utf-8"))


def _extract_alive_characters(kb: dict) -> list[dict]:
    """提取存活角色列表。"""
    result = []
    characters = kb.get("entities", {}).get("characters", [])
    if isinstance(characters, dict):
        characters = list(characters.values())
    for char in characters:
        if not isinstance(char, dict):
            continue
        if char.get("status", "") == "死亡":
            continue
        result.append({
            "char_id": char.get("char_id") or char.get("id", ""),
            "name": char.get("name", ""),
            "arc_stage": char.get("arc_stage", ""),
            "snapshot": char.get("snapshot", ""),
            "status": char.get("status", ""),
        })
    return result


def _extract_planted_foreshadowing(kb: dict) -> list[dict]:
    """提取待兑现伏笔。"""
    result = []
    fs_data = kb.get("foreshadowing", {})
    if isinstance(fs_data, dict):
        planted = fs_data.get("planted", [])
    else:
        planted = []
    for fs in planted:
        if not isinstance(fs, dict):
            continue
        if fs.get("status", "") == "pending":
            result.append({
                "id": fs.get("id") or fs.get("foreshadow_id", ""),
                "description": fs.get("description", ""),
                "urgency": fs.get("urgency", ""),
                "planted_at_chapter": fs.get("planted_at_chapter") or fs.get("chapter", ""),
            })
    return result


def _extract_completed_arcs(kb: dict, volume: int) -> list[dict]:
    """提取本卷内完成弧光转变的角色。"""
    result = []
    characters = kb.get("entities", {}).get("characters", [])
    if isinstance(characters, dict):
        characters = list(characters.values())
    for char in characters:
        if not isinstance(char, dict):
            continue
        arc_history = char.get("arc_history", [])
        if not isinstance(arc_history, list):
            continue
        for entry in arc_history:
            if not isinstance(entry, dict):
                continue
            if entry.get("volume") == volume or str(entry.get("volume", "")) == str(volume):
                result.append({
                    "char_id": char.get("char_id") or char.get("id", ""),
                    "name": char.get("name", ""),
                    "arc_transition": entry,
                })
                break
    return result


def _extract_volume_summary_from_index(summary_index_path: Path, volume: int) -> str:
    """从 summary_index.md 提取本卷相关内容（简单截取最后500字）。"""
    if not summary_index_path.exists():
        return ""
    content = summary_index_path.read_text(encoding="utf-8", errors="replace")
    # 尝试找到卷分节标记（如 "## 第{N}卷" 或 "# 第{N}卷"）
    vol_patterns = [
        rf"## 第{volume}卷",
        rf"# 第{volume}卷",
        rf"## 卷{volume}[：:]",
        rf"# 卷{volume}[：:]",
        rf"Volume {volume}",
    ]
    for pat in vol_patterns:
        m = re.search(pat, content)
        if m:
            segment = content[m.start():]
            # 截到下一个同级标题
            next_vol = re.search(r"\n#+\s", segment[2:])
            if next_vol:
                segment = segment[: next_vol.start() + 2]
            words = segment.strip()
            # 最多500字
            return words[:500] if len(words) > 500 else words

    # 如果找不到卷标记，返回全文最后500字
    tail = content[-500:] if len(content) > 500 else content
    return tail.strip()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = build_arg_parser()
    args = parser.parse_args()

    project_dir = args.project_dir.resolve()
    xushikj = project_dir / ".xushikj"
    volume: int = args.volume

    if not xushikj.exists():
        print(f"错误：.xushikj 目录不存在: {xushikj}", file=sys.stderr)
        sys.exit(1)

    # 输出路径检查
    timelines_dir = xushikj / "timelines"
    timelines_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = timelines_dir / f"volume_{volume}_snapshot.json"

    if snapshot_path.exists() and not args.force:
        print(f"错误：快照文件已存在: {snapshot_path.relative_to(project_dir)}")
        print("  使用 --force 覆盖，或手动删除后重试。")
        sys.exit(1)

    # 加载 KB
    kb_path = xushikj / "knowledge_base.json"
    if kb_path.exists():
        try:
            kb = _load_json_bom_safe(kb_path)
            print(f"读取知识库: {kb_path.relative_to(project_dir)}")
        except Exception as exc:
            print(f"警告：知识库读取失败 ({exc})，将使用空 KB", file=sys.stderr)
            kb = {}
    else:
        print("警告：knowledge_base.json 不存在，将使用空 KB", file=sys.stderr)
        kb = {}

    # 加载 summary_index.md
    summary_index_path = xushikj / "summaries" / "summary_index.md"
    volume_summary = _extract_volume_summary_from_index(summary_index_path, volume)
    print(f"提取卷{volume}情节摘要: {len(volume_summary)} 字")

    # 提取各字段
    alive_characters = _extract_alive_characters(kb)
    planted_foreshadowing = _extract_planted_foreshadowing(kb)
    completed_arcs = _extract_completed_arcs(kb, volume)

    print(f"  存活角色: {len(alive_characters)} 个")
    print(f"  待兑现伏笔: {len(planted_foreshadowing)} 条")
    print(f"  本卷完成弧光转变: {len(completed_arcs)} 个")

    # 读取当前章节号
    state_path = xushikj / "state.json"
    current_chapter = 0
    if state_path.exists():
        try:
            state = _load_json_bom_safe(state_path)
            current_chapter = state.get("chapter_state", {}).get("current_chapter", 0)
        except Exception:
            pass

    # 构建快照
    snapshot: dict = {
        "_schema": "volume-snapshot-v1",
        "_generated_by": "volume_snapshot.py",
        "volume": volume,
        "volume_end_chapter": current_chapter,
        "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "alive_characters": alive_characters,
        "planted_foreshadowing": planted_foreshadowing,
        "completed_arcs": completed_arcs,
        "volume_summary": volume_summary,
    }

    # 写入快照文件
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✅ 已写入快照: {snapshot_path.relative_to(project_dir)}")

    # 更新 state.json volume_timeline
    if state_path.exists():
        try:
            state = _load_json_bom_safe(state_path)
            vt = state.setdefault("volume_timeline", {})
            snapshots = vt.setdefault("volume_snapshots", {})
            snapshots[str(volume)] = str(snapshot_path.relative_to(xushikj))
            state["updated_at"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            state_path.write_text(
                json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"✅ 已更新 state.json → volume_timeline.volume_snapshots[{volume}]")
        except Exception as exc:
            print(f"  警告：state.json 更新失败: {exc}", file=sys.stderr)

    print(f"\n卷 {volume} 快照生成完成。")
    print(f"  下一卷开始时可通过 init.py --upgrade 应用最新补丁，")
    print(f"  并参考快照中的 alive_characters 和 planted_foreshadowing 开始跨卷规划。")


if __name__ == "__main__":
    main()
