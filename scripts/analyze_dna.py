#!/usr/bin/env python3
"""
analyze_dna.py — 行文DNA量化分析脚本

将中文小说文本量化为微观风格统计数据，输出 raw_stats_{work_name}.json。
LLM 读取该文件后进行解读、模式归纳和例句选取，不再自行编造数字。

用法：
    python scripts/analyze_dna.py --input <文本文件路径> --work <作品名> [--project-dir <项目目录>]
    python scripts/analyze_dna.py --input novel.txt --work 斗破苍穹 --project-dir .xushikj
    python scripts/analyze_dna.py --input novel.txt --work 测试作品 --stdout  # 输出到标准输出

依赖（必选）：
    pip install jieba

依赖（可选，开启精确句型分类）：
    pip install spacy
    python -m spacy download zh_core_web_sm
"""

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

from chinese_char_count import count_chinese_chars

try:
    import jieba
    import jieba.posseg as pseg
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

# ── 话语标记词表（全部显性逻辑连词）─────────────────────────────────
EXPLICIT_MARKERS = [
    "但是", "然而", "不过", "况且", "何况", "而且", "并且",
    "因此", "所以", "于是", "故而", "因而",
    "虽然", "尽管", "即使", "哪怕",
    "总之", "总而言之",
    "首先", "其次", "最后", "然后", "接着", "继而",
]

# 人称代词集合（字符级检测）
PRONOUNS = set("他她它你我")

# 典型无主句起首词（动词/副词直接起句）
ZERO_SUBJECT_STARTERS = set("猛忽突骤缓轻慢只抬挥冲退走跑跌站立坐躺抓用力")

# 高频动作动词（用于连动式估算）
ACTION_VERB_PAT = re.compile(r"[走跑跳飞冲退闪抬挥砍击刺推拉抓扯踢踹扑滚翻]")

# ── 场景类型关键词表（用于 --chapter-map 模式）──────────────────────
SCENE_TYPE_KEYWORDS = {
    "combat":      ["拳", "剑", "刀", "攻击", "闪避", "战斗", "出手", "反击", "爆炸", "血"],
    "face_slap":   ["嘲笑", "讥讽", "废物", "跪", "不可能", "不敢置信", "震惊", "瞳孔", "脸色大变", "打脸"],
    "negotiation": ["谈判", "条件", "威胁", "合作", "利益", "协议", "要求", "交换", "势力"],
    "emotional":   ["泪", "哭", "心痛", "爱", "恨", "背叛", "原谅", "离开", "舍不得", "愧疚"],
    "reveal":      ["原来", "竟然", "真相", "身份", "秘密", "终于明白", "被识破", "暴露", "真正"],
    "daily":       ["修炼", "吃饭", "走进", "回到", "闲聊", "购买", "日常", "普通", "平静"],
    "system":      ["系统", "叮", "恭喜", "获得", "突破", "升级", "技能", "属性", "面板"],
}

# 章节分隔符默认正则
DEFAULT_CHAPTER_SEP = r"^第[零一二三四五六七八九十百千\d]+章"


def _reconfigure_stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ── 工具函数 ──────────────────────────────────────────────────────────

def split_sentences(text: str) -> list:
    """按中文句末标点切分句子，保留标点在句尾。"""
    parts = re.split(r"(?<=[。！？])", text)
    return [s.strip() for s in parts if s.strip()]


def split_paragraphs(text: str) -> list:
    """按空行或换行切分段落。"""
    parts = re.split(r"\n+", text)
    return [p.strip() for p in parts if p.strip()]


def variance(data: list) -> float:
    if len(data) < 2:
        return 0.0
    mean = sum(data) / len(data)
    return sum((x - mean) ** 2 for x in data) / len(data)


def percentile(sorted_data: list, p: int) -> float:
    if not sorted_data:
        return 0.0
    idx = max(0, int(len(sorted_data) * p / 100) - 1)
    return sorted_data[idx]


