#!/usr/bin/env python3
"""
rag_index.py — 叙事空间创作系统 本地 RAG 向量检索引擎

向量存储：.xushikj/rag/rag_index.json（每个项目目录独立，不跨项目共享）
向量计算：Ollama localhost:11434 / nomic-embed-text（无需 pip，urllib 直调）

降级链：
  L1 Ollama 余弦检索（nomic-embed-text 已拉取）
  L2 LLM 内联排序（retrieval_index.md 文本供 orchestrator 排序）
  L3 跳过（不阻塞写作流程）

用法:
    python rag_index.py --project-dir /path/to/project --check-backend
    python rag_index.py --project-dir /path/to/project --build
    python rag_index.py --project-dir /path/to/project --build --force
    python rag_index.py --project-dir /path/to/project --add-chapter 15
    python rag_index.py --project-dir /path/to/project --query "主角觉醒" --char-ids char_001,char_002 --top-k 3
    python rag_index.py --project-dir /path/to/project --check-staleness
"""

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib import request as urllib_request
from urllib.error import URLError

# ─── 常量 ─────────────────────────────────────────────────────────────────────
OLLAMA_BASE    = "http://localhost:11434"
EMBED_MODEL    = "nomic-embed-text"
SCHEMA_VER     = "8.2"
INDEX_FILE     = "rag/rag_index.json"
RETRIEVAL_FILE = "rag/retrieval_index.md"


def _reconfigure_stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ─── 1. 后端探测 ──────────────────────────────────────────────────────────────

