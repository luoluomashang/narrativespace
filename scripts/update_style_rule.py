#!/usr/bin/env python3
"""
update_style_rule.py — 风格规则持久化工具

在叙事空间创作系统中，当 Orchestrator 检测到用户的风格偏好修改请求
并生成 JSON action 后，运行本脚本将规则写入对应的持久存储。

支持三种输入模式：
  Mode A: --json-file path.json        从文件读取 JSON（最安全）
  Mode B: --scope X --category X --rule "..."   手动指定参数
  Mode C: 无参数自动检测              扫描 .xushikj/style_actions/pending_*.json

用法 / Usage:
  python update_style_rule.py --project-dir .
  python update_style_rule.py --project-dir . --json-file pending_001.json
  python update_style_rule.py --project-dir . --scope global --category banned_words --rule "..."
  python update_style_rule.py --project-dir . --dry-run
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


def _reconfigure_stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="风格规则持久化工具 — 将 Orchestrator 输出的风格规则写入对应层级",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
输入模式:
  Mode A: --json-file              从文件读取 JSON（推荐，无 Shell 转义问题）
  Mode B: --scope + --category + --rule  手动指定（适合脚本调用）
  Mode C: 无参数                   自动扫描 .xushikj/style_actions/pending_*.json

作用域:
  global   → ~/.narrativespace/global_author_dna.yaml（跨项目全局）
  project  → .xushikj/config/style_rules.yaml（仅本项目）
  cycle    → .xushikj/style_logs/cycle_quirks.md（仅本卷）
""",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("."),
        help="项目根目录（.xushikj/ 所在位置），默认当前目录",
    )
    parser.add_argument(
        "--json-file",
        type=Path,
        metavar="FILE",
        help="Mode A：包含 JSON action 对象的文件路径",
    )
    parser.add_argument(
        "--scope",
        choices=["global", "project", "cycle"],
        help="Mode B：规则作用域（global=全局 | project=本书 | cycle=短期）",
    )
    parser.add_argument(
        "--category",
        choices=["banned_words", "sentence_preferences", "value_baselines", "rhythm_preferences"],
        help="Mode B：规则类别",
    )
    parser.add_argument(
        "--rule",
        help="Mode B：规则正文（自然语言）",
    )
    parser.add_argument(
        "--weight",
        type=int,
        default=100,
        metavar="N",
        help="规则初始权重 0-100（默认100）",
    )
    parser.add_argument(
        "--global-dna-path",
        type=Path,
        metavar="PATH",
        help="全局 DNA 文件路径（默认：$NARRATIVESPACE_GLOBAL_PATH → ~/.narrativespace/global_author_dna.yaml）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅显示将要执行的操作，不实际写文件",
    )
    return parser


# ─── JSON 解析 ───────────────────────────────────────────────────────────────

def extract_action_json(text: str) -> dict | None:
    """
    从文本中提取 {"action": "update_style", ...} JSON 对象。
    兼容：markdown fences、LLM 前置废话、Windows 换行符。
    """
    # 尝试直接解析整个文本
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("action") == "update_style":
            return data
    except json.JSONDecodeError:
        pass

    # 正则提取：支持嵌套括号，兼容 markdown ```json ... ``` 包裹
    pattern = r'\{[^{}]*"action"\s*:\s*"update_style"[^{}]*\}'
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        try:
            data = json.loads(match)
            if isinstance(data, dict) and data.get("action") == "update_style":
                return data
        except json.JSONDecodeError:
            continue

    return None


# ─── YAML 读写 ──────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    """加载 YAML 文件，返回 dict；文件不存在返回 {}。"""
    if not path.exists():
        return {}
    if not _HAS_YAML:
        print("警告：未安装 PyYAML，无法加载 YAML 文件。请运行: pip install pyyaml", file=sys.stderr)
        return {}
    try:
        content = path.read_text(encoding="utf-8")
        result = yaml.safe_load(content)
        return result if isinstance(result, dict) else {}
    except Exception as exc:
        print(f"警告：YAML 解析失败 {path}: {exc}", file=sys.stderr)
        return {}


def dump_yaml(data: dict, path: Path) -> None:
    """将 dict 写入 YAML 文件（保留 Unicode，不使用默认流格式）。"""
    if not _HAS_YAML:
        raise RuntimeError("PyYAML 未安装，无法写入 YAML 文件。请运行: pip install pyyaml")
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ─── 全局路径解析 ──────────────────────────────────────────────────────────

