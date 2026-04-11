"""
assemble_prompt.py

Phase-1 orchestrator for step-based prompt assembly.

Usage examples:
  python scripts/assemble_prompt.py --project-dir .xushikj --step 1
  python scripts/assemble_prompt.py --project-dir .xushikj --step 10 --chapter 5
  python scripts/assemble_prompt.py --project-dir .xushikj --status
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Any

from dna_to_constraints import load_dna_constraints
from kb_slicer import format_kb_slice, slice_kb
from rule_extractor import extract_core_rules, extract_forbidden_words, extract_rules

SKILL_ROOT = Path(__file__).resolve().parent.parent


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        msg = (
            f"Invalid JSON in {path} at line {exc.lineno}, col {exc.colno}. "
            "Run a JSON validator or restore from a known-good backup."
        )
        raise ValueError(msg) from exc
    except OSError as exc:
        raise ValueError(f"Unable to read JSON file: {path} ({exc})") from exc


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _resolve_paths(project_dir: Path) -> tuple[Path, Path]:
    """Return (project_root, xushikj_dir)."""
    if project_dir.name == ".xushikj":
        return project_dir.parent, project_dir
    xushikj_dir = project_dir / ".xushikj"
    return project_dir, xushikj_dir


def _load_step_rule_map(scripts_dir: Path) -> dict[str, Any]:
    mapping_path = scripts_dir / "step_rule_map.json"
    if not mapping_path.exists():
        raise FileNotFoundError(f"Missing mapping file: {mapping_path}")
    return _read_json(mapping_path)


def _pick_step_key(step: str, writing_mode: str) -> str:
    if step == "10":
        return "10_interactive" if writing_mode == "interactive" else "10_pipeline"
    return step


def _resolve_writing_mode(state: dict[str, Any], override: str | None) -> str:
    if override:
        return override
    mode = str(state.get("config", {}).get("writing_mode", "pipeline"))
    if mode not in {"pipeline", "interactive"}:
        return "pipeline"
    return mode


def _read_recent_summaries(xushikj_dir: Path, last_n: int = 2) -> str:
    summaries_dir = xushikj_dir / "summaries"
    if not summaries_dir.exists():
        return "(no summaries found)"

    files = sorted(summaries_dir.glob("chapter_*_summary.md"))
    if not files:
        return "(no summaries found)"

    selected = files[-last_n:]
    chunks: list[str] = []
    for file in selected:
        content = file.read_text(encoding="utf-8")
        chunks.append(f"## {file.name}\n{content.strip()}")
    return "\n\n".join(chunks)


def _strip_yaml_front_matter(text: str) -> str:
    """Remove YAML front matter (---...---) from slice content."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def _load_style_snippet(
    state: dict[str, Any],
    scene_type: str,
    scene_intensity: str = "medium",
    xushikj_dir: Path | None = None,
) -> str:
    """Load a style slice from the user's style library.

    Load order:
    1) global library based on benchmark_state.linked_author + style_library_path
    2) local fallback .xushikj/benchmark/style_snippets

    Returns placeholder text (no error) when no matching slice is available.
    """
    not_available = "(style snippet not available)"

    try:
        import yaml  # type: ignore[import]
    except ImportError:
        print(
            "[WARNING] PyYAML is not installed. style_snippet loading is disabled. "
            "Install with: pip install pyyaml",
            file=sys.stderr,
        )
        return not_available

    benchmark_state = state.get("benchmark_state", {})
    linked_author: str | None = benchmark_state.get("linked_author")
    style_library_path = benchmark_state.get("style_library_path", "~/.narrativespace/style_library")
    global_root = Path(os.path.expanduser(str(style_library_path))).resolve()

    def _pick_and_read(base_dir: Path, candidates: list[str]) -> str:
        if not candidates:
            return ""
        exact = [f for f in candidates if f"_{scene_intensity}" in f]
        pool = exact if exact else candidates
        selected = random.choice(pool)
        selected_path = base_dir / selected
        if not selected_path.exists():
            return ""
        try:
            raw = selected_path.read_text(encoding="utf-8")
            return _strip_yaml_front_matter(raw).strip()
        except Exception:
            return ""

    # Primary: global style library (when linked_author exists).
    if linked_author:
        library_root = global_root / linked_author
        manifest_path = library_root / "manifest.yaml"
        if not library_root.exists():
            print(
                f"[WARNING] linked_author is set ({linked_author}) but style library directory does not exist: {library_root}",
                file=sys.stderr,
            )
        scene_files: list[str] = []
        if manifest_path.exists():
            try:
                with manifest_path.open("r", encoding="utf-8") as f:
                    manifest = yaml.safe_load(f)
            except Exception:
                manifest = None

            if isinstance(manifest, dict):
                snippets_map: dict[str, Any] = manifest.get("snippets", {})
                if isinstance(snippets_map, dict):
                    scene_payload = snippets_map.get(scene_type, {})
                    if not scene_payload and "daily" in snippets_map:
                        scene_payload = snippets_map.get("daily", {})
                    if isinstance(scene_payload, dict):
                        files = scene_payload.get("files", [])
                        if isinstance(files, list):
                            scene_files = [str(item) for item in files if isinstance(item, str)]

        text = _pick_and_read(library_root, scene_files)
        if text:
            return text

    # Fallback to local project snippets when global style library is missing/incomplete.
    if xushikj_dir is not None:
        local_snippet_dir = xushikj_dir / "benchmark" / "style_snippets"
        local_files = sorted(local_snippet_dir.glob(f"{scene_type}_*.md"))
        if not local_files and scene_type != "daily":
            local_files = sorted(local_snippet_dir.glob("daily_*.md"))
        if local_files:
            exact = [p for p in local_files if f"_{scene_intensity}" in p.name]
            pool = exact if exact else local_files
            chosen_path = random.choice(pool)
            try:
                raw = chosen_path.read_text(encoding="utf-8")
                return _strip_yaml_front_matter(raw).strip()
            except Exception:
                return not_available

    if scene_type == "unknown":
        print(
            "[WARNING] scene_type is unknown; style snippet matching is likely to fail. "
            "Check scene plan path and cycle_id consistency.",
            file=sys.stderr,
        )
    return not_available


