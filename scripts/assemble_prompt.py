"""
Assemble Lite step prompts.
"""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from encoding_utils import read_json_utf8, read_text_utf8, reconfigure_stdio_utf8, write_text_utf8
from workflow_state import assert_step_allowed, ensure_workflow_state

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

SKILL_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = SKILL_ROOT / 'templates' / 'prompts'
CONFIG_DIR = SKILL_ROOT / 'config'
EMPTY_PLACEHOLDER = '（暂无）'
PLACEHOLDER = '（待填写）'
RULE_FILES = {
    '0': ['meta_rules.yaml', 'benchmark_lite.yaml'],
    'benchmark-lite': ['meta_rules.yaml', 'benchmark_lite.yaml'],
    'worldbuilding': ['meta_rules.yaml', 'workflow.yaml'],
    'characters': ['meta_rules.yaml', 'workflow.yaml'],
    'chapter-outline': ['meta_rules.yaml', 'workflow.yaml'],
    '10': ['meta_rules.yaml', 'writing_rules.yaml', 'style_rules.yaml'],
    'writing': ['meta_rules.yaml', 'writing_rules.yaml', 'style_rules.yaml'],
    'humanizer': ['meta_rules.yaml', 'style_rules.yaml', 'humanizer_rules.yaml'],
}
TEMPLATES = {
    '0': 'step_0_benchmark_lite.md',
    'benchmark-lite': 'step_0_benchmark_lite.md',
    'worldbuilding': 'step_worldbuilding.md',
    'characters': 'step_characters.md',
    'chapter-outline': 'step_chapter_outline.md',
    '10': 'step_10_writing.md',
    'writing': 'step_10_writing.md',
    'humanizer': 'step_humanizer.md',
}
STEP_PACKAGE_INFO = {
    'benchmark-lite': {
        'title': 'benchmark-lite Prompt 包',
        'objective': '组装完整对标分析 Prompt，供外部模型生成可直接约束后续步骤的 style_notes。',
        'expected_output_schema': [
            '一、文风特征摘要',
            '二、世界观构建模式',
            '三、情节设计模式',
            '四、角色设计模式',
            '五、内化风格参数（style_profile / confidence_notes）',
            '六、多段原文采样观察（前段 / 中段 / 后段）',
            '七、小步续写约束',
        ],
    },
    'worldbuilding': {
        'title': 'worldbuilding Prompt 包',
        'objective': '组装世界观与力量体系 Prompt，供外部模型产出可长期复用的设定文档。',
        'expected_output_schema': [
            '1. 世界观底层规则',
            '2. 力量体系 / 修炼体系',
            '3. 代价与边界',
            '4. 主角起点与成长逻辑',
            '5. 世界冲突源',
            '6. 长期硬设定',
        ],
    },
    'characters': {
        'title': 'characters Prompt 包',
        'objective': '组装人物卡片设定 Prompt，供外部模型按统一字段生成核心人物卡。',
        'expected_output_schema': [
            '每个主要人物单独成卡',
            '字段至少覆盖：名字、角色类型、价值观、抱负、当前目标、内在矛盾、行为底层逻辑、压力反应基线、欲望 / 恐惧 / 羞耻 / 债务',
        ],
    },
    'chapter-outline': {
        'title': 'chapter-outline Prompt 包',
        'objective': '组装当前章节骨架 Prompt，供外部模型生成可直接进入写作的章纲。',
        'expected_output_schema': [
            '1. 本章目标',
            '2. 核心冲突',
            '3. 关键转折',
            '4. 情绪推进',
            '5. 关键场面',
            '6. 结尾钩子',
            '7. 本章必须写出的信息',
            '8. 本章必须避免的偏移',
        ],
    },
    'writing': {
        'title': 'writing Prompt 包',
        'objective': '组装正文写作 Prompt，供外部模型输出正文与回填所需结构化区块。',
        'expected_output_schema': [
            '正文',
            '## 本章摘要',
            '## 状态变化',
            '## 新增设定',
            '## 未兑现钩子',
        ],
    },
    'humanizer': {
        'title': 'humanizer Prompt 包',
        'objective': '组装章节润色 Prompt，供外部模型按 main 对齐规则执行去 AI 痕迹处理。',
        'expected_output_schema': [
            '正文',
            '## 修改清单（推荐）',
            '兼容旧版：## 修改说明 / ## 豁免记录 / ## R-DNA校验',
        ],
    },
}