def resolve_global_dna_path(args_global_dna_path: Path | None) -> Path:
    """解析全局 DNA 文件路径（优先级：参数 → 环境变量 → 默认）。"""
    if args_global_dna_path is not None:
        return args_global_dna_path
    env_val = os.environ.get("NARRATIVESPACE_GLOBAL_PATH")
    if env_val:
        return Path(env_val) / "global_author_dna.yaml"
    return Path.home() / ".narrativespace" / "global_author_dna.yaml"


# ─── 冲突检测 ──────────────────────────────────────────────────────────────

_POSITIVE_KEYWORDS = {"必须", "要求", "鼓励", "增加", "强调", "保持", "使用", "应该"}
_NEGATIVE_KEYWORDS = {"禁止", "不要", "避免", "减少", "删除", "不得", "杜绝", "严禁"}


def _detect_polarity(rule_text: str) -> str:
    """粗判规则极性：positive / negative / unknown。"""
    has_pos = any(kw in rule_text for kw in _POSITIVE_KEYWORDS)
    has_neg = any(kw in rule_text for kw in _NEGATIVE_KEYWORDS)
    if has_neg and not has_pos:
        return "negative"
    if has_pos and not has_neg:
        return "positive"
    return "unknown"


def check_conflict(new_rule: str, existing_rules: list[dict]) -> list[str]:
    """
    检测新规则与现有规则是否存在极性冲突。
    返回冲突描述列表（空表示无冲突）。
    """
    warnings = []
    new_polarity = _detect_polarity(new_rule)
    if new_polarity == "unknown":
        return warnings

    for existing in existing_rules:
        ex_rule = existing.get("rule", "")
        ex_polarity = _detect_polarity(ex_rule)
        if ex_polarity == "unknown":
            continue
        if new_polarity != ex_polarity:
            # 找出是否有共同关键词（内容上可能相关）
            new_words = set(re.findall(r'[\w]+', new_rule))
            ex_words = set(re.findall(r'[\w]+', ex_rule))
            overlap = new_words & ex_words - {"的", "了", "在", "是", "有", "不", "要", "可", "就", "和", "或"}
            if len(overlap) >= 2:
                warnings.append(
                    f"潜在冲突：新规则 [{new_polarity}] vs 现有规则 [{ex_polarity}]\n"
                    f"  新: {new_rule[:60]}\n"
                    f"  旧: {ex_rule[:60]}\n"
                    f"  共同词: {', '.join(list(overlap)[:5])}"
                )
    return warnings


# ─── 三种作用域写入 ──────────────────────────────────────────────────────────

def _generate_rule_id(category: str, existing_rules: list[dict]) -> str:
    """生成下一个规则 ID，格式：前缀_NNN。"""
    prefix_map = {
        "banned_words": "gba",
        "sentence_preferences": "gsp",
        "value_baselines": "gvb",
        "rhythm_preferences": "grp",
    }
    prefix = prefix_map.get(category, "grule")
    existing_ids = {r.get("id", "") for r in existing_rules}
    for i in range(1, 200):
        candidate = f"{prefix}_{i:03d}"
        if candidate not in existing_ids:
            return candidate
    return f"{prefix}_{len(existing_rules) + 1:03d}"


def apply_to_global(
    global_path: Path,
    category: str,
    rule_text: str,
    weight: int,
    dry_run: bool,
) -> None:
    """写入全局 DNA 文件。"""
    global_path.parent.mkdir(parents=True, exist_ok=True)

    # 读取现有全局 DNA
    data = load_yaml(global_path) if global_path.exists() else {}
    if not isinstance(data.get(category), list):
        data.setdefault(category, [])

    rules: list[dict] = data[category]

    # 重复检测
    for existing in rules:
        if existing.get("rule", "").strip() == rule_text.strip():
            print(f"[skip] 规则已存在于全局 DNA ({category})，跳过写入。")
            print(f"       已有 ID: {existing.get('id')}")
            return

    # 冲突检测
    conflicts = check_conflict(rule_text, rules)
    for warning in conflicts:
        print(f"[warn] ⚠️  {warning}")

    rule_id = _generate_rule_id(category, rules)
    new_rule = {
        "id": rule_id,
        "rule": rule_text,
        "weight": weight,
        "last_triggered_vol": None,
        "created_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
        "trigger_count": 0,
    }

    if dry_run:
        print(f"[dry-run] 将追加到全局 DNA {global_path}")
        print(f"          类别: {category}")
        print(f"          规则: {new_rule}")
        return

    rules.append(new_rule)
    dump_yaml(data, global_path)
    print(f"[write] 已写入全局 DNA: {global_path}")
    print(f"        ID: {rule_id} | 类别: {category}")