def detect_backend(xushikj: Path) -> dict:
    """
    探测可用的嵌入向量后端。

    返回: {"backend": "ollama"|"llm"|"none", "model": str|None, "note": str}

    ollama → L1 真实余弦检索
    llm    → L2 LLM 内联排序（retrieval_index.md 存在时）
    none   → L3 跳过
    """
    # 尝试 L1：连接 Ollama
    try:
        req = urllib_request.Request(
            f"{OLLAMA_BASE}/api/tags",
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib_request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = [m.get("name", "") for m in data.get("models", [])]
        # nomic-embed-text 可能以 "nomic-embed-text:latest" 形式命名
        has_model = any(EMBED_MODEL in m for m in models)
        if not has_model:
            return {
                "backend": "llm",
                "model": None,
                "note": (
                    f"Ollama 可达但未找到 {EMBED_MODEL}，"
                    f"请执行: ollama pull {EMBED_MODEL}"
                ),
            }
        return {"backend": "ollama", "model": EMBED_MODEL, "note": "Ollama L1 就绪"}
    except (URLError, OSError, json.JSONDecodeError):
        pass

    # L2：retrieval_index.md 是否存在（LLM 内联排序降级）
    if (xushikj / RETRIEVAL_FILE).exists():
        return {
            "backend": "llm",
            "model": None,
            "note": "Ollama 不可达，retrieval_index.md 存在 → L2 LLM 内联排序",
        }

    return {
        "backend": "none",
        "model": None,
        "note": "Ollama 不可达，retrieval_index.md 不存在 → L3 跳过",
    }


# ─── 2. 嵌入生成 ──────────────────────────────────────────────────────────────

def get_embedding(text: str, timeout: int = 15) -> Optional[list]:
    """
    调用 Ollama REST API 获取文本嵌入向量（768 维 float）。
    失败返回 None，调用方负责降级处理。
    """
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode("utf-8")
    req = urllib_request.Request(
        f"{OLLAMA_BASE}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        embedding = data.get("embedding")
        if isinstance(embedding, list) and len(embedding) > 0:
            return embedding
        return None
    except (URLError, OSError, json.JSONDecodeError, KeyError):
        return None


# ─── 3. 纯 Python 余弦相似度 ──────────────────────────────────────────────────

def cosine_sim(a: list, b: list) -> float:
    """纯 stdlib math 计算余弦相似度，无需 numpy。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ─── 4. 实体标签提取（防串文的基础） ─────────────────────────────────────────

def extract_entities(xushikj: Path, n: int) -> dict:
    """
    为第 n 章提取实体标签（char_IDs + loc_IDs + item_IDs）。

    优先级：
      1. kb_diffs/chapter_{N}_diff.json —— 最准确
      2. scenes/*/scene_plans/chapter_{N}.md —— 场景规划中的角色列表
      3. knowledge_base.json 名称匹配 —— 最后兜底

    返回: {"characters": [...], "locations": [...], "items": [...]}
    """
    entities: dict = {"characters": [], "locations": [], "items": []}

    # 优先级 1：kb_diffs
    for pattern in [f"kb_diffs/chapter_{n:03d}_diff.json", f"kb_diffs/chapter_{n}_diff.json"]:
        diff_file = xushikj / pattern
        if diff_file.exists():
            try:
                diff = json.loads(diff_file.read_text(encoding="utf-8"))
                changes = diff.get("changes", {})
                for etype in ("characters", "locations", "items"):
                    ids = [k for k in changes.get(etype, {}).keys() if not k.startswith("_")]
                    entities[etype] = ids
                if any(entities.values()):
                    return entities
            except (json.JSONDecodeError, KeyError):
                pass

    # 优先级 2：scene_plans（glob 跨 cycle_id 目录）
    for scene_file in (xushikj / "scenes").rglob(f"chapter_{n:03d}.md"):
        try:
            content = scene_file.read_text(encoding="utf-8")
            char_m = re.search(
                r"(?:涉及角色|char[_\-]ids?|char_IDs)[：:]\s*([\w,\s_]+)", content, re.I
            )
            loc_m = re.search(
                r"(?:地点.*?IDs?|loc[_\-]ids?|loc_IDs)[：:]\s*([\w,\s_]+)", content, re.I
            )
            if char_m:
                entities["characters"] = [
                    c.strip() for c in re.split(r"[,，\s]+", char_m.group(1)) if c.strip()
                ]
            if loc_m:
                entities["locations"] = [
                    l.strip() for l in re.split(r"[,，\s]+", loc_m.group(1)) if l.strip()
                ]
            if any(entities.values()):
                return entities
        except OSError:
            pass

    # 优先级 3：knowledge_base 名称匹配
    kb_file      = xushikj / "knowledge_base.json"
    summary_path = _find_summary(xushikj, n)
    if kb_file.exists() and summary_path:
        try:
            kb           = json.loads(kb_file.read_text(encoding="utf-8"))
            summary_text = summary_path.read_text(encoding="utf-8")
            chars = kb.get("entities", {}).get("characters", {})
            locs  = kb.get("entities", {}).get("locations", {})
            for cid, cdata in chars.items():
                if not cid.startswith("_") and cdata.get("name", "") in summary_text:
                    entities["characters"].append(cid)
            for lid, ldata in locs.items():
                if not lid.startswith("_") and ldata.get("name", "") in summary_text:
                    entities["locations"].append(lid)
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    return entities


# ─── 5. embed_text 构建 ───────────────────────────────────────────────────────

def _find_summary(xushikj: Path, n: int) -> Optional[Path]:
    """查找章节摘要文件，容忍零填充与非零填充两种命名。"""
    for pat in [f"chapter_{n:03d}_summary.md", f"chapter_{n}_summary.md"]:
        p = xushikj / "summaries" / pat
        if p.exists():
            return p
    return None


def _find_anchor(xushikj: Path, n: int) -> Optional[Path]:
    """查找章节记忆锚点文件。"""
    for pat in [f"anchor_chapter_{n:03d}.md", f"anchor_chapter_{n}.md"]:
        p = xushikj / "anchors" / pat
        if p.exists():
            return p
    return None


def _read_state(xushikj: Path) -> dict:
    """安全读取 state.json，失败返回空 dict。"""
    state_file = xushikj / "state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def build_embed_text(xushikj: Path, n: int) -> tuple:
    """
    构建第 n 章的 embed_text 和 strand。

    embed_text 格式：
      第{N}章 [{strand} 卷:{V}] {summary前300字} | 关键转折: {xxx} | 悬念: {xxx}

    返回: (embed_text: str, strand: str)  — 失败时返回 ("", "")
    """
    summary_path = _find_summary(xushikj, n)
    if not summary_path:
        return ("", "")

    summary = summary_path.read_text(encoding="utf-8").strip()

    state  = _read_state(xushikj)
    volume = state.get("planning_state", {}).get("current_volume", 1)

    # 从 strand_tracker.history 读取该章 strand
    strand = "Quest"
    for entry in state.get("strand_tracker", {}).get("history", []):
        if entry.get("chapter") == n:
            strand = entry.get("strand", "Quest")
            break

    # 提取锚点关键转折和悬念（可选）
    anchor_extras = ""
    anchor_path = _find_anchor(xushikj, n)
    if anchor_path:
        try:
            anchor_text = anchor_path.read_text(encoding="utf-8")
            for section, label in [
                ("## 关键转折", "关键转折"),
                ("## 最紧迫悬念", "悬念"),
            ]:
                m = re.search(
                    rf"{re.escape(section)}\s*\n(.*?)(?=\n##|\Z)", anchor_text, re.S
                )
                if m:
                    excerpt = m.group(1).strip().split("\n")[0][:80]
                    # 过滤掉注释行和空行
                    if excerpt and not excerpt.startswith("<!--") and not excerpt.startswith("（"):
                        anchor_extras += f" | {label}: {excerpt}"
        except OSError:
            pass

    embed_text = f"第{n}章 [{strand} 卷:{volume}] {summary[:300]}{anchor_extras}"
    return (embed_text, strand)


# ─── 6. retrieval_index.md 构建 ───────────────────────────────────────────────

def _build_retrieval_line(n: int, volume: int, strand: str, entities: dict, excerpt: str) -> str:
    """构建 retrieval_index.md 的单行记录。"""
    char_str = ",".join(entities.get("characters", []))
    loc_str  = ",".join(entities.get("locations", []))
    clean    = excerpt.strip().replace("\n", " ")[:60]
    return f"Ch.{n:03d} [vol:{volume}][{strand}][C:{char_str}][L:{loc_str}] {clean}"


def write_retrieval_index(xushikj: Path, entries: list) -> None:
    """覆盖写入完整的 rag/retrieval_index.md。"""
    lines = []
    for e in sorted(entries, key=lambda x: x["chapter"]):
        vol    = e.get("volume", 1)
        strand = e.get("strand", "Quest")
        ents   = e.get("entities", {})
        sp     = _find_summary(xushikj, e["chapter"])
        excerpt = sp.read_text(encoding="utf-8").strip().split("\n")[0][:60] if sp else ""
        lines.append(_build_retrieval_line(e["chapter"], vol, strand, ents, excerpt))
    out = xushikj / RETRIEVAL_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_retrieval_line(xushikj: Path, entry: dict) -> None:
    """更新 retrieval_index.md 中单章对应的行（追加或替换）。"""
    retrieval_path = xushikj / RETRIEVAL_FILE
    n      = entry["chapter"]
    vol    = entry.get("volume", 1)
    strand = entry.get("strand", "Quest")
    ents   = entry.get("entities", {})
    sp     = _find_summary(xushikj, n)
    excerpt = sp.read_text(encoding="utf-8").strip().split("\n")[0][:60] if sp else ""
    new_line = _build_retrieval_line(n, vol, strand, ents, excerpt)

    if retrieval_path.exists():
        lines    = retrieval_path.read_text(encoding="utf-8").splitlines()
        prefix   = f"Ch.{n:03d} "
        replaced = False
        for i, line in enumerate(lines):
            if line.startswith(prefix):
                lines[i] = new_line
                replaced  = True
                break
        if not replaced:
            lines.append(new_line)
            lines.sort()
        retrieval_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        retrieval_path.parent.mkdir(parents=True, exist_ok=True)
        retrieval_path.write_text(new_line + "\n", encoding="utf-8")


# ─── 7. 全量构建 ──────────────────────────────────────────────────────────────

def build_index(xushikj: Path, force: bool = False) -> None:
    """
    全量构建 rag_index.json 和 retrieval_index.md。

    若 embed_text 未变化且 force=False：复用现有嵌入向量（节省 Ollama 调用）。
    """
    rag_dir = xushikj / "rag"
    rag_dir.mkdir(parents=True, exist_ok=True)
    index_path = xushikj / INDEX_FILE

    # 读取现有索引（增量复用）
    existing: dict = {}  # chapter → entry
    if index_path.exists() and not force:
        try:
            old = json.loads(index_path.read_text(encoding="utf-8"))
            for e in old.get("entries", []):
                existing[e["chapter"]] = e
        except (json.JSONDecodeError, KeyError):
            pass

    state      = _read_state(xushikj)
    kb_version = state.get("knowledge_base_version", 0)
    volume     = state.get("planning_state", {}).get("current_volume", 1)

    backend_info = detect_backend(xushikj)
    use_ollama   = backend_info["backend"] == "ollama"

    if not use_ollama:
        print(
            f"  [warn]  {backend_info['note']}\n"
            "  [info]  将只构建 retrieval_index.md（L2 降级模式），跳过嵌入向量。",
            file=sys.stderr,
        )

    summaries_dir = xushikj / "summaries"
    if not summaries_dir.exists():
        print("  [warn]  summaries/ 目录不存在，无内容可索引。", file=sys.stderr)
        return

    chapter_nums = sorted(
        int(m.group(1))
        for f in summaries_dir.glob("chapter_*_summary.md")
        if (m := re.search(r"chapter_(\d+)_summary", f.name))
    )
    if not chapter_nums:
        print("  [info]  未找到任何摘要文件，索引为空。", file=sys.stderr)
        return

    entries = []
    for n in chapter_nums:
        embed_text, strand = build_embed_text(xushikj, n)
        if not embed_text:
            print(f"  [skip]  第{n}章摘要为空，跳过。", file=sys.stderr)
            continue

        ents      = extract_entities(xushikj, n)
        embedding = None

        if use_ollama:
            old_entry = existing.get(n)
            if (
                old_entry
                and old_entry.get("embed_text") == embed_text
                and old_entry.get("embedding")
                and not force
            ):
                embedding = old_entry["embedding"]
                print(f"  [cache] 第{n}章 嵌入向量复用", file=sys.stderr)
            else:
                embedding = get_embedding(embed_text)
                if embedding:
                    print(f"  [embed] 第{n}章 ✓ dim={len(embedding)}", file=sys.stderr)
                else:
                    print(
                        f"  [warn]  第{n}章 嵌入失败，条目仅含文本（L2 可用）",
                        file=sys.stderr,
                    )

        entries.append({
            "chapter":      n,
            "volume":       volume,
            "strand":       strand,
            "embed_text":   embed_text,
            "embedding":    embedding,
            "entities":     ents,
            "summary_path": f"summaries/chapter_{n:03d}_summary.md",
            "anchor_path":  f"anchors/anchor_chapter_{n:03d}.md",
        })

    index_data = {
        "schema_version":      SCHEMA_VER,
        "built_at":            datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kb_version_at_build": kb_version,
        "embedding_model":     EMBED_MODEL if use_ollama else None,
        "embedding_dim":       len(entries[0]["embedding"]) if (entries and entries[0].get("embedding")) else 0,
        "total_entries":       len(entries),
        "backend_used":        backend_info["backend"],
        "entries":             entries,
    }
    index_path.write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [OK]    rag_index.json 已写入 {len(entries)} 条记录。")

    write_retrieval_index(xushikj, entries)
    print(f"  [OK]    retrieval_index.md 已同步（{len(entries)} 行）。")

    _update_rag_state(xushikj, entries, backend_info["backend"])


# ─── 8. 增量追加单章 ──────────────────────────────────────────────────────────

def add_chapter(xushikj: Path, n: int) -> None:
    """
    增量追加或覆盖第 n 章的索引条目。
    适合写完每章后立即调用，毫秒级响应。
    """
    rag_dir    = xushikj / "rag"
    rag_dir.mkdir(parents=True, exist_ok=True)
    index_path = xushikj / INDEX_FILE

    # 读取现有索引
    index_data: dict = {}
    entries:    list = []
    if index_path.exists():
        try:
            index_data = json.loads(index_path.read_text(encoding="utf-8"))
            entries    = index_data.get("entries", [])
        except (json.JSONDecodeError, KeyError):
            pass

    embed_text, strand = build_embed_text(xushikj, n)
    if not embed_text:
        print(f"  [warn]  第{n}章摘要不存在，无法索引。", file=sys.stderr)
        return

    ents         = extract_entities(xushikj, n)
    backend_info = detect_backend(xushikj)
    use_ollama   = backend_info["backend"] == "ollama"
    embedding    = get_embedding(embed_text) if use_ollama else None

    state  = _read_state(xushikj)
    volume = state.get("planning_state", {}).get("current_volume", 1)

    new_entry = {
        "chapter":      n,
        "volume":       volume,
        "strand":       strand,
        "embed_text":   embed_text,
        "embedding":    embedding,
        "entities":     ents,
        "summary_path": f"summaries/chapter_{n:03d}_summary.md",
        "anchor_path":  f"anchors/anchor_chapter_{n:03d}.md",
    }

    replaced = False
    for i, e in enumerate(entries):
        if e["chapter"] == n:
            entries[i] = new_entry
            replaced   = True
            break
    if not replaced:
        entries.append(new_entry)
    entries.sort(key=lambda x: x["chapter"])

    index_data.update({
        "schema_version": SCHEMA_VER,
        "built_at":       datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_entries":  len(entries),
        "backend_used":   backend_info["backend"],
        "entries":        entries,
    })
    index_path.write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _update_retrieval_line(xushikj, new_entry)
    _update_rag_state(xushikj, entries, backend_info["backend"])

    action = "覆盖更新" if replaced else "追加"
    print(
        f"  [OK]    第{n}章索引已{action}"
        f"（strand={strand}, chars={ents['characters']}, locs={ents['locations']}）"
    )


def _update_rag_state(xushikj: Path, entries: list, backend: str) -> None:
    """更新 state.json 中的 rag_state 字段（非阻塞）。"""
    state_file = xushikj / "state.json"
    if not state_file.exists():
        return
    try:
        state     = json.loads(state_file.read_text(encoding="utf-8"))
        rag_state = state.setdefault("rag_state", {})
        rag_state["enabled"]              = True
        rag_state["backend"]              = backend
        rag_state["total_indexed"]        = len(entries)
        rag_state["last_indexed_chapter"] = max((e["chapter"] for e in entries), default=0)
        rag_state["index_version"]        = rag_state.get("index_version", 0) + 1
        rag_state["fallback_level"]       = (
            "L1" if backend == "ollama" else ("L2" if backend == "llm" else "L3")
        )
        state["updated_at"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except (json.JSONDecodeError, KeyError, OSError):
        pass


# ─── 9. 查询（四层防串文隔离） ───────────────────────────────────────────────

def query(
    xushikj:         Path,
    text:            str,
    char_ids:        list,
    loc_ids:         list,
    top_k:           int = 3,
    current_chapter: int = 0,
) -> list:
    """
    带实体隔离锁的 RAG 语义检索。

    四层隔离：
      Layer 1 硬实体过滤  — char_IDs 零交集 → 直接排除（核心防串文）
      Layer 2 时效排除    — 最近 2 章（已由 recent_summaries 覆盖）排除
      Layer 3 余弦相似度  — Ollama L1 或 L2 文本相关性降级
      Layer 4 多样性上限  — 每个主角色最多贡献 max(2, top_k//2) 条

    返回: [{chapter, strand, entities, summary_path, embed_text, score, fallback_level}]
    """
    index_path = xushikj / INDEX_FILE
    if not index_path.exists():
        return []

    try:
        index_data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    all_entries = index_data.get("entries", [])
    if not all_entries:
        return []

    # ── Layer 2：时效排除 ─────────────────────────────────────────────────────
    excluded = {current_chapter, current_chapter - 1, current_chapter - 2}
    candidates = [e for e in all_entries if e["chapter"] not in excluded]

    # ── Layer 1：硬实体过滤（防串文核心） ────────────────────────────────────
    query_chars = set(char_ids)
    query_locs  = set(loc_ids)
    filtered    = []
    for e in candidates:
        e_chars      = set(e.get("entities", {}).get("characters", []))
        char_overlap = len(e_chars & query_chars)
        # 若 query_chars 非空：必须有角色交集，否则硬排除
        if query_chars and char_overlap == 0:
            continue
        filtered.append(e)

    if not filtered:
        return []

    # ── Layer 3：相似度评分 ───────────────────────────────────────────────────
    backend_info = detect_backend(xushikj)
    use_ollama   = backend_info["backend"] == "ollama"
    query_emb    = None
    if use_ollama:
        query_emb = get_embedding(text)
        if query_emb is None:
            use_ollama = False  # 嵌入失败降级

    scored = []
    for e in filtered:
        if use_ollama and query_emb:
            emb = e.get("embedding")
            if emb:
                score = cosine_sim(query_emb, emb)
            else:
                score = 0.3  # 有索引但无向量（全量 build 时 Ollama 不可用产生）
        else:
            # L2：简单词汇命中率
            safe_text = e.get("embed_text", "")
            hits  = sum(1 for word in text if word in safe_text)
            score = min(hits / max(len(text), 1) * 0.8, 1.0)
        scored.append({**e, "_score": score})

    scored.sort(key=lambda x: x["_score"], reverse=True)

    # ── Layer 4：多样性上限 ───────────────────────────────────────────────────
    per_char: dict = {}
    max_per_char   = max(2, top_k // 2)
    results        = []
    for e in scored:
        if len(results) >= top_k:
            break
        primary_char = (e.get("entities", {}).get("characters") or ["_unknown"])[0]
        cnt = per_char.get(primary_char, 0)
        if cnt >= max_per_char:
            continue
        per_char[primary_char] = cnt + 1
        results.append({
            "chapter":       e["chapter"],
            "strand":        e.get("strand", "Quest"),
            "entities":      e.get("entities", {}),
            "summary_path":  e.get("summary_path", ""),
            "embed_text":    e.get("embed_text", "")[:120],
            "score":         round(e["_score"], 4),
            "fallback_level": "L1" if (use_ollama and e.get("embedding")) else "L2",
        })

    return results


# ─── 10. 新鲜度检测 ───────────────────────────────────────────────────────────

def check_staleness(xushikj: Path) -> dict:
    """
    检测 RAG 索引相对于当前 KB 版本的新鲜度。

    staleness ≤ 0  → ok
    staleness 1-10 → warn（建议重建）
    staleness > 10 → critical（强烈建议重建）
    """
    index_path = xushikj / INDEX_FILE
    if not index_path.exists():
        return {
            "staleness": -1,
            "level": "critical",
            "note": "rag_index.json 不存在，请先执行 --build",
        }
    try:
        index_data     = json.loads(index_path.read_text(encoding="utf-8"))
        built_kb_ver   = index_data.get("kb_version_at_build", 0)
        total_entries  = index_data.get("total_entries", 0)
    except (json.JSONDecodeError, OSError):
        return {"staleness": -1, "level": "critical", "note": "rag_index.json 解析失败"}

    state          = _read_state(xushikj)
    current_kb_ver = state.get("knowledge_base_version", 0)
    staleness      = current_kb_ver - built_kb_ver

    if staleness <= 0:
        return {
            "staleness": 0,
            "level": "ok",
            "note": f"索引新鲜（{total_entries} 条）",
            "total_entries": total_entries,
        }
    elif staleness <= 10:
        return {
            "staleness": staleness,
            "level": "warn",
            "note": f"索引轻微过时（差 {staleness} 个 KB 版本），建议执行 --build",
            "total_entries": total_entries,
        }
    else:
        return {
            "staleness": staleness,
            "level": "critical",
            "note": f"索引严重过时（差 {staleness} 个 KB 版本），强烈建议执行 --build",
            "total_entries": total_entries,
        }


# ─── 11. CLI 入口 ─────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="叙事空间创作系统 本地 RAG 向量检索引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python rag_index.py --project-dir /path/to/project --check-backend
  python rag_index.py --project-dir /path/to/project --build
  python rag_index.py --project-dir /path/to/project --build --force
  python rag_index.py --project-dir /path/to/project --add-chapter 15
  python rag_index.py --project-dir /path/to/project --query "主角觉醒" --char-ids char_001 --current-chapter 16
  python rag_index.py --project-dir /path/to/project --check-staleness
""",
    )
    parser.add_argument(
        "--project-dir", required=True, type=Path,
        help="项目根目录（.xushikj/ 所在目录，非 .xushikj 本身）",
    )
    parser.add_argument("--build", action="store_true", help="全量构建向量索引")
    parser.add_argument(
        "--force", action="store_true",
        help="强制重建所有嵌入，即使 embed_text 未变化（配合 --build 使用）",
    )
    parser.add_argument(
        "--add-chapter", type=int, metavar="N", help="增量追加/更新第 N 章的索引条目",
    )
    parser.add_argument(
        "--query", type=str, metavar="TEXT", help="执行语义检索（建议同时提供 --char-ids）",
    )
    parser.add_argument(
        "--char-ids", type=str, default="",
        help="本章涉及角色 ID（逗号分隔），用于实体锁过滤，空表示宽松模式",
    )
    parser.add_argument(
        "--loc-ids", type=str, default="",
        help="本章涉及地点 ID（逗号分隔）",
    )
    parser.add_argument("--top-k", type=int, default=3, help="返回结果数量（默认 3）")
    parser.add_argument(
        "--current-chapter", type=int, default=0,
        help="当前正在写的章节号（用于时效排除，避免返回最近 2 章）",
    )
    parser.add_argument(
        "--check-backend", action="store_true",
        help="探测 Ollama 可用性，输出后端状态 JSON",
    )
    parser.add_argument(
        "--check-staleness", action="store_true",
        help="检测向量索引的新鲜度，输出状态 JSON",
    )
    return parser


def main() -> None:
    _reconfigure_stdout_utf8()
    parser = build_arg_parser()
    args   = parser.parse_args()

    project_dir = args.project_dir.resolve()
    xushikj     = project_dir / ".xushikj"

    if not xushikj.exists():
        print(f"错误：.xushikj/ 目录不存在: {xushikj}", file=sys.stderr)
        sys.exit(1)

    if args.check_backend:
        print(json.dumps(detect_backend(xushikj), ensure_ascii=False, indent=2))
        return

    if args.check_staleness:
        print(json.dumps(check_staleness(xushikj), ensure_ascii=False, indent=2))
        return

    if args.build:
        print(f"\n叙事空间 RAG 引擎 — 全量构建")
        print(f"项目: {project_dir}")
        print("-" * 50)
        build_index(xushikj, force=args.force)
        return

    if args.add_chapter is not None:
        print(f"\n叙事空间 RAG 引擎 — 增量更新 第{args.add_chapter}章")
        add_chapter(xushikj, args.add_chapter)
        return

    if args.query:
        char_ids = [c.strip() for c in args.char_ids.split(",") if c.strip()]
        loc_ids  = [l.strip() for l in args.loc_ids.split(",")  if l.strip()]
        results  = query(
            xushikj, args.query,
            char_ids=char_ids,
            loc_ids=loc_ids,
            top_k=args.top_k,
            current_chapter=args.current_chapter,
        )
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