# ── 各维度分析函数 ────────────────────────────────────────────────────

def analyze_punctuation(text: str, total_chars: int, sentences: list, paragraphs: list) -> dict:
    """标点与停顿控制：完全字符统计，精度 100%。"""
    def density(char):
        return round(text.count(char) / total_chars * 1000, 2) if total_chars else 0

    # 段尾标点分布
    para_ending_dist = Counter()
    for p in paragraphs:
        if p:
            last = p[-1]
            if last in "。！？…\"'）】":
                para_ending_dist[last] += 1
            else:
                para_ending_dist["其他"] += 1

    # 每句平均逗号数（呼吸节奏指标）
    total_commas = text.count("，")
    avg_clauses = round(total_commas / len(sentences), 2) if sentences else 0

    return {
        "comma_per_1000":             density("，"),
        "period_per_1000":            density("。"),
        "exclaim_per_1000":           density("！"),
        "question_per_1000":          density("？"),
        "ellipsis_per_1000":          round(text.count("…") / 2 / total_chars * 1000, 2) if total_chars else 0,
        "dash_per_1000":              round(text.count("—") / 2 / total_chars * 1000, 2) if total_chars else 0,
        "avg_clauses_per_sentence":   avg_clauses,
        "para_ending_dist":           dict(para_ending_dist),
    }


def analyze_paragraph(paragraphs: list) -> dict:
    """段落结构：字符串切割后计算，精度 100%。"""
    lengths = [len(p) for p in paragraphs]
    if not lengths:
        return {}
    sorted_lengths = sorted(lengths)
    avg = round(sum(lengths) / len(lengths), 1)
    var = round(variance([float(l) for l in lengths]), 1)
    short_threshold = 30
    short_ratio = round(sum(1 for l in lengths if l <= short_threshold) / len(lengths), 3)
    return {
        "count":            len(lengths),
        "avg_length":       avg,
        "length_variance":  var,
        "short_para_ratio": short_ratio,
        "length_percentiles": {
            "p25": percentile(sorted_lengths, 25),
            "p50": percentile(sorted_lengths, 50),
            "p75": percentile(sorted_lengths, 75),
            "p95": percentile(sorted_lengths, 95),
        },
    }


def analyze_sentence(sentences: list) -> dict:
    """句子节奏：基于标点切分，基础层精度高。"""
    lengths = [len(s) for s in sentences]
    if not lengths:
        return {}
    sorted_lengths = sorted(lengths)
    avg = round(sum(lengths) / len(lengths), 1)

    # 句首字符粗分类
    opening_types = Counter()
    for s in sentences:
        if not s:
            continue
        c = s[0]
        if c in '"「『【（':
            opening_types["对话/引用"] += 1
        elif c in "但然虽尽可却偏":
            opening_types["转折词"] += 1
        elif c in PRONOUNS:
            opening_types["人称代词"] += 1
        elif c in ZERO_SUBJECT_STARTERS:
            opening_types["动词/副词（潜在无主句）"] += 1
        elif "\u4e00" <= c <= "\u9fff":
            opening_types["汉字（其他）"] += 1
        else:
            opening_types["其他"] += 1

    total = len(sentences)
    opening_dist = {k: round(v / total, 3) for k, v in opening_types.most_common()}

    return {
        "count":      total,
        "avg_length": avg,
        "length_percentiles": {
            "p25": percentile(sorted_lengths, 25),
            "p50": percentile(sorted_lengths, 50),
            "p75": percentile(sorted_lengths, 75),
            "p95": percentile(sorted_lengths, 95),
        },
        "opening_char_dist": opening_dist,
    }


