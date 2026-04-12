#!/usr/bin/env python3
"""
Unified Lite workflow gate and confirmation state management.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from encoding_utils import read_json_utf8, reconfigure_stdio_utf8, write_text_utf8

DEFAULT_NEXT_STEP = {
    'benchmark-lite': 'worldbuilding',
    'worldbuilding': 'characters',
    'characters': 'chapter-outline',
    'chapter-outline': '10',
    '10': 'humanizer',
    'humanizer': '',
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def resolve_paths(project_dir: Path) -> tuple[Path, Path]:
    project_dir = project_dir.resolve()
    if project_dir.name == '.xushikj':
        return project_dir.parent, project_dir
    return project_dir, project_dir / '.xushikj'


def workflow_defaults() -> dict[str, Any]:
    return {
        'current_step_status': 'idle',
        'pending_user_confirmation': False,
        'pending_step': '',
        'next_step_suggestion': '',
        'last_gate_message': '',
        'last_validation_passed': False,
        'last_validation_summary': '',
        'landed_outputs': [],
        'last_completed_step': '',
    }


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def ensure_workflow_state(state: dict[str, Any]) -> dict[str, Any]:
    payload = state.get('workflow')
    defaults = workflow_defaults()
    if not isinstance(payload, dict):
        state['workflow'] = defaults
        return state
    merged = defaults | payload
    landed_outputs = merged.get('landed_outputs', [])
    merged['landed_outputs'] = [str(item) for item in landed_outputs] if isinstance(landed_outputs, list) else []
    state['workflow'] = merged
    return state


def load_state(project_dir: Path) -> tuple[Path, Path, Path, dict[str, Any]]:
    project_root, xushikj_dir = resolve_paths(project_dir)
    state_path = xushikj_dir / 'state.json'
    if not state_path.exists():
        raise FileNotFoundError(f'Missing state.json: {state_path}')
    state = ensure_workflow_state(read_json_utf8(state_path))
    return project_root, xushikj_dir, state_path, state


def save_state(state_path: Path, state: dict[str, Any]) -> None:
    state['last_updated'] = _now_iso()
    write_text_utf8(state_path, json.dumps(state, ensure_ascii=False, indent=2) + '\n')


def assert_step_allowed(project_dir: Path, step: str) -> None:
    if step == 'status':
        return
    _, _, _, state = load_state(project_dir)
    workflow = ensure_workflow_state(state)['workflow']
    pending = bool(workflow.get('pending_user_confirmation'))
    pending_step = str(workflow.get('pending_step', '')).strip()
    if pending:
        raise RuntimeError(
            f'当前步骤 {pending_step or state.get("current_step", "")} 已完成并待用户确认；'
            f'禁止直接进入 {step}。请先执行 python scripts/workflow_state.py confirm --project-dir {project_dir}。'
        )


def mark_step_complete(
    project_dir: Path,
    *,
    step: str,
    output_paths: list[Path] | None = None,
    validation_passed: bool,
    validation_summary: str,
    next_step_suggestion: str | None = None,
) -> dict[str, Any]:
    _, _, state_path, state = load_state(project_dir)
    workflow = ensure_workflow_state(state)['workflow']
    state['current_step'] = step
    state['last_completed_steps'] = _dedupe_strings([*state.get('last_completed_steps', []), step])
    workflow['current_step_status'] = 'completed'
    workflow['pending_user_confirmation'] = True
    workflow['pending_step'] = step
    workflow['last_completed_step'] = step
    workflow['next_step_suggestion'] = next_step_suggestion if next_step_suggestion is not None else DEFAULT_NEXT_STEP.get(step, '')
    workflow['last_gate_message'] = f'步骤 {step} 已完成，请等待用户确认后再继续。'
    workflow['last_validation_passed'] = bool(validation_passed)
    workflow['last_validation_summary'] = validation_summary.strip()
    serialized_outputs = [str(path) for path in (output_paths or [])]
    workflow['landed_outputs'] = _dedupe_strings([*workflow.get('landed_outputs', []), *serialized_outputs])
    save_state(state_path, state)
    return state


def confirm_step(project_dir: Path, advance_to: str | None = None) -> dict[str, Any]:
    _, _, state_path, state = load_state(project_dir)
    workflow = ensure_workflow_state(state)['workflow']
    pending_step = str(workflow.get('pending_step', '')).strip() or str(state.get('current_step', '')).strip()
    state['current_step'] = advance_to if advance_to is not None else (workflow.get('next_step_suggestion') or pending_step)
    workflow['current_step_status'] = 'idle'
    workflow['pending_user_confirmation'] = False
    workflow['pending_step'] = ''
    workflow['last_gate_message'] = f'用户已确认步骤 {pending_step}。'
    workflow['next_step_suggestion'] = ''
    save_state(state_path, state)
    return state


def workflow_status(project_dir: Path) -> str:
    _, _, _, state = load_state(project_dir)
    workflow = ensure_workflow_state(state)['workflow']
    return '\n'.join([
        f"current_step={state.get('current_step', '')}",
        f"current_step_status={workflow.get('current_step_status', '')}",
        f"pending_user_confirmation={str(bool(workflow.get('pending_user_confirmation'))).lower()}",
        f"pending_step={workflow.get('pending_step', '')}",
        f"next_step_suggestion={workflow.get('next_step_suggestion', '')}",
        f"last_validation_passed={str(bool(workflow.get('last_validation_passed'))).lower()}",
        f"last_gate_message={workflow.get('last_gate_message', '')}",
    ])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Manage Lite workflow state and confirmation gates')
    subparsers = parser.add_subparsers(dest='command', required=True)

    status_parser = subparsers.add_parser('status', help='Print workflow gate status')
    status_parser.add_argument('--project-dir', required=True, type=Path)

    confirm_parser = subparsers.add_parser('confirm', help='Clear pending gate after user confirmation')
    confirm_parser.add_argument('--project-dir', required=True, type=Path)
    confirm_parser.add_argument('--advance-to', help='Optional explicit next step')
    return parser


def main() -> int:
    reconfigure_stdio_utf8()
    args = build_parser().parse_args()
    if args.command == 'status':
        print(workflow_status(args.project_dir))
        return 0
    if args.command == 'confirm':
        state = confirm_step(args.project_dir, advance_to=args.advance_to)
        workflow = ensure_workflow_state(state)['workflow']
        print(f"[workflow_state] confirmed; current_step={state.get('current_step', '')}")
        print(f"[workflow_state] pending_user_confirmation={str(bool(workflow.get('pending_user_confirmation'))).lower()}")
        return 0
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
