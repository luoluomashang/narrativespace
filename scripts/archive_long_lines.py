#!/usr/bin/env python3
"""
archive_long_lines.py — 叙事空间创作系统 记忆自动归档脚本

当 memory.md 超过1500字时，自动识别并转移符合条件的内容到 archive_memory.json

用法：
    python3 archive_long_lines.py --memory-path .xushikj/memory.md \\
                                  --archive-path .xushikj/archive_memory.json \\
                                  --kb-path .xushikj/knowledge_base.json
"""

import json
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


def _reconfigure_stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def identify_archivable_sections(memory_content: str) -> List[Dict[str, Any]]:
    """
    分析memory.md内容，识别可归档的内容块。
    
    返回: [{start_line, end_line, category, content, condition_id}]
    """
    lines = memory_content.split("\n")
    archivable = []
    
    # 1. 识别"已完结卷次"的标记 (---【卷X 完成】---)
    for i, line in enumerate(lines):
        if re.match(r"^[-]{3,}【卷\d+ 完成】[-]{3,}$", line):
            # 这一块前面的内容可能是可归档的
            archivable.append({
                "start_line": 0 if i == 0 else i - 10,
                "end_line": i,
                "category": "historical_outline",
                "condition_id": "condition_1"
            })
    
    # 2. 识别"已回收伏笔"标记 (标签: #伏笔/已回收 或 status: resolved)
    for i, line in enumerate(lines):
        if "#伏笔/已回收" in line or "【已回收】" in line:
            # 前后10行作为上下文
            start = max(0, i - 5)
            end = min(len(lines), i + 10)
            archivable.append({
                "start_line": start,
                "end_line": end,
                "category": "resolved_foreshadow",
                "condition_id": "condition_2"
            })
    
    # 3. 识别"已死亡角色"的传记
    for i, line in enumerate(lines):
        if re.search(r"\[已死亡\]|status: 死亡|status: deceased", line):
            start = max(0, i - 3)
            end = min(len(lines), i + 15)
            archivable.append({
                "start_line": start,
                "end_line": end,
                "category": "dead_character",
                "condition_id": "condition_3"
            })
    
    # 4. 识别"历史版本大纲"标记 (备注: [备份版本] 或 [旧版])
    for i, line in enumerate(lines):
        if "[备份版本]" in line or "[旧版本]" in line or "[弃用]" in line:
            start = max(0, i - 2)
            end = min(len(lines), i + 10)
            archivable.append({
                "start_line": start,
                "end_line": end,
                "category": "historical_outline",
                "condition_id": "condition_4"
            })
    
    return archivable


def extract_archivable_content(
    memory_content: str,
    archivable_sections: List[Dict],
    current_chapter: int,
    kb: Dict
) -> List[Dict[str, Any]]:
    """
    从识别出的可归档段落中提取内容，生成archive_memory条目。
    
    返回: [archive_entry]
    """
    lines = memory_content.split("\n")
    entries = []
    
    for section in archivable_sections:
        start = section["start_line"]
        end = section["end_line"]
        content_lines = lines[start:end]
        content = "\n".join(content_lines).strip()
        
        if not content or len(content) < 20:
            continue
        
        # 提取关键词
        keywords = []
        for word in ["伏笔", "反派", "世界观", "角色", "秘密", "关系", "时间线"]:
            if word in content:
                keywords.append(word)
        
        # 评估recall概率（基于内容长度和关键词数量）
        recall_probability = "low"
        if len(keywords) >= 2:
            recall_probability = "high"
        elif len(keywords) == 1 or len(content) > 500:
            recall_probability = "medium"
        
        entry = {
            "id": f"entry_{len(entries):03d}",
            "category": section["category"],
            "content": content,
            "archived_at_chapter": current_chapter,
            "recall_probability": recall_probability,
            "keywords": keywords,
            "timestamp": datetime.now().isoformat()
        }
        entries.append(entry)
    
    return entries


def load_or_create_archive(archive_path: Path) -> Dict[str, Any]:
    """加载或创建 archive_memory.json"""
    if archive_path.exists():
        with open(archive_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    return {
        "version": "1.0",
        "entries": [],
        "metadata": {
            "last_archived_chapter": 0,
            "total_entries": 0,
            "volume_snapshots": {}
        }
    }


def save_archive(archive: Dict, archive_path: Path) -> None:
    """保存 archive_memory.json"""
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)


