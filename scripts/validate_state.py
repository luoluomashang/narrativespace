"""
Validate Lite project prerequisites.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

STEP_DEPENDENCIES = {
    "project_card": ["reply_length", "target_platform"],
    "7": ["project_card", "reply_length", "target_platform"],
    "8": ["volume_plan", "knowledge_base", "reply_length", "target_platform"],
    "10": ["knowledge_base", "scene_card", "summary_index", "reply_length", "target_platform"],
    # humanizer uses a named step because it is an optional post-process hook, not a numbered pipeline step.
    "humanizer": ["chapter_file", "reply_length", "target_platform"],
}


def _reconfigure_stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _resolve_xushikj_dir(project_dir: Path) -> Path:
    return project_dir if project_dir.name == ".xushikj" else project_dir / ".xushikj"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def _count_chinese_chars_with_script(chapter_path: Path) -> int:
    script_path = Path(__file__).resolve().parent / "chinese_char_count.py"
    proc = subprocess.run(
        [sys.executable, str(script_path), "--input", str(chapter_path), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "chinese_char_count failed")
    payload = json.loads(proc.stdout)
    return int(payload.get("chinese_chars", 0))


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

    dependency_checks = {
        "project_card": ((xushikj_dir / "outline" / "project_card.md").exists(), "Step 7 之前必须已有 project_card.md"),
        "volume_plan": ((xushikj_dir / "outline" / f"volume_{state.get('current_volume', 1)}_one_page.md").exists(), "Step 8 之前必须已有当前卷一页纲"),
        "knowledge_base": (kb_path.exists(), f"Step {step} 之前必须已有 knowledge_base.json" if step == "10" else "Step 8 之前必须已有 knowledge_base.json"),
        "scene_card": (scene_path.exists(), f"Step 10 之前必须已有章节卡: {scene_path}"),
        "summary_index": (summary_path.exists(), "Step 10 之前必须已有 summary_index.md"),
        "chapter_file": (chapter_path.exists(), f"Humanizer 缺少目标章节: {chapter_path}"),
        "reply_length": (isinstance(state.get("reply_length"), int) and int(state.get("reply_length")) > 0, "进入 Lite 主流程前必须先确认 reply_length"),
        "target_platform": (isinstance(state.get("target_platform"), str) and bool(state.get("target_platform", "").strip()), "进入 Lite 主流程前必须先确认 target_platform"),
    }
    for dependency in STEP_DEPENDENCIES.get(step, []):
        ok, message = dependency_checks[dependency]
        if not ok:
            errors.append(message)

    threshold = min_chapter_chars
    if threshold is None and isinstance(state.get("reply_length"), int):
        threshold = int(state["reply_length"])

    if chapter_path.exists() and threshold is not None:
        try:
            zh_chars = _count_chinese_chars_with_script(chapter_path)
        except Exception as exc:
            errors.append(f"章节字数验收失败：{exc}")
        else:
            infos.append(f"chapter_{effective_chapter}_zh_chars={zh_chars}")
            infos.append("chapter_length_check=scripts/chinese_char_count.py")
            if zh_chars < threshold:
                errors.append(f"chapter_{effective_chapter} 中文字数不足：{zh_chars} < {threshold}")
            target_platform = str(state.get("target_platform", "")).strip().lower()
            if target_platform == "fanqie" and zh_chars > 3500:
                errors.append(f"chapter_{effective_chapter} 中文字数超出番茄硬门槛：{zh_chars} > 3500")

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
