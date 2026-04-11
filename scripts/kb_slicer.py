"""
Lite KB slicer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def slice_kb(kb_path: Path, focus_names: list[str] | None = None) -> dict[str, Any]:
    kb = _read_json(kb_path)
    focus_names = [cleaned for name in (focus_names or []) if (cleaned := name.strip())]

    characters = kb.get("characters", [])
    if not isinstance(characters, list):
        characters = []

    if focus_names:
        selected_characters = [
            item for item in characters
            if isinstance(item, dict) and str(item.get("name", "")).strip() in focus_names
        ]
    else:
        selected_characters = [item for item in characters if isinstance(item, dict)][:5]

    selected_ids = {
        str(item.get("id", ""))
        for item in selected_characters
        if isinstance(item, dict)
    }

    relationships = kb.get("relationships", [])
    if not isinstance(relationships, list):
        relationships = []
    selected_relationships = [
        item for item in relationships
        if isinstance(item, dict)
        and (
            str(item.get("source", "")) in selected_ids
            or str(item.get("target", "")) in selected_ids
        )
    ][:10]

    world_rules = kb.get("world_rules", [])
    if not isinstance(world_rules, list):
        world_rules = []

    open_loops = kb.get("open_loops", [])
    if not isinstance(open_loops, list):
        open_loops = []

    return {
        "project": kb.get("project", {}),
        "characters": selected_characters,
        "relationships": selected_relationships,
        "world_rules": world_rules[:5],
        "current_volume": kb.get("current_volume", {}),
        "open_loops": open_loops[:8],
    }


def format_kb_slice(kb_slice: dict[str, Any], max_chars: int = 3000) -> str:
    text = json.dumps(kb_slice, ensure_ascii=False, indent=2)
    return text if len(text) <= max_chars else text[: max_chars - 3] + "..."
