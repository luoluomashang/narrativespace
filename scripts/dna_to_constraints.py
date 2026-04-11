"""
dna_to_constraints.py

Condense dna_human_*.yaml into a short executable constraint list.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from exc


def _flatten(node: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        out.append(node)
        for v in node.values():
            _flatten(v, out)
    elif isinstance(node, list):
        for item in node:
            _flatten(item, out)


def _extract_list_like(data: Any, keys: list[str], limit: int) -> list[str]:
    pool: list[dict[str, Any]] = []
    _flatten(data, pool)
    out: list[str] = []
    for item in pool:
        for key in keys:
            val = item.get(key)
            if isinstance(val, list):
                for x in val:
                    s = str(x).strip()
                    if s and s not in out:
                        out.append(s)
            elif isinstance(val, str):
                s = val.strip()
                if s and s not in out:
                    out.append(s)
            if len(out) >= limit:
                return out[:limit]
    return out[:limit]


def load_dna_constraints(style_modules_dir: Path, max_do: int = 5, max_dont: int = 5) -> list[str]:
    dna_files = sorted(style_modules_dir.glob("dna_human_*.yaml"))
    if not dna_files:
        dna_files = sorted(style_modules_dir.glob("clone_*.yaml"))

    if dna_files:
        print(f"[dna_to_constraints] 加载 {len(dna_files)} 个 DNA 约束文件：{[f.name for f in dna_files]}")
    if not dna_files:
        print(
            "[dna_to_constraints] ERROR: 未找到 DNA 约束文件（dna_human_*.yaml / clone_*.yaml），dna_constraints 将为空。",
            file=sys.stderr,
        )
        print(
            "[dna_to_constraints] 下一步：运行 `python scripts/slice_library.py write-dna --project-dir <project> --project-name <name> --dna-json <file>` "
            "或手动放置 dna_human_*.yaml 到 .xushikj/config/style_modules/",
            file=sys.stderr,
        )
        return []

    dna_path = dna_files[0]
    with dna_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    do_items = _extract_list_like(data, ["do", "do_list", "dos", "preferred", "guidelines"], max_do)
    dont_items = _extract_list_like(data, ["dont", "dont_list", "donts", "forbidden", "avoid"], max_dont)

    lines: list[str] = [f"- [dna] source={dna_path.name}"]
    for item in do_items:
        lines.append(f"- [dna-do] {item}")
    for item in dont_items:
        lines.append(f"- [dna-dont] {item}")

    return lines[: 1 + max_do + max_dont]