def _discover_cycle_id(xushikj_dir: Path, requested_cycle_id: str) -> tuple[str, Path | None]:
    """Return a usable cycle_id and optional cycle path, with compatibility fallback."""
    scenes_root = xushikj_dir / "scenes"
    preferred = scenes_root / requested_cycle_id
    if preferred.exists():
        return requested_cycle_id, preferred

    # Handle legacy zero-padded naming mismatch.
    if requested_cycle_id == "cycle_001" and (scenes_root / "cycle_1").exists():
        return "cycle_1", scenes_root / "cycle_1"
    if requested_cycle_id == "cycle_1" and (scenes_root / "cycle_001").exists():
        return "cycle_001", scenes_root / "cycle_001"

    candidates = sorted([p for p in scenes_root.glob("cycle_*") if p.is_dir()])
    if candidates:
        fallback = candidates[-1]
        return fallback.name, fallback
    return requested_cycle_id, None


def _extract_scene_type(scene_text: str) -> str:
    m = re.search(r"scene_type\s*[:：]\s*([a-zA-Z_]+)", scene_text)
    return m.group(1).lower().strip() if m else "unknown"


def _extract_scene_intensity(scene_text: str) -> str:
    m = re.search(r"scene_intensity\s*[:：]\s*(high|medium|low)", scene_text, flags=re.IGNORECASE)
    return m.group(1).lower().strip() if m else "medium"


def _extract_ids(scene_text: str, prefix: str) -> list[str]:
    pattern = rf"\b{prefix}_[0-9]{{3,}}\b"
    return sorted(set(re.findall(pattern, scene_text)))


