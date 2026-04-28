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


# ============================================================================
# Concrete rules (added Phase 2.5.1)
# ============================================================================
#
# Each rule lands together with the agent whose output it constrains, per
# the project's "rule-with-consumer" principle. Phase 1 cleanup removed all
# speculative rules; these are the first concrete rules — motivated by
# real failure modes observed when arrangement-decider can produce layers
# that overflow the structure-decider's section bounds.


@cohesion_rule(spheres=("structure", "arrangement"))
def arrangement_layers_within_structure_bounds(
    bp: SectionBlueprint,
) -> Optional[CohesionViolation]:
    """Every arrangement.layers[*] must fit inside structure.total_bars.

    Background: a layer with exits_at_bar > total_bars produces MIDI events
    beyond the section's nominal end. The composer's track_layerer happily
    extends the rendering, but the rest of the pipeline (multi-section
    composition, .als injection) assumes layers are bounded.
    """
    structure = bp.structure
    arrangement = bp.arrangement
    assert structure is not None and arrangement is not None
    total_bars = structure.value.total_bars

    for i, layer in enumerate(arrangement.value.layers):
        if layer.enters_at_bar < 0:
            return CohesionViolation(
                rule="arrangement_layers_within_structure_bounds",
                severity="block",
                message=(
                    f"Layer #{i} ({layer.role!r}, {layer.instrument!r}): "
                    f"enters_at_bar={layer.enters_at_bar} is negative."
                ),
                spheres=("structure", "arrangement"),
            )
        if layer.exits_at_bar > total_bars:
            return CohesionViolation(
                rule="arrangement_layers_within_structure_bounds",
                severity="block",
                message=(
                    f"Layer #{i} ({layer.role!r}, {layer.instrument!r}): "
                    f"exits_at_bar={layer.exits_at_bar} but "
                    f"structure.total_bars={total_bars}. Layer would "
                    f"extend past the section. Either trim the layer or "
                    f"increase total_bars."
                ),
                spheres=("structure", "arrangement"),
            )
        if layer.enters_at_bar >= total_bars:
            return CohesionViolation(
                rule="arrangement_layers_within_structure_bounds",
                severity="block",
                message=(
                    f"Layer #{i} ({layer.role!r}, {layer.instrument!r}): "
                    f"enters_at_bar={layer.enters_at_bar} is not strictly "
                    f"less than total_bars={total_bars} — layer would "
                    f"never become active."
                ),
                spheres=("structure", "arrangement"),
            )
    return None


@cohesion_rule(spheres=("structure", "arrangement"))
def instrumentation_changes_within_structure_bounds(
    bp: SectionBlueprint,
) -> Optional[CohesionViolation]:
    """Every instrumentation_changes[*].bar must fit inside total_bars.

    A change at bar > total_bars or bar < 0 cannot be applied at any point
    in the section.
    """
    structure = bp.structure
    arrangement = bp.arrangement
    assert structure is not None and arrangement is not None
    total_bars = structure.value.total_bars

    for i, change in enumerate(arrangement.value.instrumentation_changes):
        if not (0 <= change.bar <= total_bars):
            return CohesionViolation(
                rule="instrumentation_changes_within_structure_bounds",
                severity="block",
                message=(
                    f"instrumentation_changes[{i}]: bar={change.bar} not in "
                    f"[0, {total_bars}]. Change would be invisible to the "
                    f"renderer. ({change.change!r})"
                ),
                spheres=("structure", "arrangement"),
            )
    return None


@cohesion_rule(spheres=("structure", "dynamics"))
def dynamics_within_structure_bounds(
    bp: SectionBlueprint,
) -> Optional[CohesionViolation]:
    """peak_bar and inflection_points[*].bar must fit inside total_bars.

    Phase 2.6 ships dynamics decisions as descriptive metadata (composer
    doesn't yet apply velocity envelopes). But out-of-bounds bars in
    dynamics are nonsensical regardless and would silently misrepresent
    the section if/when wired downstream.
    """
    structure = bp.structure
    dynamics = bp.dynamics
    assert structure is not None and dynamics is not None
    total_bars = structure.value.total_bars

    if dynamics.value.peak_bar is not None:
        if not (0 <= dynamics.value.peak_bar < total_bars):
            return CohesionViolation(
                rule="dynamics_within_structure_bounds",
                severity="block",
                message=(
                    f"dynamics.peak_bar={dynamics.value.peak_bar} not in "
                    f"[0, {total_bars}). Peak would land outside the section."
                ),
                spheres=("structure", "dynamics"),
            )
    for i, (bar, db) in enumerate(dynamics.value.inflection_points):
        if not (0 <= bar <= total_bars):
            return CohesionViolation(
                rule="dynamics_within_structure_bounds",
                severity="block",
                message=(
                    f"dynamics.inflection_points[{i}]: bar={bar} not in "
                    f"[0, {total_bars}]. Inflection point at db={db} "
                    f"would be invisible to the renderer."
                ),
                spheres=("structure", "dynamics"),
            )
    return None


