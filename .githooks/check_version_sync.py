#!/usr/bin/env python3
"""
Pre-commit version sync check for Mix Analyzer.

Reads `VERSION` from mix_analyzer.py (canonical) and compares it to the
docstring version stamp (line ~4) in 7 other production files.

Triggers only if any of those 8 files is staged in the current commit —
otherwise exits 0 silently. Aborts the commit (exit 1) if any drift.

Mirrors the logic of .claude/agents/version-sync-checker.md but runs as a
deterministic git hook (no LLM needed).
"""
import re
import subprocess
import sys
from pathlib import Path

VERSIONED_FILES = [
    "mix_analyzer.py",
    "als_utils.py",
    "spectral_evolution.py",
    "feature_storage.py",
    "eq8_automation.py",
    "automation_map.py",
    "section_detector.py",
    "cde_engine.py",
]
CANONICAL = "mix_analyzer.py"
VERSION_PATTERN = re.compile(r"v?(\d+\.\d+\.\d+)")
CONST_PATTERN = re.compile(r"^VERSION\s*=\s*['\"](\d+\.\d+\.\d+)['\"]", re.MULTILINE)


def staged_files():
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True, check=True,
    )
    return set(out.stdout.strip().splitlines())


def find_version_in_docstring(path):
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines()[:15]:
        m = VERSION_PATTERN.search(line)
        if m:
            return m.group(1)
    return None


def find_canonical_version():
    text = Path(CANONICAL).read_text(encoding="utf-8", errors="ignore")
    m = CONST_PATTERN.search(text)
    return m.group(1) if m else None


def main():
    staged = staged_files()
    if not (staged & set(VERSIONED_FILES)):
        return 0

    canonical = find_canonical_version()
    if not canonical:
        print("[pre-commit] FAIL: cannot find VERSION constant in mix_analyzer.py", file=sys.stderr)
        return 1

    drifts = []
    for f in VERSIONED_FILES:
        if not Path(f).exists():
            continue
        v = find_version_in_docstring(f)
        if v is None:
            drifts.append((f, "no version stamp found"))
        elif v != canonical:
            drifts.append((f, v))

    if drifts:
        print(f"[pre-commit] VERSION OUT-OF-SYNC. Canonical: v{canonical}", file=sys.stderr)
        for f, v in drifts:
            print(f"    {f}: {v}", file=sys.stderr)
        print("    Fix the docstrings to match VERSION, then re-commit.", file=sys.stderr)
        print("    To bypass (not recommended): git commit --no-verify", file=sys.stderr)
        return 1

    print(f"[pre-commit] version sync OK (v{canonical})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