def _extract_char_names_from_scene(scene_text: str, kb_data: dict[str, Any]) -> list[str]:
    m = re.search(r"viewpoint_character\s*[:：]\s*([^\n\r]+)", scene_text, flags=re.IGNORECASE)
    if not m:
        return []

    raw = m.group(1).strip()
    if not raw:
        return []

    candidates = [part.strip(" \t\"'[]（）()") for part in re.split(r"[，,、/]", raw)]
    candidates = [name for name in candidates if name]
    if not candidates:
        return []

    kb_chars = kb_data.get("characters", {})
    if not isinstance(kb_chars, dict):
        entities = kb_data.get("entities", {})
        kb_chars = entities.get("characters", {}) if isinstance(entities, dict) else {}
    if not isinstance(kb_chars, dict):
        return []

    kb_char_names = set(kb_chars.keys())
    return [name for name in candidates if name in kb_char_names]


def _load_scene_context(xushikj_dir: Path, state: dict[str, Any], chapter: int | None) -> tuple[str, list[str], list[str]]:
    if chapter is None:
        return "(no scene card loaded)", [], []

    cycle_id = state.get("rolling_context", {}).get("cycle_id", "cycle_1")
    effective_cycle_id, cycle_path = _discover_cycle_id(xushikj_dir, str(cycle_id))
    scene_plan = xushikj_dir / "scenes" / effective_cycle_id / "scene_plans" / f"chapter_{chapter}.md"
    if not scene_plan.exists():
        if cycle_path is None:
            return (
                f"(scene plan not found: {scene_plan}; no cycle_* directory exists under {xushikj_dir / 'scenes'})",
                [],
                [],
            )
        return f"(scene plan not found: {scene_plan})", [], []

    scene_text = scene_plan.read_text(encoding="utf-8")
    char_ids = _extract_ids(scene_text, "char")
    loc_ids = _extract_ids(scene_text, "loc")
    return scene_text, char_ids, loc_ids


def _load_template(step_key: str) -> str:
    templates_dir = SKILL_ROOT / "templates" / "prompts"
    if not templates_dir.exists():
        # Phase-1 fallback template when Phase-2 templates are not created yet.
        return (
            "# Step Prompt\n\n"
            "## Step\n{{step}}\n\n"
            "## Project\n{{project_name}}\n\n"
            "## Scene Card\n{{scene_card}}\n\n"
            "## Recent Summaries\n{{recent_summaries}}\n\n"
            "## KB Slice\n{{kb_slice}}\n\n"
            "## Style Snippet\n{{style_snippet}}\n\n"
            "## DNA Constraints\n{{dna_constraints}}\n\n"
            "## Rules\n{{rules}}\n\n"
            "## Forbidden Words\n{{forbidden_words}}\n\n"
            "## Output Constraints\n{{output_constraints}}\n"
        )

    preferred_names = {
        "0": "step_0_benchmark.md",
        "4": "step_4_one_page.md",
        "7": "step_7.md",
        "8": "step_8.md",
        "9": "step_9.md",
        "11": "step_11.md",
        "10_pipeline": "step_10_pipeline.md",
        "10_interactive": "step_10_interactive.md",
    }
    preferred = preferred_names.get(step_key)
    if preferred:
        preferred_path = templates_dir / preferred
        if preferred_path.exists():
            return preferred_path.read_text(encoding="utf-8")
        print(
            f"[WARNING] _load_template: preferred template not found for step '{step_key}': {preferred_path}",
            file=sys.stderr,
        )

    candidate = templates_dir / f"step_{step_key}.md"
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")

    wildcard_matches = sorted(templates_dir.glob(f"step_{step_key}_*.md"))
    if wildcard_matches:
        return wildcard_matches[0].read_text(encoding="utf-8")

    # Writing mode compatibility: step_10_pipeline / step_10_interactive -> step_10_*.md
    if step_key.startswith("10"):
        writing_matches = sorted(templates_dir.glob("step_10_*.md"))
        if writing_matches:
            return writing_matches[0].read_text(encoding="utf-8")

    fallback = templates_dir / "step_default.md"
    if fallback.exists():
        return fallback.read_text(encoding="utf-8")

    print(
        f"[WARNING] _load_template: no template found for step '{step_key}', using minimal fallback skeleton.",
        file=sys.stderr,
    )
    return (
        "# Step Prompt\n\n"
        "Step: {{step}}\n"
        "Project: {{project_name}}\n"
        "Scene Card: {{scene_card}}\n"
        "Recent Summaries: {{recent_summaries}}\n"
        "KB Slice: {{kb_slice}}\n"
        "Style Snippet: {{style_snippet}}\n"
        "DNA Constraints: {{dna_constraints}}\n"
        "Rules:\n{{rules}}\n"
    )


