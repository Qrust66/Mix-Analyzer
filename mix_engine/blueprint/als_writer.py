"""als_writer — apply a MixBlueprint to a .als file safely.

Phase 4.19 implementation. Maps each filled lane in a MixBlueprint to its
matching Tier B writer and runs them in MIX_DEPENDENCIES topological
order, mutating the same .als XML tree (or a copy thereof) sequentially.

The writer never decides WHAT to change — that's the agents' job. It
only knows HOW to apply a typed delta to the XML structure, by
delegating to the per-lane Tier B writers in :mod:`mix_engine.writers`.

Single source of truth : :data:`_LANE_WRITERS` is the only mapping from
a lane name to its writer function. Adding a new Tier B writer means
adding ONE entry here ; the Director picks it up automatically.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from mix_engine.blueprint.schema import MixBlueprint
from mix_engine.writers import (
    apply_automation_decision,
    apply_chain_decision,
    apply_dynamics_corrective_decision,
    apply_eq_corrective_decision,
    apply_mastering_decision,
    apply_routing_decision,
    apply_spatial_decision,
)


# ============================================================================
# Lane → writer dispatch — single source of truth
# ============================================================================


# Mapping (lane_name → apply_function). The apply_function signature is
# uniform across every Tier B writer :
#     apply_X(als_path, decision, output_path, dry_run, invoke_safety_guardian)
#         → ReportDataclass with .safety_guardian_status field
#
# Adding a new Tier B writer = one entry here. The Director and the
# topological order helper pick it up automatically.
_LANE_WRITERS: dict[str, Callable[..., Any]] = {
    "routing":             apply_routing_decision,
    "eq_corrective":       apply_eq_corrective_decision,
    "dynamics_corrective": apply_dynamics_corrective_decision,
    "stereo_spatial":      apply_spatial_decision,
    "chain":               apply_chain_decision,
    "automation":          apply_automation_decision,
    "mastering":           apply_mastering_decision,
}


def lanes_with_writer() -> frozenset[str]:
    """Return the set of lane names that have a Tier B writer.

    Derived from :data:`_LANE_WRITERS` so there's no dual-source drift.
    """
    return frozenset(_LANE_WRITERS)


# ============================================================================
# Report dataclass
# ============================================================================


@dataclass(frozen=True)
class AlsWriterReport:
    """Audit trail of one ``apply_blueprint()`` invocation."""

    output_path: str
    """Final .als path (== als_path on overwrite, else the user's output)."""

    execution_order: tuple[str, ...] = ()
    """Lanes actually executed, in topological order."""

    lane_reports: dict[str, Any] = field(default_factory=dict)
    """Per-lane writer report keyed by lane name."""

    skipped_lanes: tuple[tuple[str, str], ...] = ()
    """``(lane, reason)`` pairs for lanes filled in the blueprint but
    silently skipped at write time (e.g. ``diagnostic`` is read-only,
    ``eq_creative`` / ``saturation_color`` have no writer yet)."""

    overall_safety_status: str = "PASS"
    """``PASS`` if every applied lane returned safety_guardian == ``PASS``
    (or ``SKIPPED``). ``FAIL`` if any returned ``FAIL``."""


# ============================================================================
# Public API
# ============================================================================


def apply_blueprint(
    bp: MixBlueprint,
    als_path: str | Path,
    output_path: str | Path | None = None,
    dry_run: bool = False,
    invoke_safety_guardian: bool = True,
) -> AlsWriterReport:
    """Apply every filled lane of ``bp`` to the .als file in topological order.

    Lanes filled in the blueprint but without a Tier B writer (currently
    ``diagnostic`` — read-only — and the future ``eq_creative`` /
    ``saturation_color``) land in :attr:`AlsWriterReport.skipped_lanes`
    with a reason. They never raise.

    Args:
        bp: The MixBlueprint carrying decisions per lane.
        als_path: Source .als file.
        output_path: Destination .als. ``None`` = overwrite source.
        dry_run: Validate without writing the .als.
        invoke_safety_guardian: Forward to each Tier B writer's
            post-write safety check.

    Returns:
        :class:`AlsWriterReport` with per-lane reports + overall status.

    Raises:
        FileNotFoundError: Source .als does not exist.
    """
    # Local import to break the otherwise-circular
    # mix_engine.director ↔ mix_engine.blueprint.als_writer dependency.
    from mix_engine.director.director import topological_order

    als_path = Path(als_path)
    if not als_path.exists():
        raise FileNotFoundError(f"Source .als not found : {als_path}")

    # Resolve writable working path. When output != source, we copy the
    # source first and let every lane mutate the copy in-place ; this
    # keeps each writer's output_path semantics identical whether the
    # user wanted overwrite or a new file.
    if dry_run:
        working_path = als_path
    elif output_path is None or Path(output_path) == als_path:
        working_path = als_path
    else:
        working_path = Path(output_path)
        shutil.copy(als_path, working_path)

    filled = bp.filled_lanes()
    skipped: list[tuple[str, str]] = []
    writable: set[str] = set()
    for lane in filled:
        if lane not in _LANE_WRITERS:
            skipped.append((
                lane,
                f"lane {lane!r} has no Tier B writer "
                f"(read-only diagnostic, or deferred creative agent)",
            ))
            continue
        writable.add(lane)

    execution_order = topological_order(frozenset(writable))

    lane_reports: dict[str, Any] = {}
    any_fail = False
    for lane in execution_order:
        writer = _LANE_WRITERS[lane]
        decision = getattr(bp, lane)
        report = writer(
            working_path, decision,
            output_path=working_path if not dry_run else None,
            dry_run=dry_run,
            invoke_safety_guardian=invoke_safety_guardian,
        )
        lane_reports[lane] = report
        status = getattr(report, "safety_guardian_status", "SKIPPED")
        if status == "FAIL":
            any_fail = True

    return AlsWriterReport(
        output_path=str(working_path),
        execution_order=execution_order,
        lane_reports=lane_reports,
        skipped_lanes=tuple(skipped),
        overall_safety_status="FAIL" if any_fail else "PASS",
    )
