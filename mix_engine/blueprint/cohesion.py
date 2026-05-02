"""Mix-side cohesion checks — declarative cross-lane rules.

Mirrors composition_engine.blueprint.cohesion. A "mix cohesion rule" is a
predicate that takes a MixBlueprint and returns either None (cohesive)
or a MixCohesionViolation. Rules are auto-collected via the
@mix_cohesion_rule decorator and silently skipped when their required
lanes aren't filled — safe to run on partial blueprints.

Phase 4.19 ships the infrastructure ; Phase 4.19.1 ships the first
concrete rule (`sidechain_target_exists_in_routing`). Subsequent rules
land alongside the agent that motivates each one (rule-with-consumer
principle) — speculative rules drift away from real schema fields.

Future rules expected (not yet implemented — listed in
docs/MIX_ENGINE_ARCHITECTURE.md §7) :

| Rule                                              | Severity | Lanes |
|---------------------------------------------------|----------|-------|
| eq_cuts_dont_create_phase_holes_with_neighbours   | warn     | eq_corrective × eq_corrective (cross-track) |
| master_ceiling_below_minus_03_dbtp                | block    | mastering |
| automation_envelope_targets_active_param          | block    | automation × any device |
| chain_order_respects_signal_flow                  | warn     | chain × all devices |
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional

from mix_engine.blueprint.schema import MixBlueprint


@dataclass(frozen=True)
class MixCohesionViolation:
    """One coherence issue detected in a MixBlueprint."""

    rule: str
    severity: Literal["info", "warn", "block"]
    message: str
    lanes: tuple[str, ...]


@dataclass(frozen=True)
class MixCohesionReport:
    """The full set of violations for a MixBlueprint."""

    violations: tuple[MixCohesionViolation, ...] = ()

    @property
    def is_clean(self) -> bool:
        """True if no rule blocked. Warnings + infos are allowed."""
        return not any(v.severity == "block" for v in self.violations)

    @property
    def blockers(self) -> tuple[MixCohesionViolation, ...]:
        return tuple(v for v in self.violations if v.severity == "block")

    @property
    def warnings(self) -> tuple[MixCohesionViolation, ...]:
        return tuple(v for v in self.violations if v.severity == "warn")


MixCohesionFn = Callable[[MixBlueprint], Optional[MixCohesionViolation]]
_RULES: list[MixCohesionFn] = []


def mix_cohesion_rule(
    lanes: tuple[str, ...],
) -> Callable[[MixCohesionFn], MixCohesionFn]:
    """Register a cohesion rule that depends on the listed mix lanes.

    The rule will be auto-skipped when any of ``lanes`` is not filled in
    the MixBlueprint passed to :func:`check_mix_cohesion`.

    Usage::

        @mix_cohesion_rule(lanes=("dynamics_corrective", "routing"))
        def sidechain_target_exists(bp):
            ...
    """

    def decorator(fn: MixCohesionFn) -> MixCohesionFn:
        fn._lanes = lanes  # type: ignore[attr-defined]
        _RULES.append(fn)
        return fn

    return decorator


def check_mix_cohesion(bp: MixBlueprint) -> MixCohesionReport:
    """Run every registered rule whose required lanes are filled."""
    violations: list[MixCohesionViolation] = []
    filled = set(bp.filled_lanes())
    for rule in _RULES:
        required = getattr(rule, "_lanes", ())
        if not all(lane in filled for lane in required):
            continue
        result = rule(bp)
        if result is not None:
            violations.append(result)
    return MixCohesionReport(violations=tuple(violations))


# ============================================================================
# Concrete rules (Phase 4.19.1+)
# ============================================================================
#
# Each rule lands together with the agent whose output it constrains, per
# the project's "rule-with-consumer" principle.


@mix_cohesion_rule(lanes=("dynamics_corrective", "routing"))
def sidechain_target_exists_in_routing(
    bp: MixBlueprint,
) -> Optional[MixCohesionViolation]:
    """Block when ``dynamics_corrective`` references an external sidechain
    trigger that ``routing`` is removing in the same blueprint.

    Failure mode caught :
        dynamics-corrective-decider says "duck Bass when Kick triggers"
        (DynamicsCorrection.sidechain.mode == "external",
         .trigger_track == "Kick")
        AND
        routing-and-sidechain-architect says "remove the sidechain on
        Bass" (SidechainRepair.fix_type == "sidechain_remove",
         .current_trigger == "Kick", .track == "Bass" or any).

    Both can be individually valid, but together they leave Tier B in
    contradiction — dynamics writer would configure a Compressor2
    sidechain pointing at Kick, routing writer would unwire it. Result :
    a half-configured sidechain block with no input, silent in Ableton.

    Other failure modes (sidechain_redirect targeting the same trigger
    name, internal-mode sidechains, etc.) are out of scope for v1 — the
    redirect case is ambiguous (the dynamics decision may already
    operate on the post-redirect state) and would warn at most.
    """
    dynamics = bp.dynamics_corrective
    routing = bp.routing
    assert dynamics is not None and routing is not None  # decorator-guaranteed

    removed_triggers: set[str] = {
        repair.current_trigger
        for repair in routing.value.repairs
        if repair.fix_type == "sidechain_remove"
        and repair.current_trigger is not None
    }
    if not removed_triggers:
        return None

    for correction in dynamics.value.corrections:
        sc = correction.sidechain
        if sc is None or sc.mode != "external" or sc.trigger_track is None:
            continue
        if sc.trigger_track in removed_triggers:
            return MixCohesionViolation(
                rule="sidechain_target_exists_in_routing",
                severity="block",
                message=(
                    f"DynamicsCorrection on track {correction.track!r} uses "
                    f"external sidechain triggered by {sc.trigger_track!r}, "
                    f"but routing.repairs contains a sidechain_remove on "
                    f"trigger {sc.trigger_track!r}. Tier B would write a "
                    f"Compressor2 sidechain block with no live input. "
                    f"Either drop the dynamics correction OR drop the "
                    f"routing remove."
                ),
                lanes=("dynamics_corrective", "routing"),
            )
    return None
