#!/usr/bin/env python3
"""
chinese_char_count.py

Count Chinese characters only (CJK Unified Ideographs), intended as the
single baseline utility for chapter length checks across modules.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from encoding_utils import reconfigure_stdio_utf8

# Basic CJK Unified Ideographs range.
ZH_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
FANQIE_MAX_CHARS = 3500


def count_chinese_chars(text: str) -> int:
    return len(ZH_CHAR_RE.findall(text))


def count_chinese_chars_in_file(path: Path, encoding: str = "utf-8-sig") -> int:
    return count_chinese_chars(path.read_text(encoding=encoding, errors="replace"))


def validate_chinese_char_count(
    text: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
    label: str = "text",
) -> tuple[int, list[str]]:
    count = count_chinese_chars(text)
    errors: list[str] = []
    if minimum is not None and count < minimum:
        errors.append(f"{label} 中文字数不足：{count} < {minimum}")
    if maximum is not None and count > maximum:
        errors.append(f"{label} 中文字数超长：{count} > {maximum}")
    return count, errors


def main() -> int:
    reconfigure_stdio_utf8()
    parser = argparse.ArgumentParser(description="Count Chinese characters only")
    parser.add_argument("--input", type=Path, help="Text file path")
    parser.add_argument("--text", type=str, help="Raw text input")
    parser.add_argument("--encoding", type=str, default="utf-8-sig", help="Input encoding")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if not args.input and args.text is None:
        print("[ERROR] Provide either --input or --text", file=sys.stderr)
        return 2

    if args.input and args.text is not None:
        print("[ERROR] Use only one source: --input or --text", file=sys.stderr)
        return 2

    if args.input:
        if not args.input.exists():
            print(f"[ERROR] File not found: {args.input}", file=sys.stderr)
            return 1
        count = count_chinese_chars_in_file(args.input, encoding=args.encoding)
        source = str(args.input)
    else:
        count = count_chinese_chars(args.text or "")
        source = "inline_text"

    if args.json:
        print(json.dumps({"source": source, "chinese_chars": count}, ensure_ascii=False, indent=2))
    else:
        print(count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
