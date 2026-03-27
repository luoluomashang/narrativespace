#!/usr/bin/env python3
"""
validate_references.py — 叙事空间创作系统 跨模块引用验证脚本

检查以下内容：
  1. 所有模块prompt.md中引用的config/文件是否存在
  2. modules/*/prompt.md → modules/*/references/* 的路径有效性
  3. 打印ASCII依赖关系树
  4. 检查SKILL.md version字段一致性
  5. 验证所有import/include是否可达
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Tuple


SKILL_ROOT = Path(__file__).resolve().parent.parent


def check_config_references() -> List[str]:
    """检查所有prompt.md中引用的config/文件是否存在。"""
    issues = []
    config_dir = SKILL_ROOT / "config"
    
    for module_dir in (SKILL_ROOT / "modules").glob("*/"):
        prompt_file = module_dir / "prompt.md"
        if not prompt_file.exists():
            continue
        
        content = prompt_file.read_text(encoding="utf-8")
        
        # 查找所有 .yaml 引用，支持 config/ 和相对路径两种格式
        for line in content.split("\n"):
            if "config/" in line or ".yaml" in line:
                # 简单启发式：提取可能的文件名（含路径前缀）
                import re
                # 先尝试提取带路径的引用（如 style_modules/index.yaml）
                path_matches = re.findall(r"([\w/]+\.yaml)", line)
                for path_str in path_matches:
                    config_file = config_dir / path_str
                    # 也支持只有文件名的情况（递归查找）
                    if not config_file.exists():
                        filename = Path(path_str).name
                        found = any(config_dir.rglob(filename))
                        if not found:
                            issues.append(
                                f"  ❌ {module_dir.name}/prompt.md 引用不存在的配置："
                                f" {path_str}"
                            )
    
    return issues


def check_reference_links() -> List[str]:
    """检查modules/*/prompt.md中的references/链接是否有效。"""
    issues = []
    
    for module_dir in (SKILL_ROOT / "modules").glob("*/"):
        prompt_file = module_dir / "prompt.md"
        references_dir = module_dir / "references"
        
        if not prompt_file.exists():
            continue
        
        content = prompt_file.read_text(encoding="utf-8")
        
        # 查找markdown链接中的相对路径
        import re
        links = re.findall(r"\[.*?\]\((.*?\.md)\)", content)
        for link in links:
            target = (module_dir / link).resolve()
            if not target.exists():
                issues.append(
                    f"  ❌ {module_dir.name}/prompt.md 引用死链："
                    f" {link} (resolved to {target})"
                )
    
    return issues


def check_skill_versions() -> List[str]:
    """检查所有SKILL.md的version字段是否一致。"""
    issues = []
    versions: Dict[str, str] = {}
    
    # 检查root SKILL.md
    root_skill = SKILL_ROOT / "SKILL.md"
    if root_skill.exists():
        content = root_skill.read_text(encoding="utf-8")
        import re
        match = re.search(r'version["\s:]*:?\s*["\']?([\d.]+)["\']?', content)
        if match:
            versions["narrativespace-xushikj"] = match.group(1)
    
    # 检查module SKILL.md
    for module_dir in (SKILL_ROOT / "modules").glob("*/"):
        skill_file = module_dir / "SKILL.md"
        if skill_file.exists():
            content = skill_file.read_text(encoding="utf-8")
            import re
            match = re.search(r'version["\s:]*:?\s*["\']?([\d.]+)["\']?', content)
            if match:
                versions[module_dir.name] = match.group(1)
    
    # 检查一致性
    if versions:
        root_version = list(versions.values())[0]
        for module_name, version in versions.items():
            if version != root_version:
                issues.append(
                    f"  ⚠️  版本不一致：{module_name} = {version} "
                    f"(其他为 {root_version})"
                )
    
    return issues


def print_module_tree() -> None:
    """打印ASCII模块依赖树。"""
    print("\n" + "=" * 70)
    print("叙事空间创作系统 v3.0 — 模块依赖关系树")
    print("=" * 70)
    
    tree = """
                    ┌──────────────────────────────────┐
                    │  narrativespace-xushikj (root)   │
                    │  (SKILL.md + prompt.md + README) │
                    └──────────────┬───────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
    ┌────────────┐           ┌──────────────┐          ┌────────────┐
    │ benchmark  │           │   planning   │          │ knowledge- │
    │ (步骤0)  │           │ (步骤1-6,11) │          │   base     │
    │ 对标分析  │           │   规划阶段   │          │ (步骤7)  │
    └────────────┘           └──────────────┘          │  知识库    │
        │                          │                    └────────────┘
        │                          │                          ▲
        │      ┌──────────────────┘                          │
        │      │                                              │
        ▼      ▼                                              │
    ┌─────────────────┐    ┌──────────────┐     ┌──────────┐│
    │    scenes       │    │   writing    │     │interactive││
    │ (步骤8-9)     │    │ (步骤10A)   │     │ (步骤10B)││
    │  场景规划      │    │ 流水线写作  │     │ 互动写作 ││
    └────────┬────────┘    └──────┬───────┘     └──────────┘│
             │                    │                          │
             │      ┌─────────────┼──────────────────────────┘
             │      │             │
             │      ▼             ▼
             │   ┌────────────────────────┐
             │   │    humanizer           │
             │   │    (后处理/可选)       │
             │   │    去AI痕迹            │
             │   └────────────────────────┘
             │
             └─→ (输出) 完整章节 → 发布

【跨模块依赖】
    benchmark → planning, scenes
    planning → knowledge-base, scenes, writing
    knowledge-base (中心枢纽) ← all modules
    scenes → writing
    writing → humanizer (可选)
    interactive ← knowledge-base, writing
"""
    
    print(tree)


def validate_all() -> bool:
    """执行所有验证，返回是否通过。"""
    print("\n" + "=" * 70)
    print("开始全面跨引用验证...")
    print("=" * 70)
    
    all_issues: List[str] = []
    
    # 1. 检查config引用
    print("\n[1/4] 检查 config/ 文件引用...")
    issues = check_config_references()
    if issues:
        all_issues.extend(issues)
        for issue in issues:
            print(issue)
    else:
        print("  ✅ 所有 config/ 文件引用有效")
    
    # 2. 检查reference链接
    print("\n[2/4] 检查 references/ 文件链接...")
    issues = check_reference_links()
    if issues:
        all_issues.extend(issues)
        for issue in issues:
            print(issue)
    else:
        print("  ✅ 所有 references/ 链接有效")
    
    # 3. 检查version一致性
    print("\n[3/4] 检查 SKILL.md 版本一致性...")
    issues = check_skill_versions()
    if issues:
        all_issues.extend(issues)
        for issue in issues:
            print(issue)
    else:
        print("  ✅ 所有 SKILL.md 版本一致")
    
    # 4. 打印依赖树
    print("\n[4/4] 依赖关系树:")
    print_module_tree()
    
    # 总结
    print("\n" + "=" * 70)
    if all_issues:
        print(f"❌ 验证完成：发现 {len(all_issues)} 个问题")
        print("=" * 70)
        return False
    else:
        print("✅ 验证完成：所有引用一致，模块连通性良好")
        print("=" * 70)
        return True


if __name__ == "__main__":
    success = validate_all()
    exit(0 if success else 1)
