#!/usr/bin/env python3
"""
Lite workflow smoke regression.
"""

from __future__ import annotations

import argparse
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

    project_dir = Path(args.project_dir).resolve() / '中文项目'
    project_dir.mkdir(parents=True, exist_ok=True)
    expect_success(
        [sys.executable, str(init_script), '--project-dir', str(project_dir), '--yes', '--reply-length', '50'],
        contains=['[init] Lite project ready'],
        forbid_replacement_char=True,
    )

    xushikj_dir = project_dir / '.xushikj'
    benchmark_dir = xushikj_dir / 'benchmark'
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    worldbuilding_dir = xushikj_dir / 'worldbuilding'
    worldbuilding_dir.mkdir(parents=True, exist_ok=True)
    outline_dir = xushikj_dir / 'chapter_outlines'
    outline_dir.mkdir(parents=True, exist_ok=True)

    write_text_utf8(
        benchmark_dir / 'style_notes.md',
        '# 文风特征指南\n\n'
        '## 词汇偏好\n- 多用短促口语。\n\n'
        '## 句式节奏\n- 长短句交替。\n\n'
        '## 标点习惯\n- 逗号和破折号较多。\n\n'
        '## 情感与基调\n- 冷静克制。\n\n'
        '## 修辞与细节偏好\n- 细看动作。\n\n'
        '## AI 套话黑名单 / 禁用表达\n- 总而言之\n\n'
        '## 小步续写约束\n- 先稳住语感，再扩写。\n',
    )
    write_text_utf8(
        worldbuilding_dir / 'worldview.md',
        '# 世界观与力量体系设定\n\n'
        '## 世界观底层规则\n- 城市被旧神阴影覆盖。\n\n'
        '## 力量体系 / 修炼体系\n- 借火种修行。\n\n'
        '## 代价与边界\n- 每次借火都会灼伤记忆。\n\n'
        '## 主角起点与成长逻辑\n- 主角从残火学徒开始。\n\n'
        '## 世界冲突源\n- 旧神复苏。\n\n'
        '## 长期硬设定\n- 火种不可凭空再生。\n',
    )
    write_text_utf8(
        outline_dir / f'chapter_{args.chapter}.md',
        '# 第1章章纲\n\n'
        '## 本章目标\n- 主角第一次接触禁火。\n\n'
        '## 核心冲突\n- 是否冒险点燃禁火。\n\n'
        '## 关键转折\n- 他发现禁火会吞掉名字。\n\n'
        '## 情绪推进\n- 从犹豫到决断。\n\n'
        '## 关键场面\n- 夜里独自试火。\n\n'
        '## 结尾钩子\n- 门外有人叫出了他失去的名字。\n\n'
        '## 本章必须写出的信息\n- 禁火代价。\n\n'
        '## 本章必须避免的偏移\n- 不要提前引出终局真相。\n',
    )

    failures: list[str] = []
    try:
        for cmd, contains in [
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', 'benchmark-lite'], ['文风克隆分析师', 'AI 套话黑名单']),
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', 'worldbuilding'], ['设定讨论搭档', '世界观与力量体系设定']),
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', 'chapter-outline', '--chapter', str(args.chapter)], ['章节骨架讨论搭档', '本章目标']),
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', '10', '--chapter', str(args.chapter)], ['文风克隆续写主笔', '文风特征指南', '本章最低中文字符数：50']),
        ]:
            expect_success(cmd, contains=contains, forbid_replacement_char=True)

        missing_benchmark_project = Path(args.project_dir).resolve() / '缺对标'
        missing_benchmark_project.mkdir(parents=True, exist_ok=True)
        expect_success([sys.executable, str(init_script), '--project-dir', str(missing_benchmark_project), '--yes', '--reply-length', '50'])
        gate_x = missing_benchmark_project / '.xushikj'
        (gate_x / 'worldbuilding').mkdir(parents=True, exist_ok=True)
        (gate_x / 'chapter_outlines').mkdir(parents=True, exist_ok=True)
        write_text_utf8(gate_x / 'worldbuilding' / 'worldview.md', '# 世界观与力量体系设定\n\n## 世界观底层规则\n- 已写好。\n')
        write_text_utf8(gate_x / 'chapter_outlines' / 'chapter_1.md', '# 第1章章纲\n\n## 本章目标\n- 已写好。\n')
        expect_failure(
            [sys.executable, str(validate_script), '--project-dir', str(missing_benchmark_project), '--for-step', '10', '--chapter', '1'],
            contains=['必须先完成 benchmark-lite'],
        )

        writing_output = xushikj_dir / 'drafts' / 'chapter_1_output.md'
        body = '测试正文' * 1200
        write_text_utf8(
            writing_output,
            body + '\n\n'
            '## 本章摘要\n- 主角点燃禁火并听见失去的名字。\n\n'
            '## 状态变化\n- 主角正式背上禁火代价。\n\n'
            '## 新增设定\n- 禁火会吞掉名字。\n\n'
            '## 未兑现钩子\n- 门外来者是谁。\n',
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
        expect_success(
            [sys.executable, str(workflow_script), 'confirm', '--project-dir', str(project_dir)],
            contains=['current_step=humanizer', 'pending_user_confirmation=false'],
            forbid_replacement_char=True,
        )

        short_project = Path(args.project_dir).resolve() / '短章测试'
        short_project.mkdir(parents=True, exist_ok=True)
        expect_success([sys.executable, str(init_script), '--project-dir', str(short_project), '--yes', '--reply-length', '50'], contains=['[init] Lite project ready'])
        short_x = short_project / '.xushikj'
        short_output = short_x / 'drafts' / 'chapter_1_output.md'
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

        standalone_dir = Path(args.project_dir).resolve() / '独立润色'
        standalone_dir.mkdir(parents=True, exist_ok=True)
        standalone_chapter = standalone_dir / 'chapter_独立.md'
        write_text_utf8(standalone_chapter, '这是独立润色测试正文。\n')
        standalone_style_dir = standalone_dir / '.xushikj' / 'config' / 'style_modules'
        standalone_style_dir.mkdir(parents=True, exist_ok=True)
        write_text_utf8(
            standalone_style_dir / 'dna_human_test.yaml',
            'do:\n  - 保留短促停顿\n  - 保留角色口头禅\navoid:\n  - 把文本洗成统一播音腔\n',
        )
        expect_success(
            [sys.executable, str(assemble_script), '--project-dir', str(standalone_dir), '--step', 'humanizer', '--chapter-file', str(standalone_chapter)],
            contains=['出版前润色编辑', 'R1-EXEMPT', 'source=dna_human:dna_human_test.yaml'],
            forbid_replacement_char=True,
        )
        humanizer_output = standalone_dir / 'humanizer_output.md'
        write_text_utf8(
            humanizer_output,
            '这是独立润色测试正文。\n\n'
            '## 修改说明\n- [R2] 合并孤立短句。\n- [R-DNA] 保留了角色短促停顿。\n\n'
            '## 豁免记录\n- R1-EXEMPT：保留一处强语义反转。\n\n'
            '## R-DNA校验\n- 已保护的 DNA 特征：短促停顿、角色口头禅。\n',
        )
        expect_success(
            [sys.executable, str(landing_script), 'humanizer', '--project-dir', str(standalone_dir), '--chapter-file', str(standalone_chapter), '--input-file', str(humanizer_output)],
            contains=['已写入润色稿', '已写入修改说明'],
            forbid_replacement_char=True,
        )
        expect_success(
            [sys.executable, str(validate_script), '--project-dir', str(standalone_dir), '--for-step', 'humanizer', '--chapter-file', str(standalone_chapter)],
            contains=['humanizer_chapter='],
            forbid_replacement_char=True,
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