def _read_json(path: Path) -> dict[str, Any]:
    return read_json_utf8(path)


def _read_text(path: Path, default: str = EMPTY_PLACEHOLDER) -> str:
    return read_text_utf8(path, default, strip=True) or default


def _load_yaml_or_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    fallback = default or {}
    if not path.exists():
        return fallback
    raw = read_text_utf8(path, '', strip=True)
    if not raw:
        return fallback
    try:
        if YAML_AVAILABLE:
            payload = yaml.safe_load(raw)
        else:
            payload = json.loads(raw)
    except Exception:
        return fallback
    return payload if isinstance(payload, dict) else fallback


def _resolve_paths(project_dir: Path) -> tuple[Path, Path]:
    project_dir = project_dir.resolve()
    if project_dir.name == '.xushikj':
        return project_dir.parent, project_dir
    return project_dir, project_dir / '.xushikj'


def _load_state(xushikj_dir: Path) -> dict[str, Any]:
    state_path = xushikj_dir / 'state.json'
    if not state_path.exists():
        raise FileNotFoundError(f'Missing state.json: {state_path}')
    return ensure_workflow_state(_read_json(state_path))


def _load_rules(step: str) -> str:
    sections: list[str] = []
    for filename in RULE_FILES.get(step, ['meta_rules.yaml']):
        path = CONFIG_DIR / filename
        if path.exists():
            body = read_text_utf8(path, '', strip=True)
            sections.append(f'## {filename}\n{body}')
    return '\n\n'.join(sections) if sections else '（无额外规则）'


def _extract_constraint_lines(data: Any, keys: list[str], limit: int) -> list[str]:
    pool: list[dict[str, Any]] = []

    def _flatten(node: Any) -> None:
        if isinstance(node, dict):
            pool.append(node)
            for value in node.values():
                _flatten(value)
        elif isinstance(node, list):
            for item in node:
                _flatten(item)

    _flatten(data)
    lines: list[str] = []
    for item in pool:
        for key in keys:
            value = item.get(key)
            if isinstance(value, list):
                for raw in value:
                    text = str(raw).strip()
                    if text and text not in lines:
                        lines.append(text)
            elif isinstance(value, str):
                text = value.strip()
                if text and text not in lines:
                    lines.append(text)
            if len(lines) >= limit:
                return lines[:limit]
    return lines[:limit]


def _humanizer_dna_constraints(xushikj_dir: Path) -> str:
    style_modules_dir = xushikj_dir / 'config' / 'style_modules'
    if not style_modules_dir.exists():
        return '（当前项目未提供 dna_human_*.yaml / clone_*.yaml，可跳过 R-DNA 保护）'

    dna_files = sorted(style_modules_dir.glob('dna_human_*.yaml'))
    source_label = 'dna_human'
    if not dna_files:
        dna_files = sorted(style_modules_dir.glob('clone_*.yaml'))
        source_label = 'clone'
    if not dna_files:
        return '（当前项目未提供 dna_human_*.yaml / clone_*.yaml，可跳过 R-DNA 保护）'

    dna_path = dna_files[0]
    dna_payload = _load_yaml_or_json(dna_path, {})
    do_items = _extract_constraint_lines(dna_payload, ['do', 'do_list', 'dos', 'preferred', 'guidelines'], 8)
    dont_items = _extract_constraint_lines(dna_payload, ['dont', 'dont_list', 'donts', 'forbidden', 'avoid'], 8)
    lines = [f'- source={source_label}:{dna_path.name}']
    lines.extend(f'- DO: {item}' for item in do_items)
    lines.extend(f"- DON'T: {item}" for item in dont_items)
    return '\n'.join(lines) if len(lines) > 1 else f'- source={source_label}:{dna_path.name}'


