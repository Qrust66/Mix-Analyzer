#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_mix_decisions.py — CLI orchestrator for mix_engine Tier B writers.

Phase 4.13 — applies a batch of Tier A decisions (EQ corrective, dynamics
corrective, stereo/spatial, routing, mastering, chain, automation) to an
Ableton .als file via the corresponding Tier B writers. End-to-end test
drive entry point.

Phase 4.19 — refactored to delegate orchestration to
:class:`mix_engine.director.Director`. The CLI now :

1. Parses each JSON flag into a typed ``MixDecision``.
2. Assembles them into a :class:`mix_engine.blueprint.MixBlueprint`.
3. Hands the blueprint to ``Director.apply_mix()`` which runs cohesion
   checks, then delegates to ``als_writer.apply_blueprint()`` (which
   calls each Tier B writer in MIX_DEPENDENCIES topological order).

Usage :

    python scripts/apply_mix_decisions.py \\
        --als input.als \\
        --eq-json eq_decision.json \\
        --dynamics-json dynamics_decision.json \\
        --spatial-json spatial_decision.json \\
        --chain-json chain_decision.json \\
        --output output.als

Any of the decision flags is optional — if absent, that lane is omitted
from the blueprint.

Each Tier B writer's safety_guardian runs post-write per lane. A
``--no-safety`` flag disables all of them (not recommended).

If cross-lane cohesion checks find block-severity violations, the apply
is halted and a ``COHESION_BLOCKED`` exit (3) is returned. Use
``--force`` to override (not recommended — the violations are real).

Exit codes :
    0 — all writers applied successfully (status PASS or all SKIPPED)
    1 — at least one writer reported safety_guardian = FAIL
    2 — CLI argument or input file error
    3 — cohesion blocked (cross-lane block-severity violation)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Repo-root on sys.path so `import als_utils` resolves regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mix_engine.blueprint import (
    MixBlueprint,
    parse_automation_decision,
    parse_chain_decision,
    parse_dynamics_corrective_decision,
    parse_eq_corrective_decision,
    parse_mastering_decision,
    parse_routing_decision,
    parse_spatial_decision,
)
from mix_engine.director import Director


# CLI flag → (lane_name, parser_fn) mapping.
_FLAG_TO_LANE_PARSER: tuple[tuple[str, str, callable], ...] = (
    ("eq_json",         "eq_corrective",       parse_eq_corrective_decision),
    ("dynamics_json",   "dynamics_corrective", parse_dynamics_corrective_decision),
    ("spatial_json",    "stereo_spatial",      parse_spatial_decision),
    ("routing_json",    "routing",             parse_routing_decision),
    ("mastering_json",  "mastering",           parse_mastering_decision),
    ("chain_json",      "chain",               parse_chain_decision),
    ("automation_json", "automation",          parse_automation_decision),
)


