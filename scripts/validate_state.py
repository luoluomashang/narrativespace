"""
validate_state.py

Preflight checks for .xushikj runtime state and writing prerequisites.

Usage:
  python scripts/validate_state.py --project-dir .
  python scripts/validate_state.py --project-dir . --chapter 3 --strict
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ZH_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


def _count_zh_chars(text: str) -> int:
    return len(ZH_CHAR_RE.findall(text))


def _resolve_xushikj_dir(project_dir: Path) -> Path:
    if project_dir.name == ".xushikj":
        return project_dir
    return project_dir / ".xushikj"


def _reconfigure_stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _detect_cycle_dir(scenes_root: Path, requested_cycle: str) -> tuple[str, Path | None]:
    preferred = scenes_root / requested_cycle
    if preferred.exists():
        return requested_cycle, preferred

    if requested_cycle == "cycle_001" and (scenes_root / "cycle_1").exists():
        return "cycle_1", scenes_root / "cycle_1"
    if requested_cycle == "cycle_1" and (scenes_root / "cycle_001").exists():
        return "cycle_001", scenes_root / "cycle_001"

    candidates = sorted([p for p in scenes_root.glob("cycle_*") if p.is_dir()])
    if candidates:
        return candidates[-1].name, candidates[-1]
    return requested_cycle, None


def validate(
    project_dir: Path,
    chapter: int | None,
    strict: bool,
    for_step10: bool,
    min_chapter_chars: int | None,
) -> int:
    xushikj_dir = _resolve_xushikj_dir(project_dir)
    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    if not xushikj_dir.exists():
        print(f"[ERROR] .xushikj 目录不存在: {xushikj_dir}")
        return 2

    state_path = xushikj_dir / "state.json"
    if not state_path.exists():
        print(f"[ERROR] state.json 不存在: {state_path}")
        return 2

    try:
        state = _load_json(state_path)
    except json.JSONDecodeError as exc:
        print(
            f"[ERROR] state.json JSON 损坏: line={exc.lineno}, col={exc.colno}, msg={exc.msg}",
            file=sys.stderr,
        )
        return 2
    except OSError as exc:
        print(f"[ERROR] 读取 state.json 失败: {exc}", file=sys.stderr)
        return 2

    writing_mode = str(state.get("config", {}).get("writing_mode", "pipeline"))
    if writing_mode not in {"pipeline", "interactive"}:
        warnings.append(f"config.writing_mode 非法值: {writing_mode}（建议 pipeline 或 interactive）")

    if for_step10 and chapter is None:
        errors.append("--for-step10 模式下必须提供 --chapter。")

    cycle_id = str(state.get("rolling_context", {}).get("cycle_id", "cycle_1"))
    scenes_root = xushikj_dir / "scenes"
    effective_cycle_id, cycle_dir = _detect_cycle_dir(scenes_root, cycle_id)
    if cycle_dir is None:
        errors.append(f"未找到场景目录: {scenes_root}/cycle_*")
    else:
        infos.append(f"cycle_id={cycle_id}, effective_cycle={effective_cycle_id}")
        scene_list = cycle_dir / "scene_list.md"
        scene_plans_dir = cycle_dir / "scene_plans"
        if not scene_list.exists():
            warnings.append(f"缺少 scene_list: {scene_list}")
        if not scene_plans_dir.exists():
            errors.append(f"缺少 scene_plans 目录: {scene_plans_dir}")
        elif chapter is not None:
            scene_plan = scene_plans_dir / f"chapter_{chapter}.md"
            if not scene_plan.exists():
                errors.append(f"缺少 chapter scene plan: {scene_plan}")
            else:
                scene_text = scene_plan.read_text(encoding="utf-8")
                if "scene_type" not in scene_text:
                    errors.append(f"scene_plan 缺少 scene_type 字段: {scene_plan}")

    kb_path = xushikj_dir / "knowledge_base.json"
    if not kb_path.exists():
        warnings.append(f"缺少知识库: {kb_path}")

    snippet_dir = xushikj_dir / "benchmark" / "style_snippets"
    snippet_files = sorted(snippet_dir.glob("*.md")) if snippet_dir.exists() else []
    if not snippet_files:
        warnings.append(
            "未检测到 style_snippets（需先执行 write-snippet 才会注入 style_snippet）"
        )

    style_modules_dir = xushikj_dir / "config" / "style_modules"
    dna_files = sorted(style_modules_dir.glob("dna_human_*.yaml")) if style_modules_dir.exists() else []
    clone_files = sorted(style_modules_dir.glob("clone_*.yaml")) if style_modules_dir.exists() else []
    if not dna_files and not clone_files:
        warnings.append(
            "未检测到 DNA 约束文件（dna_human_*.yaml / clone_*.yaml），Step10 将缺少 dna_constraints"
        )

    if for_step10:
        if not kb_path.exists():
            errors.append(f"Step10 缺少知识库: {kb_path}")
        if not snippet_files:
            errors.append("Step10 缺少 style_snippets，禁止继续写作。")
        if not dna_files and not clone_files:
            errors.append("Step10 缺少 DNA 约束文件，禁止继续写作。")

    if chapter is not None and min_chapter_chars is not None:
        chapter_file = xushikj_dir / "chapters" / f"chapter_{chapter}.md"
        if not chapter_file.exists():
            errors.append(f"章节文件不存在，无法校验字数: {chapter_file}")
        else:
            text = chapter_file.read_text(encoding="utf-8")
            zh_count = _count_zh_chars(text)
            infos.append(f"chapter_{chapter} 中文字数={zh_count}")
            if zh_count < min_chapter_chars:
                errors.append(
                    f"chapter_{chapter} 中文字数不足：{zh_count} < {min_chapter_chars}"
                )

    print(f"[validate_state] project={project_dir}")
    print(f"[validate_state] mode={writing_mode}")
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
    p = argparse.ArgumentParser(description="Validate .xushikj state and writing prerequisites")
    p.add_argument("--project-dir", required=True, type=Path, help="Project root or .xushikj path")
    p.add_argument("--chapter", type=int, help="Optional chapter number for scene plan existence check")
    p.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures (exit code 1)",
    )
    p.add_argument(
        "--for-step10",
        action="store_true",
        help="Enable Step10 hard checks (scene/kb/snippet/dna required)",
    )
    p.add_argument(
        "--min-chapter-chars",
        type=int,
        help="Optional minimum Chinese character count check for chapter file",
    )
    return p


def main() -> int:
    _reconfigure_stdout_utf8()
    args = build_parser().parse_args()
    return validate(
        project_dir=args.project_dir,
        chapter=args.chapter,
        strict=args.strict,
        for_step10=args.for_step10,
        min_chapter_chars=args.min_chapter_chars,
    )


if __name__ == "__main__":
    sys.exit(main())
