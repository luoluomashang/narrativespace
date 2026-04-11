"""
Validate Lite project prerequisites.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ZH_CHAR_RE = re.compile(r"[一-鿿]")


def _reconfigure_stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _count_zh_chars(text: str) -> int:
    return len(ZH_CHAR_RE.findall(text))


def _resolve_xushikj_dir(project_dir: Path) -> Path:
    return project_dir if project_dir.name == ".xushikj" else project_dir / ".xushikj"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def validate(project_dir: Path, chapter: int | None, strict: bool, for_step: str | None, min_chapter_chars: int | None) -> int:
    xushikj_dir = _resolve_xushikj_dir(project_dir.resolve())
    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    if not xushikj_dir.exists():
        print(f"[ERROR] 缺少 .xushikj 目录: {xushikj_dir}")
        return 2

    state_path = xushikj_dir / "state.json"
    if not state_path.exists():
        print(f"[ERROR] 缺少 state.json: {state_path}")
        return 2

    state = _load_json(state_path)
    infos.append(f"current_step={state.get('current_step', '')}")
    infos.append(f"current_chapter={state.get('current_chapter', 1)}")

    step = for_step or ""
    if step == "writing":
        step = "10"

    kb_path = xushikj_dir / "knowledge_base.json"
    summary_path = xushikj_dir / "summaries" / "summary_index.md"
    if not kb_path.exists():
        warnings.append(f"缺少知识库: {kb_path}")
    if not summary_path.exists():
        warnings.append(f"缺少摘要索引: {summary_path}")

    effective_chapter = chapter or int(state.get("current_chapter", 1))
    scene_path = xushikj_dir / "scenes" / f"chapter_{effective_chapter}.md"
    chapter_path = xushikj_dir / "chapters" / f"chapter_{effective_chapter}.md"

    if step == "7" and not (xushikj_dir / "outline" / "project_card.md").exists():
        errors.append("Step 7 之前必须已有 project_card.md")
    if step == "8":
        if not (xushikj_dir / "outline" / f"volume_{state.get('current_volume', 1)}_one_page.md").exists():
            errors.append("Step 8 之前必须已有当前卷一页纲")
        if not kb_path.exists():
            errors.append("Step 8 之前必须已有 knowledge_base.json")
    if step == "10":
        if not kb_path.exists():
            errors.append("Step 10 缺少 knowledge_base.json")
        if not scene_path.exists():
            errors.append(f"Step 10 缺少章节卡: {scene_path}")
        if not summary_path.exists():
            errors.append("Step 10 缺少 summary_index.md")
    if step == "humanizer" and not chapter_path.exists():
        errors.append(f"Humanizer 缺少目标章节: {chapter_path}")

    if chapter_path.exists() and min_chapter_chars is not None:
        zh_chars = _count_zh_chars(chapter_path.read_text(encoding="utf-8"))
        infos.append(f"chapter_{effective_chapter}_zh_chars={zh_chars}")
        if zh_chars < min_chapter_chars:
            errors.append(f"chapter_{effective_chapter} 中文字数不足：{zh_chars} < {min_chapter_chars}")

    print(f"[validate_state] project={project_dir}")
    for msg in infos:
        print(f"[INFO] {msg}")
    for msg in warnings:
        print(f"[WARNING] {msg}")
    for msg in errors:
        print(f"[ERROR] {msg}")

    if errors:
        return 1
    if strict and warnings:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate narrativespace Lite state")
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--chapter", type=int)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--for-step", help="Optional target step: 7 / 8 / 10 / humanizer")
    parser.add_argument("--for-step10", action="store_true", help="Compatibility alias for --for-step 10")
    parser.add_argument("--min-chapter-chars", type=int)
    return parser


def main() -> int:
    _reconfigure_stdout_utf8()
    args = build_parser().parse_args()
    for_step = "10" if args.for_step10 and not args.for_step else args.for_step
    return validate(args.project_dir, args.chapter, args.strict, for_step, args.min_chapter_chars)


if __name__ == "__main__":
    raise SystemExit(main())
