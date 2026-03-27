#!/usr/bin/env python3
"""
批量更新narrativeSpace-xushikj中所有modules/*/SKILL.md的parent字段
"""

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

for mod_path, parent_name in modules.items():
    skill_file = SKILL_ROOT / mod_path / "SKILL.md"
    
    if not skill_file.exists():
        print(f"⚠️  {skill_file} 不存在")
        continue
    
    content = skill_file.read_text(encoding="utf-8")
    
    # 替换parent字段
    # 如果已有parent字段，替换；如果没有，在第一个冒号后添加
    if "parent:" in content:
        # 替换现有parent
        content = re.sub(
            r'parent:\s*opencode-xushikj-chuangzuo|parent:\s*[^\n]*',
            f'parent: {parent_name}',
            content
        )
    else:
        # 在metadata部分添加parent字段
        content = re.sub(
            r'(metadata:\s*\n)',
            f'metadata:\n  parent: {parent_name}\n',
            content
        )
    
    skill_file.write_text(content, encoding="utf-8")
    print(f"✅ 更新 {mod_path}/SKILL.md")

print("\n✅ 所有SKILL.md更新完成！")