def prune_memory(memory_content: str, archivable_sections: List[Dict]) -> str:
    """
    从memory.md中删除已归档的行。
    
    为了安全，我们标记而不是删除。
        - 将被归档的行改为 <!-- ARCHIVED -->[原始内容]<!-- /ARCHIVED -->
    """
    lines = memory_content.split("\n")
    
    # 标记所有待删除的行
    to_mark = set()
    for section in archivable_sections:
        for i in range(section["start_line"], section["end_line"]):
            to_mark.add(i)
    
    # 实际上，为了保守起见，仅将关键行标记，不真正删除
    # 而是插入"已归档"标记
    result_lines = []
    for i, line in enumerate(lines):
        if i in to_mark and line.strip() and not line.strip().startswith("#"):
            # 非标题行，插入标记
            result_lines.append(f"<!-- ARCHIVED CH{i} --> {line}")
        else:
            result_lines.append(line)
    
    return "\n".join(result_lines)


def main():
    import argparse
    _reconfigure_stdout_utf8()
    
    parser = argparse.ArgumentParser(description="记忆自动归档脚本")
    parser.add_argument("--memory-path", required=True, help="memory.md 路径")
    parser.add_argument("--archive-path", required=True, help="archive_memory.json 路径")
    parser.add_argument("--kb-path", required=True, help="knowledge_base.json 路径")
    parser.add_argument("--current-chapter", type=int, default=1, help="当前章节号")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入")
    
    args = parser.parse_args()
    
    memory_path = Path(args.memory_path)
    archive_path = Path(args.archive_path)
    kb_path = Path(args.kb_path)
    
    if not memory_path.exists():
        print(f"ERROR: memory.md 不存在: {memory_path}", file=sys.stderr)
        sys.exit(1)
    
    # 加载memory、archive、kb
    memory_content = memory_path.read_text(encoding="utf-8")
    
    archive = load_or_create_archive(archive_path)
    
    kb = {}
    if kb_path.exists():
        with open(kb_path, "r", encoding="utf-8") as f:
            kb = json.load(f)
    
    # 检查是否超过字数限制
    memory_char_count = len(memory_content)
    print(f"当前 memory.md 大小: {memory_char_count} 字")
    
    if memory_char_count <= 1500:
        print("✅ memory.md 未超限，无需归档")
        return
    
    print(f"⚠️  memory.md 超过限制 (>{1500} 字)，开始归档...")
    
    # 识别可归档段落
    archivable_sections = identify_archivable_sections(memory_content)
    print(f"   识别出 {len(archivable_sections)} 个可归档段落")
    
    # 提取内容生成archive条目
    new_entries = extract_archivable_content(
        memory_content,
        archivable_sections,
        args.current_chapter,
        kb
    )
    
    if not new_entries:
        print("   ❌ 未识别到可归档内容，请手动补充标记")
        return
    
    print(f"   提取 {len(new_entries)} 条新条目")
    
    # 合并到archive
    archive["entries"].extend(new_entries)
    archive["metadata"]["total_entries"] = len(archive["entries"])
    archive["metadata"]["last_archived_chapter"] = args.current_chapter
    
    if args.dry_run:
        print("\n【干运行预览】")
        print(f"将添加到 archive_memory.json:")
        for entry in new_entries:
            print(f"  - {entry['id']}: {entry['category']} (recall={entry['recall_probability']})")
        print(f"\n总条目数: {len(archive['entries'])}")
    else:
        # 写入archive
        save_archive(archive, archive_path)
        print(f"✅ 已保存 {len(new_entries)} 条到 {archive_path}")
        
        # 标记memory.md中被归档的行（不真正删除）
        pruned_memory = prune_memory(memory_content, archivable_sections)
        memory_path.write_text(pruned_memory, encoding="utf-8")
        print(f"✅ 已标记 memory.md 中的归档行")
        
        # 显示当前memory.md新大小
        new_size = len(pruned_memory)
        print(f"\n【结果】memory.md: {memory_char_count} → {new_size} 字")


if __name__ == "__main__":
    main()
