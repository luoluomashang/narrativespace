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
    'benchmark-lite',
    'worldbuilding',
    'characters',
    'chapter-outline',
    'writing',
    'humanizer',
}
EXPECTED_PROMPT_TEMPLATES = {
    'step_0_benchmark_lite.md',
    'step_worldbuilding.md',
    'step_characters.md',
    'step_chapter_outline.md',
    'step_10_writing.md',
    'step_humanizer.md',
}
EXPECTED_CONFIGS = {
    'benchmark_lite.yaml',
    'human_touch_rules.yaml',
    'humanizer_rules.yaml',
    'meta_rules.yaml',
    'style_rules.yaml',
    'workflow.yaml',
    'writing_rules.yaml',
}
EXPECTED_SCRIPTS = {
    'analyze_dna.py',
    'assemble_prompt.py',
    'chinese_char_count.py',
    'encoding_utils.py',
    'init.py',
    'kb_slicer.py',
    'landing.py',
    'regression_workflow_guards.py',
    'slice_library.py',
    'update_skill_metadata.py',
    'validate_references.py',
    'validate_state.py',
    'workflow_state.py',
}
EXPECTED_ROLE_HEADINGS = {
    'step_0_benchmark_lite.md': '## 模块身份',
    'step_worldbuilding.md': '## 模块身份',
    'step_characters.md': '## 模块身份',
    'step_chapter_outline.md': '## 模块身份',
    'step_10_writing.md': '## 模块身份',
    'step_humanizer.md': '## 模块身份',
}


def _extract_version(text: str) -> str | None:
    match = re.search(r'version:\s*([\d.]+)', text)
    return match.group(1) if match else None


