"""
kb_slicer.py

Builds a compact knowledge-base slice for the current chapter context.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def slice_kb(
    kb_path: Path,
    character_ids: list[str] | None = None,
    location_ids: list[str] | None = None,
    include_foreshadowing: bool = True,
) -> dict[str, Any]:
    """Return a reduced KB payload for prompt injection."""
    character_ids = character_ids or []
    location_ids = location_ids or []

    kb = _read_json(kb_path)
    entities = kb.get("entities", {})

    all_chars = entities.get("characters", {}) if isinstance(entities, dict) else {}
    selected_chars = {
        cid: all_chars[cid]
        for cid in character_ids
        if isinstance(all_chars, dict) and cid in all_chars
    }

    all_locs = entities.get("locations", {}) if isinstance(entities, dict) else {}
    selected_locs = {
        lid: all_locs[lid]
        for lid in location_ids
        if isinstance(all_locs, dict) and lid in all_locs
    }

    all_items = entities.get("items", {}) if isinstance(entities, dict) else {}
    selected_items = {}
    if isinstance(all_items, dict):
        for item_id, item in all_items.items():
            owner = str(item.get("current_owner", "")) if isinstance(item, dict) else ""
            if owner and owner in character_ids:
                selected_items[item_id] = item

    relationships = kb.get("relationships", [])
    selected_relationships: list[dict[str, Any]] = []
    if isinstance(relationships, list):
        for rel in relationships:
            if not isinstance(rel, dict):
                continue
            a = str(rel.get("entity_a", ""))
            b = str(rel.get("entity_b", ""))
            if a in character_ids or b in character_ids:
                selected_relationships.append(rel)

    foreshadowing = {}
    if include_foreshadowing:
        all_foreshadowing = kb.get("foreshadowing", {})
        planted = []
        if isinstance(all_foreshadowing, dict):
            planted = [
                x
                for x in all_foreshadowing.get("planted", [])
                if isinstance(x, dict) and x.get("status") == "pending"
            ]
        foreshadowing = {"planted": planted[:10]}

    timeline = kb.get("timeline", [])
    timeline_tail = timeline[-5:] if isinstance(timeline, list) else []

    return {
        "characters": selected_chars,
        "locations": selected_locs,
        "items": selected_items,
        "relationships": selected_relationships,
        "foreshadowing": foreshadowing,
        "timeline_tail": timeline_tail,
        "style_profile": kb.get("style_profile", {}),
    }


def format_kb_slice(kb_slice: dict[str, Any], max_chars: int = 3500) -> str:
    """Serialize KB slice for prompt injection with a safe length cap."""
    text = json.dumps(kb_slice, ensure_ascii=False, indent=2)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."
