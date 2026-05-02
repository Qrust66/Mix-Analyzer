#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_mix_decisions.py — CLI orchestrator for mix_engine Tier B writers.

Phase 4.13 — applies a batch of Tier A decisions (EQ corrective, dynamics
corrective, stereo/spatial) to an Ableton .als file via the corresponding
Tier B writers. End-to-end test drive entry point.

Workflow :

    Tier A subagents (eq-corrective-decider, dynamics-corrective-decider,
    stereo-and-spatial-engineer) produce JSON decisions
                              ↓
    User saves each decision to a .json file
                              ↓
    This CLI reads them, applies via Tier B writers in canonical order :
        1. EQ corrective → eq8-configurator
        2. Dynamics corrective → dynamics-configurator (Phase 4.11 v1 = GlueComp + Limiter)
        3. Stereo/spatial → spatial-configurator
        4. Routing → routing-configurator
        5. Mastering → master-bus-configurator
        6. Chain assembly → chain-assembler (absolute per-track ordering — last)
                              ↓
    Modified .als + aggregated report (PASS/FAIL + skipped + warnings)

Usage :

    python scripts/apply_mix_decisions.py \\
        --als input.als \\
        --eq-json eq_decision.json \\
        --dynamics-json dynamics_decision.json \\
        --spatial-json spatial_decision.json \\
        --chain-json chain_decision.json \\
        --output output.als

Any of the decision flags is optional — if absent, that lane is skipped
in the orchestration. So you can apply only EQ moves, or only spatial
moves, etc.

Each Tier B writer's safety_guardian runs post-write per lane. A
``--no-safety`` flag disables all of them (not recommended).

Exit codes :
    0 — all writers applied successfully (status PASS or all SKIPPED)
    1 — at least one writer reported safety_guardian = FAIL
    2 — CLI argument or input file error
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# Repo-root on sys.path so `import als_utils` resolves regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import als_utils
from mix_engine.blueprint import (
    parse_chain_decision,
    parse_dynamics_corrective_decision,
    parse_eq_corrective_decision,
    parse_mastering_decision,
    parse_routing_decision,
    parse_spatial_decision,
)
from mix_engine.writers import (
    apply_chain_decision,
    apply_dynamics_corrective_decision,
    apply_eq_corrective_decision,
    apply_mastering_decision,
    apply_routing_decision,
    apply_spatial_decision,
)


