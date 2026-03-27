"""
init.py — 叙事空间创作系统项目初始化脚本

将 xushikj-chuangzuo 基线配置同步到指定项目目录的 .xushikj/ 结构。

用法:
    python init.py --project-dir /path/to/project
    python init.py --project-dir /path/to/project --force
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


# Skill 根目录（本文件所在位置的两级父目录）
SKILL_ROOT = Path(__file__).resolve().parent.parent


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="初始化叙事空间创作系统项目目录结构",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        type=Path,
        help="项目根目录路径（.xushikj/ 将在此目录下创建）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制覆盖已存在的文件（默认跳过已有文件）",
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
    ]
    for subdir in subdirs:
        (xushikj / subdir).mkdir(parents=True, exist_ok=True)


def copy_if_missing(src: Path, dst: Path, force: bool) -> str:
    """复制文件；若 dst 已存在且 force=False 则跳过。返回操作描述。"""
    if dst.exists() and not force:
        return f"  [skip]  {dst}"
    shutil.copy2(src, dst)
    return f"  [write] {dst}"


def sync_config(xushikj: Path, force: bool) -> list[str]:
    """将 Skill config/ 目录同步到项目 .xushikj/config/。"""
    config_src = SKILL_ROOT / "config"
    config_dst = xushikj / "config"
    log: list[str] = []

    if not config_src.is_dir():
        log.append(f"  [warn]  Skill config/ 目录未找到，跳过配置同步: {config_src}")
        return log

    for src_file in config_src.rglob("*"):
        if src_file.is_file():
            rel = src_file.relative_to(config_src)
            dst_file = config_dst / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            log.append(copy_if_missing(src_file, dst_file, force))

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
            log.append(f"  [skip]  模板文件不存在，跳过: {src_name}")
            continue
        dst = xushikj / dst_name
        dst.parent.mkdir(parents=True, exist_ok=True)
        result = copy_if_missing(src, dst, force)
        log.append(result)

        # 对 state.json 写入初始时间戳
        if dst_name == "state.json" and "[write]" in result:
            try:
                with dst.open("r", encoding="utf-8") as f:
                    state = json.load(f)
                now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                state["created_at"] = now
                state["updated_at"] = now
                with dst.open("w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                log.append(f"  [patch] 写入初始时间戳到 state.json")
            except (json.JSONDecodeError, KeyError) as exc:
                log.append(f"  [warn]  无法更新 state.json 时间戳: {exc}")

    return log


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    project_dir: Path = args.project_dir.resolve()
    force: bool = args.force
    xushikj = project_dir / ".xushikj"

    if not project_dir.exists():
        print(f"错误：项目目录不存在: {project_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"\n叙事空间创作系统 — 项目初始化")
    print(f"项目目录 : {project_dir}")
    print(f"目标路径 : {xushikj}")
    print(f"强制覆盖 : {'是' if force else '否'}")
    print("-" * 60)

    ensure_dirs(xushikj)
    print("创建目录结构... 完成")

    log: list[str] = []
    log.extend(copy_templates(xushikj, force))
    log.extend(sync_config(xushikj, force))

    print("\n文件操作详情:")
    for line in log:
        print(line)

    written = sum(1 for l in log if "[write]" in l or "[patch]" in l)
    skipped = sum(1 for l in log if "[skip]" in l)
    warned = sum(1 for l in log if "[warn]" in l)

    print("\n" + "=" * 60)
    print(f"初始化完成: {written} 个文件写入，{skipped} 个跳过，{warned} 个警告")
    print(f"项目目录已就绪: {xushikj}")
    
    # 新增：验证和可视化
    print("\n" + "=" * 60)
    print("【验证与可视化】")
    print("=" * 60)
    
    print("\n[1/3] 模块依赖树:")
    print_dependency_tree()
    
    print("\n[2/3] 配置文件完整性检查:")
    check_config_files(SKILL_ROOT, xushikj)
    
    print("\n[3/3] 版本一致性检查:")
    check_version_consistency(SKILL_ROOT)
    
    print("\n✅ 所有初始化和验证已完成！")


def print_dependency_tree() -> None:
    """打印简化的模块依赖树"""
    tree = """
    narrativeSpace-xushikj (统一根目录)
    ├── modules/
    │   ├── benchmark (步骤0：对标分析)
    │   ├── planning (步骤1-6,11：规划)
    │   ├── knowledge-base (步骤7：知识库)
    │   ├── scenes (步骤8-9：场景规划)
    │   ├── writing (步骤10A：流水线写作) ←── 核心枢纽
    │   ├── interactive (步骤10B：互动写作)
    │   └── humanizer (后处理：去AI痕迹)
    ├── config/ (21个配置文件)
    ├── templates/ (5个模板)
    ├── scripts/ (初始化和验证脚本)
    └── references/ (设计文档)
    
    【数据流向】
    benchmark → planning → knowledge-base ↗
                    ↓           ↓
                  scenes ────→ writing ← interactive
                                 ↓
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
        "layer_definitions.yaml",        # ✨ NEW
        "memory_archival_policy.yaml",   # ✨ NEW
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
    
    if present:
        print(f"  ✅ 找到 {len(present)} 个关键配置文件")
    if missing:
        print(f"  ⚠️  缺少 {len(missing)} 个配置：{', '.join(missing)}")
    else:
        print(f"  ✅ 所有关键配置文件完整")


def check_version_consistency(skill_root: Path) -> None:
    """检查所有SKILL.md的版本号是否一致"""
    import re
    
    skill_files = [skill_root / "SKILL.md"]
    skill_files.extend((skill_root / "modules").glob("*/SKILL.md"))
    
    versions = {}
    for skill_file in skill_files:
        if skill_file.exists():
            try:
                content = skill_file.read_text(encoding="utf-8")
                # 简单的正则提取version字段
                match = re.search(r'["\']?version["\']?\s*:\s*["\']?([\d.]+)["\']?', content)
                if match:
                    version = match.group(1)
                    versions[skill_file.parent.name] = version
            except Exception:
                pass
    
    if versions:
        first_version = list(versions.values())[0]
        all_same = all(v == first_version for v in versions.values())
        
        if all_same:
            print(f"  ✅ 所有模块版本一致（v{first_version}）")
        else:
            print(f"  ⚠️  版本不一致：")
            for module, version in versions.items():
                marker = "✓" if version == first_version else "✗"
                print(f"      {marker} {module}: v{version}")


if __name__ == "__main__":
    main()