def apply_to_project(
    xushikj: Path,
    category: str,
    rule_text: str,
    weight: int,
    dry_run: bool,
) -> None:
    """写入项目级 style_rules.yaml 的 user_additions 区域。"""
    style_rules_path = xushikj / "config" / "style_rules.yaml"
    if not style_rules_path.exists():
        print(f"[warn] style_rules.yaml 不存在: {style_rules_path}", file=sys.stderr)
        return

    data = load_yaml(style_rules_path)
    user_additions = data.setdefault("user_additions", {})
    cat_list: list[dict] = user_additions.setdefault(category, [])

    # 重复检测
    for existing in cat_list:
        if existing.get("rule", "").strip() == rule_text.strip():
            print(f"[skip] 规则已存在于 style_rules.yaml user_additions ({category})，跳过。")
            return

    rule_id = _generate_rule_id(category, cat_list)
    new_rule = {
        "id": rule_id,
        "rule": rule_text,
        "weight": weight,
        "created_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
    }

    if dry_run:
        print(f"[dry-run] 将追加到 style_rules.yaml user_additions[{category}]")
        print(f"          规则: {new_rule}")
        return

    cat_list.append(new_rule)
    dump_yaml(data, style_rules_path)
    print(f"[write] 已写入 style_rules.yaml user_additions[{category}]")
    print(f"        ID: {rule_id}")


def apply_to_cycle(
    xushikj: Path,
    rule_text: str,
    dry_run: bool,
) -> None:
    """追加规则到 cycle_quirks.md 的「本卷临时规则」区域。"""
    cycle_path = xushikj / "style_logs" / "cycle_quirks.md"
    if not cycle_path.exists():
        print(f"[warn] cycle_quirks.md 不存在: {cycle_path}，将创建", file=sys.stderr)
        cycle_path.parent.mkdir(parents=True, exist_ok=True)
        cycle_path.write_text(
            "# 短期风格覆写 (Cycle Quirks)\n\n## 本卷临时规则\n\n",
            encoding="utf-8",
        )

    content = cycle_path.read_text(encoding="utf-8")
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    new_line = f"- [{timestamp}] {rule_text}\n"

    # 在 ## 本卷临时规则 段落内追加
    target = "## 本卷临时规则"
    if target in content:
        idx = content.index(target) + len(target)
        # 跳过紧接的注释行
        after = content[idx:]
        # 在第一个非注释、非空行前插入
        lines = after.split("\n")
        insert_at = 1
        for i, line in enumerate(lines[1:], 1):
            if line.startswith("<!--") or line.strip() == "":
                insert_at = i + 1
            else:
                break
        lines.insert(insert_at, new_line.rstrip())
        new_content = content[:idx] + "\n".join(lines)
    else:
        new_content = content + f"\n{target}\n\n{new_line}"

    if dry_run:
        print(f"[dry-run] 将追加到 cycle_quirks.md:")
        print(f"          {new_line.strip()}")
        return

    cycle_path.write_text(new_content, encoding="utf-8")
    print(f"[write] 已追加到 cycle_quirks.md")
    print(f"        规则: {rule_text[:80]}")


# ─── 主流程 ──────────────────────────────────────────────────────────────────