def analyze_sentence_types_spacy(text: str) -> dict:
    """句型分类（精确层）：使用 spaCy 依存句法分析。"""
    try:
        nlp = spacy.load("zh_core_web_sm")
    except OSError:
        return {
            "source": "spacy_model_missing",
            "note": "请运行: python -m spacy download zh_core_web_sm",
        }

    # 超长文本分块处理，避免 spaCy 在整本小说上触发 max_length / 内存异常。
    max_chunk_chars = 30000
    chunks: list[str] = []
    if len(text) <= max_chunk_chars:
        chunks = [text]
    else:
        parts = re.split(r"(?<=[。！？!?])", text)
        buf = []
        buf_len = 0
        for part in parts:
            if not part:
                continue
            if buf_len + len(part) > max_chunk_chars and buf:
                chunks.append("".join(buf))
                buf = [part]
                buf_len = len(part)
            else:
                buf.append(part)
                buf_len += len(part)
        if buf:
            chunks.append("".join(buf))

    counts = Counter({"zero_subject": 0, "svo": 0, "sv_no_object": 0, "serial_verb": 0})
    total = 0

    for chunk in chunks:
        if not chunk.strip():
            continue
        # 保险起见，每块单独抬高 max_length，防止模型默认阈值过低。
        nlp.max_length = max(nlp.max_length, len(chunk) + 1000)
        try:
            doc = nlp(chunk)
        except Exception:
            # 超长文本在低内存环境下可能触发 numpy/spaCy 内存错误，降级到 estimate。
            return {
                "source": "estimate",
                "note": "spaCy 长文本分块解析失败，已降级为启发式估算",
            }
        for sent in doc.sents:
            total += 1
            tokens = list(sent)
            has_nsubj = any(t.dep_ == "nsubj" for t in tokens)
            has_dobj = any(t.dep_ in ("dobj", "obj") for t in tokens)
            verbs = [t for t in tokens if t.pos_ == "VERB"]

            if not has_nsubj:
                counts["zero_subject"] += 1
            elif has_dobj:
                counts["svo"] += 1
            else:
                counts["sv_no_object"] += 1

            if len(verbs) >= 3:
                counts["serial_verb"] += 1

    if total == 0:
        return {"source": "spacy", "total_parsed": 0}

    return {
        "source":              "spacy",
        "total_parsed":        total,
        "zero_subject_ratio":  round(counts["zero_subject"]  / total, 3),
        "svo_ratio":           round(counts["svo"]           / total, 3),
        "sv_no_object_ratio":  round(counts["sv_no_object"]  / total, 3),
        "serial_verb_ratio":   round(counts["serial_verb"]   / total, 3),
    }


def analyze_sentence_types_estimate(sentences: list) -> dict:
    """
    句型分类（降级估算层）：无 spaCy 时基于词典启发式判断。
    精度有限，输出中标注 source: estimate。
    """
    zero_count   = 0
    serial_count = 0
    total = len(sentences)

    for s in sentences:
        if not s:
            continue
        first_char = s[0]
        # 无主句估算：句首为典型动词/副词，且句首4字内无人称代词
        if first_char in ZERO_SUBJECT_STARTERS and not any(p in s[:4] for p in PRONOUNS):
            zero_count += 1
        # 连动式估算：句中出现 3+ 个高频动作动词
        if len(ACTION_VERB_PAT.findall(s)) >= 3:
            serial_count += 1

    if total == 0:
        return {"source": "estimate"}

    return {
        "source":            "estimate",
        "note":              "降级估算，精度有限。安装 spacy + zh_core_web_sm 可获得精确结果",
        "zero_subject_ratio": round(zero_count   / total, 3),
        "serial_verb_ratio":  round(serial_count / total, 3),
    }


