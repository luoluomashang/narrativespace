#!/usr/bin/env python3
"""
Regression checks for workflow hard guards.

Checks:
1) Step10 hard-stop must fail when scene plan is missing.
2) Step10 template routing must respect explicit --writing-mode.
3) validate_state step10 gate must pass for a valid chapter.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def main() -> int:
    p = argparse.ArgumentParser(description="Run workflow guard regressions")
    p.add_argument("--project-dir", required=True, help="Project root or .xushikj path")
    p.add_argument("--good-chapter", type=int, default=1, help="Existing chapter index for positive checks")
    p.add_argument("--bad-chapter", type=int, default=999, help="Missing chapter index for negative checks")
    p.add_argument("--min-chapter-chars", type=int, default=2500, help="Minimum Chinese char threshold")
    args = p.parse_args()

    script_dir = Path(__file__).resolve().parent
    assemble = script_dir / "assemble_prompt.py"
    validate = script_dir / "validate_state.py"

    work_dir = Path(args.project_dir)
    out_dir = work_dir / "drafts"
    out_dir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []

    # 1) Hard stop failure case.
    rc, out = run_cmd(
        [
            sys.executable,
            str(assemble),
            "--project-dir",
            str(args.project_dir),
            "--step",
            "10",
            "--chapter",
            str(args.bad_chapter),
            "--output",
            "file",
            "--output-file",
            str(out_dir / "regression_should_fail_step10.md"),
        ]
    )
    if rc == 0 or "Step10 HARD STOP" not in out:
        failures.append("Expected Step10 hard-stop failure did not occur.")

    # 2) Explicit writing mode routing.
    pipeline_path = out_dir / "regression_step10_pipeline.md"
    rc_pipe, out_pipe = run_cmd(
        [
            sys.executable,
            str(assemble),
            "--project-dir",
            str(args.project_dir),
            "--step",
            "10",
            "--chapter",
            str(args.good_chapter),
            "--writing-mode",
            "pipeline",
            "--output",
            "file",
            "--output-file",
            str(pipeline_path),
        ]
    )
    if rc_pipe != 0:
        failures.append("Pipeline mode assembly failed unexpectedly.")
    elif "# 章节写作（步骤10A）" not in pipeline_path.read_text(encoding="utf-8"):
        failures.append("Pipeline prompt content is not step10A template.")

    interactive_path = out_dir / "regression_step10_interactive.md"
    rc_int, out_int = run_cmd(
        [
            sys.executable,
            str(assemble),
            "--project-dir",
            str(args.project_dir),
            "--step",
            "10",
            "--chapter",
            str(args.good_chapter),
            "--writing-mode",
            "interactive",
            "--output",
            "file",
            "--output-file",
            str(interactive_path),
        ]
    )
    if rc_int != 0:
        failures.append("Interactive mode assembly failed unexpectedly.")
    elif "# 互动写作（步骤10B）" not in interactive_path.read_text(encoding="utf-8"):
        failures.append("Interactive prompt content is not step10B template.")

    # 3) Step10 gate validation.
    rc_val, out_val = run_cmd(
        [
            sys.executable,
            str(validate),
            "--project-dir",
            str(work_dir.parent if work_dir.name == ".xushikj" else work_dir),
            "--for-step10",
            "--chapter",
            str(args.good_chapter),
            "--min-chapter-chars",
            str(args.min_chapter_chars),
        ]
    )
    if rc_val != 0:
        failures.append("validate_state step10 gate failed unexpectedly.")

    if failures:
        print("[regression] FAILED")
        for item in failures:
            print(f"- {item}")
        print("\n[debug] assemble_fail_output:\n" + out)
        print("\n[debug] assemble_pipeline_output:\n" + out_pipe)
        print("\n[debug] assemble_interactive_output:\n" + out_int)
        print("\n[debug] validate_output:\n" + out_val)
        return 1

    print("[regression] PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
