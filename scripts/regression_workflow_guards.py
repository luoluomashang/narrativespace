#!/usr/bin/env python3
"""
Lite workflow smoke regression.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from hashlib import sha256
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
    characters_dir = xushikj_dir / 'outline' / 'characters'
    characters_dir.mkdir(parents=True, exist_ok=True)
    outline_dir = xushikj_dir / 'chapter_outlines'
    outline_dir.mkdir(parents=True, exist_ok=True)

    source_text = ('开头样本。' * 120) + ('中段样本。' * 120) + ('结尾样本。' * 120)
    source_file = project_dir / 'benchmark_source.txt'
    write_text_utf8(source_file, source_text)
    registry = {
        'source_file': str(source_file.resolve()),
        'source_title': '测试原文',
        'source_sha256': sha256(source_file.read_bytes()).hexdigest(),
    }
    write_text_utf8(benchmark_dir / 'source_registry.json', json.dumps(registry, ensure_ascii=False, indent=2) + '\n')

    write_text_utf8(
        benchmark_dir / 'style_notes.md',
        '# 文风特征指南 / 对标风格分析报告\n\n'
        '## 一、文风特征摘要\n\n'
        '### 1.1 语言风格参数\n- 词汇偏好：多用短促口语。\n- 句式特征：长短句交替。\n- 叙述视角：近距离第三人称。\n- 口语化程度：偏高。\n- 标点习惯：逗号和破折号较多。\n- 段落结构：短段推进。\n- 情感基调：冷静克制。\n- 修辞与细节偏好：细看动作。\n\n'
        '### 1.2 与限制列表的交叉比对\n- AI 套话黑名单 / 禁用表达：总而言之。\n\n'
        '## 七、小步续写约束\n- 先稳住语感，再扩写。\n',
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
        characters_dir / 'char_001.md',
        '# 林烬\n\n'
        '- 角色类型：主角\n'
        '- 价值观：先活下来再谈体面\n'
        '- 抱负：掌控禁火\n'
        '- 当前目标：查清失名真相\n'
        '- 内在矛盾：求生与自毁并存\n'
        '- 行为底层逻辑：绝不再被动挨打\n'
        '- 压力反应基线：先硬撑，再突然爆发\n'
        '- 欲望 / 恐惧 / 羞耻 / 债务：想活 / 怕失名 / 羞于软弱 / 欠师父一条命\n',
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
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', 'benchmark-lite'], ['文风克隆分析师', '前段样本', '中段样本', '后段样本']),
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', 'worldbuilding'], ['设定讨论搭档', '世界观与力量体系设定']),
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', 'characters'], ['人物设定讨论搭档', '每张人物卡最小字段集']),
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', 'chapter-outline', '--chapter', str(args.chapter)], ['章节骨架讨论搭档', '相关人物卡片']),
            ([sys.executable, str(assemble_script), '--project-dir', str(project_dir), '--step', '10', '--chapter', str(args.chapter)], ['文风克隆续写主笔', '相关人物卡片', '本章最低中文字符数：50']),
        ]:
            expect_success(cmd, contains=contains, forbid_replacement_char=True)

        missing_character_project = Path(args.project_dir).resolve() / '缺人物卡'
        missing_character_project.mkdir(parents=True, exist_ok=True)
        expect_success([sys.executable, str(init_script), '--project-dir', str(missing_character_project), '--yes', '--reply-length', '50'])
        gate_x = missing_character_project / '.xushikj'
        (gate_x / 'benchmark').mkdir(parents=True, exist_ok=True)
        (gate_x / 'worldbuilding').mkdir(parents=True, exist_ok=True)
        (gate_x / 'chapter_outlines').mkdir(parents=True, exist_ok=True)
        write_text_utf8(gate_x / 'benchmark' / 'style_notes.md', '# 文风特征指南 / 对标风格分析报告\n\n## 一、文风特征摘要\n- 已写好。\n')
        write_text_utf8(gate_x / 'worldbuilding' / 'worldview.md', '# 世界观与力量体系设定\n\n## 世界观底层规则\n- 已写好。\n')
        write_text_utf8(gate_x / 'chapter_outlines' / 'chapter_1.md', '# 第1章章纲\n\n## 本章目标\n- 已写好。\n')
        expect_failure(
            [sys.executable, str(validate_script), '--project-dir', str(missing_character_project), '--for-step', '10', '--chapter', '1'],
            contains=['必须先完成人物卡片设定'],
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
            contains=['小说文本后处理专家', '无用细节清除', 'DNA 保护约束'],
            forbid_replacement_char=True,
        )
        humanizer_output = standalone_dir / 'humanizer_output.md'
        write_text_utf8(
            humanizer_output,
            '这是独立润色测试正文。\n\n'
            '## 修改清单\n\n'
            '| # | 规则 | 原文 | 修改后 | 原因 |\n'
            '|---|------|------|--------|------|\n'
            '| 1 | R3 | 与此同时，她转过身 | 她转过身 | AI衔接词删除 |\n',
        )
        expect_success(
            [sys.executable, str(landing_script), 'humanizer', '--project-dir', str(standalone_dir), '--chapter-file', str(standalone_chapter), '--input-file', str(humanizer_output)],
            contains=['已写入润色稿', '已写入修改清单'],
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
