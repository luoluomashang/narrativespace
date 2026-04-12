#!/usr/bin/env python3
"""
Land Lite writing and humanizer model outputs into project files.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from chinese_char_count import FANQIE_MAX_CHARS, validate_chinese_char_count
from encoding_utils import read_json_utf8, read_text_utf8, reconfigure_stdio_utf8, write_text_utf8
from workflow_state import mark_step_complete, resolve_paths

SKILL_ROOT = Path(__file__).resolve().parent.parent
WRITING_SECTION_ORDER = ["本章摘要", "状态变化", "新增设定", "未兑现钩子"]
HUMANIZER_SECTION = "修改说明"
HUMANIZER_OPTIONAL_SECTIONS = ["豁免记录", "R-DNA校验"]


def _split_markdown_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE))
    if not matches:
        return text.strip(), []
    intro = text[: matches[0].start()].strip()
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[start:end].strip()))
    return intro, sections


def _render_markdown_sections(intro: str, sections: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    if intro.strip():
        parts.append(intro.strip())
    for heading, body in sections:
        parts.append(f"## {heading}\n{body.strip()}")
    return "\n\n".join(part for part in parts if part.strip()).strip() + "\n"


def _parse_list_section(text: str) -> list[str]:
    items: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line == "（暂无）":
            continue
        if line.startswith("-"):
            cleaned = line[1:].strip()
        else:
            cleaned = line
        if cleaned:
            items.append(cleaned)
    return items


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _upsert_markdown_section(
    sections: list[tuple[str, str]],
    heading: str,
    body: str,
) -> list[tuple[str, str]]:
    updated = False
    output: list[tuple[str, str]] = []
    for name, existing in sections:
        if name == heading:
            output.append((heading, body))
            updated = True
        else:
            output.append((name, existing))
    if not updated:
        output.append((heading, body))
    return output


def _parse_writing_output(raw_text: str) -> tuple[str, dict[str, str]]:
    body, sections = _split_markdown_sections(raw_text)
    section_map = {heading: content for heading, content in sections}
    missing = [heading for heading in WRITING_SECTION_ORDER if heading not in section_map]
    extra = [heading for heading, _ in sections if heading not in WRITING_SECTION_ORDER]
    if not body:
        raise ValueError("正文为空，拒绝落盘。")
    if missing:
        raise ValueError(f"写作输出缺少结构化区块：{', '.join(missing)}")
    if extra:
        raise ValueError(f"写作输出存在未约定区块：{', '.join(extra)}")
    ordered = {heading: section_map[heading].strip() or "（暂无）" for heading in WRITING_SECTION_ORDER}
    return body.strip(), ordered


def _parse_humanizer_output(raw_text: str) -> tuple[str, dict[str, str]]:
    body, sections = _split_markdown_sections(raw_text)
    section_map = {heading: content for heading, content in sections}
    if not body:
        raise ValueError("润色正文为空，拒绝落盘。")
    if HUMANIZER_SECTION not in section_map:
        raise ValueError("润色输出缺少 `## 修改说明` 区块。")
    missing = [heading for heading in HUMANIZER_OPTIONAL_SECTIONS if heading not in section_map]
    if missing:
        raise ValueError(f"润色输出缺少结构化区块：{', '.join(missing)}")
    parsed = {
        HUMANIZER_SECTION: section_map[HUMANIZER_SECTION].strip() or "（暂无）",
        "豁免记录": section_map["豁免记录"].strip() or "- 无",
        "R-DNA校验": section_map["R-DNA校验"].strip() or "- 未启用 DNA 保护",
    }
    return body.strip(), parsed


def _load_summary_template() -> str:
    return read_text_utf8(SKILL_ROOT / "templates" / "summary_index_template.md", "")


def _load_memory_template() -> str:
    return read_text_utf8(SKILL_ROOT / "templates" / "memory_template.md", "")


def _update_summary_index(summary_path: Path, chapter_no: int, summary_text: str, hooks: list[str]) -> None:
    intro, sections = _split_markdown_sections(read_text_utf8(summary_path, _load_summary_template()))
    recent_lines = _parse_list_section(dict(sections).get("最近章节摘要", ""))
    recent_entry = f"[第{chapter_no}章] {_one_line(summary_text)}"
    recent_lines = [line for line in recent_lines if not line.startswith(f"[第{chapter_no}章]")]
    recent_lines.append(recent_entry)

    hook_lines = _parse_list_section(dict(sections).get("未解决悬念", ""))
    hook_lines = [line for line in hook_lines if not line.startswith(f"[第{chapter_no}章]")]
    hook_lines.extend(f"[第{chapter_no}章] {item}" for item in hooks)

    sections = _upsert_markdown_section(sections, "最近章节摘要", "\n".join(f"- {line}" for line in recent_lines) or "- （暂无）")
    sections = _upsert_markdown_section(sections, "未解决悬念", "\n".join(f"- {line}" for line in hook_lines) or "- （暂无）")
    write_text_utf8(summary_path, _render_markdown_sections(intro, sections))


def _update_memory(memory_path: Path, chapter_no: int, summary_text: str, settings: list[str], hooks: list[str], current_volume_goal: str) -> None:
    intro, sections = _split_markdown_sections(read_text_utf8(memory_path, _load_memory_template()))
    sections = _upsert_markdown_section(
        sections,
        "当前任务",
        "\n".join(
            [
                "- 当前步骤：10（已落盘，待用户确认）",
                f"- 当前章：第 {chapter_no} 章",
                f"- 当前卷目标：{current_volume_goal or '（暂无）'}",
            ]
        ),
    )
    sections = _upsert_markdown_section(
        sections,
        "下次续写前要记得",
        "\n".join(
            [
                f"- 下一章必须兑现：{hooks[0] if hooks else '（暂无）'}",
                "- 下一章必须避免：未经用户确认直接推进流程",
                f"- 待补录到 KB / summary_index 的信息：{'; '.join(settings) if settings else _one_line(summary_text)}",
            ]
        ),
    )
    write_text_utf8(memory_path, _render_markdown_sections(intro, sections))


def _ensure_kb_defaults(kb: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(kb.get("open_loops"), list):
        kb["open_loops"] = []
    if not isinstance(kb.get("chapter_notes"), list):
        kb["chapter_notes"] = []
    return kb


def _update_kb(
    kb_path: Path,
    *,
    chapter_no: int,
    summary_text: str,
    state_changes: list[str],
    settings: list[str],
    hooks: list[str],
) -> None:
    kb = _ensure_kb_defaults(read_json_utf8(kb_path))
    if isinstance(kb.get("project"), dict) and not str(kb["project"].get("title", "")).strip():
        kb["project"]["title"] = ""
    kb["chapter_notes"] = [
        item
        for item in kb["chapter_notes"]
        if not isinstance(item, dict) or str(item.get("chapter", "")).strip() != str(chapter_no)
    ]
    kb["chapter_notes"].append(
        {
            "chapter": chapter_no,
            "summary": summary_text,
            "state_changes": state_changes,
            "new_settings": settings,
            "unresolved_hooks": hooks,
        }
    )

    existing_questions = {
        str(item.get("question", "")).strip(): item
        for item in kb["open_loops"]
        if isinstance(item, dict)
    }
    for index, hook in enumerate(hooks, start=1):
        existing = existing_questions.get(hook)
        if existing is not None:
            existing["status"] = "open"
            continue
        kb["open_loops"].append(
            {
                "id": f"loop_auto_ch{chapter_no}_{index}",
                "question": hook,
                "introduced_in": f"chapter_{chapter_no}",
                "planned_payoff": "",
                "status": "open",
            }
        )
    write_text_utf8(kb_path, json.dumps(kb, ensure_ascii=False, indent=2) + "\n")


def _fanqie_max(target_platform: str) -> int | None:
    return FANQIE_MAX_CHARS if target_platform.strip().lower() == "fanqie" else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text_utf8(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def land_writing(project_dir: Path, input_file: Path, chapter: int | None) -> int:
    project_root, xushikj_dir = resolve_paths(project_dir)
    state_path = xushikj_dir / "state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"Missing state.json: {state_path}")
    state = read_json_utf8(state_path)
    chapter_no = chapter or int(state.get("current_chapter", 1))
    raw_text = read_text_utf8(input_file.resolve(), "")
    body, sections = _parse_writing_output(raw_text)

    reply_length = int(state.get("reply_length") or 0)
    target_platform = str(state.get("target_platform") or "")
    count, count_errors = validate_chinese_char_count(
        body,
        minimum=reply_length if reply_length > 0 else None,
        maximum=_fanqie_max(target_platform),
        label=f"chapter_{chapter_no}",
    )
    if count_errors:
        raise ValueError("; ".join(count_errors))

    drafts_dir = xushikj_dir / "drafts"
    chapters_dir = xushikj_dir / "chapters"
    summaries_dir = xushikj_dir / "summaries"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)

    raw_output_path = drafts_dir / f"chapter_{chapter_no}_raw_output.md"
    structured_path = drafts_dir / f"chapter_{chapter_no}_landing.json"
    chapter_path = chapters_dir / f"chapter_{chapter_no}.md"
    summary_path = summaries_dir / "summary_index.md"
    memory_path = xushikj_dir / "memory.md"
    kb_path = xushikj_dir / "knowledge_base.json"

    write_text_utf8(raw_output_path, raw_text if raw_text.endswith("\n") else raw_text + "\n")
    write_text_utf8(chapter_path, body + "\n")
    _write_json(
        structured_path,
        {
            "chapter": chapter_no,
            "chapter_path": str(chapter_path),
            "raw_output_path": str(raw_output_path),
            "chinese_chars": count,
            "sections": sections,
        },
    )

    hook_items = _parse_list_section(sections["未兑现钩子"])
    setting_items = _parse_list_section(sections["新增设定"])
    state_change_items = _parse_list_section(sections["状态变化"])
    summary_items = _parse_list_section(sections["本章摘要"])
    summary_text = summary_items[0] if summary_items else _one_line(sections["本章摘要"])
    kb_snapshot = read_json_utf8(kb_path) if kb_path.exists() else {}
    current_volume_goal = ""
    if isinstance(kb_snapshot.get("current_volume"), dict):
        current_volume_goal = str(kb_snapshot["current_volume"].get("goal", "")).strip()
    _update_summary_index(summary_path, chapter_no, summary_text, hook_items)
    _update_memory(
        memory_path,
        chapter_no,
        summary_text,
        setting_items,
        hook_items,
        current_volume_goal,
    )
    _update_kb(
        kb_path,
        chapter_no=chapter_no,
        summary_text=summary_text,
        state_changes=state_change_items,
        settings=setting_items,
        hooks=hook_items,
    )

    state["current_chapter"] = chapter_no
    recent_outputs = state.get("recent_outputs", {})
    if not isinstance(recent_outputs, dict):
        recent_outputs = {}
        state["recent_outputs"] = recent_outputs
    recent_outputs["latest_chapter"] = str(chapter_path.relative_to(xushikj_dir))
    recent_outputs["summary_index"] = str(summary_path.relative_to(xushikj_dir))
    recent_outputs["memory"] = str(memory_path.relative_to(xushikj_dir))
    recent_outputs["knowledge_base"] = str(kb_path.relative_to(xushikj_dir))
    write_text_utf8(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")

    mark_step_complete(
        project_root,
        step="10",
        output_paths=[chapter_path, summary_path, memory_path, kb_path, structured_path],
        validation_passed=True,
        validation_summary=f"chapter_{chapter_no} 中文字数={count}",
        next_step_suggestion="8",
    )
    print(f"[landing] 已写入正文：{chapter_path}")
    print(f"[landing] 已回写摘要：{summary_path}")
    print(f"[landing] 已回写 Memory：{memory_path}")
    print(f"[landing] 已回写知识库：{kb_path}")
    print(f"[landing] chapter_{chapter_no}_zh_chars={count}")
    return 0


def land_humanizer(project_dir: Path, input_file: Path, chapter: int | None, chapter_file: Path | None) -> int:
    project_root, xushikj_dir = resolve_paths(project_dir)
    raw_text = read_text_utf8(input_file.resolve(), "")
    body, sections = _parse_humanizer_output(raw_text)
    humanized_dir = xushikj_dir / "humanized"
    drafts_dir = xushikj_dir / "drafts"
    humanized_dir.mkdir(parents=True, exist_ok=True)
    drafts_dir.mkdir(parents=True, exist_ok=True)

    if chapter is not None:
        output_name = f"chapter_{chapter}.md"
    elif chapter_file is not None:
        output_name = f"{chapter_file.resolve().stem}.md"
    else:
        state_path = xushikj_dir / "state.json"
        if state_path.exists():
            state = read_json_utf8(state_path)
            output_name = f"chapter_{int(state.get('current_chapter', 1))}.md"
        else:
            output_name = "chapter_humanized.md"

    output_path = humanized_dir / output_name
    notes_path = drafts_dir / f"{Path(output_name).stem}_humanizer_notes.md"
    write_text_utf8(output_path, body + "\n")
    write_text_utf8(
        notes_path,
        "\n\n".join(
            [
                f"## {HUMANIZER_SECTION}\n{sections[HUMANIZER_SECTION]}",
                f"## 豁免记录\n{sections['豁免记录']}",
                f"## R-DNA校验\n{sections['R-DNA校验']}",
            ]
        )
        + "\n",
    )

    state_path = xushikj_dir / "state.json"
    if state_path.exists():
        state = read_json_utf8(state_path)
        recent_outputs = state.get("recent_outputs", {})
        if not isinstance(recent_outputs, dict):
            recent_outputs = {}
            state["recent_outputs"] = recent_outputs
        recent_outputs["latest_humanized"] = str(output_path.relative_to(xushikj_dir))
        write_text_utf8(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        mark_step_complete(
            project_root,
            step="humanizer",
            output_paths=[output_path, notes_path],
            validation_passed=True,
            validation_summary=f"humanized_output={output_name}",
            next_step_suggestion="",
        )

    print(f"[landing] 已写入润色稿：{output_path}")
    print(f"[landing] 已写入修改说明：{notes_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Land Lite model outputs into project files")
    subparsers = parser.add_subparsers(dest="command", required=True)

    writing = subparsers.add_parser("writing", help="Land step 10 writing output")
    writing.add_argument("--project-dir", required=True, type=Path)
    writing.add_argument("--input-file", required=True, type=Path)
    writing.add_argument("--chapter", type=int)

    humanizer = subparsers.add_parser("humanizer", help="Land humanizer output")
    humanizer.add_argument("--project-dir", required=True, type=Path)
    humanizer.add_argument("--input-file", required=True, type=Path)
    humanizer.add_argument("--chapter", type=int)
    humanizer.add_argument("--chapter-file", type=Path)
    return parser


def main() -> int:
    reconfigure_stdio_utf8()
    args = build_parser().parse_args()
    if args.command == "writing":
        return land_writing(args.project_dir, args.input_file, args.chapter)
    if args.command == "humanizer":
        return land_humanizer(args.project_dir, args.input_file, args.chapter, args.chapter_file)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
