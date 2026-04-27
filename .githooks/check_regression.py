#!/usr/bin/env python3
"""
Pre-push regression check for Mix Analyzer.

Decides between two test suites based on what is being pushed:

- FAST suite (~10-15s): test_spectral_evolution.py, test_eq8_automation.py,
  test_v25_integration.py — runs when only .als / build scripts / docs
  changed.

- FULL suite (~2 min): pytest tests/ -v — runs when any of the 8
  production files or any test file changed.

Reads pre-push hook arguments from stdin (one line per ref pushed:
"<local_ref> <local_sha> <remote_ref> <remote_sha>"). For each ref,
diffs against the remote sha to find changed files.

Exit 0 = tests pass, push proceeds.
Exit 1 = tests fail OR cannot run, push blocked.
"""
import subprocess
import sys
from pathlib import Path

PROD_FILES = {
    "mix_analyzer.py",
    "als_utils.py",
    "spectral_evolution.py",
    "feature_storage.py",
    "eq8_automation.py",
    "automation_map.py",
    "section_detector.py",
    "cde_engine.py",
    "tfp_parser.py",
    "tfp_coherence.py",
}

FAST_SUITE = [
    "tests/test_spectral_evolution.py",
    "tests/test_eq8_automation.py",
    "tests/test_v25_integration.py",
]

ZERO_SHA = "0000000000000000000000000000000000000000"


def changed_files_for_push():
    """Read pre-push refs from stdin, return set of changed file paths."""
    changed = set()
    for line in sys.stdin:
        parts = line.strip().split()
        if len(parts) != 4:
            continue
        local_ref, local_sha, remote_ref, remote_sha = parts
        if local_sha == ZERO_SHA:
            # Branch deletion — nothing to test
            continue
        if remote_sha == ZERO_SHA:
            # New branch on remote — diff against the merge base with main
            try:
                base = subprocess.check_output(
                    ["git", "merge-base", local_sha, "main"],
                    text=True, stderr=subprocess.DEVNULL,
                ).strip()
            except subprocess.CalledProcessError:
                # Cannot determine base — fall back to all production files
                return None  # signal: run full suite
            range_spec = f"{base}..{local_sha}"
        else:
            range_spec = f"{remote_sha}..{local_sha}"
        out = subprocess.check_output(
            ["git", "diff", "--name-only", range_spec],
            text=True,
        )
        for f in out.strip().splitlines():
            if f.strip():
                changed.add(f.strip())
    return changed


def needs_full_suite(changed):
    """True if any prod file or any tests/* file is in the changeset."""
    if changed is None:
        return True
    for f in changed:
        if f in PROD_FILES:
            return True
        if f.startswith("tests/") and f.endswith(".py"):
            return True
    return False


def run_pytest(args):
    """Invoke pytest with given args. Returns exit code."""
    cmd = [sys.executable, "-m", "pytest", *args]
    print(f"[pre-push] Running: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd)
    return result.returncode


def main():
    changed = changed_files_for_push()
    if changed is not None and not changed:
        print("[pre-push] No file changes detected, skipping tests", file=sys.stderr)
        return 0

    if needs_full_suite(changed):
        print("[pre-push] Production code or tests changed — running FULL suite", file=sys.stderr)
        rc = run_pytest(["tests/", "-q", "--tb=short"])
    else:
        # Filter fast-suite paths to those that actually exist
        existing = [t for t in FAST_SUITE if Path(t).exists()]
        if not existing:
            print("[pre-push] Fast suite files missing, skipping (no relevant code touched)", file=sys.stderr)
            return 0
        print(f"[pre-push] Only docs/scripts/.als changed — running FAST suite ({len(existing)} files)", file=sys.stderr)
        rc = run_pytest([*existing, "-q", "--tb=short"])

    if rc != 0:
        print(
            "[pre-push] Tests FAILED. Push blocked.\n"
            "    Fix the failures and try Push again.\n"
            "    To bypass (not recommended): git push --no-verify",
            file=sys.stderr,
        )
        return 1
    print("[pre-push] Tests passed — proceeding with push", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