def analyze_lexical(text: str, total_chars: int) -> dict:
    """词语结构：使用 jieba 词性标注，精度高。"""
    if not JIEBA_AVAILABLE:
        return {"source": "jieba_missing", "note": "请运行: pip install jieba"}

    words_with_pos = list(pseg.cut(text))
    total_words = len(words_with_pos)
    pos_counter = Counter()
    pronoun_word_count = 0
    four_char_count = 0

    for word, flag in words_with_pos:
        pos_counter[flag] += 1
        if flag.startswith("r"):      # 代词
            pronoun_word_count += 1
        # 四字格：长度=4，全部是汉字，非标点/数字
        if (len(word) == 4
                and flag not in ("x", "w", "m")
                and all("\u4e00" <= c <= "\u9fff" for c in word)):
            four_char_count += 1

    # 叠词检测（ABB / AABB）
    abb_count  = len(re.findall(r"([\u4e00-\u9fff])([\u4e00-\u9fff])\2", text))
    aabb_count = len(re.findall(r"([\u4e00-\u9fff])\1([\u4e00-\u9fff])\2", text))

    # 字符级代词密度（覆盖"他们""她们"等多字代词）
    pronoun_chars = sum(1 for c in text if c in PRONOUNS)

    return {
        "source":      "jieba",
        "total_words": total_words,
        "four_char_density":         round(four_char_count    / total_chars * 1000, 2) if total_chars else 0,
        "pronoun_density_per_1000":  round(pronoun_chars      / total_chars * 1000, 2) if total_chars else 0,
        "abb_count":                 abb_count,
        "aabb_count":                aabb_count,
        "pos_distribution": {
            "verb_ratio":    round(pos_counter.get("v",  0) / total_words, 3) if total_words else 0,
            "noun_ratio":    round((pos_counter.get("n", 0) + pos_counter.get("nr", 0) + pos_counter.get("ns", 0)) / total_words, 3) if total_words else 0,
            "adj_ratio":     round(pos_counter.get("a",  0) / total_words, 3) if total_words else 0,
            "pronoun_ratio": round(pronoun_word_count        / total_words, 3) if total_words else 0,
            "adv_ratio":     round(pos_counter.get("d",  0) / total_words, 3) if total_words else 0,
        },
    }


def analyze_discourse(text: str, total_chars: int, paragraphs: list) -> dict:
    """话语标记显性密度：关键词列表精确匹配。"""
    marker_breakdown = {m: text.count(m) for m in EXPLICIT_MARKERS}
    total_markers = sum(marker_breakdown.values())
    density = round(total_markers / total_chars * 1000, 2) if total_chars else 0

    # 段间硬切比：连续两段之间缺少连词桥接
    hard_cuts = 0
    soft_cuts = 0
    bridge_markers = ["于是", "然后", "接着", "但是", "然而", "不过", "因此", "所以", "继而"]
    for i in range(1, len(paragraphs)):
        window = (paragraphs[i - 1][-15:] if len(paragraphs[i - 1]) >= 15 else paragraphs[i - 1]) \
                 + (paragraphs[i][:15])
        has_bridge = any(m in window for m in bridge_markers)
        if has_bridge:
            soft_cuts += 1
        else:
            hard_cuts += 1

    total_boundaries = len(paragraphs) - 1
    hard_cut_ratio = round(hard_cuts / total_boundaries, 3) if total_boundaries else 0

    # 过滤出现次数为 0 的标记
    marker_breakdown = {k: v for k, v in marker_breakdown.items() if v > 0}

    return {
        "explicit_marker_density_per_1000": density,
        "total_explicit_markers":           total_markers,
        "hard_cut_ratio":                   hard_cut_ratio,
        "marker_breakdown":                 marker_breakdown,
    }


