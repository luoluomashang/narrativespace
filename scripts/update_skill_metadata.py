#!/usr/bin/env python3
"""
批量更新 Lite active modules/*/SKILL.md 的 parent 字段，
以及可选同步版本号（--sync-version）。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from encoding_utils import read_text_utf8, reconfigure_stdio_utf8, write_text_utf8

SKILL_ROOT = Path(__file__).resolve().parent.parent

modules = {
    'modules/benchmark-lite': 'narrativespace-lite',
    'modules/worldbuilding': 'narrativespace-lite',
    'modules/chapter-outline': 'narrativespace-lite',
    'modules/writing': 'narrativespace-lite',
    'modules/humanizer': 'narrativespace-lite',
}


def _read_root_version() -> str:
    root_skill = SKILL_ROOT / 'SKILL.md'
    if root_skill.exists():
        content = read_text_utf8(root_skill, '')
        match = re.search(r'version:\s*([\d.]+)', content)
        if match:
            return match.group(1)
    return ''


def main() -> None:
    reconfigure_stdio_utf8()
    parser = argparse.ArgumentParser(description='批量更新子模块 SKILL.md 元数据')
    parser.add_argument(
        '--sync-version',
        metavar='VERSION',
        nargs='?',
        const='',
        default=None,
        help='同步版本号到所有子模块 SKILL.md（不填则从根 SKILL.md 自动读取）',
    )
    args = parser.parse_args()

    sync_version: str | None = None
    if args.sync_version is not None:
        sync_version = args.sync_version or _read_root_version()
        if not sync_version:
            print('⚠️  无法确定目标版本号（--sync-version 未提供且根 SKILL.md 未找到 version 字段）')
            return

    for mod_path, parent_name in modules.items():
        skill_file = SKILL_ROOT / mod_path / 'SKILL.md'
        if not skill_file.exists():
            print(f'⚠️  {skill_file} 不存在')
            continue
        content = read_text_utf8(skill_file, '')
        if 'parent:' in content:
            content = re.sub(r'parent:\s*opencode-xushikj-chuangzuo|parent:\s*[^\n]*', f'parent: {parent_name}', content)
        else:
            content = re.sub(r'(metadata:\s*\n)', f'metadata:\n  parent: {parent_name}\n', content)
        if sync_version:
            content = re.sub(r'version:\s*[\d.]+', f'version: {sync_version}', content)
        write_text_utf8(skill_file, content)
        tag = f' + version → {sync_version}' if sync_version else ''
        print(f'✅ 更新 {mod_path}/SKILL.md（parent{tag}）')

    print('\n✅ 所有SKILL.md更新完成！')


if __name__ == '__main__':
    main()
