#!/usr/bin/env python3
"""
consolidate_dna.py — DNA 提纯与权重衰减工具

对全局作者 DNA 执行：
  Phase A: 加载全局 DNA + 项目 DNA 文件
  Phase B: 语义去重（L1 Ollama 余弦相似度 / L2 精确匹配 / L3 跳过）
  Phase C: 冲突检测（极性分析，标记人工确认项）
  Phase D: 权重衰减（长期未触发的规则权重下降，低于阈值归档）
  Phase E: Token 预算强制执行（超过上限按 weight*recency 排序归档）
  Phase F: 写回（更新 global_author_dna.yaml 全局 + 本地副本）

用法 / Usage:
  python consolidate_dna.py --project-dir . --current-volume 3
  python consolidate_dna.py --project-dir . --current-volume 3 --dry-run
  python consolidate_dna.py --global-dna-path ~/.narrativespace/global_author_dna.yaml --current-volume 3
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# 将 scripts/ 目录加入 path 以便 from rag_index import ...
sys.path.insert(0, str(Path(__file__).parent))

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

try:
    from rag_index import get_embedding, cosine_sim, detect_backend
    _HAS_RAG = True
except ImportError:
    _HAS_RAG = False


def _reconfigure_stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DNA 提纯与权重衰减工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
语义去重降级链（与 RAG 一致）:
  L1: Ollama nomic-embed-text 余弦相似度（需 Ollama 在线且已拉取模型）
  L2: 精确文本匹配（Ollama 不可达时降级）
  L3: 跳过去重（仅执行权重衰减和预算检查）
""",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("."),
        help="项目根目录（.xushikj/ 所在位置），默认当前目录",
    )
    parser.add_argument(
        "--global-dna-path",
        type=Path,
        metavar="PATH",
        help="全局 DNA 文件路径（默认：$NARRATIVESPACE_GLOBAL_PATH → ~/.narrativespace/global_author_dna.yaml）",
    )
    parser.add_argument(
        "--current-volume",
        type=int,
        default=1,
        metavar="N",
        help="当前卷号，用于计算权重衰减（默认 1）",
    )
    parser.add_argument(
        "--decay-threshold",
        type=int,
        default=30,
        metavar="N",
        help="权重归档阈值（低于此值移至 archived_dna.yaml，默认 30）",
    )
    parser.add_argument(
        "--decay-gap",
        type=int,
        default=3,
        metavar="N",
        help="衰减触发最少间隔卷数（current_vol - last_triggered_vol > 此值，默认 3）",
    )
    parser.add_argument(
        "--decay-rate",
        type=float,
        default=0.20,
        metavar="F",
        help="每次衰减幅度（默认 0.20 即 20%%）",
    )
    parser.add_argument(
        "--max-rules",
        type=int,
        default=50,
        metavar="N",
        help="全局 DNA 规则硬上限（超出则强制归档低权重规则，默认 50）",
    )
    parser.add_argument(
        "--sim-threshold",
        type=float,
        default=0.85,
        metavar="F",
        help="语义相似度阈值，超过此值标记为候选重复（默认 0.85）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅显示分析报告，不实际修改文件",
    )
    return parser


# ─── 工具函数 ────────────────────────────────────────────────────────────────

def _resolve_global_dna_path(args_path: Path | None) -> Path:
    if args_path is not None:
        return args_path
    env_val = os.environ.get("NARRATIVESPACE_GLOBAL_PATH")
    if env_val:
        return Path(env_val) / "global_author_dna.yaml"
    return Path.home() / ".narrativespace" / "global_author_dna.yaml"


def _load_yaml(path: Path) -> dict:
    if not path.exists() or not _HAS_YAML:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"[warn] YAML 解析失败 {path}: {exc}", file=sys.stderr)
        return {}


