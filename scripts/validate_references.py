#!/usr/bin/env python3
"""
Validate active Lite references.
"""

from __future__ import annotations

import re
from pathlib import Path

from assemble_prompt import TEMPLATES

SKILL_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_MODULES = {
    "benchmark-lite",
    "planning",
    "knowledge-base",
    "scenes",
    "writing",
    "humanizer",
}


def _extract_version(text: str) -> str | None:
    match = re.search(r"version:\s*([\d.]+)", text)
    return match.group(1) if match else None


def validate_all() -> bool:
    issues: list[str] = []

    modules_root = SKILL_ROOT / "modules"
    module_names = {path.name for path in modules_root.iterdir() if path.is_dir()}
    missing = EXPECTED_MODULES - module_names
    extra = {name for name in module_names if name not in EXPECTED_MODULES}
    if missing:
        issues.append(f"缺少 Lite 模块: {sorted(missing)}")
    if extra:
        issues.append(f"存在未纳入 Lite 主架构的模块目录: {sorted(extra)}")

    root_version = _extract_version((SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8"))
    if not root_version:
        issues.append("根 SKILL.md 缺少 version")

    for module_name in sorted(EXPECTED_MODULES & module_names):
        skill_path = modules_root / module_name / "SKILL.md"
        prompt_path = modules_root / module_name / "prompt.md"
        if not skill_path.exists():
            issues.append(f"模块缺少 SKILL.md: {module_name}")
            continue
        if not prompt_path.exists():
            issues.append(f"模块缺少 prompt.md: {module_name}")
        version = _extract_version(skill_path.read_text(encoding="utf-8"))
        if version != root_version:
            issues.append(f"版本不一致: {module_name}={version}, root={root_version}")

    required_templates = sorted(set(TEMPLATES.values()))
    prompt_root = SKILL_ROOT / "templates" / "prompts"
    for name in required_templates:
        if not (prompt_root / name).exists():
            issues.append(f"缺少 Prompt 模板: templates/prompts/{name}")

    required_configs = [
        "workflow.yaml",
        "meta_rules.yaml",
        "writing_rules.yaml",
        "style_rules.yaml",
        "benchmark_lite.yaml",
    ]
    config_root = SKILL_ROOT / "config"
    for name in required_configs:
        if not (config_root / name).exists():
            issues.append(f"缺少配置文件: config/{name}")

    print("=" * 60)
    print("Lite references validation")
    print("=" * 60)
    if issues:
        for issue in issues:
            print(f"[ERROR] {issue}")
        return False
    print("[OK] Lite 模块、模板、配置均已就位")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if validate_all() else 1)
