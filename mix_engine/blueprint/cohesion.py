"""Mix-side cohesion checks — declarative cross-lane rules.

Mirrors composition_engine.blueprint.cohesion. A "mix cohesion rule" is a
predicate that takes a MixBlueprint and returns either None (cohesive)
or a MixCohesionViolation. Rules are auto-collected via the
@mix_cohesion_rule decorator and silently skipped when their required
lanes aren't filled — safe to run on partial blueprints.

Phase 4.19 ships ONLY the infrastructure. Concrete rules land alongside
the agent that motivates each one (rule-with-consumer principle).
Writing rules in advance leads to speculative checks based on field
shapes the agents may not actually use.

Future rules expected (none implemented yet — listed in
docs/MIX_ENGINE_ARCHITECTURE.md §7) :

| Rule                                              | Severity | Lanes |
|---------------------------------------------------|----------|-------|
| eq_cuts_dont_create_phase_holes_with_neighbours   | warn     | eq_corrective × eq_corrective (cross-track) |
| sidechain_target_exists_in_routing                | block    | dynamics_corrective × routing |
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
