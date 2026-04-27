"""Declarative cohesion checks across spheres.

A "cohesion rule" is a small predicate that takes a SectionBlueprint and
returns either None (cohesive) or a CohesionViolation (problem detected).
Rules are auto-collected via the @cohesion_rule decorator, so adding a
new rule is just defining a function — no central registry to update.

Rules declare the spheres they need: a rule is silently skipped when any
required sphere is not filled in the blueprint. This makes rules safe to
run on partial blueprints during the director's progressive fill.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional

from composition_engine.blueprint.schema import SectionBlueprint

# ============================================================================
# Violation reporting
# ============================================================================


@dataclass(frozen=True)
class CohesionViolation:
    """One coherence issue detected in a blueprint."""

    rule: str  # the rule's function name
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


# ============================================================================
# Rule registry (decorator-based)
# ============================================================================


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
        # Stash the spheres on the function for the runner to read
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


# ============================================================================
# Initial rule set
# ============================================================================
# These illustrate the pattern. More rules will be added as we encode each
# sphere's domain knowledge. Rules are intentionally conservative at this
# stage — the goal is to catch "obvious incoherence", not to second-guess
# every creative choice.


@cohesion_rule(spheres=("arrangement", "harmony"))
def density_vs_harmonic_rhythm(bp: SectionBlueprint) -> Optional[CohesionViolation]:
    """Sparse arrangement + dense harmonic rhythm = audibly conflicted."""
    assert bp.arrangement is not None and bp.harmony is not None
    if (
        bp.arrangement.value.density_curve == "sparse"
        and bp.harmony.value.harmonic_rhythm > 1.0
    ):
        return CohesionViolation(
            rule="density_vs_harmonic_rhythm",
            severity="warn",
            message=(
                f"Sparse density with harmonic rhythm of "
                f"{bp.harmony.value.harmonic_rhythm} chords/bar tends to feel "
                f"harmonically dense despite sparse instrumentation. Consider "
                f"<= 0.5 chords/bar for genuine sparseness."
            ),
            spheres=("arrangement", "harmony"),
        )
    return None


@cohesion_rule(spheres=("dynamics", "structure"))
def dynamic_arc_within_section_bounds(
    bp: SectionBlueprint,
) -> Optional[CohesionViolation]:
    """Dynamic peak_bar and inflection points must be inside [0, total_bars)."""
    assert bp.dynamics is not None and bp.structure is not None
    total = bp.structure.value.total_bars
    dyn = bp.dynamics.value
    if dyn.peak_bar is not None and not (0 <= dyn.peak_bar < total):
        return CohesionViolation(
            rule="dynamic_arc_within_section_bounds",
            severity="block",
            message=(
                f"Dynamic peak_bar={dyn.peak_bar} is outside section "
                f"[0, {total}). Cannot be composed."
            ),
            spheres=("dynamics", "structure"),
        )
    for bar, _db in dyn.inflection_points:
        if not (0 <= bar < total):
            return CohesionViolation(
                rule="dynamic_arc_within_section_bounds",
                severity="block",
                message=(
                    f"Dynamic inflection point at bar={bar} is outside "
                    f"section [0, {total})."
                ),
                spheres=("dynamics", "structure"),
            )
    return None


@cohesion_rule(spheres=("arrangement", "structure"))
def layers_within_section_bounds(
    bp: SectionBlueprint,
) -> Optional[CohesionViolation]:
    """Every layer must enter and exit within the section's bar range."""
    assert bp.arrangement is not None and bp.structure is not None
    total = bp.structure.value.total_bars
    for layer in bp.arrangement.value.layers:
        if not (0 <= layer.enters_at_bar < total):
            return CohesionViolation(
                rule="layers_within_section_bounds",
                severity="block",
                message=(
                    f"Layer {layer.role!r} enters at bar {layer.enters_at_bar}, "
                    f"outside [0, {total})."
                ),
                spheres=("arrangement", "structure"),
            )
        if not (0 < layer.exits_at_bar <= total):
            return CohesionViolation(
                rule="layers_within_section_bounds",
                severity="block",
                message=(
                    f"Layer {layer.role!r} exits at bar {layer.exits_at_bar}, "
                    f"outside (0, {total}]."
                ),
                spheres=("arrangement", "structure"),
            )
        if layer.enters_at_bar >= layer.exits_at_bar:
            return CohesionViolation(
                rule="layers_within_section_bounds",
                severity="block",
                message=(
                    f"Layer {layer.role!r} enters at "
                    f"{layer.enters_at_bar} but exits at {layer.exits_at_bar} — "
                    f"empty or negative-duration layer."
                ),
                spheres=("arrangement", "structure"),
            )
    return None


@cohesion_rule(spheres=("rhythm", "performance"))
def swing_consistency(bp: SectionBlueprint) -> Optional[CohesionViolation]:
    """If both rhythm and performance specify swing, they should agree."""
    assert bp.rhythm is not None and bp.performance is not None
    rhythm_swing = bp.rhythm.value.swing
    perf_swing = bp.performance.value.swing if hasattr(bp.performance.value, "swing") else None
    # PerformanceDecision doesn't currently have a swing field — this rule
    # exists as a template for when/if we add one. For now it's inert.
    _ = rhythm_swing, perf_swing
    return None


@cohesion_rule(spheres=("structure",))
def sub_sections_within_total(bp: SectionBlueprint) -> Optional[CohesionViolation]:
    """All declared sub-sections must lie within the total bar count."""
    assert bp.structure is not None
    total = bp.structure.value.total_bars
    for ss in bp.structure.value.sub_sections:
        if not (0 <= ss.start_bar < total):
            return CohesionViolation(
                rule="sub_sections_within_total",
                severity="block",
                message=(
                    f"Sub-section {ss.name!r} starts at {ss.start_bar}, "
                    f"outside [0, {total})."
                ),
                spheres=("structure",),
            )
        if not (0 < ss.end_bar <= total):
            return CohesionViolation(
                rule="sub_sections_within_total",
                severity="block",
                message=(
                    f"Sub-section {ss.name!r} ends at {ss.end_bar}, "
                    f"outside (0, {total}]."
                ),
                spheres=("structure",),
            )
        if ss.start_bar >= ss.end_bar:
            return CohesionViolation(
                rule="sub_sections_within_total",
                severity="block",
                message=(
                    f"Sub-section {ss.name!r}: start={ss.start_bar} >= "
                    f"end={ss.end_bar}."
                ),
                spheres=("structure",),
            )
    return None
