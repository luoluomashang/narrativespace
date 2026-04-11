"""
rule_extractor.py

Extracts a small set of rules from YAML files and converts them into
flat natural-language lines suitable for prompt assembly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML is required for rule extraction. Install with: pip install pyyaml"
    ) from exc


# Known conflict pairs. If both appear, later pair member is dropped.
CONFLICT_PAIRS: list[tuple[str, str]] = [
    ("wr_11", "ht_01"),
]


def _flatten_yaml(node: Any, out: list[dict[str, Any]]) -> None:
    """Recursively collect dict nodes from YAML tree."""
    if isinstance(node, dict):
        out.append(node)
        for value in node.values():
            _flatten_yaml(value, out)
    elif isinstance(node, list):
        for item in node:
            _flatten_yaml(item, out)


def _find_by_id(data: Any, wanted_id: str) -> dict[str, Any] | None:
    pool: list[dict[str, Any]] = []
    _flatten_yaml(data, pool)
    for item in pool:
        if item.get("id") == wanted_id:
            return item
    return None


def _line_from_rule(rule_id: str, payload: dict[str, Any]) -> str:
    name = str(payload.get("name", "")).strip()
    # Priority: content > description > rule
    content = str(payload.get("content", "")).strip().replace("\n", " ")
    if not content:
        content = str(payload.get("description", "")).strip().replace("\n", " ")
    if not content:
        content = str(payload.get("rule", "")).strip().replace("\n", " ")
    short = " ".join(content.split())
    if len(short) > 160:
        short = short[:157] + "..."
    if not short:
        import sys
        print(
            f"[WARNING] _line_from_rule: rule '{rule_id}' has no extractable text (content/description/rule all empty).",
            file=sys.stderr,
        )
        return f"- [{rule_id}]"
    if name:
        return f"- [{rule_id}] {name}: {short}"
    return f"- [{rule_id}] {short}"


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _apply_conflict_screen(rule_ids: Iterable[str]) -> list[str]:
    selected = list(dict.fromkeys(rule_ids))
    remove: set[str] = set()
    selected_set = set(selected)
    for first, second in CONFLICT_PAIRS:
        if first in selected_set and second in selected_set:
            remove.add(second)
    return [rid for rid in selected if rid not in remove]


def extract_rules(config_dir: Path, sources: list[dict[str, Any]], max_rules: int = 10) -> list[str]:
    """
    sources format:
    [{"file": "writing_rules.yaml", "ids": ["wr_01", "wr_02"]}, ...]
    """
    lines: list[str] = []
    for source in sources:
        file_name = source.get("file")
        ids: list[str] = source.get("ids", [])
        if not file_name:
            continue

        yaml_path = config_dir / file_name
        if not yaml_path.exists():
            lines.append(f"- [warning] Missing config file: {file_name}")
            continue

        data = _read_yaml(yaml_path)
        if not ids:
            # For non-ID sources, emit a short source marker only.
            lines.append(f"- [source] Loaded {file_name}")
            continue

        ids = _apply_conflict_screen(ids)
        for rule_id in ids:
            rule = _find_by_id(data, rule_id)
            if rule is None:
                lines.append(f"- [warning] Rule {rule_id} not found in {file_name}")
                continue
            lines.append(_line_from_rule(rule_id, rule))
            if len(lines) >= max_rules:
                return lines

    return lines[:max_rules]


def extract_forbidden_words(style_rules_path: Path, limit: int = 25) -> list[str]:
    """Best-effort extraction of warning words list from style_rules.yaml."""
    if not style_rules_path.exists():
        return []

    data = _read_yaml(style_rules_path)
    warning_words = data.get("warning_words", {}) if isinstance(data, dict) else {}
    values = warning_words.get("list", []) if isinstance(warning_words, dict) else []

    if not isinstance(values, list):
        return []
    words = [str(x).strip() for x in values if str(x).strip()]
    return words[:limit]


def extract_core_rules(core_rules_path: Path, limit: int = 15) -> list[str]:
    """Extract compact rule lines from config/core_15_rules.yaml."""
    if not core_rules_path.exists():
        return []

    data = _read_yaml(core_rules_path)
    rules = data.get("rules", []) if isinstance(data, dict) else []
    if not isinstance(rules, list):
        return []

    lines: list[str] = []
    for item in rules:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("id", "core")).strip() or "core"
        text = str(item.get("text", "")).strip().replace("\n", " ")
        if text:
            lines.append(f"- [{rid}] {text}")
        if len(lines) >= limit:
            break
    return lines
