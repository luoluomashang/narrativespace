"""
Assemble Lite step prompts.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from encoding_utils import read_json_utf8, read_text_utf8, reconfigure_stdio_utf8, write_text_utf8
from kb_slicer import format_kb_slice, slice_kb

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

SKILL_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = SKILL_ROOT / 'templates' / 'prompts'
CONFIG_DIR = SKILL_ROOT / 'config'
MAX_FOCUS_NAMES = 6
EMPTY_PLACEHOLDER = '（暂无）'

RULE_FILES = {
    '0': ['meta_rules.yaml', 'benchmark_lite.yaml'],
    'project_card': ['meta_rules.yaml', 'workflow.yaml'],
    '4': ['meta_rules.yaml', 'workflow.yaml'],
    '7': ['meta_rules.yaml', 'workflow.yaml'],
    '8': ['meta_rules.yaml', 'workflow.yaml'],
    '10': ['meta_rules.yaml', 'writing_rules.yaml', 'style_rules.yaml'],
    'humanizer': ['meta_rules.yaml', 'style_rules.yaml'],
}
TEMPLATES = {
    '0': 'step_0_benchmark_lite.md',
    'project_card': 'step_project_card.md',
    '4': 'step_4_one_page.md',
    '7': 'step_7_kb.md',
    '8': 'step_8_scene_card.md',
    '10': 'step_10_writing.md',
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
    return _read_json(state_path)


def _load_rules(step: str) -> str:
    sections: list[str] = []
    for filename in RULE_FILES.get(step, ['meta_rules.yaml']):
        path = CONFIG_DIR / filename
        if path.exists():
            body = read_text_utf8(path, '', strip=True)
            sections.append(f'## {filename}\n{body}')
    return '\n\n'.join(sections) if sections else '（无额外规则）'


def _recent_summaries(xushikj_dir: Path) -> str:
    summary_path = xushikj_dir / 'summaries' / 'summary_index.md'
    return _compress_summary_index(_read_text(summary_path))


def _project_name(state: dict[str, Any], project_root: Path) -> str:
    name = str(state.get('project_name', '')).strip()
    return name or project_root.name


def _project_context(xushikj_dir: Path, state: dict[str, Any]) -> str:
    parts: list[str] = []
    project_card = xushikj_dir / 'outline' / 'project_card.md'
    if project_card.exists():
        parts.append('## 已有立项卡\n' + _read_text(project_card))
    if state.get('active_style_profile'):
        parts.append(f"## 当前风格\n{state['active_style_profile']}")
    reply_length = state.get('reply_length')
    target_platform = state.get('target_platform')
    parts.append(
        '## 当前写作硬约束\n'
        f"- 每章最小中文字符数：{reply_length if reply_length else '（待确认）'}\n"
        f"- 目标平台：{target_platform if target_platform else '（待确认）'}"
    )
    style_notes = xushikj_dir / 'benchmark' / 'style_notes.md'
    if style_notes.exists():
        parts.append('## 对标风格备忘\n' + _read_text(style_notes))
    return '\n\n'.join(parts) if parts else '（由用户在当前步骤补充）'


def _compress_memory_hint(line: str, max_chars: int = 42) -> str:
    stripped = re.sub(r'\s+', ' ', line).strip()
    if len(stripped) <= max_chars:
        return stripped
    return stripped[:max_chars].rstrip('，,；;。.!?？') + '…'


def _compress_summary_index(summary_text: str) -> str:
    if summary_text in {'', EMPTY_PLACEHOLDER}:
        return EMPTY_PLACEHOLDER

    lines = summary_text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_title = ''
    current_lines: list[str] = []

    for line in lines:
        if line.startswith('## '):
            if current_title or current_lines:
                sections.append((current_title, current_lines))
            current_title = line
            current_lines = []
            continue
        current_lines.append(line)
    if current_title or current_lines:
        sections.append((current_title, current_lines))

    if not sections:
        return '\n'.join(lines[-20:]).strip() or EMPTY_PLACEHOLDER

    rendered: list[str] = []
    for title, body_lines in sections:
        body = [line for line in body_lines if line.strip()]
        if title == '## 最近章节摘要':
            entries = [line for line in body if line.lstrip().startswith('-')]
            if len(entries) > 3:
                earlier = entries[:-3]
                recent = entries[-3:]
                compressed_earlier = [f"- {_compress_memory_hint(line[1:].strip())}" for line in earlier]
                if title:
                    rendered.append(title)
                rendered.extend(recent)
                rendered.append('')
                rendered.append('## 压缩前情')
                rendered.extend(compressed_earlier[-7:])
                continue
        if title:
            rendered.append(title)
        rendered.extend(body or [f'- {EMPTY_PLACEHOLDER}'])
    return '\n'.join(rendered).strip() or EMPTY_PLACEHOLDER


def _extract_focus_names(scene_text: str) -> list[str]:
    pattern = re.compile(r'^(viewpoint_character|kb_refs)\s*[:：]\s*(.+)$', re.IGNORECASE)
    names: list[str] = []
    for line in scene_text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        raw_value = match.group(2)
        for token in re.split(r'[、,/，]+', raw_value):
            cleaned = token.strip().strip("[]()（）\"' ")
            if cleaned and cleaned not in names:
                names.append(cleaned)
    return names[:MAX_FOCUS_NAMES]


def _parse_scene_fields(scene_text: str) -> dict[str, str]:
    scene_fields: dict[str, str] = {}
    for line in scene_text.splitlines():
        matches = re.search(r'[:：]', line)
        if matches is None:
            continue
        separator = matches.group(0)
        key, value = line.split(separator, 1)
        scene_fields[key.strip().lower()] = value.strip()
    return scene_fields


def _strip_yaml_frontmatter(text: str) -> str:
    if text.startswith('---'):
        end = text.find('\n---', 3)
        if end != -1:
            return text[end + 4:].lstrip('\n')
    return text


def _load_style_snippet(xushikj_dir: Path, scene_text: str) -> str:
    snippet_dir = xushikj_dir / 'benchmark' / 'style_snippets'
    manifest_path = snippet_dir / 'manifest.yaml'
    scene_meta = _parse_scene_fields(scene_text)
    raw_scene_type = scene_meta.get('scene_type', '').strip().lower()
    preferred_scene_type = raw_scene_type or 'daily'
    scene_intensity = scene_meta.get('scene_intensity', 'medium').strip() or 'medium'

    if not snippet_dir.exists():
        return '（无风格片段，可直接按规则写作）'

    manifest = _load_yaml_or_json(manifest_path, {'snippets': {}})
    snippets_by_type = manifest.get('snippets', {})
    selected_path: Path | None = None
    selected_scene_type = preferred_scene_type

    if isinstance(snippets_by_type, dict):
        candidate_scene_types = [preferred_scene_type]
        if preferred_scene_type != 'daily':
            candidate_scene_types.append('daily')
        for scene_type in candidate_scene_types:
            payload = snippets_by_type.get(scene_type, {})
            if isinstance(payload, dict):
                files = payload.get('files', [])
                if isinstance(files, list):
                    for filename in files:
                        candidate = snippet_dir / str(filename)
                        if candidate.exists():
                            selected_path = candidate
                            selected_scene_type = scene_type
                            break
            if selected_path is not None:
                break

    if selected_path is None:
        snippets = sorted(snippet_dir.glob('*.md'))
        if not snippets:
            return '（无风格片段，可直接按规则写作）'
        selected_path = snippets[0]
        selected_scene_type = 'fallback'

    snippet_body = _strip_yaml_frontmatter(_read_text(selected_path))
    return (
        f"> 风格切片来源：scene_type={selected_scene_type} / intensity={scene_intensity} / file={selected_path.name}\n"
        f"{snippet_body}"
    )


def _memory_context(xushikj_dir: Path) -> str:
    return _read_text(xushikj_dir / 'memory.md')


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
    scene_path = xushikj_dir / 'scenes' / f"chapter_{state.get('current_chapter', 1)}.md"
    chapter_path = xushikj_dir / 'chapters' / f"chapter_{state.get('current_chapter', 1)}.md"
    return '\n'.join([
        f'project={project_root}',
        'initialized=true',
        f"current_step={state.get('current_step', '')}",
        f"current_volume={state.get('current_volume', 1)}",
        f"current_chapter={state.get('current_chapter', 1)}",
        f"writing_mode={state.get('writing_mode', 'pipeline')}",
        f"reply_length={state.get('reply_length', '')}",
        f"target_platform={state.get('target_platform', '')}",
        f'scene_card_exists={scene_path.exists()}',
        f'chapter_exists={chapter_path.exists()}',
        f"style_notes_exists={(xushikj_dir / 'benchmark' / 'style_notes.md').exists()}",
        f"style_manifest_exists={(xushikj_dir / 'benchmark' / 'style_snippets' / 'manifest.yaml').exists()}",
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
    if step == 'humanizer':
        template = read_text_utf8(PROMPTS_DIR / TEMPLATES[step], '')
        humanizer_chapter_path, chapter_label = _resolve_humanizer_chapter(project_root, xushikj_dir, chapter, chapter_file)
        values = {
            'chapter_label': chapter_label,
            'chapter_text': _read_text(humanizer_chapter_path),
            'rules': _load_rules(step),
        }
        return _render(template, values)

    state = _load_state(xushikj_dir)
    template = read_text_utf8(PROMPTS_DIR / TEMPLATES[step], '')
    project_name = _project_name(state, project_root)
    current_volume = int(state.get('current_volume', 1))
    chapter_no = chapter or int(state.get('current_chapter', 1))

    project_card = _read_text(xushikj_dir / 'outline' / 'project_card.md')
    volume_plan = _read_text(xushikj_dir / 'outline' / f'volume_{current_volume}_one_page.md')
    existing_kb = _read_text(xushikj_dir / 'knowledge_base.json', default='{}')
    summary_text = _recent_summaries(xushikj_dir)
    chapter_label = f'第 {chapter_no} 章'
    scene_path = xushikj_dir / 'scenes' / f'chapter_{chapter_no}.md'
    scene_card = _read_text(scene_path)
    scene_meta = _parse_scene_fields(scene_card)
    focus_names = _extract_focus_names(scene_card)

    kb_slice_text = '（知识库缺失）'
    kb_path = xushikj_dir / 'knowledge_base.json'
    if kb_path.exists():
        kb_slice_text = format_kb_slice(slice_kb(kb_path, focus_names=focus_names))

    if step == '10' and not scene_path.exists():
        raise FileNotFoundError(f'Writing step requires scene card: {scene_path}')

    chapter_path = xushikj_dir / 'chapters' / f'chapter_{chapter_no}.md'
    values = {
        'project_name': project_name,
        'project_context': _project_context(xushikj_dir, state),
        'recent_summaries': summary_text,
        'memory_context': _memory_context(xushikj_dir),
        'rules': _load_rules(step),
        'project_card': project_card,
        'volume_plan': volume_plan,
        'existing_kb': existing_kb,
        'kb_slice': kb_slice_text,
        'chapter_label': chapter_label,
        'scene_card': scene_card,
        'scene_type': scene_meta.get('scene_type', 'daily') or 'daily',
        'scene_intensity': scene_meta.get('scene_intensity', 'medium') or 'medium',
        'reply_length': str(state.get('reply_length') or '（待确认）'),
        'target_platform': str(state.get('target_platform') or '（待确认）'),
        'style_snippet': _load_style_snippet(xushikj_dir, scene_card),
        'chapter_text': _read_text(chapter_path),
    }
    return _render(template, values)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Assemble narrativespace Lite prompt')
    parser.add_argument('--project-dir', required=True, type=Path, help='Project root or .xushikj path')
    parser.add_argument('--step', help='0 / project_card / 4 / 7 / 8 / 10 / humanizer')
    parser.add_argument('--chapter', type=int, help='Optional chapter number for step 8/10/humanizer')
    parser.add_argument('--chapter-file', type=Path, help='Optional standalone chapter file for humanizer')
    parser.add_argument('--output', choices=['stdout', 'file'], default='stdout')
    parser.add_argument('--output-file', type=Path)
    parser.add_argument('--status', action='store_true', help='Show Lite project status')
    parser.add_argument('--writing-mode', help='Reserved for compatibility; Lite currently uses pipeline only')
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
