from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def reconfigure_stdio_utf8() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def read_text_utf8(path: Path, default: str | None = None, *, strip: bool = False) -> str:
    if not path.exists():
        if default is None:
            raise FileNotFoundError(path)
        return default
    text = path.read_text(encoding='utf-8-sig', errors='replace')
    return text.strip() if strip else text


def write_text_utf8(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')


def read_json_utf8(path: Path) -> dict[str, Any]:
    with path.open('r', encoding='utf-8-sig', errors='replace') as fh:
        payload = json.load(fh)
    return payload if isinstance(payload, dict) else {}


def subprocess_utf8_kwargs() -> dict[str, Any]:
    return {
        'text': True,
        'encoding': 'utf-8',
        'errors': 'replace',
    }
