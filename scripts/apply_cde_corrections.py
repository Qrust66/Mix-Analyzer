#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_cde_corrections.py — CLI wrapper for Feature 1 (F1e1 + F1e2).

Applies a batch of CDE diagnostics to an Ableton ``.als`` project and
writes the updated diagnostic statuses back to the source JSON.

Typical usage — section-locked apply filtered to critical:

    python scripts/apply_cde_corrections.py \\
        --als "Rapports test développement/Acid_Drops_Sections_TFP.als" \\
        --diagnostics-json "Rapports test développement/Acid_Drops_Sections_TFP_diagnostics.json" \\
        --filter severity=critical \\
        --yes

Peak-following (F1e2) — use trajectories from a Mix Analyzer report:

    python scripts/apply_cde_corrections.py \\
        --als <.als>                      \\
        --diagnostics-json <diags.json>   \\
        --peak-xlsx <Acid_Drops_MixAnalyzer_*.xlsx>  \\
        --tolerance-semitones 2.0         \\
        --yes

Revert (F1e2) — restore the ``.als`` from its ``.als.v24.bak``:

    # Revert every diagnostic currently marked "applied":
    python scripts/apply_cde_corrections.py \\
        --als <.als> --diagnostics-json <diags.json> --revert

    # Targeted revert of specific diagnostic IDs:
    python scripts/apply_cde_corrections.py \\
        --als <.als> --diagnostics-json <diags.json> \\
        --revert D1,D2

Dry-run (show the preview but do not write):

    python scripts/apply_cde_corrections.py \\
        --als <path> --diagnostics-json <json> --dry-run

Exit codes:

    0  success (apply / revert / dry-run preview)
    1  input error (missing file, malformed JSON, argparse failure)
    2  nothing applied (filter left zero diagnostics, or every entry
       was skipped — check the report warnings)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import re  # noqa: E402

from cde_apply import (  # noqa: E402
    DEFAULT_FREQ_CLUSTER_TOLERANCE_SEMITONES,
    load_peak_trajectories_from_excel,
    revert_cde_application,
    write_dynamic_eq8_from_cde_diagnostics,
)
from cde_engine import (  # noqa: E402
    CorrectionDiagnostic,
    dump_diagnostics_to_json,
    load_diagnostics_from_json,
)


_VALID_FILTER_KEYS = ("severity", "issue_type")

# Excel track names carry the project prefix + .wav extension + the
# TFP ``[X_Y]`` bracket (``/`` replaced with ``_`` during bounce —
# slashes are illegal in filenames). Ableton's EffectiveName inside
# the ``.als`` uses ``[X/Y]``. This regex matches only valid TFP
# role pairs so we don't rewrite unrelated underscores.
_TFP_UNDERSCORE_IN_BRACKETS_RE = re.compile(r"\[([HSA])_([RHMT])\]")


