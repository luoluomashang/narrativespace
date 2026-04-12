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

from chinese_char_count import validate_chinese_char_count
from encoding_utils import read_json_utf8, reconfigure_stdio_utf8, subprocess_utf8_kwargs
from workflow_state import ensure_workflow_state

PLACEHOLDER = '（待填写）'
STEP_DEPENDENCIES = {
    'worldbuilding': ['benchmark'],
    'characters': ['benchmark', 'worldview'],
    'chapter-outline': ['benchmark', 'worldview', 'characters'],
    '10': ['benchmark', 'worldview', 'characters', 'chapter_outline', 'reply_length'],
    'humanizer': ['chapter_file'],
}


def _resolve_xushikj_dir(project_dir: Path) -> Path:
    return project_dir if project_dir.name == '.xushikj' else project_dir / '.xushikj'


def _load_json(path: Path) -> dict[str, Any]:
    return read_json_utf8(path)


def _resolve_humanizer_chapter_path(project_dir: Path, chapter: int | None, chapter_file: Path | None) -> Path:
    if chapter_file is not None:
        return chapter_file.resolve()

    xushikj_dir = _resolve_xushikj_dir(project_dir.resolve())
    if chapter is not None:
        candidates = [
            xushikj_dir / 'chapters' / f'chapter_{chapter}.md',
            project_dir.resolve() / 'chapters' / f'chapter_{chapter}.md',
            project_dir.resolve() / f'chapter_{chapter}.md',
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    state_path = xushikj_dir / 'state.json'
    if state_path.exists():
        state = _load_json(state_path)
        current_chapter = int(state.get('current_chapter', 1))
        return xushikj_dir / 'chapters' / f'chapter_{current_chapter}.md'

    raise FileNotFoundError('Humanizer requires --chapter-file or --chapter when state.json is unavailable')


def _count_chinese_chars_with_script(chapter_path: Path) -> int:
    script_path = Path(__file__).resolve().parent / 'chinese_char_count.py'
    proc = subprocess.run(
        [sys.executable, str(script_path), '--input', str(chapter_path), '--json'],
        capture_output=True,
        **subprocess_utf8_kwargs(),
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or 'chinese_char_count failed')
    payload = json.loads(proc.stdout)
    return int(payload.get('chinese_chars', 0))


def _ready_text_file(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8-sig', errors='replace').strip()
    return bool(text) and PLACEHOLDER not in text


def _ready_character_cards(path: Path) -> bool:
    if not path.exists():
        return False
    for card_path in sorted(path.glob('*.md')):
        text = card_path.read_text(encoding='utf-8-sig', errors='replace').strip()
        if text and PLACEHOLDER not in text:
            return True
    return False


def validate(
    project_dir: Path,
    chapter: int | None,
    strict: bool,
    for_step: str | None,
    min_chapter_chars: int | None,
    chapter_file: Path | None,
) -> int:
    xushikj_dir = _resolve_xushikj_dir(project_dir.resolve())
    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    step = (for_step or '').strip()
    if step == 'writing':
        step = '10'

    if step == 'humanizer' and (chapter_file is not None or not xushikj_dir.exists()):
        try:
            humanizer_chapter_path = _resolve_humanizer_chapter_path(project_dir, chapter, chapter_file)
        except FileNotFoundError as exc:
            print(f'[ERROR] {exc}')
            return 2
        print(f'[validate_state] project={project_dir}')
        print(f'[INFO] humanizer_chapter={humanizer_chapter_path}')
        if not humanizer_chapter_path.exists():
            print(f'[ERROR] Humanizer 缺少目标章节: {humanizer_chapter_path}')
            return 1
        return 0

    if not xushikj_dir.exists():
        print(f'[ERROR] 缺少 .xushikj 目录: {xushikj_dir}')
        return 2

    state_path = xushikj_dir / 'state.json'
    if not state_path.exists():
        print(f'[ERROR] 缺少 state.json: {state_path}')
        return 2

    state = _load_json(state_path)
    state = ensure_workflow_state(state)
    workflow = state.get('workflow', {})
    infos.append(f"current_step={state.get('current_step', '')}")
    infos.append(f"current_chapter={state.get('current_chapter', 1)}")
    infos.append(f"pending_user_confirmation={str(bool(workflow.get('pending_user_confirmation'))).lower()}")

    summary_path = xushikj_dir / 'summaries' / 'summary_index.md'
    memory_path = xushikj_dir / 'memory.md'
    if not summary_path.exists():
        warnings.append(f'缺少摘要索引: {summary_path}')
    if not memory_path.exists():
        warnings.append(f'缺少 Memory: {memory_path}')

    effective_chapter = chapter or int(state.get('current_chapter', 1))
    outline_path = xushikj_dir / 'chapter_outlines' / f'chapter_{effective_chapter}.md'
    chapter_path = _resolve_humanizer_chapter_path(project_dir, effective_chapter, chapter_file) if step == 'humanizer' else xushikj_dir / 'chapters' / f'chapter_{effective_chapter}.md'
    benchmark_path = xushikj_dir / 'benchmark' / 'style_notes.md'
    worldview_path = xushikj_dir / 'worldbuilding' / 'worldview.md'
    characters_dir = xushikj_dir / 'outline' / 'characters'

    dependency_checks = {
        'benchmark': (_ready_text_file(benchmark_path), f'进入 {step or "当前步骤"} 前必须先完成 benchmark-lite：{benchmark_path}'),
        'worldview': (_ready_text_file(worldview_path), f'进入 {step or "当前步骤"} 前必须先完成世界观设定：{worldview_path}'),
        'characters': (_ready_character_cards(characters_dir), f'进入 {step or "当前步骤"} 前必须先完成人物卡片设定：{characters_dir}'),
        'chapter_outline': (_ready_text_file(outline_path), f'Step 10 之前必须已有章纲讨论结果：{outline_path}'),
        'chapter_file': (chapter_path.exists(), f'Humanizer 缺少目标章节: {chapter_path}'),
        'reply_length': (isinstance(state.get('reply_length'), int) and int(state.get('reply_length')) > 0, '进入正文写作前必须先确认 reply_length'),
    }
    for dependency in STEP_DEPENDENCIES.get(step, []):
        ok, message = dependency_checks[dependency]
        if not ok:
            errors.append(message)

    threshold = min_chapter_chars
    if threshold is None and isinstance(state.get('reply_length'), int):
        threshold = int(state['reply_length'])

    if step == '10' and chapter_path.exists() and threshold is not None:
        try:
            zh_chars = _count_chinese_chars_with_script(chapter_path)
        except Exception as exc:
            errors.append(f'章节字数验收失败：{exc}')
        else:
            infos.append(f'chapter_{effective_chapter}_zh_chars={zh_chars}')
            infos.append('chapter_length_check=scripts/chinese_char_count.py')
            _, count_errors = validate_chinese_char_count(
                chapter_path.read_text(encoding='utf-8-sig', errors='replace'),
                minimum=threshold,
                label=f'chapter_{effective_chapter}',
            )
            errors.extend(count_errors)

    print(f'[validate_state] project={project_dir}')
    for msg in infos:
        print(f'[INFO] {msg}')
    for msg in warnings:
        print(f'[WARNING] {msg}')
    for msg in errors:
        print(f'[ERROR] {msg}')

    if errors:
        return 1
    if strict and warnings:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Validate narrativespace Lite state')
    parser.add_argument('--project-dir', required=True, type=Path)
    parser.add_argument('--chapter', type=int)
    parser.add_argument('--strict', action='store_true')
    parser.add_argument('--for-step', help='Optional target step: worldbuilding / characters / chapter-outline / 10 / humanizer')
    parser.add_argument('--for-step10', action='store_true', help='Compatibility alias for --for-step 10')
    parser.add_argument('--min-chapter-chars', type=int)
    parser.add_argument('--chapter-file', type=Path, help='Optional standalone chapter file for humanizer')
    return parser


def main() -> int:
    reconfigure_stdio_utf8()
    args = build_parser().parse_args()
    for_step = '10' if args.for_step10 and not args.for_step else args.for_step
    return validate(args.project_dir, args.chapter, args.strict, for_step, args.min_chapter_chars, args.chapter_file)


if __name__ == '__main__':
    raise SystemExit(main())