def _load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _print_lane_report(lane: str, report) -> None:
    """Pretty-print one lane's writer report."""
    print()
    print(f"=== {lane} ===")
    print(f"  output: {report.output_path}")
    print(f"  safety: {report.safety_guardian_status}")

    if hasattr(report, "bands_applied"):
        print(f"  bands applied: {len(report.bands_applied)}")
        for b in report.bands_applied:
            print(f"    + {b}")
    if hasattr(report, "corrections_applied"):
        print(f"  corrections applied: {len(report.corrections_applied)}")
        for c in report.corrections_applied:
            print(f"    + {c}")
    if hasattr(report, "moves_applied"):
        print(f"  moves applied: {len(report.moves_applied)}")
        for m in report.moves_applied:
            print(f"    + {m}")
    if hasattr(report, "repairs_applied"):
        print(f"  repairs applied: {len(report.repairs_applied)}")
        for r in report.repairs_applied:
            print(f"    + {r}")
    if hasattr(report, "plans_applied"):
        print(f"  plans applied: {len(report.plans_applied)}")
        for p in report.plans_applied:
            print(f"    + {p} (reordered)")
        if getattr(report, "plans_no_op", ()):
            print(f"  plans no-op: {len(report.plans_no_op)}")
            for p in report.plans_no_op:
                print(f"    = {p} (already in target order)")
        if getattr(report, "devices_reordered", 0):
            print(f"  devices repositioned: {report.devices_reordered}")
        if getattr(report, "slots_unmatched", ()):
            print(f"  slots unmatched: {len(report.slots_unmatched)}")
            for sid, reason in report.slots_unmatched:
                print(f"    - {sid} : {reason}")
    if hasattr(report, "envelopes_applied") and hasattr(report, "band_tracks_applied"):
        print(f"  envelopes applied: {len(report.envelopes_applied)}")
        for e in report.envelopes_applied[:8]:
            print(f"    + {e}")
        if len(report.envelopes_applied) > 8:
            print(f"    + ... ({len(report.envelopes_applied) - 8} more)")
        if getattr(report, "band_tracks_applied", ()):
            print(f"  band_tracks applied: {len(report.band_tracks_applied)}")
            for bt in report.band_tracks_applied:
                print(f"    + {bt}")
        if getattr(report, "breakpoints_written", 0):
            print(f"  breakpoints written: {report.breakpoints_written}")
        if getattr(report, "notch_coercions", 0):
            print(f"  notch→bell coercions: {report.notch_coercions}")
        if getattr(report, "band_tracks_skipped", ()):
            print(f"  band_tracks skipped: {len(report.band_tracks_skipped)}")
            for bt_id, reason in report.band_tracks_skipped:
                print(f"    - {bt_id} : {reason}")

    skipped = (
        getattr(report, "bands_skipped", None)
        or getattr(report, "corrections_skipped", None)
        or getattr(report, "moves_skipped", None)
        or getattr(report, "repairs_skipped", None)
        or getattr(report, "plans_skipped", None)
        or getattr(report, "envelopes_skipped", None)
        or ()
    )
    if skipped:
        print(f"  skipped: {len(skipped)}")
        for s_id, reason in skipped:
            print(f"    - {s_id} : {reason}")

    if report.warnings:
        print(f"  warnings: {len(report.warnings)}")
        for w in report.warnings[:10]:
            print(f"    ! {w}")
        if len(report.warnings) > 10:
            print(f"    ! ... ({len(report.warnings) - 10} more warnings)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply Tier A mix decisions to an .als via Tier B writers."
    )
    parser.add_argument("--als", required=True, type=Path,
                        help="Source .als file.")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output .als path (default: overwrite source).")
    parser.add_argument("--eq-json", type=Path, default=None,
                        help="EQ corrective decision JSON.")
    parser.add_argument("--dynamics-json", type=Path, default=None,
                        help="Dynamics corrective decision JSON.")
    parser.add_argument("--spatial-json", type=Path, default=None,
                        help="Spatial / stereo decision JSON.")
    parser.add_argument("--routing-json", type=Path, default=None,
                        help="Routing / sidechain repair decision JSON.")
    parser.add_argument("--mastering-json", type=Path, default=None,
                        help="Mastering decision JSON (master bus + sub-bus glue).")
    parser.add_argument("--chain-json", type=Path, default=None,
                        help="Chain-build decision JSON (per-track absolute device ordering).")
    parser.add_argument("--automation-json", type=Path, default=None,
                        help="Automation decision JSON (envelopes + band_tracks).")
    parser.add_argument("--no-safety", action="store_true",
                        help="Disable post-write safety_guardian (not recommended).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate without writing the .als.")
    parser.add_argument("--force", action="store_true",
                        help="Apply even if cohesion check has block-severity "
                             "violations (not recommended).")
    args = parser.parse_args(argv)

    if not args.als.exists():
        print(f"ERROR: --als path not found: {args.als}", file=sys.stderr)
        return 2

    # Build MixBlueprint from supplied JSON flags, lane by lane.
    bp = MixBlueprint(name=args.als.stem)
    any_decision = False
    for flag, lane, parse_fn in _FLAG_TO_LANE_PARSER:
        json_path: Path | None = getattr(args, flag)
        if json_path is None:
            continue
        if not json_path.exists():
            print(f"ERROR: decision JSON not found: {json_path}", file=sys.stderr)
            return 2
        try:
            decision = parse_fn(_load_json(json_path))
        except Exception as exc:
            print(
                f"ERROR: failed to parse {json_path} as {lane} decision : "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 2
        bp = bp.with_decision(lane, decision)
        any_decision = True

    if not any_decision:
        print(
            "ERROR: at least one of --eq-json / --dynamics-json / "
            "--spatial-json / --routing-json / --mastering-json / "
            "--chain-json / --automation-json must be provided.",
            file=sys.stderr,
        )
        return 2

    print(f"Source .als : {args.als}")
    print(f"Output .als : {args.output if args.output else args.als}")
    print(f"Dry-run : {args.dry_run}")
    print(f"Safety guardian : "
          f"{'DISABLED' if args.no_safety else 'enabled per-writer'}")
    print(f"Filled lanes : {', '.join(bp.filled_lanes())}")

    director = Director()
    result = director.apply_mix(
        bp=bp,
        als_path=args.als,
        output_path=args.output,
        dry_run=args.dry_run,
        invoke_safety_guardian=not args.no_safety,
        force=args.force,
    )

    print()
    print(f"Cohesion : {len(result.cohesion.violations)} violation(s) "
          f"({len(result.cohesion.blockers)} block, "
          f"{len(result.cohesion.warnings)} warn)")
    for v in result.cohesion.violations:
        print(f"  [{v.severity}] {v.rule} ({', '.join(v.lanes)}) : {v.message}")

    if result.overall_status == "COHESION_BLOCKED":
        print()
        print("=== RESULT : COHESION_BLOCKED — cohesion check has "
              "block-severity violations, no .als written. ===")
        print("Pass --force to override (the violations are real).")
        return 3

    apply_report = result.apply_report
    assert apply_report is not None  # cleared by the COHESION_BLOCKED branch
    print()
    print(f"Execution order : {' → '.join(apply_report.execution_order)}")
    if apply_report.skipped_lanes:
        print(f"Skipped lanes : {len(apply_report.skipped_lanes)}")
        for lane, reason in apply_report.skipped_lanes:
            print(f"  - {lane} : {reason}")

    for lane in apply_report.execution_order:
        _print_lane_report(lane, apply_report.lane_reports[lane])

    print()
    if not result.ok:
        print("=== RESULT : FAIL "
              "(at least one writer reported safety_guardian=FAIL) ===")
        return 1

    print("=== RESULT : OK ===")
    print(f"Modified .als ready: {apply_report.output_path}")
    print("Open in Ableton Live to verify.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