def extract_example_sentences(sentences: list) -> dict:
    """
    从句子列表中抽取各类型代表句，作为 LLM 解读时的原文锚点。
    key → 至多 3-5 个句子，直接来自原文。
    """
    examples = {
        "zero_subject":  [],  # 无主句
        "serial_verb":   [],  # 连动式（3+ 动作）
        "long_sentence": [],  # 长句（≥ 30 字）
        "short_burst":   [],  # 短句（≤ 8 字）
        "with_ellipsis": [],  # 含省略号
        "with_dash":     [],  # 含破折号
    }
    MAX = {"zero_subject": 3, "serial_verb": 3, "long_sentence": 3, "short_burst": 5,
           "with_ellipsis": 3, "with_dash": 3}

    for s in sentences:
        if not s:
            continue
        # 无主句
        if (s[0] in ZERO_SUBJECT_STARTERS
                and not any(p in s[:4] for p in PRONOUNS)
                and len(examples["zero_subject"]) < MAX["zero_subject"]):
            examples["zero_subject"].append(s)
        # 连动式
        if (len(ACTION_VERB_PAT.findall(s)) >= 3
                and len(examples["serial_verb"]) < MAX["serial_verb"]):
            examples["serial_verb"].append(s)
        # 长句
        if len(s) >= 30 and len(examples["long_sentence"]) < MAX["long_sentence"]:
            examples["long_sentence"].append(s)
        # 短句爆发
        if len(s) <= 8 and len(examples["short_burst"]) < MAX["short_burst"]:
            examples["short_burst"].append(s)
        # 省略号
        if "…" in s and len(examples["with_ellipsis"]) < MAX["with_ellipsis"]:
            examples["with_ellipsis"].append(s)
        # 破折号
        if "——" in s and len(examples["with_dash"]) < MAX["with_dash"]:
            examples["with_dash"].append(s)

    return {k: v for k, v in examples.items() if v}


# ── 主分析函数 ────────────────────────────────────────────────────────

def analyze(text: str, work_name: str) -> dict:
    """对输入文本执行全量微观分析，返回 raw_stats 字典。"""
    # 规范化换行
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 过滤章节标题行（"第X章" 格式）
    lines = text.split("\n")
    content_lines = [
        l for l in lines
        if not re.match(r"^第[零一二三四五六七八九十百千万0-9]+[章节回]", l.strip())
    ]
    text = "\n".join(content_lines)

    paragraphs = split_paragraphs(text)
    sentences  = split_sentences(text)
    # 中文字符数（统一基线统计）
    total_chars = count_chinese_chars(text)

    result = {
        "meta": {
            "source":          work_name,
            "total_chars":     total_chars,
            "total_sentences": len(sentences),
            "total_paragraphs": len(paragraphs),
        },
        "punctuation": analyze_punctuation(text, total_chars, sentences, paragraphs),
        "paragraph":   analyze_paragraph(paragraphs),
        "sentence":    analyze_sentence(sentences),
        "sentence_types": (
            analyze_sentence_types_spacy(text)
            if SPACY_AVAILABLE
            else analyze_sentence_types_estimate(sentences)
        ),
        "lexical": (
            analyze_lexical(text, total_chars)
            if JIEBA_AVAILABLE
            else {"source": "jieba_missing", "note": "请运行: pip install jieba"}
        ),
        "discourse":         analyze_discourse(text, total_chars, paragraphs),
        "example_sentences": extract_example_sentences(sentences),
    }
    return result


# ── 章节类型标注（--chapter-map 模式）────────────────────────────────

def split_chapters(text: str, chapter_sep: str) -> list:
    """按章节标题正则切分文本，返回 [(chapter_num, chapter_text), ...]"""
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


def score_chapter_types(chapter_text: str) -> dict:
    """对单章文本计算各场景类型的关键词密度得分。"""
    text_len = count_chinese_chars(chapter_text)
    if text_len == 0:
        return {st: 0.0 for st in SCENE_TYPE_KEYWORDS}

    scores = {}
    for scene_type, keywords in SCENE_TYPE_KEYWORDS.items():
        count = sum(chapter_text.count(kw) for kw in keywords)
        scores[scene_type] = round(count / text_len * 1000, 2)
    return scores


