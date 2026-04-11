#!/usr/bin/env python3
"""
Validate active Lite references.
"""

from __future__ import annotations

import re
from pathlib import Path

from assemble_prompt import TEMPLATES
from encoding_utils import read_text_utf8, reconfigure_stdio_utf8

SKILL_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_MODULES = {
    "benchmark-lite",
    "planning",
    "knowledge-base",
    "scenes",
    "writing",
    "humanizer",
}
EXPECTED_PROMPT_TEMPLATES = {
    "step_0_benchmark_lite.md",
    "step_4_one_page.md",
    "step_7_kb.md",
    "step_8_scene_card.md",
    "step_10_writing.md",
    "step_humanizer.md",
    "step_project_card.md",
}
EXPECTED_CONFIGS = {
    "benchmark_lite.yaml",
    "human_touch_rules.yaml",
    "meta_rules.yaml",
    "style_rules.yaml",
    "workflow.yaml",
    "writing_rules.yaml",
}
EXPECTED_SCRIPTS = {
    "analyze_dna.py",
    "assemble_prompt.py",
    "chinese_char_count.py",
    "encoding_utils.py",
    "init.py",
    "kb_slicer.py",
    "regression_workflow_guards.py",
    "slice_library.py",
    "update_skill_metadata.py",
    "validate_references.py",
    "validate_state.py",
}
EXPECTED_ROLE_HEADINGS = {
    "step_0_benchmark_lite.md": "## 模块身份",
    "step_project_card.md": "## 模块身份",
    "step_4_one_page.md": "## 模块身份",
    "step_7_kb.md": "## 模块身份",
    "step_8_scene_card.md": "## 模块身份",
    "step_10_writing.md": "## 模块身份",
    "step_humanizer.md": "## 模块身份",
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

    root_skill_text = read_text_utf8(SKILL_ROOT / "SKILL.md", "")
    root_version = _extract_version(root_skill_text)
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
        version = _extract_version(read_text_utf8(skill_path, ""))
        if version != root_version:
            issues.append(f"版本不一致: {module_name}={version}, root={root_version}")

    required_templates = sorted(set(TEMPLATES.values()))
    prompt_root = SKILL_ROOT / "templates" / "prompts"
    for name in required_templates:
        if not (prompt_root / name).exists():
            issues.append(f"缺少 Prompt 模板: templates/prompts/{name}")
    for name, heading in EXPECTED_ROLE_HEADINGS.items():
        template_path = prompt_root / name
        if template_path.exists():
            template_text = read_text_utf8(template_path, "")
            if heading not in template_text:
                issues.append(f"Prompt 模板缺少角色定位结构: templates/prompts/{name}")
    active_templates = {path.name for path in prompt_root.iterdir() if path.is_file()}
    extra_templates = active_templates - EXPECTED_PROMPT_TEMPLATES
    if extra_templates:
        issues.append(f"templates/prompts 存在未清理旧模板: {sorted(extra_templates)}")

    config_root = SKILL_ROOT / "config"
    for name in sorted(EXPECTED_CONFIGS - {"human_touch_rules.yaml"}):
        if not (config_root / name).exists():
            issues.append(f"缺少配置文件: config/{name}")
    active_configs = {path.name for path in config_root.iterdir() if path.is_file()}
    extra_configs = active_configs - EXPECTED_CONFIGS
    if extra_configs:
        issues.append(f"config/ 存在未清理旧配置: {sorted(extra_configs)}")

    scripts_root = SKILL_ROOT / "scripts"
    active_scripts = {path.name for path in scripts_root.iterdir() if path.is_file()}
    extra_scripts = active_scripts - EXPECTED_SCRIPTS
    if extra_scripts:
        issues.append(f"scripts/ 存在未清理旧脚本: {sorted(extra_scripts)}")

    root_prompt_text = read_text_utf8(SKILL_ROOT / "prompt.md", "")
    if "benchmark-lite、planning、knowledge-base、scenes、writing、humanizer" not in root_prompt_text:
        issues.append("prompt.md 路由表未保持 Lite active 模块口径")
    if "在进入 planning / scenes / writing 前" not in root_prompt_text:
        issues.append("prompt.md 缺少 scenes 前置门禁口径")
    if "humanizer 是唯一允许脱离 `.xushikj/` 单独使用的模块" not in root_prompt_text:
        issues.append("prompt.md 缺少 humanizer 独立使用口径")

    if "在进入 planning / scenes / writing 前" not in root_skill_text:
        issues.append("SKILL.md 缺少 scenes 前置门禁口径")
    if "除 humanizer 外，所有模块都以 `.xushikj/` 为唯一运行时目录" not in root_skill_text:
        issues.append("SKILL.md 缺少 humanizer 独立运行口径")

    readme_text = read_text_utf8(SKILL_ROOT / "README.md", "")
    if "benchmark-lite" not in readme_text:
        issues.append("README.md 缺少 benchmark-lite active 命名")

    quickstart_text = read_text_utf8(SKILL_ROOT / "QUICKSTART.md", "")
    if "--step 8 --chapter 1" not in quickstart_text:
        issues.append("QUICKSTART.md 缺少 scenes 组装示例")
    if "--step humanizer --chapter-file" not in quickstart_text:
        issues.append("QUICKSTART.md 缺少 humanizer 独立示例")

    validate_state_text = read_text_utf8(scripts_root / "validate_state.py", "")
    if '"humanizer": ["chapter_file"]' not in validate_state_text:
        issues.append("validate_state.py 的 humanizer 门禁仍未独立")

    metadata_sync_text = read_text_utf8(scripts_root / "update_skill_metadata.py", "")
    if '"modules/benchmark":' in metadata_sync_text or '"modules/interactive":' in metadata_sync_text:
        issues.append("update_skill_metadata.py 仍残留旧模块命名")

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
    reconfigure_stdio_utf8()
    raise SystemExit(0 if validate_all() else 1)