def _recent_summaries(xushikj_dir: Path) -> str:
    return _read_text(xushikj_dir / 'summaries' / 'summary_index.md')


def _project_name(state: dict[str, Any], project_root: Path) -> str:
    name = str(state.get('project_name', '')).strip()
    return name or project_root.name


def _project_context(state: dict[str, Any]) -> str:
    parts = [
        '## 当前项目硬约束',
        f"- 每章最小中文字符数：{state.get('reply_length') or '（待确认）'}",
        f"- 目标平台（可选）：{state.get('target_platform') or '（未设置）'}",
        f"- 当前写作模式：{state.get('writing_mode') or 'style-clone'}",
    ]
    benchmark_state = state.get('benchmark_state', {})
    if isinstance(benchmark_state, dict) and benchmark_state.get('sample_scope'):
        parts.append(f"- 对标采样策略：{benchmark_state.get('sample_scope')}")
    return '\n'.join(parts)


def _ready_text(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8-sig', errors='replace').strip()
    return bool(text) and PLACEHOLDER not in text


def _ready_character_cards(path: Path) -> bool:
    if not path.exists():
        return False
    for card_path in sorted(path.glob('*.md')):
        text = card_path.read_text(encoding='utf-8-sig', errors='replace').strip()
        if text and PLACEHOLDER not in text:
            return True
    return False


def _memory_context(xushikj_dir: Path) -> str:
    return _read_text(xushikj_dir / 'memory.md')


def _previous_excerpt(xushikj_dir: Path, chapter_no: int) -> str:
    if chapter_no <= 1:
        return '（暂无前文，可直接从本章开写）'
    previous_path = xushikj_dir / 'chapters' / f'chapter_{chapter_no - 1}.md'
    if not previous_path.exists():
        return '（上一章正文暂缺）'
    text = _read_text(previous_path)
    if len(text) <= 1200:
        return text
    return text[-1200:]


def _render(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f'{{{{{key}}}}}', value)
    return rendered


def _canonical_step(step: str) -> str:
    return 'writing' if step in {'10', 'writing'} else step


def _character_cards_dir(xushikj_dir: Path) -> Path:
    return xushikj_dir / 'outline' / 'characters'


def _card_name(card_path: Path, text: str) -> str:
    first_line = text.splitlines()[0].strip() if text.splitlines() else ''
    if first_line.startswith('#'):
        return first_line.lstrip('#').strip()
    return card_path.stem


def _format_cards(card_paths: list[Path]) -> str:
    if not card_paths:
        return '（暂无人物卡）'
    blocks: list[str] = []
    for path in card_paths:
        text = _read_text(path)
        name = _card_name(path, text)
        blocks.append(f'### {name}\n来源：{path.name}\n{text}')
    return '\n\n'.join(blocks)


def _existing_character_cards(xushikj_dir: Path) -> str:
    cards_dir = _character_cards_dir(xushikj_dir)
    return _format_cards(sorted(cards_dir.glob('*.md')))


def _select_character_cards(xushikj_dir: Path, query_text: str, limit: int = 4) -> str:
    cards_dir = _character_cards_dir(xushikj_dir)
    card_paths = sorted(cards_dir.glob('*.md'))
    if not card_paths:
        return '（暂无人物卡）'
    lowered = query_text.lower()
    scored: list[tuple[int, Path]] = []
    for path in card_paths:
        text = _read_text(path)
        name = _card_name(path, text)
        score = 0
        for token in {path.stem.lower(), name.lower()}:
            if token and token in lowered:
                score += 2
        if text and any(line.strip() and line.strip() in query_text for line in text.splitlines()[:3]):
            score += 1
        scored.append((score, path))
    scored.sort(key=lambda item: (-item[0], item[1].name))
    selected = [path for _, path in scored[:limit] if _read_text(path) != EMPTY_PLACEHOLDER]
    return _format_cards(selected)


def _benchmark_source_samples(xushikj_dir: Path) -> str:
    benchmark_dir = xushikj_dir / 'benchmark'
    registry_path = benchmark_dir / 'source_registry.json'
    source_path: Path | None = None
    source_title = ''
    if registry_path.exists():
        payload = _load_yaml_or_json(registry_path, {})
        candidate = payload.get('source_file')
        if candidate:
            source_path = Path(str(candidate))
            source_title = str(payload.get('source_title', ''))
    if source_path is None or not source_path.exists():
        for candidate in sorted(benchmark_dir.glob('*')):
            if candidate.name in {'style_notes.md', 'source_registry.json'} or candidate.is_dir():
                continue
            if candidate.suffix.lower() in {'.md', '.txt'}:
                source_path = candidate
                source_title = candidate.stem
                break
    if source_path is None or not source_path.exists():
        return '（未登记对标原文；若用户提供原文文件，请先写入 `.xushikj/benchmark/source_registry.json` 或放入 benchmark 目录，再重新组装 Prompt）'

    raw_text = source_path.read_text(encoding='utf-8-sig', errors='replace').replace('\r\n', '\n').strip()
    if not raw_text:
        return f'（已找到对标原文 {source_path.name}，但内容为空）'

    def excerpt(ratio: float, width: int = 700) -> str:
        if len(raw_text) <= width:
            return raw_text
        center = int(len(raw_text) * ratio)
        start = max(0, center - width // 2)
        end = min(len(raw_text), start + width)
        start_break = raw_text.rfind('\n', 0, start)
        end_break = raw_text.find('\n', end)
        if start_break != -1:
            start = start_break + 1
        if end_break != -1:
            end = end_break
        snippet = raw_text[start:end].strip()
        return snippet or raw_text[max(0, center - width // 2): min(len(raw_text), center + width // 2)].strip()

    title = source_title or source_path.name
    return '\n\n'.join([
        f'来源：{title} / 文件：{source_path}',
        '### 前段样本\n' + excerpt(0.15),
        '### 中段样本\n' + excerpt(0.50),
        '### 后段样本\n' + excerpt(0.85),
    ])


def _status(project_root: Path, xushikj_dir: Path) -> str:
    initialized = xushikj_dir.exists() and (xushikj_dir / 'state.json').exists()
    if not initialized:
        return f'project={project_root}\ninitialized=false'
    state = _load_state(xushikj_dir)
    workflow = state['workflow']
    chapter_no = int(state.get('current_chapter', 1))
    return '\n'.join([
        f'project={project_root}',
        'initialized=true',
        f"current_step={state.get('current_step', '')}",
        f"current_chapter={chapter_no}",
        f"writing_mode={state.get('writing_mode', 'style-clone')}",
        f"reply_length={state.get('reply_length', '')}",
        f"target_platform={state.get('target_platform', '')}",
        f"pending_user_confirmation={str(bool(workflow.get('pending_user_confirmation'))).lower()}",
        f"pending_step={workflow.get('pending_step', '')}",
        f"next_step_suggestion={workflow.get('next_step_suggestion', '')}",
        f"benchmark_ready={_ready_text(xushikj_dir / 'benchmark' / 'style_notes.md')}",
        f"worldview_ready={_ready_text(xushikj_dir / 'worldbuilding' / 'worldview.md')}",
        f"characters_ready={_ready_character_cards(_character_cards_dir(xushikj_dir))}",
        f"chapter_outline_ready={_ready_text(xushikj_dir / 'chapter_outlines' / f'chapter_{chapter_no}.md')}",
        f"chapter_exists={(xushikj_dir / 'chapters' / f'chapter_{chapter_no}.md').exists()}",
    ])


def _resolve_humanizer_chapter(
    project_root: Path,
    xushikj_dir: Path,
    chapter: int | None,
    chapter_file: Path | None,
) -> tuple[Path, str]:
    if chapter_file is not None:
        path = chapter_file.resolve()
        if not path.exists():
            raise FileNotFoundError(f'Humanizer chapter file not found: {path}')
        return path, path.stem

    if chapter is not None:
        candidates = [
            xushikj_dir / 'chapters' / f'chapter_{chapter}.md',
            project_root / 'chapters' / f'chapter_{chapter}.md',
            project_root / f'chapter_{chapter}.md',
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate, f'第 {chapter} 章'
        raise FileNotFoundError(f'Humanizer chapter file not found: {candidates[0]}')

    state_path = xushikj_dir / 'state.json'
    if state_path.exists():
        state = _load_state(xushikj_dir)
        chapter_no = int(state.get('current_chapter', 1))
        chapter_path = xushikj_dir / 'chapters' / f'chapter_{chapter_no}.md'
        if not chapter_path.exists():
            raise FileNotFoundError(f'Humanizer chapter file not found: {chapter_path}')
        return chapter_path, f'第 {chapter_no} 章'

    raise FileNotFoundError('Humanizer requires --chapter-file or --chapter when state.json is unavailable')


def _input_context_summary(
    project_root: Path,
    xushikj_dir: Path,
    state: dict[str, Any] | None,
    step: str,
    chapter: int | None,
    chapter_file: Path | None,
) -> list[str]:
    canonical_step = _canonical_step(step)
    project_name = _project_name(state or {}, project_root)
    lines = [
        f'项目名：{project_name}',
        f'项目根目录：{project_root}',
        f'运行时目录：{xushikj_dir}',
        f'步骤标识：{canonical_step}',
    ]
    if state:
        lines.extend([
            f"state.current_step：{state.get('current_step', '')}",
            f"state.current_chapter：{state.get('current_chapter', 1)}",
            f"state.reply_length：{state.get('reply_length') or '（待确认）'}",
            f"state.target_platform：{state.get('target_platform') or '（未设置）'}",
            f"state.writing_mode：{state.get('writing_mode') or 'style-clone'}",
        ])
    if canonical_step == 'humanizer':
        chapter_path, chapter_label = _resolve_humanizer_chapter(project_root, xushikj_dir, chapter, chapter_file)
        lines.extend([
            f'目标章节：{chapter_label}',
            f'章节文件：{chapter_path}',
        ])
        return lines

    chapter_no = chapter or int((state or {}).get('current_chapter', 1))
    lines.extend([
        f'目标章节：第 {chapter_no} 章',
        f'文风指南：{xushikj_dir / "benchmark" / "style_notes.md"}',
        f'世界观设定：{xushikj_dir / "worldbuilding" / "worldview.md"}',
        f'人物卡目录：{xushikj_dir / "outline" / "characters"}',
        f'章纲文件：{xushikj_dir / "chapter_outlines" / f"chapter_{chapter_no}.md"}',
    ])
    return lines


def _result_write_back(
    project_root: Path,
    xushikj_dir: Path,
    step: str,
    chapter: int | None,
    chapter_file: Path | None,
) -> dict[str, str]:
    canonical_step = _canonical_step(step)
    state = _load_state(xushikj_dir) if (xushikj_dir / 'state.json').exists() else {}
    chapter_no = chapter or int(state.get('current_chapter', 1))
    # These command strings are meant to be copied into a shell, so every filesystem path
    # that appears inside an executable command must be shell-quoted defensively.
    project_arg = shlex.quote(str(project_root))
    if canonical_step == 'benchmark-lite':
        return {
            'save_target': str(xushikj_dir / 'benchmark' / 'style_notes.md'),
            'landing_command': '（无专用落盘脚本；请将外部模型结果人工确认后写入该文件）',
            'validation_command': f'python scripts/validate_state.py --project-dir {project_arg} --for-step worldbuilding',
            'next_step_after_success': 'worldbuilding',
        }
    if canonical_step == 'worldbuilding':
        return {
            'save_target': str(xushikj_dir / 'worldbuilding' / 'worldview.md'),
            'landing_command': '（无专用落盘脚本；请将外部模型结果人工确认后写入该文件）',
            'validation_command': f'python scripts/validate_state.py --project-dir {project_arg} --for-step characters',
            'next_step_after_success': 'characters',
        }
    if canonical_step == 'characters':
        return {
            'save_target': str(xushikj_dir / 'outline' / 'characters'),
            'landing_command': '（无专用落盘脚本；请将每个角色结果分别写入该目录下的独立 Markdown 文件）',
            'validation_command': f'python scripts/validate_state.py --project-dir {project_arg} --for-step chapter-outline --chapter {chapter_no}',
            'next_step_after_success': 'chapter-outline',
        }
    if canonical_step == 'chapter-outline':
        return {
            'save_target': str(xushikj_dir / 'chapter_outlines' / f'chapter_{chapter_no}.md'),
            'landing_command': '（无专用落盘脚本；请将外部模型结果人工确认后写入该文件）',
            'validation_command': f'python scripts/validate_state.py --project-dir {project_arg} --for-step 10 --chapter {chapter_no}',
            'next_step_after_success': '10',
        }
    if canonical_step == 'writing':
        draft_output = xushikj_dir / 'drafts' / f'chapter_{chapter_no}_output.md'
        return {
            'save_target': str(draft_output),
            'landing_command': f'python scripts/landing.py writing --project-dir {project_arg} --chapter {chapter_no} --input-file {shlex.quote(str(draft_output))}',
            'validation_command': f'python scripts/validate_state.py --project-dir {project_arg} --for-step 10 --chapter {chapter_no}',
            'next_step_after_success': 'humanizer',
        }
    humanizer_chapter_path, _ = _resolve_humanizer_chapter(project_root, xushikj_dir, chapter, chapter_file)
    draft_output = xushikj_dir / 'drafts' / f'{humanizer_chapter_path.stem}_humanizer_output.md'
    validate_cmd = (
        f'python scripts/validate_state.py --project-dir {project_arg} --for-step humanizer --chapter-file {shlex.quote(str(humanizer_chapter_path))}'
        if chapter_file is not None
        else f'python scripts/validate_state.py --project-dir {project_arg} --for-step humanizer --chapter {chapter_no}'
    )
    landing_cmd = (
        f'python scripts/landing.py humanizer --project-dir {project_arg} --chapter-file {shlex.quote(str(humanizer_chapter_path))} --input-file {shlex.quote(str(draft_output))}'
        if chapter_file is not None
        else f'python scripts/landing.py humanizer --project-dir {project_arg} --chapter {chapter_no} --input-file {shlex.quote(str(draft_output))}'
    )
    return {
        'save_target': str(draft_output),
        'landing_command': landing_cmd,
        'validation_command': validate_cmd,
        'next_step_after_success': '（可结束当前章节流程）',
    }


def _prompt_handoff_notes(step: str) -> list[str]:
    canonical_step = _canonical_step(step)
    notes = [
        '将下方 `## 已组装 Prompt` 原文完整交给外部模型，不要删改规则段落。',
        '要求外部模型只返回步骤结果本身，不要解释 Prompt 组装过程或额外寒暄。',
        '外部模型返回后，先人工检查，再按“结果回填”写入项目文件。',
    ]
    if canonical_step in {'writing', 'humanizer'}:
        notes.append('writing / humanizer 结果应先保存为 Markdown 文件，再执行落盘命令。')
    return notes


def _render_prompt_package_markdown(package: dict[str, Any]) -> str:
    sections = [
        '# Prompt Package',
        '',
        f"- 模式：{package['mode']}",
        f"- 步骤：{package['step']}",
        f"- 标题：{package['title']}",
        '',
        '## 当前步骤目标',
        package['objective'],
        '',
        '## 输入上下文摘要',
        '\n'.join(f'- {line}' for line in package['input_context']),
        '',
        '## 推荐投喂方式',
        '\n'.join(f'{number}. {line}' for number, line in enumerate(package['handoff_notes'], start=1)),
        '',
        '## 预期输出结构',
        '\n'.join(f'- {line}' for line in package['expected_output_schema']),
        '',
        '## 结果回填',
        f"- 保存目标：{package['result_write_back']['save_target']}",
        f"- 落盘命令：{package['result_write_back']['landing_command']}",
        f"- 验证命令：{package['result_write_back']['validation_command']}",
        f"- 成功后建议步骤：{package['result_write_back']['next_step_after_success']}",
        '',
        '## 已组装 Prompt',
        package['assembled_prompt'].strip(),
        '',
    ]
    return '\n'.join(sections)


def build_prompt_package(project_dir: Path, step: str, chapter: int | None, chapter_file: Path | None = None) -> dict[str, Any]:
    project_root, xushikj_dir = _resolve_paths(project_dir)
    raw_prompt = assemble(project_dir, step, chapter, chapter_file)
    state = _load_state(xushikj_dir) if (xushikj_dir / 'state.json').exists() else None
    canonical_step = _canonical_step(step)
    package_info = STEP_PACKAGE_INFO[canonical_step]
    return {
        'mode': 'prompt-only',
        'step': canonical_step,
        'title': package_info['title'],
        'objective': package_info['objective'],
        'input_context': _input_context_summary(project_root, xushikj_dir, state, step, chapter, chapter_file),
        'handoff_notes': _prompt_handoff_notes(step),
        'expected_output_schema': package_info['expected_output_schema'],
        'result_write_back': _result_write_back(project_root, xushikj_dir, step, chapter, chapter_file),
        'assembled_prompt': raw_prompt,
    }


def assemble(project_dir: Path, step: str, chapter: int | None, chapter_file: Path | None = None) -> str:
    project_root, xushikj_dir = _resolve_paths(project_dir)
    if step == 'status':
        return _status(project_root, xushikj_dir)
    if step not in TEMPLATES:
        raise ValueError(f'Unsupported Lite step: {step}')
    if step != 'humanizer':
        assert_step_allowed(project_root, step)
    if step == 'humanizer':
        if (xushikj_dir / 'state.json').exists():
            assert_step_allowed(project_root, step)
        template = read_text_utf8(PROMPTS_DIR / TEMPLATES[step], '')
        humanizer_chapter_path, chapter_label = _resolve_humanizer_chapter(project_root, xushikj_dir, chapter, chapter_file)
        values = {
            'chapter_label': chapter_label,
            'chapter_text': _read_text(humanizer_chapter_path),
            'rules': _load_rules(step),
            'dna_constraints': _humanizer_dna_constraints(xushikj_dir),
        }
        return _render(template, values)

    state = _load_state(xushikj_dir)
    project_name = _project_name(state, project_root)
    chapter_no = chapter or int(state.get('current_chapter', 1))
    style_notes_path = xushikj_dir / 'benchmark' / 'style_notes.md'
    worldview_path = xushikj_dir / 'worldbuilding' / 'worldview.md'
    characters_dir = _character_cards_dir(xushikj_dir)
    outline_path = xushikj_dir / 'chapter_outlines' / f'chapter_{chapter_no}.md'
    template = read_text_utf8(PROMPTS_DIR / TEMPLATES[step], '')

    if step in {'worldbuilding', 'characters', 'chapter-outline', '10', 'writing'} and not _ready_text(style_notes_path):
        raise FileNotFoundError(f'benchmark-lite 尚未完成，请先产出可用的文风特征指南：{style_notes_path}')
    if step in {'characters', 'chapter-outline', '10', 'writing'} and not _ready_text(worldview_path):
        raise FileNotFoundError(f'世界观设定尚未完成，请先补齐：{worldview_path}')
    if step in {'chapter-outline', '10', 'writing'} and not _ready_character_cards(characters_dir):
        raise FileNotFoundError(f'人物卡片设定尚未完成，请先补齐：{characters_dir}')
    if step in {'10', 'writing'} and not _ready_text(outline_path):
        raise FileNotFoundError(f'章纲讨论尚未完成，请先补齐：{outline_path}')
    if step in {'10', 'writing'} and not (isinstance(state.get('reply_length'), int) and int(state.get('reply_length')) > 0):
        raise ValueError('进入 writing 前必须先确认 reply_length')

    previous_excerpt = _previous_excerpt(xushikj_dir, chapter_no)
    selection_query = '\n'.join([_read_text(outline_path, ''), previous_excerpt])
    values = {
        'project_name': project_name,
        'project_context': _project_context(state),
        'recent_summaries': _recent_summaries(xushikj_dir),
        'rules': _load_rules(step),
        'style_guide': _read_text(style_notes_path),
        'worldview_text': _read_text(worldview_path),
        'existing_character_cards': _existing_character_cards(xushikj_dir),
        'character_cards': _select_character_cards(xushikj_dir, selection_query),
        'chapter_outline': _read_text(outline_path),
        'chapter_label': f'第 {chapter_no} 章',
        'reply_length': str(state.get('reply_length') or '（待确认）'),
        'target_platform': str(state.get('target_platform') or '（未设置）'),
        'memory_context': _memory_context(xushikj_dir),
        'previous_excerpt': previous_excerpt,
        'benchmark_source_samples': _benchmark_source_samples(xushikj_dir),
        'existing_style_notes': _read_text(style_notes_path),
    }
    return _render(template, values)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Assemble narrativespace Lite prompt')
    parser.add_argument('--project-dir', required=True, type=Path, help='Project root or .xushikj path')
    parser.add_argument('--step', help='0 / benchmark-lite / worldbuilding / characters / chapter-outline / 10 / writing / humanizer')
    parser.add_argument('--chapter', type=int, help='Optional chapter number for step chapter-outline/10/humanizer')
    parser.add_argument('--chapter-file', type=Path, help='Optional standalone chapter file for humanizer')
    parser.add_argument('--output', choices=['stdout', 'file'], default='stdout')
    parser.add_argument('--output-file', type=Path)
    parser.add_argument('--format', choices=['markdown', 'json'], default='markdown', help='Prompt package output format')
    parser.add_argument('--raw-prompt', action='store_true', help='Output only the assembled prompt without the prompt package wrapper')
    parser.add_argument('--status', action='store_true', help='Show Lite project status')
    parser.add_argument('--writing-mode', help='Reserved for compatibility; Lite currently uses style-clone only')
    return parser


def main() -> int:
    reconfigure_stdio_utf8()
    args = build_arg_parser().parse_args()
    step = 'status' if args.status else args.step
    if not step:
        raise SystemExit('--step or --status is required')
    if step == 'status' or args.raw_prompt:
        result = assemble(args.project_dir, step, args.chapter, args.chapter_file)
    else:
        package = build_prompt_package(args.project_dir, step, args.chapter, args.chapter_file)
        result = (
            json.dumps(package, ensure_ascii=False, indent=2)
            if args.format == 'json'
            else _render_prompt_package_markdown(package)
        )
    if args.output == 'file':
        if not args.output_file:
            raise SystemExit('--output file requires --output-file')
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        write_text_utf8(args.output_file, result + '\n')
        print(f'[assemble_prompt] wrote {args.output_file}')
    else:
        print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