def _render(template: str, values: dict[str, str]) -> str:
    text = template
    for key, value in values.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def _approx_tokens(text: str) -> int:
    # Rough multilingual estimate.
    return max(1, len(text) // 2)


def _warn_step10_prerequisites(
    xushikj_dir: Path,
    step_key: str,
    chapter: int | None,
    scene_card: str,
    style_snippet: str,
    dna_lines: list[str],
) -> None:
    if not step_key.startswith("10"):
        return

    if chapter is not None and scene_card.startswith("(scene plan not found"):
        print(
            f"[WARNING] Step10 chapter={chapter} 未找到 scene plan，scene_type 将退化为 unknown。",
            file=sys.stderr,
        )

    snippet_dir = xushikj_dir / "benchmark" / "style_snippets"
    if style_snippet == "(style snippet not available)":
        if not snippet_dir.exists() or not list(snippet_dir.glob("*.md")):
            print(
                "[WARNING] 本地未检测到 style_snippets。请先执行 write-snippet 子命令落盘切片。",
                file=sys.stderr,
            )
        else:
            print(
                "[WARNING] style_snippets 已存在，但本次未匹配到对应 scene_type/intensity。",
                file=sys.stderr,
            )

    if not dna_lines:
        print(
            "[WARNING] 未加载到 DNA 约束。请确认 .xushikj/config/style_modules 下存在 dna_human_*.yaml 或 clone_*.yaml。",
            file=sys.stderr,
        )


def _step10_hard_stop_issues(
    step_key: str,
    chapter: int | None,
    scene_card: str,
    scene_type: str,
    style_snippet: str,
    dna_lines: list[str],
) -> list[str]:
    if not step_key.startswith("10"):
        return []

    issues: list[str] = []
    if chapter is None:
        issues.append("Step10 必须提供 --chapter。")
    if scene_card.startswith("(scene plan not found"):
        issues.append("缺少 scene_plan，无法执行 Step10。")
    if scene_type == "unknown":
        issues.append("scene_type=unknown，说明场景卡缺失 scene_type 字段或读取失败。")
    if style_snippet == "(style snippet not available)":
        issues.append("未匹配到 style_snippet，请先完成 benchmark 切片落盘。")
    if not dna_lines:
        issues.append("未加载到 DNA 约束（dna_human_*.yaml/clone_*.yaml）。")
    return issues


def _step10_remediation_hints(
    xushikj_dir: Path,
    chapter: int | None,
    scene_card: str,
    scene_type: str,
    style_snippet: str,
    dna_lines: list[str],
) -> list[str]:
    hints: list[str] = []

    if chapter is None:
        hints.append("补充参数：--chapter <N>")

    if scene_card.startswith("(scene plan not found"):
        if chapter is None:
            hints.append("先确定章节号，再创建 scene_plan。")
        else:
            hints.append(
                f"创建场景卡：{xushikj_dir / 'scenes' / 'cycle_1' / 'scene_plans' / f'chapter_{chapter}.md'}"
            )

    if scene_type == "unknown":
        hints.append("在 scene_plan 中补齐字段：scene_type: <daily/combat/...>")

    if style_snippet == "(style snippet not available)":
        hints.append(
            "先执行切片落盘：python narrativespace/scripts/slice_library.py write-snippet --project-dir . --scene-type daily --content-file snippet_daily.md"
        )

    if not dna_lines:
        hints.append(
            "先写入 DNA：python narrativespace/scripts/slice_library.py write-dna --project-dir . --project-name my_project --dna-json dna_profile.json"
        )

    hints.append(
        "修复后重新组装：python narrativespace/scripts/assemble_prompt.py --project-dir .xushikj --step 10 --chapter <N> --writing-mode pipeline --output file"
    )
    return hints


def build_prompt(
    project_root: Path,
    xushikj_dir: Path,
    step: str,
    chapter: int | None,
    writing_mode_override: str | None = None,
    allow_step10_degraded: bool = False,
) -> str:
    state_path = xushikj_dir / "state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"Missing state.json: {state_path}")

    state = _read_json(state_path)
    writing_mode = _resolve_writing_mode(state, writing_mode_override)
    step_key = _pick_step_key(step, writing_mode)

    scripts_dir = SKILL_ROOT / "scripts"
    mapping = _load_step_rule_map(scripts_dir)
    step_config = mapping.get("steps", {}).get(step_key)
    if not step_config:
        raise ValueError(f"No rule mapping for step key: {step_key}")

    config_dir = xushikj_dir / "config"
    fallback_config_dir = SKILL_ROOT / "config"
    if not config_dir.exists():
        config_dir = fallback_config_dir

    max_rules = mapping.get("meta", {}).get("max_rules_per_step", 10)
    rules = extract_rules(config_dir, step_config.get("rule_sources", []), max_rules=max_rules)

    core_rules_path = config_dir / "core_15_rules.yaml"
    core_rules = extract_core_rules(core_rules_path, limit=10)

    style_rules_path = config_dir / "style_rules.yaml"
    forbidden_words = extract_forbidden_words(style_rules_path, limit=20)

    scene_card, char_ids, loc_ids = _load_scene_context(xushikj_dir, state, chapter)
    scene_type = _extract_scene_type(scene_card)
    scene_intensity = _extract_scene_intensity(scene_card)

    kb_path = xushikj_dir / "knowledge_base.json"
    kb_slice = "(kb slice not available)"
    if kb_path.exists():
        query_char_ids = list(char_ids)
        if not query_char_ids:
            kb_data = _read_json(kb_path)
            query_char_ids = _extract_char_names_from_scene(scene_card, kb_data)
        if query_char_ids or loc_ids:
            kb_slice_obj = slice_kb(kb_path, character_ids=query_char_ids, location_ids=loc_ids)
            kb_slice = format_kb_slice(kb_slice_obj)

    recent_summaries = _read_recent_summaries(xushikj_dir, last_n=2)

    dna_lines: list[str] = []
    style_snippet = ""
    if step_key.startswith("10"):
        style_modules_dir = config_dir / "style_modules"
        dna_lines = load_dna_constraints(style_modules_dir, max_do=5, max_dont=5)
        style_snippet = _load_style_snippet(state, scene_type, scene_intensity, xushikj_dir)

    _warn_step10_prerequisites(
        xushikj_dir=xushikj_dir,
        step_key=step_key,
        chapter=chapter,
        scene_card=scene_card,
        style_snippet=style_snippet,
        dna_lines=dna_lines,
    )

    if not allow_step10_degraded:
        issues = _step10_hard_stop_issues(
            step_key=step_key,
            chapter=chapter,
            scene_card=scene_card,
            scene_type=scene_type,
            style_snippet=style_snippet,
            dna_lines=dna_lines,
        )
        if issues:
            hints = _step10_remediation_hints(
                xushikj_dir=xushikj_dir,
                chapter=chapter,
                scene_card=scene_card,
                scene_type=scene_type,
                style_snippet=style_snippet,
                dna_lines=dna_lines,
            )
            raise ValueError(
                "Step10 HARD STOP: "
                + " | ".join(issues)
                + "\nFix:\n- "
                + "\n- ".join(hints)
            )

    all_rules = core_rules + rules + dna_lines
    if not all_rules:
        all_rules = ["(no rules)"]

    template = _load_template(step_key)
    prompt = _render(
        template,
        {
            "step": step,
            "step_key": step_key,
            "project_name": str(state.get("project_name", "")),
            "benchmark_works": "、".join(state.get("config", {}).get("benchmark_works", [])) or "(none)",
            "sample_scope": str(state.get("benchmark_state", {}).get("sample_scope", "quick")),
            "scene_type": scene_type,
            "scene_card": scene_card,
            "recent_summaries": recent_summaries,
            "kb_slice": kb_slice,
            "style_snippet": style_snippet,
            "dna_constraints": "\n".join(dna_lines) if dna_lines else "(no dna constraints)",
            "rules": "\n".join(all_rules),
            "forbidden_words": "、".join(forbidden_words) if forbidden_words else "(none)",
            "output_constraints": "Follow step contract strictly. Do not auto-advance to next step.",
            "chapter": str(chapter) if chapter is not None else "",
        },
    )
    return prompt


def cmd_status(project_root: Path, xushikj_dir: Path) -> int:
    state_path = xushikj_dir / "state.json"
    if not state_path.exists():
        print(f"state.json not found: {state_path}")
        return 1

    state = _read_json(state_path)
    print("Project:", state.get("project_name", ""))
    print("Current step:", state.get("current_step"))
    print("Planning current step:", state.get("planning_state", {}).get("current_step"))
    print("Current chapter:", state.get("chapter_state", {}).get("current_chapter"))
    print("Writing mode:", state.get("config", {}).get("writing_mode", "pipeline"))
    print("Cycle:", state.get("rolling_context", {}).get("cycle_id", "cycle_1"))
    return 0


def cmd_advance(project_root: Path, xushikj_dir: Path) -> int:
    state_path = xushikj_dir / "state.json"
    if not state_path.exists():
        print(f"state.json not found: {state_path}")
        return 1

    state = _read_json(state_path)
    current = state.get("current_step", "project_card")

    # v10.0 sequence
    V10_SEQUENCE = ["project_card", 4, 7, 8, 9, 10, 11]
    try:
        idx = V10_SEQUENCE.index(current)
        nxt = V10_SEQUENCE[idx + 1] if idx + 1 < len(V10_SEQUENCE) else current
    except (ValueError, IndexError):
        # current step not in v10.0 sequence; try numeric advance as fallback
        try:
            nxt = int(float(str(current))) + 1
        except Exception:
            nxt = 4

    completed = state.get("completed_steps", [])
    if current not in completed:
        completed.append(current)
    state["completed_steps"] = completed
    state["current_step"] = nxt
    state["updated_at"] = ""
    _write_json(state_path, state)

    print(f"Advanced step: {current} -> {nxt}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Assemble step-level prompt package")
    p.add_argument("--project-dir", required=True, type=Path, help="Project root or .xushikj path")
    p.add_argument("--step", type=str, help="Workflow step, e.g. 1, 2.5, 10")
    p.add_argument("--chapter", type=int, help="Chapter number for writing steps")
    p.add_argument(
        "--output",
        choices=["stdout", "file"],
        default="stdout",
        help="Output prompt to stdout or file",
    )
    p.add_argument("--output-file", type=Path, help="Output file path when --output file")
    p.add_argument(
        "--writing-mode",
        choices=["pipeline", "interactive"],
        help="Override writing mode for this run (does not mutate state.json)",
    )
    p.add_argument(
        "--allow-step10-degraded",
        action="store_true",
        help="Allow Step10 assembly with missing prerequisites (not recommended)",
    )
    p.add_argument("--status", action="store_true", help="Print current project status")
    p.add_argument("--advance", action="store_true", help="Advance current step in state.json")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    project_root, xushikj_dir = _resolve_paths(args.project_dir)

    if args.status:
        return cmd_status(project_root, xushikj_dir)
    if args.advance:
        return cmd_advance(project_root, xushikj_dir)

    if not args.step:
        print("--step is required unless using --status or --advance")
        return 2

    try:
        prompt = build_prompt(
            project_root,
            xushikj_dir,
            args.step,
            args.chapter,
            writing_mode_override=args.writing_mode,
            allow_step10_degraded=args.allow_step10_degraded,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    token_est = _approx_tokens(prompt)

    if args.output == "stdout":
        print(prompt)
        print(f"\n\n[meta] approx_tokens={token_est}")
        return 0

    out = args.output_file or (xushikj_dir / "drafts" / f"assembled_step_{args.step}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(prompt, encoding="utf-8")
    print(f"Prompt written to: {out}")
    print(f"[meta] approx_tokens={token_est}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