def validate_all() -> bool:
    issues: list[str] = []

    modules_root = SKILL_ROOT / 'modules'
    module_names = {path.name for path in modules_root.iterdir() if path.is_dir()}
    missing = EXPECTED_MODULES - module_names
    extra = {name for name in module_names if name not in EXPECTED_MODULES}
    if missing:
        issues.append(f'缺少 Lite 模块: {sorted(missing)}')
    if extra:
        issues.append(f'存在未纳入 Lite 主架构的模块目录: {sorted(extra)}')

    root_skill_text = read_text_utf8(SKILL_ROOT / 'SKILL.md', '')
    root_version = _extract_version(root_skill_text)
    if not root_version:
        issues.append('根 SKILL.md 缺少 version')

    for module_name in sorted(EXPECTED_MODULES & module_names):
        skill_path = modules_root / module_name / 'SKILL.md'
        prompt_path = modules_root / module_name / 'prompt.md'
        if not skill_path.exists():
            issues.append(f'模块缺少 SKILL.md: {module_name}')
            continue
        if not prompt_path.exists():
            issues.append(f'模块缺少 prompt.md: {module_name}')
        version = _extract_version(read_text_utf8(skill_path, ''))
        if version != root_version:
            issues.append(f'版本不一致: {module_name}={version}, root={root_version}')

    required_templates = sorted(set(TEMPLATES.values()))
    prompt_root = SKILL_ROOT / 'templates' / 'prompts'
    for name in required_templates:
        if not (prompt_root / name).exists():
            issues.append(f'缺少 Prompt 模板: templates/prompts/{name}')
    for name, heading in EXPECTED_ROLE_HEADINGS.items():
        template_path = prompt_root / name
        if template_path.exists():
            template_text = read_text_utf8(template_path, '')
            if heading not in template_text:
                issues.append(f'Prompt 模板缺少角色定位结构: templates/prompts/{name}')
    active_templates = {path.name for path in prompt_root.iterdir() if path.is_file()}
    extra_templates = active_templates - EXPECTED_PROMPT_TEMPLATES
    if extra_templates:
        issues.append(f'templates/prompts 存在未清理旧模板: {sorted(extra_templates)}')

    config_root = SKILL_ROOT / 'config'
    for name in sorted(EXPECTED_CONFIGS - {'human_touch_rules.yaml'}):
        if not (config_root / name).exists():
            issues.append(f'缺少配置文件: config/{name}')
    active_configs = {path.name for path in config_root.iterdir() if path.is_file()}
    extra_configs = active_configs - EXPECTED_CONFIGS
    if extra_configs:
        issues.append(f'config/ 存在未清理旧配置: {sorted(extra_configs)}')

    scripts_root = SKILL_ROOT / 'scripts'
    active_scripts = {path.name for path in scripts_root.iterdir() if path.is_file()}
    extra_scripts = active_scripts - EXPECTED_SCRIPTS
    if extra_scripts:
        issues.append(f'scripts/ 存在未清理旧脚本: {sorted(extra_scripts)}')

    root_prompt_text = read_text_utf8(SKILL_ROOT / 'prompt.md', '')
    if 'benchmark-lite、worldbuilding、characters、chapter-outline、writing、humanizer' not in root_prompt_text:
        issues.append('prompt.md 路由表未保持 Lite active 模块口径')
    if 'benchmark-lite 是强制前置' not in root_prompt_text:
        issues.append('prompt.md 缺少 benchmark 强制前置口径')
    if 'characters 未完成时' not in root_prompt_text:
        issues.append('prompt.md 缺少人物卡门禁口径')
    if 'humanizer 是唯一允许脱离 `.xushikj/` 单独使用的模块' not in root_prompt_text:
        issues.append('prompt.md 缺少 humanizer 独立使用口径')
    if 'python scripts/landing.py writing' not in root_prompt_text:
        issues.append('prompt.md 缺少写作落盘入口口径')
    if 'python scripts/workflow_state.py confirm' not in root_prompt_text:
        issues.append('prompt.md 缺少流程确认入口口径')
    if 'main 分支' not in root_prompt_text:
        issues.append('prompt.md 缺少 humanizer 对齐 main 口径')

    if 'benchmark-lite 完成前，不得进入 worldbuilding / characters / chapter-outline / writing' not in root_skill_text:
        issues.append('SKILL.md 缺少 benchmark 强制前置口径')
    if 'characters 完成前，不得进入 chapter-outline / writing' not in root_skill_text:
        issues.append('SKILL.md 缺少人物卡门禁口径')
    if '只校验 `reply_length` 对应的最小中文字符数' not in root_skill_text:
        issues.append('SKILL.md 缺少仅保留下限的字数规则')
    if 'main` 分支后处理模块保持一致' not in root_skill_text:
        issues.append('SKILL.md 缺少 humanizer 对齐 main 口径')

    readme_text = read_text_utf8(SKILL_ROOT / 'README.md', '')
    if 'benchmark-lite' not in readme_text or 'characters' not in readme_text or 'chapter-outline' not in readme_text:
        issues.append('README.md 缺少新 Lite 主流程命名')
    if '完整的 style_notes 契约' not in readme_text:
        issues.append('README.md 缺少 benchmark 完整契约说明')

    quickstart_text = read_text_utf8(SKILL_ROOT / 'QUICKSTART.md', '')
    if '--step worldbuilding' not in quickstart_text:
        issues.append('QUICKSTART.md 缺少 worldbuilding 组装示例')
    if '--step characters' not in quickstart_text:
        issues.append('QUICKSTART.md 缺少 characters 组装示例')
    if '--step chapter-outline --chapter 1' not in quickstart_text:
        issues.append('QUICKSTART.md 缺少 chapter-outline 组装示例')
    if '--step humanizer --chapter-file' not in quickstart_text:
        issues.append('QUICKSTART.md 缺少 humanizer 独立示例')
    if '修改清单' not in quickstart_text:
        issues.append('QUICKSTART.md 缺少 humanizer 新输出契约口径')

    validate_state_text = read_text_utf8(scripts_root / 'validate_state.py', '')
    if 'characters' not in validate_state_text:
        issues.append('validate_state.py 缺少人物卡依赖门禁')
    if 'target_platform' in validate_state_text.split('STEP_DEPENDENCIES', 1)[-1]:
        issues.append('validate_state.py 门禁未切换到仅保留 reply_length')

    landing_text = read_text_utf8(scripts_root / 'landing.py', '')
    if 'knowledge_base' in landing_text or 'chapter_notes' in landing_text:
        issues.append('landing.py 仍残留旧 KB 回写逻辑')
    if 'maximum=' in landing_text:
        issues.append('landing.py 仍残留字数上限校验')
    if '修改清单' not in landing_text:
        issues.append('landing.py 未兼容 main 风格的 humanizer 输出')

    workflow_text = read_text_utf8(scripts_root / 'workflow_state.py', '')
    if 'characters' not in workflow_text or 'chapter-outline' not in workflow_text:
        issues.append('workflow_state.py 未切换到含人物卡的新步骤链路')

    benchmark_template_text = read_text_utf8(prompt_root / 'step_0_benchmark_lite.md', '')
    if '多段原文采样' not in benchmark_template_text or '前段 / 中段 / 后段' not in benchmark_template_text:
        issues.append('step_0_benchmark_lite.md 未声明多段采样规则')

    humanizer_template_text = read_text_utf8(prompt_root / 'step_humanizer.md', '')
    if '无用细节清除' not in humanizer_template_text or '修改清单' not in humanizer_template_text:
        issues.append('step_humanizer.md 未对齐 main 后处理契约')

    metadata_sync_text = read_text_utf8(scripts_root / 'update_skill_metadata.py', '')
    if 'modules/planning' in metadata_sync_text or 'modules/scenes' in metadata_sync_text or 'modules/knowledge-base' in metadata_sync_text:
        issues.append('update_skill_metadata.py 仍残留旧模块命名')
    if 'modules/characters' not in metadata_sync_text:
        issues.append('update_skill_metadata.py 缺少 characters 模块')

    print('=' * 60)
    print('Lite references validation')
    print('=' * 60)
    if issues:
        for issue in issues:
            print(f'[ERROR] {issue}')
        return False
    print('[OK] Lite 模块、模板、配置均已就位')
    return True


if __name__ == '__main__':
    reconfigure_stdio_utf8()
    raise SystemExit(0 if validate_all() else 1)