def _dump_yaml(data: dict, path: Path) -> None:
    if not _HAS_YAML:
        raise RuntimeError("PyYAML 未安装")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _all_rules(data: dict) -> list[tuple[str, dict]]:
    """返回所有规则 (category, rule_dict) 元组列表。"""
    categories = ["banned_words", "sentence_preferences", "value_baselines", "rhythm_preferences"]
    result = []
    for cat in categories:
        for rule in data.get(cat, []):
            if isinstance(rule, dict):
                result.append((cat, rule))
    return result


def _estimate_tokens(data: dict) -> int:
    """估算全局 DNA 的 token 数（粗算：每条规则约 40 token）。"""
    rule_count = sum(
        len(v) for v in data.values()
        if isinstance(v, list)
    )
    return rule_count * 40


# ─── Phase B: 语义去重 ────────────────────────────────────────────────────────

_POSITIVE_KEYWORDS = {"必须", "要求", "鼓励", "增加", "强调", "保持", "使用", "应该"}
_NEGATIVE_KEYWORDS = {"禁止", "不要", "避免", "减少", "删除", "不得", "杜绝", "严禁"}


def _polarity(text: str) -> str:
    has_pos = any(kw in text for kw in _POSITIVE_KEYWORDS)
    has_neg = any(kw in text for kw in _NEGATIVE_KEYWORDS)
    if has_neg and not has_pos:
        return "negative"
    if has_pos and not has_neg:
        return "positive"
    return "unknown"


def _dedup_l1_semantic(
    rules: list[tuple[str, dict]],
    sim_threshold: float,
) -> tuple[list[dict], list[dict]]:
    """
    L1 语义去重：使用 Ollama nomic-embed-text 计算规则对的余弦相似度。
    返回 (duplicates, conflicts) 两组标记列表，均为 dict 格式。
    """
    duplicates = []
    conflicts = []

    # 按类别分组
    by_category: dict[str, list[tuple[int, dict]]] = {}
    for i, (cat, rule) in enumerate(rules):
        by_category.setdefault(cat, []).append((i, rule))

    for cat, indexed_rules in by_category.items():
        if len(indexed_rules) < 2:
            continue
        texts = [r.get("rule", "") for _, r in indexed_rules]

        # 批量获取嵌入向量
        print(f"  计算 {cat} 中 {len(texts)} 条规则的语义相似度...")
        embeddings = []
        for text in texts:
            emb = get_embedding(text)
            embeddings.append(emb)

        # 两两比较
        for i in range(len(indexed_rules)):
            for j in range(i + 1, len(indexed_rules)):
                if embeddings[i] is None or embeddings[j] is None:
                    continue
                sim = cosine_sim(embeddings[i], embeddings[j])
                if sim < sim_threshold:
                    continue

                ri = indexed_rules[i][1]
                rj = indexed_rules[j][1]
                pol_i = _polarity(ri.get("rule", ""))
                pol_j = _polarity(rj.get("rule", ""))

                entry = {
                    "category": cat,
                    "rule_a": ri,
                    "rule_b": rj,
                    "similarity": round(sim, 3),
                }

                # 极性相反 → 冲突
                if pol_i != "unknown" and pol_j != "unknown" and pol_i != pol_j:
                    entry["type"] = "conflict"
                    entry["polarity_a"] = pol_i
                    entry["polarity_b"] = pol_j
                    conflicts.append(entry)
                    print(
                        f"  [CONFLICT] sim={sim:.3f} | {pol_i} vs {pol_j}\n"
                        f"    A: {ri.get('rule', '')[:60]}\n"
                        f"    B: {rj.get('rule', '')[:60]}"
                    )
                else:
                    entry["type"] = "duplicate_candidate"
                    duplicates.append(entry)
                    print(
                        f"  [DUP?] sim={sim:.3f}\n"
                        f"    A: {ri.get('rule', '')[:60]}\n"
                        f"    B: {rj.get('rule', '')[:60]}"
                    )

    return duplicates, conflicts


