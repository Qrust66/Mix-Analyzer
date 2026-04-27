"""Declarative cohesion checks across spheres.

A "cohesion rule" is a small predicate that takes a SectionBlueprint and
returns either None (cohesive) or a CohesionViolation (problem detected).
Rules are auto-collected via the @cohesion_rule decorator, so adding a
new rule is just defining a function — no central registry to update.

Rules declare the spheres they need: a rule is silently skipped when any
required sphere is not filled in the blueprint. This makes rules safe to
run on partial blueprints during the director's progressive fill.

Phase 1 ships only the infrastructure. Concrete rules are added alongside
the agent that motivates each one — coupling rules to the sphere agents
that produce the values they constrain. Writing rules in advance leads to
speculative checks based on field shapes the agents may not actually use.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional

from composition_engine.blueprint.schema import SectionBlueprint


@dataclass(frozen=True)
class CohesionViolation:
    """One coherence issue detected in a blueprint."""

    rule: str
    severity: Literal["info", "warn", "block"]
    message: str
    spheres: tuple[str, ...]


@dataclass(frozen=True)
class CohesionReport:
    """The full set of violations for a blueprint."""

    violations: tuple[CohesionViolation, ...] = ()

    @property
    def is_clean(self) -> bool:
        """True if no rule blocked. Warnings are allowed."""
        return not any(v.severity == "block" for v in self.violations)

    @property
    def blockers(self) -> tuple[CohesionViolation, ...]:
        return tuple(v for v in self.violations if v.severity == "block")

    @property
    def warnings(self) -> tuple[CohesionViolation, ...]:
        return tuple(v for v in self.violations if v.severity == "warn")


CohesionFn = Callable[[SectionBlueprint], Optional[CohesionViolation]]
_RULES: list[CohesionFn] = []


def cohesion_rule(spheres: tuple[str, ...]) -> Callable[[CohesionFn], CohesionFn]:
    """Register a cohesion rule that depends on the listed spheres.

    The rule will be auto-skipped when any of `spheres` is not filled in
    the blueprint passed to check_cohesion().

    Usage:

        @cohesion_rule(spheres=("arrangement", "harmony"))
        def density_vs_harmonic_rhythm(bp):
            ...
    """

    def decorator(fn: CohesionFn) -> CohesionFn:
        fn._spheres = spheres  # type: ignore[attr-defined]
        _RULES.append(fn)
        return fn

    return decorator


def check_cohesion(bp: SectionBlueprint) -> CohesionReport:
    """Run every registered rule whose required spheres are filled."""
    violations: list[CohesionViolation] = []
    filled = set(bp.filled_spheres())
    for rule in _RULES:
        required = getattr(rule, "_spheres", ())
        if not all(s in filled for s in required):
            continue
        result = rule(bp)
        if result is not None:
            violations.append(result)
    return CohesionReport(violations=tuple(violations))
