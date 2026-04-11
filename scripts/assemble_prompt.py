"""
Assemble Lite step prompts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from kb_slicer import format_kb_slice, slice_kb

SKILL_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = SKILL_ROOT / 'templates' / 'prompts'
CONFIG_DIR = SKILL_ROOT / 'config'

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


def _reconfigure_stdout_utf8() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def _read_json(path: Path) -> dict[str, Any]:
    with path.open('r', encoding='utf-8-sig') as fh:
        return json.load(fh)


def _read_text(path: Path, default: str = '（暂无）') -> str:
    if not path.exists():
        return default
    return path.read_text(encoding='utf-8').strip() or default


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
            body = path.read_text(encoding='utf-8').strip()
            sections.append(f'## {filename}\n{body}')
    return '\n\n'.join(sections) if sections else '（无额外规则）'


def _recent_summaries(xushikj_dir: Path) -> str:
    return _read_text(xushikj_dir / 'summaries' / 'summary_index.md')


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
    return '\n\n'.join(parts) if parts else '（由用户在当前步骤补充）'


def _extract_focus_names(scene_text: str) -> list[str]:
    names: list[str] = []
    for line in scene_text.splitlines():
        lower = line.lower()
        if any(key in lower for key in ['viewpoint_character', 'kb_refs']):
            _, _, value = line.partition(':')
            if not value:
                _, _, value = line.partition('：')
            for token in value.replace('/', '、').replace(',', '、').split('、'):
                token = token.strip().strip('[]')
                if token and token not in names:
                    names.append(token)
    return names[:6]


def _load_style_snippet(xushikj_dir: Path) -> str:
    snippet_dir = xushikj_dir / 'benchmark' / 'style_snippets'
    snippets = sorted(snippet_dir.glob('*.md')) if snippet_dir.exists() else []
    if not snippets:
        return '（无风格片段，可直接按规则写作）'
    return _read_text(snippets[0])


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
        f'scene_card_exists={scene_path.exists()}',
        f'chapter_exists={chapter_path.exists()}',
    ])


def assemble(project_dir: Path, step: str, chapter: int | None) -> str:
    project_root, xushikj_dir = _resolve_paths(project_dir)
    if step == 'status':
        return _status(project_root, xushikj_dir)
    if step not in TEMPLATES:
        raise ValueError(f'Unsupported Lite step: {step}')

    state = _load_state(xushikj_dir)
    template = (PROMPTS_DIR / TEMPLATES[step]).read_text(encoding='utf-8')
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
        'rules': _load_rules(step),
        'project_card': project_card,
        'volume_plan': volume_plan,
        'existing_kb': existing_kb,
        'kb_slice': kb_slice_text,
        'chapter_label': chapter_label,
        'scene_card': scene_card,
        'style_snippet': _load_style_snippet(xushikj_dir),
        'chapter_text': _read_text(chapter_path),
    }
    return _render(template, values)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Assemble narrativespace Lite prompt')
    parser.add_argument('--project-dir', required=True, type=Path, help='Project root or .xushikj path')
    parser.add_argument('--step', help='0 / project_card / 4 / 7 / 8 / 10 / humanizer')
    parser.add_argument('--chapter', type=int, help='Optional chapter number for step 8/10/humanizer')
    parser.add_argument('--output', choices=['stdout', 'file'], default='stdout')
    parser.add_argument('--output-file', type=Path)
    parser.add_argument('--status', action='store_true', help='Show Lite project status')
    parser.add_argument('--writing-mode', help='Reserved for compatibility; Lite currently uses pipeline only')
    return parser


def main() -> int:
    _reconfigure_stdout_utf8()
    args = build_arg_parser().parse_args()
    step = 'status' if args.status else args.step
    if not step:
        raise SystemExit('--step or --status is required')
    result = assemble(args.project_dir, step, args.chapter)
    if args.output == 'file':
        if not args.output_file:
            raise SystemExit('--output file requires --output-file')
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_text(result + '\n', encoding='utf-8')
        print(f'[assemble_prompt] wrote {args.output_file}')
    else:
        print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
