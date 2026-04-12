#!/usr/bin/env python3
"""
Lite workflow smoke regression.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from encoding_utils import reconfigure_stdio_utf8, subprocess_utf8_kwargs, write_text_utf8


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, **subprocess_utf8_kwargs())
    return proc.returncode, (proc.stdout or '') + (proc.stderr or '')


def expect_success(cmd: list[str], *, contains: list[str] | None = None, forbid_replacement_char: bool = False) -> str:
    rc, out = run_cmd(cmd)
    if rc != 0:
        raise AssertionError('$ ' + ' '.join(cmd) + '\n' + out)
    for needle in contains or []:
        if needle not in out:
            raise AssertionError(f'缺少预期输出: {needle}\n$ {" ".join(cmd)}\n{out}')
    if forbid_replacement_char and '�' in out:
        raise AssertionError(f'检测到乱码替代字符\n$ {" ".join(cmd)}\n{out}')
    return out


def expect_failure(cmd: list[str], *, contains: list[str] | None = None) -> str:
    rc, out = run_cmd(cmd)
    if rc == 0:
        raise AssertionError('命令应失败但成功：$ ' + ' '.join(cmd) + '\n' + out)
    for needle in contains or []:
        if needle not in out:
            raise AssertionError(f'失败输出缺少预期内容: {needle}\n$ {" ".join(cmd)}\n{out}')
    return out


def main() -> int:
    reconfigure_stdio_utf8()
    parser = argparse.ArgumentParser(description='Run Lite workflow smoke checks')
    parser.add_argument('--project-dir', required=True)
    parser.add_argument('--chapter', type=int, default=1)
    args = parser.parse_args()

    scripts_dir = Path(__file__).resolve().parent
    init_script = scripts_dir / 'init.py'
    assemble_script = scripts_dir / 'assemble_prompt.py'
    landing_script = scripts_dir / 'landing.py'
    workflow_script = scripts_dir / 'workflow_state.py'
    validate_script = scripts_dir / 'validate_state.py'
    slice_script = scripts_dir / 'slice_library.py'

    project_dir = Path(args.project_dir).resolve() / '中文项目'
    project_dir.mkdir(parents=True, exist_ok=True)
    expect_success([
        sys.executable,
        str(init_script),
        '--project-dir',
        str(project_dir),
        '--yes',
        '--reply-length',
        '50',
        '--target-platform',
        'fanqie',
    ], contains=['[init] Lite project ready'], forbid_replacement_char=True)

    xushikj_dir = project_dir / '.xushikj'
    outline_dir = xushikj_dir / 'outline'
    outline_dir.mkdir(parents=True, exist_ok=True)
    write_text_utf8(outline_dir / 'project_card.md', '一句话卖点：中文测试项目\n')
    write_text_utf8(outline_dir / 'volume_1_one_page.md', '第一卷目标：完成 Lite 中文烟雾测试\n')
    (xushikj_dir / 'scenes').mkdir(parents=True, exist_ok=True)
    write_text_utf8(
        xushikj_dir / 'scenes' / f'chapter_{args.chapter}.md',
        'chapter_number: 1\n'
        'scene_type: daily\n'
        'scene_intensity: medium\n'
        'viewpoint_character: 测试主角\n'
        'chapter_goal: 通过烟雾测试\n'
        'external_conflict: 工具链校验\n'
        'internal_tension: 担心改造不完整\n'
        'key_progression: 生成一版可直接使用的 Lite 产物\n'
        'ending_hook: 下一章开始真实写作\n'
        'kb_refs: 测试主角\n',
    )
    benchmark_dir = xushikj_dir / 'benchmark' / 'style_snippets'
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    write_text_utf8(xushikj_dir / 'benchmark' / 'style_notes.md', '题材气质：轻快升级流\n')
    write_text_utf8(benchmark_dir / 'daily_sample.md', '他抬手推门，潮湿的风立刻灌进走廊。')
    write_text_utf8(
        benchmark_dir / 'manifest.yaml',
        'snippets:\n'
        '  daily:\n'
        '    files:\n'
        '      - daily_sample.md\n'
        '    count: 1\n',
    )

    failures: list[str] = []
    try:
        for cmd, contains in [
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', 'project_card'], ['产品策划']),
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', '4'], ['当前卷一页纲']),
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', '7'], ['设定整理员']),
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', '8', '--chapter', str(args.chapter)], ['章节导演']),
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', '10', '--chapter', str(args.chapter)], ['连载小说执笔者', '风格切片来源']),
        ]:
            expect_success(cmd, contains=contains, forbid_replacement_char=True)

        writing_output = xushikj_dir / 'drafts' / 'chapter_1_output.md'
        write_text_utf8(
            writing_output,
            ('测试正文。' * 30) + '\n\n'
            '## 本章摘要\n'
            '- 主角完成烟雾测试并准备进入下一章。\n\n'
            '## 状态变化\n'
            '- 主角确认当前工具链可用。\n\n'
            '## 新增设定\n'
            '- 烟雾测试流程要求先落盘再验收。\n\n'
            '## 未兑现钩子\n'
            '- 下一章开始真实写作。\n',
        )
        expect_success(
            [sys.executable, str(landing_script), 'writing', '--project-dir', str(project_dir), '--chapter', str(args.chapter), '--input-file', str(writing_output)],
            contains=['已写入正文', 'chapter_1_zh_chars='],
            forbid_replacement_char=True,
        )
        expect_success(
            [sys.executable, str(validate_script), '--project-dir', str(project_dir), '--for-step', '10', '--chapter', str(args.chapter)],
            contains=['chapter_1_zh_chars=', 'pending_user_confirmation=true'],
            forbid_replacement_char=True,
        )
        expect_failure(
            [sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', '8', '--chapter', str(args.chapter)],
            contains=['待用户确认'],
        )
        expect_success(
            [sys.executable, str(workflow_script), 'confirm', '--project-dir', str(project_dir)],
            contains=['pending_user_confirmation=false'],
            forbid_replacement_char=True,
        )
        expect_success(
            [sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', '8', '--chapter', str(args.chapter)],
            contains=['章节导演'],
            forbid_replacement_char=True,
        )

        short_project = Path(args.project_dir).resolve() / '短章测试'
        short_project.mkdir(parents=True, exist_ok=True)
        expect_success([
            sys.executable,
            str(init_script),
            '--project-dir',
            str(short_project),
            '--yes',
            '--reply-length',
            '50',
            '--target-platform',
            'fanqie',
        ], contains=['[init] Lite project ready'], forbid_replacement_char=True)
        short_xushikj = short_project / '.xushikj'
        short_output = short_xushikj / 'drafts' / 'chapter_1_output.md'
        write_text_utf8(
            short_output,
            '太短了。\n\n'
            '## 本章摘要\n- 太短。\n\n'
            '## 状态变化\n- （暂无）\n\n'
            '## 新增设定\n- （暂无）\n\n'
            '## 未兑现钩子\n- （暂无）\n',
        )
        expect_failure(
            [sys.executable, str(landing_script), 'writing', '--project-dir', str(short_project), '--chapter', '1', '--input-file', str(short_output)],
            contains=['中文字数不足'],
        )

        scenes_gate_project = Path(args.project_dir).resolve() / '门禁测试'
        scenes_gate_project.mkdir(parents=True, exist_ok=True)
        expect_success([sys.executable, str(init_script), '--project-dir', str(scenes_gate_project), '--yes'])
        gate_xushikj_dir = scenes_gate_project / '.xushikj'
        (gate_xushikj_dir / 'outline').mkdir(parents=True, exist_ok=True)
        write_text_utf8(gate_xushikj_dir / 'outline' / 'volume_1_one_page.md', '第一卷目标：检查 scenes 门禁\n')
        gate_kb = gate_xushikj_dir / 'knowledge_base.json'
        write_text_utf8(
            gate_kb,
            json.dumps(
                {
                    'project': {},
                    'characters': [],
                    'relationships': [],
                    'world_rules': [],
                    'current_volume': {},
                    'open_loops': [],
                },
                ensure_ascii=False,
                indent=2,
            ) + '\n',
        )
        expect_failure(
            [sys.executable, str(validate_script), '--project-dir', str(scenes_gate_project), '--for-step', '8', '--chapter', '1'],
            contains=['进入 Lite 主流程前必须先确认 reply_length', '进入 Lite 主流程前必须先确认 target_platform'],
        )

        standalone_dir = Path(args.project_dir).resolve() / '独立润色'
        standalone_dir.mkdir(parents=True, exist_ok=True)
        standalone_chapter = standalone_dir / 'chapter_独立.md'
        write_text_utf8(standalone_chapter, '这是独立润色测试正文。\n')
        expect_success(
            [
                sys.executable,
                str(assemble_script),
                '--project-dir',
                str(standalone_dir),
                '--step',
                'humanizer',
                '--chapter-file',
                str(standalone_chapter),
            ],
            contains=['出版前润色编辑', '这是独立润色测试正文。'],
            forbid_replacement_char=True,
        )
        humanizer_output = standalone_dir / 'humanizer_output.md'
        write_text_utf8(
            humanizer_output,
            '这是独立润色测试正文。\n\n## 修改说明\n- 调整句式节奏。\n',
        )
        expect_success(
            [
                sys.executable,
                str(landing_script),
                'humanizer',
                '--project-dir',
                str(standalone_dir),
                '--chapter-file',
                str(standalone_chapter),
                '--input-file',
                str(humanizer_output),
            ],
            contains=['已写入润色稿', '已写入修改说明'],
            forbid_replacement_char=True,
        )
        expect_success(
            [
                sys.executable,
                str(validate_script),
                '--project-dir',
                str(standalone_dir),
                '--for-step',
                'humanizer',
                '--chapter-file',
                str(standalone_chapter),
            ],
            contains=['humanizer_chapter='],
            forbid_replacement_char=True,
        )

        slice_project = Path(args.project_dir).resolve() / '切片测试'
        slice_project.mkdir(parents=True, exist_ok=True)
        expect_success([sys.executable, str(init_script), '--project-dir', str(slice_project), '--yes'], contains=['[init] Lite project ready'])
        novel_path = slice_project / 'novel.txt'
        write_text_utf8(
            novel_path,
            '第1章\n'
            '系统叮的一声响起，少年开始修炼，随后一路追击敌人，最终揭开秘密。\n',
        )
        expect_success(
            [
                sys.executable,
                str(slice_script),
                '--input',
                str(novel_path),
                '--author',
                'regression_author',
                '--title',
                '回归测试小说',
                '--project-dir',
                str(slice_project),
            ],
            contains=['已生成场景覆盖基线'],
            forbid_replacement_char=True,
        )
        short_snippet = slice_project / 'snippet_short.md'
        write_text_utf8(short_snippet, '系统叮的一声响起。')
        expect_failure(
            [
                sys.executable,
                str(slice_script),
                'write-snippet',
                '--project-dir',
                str(slice_project),
                '--scene-type',
                'system',
                '--content-file',
                str(short_snippet),
            ],
            contains=['切片字数校验失败'],
        )
    except AssertionError as exc:
        failures.append(str(exc))

    if failures:
        print('[regression] FAILED')
        for failure in failures:
            print(failure)
        return 1

    print('[regression] PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
