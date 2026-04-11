"""
Lite project initializer for narrativespace.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
ACTIVE_CONFIGS = [
    'workflow.yaml',
    'meta_rules.yaml',
    'writing_rules.yaml',
    'style_rules.yaml',
    'benchmark_lite.yaml',
]
OPTIONAL_CONFIGS = ['human_touch_rules.yaml']
TEXT_TEMPLATES = {
    'summaries/summary_index.md': SKILL_ROOT / 'templates' / 'summary_index_template.md',
    'memory.md': SKILL_ROOT / 'templates' / 'memory_template.md',
}
JSON_TEMPLATES = {
    'state.json': SKILL_ROOT / 'templates' / 'state_template.json',
    'knowledge_base.json': SKILL_ROOT / 'templates' / 'kb_template.json',
}


def _reconfigure_stdout_utf8() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _read_json(path: Path) -> dict[str, Any]:
    with path.open('r', encoding='utf-8-sig') as fh:
        return json.load(fh)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _merge_dict(defaults: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    """Merge Lite defaults into an existing payload.

    Dicts merge recursively. Lists are intentionally treated as user-owned content and
    therefore replaced wholesale by the existing value instead of concatenating defaults.
    When an existing key is absent, the default list remains in place.
    Scalar values use the existing value whenever the key is present.
    """
    merged = defaults.copy()
    for key, value in existing.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = value
        else:
            merged[key] = value
    return merged


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Initialize narrativespace Lite project')
    parser.add_argument('--project-dir', required=True, type=Path)
    parser.add_argument('--upgrade', action='store_true', help='Merge new Lite defaults into an existing project')
    parser.add_argument('--force', action='store_true', help='Overwrite generated Lite files')
    parser.add_argument('--yes', '-y', action='store_true', help='Reserved for non-interactive compatibility')
    parser.add_argument('--build-rag-index', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--init-volume-timeline', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--volume', type=int, default=1, help=argparse.SUPPRESS)
    parser.add_argument('--global-dna-path', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--link-author', type=str, help=argparse.SUPPRESS)
    return parser


def ensure_dirs(xushikj_dir: Path) -> None:
    for relative in [
        'config',
        'outline',
        'benchmark/style_snippets',
        'scenes',
        'chapters',
        'summaries',
        'drafts',
        'humanized',
    ]:
        (xushikj_dir / relative).mkdir(parents=True, exist_ok=True)


def copy_configs(xushikj_dir: Path, force: bool) -> list[str]:
    log: list[str] = []
    for filename in ACTIVE_CONFIGS + OPTIONAL_CONFIGS:
        src = SKILL_ROOT / 'config' / filename
        if not src.exists():
            continue
        dst = xushikj_dir / 'config' / filename
        if dst.exists() and not force:
            log.append(f'  [skip]    config/{filename}')
            continue
        shutil.copy2(src, dst)
        log.append(f'  [write]   config/{filename}')
    return log


def write_text_templates(xushikj_dir: Path, force: bool) -> list[str]:
    log: list[str] = []
    for relative_name, src in TEXT_TEMPLATES.items():
        dst = xushikj_dir / relative_name
        if dst.exists() and not force:
            log.append(f'  [skip]    {relative_name}')
            continue
        shutil.copy2(src, dst)
        log.append(f'  [write]   {relative_name}')
    return log


def write_json_templates(xushikj_dir: Path, force: bool, upgrade: bool) -> list[str]:
    log: list[str] = []
    for relative_name, src in JSON_TEMPLATES.items():
        dst = xushikj_dir / relative_name
        default_payload = _read_json(src)
        if relative_name == 'state.json':
            default_payload['last_updated'] = _now_iso()
        if not dst.exists() or force:
            _write_json(dst, default_payload)
            log.append(f'  [write]   {relative_name}')
            continue
        if upgrade:
            merged = _merge_dict(default_payload, _read_json(dst))
            if relative_name == 'state.json':
                merged['last_updated'] = _now_iso()
            _write_json(dst, merged)
            log.append(f'  [merge]   {relative_name}')
        else:
            log.append(f'  [skip]    {relative_name}')
    return log


def main() -> int:
    _reconfigure_stdout_utf8()
    args = build_arg_parser().parse_args()
    project_dir = args.project_dir.resolve()
    xushikj_dir = project_dir if project_dir.name == '.xushikj' else project_dir / '.xushikj'

    ensure_dirs(xushikj_dir)

    log: list[str] = []
    log.extend(copy_configs(xushikj_dir, force=args.force or args.upgrade))
    log.extend(write_text_templates(xushikj_dir, force=args.force))
    log.extend(write_json_templates(xushikj_dir, force=args.force, upgrade=args.upgrade))

    print(f'[init] Lite project ready: {xushikj_dir}')
    for line in log:
        print(line)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