def _process_action(
    action: dict,
    project_dir: Path,
    global_dna_path: Path,
    dry_run: bool,
) -> bool:
    """处理单条 action 字典，返回是否成功。"""
    xushikj = project_dir / ".xushikj"

    scope = action.get("scope", "").lower()
    category = action.get("category", "")
    rule_text = action.get("rule", "").strip()
    weight = int(action.get("weight", 100))

    if not scope or not rule_text:
        print(f"[error] action 缺少必要字段 (scope 或 rule): {action}", file=sys.stderr)
        return False

    valid_categories = {"banned_words", "sentence_preferences", "value_baselines", "rhythm_preferences"}
    if scope in ("global", "project") and category not in valid_categories:
        print(f"[warn] 类别 '{category}' 不在标准列表 {valid_categories}，将使用 'sentence_preferences' 作为默认")
        category = "sentence_preferences"

    print(f"\n处理规则：scope={scope} | category={category}")
    print(f"  内容: {rule_text[:100]}")

    if scope == "global":
        apply_to_global(global_dna_path, category, rule_text, weight, dry_run)
        # 同步本地副本
        local_copy = xushikj / "config" / "global_author_dna.yaml"
        if global_dna_path != local_copy and global_dna_path.exists() and not dry_run:
            import shutil
            shutil.copy2(global_dna_path, local_copy)
            print(f"[sync] 已同步本地副本: config/global_author_dna.yaml")

    elif scope == "project":
        if not xushikj.exists():
            print(f"[error] .xushikj/ 不存在: {xushikj}", file=sys.stderr)
            return False
        apply_to_project(xushikj, category, rule_text, weight, dry_run)

    elif scope == "cycle":
        if not xushikj.exists():
            print(f"[error] .xushikj/ 不存在: {xushikj}", file=sys.stderr)
            return False
        apply_to_cycle(xushikj, rule_text, dry_run)

    else:
        print(f"[error] 无效的 scope: {scope}（应为 global / project / cycle）", file=sys.stderr)
        return False

    return True


def main() -> None:
    _reconfigure_stdout_utf8()
    parser = build_arg_parser()
    args = parser.parse_args()

    project_dir = args.project_dir.resolve()
    dry_run: bool = args.dry_run
    global_dna_path = resolve_global_dna_path(
        args.global_dna_path if hasattr(args, "global_dna_path") else None
    )

    if not _HAS_YAML:
        print("错误: PyYAML 未安装。请运行: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    print("叙事空间 — 风格规则持久化工具 v8.5")
    print(f"项目目录: {project_dir}")
    print(f"全局 DNA: {global_dna_path}")
    if dry_run:
        print("[dry-run 模式] 不会实际写入文件")
    print("-" * 50)

    # ── Mode A: --json-file ──────────────────────────────────────────────────
    if args.json_file:
        jf = args.json_file if args.json_file.is_absolute() else (project_dir / args.json_file)
        if not jf.exists():
            print(f"[error] JSON 文件不存在: {jf}", file=sys.stderr)
            sys.exit(1)
        text = jf.read_text(encoding="utf-8")
        action = extract_action_json(text)
        if not action:
            print(f"[error] 无法从 {jf} 提取有效的 update_style JSON", file=sys.stderr)
            sys.exit(1)
        _process_action(action, project_dir, global_dna_path, dry_run)
        return

    # ── Mode B: explicit params ──────────────────────────────────────────────
    if args.scope and args.rule:
        action = {
            "action": "update_style",
            "scope": args.scope,
            "category": args.category or "sentence_preferences",
            "rule": args.rule,
            "weight": args.weight,
        }
        _process_action(action, project_dir, global_dna_path, dry_run)
        return

    # ── Mode C: auto-detect pending_*.json ─────────────────────────────────
    xushikj = project_dir / ".xushikj"
    actions_dir = xushikj / "style_actions"
    processed_dir = actions_dir / "processed"

    if not actions_dir.exists():
        print(f"[info] style_actions/ 目录不存在: {actions_dir}")
        print("  请使用 --json-file 或 --scope + --rule 模式")
        parser.print_help()
        sys.exit(0)

    pending_files = sorted(actions_dir.glob("pending_*.json"))
    if not pending_files:
        print(f"[info] 未发现 pending_*.json 文件 in {actions_dir}")
        print("  创建方式：将 Orchestrator 生成的 JSON 保存为 pending_001.json")
        sys.exit(0)

    processed_dir.mkdir(exist_ok=True)
    success_count = 0
    for pf in pending_files:
        print(f"\n处理文件: {pf.name}")
        text = pf.read_text(encoding="utf-8")
        action = extract_action_json(text)
        if not action:
            print(f"  [error] 无法提取 JSON，跳过: {pf.name}", file=sys.stderr)
            continue
        ok = _process_action(action, project_dir, global_dna_path, dry_run)
        if ok and not dry_run:
            dest = processed_dir / pf.name
            pf.rename(dest)
            print(f"  [done] 已移至 processed/{pf.name}")
            success_count += 1

    print(f"\n完成：已处理 {success_count}/{len(pending_files)} 个文件")


if __name__ == "__main__":
    main()
