"""
init.py — 叙事空间创作系统项目初始化脚本

将 xushikj-chuangzuo 基线配置同步到指定项目目录的 .xushikj/ 结构。

用法:
    python init.py --project-dir /path/to/project
    python init.py --project-dir /path/to/project --force
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _reconfigure_stdout_utf8() -> None:
    """强制 stdout/stderr 使用 UTF-8，避免 Windows GBK 控制台编码错误。"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# UTF-8 BOM (EF BB BF)
_BOM = b"\xef\xbb\xbf"


# Skill 根目录（本文件所在位置的两级父目录）
SKILL_ROOT = Path(__file__).resolve().parent.parent


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="初始化叙事空间创作系统项目目录结构",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
模式说明:
  默认模式       : 仅写入不存在的文件，跳过已有文件
  --upgrade      : 升级模式——更新系统文件（config/、references/），保留用户数据
  --force        : 强制模式——覆盖所有文件（包括 state.json 等用户数据，慎用）
""",
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        type=Path,
        help="项目根目录路径（.xushikj/ 将在此目录下创建）",
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="升级模式：更新 config/ 和 references/ 系统文件，保留 state.json 等用户数据",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制模式：覆盖所有已存在的文件（包括用户数据，慎用）",
    )
    parser.add_argument(
        "--build-rag-index",
        action="store_true",
        help="（v8.2）初始化后立即全量构建 RAG 向量索引（需 Ollama + nomic-embed-text）",
    )
    parser.add_argument(
        "--init-volume-timeline",
        action="store_true",
        help="（v8.2）从模板创建卷级时间线文件并更新 state.json",
    )
    parser.add_argument(
        "--volume",
        type=int,
        default=1,
        metavar="N",
        help="配合 --init-volume-timeline 使用，指定卷号（默认 1）",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="跳过所有交互式确认，自动继续（适用于 CI / 自动化场景）",
    )
    parser.add_argument(
        "--global-dna-path",
        type=Path,
        metavar="PATH",
        help="全局作者DNA文件路径（默认：$NARRATIVESPACE_GLOBAL_PATH → ~/.narrativespace/global_author_dna.yaml）",
    )
    return parser


def ensure_dirs(xushikj: Path) -> None:
    """创建 .xushikj/ 目录树。"""
    subdirs = [
        "config/style_modules",
        "outline/characters",
        "scenes",
        "benchmark/style_snippets",
        "summaries",
        "chapters",
        "drafts",
        "kb_diffs",
        "quality_reports",
        "references",
        "anchors",
        "rag",
        "timelines",
        "branches",
        "style_logs",
        "style_actions",
        "style_actions/processed",
    ]
    for subdir in subdirs:
        (xushikj / subdir).mkdir(parents=True, exist_ok=True)


def copy_if_missing(src: Path, dst: Path, force: bool, base: Path | None = None) -> str:
    """复制文件；若 dst 已存在且 force=False 则跳过。返回操作描述。

    Args:
        src: 源文件路径。
        dst: 目标文件路径。
        force: 为 True 时强制覆盖已存在文件。
        base: 可选基准路径，用于生成短相对路径显示（默认显示绝对路径）。
    """
    display = str(dst.relative_to(base)) if base else str(dst)
    if dst.exists() and not force:
        return f"  [skip]    {display}"
    shutil.copy2(src, dst)
    return f"  [write]   {display}"


def strip_bom_if_present(path: Path) -> bool:
    """检测并移除 JSON 文件中的 UTF-8 BOM 头。返回是否执行了修复。

    Args:
        path: 目标文件路径（必须是 JSON 文件）。

    Returns:
        True 若 BOM 已被移除，False 若文件本身无 BOM。

    Raises:
        ValueError: 若文件内容在去除 BOM 后无法解析为合法 JSON。
    """
    raw = path.read_bytes()
    if not raw.startswith(_BOM):
        return False
    clean = raw[len(_BOM):]
    # 验证去除 BOM 后的内容仍是合法 JSON
    try:
        json.loads(clean.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"去除 BOM 后 JSON 解析失败: {exc}") from exc
    path.write_bytes(clean)
    return True


def copy_references(xushikj: Path, force: bool) -> list[str]:
    """将写作 Sub-agent 所需的参考文件复制到项目 .xushikj/references/。

    目前包括：
      - few_shot_examples.md: 写作 Sub-agent 的题材匹配示例库
      - chapter-architecture-rules.md: 章节架构规则（Mission/Turn/Residue）
      - dialogue-writing-rules.md: 对话写作规则（压力驱动版）
    """
    references_src = SKILL_ROOT / "modules" / "writing" / "references"
    references_dst = xushikj / "references"
    log: list[str] = []

    deploy_files = [
        "few_shot_examples.md",
        "chapter-architecture-rules.md",
        "dialogue-writing-rules.md",
    ]
    for fname in deploy_files:
        src = references_src / fname
        if not src.exists():
            log.append(f"  [warn]    参考文件不存在，跳过: {src}")
            continue
        dst = references_dst / fname
        log.append(copy_if_missing(src, dst, force, base=xushikj))

    return log


def inject_global_dna(xushikj: Path, global_dna_path: Path | None, log: list[str]) -> None:
    """处理全局作者DNA文件的路径解析、模板部署和本地副本同步。（v8.5 新增）"""
    import os

    # 路径解析优先级：--global-dna-path > NARRATIVESPACE_GLOBAL_PATH env > ~/.narrativespace/
    if global_dna_path is not None:
        resolved = global_dna_path
    else:
        env_val = os.environ.get("NARRATIVESPACE_GLOBAL_PATH")
        if env_val:
            resolved = Path(env_val) / "global_author_dna.yaml"
        else:
            resolved = Path.home() / ".narrativespace" / "global_author_dna.yaml"

    local_copy = xushikj / "config" / "global_author_dna.yaml"

    # 若全局文件不存在，从模板部署（首次初始化）
    if not resolved.exists():
        tpl = SKILL_ROOT / "templates" / "global_author_dna_template.yaml"
        if tpl.exists():
            resolved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(tpl), str(resolved))
            log.append(f"  [write]   全局DNA模板已部署到: {resolved}")
        else:
            log.append(f"  [skip]    全局DNA模板不存在，跳过全局DNA初始化: {tpl}")
            return
    else:
        log.append(f"  [info]    全局DNA已存在，跳过覆盖: {resolved}")

    # 同步本地副本
    if not local_copy.exists():
        shutil.copy2(str(resolved), str(local_copy))
        log.append(f"  [write]   全局DNA本地副本已创建: config/global_author_dna.yaml")
    else:
        log.append(f"  [skip]    全局DNA本地副本已存在: config/global_author_dna.yaml")

    # 部署 cycle_quirks_template.md（如果 style_logs 中没有 cycle_quirks.md）
    cycle_quirks_tpl = SKILL_ROOT / "templates" / "cycle_quirks_template.md"
    cycle_quirks_dst = xushikj / "style_logs" / "cycle_quirks.md"
    if cycle_quirks_tpl.exists() and not cycle_quirks_dst.exists():
        shutil.copy2(str(cycle_quirks_tpl), str(cycle_quirks_dst))
        log.append(f"  [write]   本卷风格覆写模板已部署: style_logs/cycle_quirks.md")


def sync_config(xushikj: Path, force: bool) -> list[str]:
    """将 Skill config/ 目录同步到项目 .xushikj/config/。"""
    config_src = SKILL_ROOT / "config"
    config_dst = xushikj / "config"
    log: list[str] = []

    if not config_src.is_dir():
        log.append(f"  [warn]    Skill config/ 目录未找到，跳过配置同步: {config_src}")
        return log

    for src_file in config_src.rglob("*"):
        if src_file.is_file():
            rel = src_file.relative_to(config_src)
            dst_file = config_dst / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            log.append(copy_if_missing(src_file, dst_file, force, base=xushikj))

    return log


def copy_templates(xushikj: Path, force: bool) -> list[str]:
    """从 Skill templates/ 复制 state.json、memory.md 等文件到 .xushikj/。"""
    templates_src = SKILL_ROOT / "templates"
    log: list[str] = []

    mappings: list[tuple[str, str]] = [
        ("state_template.json", "state.json"),
        ("memory_template.md", "memory.md"),
        ("summary_index_template.md", "summaries/_index.md"),
        ("kb_template.json", "knowledge_base.json"),
    ]

    for src_name, dst_name in mappings:
        src = templates_src / src_name
        if not src.exists():
            log.append(f"  [skip]    模板文件不存在，跳过: {src_name}")
            continue
        dst = xushikj / dst_name
        dst.parent.mkdir(parents=True, exist_ok=True)
        result = copy_if_missing(src, dst, force, base=xushikj)
        log.append(result)

        # JSON 文件：检测并移除 BOM（PowerShell 等工具可能生成带 BOM 的 JSON）
        if dst.suffix == ".json" and ("[write]" in result):
            try:
                if strip_bom_if_present(dst):
                    log.append(f"  [patch]   移除 BOM 头: {dst_name}")
            except ValueError as exc:
                log.append(f"  [warn]    BOM 检测失败，文件可能损坏: {exc}")

        # 对 state.json 写入初始时间戳并强制校验 writing_mode
        if dst_name == "state.json" and "[write]" in result:
            try:
                with dst.open("r", encoding="utf-8") as f:
                    state = json.load(f)
                now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                state["created_at"] = now
                state["updated_at"] = now
                # 强制确保 writing_mode 默认为 pipeline（防止旧模板残留 interactive）
                config = state.setdefault("config", {})
                if config.get("writing_mode") not in ("pipeline", "interactive"):
                    config["writing_mode"] = "pipeline"
                    log.append("  [patch]   writing_mode 已补全为 'pipeline'")
                with dst.open("w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                log.append(f"  [patch]   写入初始时间戳到 state.json")
            except (json.JSONDecodeError, KeyError) as exc:
                log.append(f"  [warn]    无法更新 state.json: {exc}")

    return log


def scan_project_gaps(xushikj: Path, skill_root: Path) -> dict[str, list[str]]:
    """扫描项目 .xushikj/ 中缺失的文件，按类别返回。

    Args:
        xushikj: 项目 .xushikj/ 目录。
        skill_root: Skill 根目录，用于获取全量文件清单。

    Returns:
        字典，key 为文件类别，value 为缺失文件的相对路径列表（相对于 xushikj）。
        若无缺失则返回空字典。
    """
    gaps: dict[str, list[str]] = {}

    # 用户数据模板
    user_data_missing = [
        str(Path(dst_name))
        for _, dst_name in [
            ("state_template.json",       "state.json"),
            ("memory_template.md",        "memory.md"),
            ("summary_index_template.md", "summaries/_index.md"),
            ("kb_template.json",          "knowledge_base.json"),
        ]
        if not (xushikj / dst_name).exists()
    ]
    if user_data_missing:
        gaps["用户数据"] = user_data_missing

    # 参考文件
    ref_missing = [
        str(Path("references") / fname)
        for fname in [
            "few_shot_examples.md",
            "chapter-architecture-rules.md",
            "dialogue-writing-rules.md",
        ]
        if not (xushikj / "references" / fname).exists()
    ]
    if ref_missing:
        gaps["参考文件"] = ref_missing

    # 配置文件
    config_src = skill_root / "config"
    if config_src.is_dir():
        config_missing = [
            str(Path("config") / src_file.relative_to(config_src))
            for src_file in config_src.rglob("*")
            if src_file.is_file() and not (xushikj / "config" / src_file.relative_to(config_src)).exists()
        ]
        if config_missing:
            gaps["配置文件"] = sorted(config_missing)

    return gaps


def main() -> None:
    _reconfigure_stdout_utf8()

    parser = build_arg_parser()
    args = parser.parse_args()

    project_dir: Path = args.project_dir.resolve()
    force: bool = args.force
    upgrade: bool = args.upgrade
    build_rag: bool = getattr(args, "build_rag_index", False)
    init_vol_timeline: bool = getattr(args, "init_volume_timeline", False)
    volume_num: int = getattr(args, "volume", 1)

    if force and upgrade:
        print("错误：--force 与 --upgrade 不能同时使用。", file=sys.stderr)
        sys.exit(1)

    xushikj = project_dir / ".xushikj"

    if not project_dir.exists():
        print(f"错误：项目目录不存在: {project_dir}", file=sys.stderr)
        sys.exit(1)

    # ── 标题 ──────────────────────────────────────────────────────────────────
    print(f"\n叙事空间创作系统 — 项目{'升级' if upgrade else '初始化'}")
    print(f"项目目录 : {project_dir}")
    print(f"目标路径 : {xushikj}")
    if upgrade:
        print(f"模式     : 升级（config/ 和 references/ 将更新，用户数据保留）")
    elif force:
        print(f"模式     : 强制覆盖（所有文件将被重写）")
    else:
        print(f"模式     : 默认（跳过已存在的文件）")
    print("-" * 60)

    ensure_dirs(xushikj)
    print("创建目录结构... 完成")

    # ── 缺失文件预检 ──────────────────────────────────────────────────────────
    gaps = scan_project_gaps(xushikj, SKILL_ROOT)
    if gaps:
        total_missing = sum(len(v) for v in gaps.values())
        print(f"\n[!] 发现 {total_missing} 个缺失文件（本次运行将自动补充）:")
        for category, files in gaps.items():
            print(f"\n  [{category}] ({len(files)} 个)")
            for f in files:
                print(f"    - {f}")
        print()
        if sys.stdin.isatty() and not force and not args.yes:
            try:
                ans = input("是否补充上述缺失文件？[Y/n] ").strip().lower()
                if ans in ("n", "no"):
                    print("已取消，未作任何修改。")
                    sys.exit(0)
            except (EOFError, KeyboardInterrupt):
                print("\n已取消。")
                sys.exit(0)

    log: list[str] = []

    if upgrade:
        # 升级模式：仅更新系统文件，保留用户数据
        log.extend(copy_templates(xushikj, force=False))      # 用户数据：保留
        log.extend(copy_references(xushikj, force=True))      # 系统文件：强制更新
        log.extend(sync_config(xushikj, force=True))          # 系统文件：强制更新
        inject_global_dna(xushikj, getattr(args, 'global_dna_path', None), log)  # v8.5

        # 升级补丁：向已存在的 state.json 中追加新字段（不覆盖已有字段）
        state_path = xushikj / "state.json"
        if state_path.exists():
            try:
                strip_bom_if_present(state_path)
                with state_path.open("r", encoding="utf-8") as f:
                    state = json.load(f)

                patched = False

                # 补丁 1：注入 required_context_files（Layer-1 上下文清单）
                if "required_context_files" not in state:
                    state["required_context_files"] = {
                        "_note": "Layer-1 上下文清单：各步骤必须加载的文件，供 orchestrator 和 init.py --upgrade 使用",
                        "always": [
                            "config/methodology.yaml",
                            "config/writing_rules.yaml",
                            "config/style_rules.yaml",
                            "config/quality_dimensions.yaml",
                        ],
                        "step_0": ["config/benchmark_triggers.yaml"],
                        "step_1_6": ["config/workflow.yaml", "config/layer_definitions.yaml"],
                        "step_10A_pipeline": [
                            "config/writing_rules.yaml",
                            "config/style_rules.yaml",
                            "config/quality_dimensions.yaml",
                            "config/meta_rules.yaml",
                            "config/golden_opening.yaml",
                            "references/chapter-architecture-rules.md",
                            "references/dialogue-writing-rules.md",
                        ],
                        "step_10B_interactive": [
                            "config/writing_rules.yaml",
                            "config/style_rules.yaml",
                            "config/quality_dimensions.yaml",
                            "config/bangui_modes.yaml",
                            "references/chapter-architecture-rules.md",
                            "references/dialogue-writing-rules.md",
                        ],
                    }
                    log.append("  [patch]   state.json 已补充 required_context_files 字段（Layer-1 失忆防护）")
                    patched = True

                # 补丁 2：向 config 注入 target_platform（若缺失）
                config = state.setdefault("config", {})
                if "target_platform" not in config:
                    config["target_platform"] = ""
                    log.append("  [patch]   state.json 已补充 config.target_platform 字段")
                    patched = True

                # 补丁 3：向 config 注入 pov_mode（若缺失）
                if "pov_mode" not in config:
                    config["pov_mode"] = "limited_third"
                    log.append("  [patch]   state.json 已补充 config.pov_mode 字段（默认 limited_third）")
                    patched = True

                # ── v8.0 升级补丁 ────────────────────────────────────

                # 补丁 4：注入 benchmark_state.dna_extraction（v8.0 DNA提取状态）
                benchmark_state = state.setdefault("benchmark_state", {})
                if "dna_extraction" not in benchmark_state:
                    benchmark_state["dna_extraction"] = {
                        "enabled": False,
                        "reference_works": [],
                        "dna_profile_path": None,
                        "dna_modules_generated": [],
                        "extraction_completed_at": None,
                    }
                    log.append("  [patch]   state.json 已补充 benchmark_state.dna_extraction 字段（v8.0 DNA提取）")
                    patched = True

                # 补丁 5：注入 interactive_state（v8.0 互动模式状态）
                if "interactive_state" not in state:
                    state["interactive_state"] = {
                        "_note": "v8.0 互动模式状态追踪",
                        "decision_density": "normal",
                        "emotional_temperature": None,
                        "turns_since_last_anchor": 0,
                        "interrupt_active": False,
                        "last_anchor_chapter": None,
                    }
                    log.append("  [patch]   state.json 已补充 interactive_state 字段（v8.0 TRPG互动状态）")
                    patched = True

                # 补丁 6：向 files 注入 anchors（v8.0 记忆锚点文件列表）
                files = state.setdefault("files", {})
                if "anchors" not in files:
                    files["anchors"] = []
                    log.append("  [patch]   state.json 已补充 files.anchors 字段（v8.0 记忆锚点）")
                    patched = True

                # 补丁 7：更新 required_context_files 中的 step_10A/10B 添加新配置
                rcf = state.get("required_context_files", {})
                step_10a = rcf.get("step_10A_pipeline", [])
                if "config/human_touch_rules.yaml" not in step_10a:
                    step_10a.extend(["config/human_touch_rules.yaml", "config/emotional_temperature.yaml"])
                    log.append("  [patch]   state.json step_10A_pipeline 已补充 v8.0 配置文件")
                    patched = True
                step_10b = rcf.get("step_10B_interactive", [])
                if "config/trpg_immersion.yaml" not in step_10b:
                    step_10b.extend(["config/trpg_immersion.yaml", "config/human_touch_rules.yaml", "config/emotional_temperature.yaml"])
                    log.append("  [patch]   state.json step_10B_interactive 已补充 v8.0 配置文件")
                    patched = True

                # 补丁 8：版本号升级到 8.0.0
                if state.get("version", "") < "8.0.0":
                    state["version"] = "8.0.0"
                    log.append("  [patch]   state.json 版本号已升级到 8.0.0")
                    patched = True

                # ── v8.1 升级补丁 ────────────────────────────────────

                # 补丁 9：注入 chapter_meta（v8.1 P2.9 结构化锚点元数据）
                if "chapter_meta" not in state:
                    state["chapter_meta"] = {
                        "_note": "v8.1 P2.9：per-chapter 结构化元数据，key 为章节号字符串，value 为锚点元数据快照",
                        "_schema": {
                            "hook_type": "crisis|reward_pre|reversal|new_threat|system_call",
                            "hook_strength": "strong|medium|weak",
                            "opening_pattern": "in_medias_res|aftermath|tension_carry|time_skip",
                            "emotion_rhythm": "string（压迫→绝境→反转→爽感→新悬念）",
                            "ending_time": "string（故事内时间标记）",
                            "ending_emotion": "string（一词）",
                        },
                    }
                    log.append("  [patch]   state.json 已补充 chapter_meta 字段（v8.1 结构化锚点元数据）")
                    patched = True

                # 补丁 10：注入 strand_tracker（v8.1 P2.6 Strand Weave 三轨节奏）
                if "strand_tracker" not in state:
                    state["strand_tracker"] = {
                        "_note": "v8.1 P2.6：Strand Weave 三轨节奏追踪（Quest主线/Fire危机/Constellation世界观）",
                        "last_quest_chapter": None,
                        "last_fire_chapter": None,
                        "last_constellation_chapter": None,
                        "history": [],
                    }
                    log.append("  [patch]   state.json 已补充 strand_tracker 字段（v8.1 Strand Weave 三轨节奏）")
                    patched = True

                # 补丁 11：注入 override_contracts（v8.1 P1.5 Override Contract 豁免记录）
                if "override_contracts" not in state:
                    state["override_contracts"] = []
                    log.append("  [patch]   state.json 已补充 override_contracts 字段（v8.1 软规则豁免记录）")
                    patched = True

                # 补丁 12：版本号升级到 8.1.0
                if state.get("version", "") < "8.1.0":
                    state["version"] = "8.1.0"
                    log.append("  [patch]   state.json 版本号已升级到 8.1.0")
                    patched = True

                # 补丁 13（v8.2）：注入 rag_state
                if "rag_state" not in state:
                    state["rag_state"] = {
                        "enabled": False,
                        "backend": None,
                        "index_version": 0,
                        "index_path": "rag/rag_index.json",
                        "retrieval_index_path": "rag/retrieval_index.md",
                        "total_indexed": 0,
                        "last_indexed_chapter": 0,
                        "fallback_level": "none",
                    }
                    log.append("  [patch]   state.json 已补充 rag_state 字段（v8.2 RAG 检索状态）")
                    patched = True

                # 补丁 14（v8.2）：注入 volume_timeline
                if "volume_timeline" not in state:
                    state["volume_timeline"] = {
                        "active_volume_file": None,
                        "files": [],
                        "last_updated_volume": None,
                    }
                    log.append("  [patch]   state.json 已补充 volume_timeline 字段（v8.2 卷级时间线）")
                    patched = True

                # 补丁 15（v8.2）：files 注入 timelines 字段
                if "timelines" not in state.get("files", {}):
                    state.setdefault("files", {})["timelines"] = []
                    log.append("  [patch]   state.json files 已补充 timelines 字段（v8.2 卷级时间线列表）")
                    patched = True

                # 补丁 16（v8.2）：版本号升级到 8.2.0
                if state.get("version", "") < "8.2.0":
                    state["version"] = "8.2.0"
                    log.append("  [patch]   state.json 版本号已升级到 8.2.0")
                    patched = True

                # 补丁 17（v8.2）：interactive_state 补充 branch_registry 和 confirmed_chapter
                interactive_state = state.setdefault("interactive_state", {})
                changed_17 = False
                if "branch_registry" not in interactive_state:
                    interactive_state["branch_registry"] = {}
                    changed_17 = True
                if "confirmed_chapter" not in interactive_state:
                    interactive_state["confirmed_chapter"] = None
                    changed_17 = True
                if changed_17:
                    log.append("  [patch]   state.json interactive_state 已补充 branch_registry 和 confirmed_chapter")
                    patched = True

                # 补丁 18（v8.5）：required_context_files 注入 global_author_dna.yaml
                rcf = state.get("required_context_files", {})
                changed_18 = False
                global_dna_entry = "config/global_author_dna.yaml"
                if isinstance(rcf.get("always"), list) and global_dna_entry not in rcf["always"]:
                    rcf["always"].append(global_dna_entry)
                    changed_18 = True
                if isinstance(rcf.get("step_10A_pipeline"), list) and global_dna_entry not in rcf["step_10A_pipeline"]:
                    rcf["step_10A_pipeline"].append(global_dna_entry)
                    changed_18 = True
                if isinstance(rcf.get("step_10B_interactive"), list) and global_dna_entry not in rcf["step_10B_interactive"]:
                    rcf["step_10B_interactive"].append(global_dna_entry)
                    changed_18 = True
                if changed_18:
                    log.append("  [patch]   state.json required_context_files 已注入 global_author_dna.yaml（v8.5）")
                    patched = True

                # 补丁 19（v8.5）：注入 global_dna_state
                if "global_dna_state" not in state:
                    state["global_dna_state"] = {
                        "_note": "v8.5 全局作者DNA状态追踪",
                        "source_path": None,
                        "injected_at": None,
                        "rule_count": 0,
                        "checksum": None,
                    }
                    log.append("  [patch]   state.json 已补充 global_dna_state 字段（v8.5 全局DNA追踪）")
                    patched = True

                # 补丁 20（v8.5）：注入 style_router_history
                if "style_router_history" not in state:
                    state["style_router_history"] = []
                    log.append("  [patch]   state.json 已补充 style_router_history 字段（v8.5 风格路由历史）")
                    patched = True

                # 补丁 21（v8.5）：版本号升级到 8.5.0
                if state.get("version", "") < "8.5.0":
                    state["version"] = "8.5.0"
                    log.append("  [patch]   state.json 版本号已升级到 8.5.0")
                    patched = True

                if patched:
                    state["updated_at"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    with state_path.open("w", encoding="utf-8") as f:
                        json.dump(state, f, ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, KeyError, OSError) as exc:
                log.append(f"  [warn]    state.json 升级补丁失败: {exc}")
    else:
        log.extend(copy_templates(xushikj, force))
        log.extend(copy_references(xushikj, force))
        log.extend(sync_config(xushikj, force))
        inject_global_dna(xushikj, getattr(args, 'global_dna_path', None), log)  # v8.5

    print("\n文件操作详情:")
    for line in log:
        print(line)

    written = sum(1 for l in log if "[write]" in l or "[patch]" in l)
    skipped = sum(1 for l in log if "[skip]" in l)
    warned  = sum(1 for l in log if "[warn]"  in l)

    print("\n" + "=" * 60)
    if upgrade:
        updated = sum(1 for l in log if "[write]" in l and ("config" in l or "references" in l))
        kept    = sum(1 for l in log if "[skip]"  in l and ("state.json" in l or "knowledge_base" in l or "memory.md" in l or "_index.md" in l))
        print(f"升级完成: {written} 个文件更新，{kept} 个用户数据文件保留，{warned} 个警告")
    else:
        print(f"初始化完成: {written} 个文件写入，{skipped} 个跳过，{warned} 个警告")
    print(f"项目目录已就绪: {xushikj}")

    # ── 验证与可视化 ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("验证与可视化")
    print("=" * 60)

    print("\n[1/3] 模块依赖树:")
    print_dependency_tree()

    print("\n[2/3] 配置文件完整性检查:")
    check_config_files(SKILL_ROOT, xushikj)

    print("\n[3/3] 版本一致性检查:")
    check_version_consistency(SKILL_ROOT)

    print("\n[完成] 所有初始化和验证已完成！")

    # ── v8.2 RAG 索引构建（--build-rag-index） ───────────────────────────────
    if build_rag:
        print("\n" + "=" * 60)
        print("v8.2 RAG 向量索引构建")
        print("=" * 60)
        import subprocess
        rag_script = SKILL_ROOT / "scripts" / "rag_index.py"
        if rag_script.exists():
            result = subprocess.run(
                [sys.executable, str(rag_script), "--project-dir", str(project_dir), "--build"],
                check=False,
            )
            if result.returncode != 0:
                print(
                    "  [warn]  RAG 构建返回非零状态码，可能 Ollama 未启动或 nomic-embed-text 未拉取。\n"
                    "          retrieval_index.md（L2 降级文件）应已生成，RAG 可在 L2 模式工作。",
                    file=sys.stderr,
                )
        else:
            print(f"  [warn]  rag_index.py 不存在: {rag_script}", file=sys.stderr)

    # ── v8.2 卷级时间线初始化（--init-volume-timeline） ─────────────────────
    if init_vol_timeline:
        print("\n" + "=" * 60)
        print(f"v8.2 卷级时间线初始化 — 第{volume_num}卷")
        print("=" * 60)
        import shutil
        tpl_src  = SKILL_ROOT / "templates" / "timeline_vol_template.json"
        tpl_dst  = xushikj / "timelines" / f"volume_{volume_num}_timeline.json"
        if not tpl_dst.exists():
            if tpl_src.exists():
                shutil.copy2(str(tpl_src), str(tpl_dst))
                print(f"  [write] 已创建: {tpl_dst.relative_to(project_dir)}")
            else:
                print(f"  [warn]  模板文件不存在: {tpl_src}", file=sys.stderr)
        else:
            print(f"  [skip]  已存在: {tpl_dst.relative_to(project_dir)}（使用 --force 覆盖）")

        # 更新 state.json volume_timeline
        state_path = xushikj / "state.json"
        if state_path.exists():
            try:
                import json as _json
                from datetime import datetime as _dt, timezone as _tz
                strip_bom_if_present(state_path)
                state = _json.loads(state_path.read_text(encoding="utf-8"))
                vt    = state.setdefault("volume_timeline", {})
                rel   = f"timelines/volume_{volume_num}_timeline.json"
                vt["active_volume_file"] = rel
                if rel not in vt.get("files", []):
                    vt.setdefault("files", []).append(rel)
                vt["last_updated_volume"] = volume_num
                state["updated_at"] = _dt.now(tz=_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                state_path.write_text(
                    _json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(f"  [patch] state.json volume_timeline 已更新（active: {rel}）")
            except (Exception,) as exc:
                print(f"  [warn]  state.json 更新失败: {exc}", file=sys.stderr)


def print_dependency_tree() -> None:
    """打印简化的模块依赖树"""
    tree = """narrativeSpace-xushikj (统一根目录)
    ├── modules/
    │   ├── benchmark (步骤0：对标分析)
    │   ├── planning (步骤1-6,11：规划)
    │   ├── knowledge-base (步骤7：知识库)
    │   ├── scenes (步骤8-9：场景规划)
    │   ├── writing (步骤10A：流水线写作) <-- 核心枢纽
    │   ├── interactive (步骤10B：互动写作)
    │   └── humanizer (后处理：去AI痕迹)
    ├── config/ (21个配置文件)
    ├── templates/ (5个模板)
    ├── scripts/ (初始化和验证脚本)
    └── references/ (设计文档)

    数据流向:
    benchmark -> planning -> knowledge-base
                    |              |
                  scenes -------> writing <- interactive
                                    |
                              humanizer (可选)
    """
    print(tree)


def check_config_files(skill_root: Path, project_xushikj: Path) -> None:
    """检查必要的配置文件是否完整"""
    required_configs = [
        "methodology.yaml",
        "writing_rules.yaml",
        "golden_opening.yaml",
        "quality_dimensions.yaml",
        "layer_definitions.yaml",
        "memory_archival_policy.yaml",
        "human_touch_rules.yaml",
        "emotional_temperature.yaml",
        "trpg_immersion.yaml",
    ]

    config_dir = project_xushikj / "config"
    missing = []
    present = []

    for fname in required_configs:
        fpath = config_dir / fname
        if fpath.exists():
            present.append(fname)
        else:
            missing.append(fname)

    if missing:
        print(f"  [warn]  缺少 {len(missing)} 个关键配置文件: {', '.join(missing)}")
    else:
        print(f"  [OK]    所有 {len(required_configs)} 个关键配置文件均已就绪")


def check_version_consistency(skill_root: Path) -> None:
    """检查所有 SKILL.md 的版本号，以根模块版本为基准报告需更新的子模块。"""
    import re

    skill_files = [skill_root / "SKILL.md"]
    skill_files.extend((skill_root / "modules").glob("*/SKILL.md"))

    versions: dict[str, str] = {}
    for skill_file in skill_files:
        if skill_file.exists():
            try:
                content = skill_file.read_text(encoding="utf-8")
                match = re.search(r'["\']?version["\']?\s*:\s*["\']?([\d.]+)["\']?', content)
                if match:
                    versions[skill_file.parent.name] = match.group(1)
            except Exception:
                pass

    if not versions:
        print("  [warn]  未找到任何版本信息")
        return

    root_name = skill_root.name
    root_version = versions.get(root_name)

    if root_version is None:
        # 回退：以最常见版本为基准
        root_version = max(set(versions.values()), key=list(versions.values()).count)

    needs_update = {k: v for k, v in versions.items() if k != root_name and v != root_version}
    up_to_date   = {k: v for k, v in versions.items() if k != root_name and v == root_version}

    print(f"  [基准]  {root_name}: v{root_version}")

    if not needs_update:
        print(f"  [OK]    所有 {len(up_to_date)} 个子模块版本与基准一致")
    else:
        for name, ver in up_to_date.items():
            print(f"  [OK]    {name}: v{ver}")
        for name, ver in needs_update.items():
            print(f"  [旧版]  {name}: v{ver}  (基准 v{root_version})")
        print(f"\n  注意: 以上子模块的 SKILL.md 版本号与根版本不一致（源码层面），")
        print(f"        需手动更新 modules/{{模块}}/SKILL.md 中的 version 字段。")


if __name__ == "__main__":
    main()
