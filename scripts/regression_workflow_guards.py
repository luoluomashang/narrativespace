#!/usr/bin/env python3
"""
Lite workflow smoke regression.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return proc.returncode, (proc.stdout or '') + (proc.stderr or '')


def main() -> int:
    parser = argparse.ArgumentParser(description='Run Lite workflow smoke checks')
    parser.add_argument('--project-dir', required=True)
    parser.add_argument('--chapter', type=int, default=1)
    args = parser.parse_args()

    scripts_dir = Path(__file__).resolve().parent
    init_script = scripts_dir / 'init.py'
    assemble_script = scripts_dir / 'assemble_prompt.py'
    validate_script = scripts_dir / 'validate_state.py'

    project_dir = Path(args.project_dir).resolve()
    rc_init, out_init = run_cmd([sys.executable, str(init_script), '--project-dir', str(project_dir), '--yes'])
    if rc_init != 0:
        print(out_init)
        return 1

    xushikj_dir = project_dir / '.xushikj'
    outline_dir = xushikj_dir / 'outline'
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / 'project_card.md').write_text('一句话卖点：测试项目\n', encoding='utf-8')
    (outline_dir / 'volume_1_one_page.md').write_text('第一卷目标：完成 Lite 烟雾测试\n', encoding='utf-8')
    (xushikj_dir / 'scenes').mkdir(parents=True, exist_ok=True)
    (xushikj_dir / 'scenes' / f'chapter_{args.chapter}.md').write_text(
        'chapter_number: 1\n'
        'viewpoint_character: 测试主角\n'
        'chapter_goal: 通过烟雾测试\n'
        'external_conflict: 工具链校验\n'
        'internal_tension: 担心改造不完整\n'
        'key_progression: 生成一版可直接使用的 Lite 产物\n'
        'ending_hook: 下一章开始真实写作\n'
        'kb_refs: 测试主角\n',
        encoding='utf-8',
    )

    checks = [
        [sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', 'project_card'],
        [sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', '4'],
        [sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', '7'],
        [sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', '8', '--chapter', str(args.chapter)],
        [sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', '10', '--chapter', str(args.chapter)],
        [sys.executable, str(validate_script), '--project-dir', str(project_dir), '--for-step', '10', '--chapter', str(args.chapter)],
    ]

    failures: list[str] = []
    for cmd in checks:
        rc, out = run_cmd(cmd)
        if rc != 0:
            failures.append('$ ' + ' '.join(cmd) + '\n' + out)

    if failures:
        print('[regression] FAILED')
        for failure in failures:
            print(failure)
        return 1

    print('[regression] PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
