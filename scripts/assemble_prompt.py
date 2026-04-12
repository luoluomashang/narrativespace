"""
Assemble Lite step prompts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from encoding_utils import read_json_utf8, read_text_utf8, reconfigure_stdio_utf8, write_text_utf8
from workflow_state import assert_step_allowed, ensure_workflow_state

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

SKILL_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = SKILL_ROOT / 'templates' / 'prompts'
CONFIG_DIR = SKILL_ROOT / 'config'
EMPTY_PLACEHOLDER = '（暂无）'
PLACEHOLDER = '（待填写）'
RULE_FILES = {
    '0': ['meta_rules.yaml', 'benchmark_lite.yaml'],
    'benchmark-lite': ['meta_rules.yaml', 'benchmark_lite.yaml'],
    'worldbuilding': ['meta_rules.yaml', 'workflow.yaml'],
    'chapter-outline': ['meta_rules.yaml', 'workflow.yaml'],
    '10': ['meta_rules.yaml', 'writing_rules.yaml', 'style_rules.yaml'],
    'writing': ['meta_rules.yaml', 'writing_rules.yaml', 'style_rules.yaml'],
    'humanizer': ['meta_rules.yaml', 'style_rules.yaml', 'humanizer_rules.yaml'],
}
TEMPLATES = {
    '0': 'step_0_benchmark_lite.md',
    'benchmark-lite': 'step_0_benchmark_lite.md',
    'worldbuilding': 'step_worldbuilding.md',
    'chapter-outline': 'step_chapter_outline.md',
    '10': 'step_10_writing.md',
    'writing': 'step_10_writing.md',
    'humanizer': 'step_humanizer.md',
}


def _read_json(path: Path) -> dict[str, Any]:
    return read_json_utf8(path)


def _read_text(path: Path, default: str = EMPTY_PLACEHOLDER) -> str:
    return read_text_utf8(path, default, strip=True) or default


def _load_yaml_or_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    fallback = default or {}
    if not path.exists():
        return fallback
    raw = read_text_utf8(path, '', strip=True)
    if not raw:
        return fallback
    try:
        if YAML_AVAILABLE:
            payload = yaml.safe_load(raw)
        else:
            payload = json.loads(raw)
    except Exception:
        return fallback
    return payload if isinstance(payload, dict) else fallback


def _resolve_paths(project_dir: Path) -> tuple[Path, Path]:
    project_dir = project_dir.resolve()
    if project_dir.name == '.xushikj':
        return project_dir.parent, project_dir
    return project_dir, project_dir / '.xushikj'


def _load_state(xushikj_dir: Path) -> dict[str, Any]:
    state_path = xushikj_dir / 'state.json'
    if not state_path.exists():
        raise FileNotFoundError(f'Missing state.json: {state_path}')
    return ensure_workflow_state(_read_json(state_path))


def _load_rules(step: str) -> str:
    sections: list[str] = []
    for filename in RULE_FILES.get(step, ['meta_rules.yaml']):
        path = CONFIG_DIR / filename
        if path.exists():
            body = read_text_utf8(path, '', strip=True)
            sections.append(f'## {filename}\n{body}')
    return '\n\n'.join(sections) if sections else '（无额外规则）'


def _extract_constraint_lines(data: Any, keys: list[str], limit: int) -> list[str]:
    pool: list[dict[str, Any]] = []

    def _flatten(node: Any) -> None:
        if isinstance(node, dict):
            pool.append(node)
            for value in node.values():
                _flatten(value)
        elif isinstance(node, list):
            for item in node:
                _flatten(item)

    _flatten(data)
    lines: list[str] = []
    for item in pool:
        for key in keys:
            value = item.get(key)
            if isinstance(value, list):
                for raw in value:
                    text = str(raw).strip()
                    if text and text not in lines:
                        lines.append(text)
            elif isinstance(value, str):
                text = value.strip()
                if text and text not in lines:
                    lines.append(text)
            if len(lines) >= limit:
                return lines[:limit]
    return lines[:limit]


def _humanizer_dna_constraints(xushikj_dir: Path) -> str:
    style_modules_dir = xushikj_dir / 'config' / 'style_modules'
    if not style_modules_dir.exists():
        return '（当前项目未提供 dna_human_*.yaml / clone_*.yaml，可跳过 R-DNA 保护）'

    dna_files = sorted(style_modules_dir.glob('dna_human_*.yaml'))
    source_label = 'dna_human'
    if not dna_files:
        dna_files = sorted(style_modules_dir.glob('clone_*.yaml'))
        source_label = 'clone'
    if not dna_files:
        return '（当前项目未提供 dna_human_*.yaml / clone_*.yaml，可跳过 R-DNA 保护）'

    dna_path = dna_files[0]
    dna_payload = _load_yaml_or_json(dna_path, {})
    do_items = _extract_constraint_lines(dna_payload, ['do', 'do_list', 'dos', 'preferred', 'guidelines'], 6)
    dont_items = _extract_constraint_lines(dna_payload, ['dont', 'dont_list', 'donts', 'forbidden', 'avoid'], 6)
    lines = [f'- source={source_label}:{dna_path.name}']
    lines.extend(f'- DO: {item}' for item in do_items)
    lines.extend(f"- DON'T: {item}" for item in dont_items)
    return '\n'.join(lines) if len(lines) > 1 else f'- source={source_label}:{dna_path.name}'


def _recent_summaries(xushikj_dir: Path) -> str:
    return _read_text(xushikj_dir / 'summaries' / 'summary_index.md')


def _project_name(state: dict[str, Any], project_root: Path) -> str:
    name = str(state.get('project_name', '')).strip()
    return name or project_root.name


def _project_context(state: dict[str, Any]) -> str:
    parts = [
        '## 当前项目硬约束',
        f"- 每章最小中文字符数：{state.get('reply_length') or '（待确认）'}",
        f"- 目标平台（可选）：{state.get('target_platform') or '（未设置）'}",
        f"- 当前写作模式：{state.get('writing_mode') or 'style-clone'}",
    ]
    if state.get('active_style_profile'):
        parts.append(f"- 当前风格标签：{state['active_style_profile']}")
    return '\n'.join(parts)


def _ready_text(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8-sig', errors='replace').strip()
    return bool(text) and PLACEHOLDER not in text


def _memory_context(xushikj_dir: Path) -> str:
    return _read_text(xushikj_dir / 'memory.md')


def _previous_excerpt(xushikj_dir: Path, chapter_no: int) -> str:
    if chapter_no <= 1:
        return '（暂无前文，可直接从本章开写）'
    previous_path = xushikj_dir / 'chapters' / f'chapter_{chapter_no - 1}.md'
    if not previous_path.exists():
        return '（上一章正文暂缺）'
    text = _read_text(previous_path)
    if len(text) <= 1200:
        return text
    return text[-1200:]


def _render(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f'{{{{{key}}}}}', value)
    return rendered


def _status(project_root: Path, xushikj_dir: Path) -> str:
    initialized = xushikj_dir.exists() and (xushikj_dir / 'state.json').exists()
    if not initialized:
        return f'project={project_root}\ninitialized=false'
    state = _load_state(xushikj_dir)
    workflow = state['workflow']
    chapter_no = int(state.get('current_chapter', 1))
    return '\n'.join([
        f'project={project_root}',
        'initialized=true',
        f"current_step={state.get('current_step', '')}",
        f"current_chapter={chapter_no}",
        f"writing_mode={state.get('writing_mode', 'style-clone')}",
        f"reply_length={state.get('reply_length', '')}",
        f"target_platform={state.get('target_platform', '')}",
        f"pending_user_confirmation={str(bool(workflow.get('pending_user_confirmation'))).lower()}",
        f"pending_step={workflow.get('pending_step', '')}",
        f"next_step_suggestion={workflow.get('next_step_suggestion', '')}",
        f"benchmark_ready={_ready_text(xushikj_dir / 'benchmark' / 'style_notes.md')}",
        f"worldview_ready={_ready_text(xushikj_dir / 'worldbuilding' / 'worldview.md')}",
        f"chapter_outline_ready={_ready_text(xushikj_dir / 'chapter_outlines' / f'chapter_{chapter_no}.md')}",
        f"chapter_exists={(xushikj_dir / 'chapters' / f'chapter_{chapter_no}.md').exists()}",
    ])


def _resolve_humanizer_chapter(
    project_root: Path,
    xushikj_dir: Path,
    chapter: int | None,
    chapter_file: Path | None,
) -> tuple[Path, str]:
    if chapter_file is not None:
        path = chapter_file.resolve()
        if not path.exists():
            raise FileNotFoundError(f'Humanizer chapter file not found: {path}')
        return path, path.stem

    if chapter is not None:
        candidates = [
            xushikj_dir / 'chapters' / f'chapter_{chapter}.md',
            project_root / 'chapters' / f'chapter_{chapter}.md',
            project_root / f'chapter_{chapter}.md',
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate, f'第 {chapter} 章'
        raise FileNotFoundError(f'Humanizer chapter file not found: {candidates[0]}')

    state_path = xushikj_dir / 'state.json'
    if state_path.exists():
        state = _load_state(xushikj_dir)
        chapter_no = int(state.get('current_chapter', 1))
        chapter_path = xushikj_dir / 'chapters' / f'chapter_{chapter_no}.md'
        if not chapter_path.exists():
            raise FileNotFoundError(f'Humanizer chapter file not found: {chapter_path}')
        return chapter_path, f'第 {chapter_no} 章'

    raise FileNotFoundError('Humanizer requires --chapter-file or --chapter when state.json is unavailable')


def assemble(project_dir: Path, step: str, chapter: int | None, chapter_file: Path | None = None) -> str:
    project_root, xushikj_dir = _resolve_paths(project_dir)
    if step == 'status':
        return _status(project_root, xushikj_dir)
    if step not in TEMPLATES:
        raise ValueError(f'Unsupported Lite step: {step}')
    if step != 'humanizer':
        assert_step_allowed(project_root, step)
    if step == 'humanizer':
        if (xushikj_dir / 'state.json').exists():
            assert_step_allowed(project_root, step)
        template = read_text_utf8(PROMPTS_DIR / TEMPLATES[step], '')
        humanizer_chapter_path, chapter_label = _resolve_humanizer_chapter(project_root, xushikj_dir, chapter, chapter_file)
        values = {
            'chapter_label': chapter_label,
            'chapter_text': _read_text(humanizer_chapter_path),
            'rules': _load_rules(step),
            'dna_constraints': _humanizer_dna_constraints(xushikj_dir),
        }
        return _render(template, values)

    state = _load_state(xushikj_dir)
    project_name = _project_name(state, project_root)
    chapter_no = chapter or int(state.get('current_chapter', 1))
    style_notes_path = xushikj_dir / 'benchmark' / 'style_notes.md'
    worldview_path = xushikj_dir / 'worldbuilding' / 'worldview.md'
    outline_path = xushikj_dir / 'chapter_outlines' / f'chapter_{chapter_no}.md'
    template = read_text_utf8(PROMPTS_DIR / TEMPLATES[step], '')

    if step in {'worldbuilding', 'chapter-outline', '10', 'writing'} and not _ready_text(style_notes_path):
        raise FileNotFoundError(f'benchmark-lite 尚未完成，请先产出可用的文风特征指南：{style_notes_path}')
    if step in {'chapter-outline', '10', 'writing'} and not _ready_text(worldview_path):
        raise FileNotFoundError(f'世界观设定尚未完成，请先补齐：{worldview_path}')
    if step in {'10', 'writing'} and not _ready_text(outline_path):
        raise FileNotFoundError(f'章纲讨论尚未完成，请先补齐：{outline_path}')
    if step in {'10', 'writing'} and not (isinstance(state.get('reply_length'), int) and int(state.get('reply_length')) > 0):
        raise ValueError('进入 writing 前必须先确认 reply_length')

    values = {
        'project_name': project_name,
        'project_context': _project_context(state),
        'recent_summaries': _recent_summaries(xushikj_dir),
        'rules': _load_rules(step),
        'style_guide': _read_text(style_notes_path),
        'worldview_text': _read_text(worldview_path),
        'chapter_outline': _read_text(outline_path),
        'chapter_label': f'第 {chapter_no} 章',
        'reply_length': str(state.get('reply_length') or '（待确认）'),
        'target_platform': str(state.get('target_platform') or '（未设置）'),
        'memory_context': _memory_context(xushikj_dir),
        'previous_excerpt': _previous_excerpt(xushikj_dir, chapter_no),
    }
    return _render(template, values)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Assemble narrativespace Lite prompt')
    parser.add_argument('--project-dir', required=True, type=Path, help='Project root or .xushikj path')
    parser.add_argument('--step', help='0 / benchmark-lite / worldbuilding / chapter-outline / 10 / writing / humanizer')
    parser.add_argument('--chapter', type=int, help='Optional chapter number for step chapter-outline/10/humanizer')
    parser.add_argument('--chapter-file', type=Path, help='Optional standalone chapter file for humanizer')
    parser.add_argument('--output', choices=['stdout', 'file'], default='stdout')
    parser.add_argument('--output-file', type=Path)
    parser.add_argument('--status', action='store_true', help='Show Lite project status')
    parser.add_argument('--writing-mode', help='Reserved for compatibility; Lite currently uses style-clone only')
    return parser


def main() -> int:
    reconfigure_stdio_utf8()
    args = build_arg_parser().parse_args()
    step = 'status' if args.status else args.step
    if not step:
        raise SystemExit('--step or --status is required')
    result = assemble(args.project_dir, step, args.chapter, args.chapter_file)
    if args.output == 'file':
        if not args.output_file:
            raise SystemExit('--output file requires --output-file')
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        write_text_utf8(args.output_file, result + '\n')
        print(f'[assemble_prompt] wrote {args.output_file}')
    else:
        print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