def _dedup_l2_exact(rules: list[tuple[str, dict]]) -> list[dict]:
    """L2 精确去重：找出 rule 字段完全相同的条目。"""
    duplicates = []
    by_category: dict[str, list[tuple[int, dict]]] = {}
    for i, (cat, rule) in enumerate(rules):
        by_category.setdefault(cat, []).append((i, rule))

    for cat, indexed_rules in by_category.items():
        seen: dict[str, dict] = {}
        for _, rule in indexed_rules:
            text = rule.get("rule", "").strip()
            if text in seen:
                duplicates.append({
                    "category": cat,
                    "rule_a": seen[text],
                    "rule_b": rule,
                    "similarity": 1.0,
                    "type": "exact_duplicate",
                })
                print(f"  [EXACT DUP] {cat}: {text[:60]}")
            else:
                seen[text] = rule

    return duplicates


# ─── Phase D: 权重衰减 ────────────────────────────────────────────────────────

def apply_decay(
    data: dict,
    current_vol: int,
    decay_gap: int,
    decay_rate: float,
    decay_threshold: int,
) -> tuple[dict, list[dict]]:
    """
    对所有规则应用权重衰减。
    返回 (updated_data, archived_rules)。
    """
    archived = []
    categories = ["banned_words", "sentence_preferences", "value_baselines", "rhythm_preferences"]

    for cat in categories:
        rules = data.get(cat, [])
        surviving = []
        for rule in rules:
            if not isinstance(rule, dict):
                surviving.append(rule)
                continue

            ltv = rule.get("last_triggered_vol")
            weight = int(rule.get("weight", 100))

            # 检查是否触发衰减
            if ltv is not None and isinstance(ltv, (int, float)):
                gap = current_vol - int(ltv)
                if gap > decay_gap:
                    decay_amount = int(weight * decay_rate)
                    new_weight = max(0, weight - decay_amount)
                    print(
                        f"  [DECAY] {rule.get('id', '?')} | "
                        f"gap={gap}卷 → weight {weight}→{new_weight}"
                    )
                    rule = dict(rule)
                    rule["weight"] = new_weight
                    weight = new_weight

            # 低于阈值 → 归档
            if weight < decay_threshold:
                archived_rule = dict(rule)
                archived_rule["archived_at"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
                archived_rule["archived_reason"] = "weight_decay"
                archived_rule["original_weight"] = weight
                archived_rule["category"] = cat
                archived.append(archived_rule)
                print(f"  [ARCHIVE] {rule.get('id', '?')} | weight={weight} < {decay_threshold}")
            else:
                surviving.append(rule)

        data[cat] = surviving

    return data, archived


# ─── Phase E: Token 预算强制执行 ──────────────────────────────────────────────

def enforce_token_budget(
    data: dict,
    max_rules: int,
    current_vol: int,
) -> tuple[dict, list[dict]]:
    """
    强制执行 Token 预算上限。
    超出 max_rules 时，按 weight * recency_bonus 排序，最低分归档。
    返回 (updated_data, newly_archived)。
    """
    categories = ["banned_words", "sentence_preferences", "value_baselines", "rhythm_preferences"]
    total_rules = sum(len(data.get(cat, [])) for cat in categories)

    if total_rules <= max_rules:
        return data, []

    excess = total_rules - max_rules
    print(f"\n[TOKEN BUDGET] 规则数 {total_rules} > 上限 {max_rules}，需归档 {excess} 条")

    # 计算所有规则的分数
    scored: list[tuple[float, str, dict]] = []
    for cat in categories:
        for rule in data.get(cat, []):
            if not isinstance(rule, dict):
                continue
            weight = float(rule.get("weight", 100))
            ltv = rule.get("last_triggered_vol")
            # recency_bonus: 最近2卷触发过 = 1.0，否则 = 0.8
            if ltv is not None and isinstance(ltv, (int, float)) and (current_vol - int(ltv)) <= 2:
                recency_bonus = 1.0
            else:
                recency_bonus = 0.8
            score = weight * recency_bonus
            scored.append((score, cat, rule))

    # 升序排列，尾部（低分）归档
    scored.sort(key=lambda x: x[0])
    to_archive = scored[:excess]

    archived = []
    for score, cat, rule in to_archive:
        archived_rule = dict(rule)
        archived_rule["archived_at"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        archived_rule["archived_reason"] = "token_budget"
        archived_rule["original_weight"] = rule.get("weight", 100)
        archived_rule["category"] = cat
        archived.append(archived_rule)
        print(f"  [BUDGET ARCHIVE] {rule.get('id', '?')} | score={score:.1f} | {rule.get('rule', '')[:50]}")

        # 从 data 中移除
        data[cat] = [r for r in data.get(cat, []) if r.get("id") != rule.get("id")]

    return data, archived


# ─── Phase F: 写回 ───────────────────────────────────────────────────────────

def write_back(
    data: dict,
    global_path: Path,
    local_copy: Path | None,
    archived_rules: list[dict],
    archived_dna_path: Path,
    dry_run: bool,
) -> None:
    """写回 global_author_dna.yaml（全局+本地副本）和 archived_dna.yaml。"""
    if dry_run:
        total = sum(len(data.get(cat, [])) for cat in
                    ["banned_words", "sentence_preferences", "value_baselines", "rhythm_preferences"])
        print(f"\n[dry-run] 将写回 global_author_dna.yaml，剩余规则: {total}")
        print(f"[dry-run] 将归档 {len(archived_rules)} 条规则到 archived_dna.yaml")
        return

    _dump_yaml(data, global_path)
    print(f"\n[write] 已写回全局 DNA: {global_path}")

    if local_copy and local_copy != global_path:
        _dump_yaml(data, local_copy)
        print(f"[sync] 已同步本地副本: {local_copy}")

    if archived_rules:
        archived_data = _load_yaml(archived_dna_path)
        existing_archived = archived_data.get("archived_rules", [])
        # 避免重复归档
        existing_ids = {r.get("id") for r in existing_archived}
        new_entries = [r for r in archived_rules if r.get("id") not in existing_ids]
        archived_data["archived_rules"] = existing_archived + new_entries
        _dump_yaml(archived_data, archived_dna_path)
        print(f"[write] 已归档 {len(new_entries)} 条规则到: {archived_dna_path}")


# ─── 主流程 ──────────────────────────────────────────────────────────────────

def run_consolidation(
    project_dir: Path,
    global_dna_path: Path | None = None,
    volume: int = 1,
    decay_threshold: int = 30,
    decay_gap: int = 3,
    decay_rate: float = 0.20,
    max_rules: int = 50,
    sim_threshold: float = 0.85,
    dry_run: bool = False,
) -> None:
    """供外部调用的主函数（如 volume_snapshot.py 调用）。"""
    global_path = _resolve_global_dna_path(global_dna_path)
    xushikj = project_dir / ".xushikj"
    local_copy = xushikj / "config" / "global_author_dna.yaml"
    archived_dna_path = xushikj / "config" / "archived_dna.yaml"

    if not global_path.exists():
        print(f"[info] 全局 DNA 文件未找到，跳过提纯: {global_path}")
        return

    if not _HAS_YAML:
        print("[error] PyYAML 未安装，无法执行提纯。请运行: pip install pyyaml", file=sys.stderr)
        return

    print(f"\n{'='*60}")
    print("叙事空间 — DNA 提纯与权重衰减 v8.5")
    print(f"全局 DNA: {global_path}")
    print(f"当前卷: {volume} | 衰减阈值: {decay_threshold} | 衰减间隔: {decay_gap}卷")
    print(f"规则上限: {max_rules} 条 | {'[dry-run]' if dry_run else '[实际执行]'}")
    print('='*60)

    # Phase A: 加载
    print("\n▶ Phase A: 加载全局 DNA")
    data = _load_yaml(global_path)
    if not data:
        print("  全局 DNA 为空，无需提纯")
        return

    all_rules = _all_rules(data)
    print(f"  已加载 {len(all_rules)} 条规则")

    all_archived: list[dict] = []

    # Phase B: 语义去重
    print("\n▶ Phase B: 语义去重")
    duplicates = []
    conflicts = []

    if _HAS_RAG:
        backend_info = detect_backend(xushikj) if xushikj.exists() else {"backend": "none"}
        if backend_info.get("backend") == "ollama":
            print(f"  使用 L1 语义去重（Ollama nomic-embed-text）")
            duplicates, conflicts = _dedup_l1_semantic(all_rules, sim_threshold)
        else:
            print(f"  Ollama 不可达（{backend_info.get('note', '')}），降级到 L2 精确匹配")
            duplicates = _dedup_l2_exact(all_rules)
    else:
        print("  rag_index 模块不可用，使用 L2 精确匹配")
        duplicates = _dedup_l2_exact(all_rules)

    if not duplicates and not conflicts:
        print("  ✓ 未发现重复或冲突")
    if conflicts:
        print(f"\n  ⚠️  发现 {len(conflicts)} 处极性冲突，需要人工确认！")
        print("  冲突规则已输出上方，请手动处理：")
        print("  - 删除其中一条：编辑 global_author_dna.yaml")
        print("  - 或运行 consolidate_dna.py --dry-run 查看详情")
    if duplicates:
        print(f"\n  ⚠️  发现 {len(duplicates)} 处候选重复，建议人工确认后删除低权重版本")

    # Phase C: 冲突提示（不自动处理，强制人工）
    if conflicts:
        print("\n▶ Phase C: 冲突检测结果（需人工处理）")
        for c in conflicts:
            print(f"  [{c['category']}] sim={c['similarity']}")
            print(f"    A [{c['polarity_a']}]: {c['rule_a'].get('rule', '')[:80]}")
            print(f"    B [{c['polarity_b']}]: {c['rule_b'].get('rule', '')[:80]}")

    # Phase D: 权重衰减
    print("\n▶ Phase D: 权重衰减")
    data, decayed_archived = apply_decay(data, volume, decay_gap, decay_rate, decay_threshold)
    if not decayed_archived:
        print("  ✓ 无规则触发衰减归档")
    all_archived.extend(decayed_archived)

    # Phase E: Token 预算
    print(f"\n▶ Phase E: Token 预算检查（上限 {max_rules} 条）")
    data, budget_archived = enforce_token_budget(data, max_rules, volume)
    if not budget_archived:
        remaining = sum(len(data.get(cat, [])) for cat in
                        ["banned_words", "sentence_preferences", "value_baselines", "rhythm_preferences"])
        print(f"  ✓ 规则数 {remaining} ≤ {max_rules}，无需强制归档")
    all_archived.extend(budget_archived)

    # Phase F: 写回
    print("\n▶ Phase F: 写回")
    write_back(data, global_path, local_copy, all_archived, archived_dna_path, dry_run)

    # 摘要
    remaining_total = sum(len(data.get(cat, [])) for cat in
                          ["banned_words", "sentence_preferences", "value_baselines", "rhythm_preferences"])
    estimated_tokens = _estimate_tokens(data)
    print(f"\n提纯完成:")
    print(f"  剩余规则: {remaining_total} 条 | 估算 token: {estimated_tokens}")
    print(f"  归档规则: {len(all_archived)} 条")
    print(f"  冲突待处理: {len(conflicts)} 处（需人工确认）")
    print(f"  重复候选: {len(duplicates)} 处（建议人工确认）")


def main() -> None:
    _reconfigure_stdout_utf8()

    if not _HAS_YAML:
        print("错误: PyYAML 未安装。请运行: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    parser = build_arg_parser()
    args = parser.parse_args()

    run_consolidation(
        project_dir=args.project_dir.resolve(),
        global_dna_path=args.global_dna_path if args.global_dna_path else None,
        volume=args.current_volume,
        decay_threshold=args.decay_threshold,
        decay_gap=args.decay_gap,
        decay_rate=args.decay_rate,
        max_rules=args.max_rules,
        sim_threshold=args.sim_threshold,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