@cohesion_rule(spheres=("structure", "arrangement"))
def arrangement_coverage_check(
    bp: SectionBlueprint,
) -> Optional[CohesionViolation]:
    """Warn if more than half the section has no active layers.

    Sometimes silence is intentional (compositional rest), so this is a
    WARNING not a block. The section will render but be largely silent,
    which is rarely what an agent intends. Surfacing it lets the user
    confirm or fix.
    """
    structure = bp.structure
    arrangement = bp.arrangement
    assert structure is not None and arrangement is not None
    total_bars = structure.value.total_bars
    if total_bars <= 0:
        return None

    coverage = [False] * total_bars
    for layer in arrangement.value.layers:
        start = max(0, layer.enters_at_bar)
        end = min(total_bars, layer.exits_at_bar)
        for bar in range(start, end):
            coverage[bar] = True

    silent_bars = sum(1 for c in coverage if not c)
    if silent_bars > total_bars // 2:
        return CohesionViolation(
            rule="arrangement_coverage_check",
            severity="warn",
            message=(
                f"{silent_bars}/{total_bars} bars have no active layers. "
                f"Section will be mostly silent. If intentional "
                f"(compositional rest), ignore this warning. Otherwise "
                f"extend layer bounds or add layers to fill the gap."
            ),
            spheres=("structure", "arrangement"),
        )
    return None


# ============================================================================
# Phase 2.7.1 — motifs cohesion rules
# ============================================================================
#
# motif-decider produces note sequences per layer. These rules verify
# the sequences are coherent with the surrounding skeleton :
#   - notes within structure.total_bars
#   - layer coverage matches arrangement.layers (no orphan motifs, no
#     unmatched layers above a tolerance)


@cohesion_rule(spheres=("structure", "motifs"))
def motif_notes_within_structure_bounds(
    bp: SectionBlueprint,
) -> Optional[CohesionViolation]:
    """Every note's bar must fit inside [0, total_bars).

    Out-of-bounds notes are silently dropped by the composer's cycle
    iteration (cycle_idx beyond num_cycles produces no output). Block
    them at cohesion time so the agent gets feedback rather than
    surprise-empty rendering.
    """
    structure = bp.structure
    motifs = bp.motifs
    assert structure is not None and motifs is not None
    total_bars = structure.value.total_bars

    for li, layer_motif in enumerate(motifs.value.by_layer):
        for ni, note in enumerate(layer_motif.notes):
            if note.bar < 0 or note.bar >= total_bars:
                return CohesionViolation(
                    rule="motif_notes_within_structure_bounds",
                    severity="block",
                    message=(
                        f"motifs.by_layer[{li}] ({layer_motif.layer_role!r}, "
                        f"{layer_motif.layer_instrument!r}) note[{ni}] at "
                        f"bar={note.bar} is outside [0, {total_bars}). "
                        f"The composer would silently drop it — fix the "
                        f"motif decision."
                    ),
                    spheres=("structure", "motifs"),
                )
    return None


@cohesion_rule(spheres=("arrangement", "motifs"))
def motifs_cover_arrangement_layers(
    bp: SectionBlueprint,
) -> Optional[CohesionViolation]:
    """Block when more than 30% of arrangement.layers have no matching motif.

    The composer falls back to placeholder stubs for unmatched layers,
    which is the disease motif-decider was built to cure. If a section
    ships with > 30% layers unmatched, it's still mostly stubs.

    A WARNING-level signal also fires for any non-zero unmatched count
    so the user sees the partial coverage explicitly.
    """
    arrangement = bp.arrangement
    motifs = bp.motifs
    assert arrangement is not None and motifs is not None

    layers = arrangement.value.layers
    if not layers:
        return None  # arrangement_layers cohesion handles this

    motif_keys = {
        (lm.layer_role.lower().strip(),
         lm.layer_instrument.lower().strip())
        for lm in motifs.value.by_layer
    }
    unmatched: list[tuple[str, str]] = []
    for layer in layers:
        key = (layer.role.lower().strip(),
               layer.instrument.lower().strip())
        if key not in motif_keys:
            # Try role-only match (composer's fallback strategy)
            role_only = any(
                k[0] == key[0] for k in motif_keys
            )
            if not role_only:
                unmatched.append((layer.role, layer.instrument))

    if not unmatched:
        return None

    coverage_pct = (len(layers) - len(unmatched)) / len(layers)
    if coverage_pct < 0.7:
        return CohesionViolation(
            rule="motifs_cover_arrangement_layers",
            severity="block",
            message=(
                f"motifs cover only {coverage_pct:.0%} of arrangement.layers "
                f"({len(layers) - len(unmatched)}/{len(layers)}). Composer "
                f"will fall back to placeholder stubs for unmatched layers : "
                f"{unmatched}. Below 70% coverage means the section is "
                f"still mostly stubs — fix the motif decision."
            ),
            spheres=("arrangement", "motifs"),
        )
    return CohesionViolation(
        rule="motifs_cover_arrangement_layers",
        severity="warn",
        message=(
            f"{len(unmatched)}/{len(layers)} layer(s) without matching motif "
            f"will render with placeholder stubs : {unmatched}. "
            f"Coverage {coverage_pct:.0%} is OK but consider adding motifs "
            f"for the missing layers to keep the agent decision rate high."
        ),
        spheres=("arrangement", "motifs"),
    )