def _load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _print_report(lane: str, report) -> bool:
    """Print one lane's report. Returns True if status is FAIL."""
    print()
    print(f"=== {lane} ===")
    print(f"  output: {report.output_path}")
    print(f"  safety: {report.safety_guardian_status}")

    # Universal fields
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

    # Skipped
    skipped = (
        getattr(report, "bands_skipped", None)
        or getattr(report, "corrections_skipped", None)
        or getattr(report, "moves_skipped", None)
        or getattr(report, "repairs_skipped", None)
        or getattr(report, "plans_skipped", None)
        or ()
    )
    if skipped:
        print(f"  skipped: {len(skipped)}")
        for s_id, reason in skipped:
            print(f"    - {s_id} : {reason}")

    if report.warnings:
        print(f"  warnings: {len(report.warnings)}")
        for w in report.warnings[:10]:  # cap to first 10
            print(f"    ! {w}")
        if len(report.warnings) > 10:
            print(f"    ! ... ({len(report.warnings) - 10} more warnings)")

    return report.safety_guardian_status == "FAIL"


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
    parser.add_argument("--no-safety", action="store_true",
                        help="Disable post-write safety_guardian (not recommended).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate without writing the .als.")
    args = parser.parse_args(argv)

    # Validate inputs
    if not args.als.exists():
        print(f"ERROR: --als path not found: {args.als}", file=sys.stderr)
        return 2

    if (args.eq_json is None and args.dynamics_json is None
            and args.spatial_json is None and args.routing_json is None
            and args.mastering_json is None and args.chain_json is None):
        print("ERROR: at least one of --eq-json / --dynamics-json / "
                "--spatial-json / --routing-json / --mastering-json / "
                "--chain-json must be provided.", file=sys.stderr)
        return 2

    for json_path in (args.eq_json, args.dynamics_json, args.spatial_json,
                       args.routing_json, args.mastering_json, args.chain_json):
        if json_path is not None and not json_path.exists():
            print(f"ERROR: decision JSON not found: {json_path}", file=sys.stderr)
            return 2

    output_path = args.output if args.output else args.als
    invoke_safety = not args.no_safety

    # If output != source, copy source first so each writer mutates in place.
    # If output == source, writers overwrite naturally.
    if not args.dry_run and args.output is not None and args.output != args.als:
        shutil.copy(args.als, args.output)
        working_path = args.output
    else:
        working_path = args.als

    print(f"Source .als : {args.als}")
    print(f"Output .als : {working_path}")
    print(f"Dry-run : {args.dry_run}")
    print(f"Safety guardian : {'DISABLED' if not invoke_safety else 'enabled per-writer'}")

    any_fail = False

    # 1. EQ corrective
    if args.eq_json is not None:
        payload = _load_json(args.eq_json)
        decision = parse_eq_corrective_decision(payload)
        report = apply_eq_corrective_decision(
            working_path, decision,
            output_path=working_path if not args.dry_run else None,
            dry_run=args.dry_run,
            invoke_safety_guardian=invoke_safety,
        )
        any_fail = _print_report("EQ corrective", report) or any_fail

    # 2. Dynamics corrective
    if args.dynamics_json is not None:
        payload = _load_json(args.dynamics_json)
        decision = parse_dynamics_corrective_decision(payload)
        report = apply_dynamics_corrective_decision(
            working_path, decision,
            output_path=working_path if not args.dry_run else None,
            dry_run=args.dry_run,
            invoke_safety_guardian=invoke_safety,
        )
        any_fail = _print_report("Dynamics corrective", report) or any_fail

    # 3. Stereo / spatial
    if args.spatial_json is not None:
        payload = _load_json(args.spatial_json)
        decision = parse_spatial_decision(payload)
        report = apply_spatial_decision(
            working_path, decision,
            output_path=working_path if not args.dry_run else None,
            dry_run=args.dry_run,
            invoke_safety_guardian=invoke_safety,
        )
        any_fail = _print_report("Spatial", report) or any_fail

    # 4. Routing / sidechain repairs
    if args.routing_json is not None:
        payload = _load_json(args.routing_json)
        decision = parse_routing_decision(payload)
        report = apply_routing_decision(
            working_path, decision,
            output_path=working_path if not args.dry_run else None,
            dry_run=args.dry_run,
            invoke_safety_guardian=invoke_safety,
        )
        any_fail = _print_report("Routing", report) or any_fail

    # 5. Mastering (master bus + sub-bus glue)
    if args.mastering_json is not None:
        payload = _load_json(args.mastering_json)
        decision = parse_mastering_decision(payload)
        report = apply_mastering_decision(
            working_path, decision,
            output_path=working_path if not args.dry_run else None,
            dry_run=args.dry_run,
            invoke_safety_guardian=invoke_safety,
        )
        any_fail = _print_report("Mastering", report) or any_fail

    # 6. Chain assembly (absolute per-track device ordering — runs last so
    #    it sees devices created/configured by all earlier writers).
    if args.chain_json is not None:
        payload = _load_json(args.chain_json)
        decision = parse_chain_decision(payload)
        report = apply_chain_decision(
            working_path, decision,
            output_path=working_path if not args.dry_run else None,
            dry_run=args.dry_run,
            invoke_safety_guardian=invoke_safety,
        )
        any_fail = _print_report("Chain assembly", report) or any_fail

    print()
    if any_fail:
        print("=== RESULT : FAIL (at least one writer reported safety_guardian=FAIL) ===")
        return 1

    print("=== RESULT : OK ===")
    print(f"Modified .als ready: {working_path}")
    print("Open in Ableton Live to verify.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
