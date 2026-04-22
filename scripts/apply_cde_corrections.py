#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_cde_corrections.py — CLI wrapper for Feature 1 F1e1.

Applies a batch of CDE diagnostics to an Ableton ``.als`` project and
writes the updated diagnostic statuses back to the source JSON.

Typical usage:

    python scripts/apply_cde_corrections.py \\
        --als "Rapports test développement/Acid_Drops_Sections_TFP.als" \\
        --diagnostics-json "Rapports test développement/Acid_Drops_Sections_TFP_diagnostics.json" \\
        --filter severity=critical \\
        --yes

Dry-run (show the preview but do not write):

    python scripts/apply_cde_corrections.py \\
        --als <path> --diagnostics-json <json> --dry-run

Exit codes:

    0  success (diagnostics applied OR dry-run preview shown)
    1  input error (missing file, malformed JSON, argparse failure)
    2  nothing applied (filter left zero diagnostics, or every entry
       was skipped — check the report warnings)

F1e2 will add ``--revert``, ``--peak-xlsx`` (peak-following), and
``--tolerance-semitones``. This minimal F1e1 ships the section-locked
apply path only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cde_apply import write_dynamic_eq8_from_cde_diagnostics  # noqa: E402
from cde_engine import (  # noqa: E402
    CorrectionDiagnostic,
    dump_diagnostics_to_json,
    load_diagnostics_from_json,
)


_VALID_FILTER_KEYS = ("severity", "issue_type")


def _apply_filter(
    diagnostics: List[CorrectionDiagnostic],
    filter_spec: Optional[str],
) -> List[CorrectionDiagnostic]:
    """Sub-select diagnostics by ``severity`` or ``issue_type``.

    ``filter_spec`` format: ``"key=value"`` or ``"key=v1,v2,v3"``
    (comma-separated alternatives).

    Unknown keys trigger a warning and return the diagnostics
    unchanged — we want the CLI to keep running when a caller
    mistypes a filter rather than silently drop everything.
    """
    if not filter_spec:
        return diagnostics
    key, _, value = filter_spec.partition("=")
    key = key.strip()
    value = value.strip()
    if not key or not value:
        print(
            f"WARNING: ignoring malformed filter {filter_spec!r} "
            f"(expected 'key=value')",
            file=sys.stderr,
        )
        return diagnostics
    if key not in _VALID_FILTER_KEYS:
        print(
            f"WARNING: unknown filter key {key!r} — "
            f"known keys: {', '.join(_VALID_FILTER_KEYS)}",
            file=sys.stderr,
        )
        return diagnostics
    values = {v.strip() for v in value.split(",") if v.strip()}
    return [
        d for d in diagnostics
        if getattr(d, key, None) in values
    ]


def _print_report_summary(report, dry_run: bool) -> None:
    print()
    header = "DRY-RUN REPORT" if dry_run else "APPLY REPORT"
    print(f"=== {header} ===")
    print(f"Applied           : {len(report.applied)}")
    print(f"Skipped           : {len(report.skipped)}")
    if report.skipped:
        sidechain_n = report.sidechain_count()
        if sidechain_n:
            print(f"  - sidechain (F1.5) : {sidechain_n}")
        primary_none_n = sum(
            1 for (_, r) in report.skipped
            if "primary_correction is None" in r
        )
        if primary_none_n:
            print(f"  - primary=None     : {primary_none_n}")
        other = len(report.skipped) - sidechain_n - primary_none_n
        if other:
            print(f"  - other            : {other}")
    print(f"Devices created   : {len(report.devices_created)}")
    print(f"Envelopes written : {report.envelopes_written}")
    if report.backup_path:
        print(f"Backup            : {report.backup_path}")
    if report.warnings:
        print(f"Warnings          : {len(report.warnings)}")
        for w in report.warnings[:5]:
            print(f"  - {w}")
        if len(report.warnings) > 5:
            print(f"  ... ({len(report.warnings) - 5} more)")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="apply_cde_corrections",
        description="Apply a batch of CDE diagnostics to an Ableton .als.",
    )
    parser.add_argument(
        "--als", required=True, type=Path,
        help="Path to the .als to modify.",
    )
    parser.add_argument(
        "--diagnostics-json", required=True, type=Path,
        help=(
            "Path to the diagnostics JSON (input). After a successful "
            "apply the file is re-dumped with updated "
            "``application_status`` / ``applied_backup_path`` values."
        ),
    )
    parser.add_argument(
        "--filter", default=None, metavar="KEY=VALUE[,VALUE...]",
        help=(
            "Sub-select diagnostics. Keys: severity, issue_type. "
            "Example: --filter severity=critical — or comma-separated "
            "alternatives: --filter severity=critical,moderate"
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show the preview and return, do NOT write the .als.",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help=(
            "Skip the interactive 'Procéder ? (y/N)' prompt — required "
            "for non-interactive / CI usage."
        ),
    )
    args = parser.parse_args(argv)

    if not args.als.exists():
        print(f"ERROR: .als not found: {args.als}", file=sys.stderr)
        return 1
    if not args.diagnostics_json.exists():
        print(
            f"ERROR: diagnostics JSON not found: {args.diagnostics_json}",
            file=sys.stderr,
        )
        return 1

    # Load once — ``diagnostics`` keeps references to the same objects
    # as ``filtered``, so any in-place mutation the writer does on a
    # filtered entry is visible when we re-dump the full list.
    diagnostics = load_diagnostics_from_json(args.diagnostics_json)
    print(
        f"Loaded {len(diagnostics)} diagnostics from "
        f"{args.diagnostics_json.name}"
    )

    filtered = _apply_filter(diagnostics, args.filter)
    if args.filter:
        dropped = len(diagnostics) - len(filtered)
        print(
            f"After filter {args.filter!r}: {len(filtered)} retained, "
            f"{dropped} dropped."
        )

    if not filtered:
        print("No diagnostics to apply after filtering. Done.")
        return 2

    report = write_dynamic_eq8_from_cde_diagnostics(
        args.als, filtered,
        dry_run=args.dry_run,
        _skip_confirmation=args.yes,
    )

    _print_report_summary(report, dry_run=args.dry_run)

    # Re-dump the full diagnostics list on success. Writing even when
    # nothing was applied would be wasteful, so we gate on
    # ``report.applied``. Dry-runs never write back.
    if not args.dry_run and report.applied:
        dump_diagnostics_to_json(diagnostics, args.diagnostics_json)
        print(
            f"\nUpdated diagnostics JSON: {args.diagnostics_json.name}"
        )
    elif not args.dry_run and not report.applied:
        print(
            "\nNothing applied — diagnostics JSON untouched. "
            "Check warnings above."
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