def generate_chapter_type_map(text: str, work_name: str, chapter_sep: str) -> dict:
    """生成章节类型标注文件内容。"""
    chapters = split_chapters(text, chapter_sep)

    chapter_entries = []
    for chapter_num, chapter_text in chapters:
        type_scores = score_chapter_types(chapter_text)
        primary_type = max(type_scores, key=type_scores.get) if any(v > 0 for v in type_scores.values()) else "daily"
        word_count = count_chinese_chars(chapter_text)

        chapter_entries.append({
            "chapter_num": chapter_num,
            "primary_type": primary_type,
            "type_scores": type_scores,
            "word_count": word_count,
        })

    return {
        "work": work_name,
        "total_chapters": len(chapter_entries),
        "chapters": chapter_entries,
    }


# ── CLI 入口 ──────────────────────────────────────────────────────────

def main():
    _reconfigure_stdout_utf8()
    parser = argparse.ArgumentParser(
        description="行文DNA量化脚本 — 输出 raw_stats_{work_name}.json"
    )
    parser.add_argument("--input",       required=True, help="输入文本文件路径（UTF-8）")
    parser.add_argument("--work",        required=True, help="作品名称（用于输出文件命名）")
    parser.add_argument("--project-dir", default=".",   help="项目根目录，含 .xushikj/ 子目录，默认为当前目录")
    parser.add_argument("--stdout",      action="store_true", help="将 JSON 输出到标准输出，不写入文件")
    parser.add_argument("--chapter-map", action="store_true", help="开启章节类型标注模式，输出 chapter_type_map.json")
    parser.add_argument("--chapter-sep", default=DEFAULT_CHAPTER_SEP, help="章节分隔符正则，默认 ^第X章")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] 文件不存在：{input_path}", file=sys.stderr)
        sys.exit(1)

    text = input_path.read_text(encoding="utf-8")
    zh_chars = count_chinese_chars(text)
    if zh_chars < 500:
        print(f"[WARN] 文本较短（{zh_chars} 中文字），结果精度有限", file=sys.stderr)

    print(f"[analyze_dna] 正在分析：{args.work}（{zh_chars} 中文字）", file=sys.stderr)
    result = analyze(text, args.work)

    if args.stdout:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        out_dir = Path(args.project_dir) / ".xushikj" / "benchmark"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", args.work)
        out_path = out_dir / f"raw_stats_{safe_name}.json"
        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[analyze_dna] 输出：{out_path}", file=sys.stderr)
        m = result["meta"]
        st = result["sentence_types"]
        lex = result["lexical"]
        print(f"  字符数：{m['total_chars']}", file=sys.stderr)
        print(f"  句子数：{m['total_sentences']}", file=sys.stderr)
        print(f"  段落数：{m['total_paragraphs']}", file=sys.stderr)
        print(f"  句型来源：{st.get('source', 'unknown')}", file=sys.stderr)
        print(f"  词法来源：{lex.get('source', 'unknown')}", file=sys.stderr)
        disc = result["discourse"]
        print(f"  显性连词密度：{disc['explicit_marker_density_per_1000']}/千字", file=sys.stderr)
        print(f"  段间硬切比：{disc['hard_cut_ratio']}", file=sys.stderr)

    # ── chapter-map 模式 ──────────────────────────────────────────────
    if args.chapter_map:
        print(f"[analyze_dna] 正在生成章节类型标注...", file=sys.stderr)
        chapter_map = generate_chapter_type_map(text, args.work, args.chapter_sep)

        if args.stdout:
            print(json.dumps(chapter_map, ensure_ascii=False, indent=2))
        else:
            out_dir = Path(args.project_dir) / ".xushikj" / "benchmark"
            out_dir.mkdir(parents=True, exist_ok=True)
            map_path = out_dir / "chapter_type_map.json"
            map_path.write_text(
                json.dumps(chapter_map, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[analyze_dna] 章节类型标注输出：{map_path}", file=sys.stderr)
            print(f"  总章节数：{chapter_map['total_chapters']}", file=sys.stderr)


if __name__ == "__main__":
    main()
