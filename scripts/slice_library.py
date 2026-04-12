#!/usr/bin/env python3
"""
slice_library.py — 风格切片库构建脚本

本脚本自动执行 Step 0（量化扫描+章节类型标注），
Step 1-2（候选提取与筛选）由 LLM 执行，
Step 3-4 通过 write-snippet / write-dna 子命令完成落盘。

用法：
    python scripts/slice_library.py \\
      --input novel.txt \\
      --author author_slug \\
      --title "作品名" \\
      [--project-dir .xushikj]     # 可选，用于存放 raw_stats
      [--append]                    # 追加模式：向已有作者库补充新作品切片
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from chinese_char_count import validate_chinese_char_count

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False



def _reconfigure_stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
# 场景类型列表（与 analyze_dna.py 保持一致）
SCENE_TYPES = [
    "combat",
    "face_slap",
    "negotiation",
    "emotional",
    "reveal",
    "daily",
    "system",
    "training",
    "romance",
    "mystery",
    "power_up",
    "chase",
    "crowd_reaction",
    "strategy",
    "flashback",
    "world_building",
    "aftermath",
    "humor",
]
SCENE_TYPE_ALIASES = {
    "action": "combat",
    "investigation": "mystery",
    "growth": "power_up",
}
SNIPPET_MIN_CHARS = 350
SNIPPET_MAX_CHARS = 500
# source_available=true 的类型至少要保留 3 个合格切片（不重复）；未命中原文的类型可豁免。
MIN_SNIPPETS_PER_ACTIVE_TYPE = 3
# 无论类型是否活跃，单类型都不能超过该数量上限。
MAX_SNIPPETS_PER_TYPE = 8

# 切片库全局根目录
STYLE_LIBRARY_ROOT = Path.home() / ".narrativespace" / "style_library"


def get_library_root():
    return STYLE_LIBRARY_ROOT


def get_author_dir(author_slug: str) -> Path:
    return get_library_root() / author_slug


def _resolve_xushikj_dir(project_dir: str) -> Path:
    path = Path(project_dir)
    if path.name == ".xushikj":
        return path
    return path / ".xushikj"


def _benchmark_registry_path(xushikj_dir: Path) -> Path:
    return xushikj_dir / "benchmark" / "source_registry.json"


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _register_source_text(project_dir: str, source_file: Path, work_title: str) -> Path:
    xushikj_dir = _resolve_xushikj_dir(project_dir)
    benchmark_dir = xushikj_dir / "benchmark"
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    raw = source_file.read_bytes()
    payload = {
        "source_file": str(source_file.resolve()),
        "source_title": work_title,
        "source_sha256": _sha256_bytes(raw),
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }

    reg_path = _benchmark_registry_path(xushikj_dir)
    reg_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return reg_path


def _strip_yaml_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def _validate_snippet_is_source_excerpt(xushikj_dir: Path, snippet_text: str) -> tuple[bool, str]:
    reg_path = _benchmark_registry_path(xushikj_dir)
    if not reg_path.exists():
        return False, f"缺少源文本登记文件：{reg_path}。请先执行 Step 0。"

    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"源文本登记文件损坏：{exc}"

    source_file = reg.get("source_file")
    source_sha256 = reg.get("source_sha256")
    if not source_file or not source_sha256:
        return False, "source_registry.json 缺少 source_file/source_sha256 字段。"

    source_path = Path(str(source_file))
    if not source_path.exists():
        return False, f"登记的原文文件不存在：{source_path}"

    raw = source_path.read_bytes()
    if _sha256_bytes(raw) != str(source_sha256):
        return False, "原文文件哈希不匹配（文件可能已变更），拒绝写入切片。"

    try:
        source_text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return False, f"原文文件编码读取失败（仅支持 UTF-8/UTF-8-SIG）：{exc}"

    candidate = _strip_yaml_frontmatter(snippet_text).strip()
    if not candidate:
        return False, "切片内容为空，拒绝写入。"

    # Strict excerpt check: only normalize line endings and trim outer spaces.
    source_norm = source_text.replace("\r\n", "\n")
    cand_norm = candidate.replace("\r\n", "\n")

    pos = source_norm.find(cand_norm)
    if pos < 0:
        sample = cand_norm[:80].replace("\n", " ")
        return False, f"切片未在原文中找到精确匹配：{sample}..."

    return True, f"原文校验通过，命中偏移={pos}"


def _load_yaml_or_default(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8")
        if YAML_AVAILABLE:
            data = yaml.safe_load(text) or {}
        else:
            data = json.loads(text)
        return data if isinstance(data, dict) else default
    except Exception:
        return default


def _dump_yaml_or_json(path: Path, data: dict) -> None:
    if YAML_AVAILABLE:
        content = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    else:
        content = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(content, encoding="utf-8")


def _normalize_scene_type(scene_type: str) -> str:
    return SCENE_TYPE_ALIASES.get(scene_type.strip().lower(), scene_type.strip().lower())


def _normalize_snippet_body(text: str) -> str:
    return _strip_yaml_frontmatter(text).replace("\r\n", "\n").strip()


def _snippet_body_digest(text: str) -> str | None:
    normalized = _normalize_snippet_body(text)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _collect_unique_scene_files(snippet_dir: Path, files: list[str]) -> tuple[list[str], list[str], set[str]]:
    unique_files: list[str] = []
    duplicate_files: list[str] = []
    digests: set[str] = set()

    for item in files:
        candidate = snippet_dir / str(item)
        if not candidate.exists():
            continue
        try:
            snippet_text = candidate.read_text(encoding="utf-8-sig")
        except Exception:
            continue
        digest = _snippet_body_digest(snippet_text)
        if digest is None:
            continue
        if digest in digests:
            duplicate_files.append(str(item))
            continue
        digests.add(digest)
        unique_files.append(str(item))

    return unique_files, duplicate_files, digests


def _append_scene_file_to_manifest(manifest_path: Path, scene_type: str, filename: str) -> None:
    manifest = _load_yaml_or_default(manifest_path, {"snippets": {}})
    snippets = manifest.setdefault("snippets", {})
    if not isinstance(snippets, dict):
        snippets = {}
        manifest["snippets"] = snippets

    payload = snippets.setdefault(scene_type, {})
    if not isinstance(payload, dict):
        payload = {}
        snippets[scene_type] = payload

    files = payload.get("files", [])
    if not isinstance(files, list):
        files = []
    if filename not in files:
        files.append(filename)
    payload["files"] = files
    payload["count"] = len(files)
    _dump_yaml_or_json(manifest_path, manifest)


def _coverage_path(xushikj_dir: Path) -> Path:
    return xushikj_dir / "benchmark" / "scene_type_coverage.json"


def _build_scene_type_coverage(chapter_type_map: dict) -> dict[str, dict[str, object]]:
    coverage: dict[str, dict[str, object]] = {
        scene_type: {"source_available": False, "chapter_hits": 0, "max_score": 0.0}
        for scene_type in SCENE_TYPES
    }
    chapters = chapter_type_map.get("chapters", [])
    if not isinstance(chapters, list):
        return coverage

    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        type_scores = chapter.get("type_scores", {})
        if not isinstance(type_scores, dict):
            continue
        for raw_scene_type, raw_score in type_scores.items():
            scene_type = _normalize_scene_type(str(raw_scene_type))
            if scene_type not in coverage:
                continue
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                score = 0.0
            if score > 0:
                coverage[scene_type]["source_available"] = True
                coverage[scene_type]["chapter_hits"] = int(coverage[scene_type]["chapter_hits"]) + 1
                coverage[scene_type]["max_score"] = max(float(coverage[scene_type]["max_score"]), score)
    return coverage


def _load_scene_type_coverage(xushikj_dir: Path) -> dict[str, dict[str, object]]:
    coverage_path = _coverage_path(xushikj_dir)
    if not coverage_path.exists():
        return _build_scene_type_coverage({})
    try:
        payload = json.loads(coverage_path.read_text(encoding="utf-8"))
    except Exception:
        return _build_scene_type_coverage({})
    if not isinstance(payload, dict):
        return _build_scene_type_coverage({})
    coverage = payload.get("scene_types", payload)
    return coverage if isinstance(coverage, dict) else _build_scene_type_coverage({})


def _sync_manifest_with_coverage(manifest_path: Path, coverage: dict[str, dict[str, object]]) -> None:
    manifest = _load_yaml_or_default(
        manifest_path,
        {
            "snippets": {},
            "snippet_limits": {
                "min_chars": SNIPPET_MIN_CHARS,
                "max_chars": SNIPPET_MAX_CHARS,
                "min_per_active_type": MIN_SNIPPETS_PER_ACTIVE_TYPE,
                "max_per_type": MAX_SNIPPETS_PER_TYPE,
                "require_unique": True,
            },
        },
    )
    snippet_dir = manifest_path.parent
    snippets = manifest.setdefault("snippets", {})
    missing_types: list[str] = []
    exempt_types: list[str] = []

    for scene_type in SCENE_TYPES:
        payload = snippets.setdefault(scene_type, {})
        if not isinstance(payload, dict):
            payload = {}
            snippets[scene_type] = payload
        files = payload.get("files", [])
        if not isinstance(files, list):
            files = []
        payload["files"] = [str(item) for item in files]
        payload["count"] = len(payload["files"])
        unique_files, duplicate_files, _ = _collect_unique_scene_files(snippet_dir, payload["files"])
        payload["unique_files"] = unique_files
        payload["unique_count"] = len(unique_files)
        payload["duplicate_files"] = duplicate_files
        scene_coverage = coverage.get(scene_type, {}) if isinstance(coverage, dict) else {}
        source_available = bool(scene_coverage.get("source_available"))
        payload["source_available"] = source_available
        payload["chapter_hits"] = int(scene_coverage.get("chapter_hits", 0) or 0)
        payload["min_required"] = MIN_SNIPPETS_PER_ACTIVE_TYPE if source_available else 0
        payload["max_allowed"] = MAX_SNIPPETS_PER_TYPE
        if not source_available:
            payload["status"] = "source_missing"
            payload["missing_reason"] = "source_missing"
            exempt_types.append(scene_type)
        elif payload["unique_count"] >= MIN_SNIPPETS_PER_ACTIVE_TYPE:
            payload["status"] = "ready"
            payload["missing_reason"] = ""
        else:
            payload["status"] = "missing"
            payload["missing_reason"] = (
                str(payload.get("last_rejection_reason", "")).strip()
                or ("duplicate_snippets_present" if duplicate_files else "awaiting_valid_snippet")
            )
            missing_types.append(scene_type)

    manifest["missing_types"] = missing_types
    manifest["exempt_types"] = exempt_types
    manifest["completeness"] = "full" if not missing_types else "partial"
    _dump_yaml_or_json(manifest_path, manifest)


def _record_snippet_rejection(manifest_path: Path, scene_type: str, reason: str, coverage: dict[str, dict[str, object]]) -> None:
    manifest = _load_yaml_or_default(manifest_path, {"snippets": {}})
    snippets = manifest.setdefault("snippets", {})
    payload = snippets.setdefault(scene_type, {})
    if not isinstance(payload, dict):
        payload = {}
        snippets[scene_type] = payload
    payload["last_rejection_reason"] = reason
    _dump_yaml_or_json(manifest_path, manifest)
    _sync_manifest_with_coverage(manifest_path, coverage)


def _resolve_global_library_target(xushikj_dir: Path) -> tuple[Path, str] | None:
    state_path = xushikj_dir / "state.json"
    if not state_path.exists():
        return None

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    benchmark_state = state.get("benchmark_state", {}) if isinstance(state, dict) else {}
    if not isinstance(benchmark_state, dict):
        return None

    linked_author = benchmark_state.get("linked_author")
    if not isinstance(linked_author, str) or not linked_author.strip():
        return None

    library_root_raw = benchmark_state.get("style_library_path", "~/.narrativespace/style_library")
    root = Path(os.path.expanduser(str(library_root_raw)))
    return root / linked_author.strip(), linked_author.strip()


def cmd_write_snippet(project_dir: str, scene_type: str, content_file: str) -> int:
    content_path = Path(content_file)
    if not content_path.exists():
        print(f"[ERROR] 内容文件不存在：{content_path}", file=sys.stderr)
        return 1

    normalized_scene_type = _normalize_scene_type(scene_type)
    if normalized_scene_type not in SCENE_TYPES:
        print(f"[ERROR] 不支持的 scene_type：{scene_type}（规范值：{', '.join(SCENE_TYPES)}）", file=sys.stderr)
        return 1

    xushikj_dir = _resolve_xushikj_dir(project_dir)
    snippet_dir = xushikj_dir / "benchmark" / "style_snippets"
    snippet_dir.mkdir(parents=True, exist_ok=True)
    coverage = _load_scene_type_coverage(xushikj_dir)
    manifest_path = snippet_dir / "manifest.yaml"
    _sync_manifest_with_coverage(manifest_path, coverage)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{normalized_scene_type}_{timestamp}.md"
    snippet_path = snippet_dir / filename
    snippet_text = content_path.read_text(encoding="utf-8-sig")
    snippet_body = _normalize_snippet_body(snippet_text)

    _, count_errors = validate_chinese_char_count(
        snippet_body,
        minimum=SNIPPET_MIN_CHARS,
        maximum=SNIPPET_MAX_CHARS,
        label=f"style_snippet[{normalized_scene_type}]",
    )
    if count_errors:
        reason = "; ".join(count_errors)
        _record_snippet_rejection(manifest_path, normalized_scene_type, reason, coverage)
        print(f"[ERROR] 切片字数校验失败：{reason}", file=sys.stderr)
        return 1

    ok, reason = _validate_snippet_is_source_excerpt(xushikj_dir, snippet_text)
    if not ok:
        _record_snippet_rejection(manifest_path, normalized_scene_type, reason, coverage)
        print(f"[ERROR] 切片原文校验失败：{reason}", file=sys.stderr)
        return 1
    print(f"[slice_library] {reason}")

    current_manifest = _load_yaml_or_default(manifest_path, {"snippets": {}})
    current_payload = current_manifest.get("snippets", {}).get(normalized_scene_type, {})
    current_files = current_payload.get("files", []) if isinstance(current_payload, dict) else []
    current_unique_files, _, current_digests = _collect_unique_scene_files(snippet_dir, current_files)
    new_digest = _snippet_body_digest(snippet_text)
    if new_digest is not None and new_digest in current_digests:
        reason = f"{normalized_scene_type} 切片重复：内容与现有切片完全一致，不计入合格数量"
        _record_snippet_rejection(manifest_path, normalized_scene_type, reason, coverage)
        print(f"[ERROR] {reason}", file=sys.stderr)
        return 1

    if len(current_unique_files) >= MAX_SNIPPETS_PER_TYPE:
        reason = f"{normalized_scene_type} 已达到上限：{len(current_unique_files)} >= {MAX_SNIPPETS_PER_TYPE}"
        _record_snippet_rejection(manifest_path, normalized_scene_type, reason, coverage)
        print(f"[ERROR] {reason}", file=sys.stderr)
        return 1

    snippet_path.write_text(snippet_text, encoding="utf-8")
    _append_scene_file_to_manifest(manifest_path, normalized_scene_type, filename)
    _sync_manifest_with_coverage(manifest_path, coverage)
    print(f"[slice_library] 已写入切片：{snippet_path}")
    print(f"[slice_library] 已更新 manifest：{manifest_path}")

    global_target = _resolve_global_library_target(xushikj_dir)
    if global_target is not None:
        author_dir, author_slug = global_target
        author_dir.mkdir(parents=True, exist_ok=True)
        global_snippet_path = author_dir / filename
        global_snippet_path.write_text(snippet_text, encoding="utf-8")

        global_manifest_path = author_dir / "manifest.yaml"
        _append_scene_file_to_manifest(global_manifest_path, normalized_scene_type, filename)
        _sync_manifest_with_coverage(global_manifest_path, coverage)

        print(f"[slice_library] 已同步全局切片库（author={author_slug}）：{global_snippet_path}")
        print(f"[slice_library] 已更新全局 manifest：{global_manifest_path}")
    else:
        print("[slice_library] 未检测到 linked_author，跳过全局库同步（仅保留项目本地切片）。")
    return 0


def _merge_keep_existing(target: dict, incoming: dict, prefix: str = "") -> list[str]:
    added_paths: list[str] = []
    for key, value in incoming.items():
        path_key = f"{prefix}.{key}" if prefix else str(key)
        if key not in target:
            target[key] = value
            added_paths.append(path_key)
            continue
        if isinstance(target[key], dict) and isinstance(value, dict):
            added_paths.extend(_merge_keep_existing(target[key], value, path_key))
    return added_paths


def cmd_write_dna(project_dir: str, project_name: str, dna_json: str) -> int:
    dna_json_path = Path(dna_json)
    if not dna_json_path.exists():
        print(f"[ERROR] DNA JSON 文件不存在：{dna_json_path}", file=sys.stderr)
        return 1

    try:
        incoming = json.loads(dna_json_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"[ERROR] 读取 DNA JSON 失败：{exc}", file=sys.stderr)
        return 1

    if not isinstance(incoming, dict):
        print("[ERROR] DNA JSON 顶层必须是对象（key-value）。", file=sys.stderr)
        return 1

    xushikj_dir = _resolve_xushikj_dir(project_dir)
    style_modules_dir = xushikj_dir / "config" / "style_modules"
    style_modules_dir.mkdir(parents=True, exist_ok=True)

    target_path = style_modules_dir / f"dna_human_{project_name}.yaml"
    existing = _load_yaml_or_default(target_path, {})
    if not isinstance(existing, dict):
        existing = {}

    added_keys = _merge_keep_existing(existing, incoming)
    _dump_yaml_or_json(target_path, existing)

    print(f"[slice_library] 已写入 DNA 文件：{target_path}")
    if added_keys:
        print(f"[slice_library] 新增字段：{', '.join(added_keys)}")
    else:
        print("[slice_library] 未新增字段（已有 key 保持不覆盖）。")
    return 0


def run_step0(input_path: str, work_name: str, project_dir: str) -> Path:
    """Step 0: 调用 analyze_dna.py 进行量化扫描 + 章节类型标注。"""
    script_dir = Path(__file__).parent
    analyze_script = script_dir / "analyze_dna.py"

    cmd = [
        sys.executable, str(analyze_script),
        "--input", input_path,
        "--work", work_name,
        "--project-dir", project_dir,
        "--chapter-map",
    ]

    print(f"[slice_library] Step 0: 运行 analyze_dna.py ...", file=sys.stderr)
    try:
        # Inherit stdio to avoid buffering huge outputs in memory.
        result = subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print(
            "[ERROR] Step 0 被中断。可改为直接执行 analyze_dna.py --chapter-map 后重试后续步骤。",
            file=sys.stderr,
        )
        sys.exit(1)

    if result.returncode != 0:
        print("[ERROR] analyze_dna.py 执行失败，请检查上方输出日志。", file=sys.stderr)
        sys.exit(1)

    chapter_map_path = Path(project_dir) / ".xushikj" / "benchmark" / "chapter_type_map.json"
    if not chapter_map_path.exists():
        print(f"[ERROR] chapter_type_map.json 未生成：{chapter_map_path}", file=sys.stderr)
        sys.exit(1)

    return chapter_map_path


def load_chapter_type_map(map_path: Path) -> dict:
    return json.loads(map_path.read_text(encoding="utf-8"))


def split_novel_chapters(input_path: str, chapter_sep: str = None) -> list:
    """读取小说文本并按章节分割，返回 [(chapter_num, text), ...]"""
    if chapter_sep is None:
        chapter_sep = r"^第[零一二三四五六七八九十百千\d]+章"

    text = Path(input_path).read_text(encoding="utf-8")
    pattern = re.compile(chapter_sep, re.MULTILINE)
    lines = text.split("\n")
    chapters = []
    current_num = 0
    current_lines = []

    for line in lines:
        if pattern.match(line.strip()):
            if current_lines:
                chapters.append((current_num, "\n".join(current_lines)))
            current_num += 1
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        chapters.append((current_num, "\n".join(current_lines)))

    return [(num, text) for num, text in chapters if num > 0]


def write_snippet_file(author_slug: str, scene_type: str, snippet_index: int,
                       metadata: dict, body_text: str) -> Path:
    """Step 3: 写入单个切片文件。"""
    author_dir = get_author_dir(author_slug)
    type_dir = author_dir / scene_type
    type_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{snippet_index:03d}.md"
    filepath = type_dir / filename

    # 构建 YAML frontmatter
    frontmatter_lines = [
        "---",
        f"author: {metadata['author']}",
        f"source: {metadata['source']}",
        f"scene_type: {metadata['scene_type']}",
        f"intensity: {metadata['intensity']}",
        f"chapter: {metadata['chapter']}",
        f"position: {metadata.get('position', 'middle')}",
        f"char_count: {metadata['char_count']}",
        f"chapter_type_score: {metadata.get('chapter_type_score', 0)}",
        f"tags: {json.dumps(metadata.get('tags', []), ensure_ascii=False)}",
        f"extracted_at: {date.today().isoformat()}",
        "---",
        "",
    ]

    content = "\n".join(frontmatter_lines) + body_text.strip() + "\n"
    filepath.write_text(content, encoding="utf-8")
    return filepath


def write_manifest(author_slug: str, display_name: str, source_work: dict,
                   snippet_info: dict, append: bool = False) -> Path:
    """Step 4: 生成或更新 manifest.yaml。"""
    author_dir = get_author_dir(author_slug)
    author_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = author_dir / "manifest.yaml"

    today = date.today().isoformat()

    if append and manifest_path.exists():
        existing = manifest_path.read_text(encoding="utf-8")
        if YAML_AVAILABLE:
            manifest = yaml.safe_load(existing)
        else:
            # Fallback: just append source work info
            print("[WARN] pyyaml 未安装，追加模式可能不完整", file=sys.stderr)
            manifest = {"author": author_slug, "source_works": [], "snippets": {}}
    else:
        manifest = {
            "author": author_slug,
            "display_name": display_name,
            "created_at": today,
            "updated_at": today,
            "source_works": [],
            "clone_yaml": None,
            "dna_yaml": None,
            "snippets": {},
            "completeness": "full",
            "missing_types": [],
        }

    manifest["updated_at"] = today

    # Add source work
    manifest.setdefault("source_works", [])
    manifest["source_works"].append(source_work)

    # Update snippets
    manifest.setdefault("snippets", {})
    for scene_type, info in snippet_info.items():
        manifest["snippets"][scene_type] = info

    # Check completeness
    missing = [st for st in SCENE_TYPES if st not in manifest["snippets"] or manifest["snippets"][st].get("count", 0) == 0]
    manifest["missing_types"] = missing
    manifest["completeness"] = "full" if not missing else "partial"

    if YAML_AVAILABLE:
        content = yaml.dump(manifest, allow_unicode=True, default_flow_style=False, sort_keys=False)
    else:
        # Fallback: JSON-style output
        content = json.dumps(manifest, ensure_ascii=False, indent=2)

    manifest_path.write_text(content, encoding="utf-8")
    return manifest_path


def print_step1_instructions(chapter_type_map: dict, input_path: str):
    """输出 Step 1-2 的 LLM 执行指令，供代理或用户手动执行。"""
    print("\n" + "=" * 70)
    print("Step 0 完成。以下步骤需要 LLM 执行：")
    print("=" * 70)
    print()
    print("Step 1（LLM层）：候选段落提取")
    print("  对 chapter_type_map.json 按 scene_type 分组，对每种类型：")
    print("  - 先读取 benchmark/scene_type_coverage.json，仅对 source_available=true 的类型提候选")
    print("  - 若 coverage 尚未生成，先完成全书扫描；不得只凭开头样本猜 scene_type")
    print("  - 按 type_scores 取该类型得分最高的20个章节")
    print(f"  - 从每个章节中提取 {SNIPPET_MIN_CHARS}-{SNIPPET_MAX_CHARS} 中文字候选段落（必须是原文逐字摘录，禁止改写）")
    print("  - source_available=true 的 scene_type 都必须给出候选；仅 source_missing 类型允许留空")
    print()
    print("Step 2（LLM层）：候选排序与最终筛选")
    print("  对每种类型的候选按语感辨识度(40%)/场景类型纯度(30%)/强度标注(20%)/章节分散性(10%)评分")
    print(f"  每种 source_available 类型最终保留 {MIN_SNIPPETS_PER_ACTIVE_TYPE}-{MAX_SNIPPETS_PER_TYPE} 个不重复切片")
    print("  强度分布尽量覆盖 high / medium / low，但优先保证 active 类型全覆盖与切片不重复")
    print("  不得编造不存在的命令参数、行号、片段位置或未核验的字符数")
    print()
    print("完成 Step 1-2 后，调用 write-snippet / write-dna 子命令落盘。")
    print("write-snippet 现已强制校验：切片必须在登记原文中精确命中，且中文字数必须在范围内，否则拒绝写入。")
    print("\n最小落盘命令示例：")
    print("  python scripts/slice_library.py write-snippet --project-dir . --scene-type daily --content-file snippet_daily.md")
    print("  python scripts/slice_library.py write-dna --project-dir . --project-name my_project --dna-json dna_profile.json")
    print("=" * 70)


def main() -> int:
    _reconfigure_stdout_utf8()
    if len(sys.argv) > 1 and sys.argv[1] in {"write-snippet", "write-dna"}:
        sub_parser = argparse.ArgumentParser(description="风格切片与 DNA 本地写入工具")
        subparsers = sub_parser.add_subparsers(dest="command", required=True)

        write_snippet_parser = subparsers.add_parser("write-snippet", help="写入项目本地 style snippet，并在有 linked_author 时同步全局库")
        write_snippet_parser.add_argument("--project-dir", required=True, help="项目根目录或 .xushikj 目录")
        write_snippet_parser.add_argument("--scene-type", required=True, help="场景类型，如 combat/daily（action 会自动映射为 combat）")
        write_snippet_parser.add_argument("--content-file", required=True, help="切片 Markdown 文件路径")

        write_dna_parser = subparsers.add_parser("write-dna", help="将 DNA JSON 写入 dna_human_*.yaml")
        write_dna_parser.add_argument("--project-dir", required=True, help="项目根目录或 .xushikj 目录")
        write_dna_parser.add_argument("--project-name", required=True, help="项目名，用于生成 dna_human_{project}.yaml")
        write_dna_parser.add_argument("--dna-json", required=True, help="LLM 产出的 DNA JSON 文件路径")

        sub_args = sub_parser.parse_args()
        if sub_args.command == "write-snippet":
            return cmd_write_snippet(sub_args.project_dir, sub_args.scene_type, sub_args.content_file)
        if sub_args.command == "write-dna":
            return cmd_write_dna(sub_args.project_dir, sub_args.project_name, sub_args.dna_json)
        return 2

    parser = argparse.ArgumentParser(
        description="风格切片库构建脚本 — 从小说文本构建全局跨项目切片库"
    )
    parser.add_argument("--input", required=True, help="整本小说的纯文本文件路径（UTF-8）")
    parser.add_argument("--author", required=True, help="作者slug（用于目录命名，如 tiancan_tudou）")
    parser.add_argument("--title", required=True, help="作品名称")
    parser.add_argument("--project-dir", default=".", help="项目根目录，含 .xushikj/ 子目录")
    parser.add_argument("--append", action="store_true", help="追加模式：向已有作者库补充新作品切片")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] 文件不存在：{input_path}", file=sys.stderr)
        return 1

    reg_path = _register_source_text(args.project_dir, input_path, args.title)
    print(f"[slice_library] 已登记原文源文件：{reg_path}", file=sys.stderr)

    # Step 0: 量化扫描 + 章节类型标注
    chapter_map_path = run_step0(str(input_path), args.title, args.project_dir)
    chapter_type_map = load_chapter_type_map(chapter_map_path)
    coverage = _build_scene_type_coverage(chapter_type_map)
    xushikj_dir = _resolve_xushikj_dir(args.project_dir)
    coverage_path = _coverage_path(xushikj_dir)
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.write_text(
        json.dumps(
            {
                "scene_types": coverage,
                "snippet_limits": {
                    "min_chars": SNIPPET_MIN_CHARS,
                    "max_chars": SNIPPET_MAX_CHARS,
                    "min_per_active_type": MIN_SNIPPETS_PER_ACTIVE_TYPE,
                    "max_per_type": MAX_SNIPPETS_PER_TYPE,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _sync_manifest_with_coverage(xushikj_dir / "benchmark" / "style_snippets" / "manifest.yaml", coverage)

    print(f"[slice_library] 章节类型标注完成：{chapter_type_map['total_chapters']} 章", file=sys.stderr)
    print(f"[slice_library] 已生成场景覆盖基线：{coverage_path}", file=sys.stderr)

    # Step 1-2 需要 LLM 执行
    print_step1_instructions(chapter_type_map, str(input_path))

    # 输出切片库目标路径
    author_dir = get_author_dir(args.author)
    print(f"\n切片库目标路径：{author_dir}", file=sys.stderr)
    print(f"manifest 路径：{author_dir / 'manifest.yaml'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
