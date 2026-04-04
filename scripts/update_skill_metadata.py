#!/usr/bin/env python3
"""
批量更新narrativeSpace-xushikj中所有modules/*/SKILL.md的parent字段
以及可选同步版本号（--sync-version）
"""

import argparse
import re
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent

modules = {
    "modules/benchmark": "narrativespace-xushikj",
    "modules/planning": "narrativespace-xushikj",
    "modules/knowledge-base": "narrativespace-xushikj",
    "modules/scenes": "narrativespace-xushikj",
    "modules/writing": "narrativespace-xushikj",
    "modules/interactive": "narrativespace-xushikj",
    "modules/humanizer": "narrativespace-xushikj"
}


def _read_root_version() -> str:
    """从根 SKILL.md 读取 version 字段。"""
    root_skill = SKILL_ROOT / "SKILL.md"
    if root_skill.exists():
        content = root_skill.read_text(encoding="utf-8")
        m = re.search(r"version:\s*([\d.]+)", content)
        if m:
            return m.group(1)
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="批量更新子模块 SKILL.md 元数据")
    parser.add_argument(
        "--sync-version",
        metavar="VERSION",
        nargs="?",
        const="",          # 无值时从根 SKILL.md 自动读取
        default=None,      # 未指定时不同步版本
        help="同步版本号到所有子模块 SKILL.md（不填则从根 SKILL.md 自动读取）",
    )
    args = parser.parse_args()

    sync_version: str | None = None
    if args.sync_version is not None:
        sync_version = args.sync_version or _read_root_version()
        if not sync_version:
            print("⚠️  无法确定目标版本号（--sync-version 未提供且根 SKILL.md 未找到 version 字段）")
            return

    for mod_path, parent_name in modules.items():
        skill_file = SKILL_ROOT / mod_path / "SKILL.md"

        if not skill_file.exists():
            print(f"⚠️  {skill_file} 不存在")
            continue

        content = skill_file.read_text(encoding="utf-8")

        # 替换 parent 字段
        if "parent:" in content:
            content = re.sub(
                r'parent:\s*opencode-xushikj-chuangzuo|parent:\s*[^\n]*',
                f'parent: {parent_name}',
                content
            )
        else:
            content = re.sub(
                r'(metadata:\s*\n)',
                f'metadata:\n  parent: {parent_name}\n',
                content
            )

        # 可选：同步版本号
        if sync_version:
            content = re.sub(r'version:\s*[\d.]+', f'version: {sync_version}', content)

        skill_file.write_text(content, encoding="utf-8")
        tag = f" + version → {sync_version}" if sync_version else ""
        print(f"✅ 更新 {mod_path}/SKILL.md（parent{tag}）")

    print("\n✅ 所有SKILL.md更新完成！")


if __name__ == "__main__":
    main()