def _excel_track_to_ableton_name(wav_name: str) -> str:
    """Convert a WAV-filename-style track name from the Mix Analyzer
    Excel report into the Ableton EffectiveName format used inside
    the ``.als``.

    Input examples  → output:
        "Acid_Drops [A_T] Ambience.wav"  → "[A/T] Ambience"
        "Acid_Drops [H_R] Kick 1.wav"    → "[H/R] Kick 1"
        "BUS Kick.wav"                    → "BUS Kick"

    The transform is conservative:
        1. Strip a trailing ``.wav`` (case-insensitive).
        2. Drop everything before the first ``[`` — that's the
           bouncer's project prefix (e.g. ``"Acid_Drops "``).
        3. Convert ``[H_R]`` → ``[H/R]`` only for valid role pairs.

    Names that have no ``[`` are returned with only the extension
    stripped — this preserves tracks without a TFP prefix (e.g.
    busses, return tracks) in a form ``find_track_by_name`` can
    still resolve.
    """
    name = wav_name
    if name.lower().endswith(".wav"):
        name = name[:-4]
    bracket_idx = name.find("[")
    if bracket_idx > 0:
        name = name[bracket_idx:]
    name = _TFP_UNDERSCORE_IN_BRACKETS_RE.sub(r"[\1/\2]", name)
    return name


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
    parser.add_argument(
        "--peak-xlsx", default=None, type=Path, metavar="PATH",
        help=(
            "F1e2. Path to a Mix Analyzer ``.xlsx`` report. When "
            "provided, the writer reads ``_track_peak_trajectories`` "
            "from the sheet and enables ``peak_follow=True`` so the "
            "Freq + Gain + Q envelopes follow the actual peaks "
            "instead of holding section-locked values."
        ),
    )
    parser.add_argument(
        "--tolerance-semitones", default=DEFAULT_FREQ_CLUSTER_TOLERANCE_SEMITONES,
        type=float, metavar="FLOAT",
        help=(
            "F1e2. Frequency clustering tolerance in semitones "
            "(default: %(default)s). Narrower = more bands per track, "
            "wider = fewer bands but broader Q-to-Q matches."
        ),
    )
    parser.add_argument(
        "--revert", nargs="?", const="", default=None, metavar="IDS",
        help=(
            "F1e2. Revert mode — restore the ``.als`` from "
            "``.als.v24.bak`` and flip matching diagnostics to "
            "``application_status=\"reverted\"``. Pass comma-separated "
            "diagnostic_ids to revert a subset (e.g. ``--revert D1,D2``) "
            "or use ``--revert`` alone to roll back every currently "
            "applied diagnostic."
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

    # F1e2 — revert branch takes precedence over the apply path.
    if args.revert is not None:
        return _run_revert(args, diagnostics)

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

    # F1e2 — optional peak-following from an Excel report.
    peak_trajectories = None
    peak_follow = False
    if args.peak_xlsx is not None:
        if not args.peak_xlsx.exists():
            print(
                f"ERROR: peak xlsx not found: {args.peak_xlsx}",
                file=sys.stderr,
            )
            return 1
        peak_trajectories = load_peak_trajectories_from_excel(
            args.peak_xlsx,
            track_name_filter=_excel_track_to_ableton_name,
        )
        peak_follow = True
        n_tracks = len(peak_trajectories)
        n_trajs = sum(len(v) for v in peak_trajectories.values())
        print(
            f"Loaded {n_trajs} peak trajectories across {n_tracks} tracks "
            f"from {args.peak_xlsx.name} — peak-following enabled."
        )

    report = write_dynamic_eq8_from_cde_diagnostics(
        args.als, filtered,
        peak_trajectories_by_track=peak_trajectories,
        peak_follow=peak_follow,
        freq_match_tolerance_semitones=args.tolerance_semitones,
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


def _run_revert(args, diagnostics: List[CorrectionDiagnostic]) -> int:
    """F1e2 revert branch. Extracted from ``main`` to keep the apply
    path readable.

    ``args.revert`` semantics:
        - ``""``               → revert every currently applied diagnostic
        - ``"D1,D2,D3"``       → revert only the listed diagnostic_ids
    """
    ids: Optional[List[str]] = None
    if args.revert:
        ids = [part.strip() for part in args.revert.split(",") if part.strip()]
        if not ids:
            ids = None  # explicit empty = treat as full rollback

    if ids is not None:
        print(f"Revert targets: {', '.join(ids)}")
    else:
        print("Revert targets: all currently-applied diagnostics")

    report = revert_cde_application(
        args.als, diagnostics=diagnostics, diagnostic_ids=ids,
    )

    print()
    print("=== REVERT REPORT ===")
    print(f"Reverted : {len(report.reverted)}")
    if report.reverted:
        preview = ", ".join(report.reverted[:5])
        if len(report.reverted) > 5:
            preview += f", +{len(report.reverted) - 5} more"
        print(f"  IDs: {preview}")
    if report.backup_path:
        print(f"Backup consumed : {report.backup_path}")
    if report.warnings:
        print(f"Warnings : {len(report.warnings)}")
        for w in report.warnings[:5]:
            print(f"  - {w}")

    # Re-dump the JSON so the flipped ``application_status`` /
    # ``rejection_reason`` / cleared ``applied_backup_path`` survive
    # on disk. Skip the rewrite when nothing was actually reverted —
    # a missing backup for example leaves the JSON untouched.
    if report.reverted:
        dump_diagnostics_to_json(diagnostics, args.diagnostics_json)
        print(f"\nUpdated diagnostics JSON: {args.diagnostics_json.name}")
        return 0

    print(
        "\nNothing reverted — diagnostics JSON untouched. "
        "Check warnings above."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
