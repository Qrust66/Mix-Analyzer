"""mix_engine.director — sequences mix agents according to MIX_DEPENDENCIES.

Phase 4.19 ships GHOST mode : the Director accepts a pre-filled
:class:`MixBlueprint`, runs cross-lane cohesion checks, then delegates
the actual XML mutation to :func:`mix_engine.blueprint.als_writer.apply_blueprint`
which calls each Tier B writer in topological order.

Architectural separation (mirror of composition_engine) :
- **Director** — orchestrator. Decides what to run (cohesion gate, then
  apply) and when (topological order via :func:`topological_order`).
- **als_writer** — applicator. Takes a validated MixBlueprint and turns
  it into XML patches by delegating to per-lane Tier B writers.
- **cohesion** — cross-lane validator. Block-severity violations halt
  the apply unless ``force=True`` is passed.

Future modes (LIVE — Director invokes Tier A LLM subagents itself ;
INTERACTIVE — user validates each lane) require a Claude-Code-side
.claude/agents/mix-director.md agent and are out of scope for the
Python module.

The DAG below is the canonical ordering. Lanes on the same level can
in principle run in parallel (decisional independence) ; for the WRITE
phase we serialise them since they all mutate the same .als XML tree.

Rationale per edge :
- everything depends on diagnostic (you don't move blind)
- routing runs second because broken refs (No Output / No Input)
  poison everything downstream
- corrective lanes (dynamics/eq/stereo) are decisionally parallelisable
- creative color (eq_creative, saturation) waits for corrective so you
  don't decorate a still-broken signal
- chain composes the per-device decisions into a track chain order
- automation writes envelopes onto already-decided params (post-chain
  so envelopes target the final device positions)
- mastering is last-mile, master bus only
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mix_engine.blueprint import (
    AlsWriterReport,
    MIX_LANES,
    MixBlueprint,
    MixCohesionReport,
    apply_blueprint,
    check_mix_cohesion,
)


# ============================================================================
# DAG declaration
# ============================================================================

# Mix lane DAG. Each key is a lane ; its value is the tuple of lanes
# that must be filled before this lane's agent can run.
MIX_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "diagnostic":          (),
    "routing":             ("diagnostic",),
    "dynamics_corrective": ("diagnostic", "routing"),
    "eq_corrective":       ("diagnostic", "routing"),
    "stereo_spatial":      ("diagnostic", "routing"),
    "eq_creative":         ("eq_corrective",),
    "saturation_color":    ("eq_corrective", "dynamics_corrective"),
    "chain":               ("eq_corrective", "eq_creative",
                            "dynamics_corrective", "saturation_color",
                            "stereo_spatial", "routing"),
    "automation":          ("chain",),
    "mastering":           ("automation",),
}

assert set(MIX_DEPENDENCIES) == set(MIX_LANES), (
    "MIX_DEPENDENCIES is out of sync with the MIX_LANES tuple"
)


def topological_order(lanes: frozenset[str] | set[str]) -> tuple[str, ...]:
    """Return a valid execution order for the given subset of lanes.

    Pure topological sort over MIX_DEPENDENCIES restricted to ``lanes``.
    Deterministic — stable order matches the MIX_LANES tuple ordering.

    Lanes not in the subset are not blockers (their deps are ignored),
    so callers can request a partial subset (e.g. only the writer lanes).

    Raises:
        ValueError: If ``lanes`` contains a name not in MIX_DEPENDENCIES,
            or if MIX_DEPENDENCIES contains a cycle restricted to ``lanes``.
    """
    unknown = set(lanes) - set(MIX_DEPENDENCIES)
    if unknown:
        raise ValueError(
            f"Unknown lane(s) {sorted(unknown)} ; expected subset of "
            f"{sorted(MIX_DEPENDENCIES)}"
        )
    remaining = set(lanes)
    done: list[str] = []
    while remaining:
        ready = [
            lane
            for lane in MIX_LANES
            if lane in remaining
            and all(
                dep in done or dep not in lanes
                for dep in MIX_DEPENDENCIES[lane]
            )
        ]
        if not ready:
            raise ValueError(
                f"Cycle in MIX_DEPENDENCIES restricted to {sorted(lanes)} ; "
                f"already done : {done}"
            )
        done.append(ready[0])
        remaining.discard(ready[0])
    return tuple(done)


# ============================================================================
# Result dataclass
# ============================================================================


@dataclass(frozen=True)
class MixResult:
    """Aggregated outcome of one ``Director.apply_mix()`` call."""

    overall_status: str
    """One of :
    - ``PASS`` : cohesion clean, every applied lane safety_guardian == PASS
    - ``COHESION_BLOCKED`` : cohesion has block-severity violations,
      no .als write attempted (call again with ``force=True`` to override)
    - ``FAIL`` : cohesion clean (or forced), but at least one lane's
      Tier B writer reported safety_guardian == FAIL
    """

    cohesion: MixCohesionReport
    """Cross-lane cohesion report. Always populated, even on PASS."""

    apply_report: Optional[AlsWriterReport] = None
    """Per-lane writer reports + execution order + final output path.
    ``None`` only when ``overall_status == COHESION_BLOCKED`` and no
    write was attempted."""

    @property
    def ok(self) -> bool:
        return self.overall_status == "PASS"

    @property
    def output_path(self) -> Optional[str]:
        """Convenience accessor — None when no write was attempted."""
        return self.apply_report.output_path if self.apply_report else None


# ============================================================================
# Director
# ============================================================================


class Director:
    """Orchestrate cohesion check + Tier B writer execution over a MixBlueprint.

    Phase 4.19 ships GHOST mode only : the caller produces a fully-filled
    :class:`MixBlueprint` (typically by hand-running the Tier A subagents
    or via a future LIVE-mode Claude-Code agent) and hands it to
    :meth:`Director.apply_mix`. The Director :

    1. Runs :func:`check_mix_cohesion` on the blueprint.
    2. If any block-severity violation is present and ``force=False``,
       returns a ``COHESION_BLOCKED`` MixResult without writing the .als.
    3. Otherwise delegates to :func:`apply_blueprint` which iterates the
       filled lanes in topological order, calling the matching Tier B
       writer for each.
    """

    def apply_mix(
        self,
        bp: MixBlueprint,
        als_path: str | Path,
        output_path: str | Path | None = None,
        dry_run: bool = False,
        invoke_safety_guardian: bool = True,
        force: bool = False,
    ) -> MixResult:
        """Apply ``bp`` to the .als file via the cohesion → apply pipeline.

        Args:
            bp: The :class:`MixBlueprint` carrying decisions per lane.
            als_path: Source .als file.
            output_path: Destination .als. ``None`` = overwrite source.
            dry_run: Validate without writing the .als.
            invoke_safety_guardian: Forward to each Tier B writer's
                post-write safety check.
            force: If True, apply even when cohesion has block-severity
                violations. The cohesion report is still populated and
                surfaced ; the user opted in to the risk.

        Returns:
            :class:`MixResult` with cohesion + apply reports.

        Raises:
            FileNotFoundError: Source .als does not exist (only when an
                apply is attempted).
        """
        cohesion = check_mix_cohesion(bp)

        if not cohesion.is_clean and not force:
            return MixResult(
                overall_status="COHESION_BLOCKED",
                cohesion=cohesion,
                apply_report=None,
            )

        apply_report = apply_blueprint(
            bp, als_path,
            output_path=output_path,
            dry_run=dry_run,
            invoke_safety_guardian=invoke_safety_guardian,
        )
        overall = (
            "FAIL" if apply_report.overall_safety_status == "FAIL"
            else "PASS"
        )
        return MixResult(
            overall_status=overall,
            cohesion=cohesion,
            apply_report=apply_report,
        )
