"""Mix-side blueprint schema — design tenets parallel to composition_engine.

A `MixBlueprint` is the immutable, partial-fill-friendly carrier of every
decision a multi-agent mix session produces. Each lane (diagnostic, routing,
EQ corrective, dynamics, …) attaches its `MixDecision[T]` independently;
cohesion rules cross-check them after the fact.

Design tenets (identical to composition_engine.blueprint.schema):

1. **Immutability** — every dataclass is frozen, every collection a tuple.
2. **Provenance is first-class** — every decision carries citations to
   the diagnostic point or the device-mapping rule that motivates it.
3. **Partial-fill friendly** — every lane is Optional. Cohesion rules
   skip silently when their dependencies aren't filled yet.
4. **Read what's there, decide what to change** — mix agents start from
   the existing .als state (via mix-diagnostician) and propose deltas,
   not full re-syntheses.

Phase 4.1 ships the foundation types (MixDecision, MixCitation,
MixBlueprint) plus the diagnostic lane (TrackInfo, FullMixMetrics,
Anomaly, HealthScore, DiagnosticReport). Other lanes land one-by-one
with their producing agent — same rule-with-consumer discipline as
composition.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Generic, Optional, TypeVar


# Mix lanes — keep in sync with the Mix Director DAG and the cohesion
# registry. Adding a lane requires also: adding the *Decision dataclass,
# extending MixBlueprint, updating MIX_DEPENDENCIES, and re-running tests.
MIX_LANES: tuple[str, ...] = (
    "diagnostic",
    "routing",
    "eq_corrective",
    "eq_creative",
    "dynamics_corrective",
    "saturation_color",
    "stereo_spatial",
    "automation",
    "chain",
    "mastering",
)


T = TypeVar("T")


@dataclass(frozen=True)
class MixCitation:
    """A pointer back to the source that justified a mix decision.

    Sources are typed via `kind` so consumers can route citations:
    - "diagnostic" — a row/metric in the Mix Analyzer Excel report
    - "device_mapping" — a slice of ableton_devices_mapping.json
    - "manipulation_guide" — a section of ALS_MANIPULATION_GUIDE.md
    - "pdf" — a passage from the mix engineer reusable prompt PDF
    - "user_brief" — the user's own intent statement
    - "als_state" — direct observation of the .als XML
    """

    kind: str
    path: str  # locator inside the source (e.g. "Anomalies!A3", "$write_rules.eq8")
    excerpt: str  # the actual text/value cited


@dataclass(frozen=True)
class MixDecision(Generic[T]):
    """The provenance-carrying envelope around any lane decision."""

    value: T
    lane: str
    cited_by: tuple[MixCitation, ...] = ()
    rationale: str = ""
    confidence: float = 0.0
    # Used by lanes that have multiple modes (e.g. automation: creative vs
    # corrective). Empty string for lanes that don't.
    mode: str = ""


# ============================================================================
# Diagnostic lane — Phase 4.1
# ============================================================================
#
# The diagnostic lane's output (DiagnosticReport) is consumed by every
# downstream mix agent. Its schema is therefore the most stable of the
# mix lanes — extending it requires updating all consumers. Be conservative
# when adding fields here; prefer enriching individual TrackInfo / Anomaly
# fields over inventing new top-level structures.


@dataclass(frozen=True)
class TrackInfo:
    """One track's identity, routing, and chain state."""

    name: str
    track_type: str  # "Audio" | "MIDI" | "Group" | "Return" | "Master"
    parent_bus: Optional[str]
    color: str  # hex or Ableton index
    devices: tuple[str, ...]  # device names in chain order
    volume_db: float  # converted from XML logarithmic value
    pan: float  # -1.0 (full L) to +1.0 (full R)
    sidechain_targets: tuple[str, ...]  # tracks this one ducks
    activator: bool  # track-on


@dataclass(frozen=True)
class FullMixMetrics:
    """Project-level loudness + spectral + spatial metrics from Excel."""

    integrated_lufs: float
    true_peak_dbtp: float
    crest_factor_db: float
    plr_db: float  # peak-to-loudness ratio
    lra_db: float  # loudness range
    dominant_band: str  # "low" | "low-mid" | "mid" | "high-mid" | "high"
    correlation: float  # mono compatibility, -1..+1
    stereo_width: float  # 0..1
    spectral_entropy: float


@dataclass(frozen=True)
class Anomaly:
    """One issue surfaced by Mix Analyzer.

    Severity grades follow the Excel report convention; agents downstream
    use them to prioritize moves (critical → fix first, info → nice-to-have).
    """

    severity: str  # "critical" | "warning" | "info"
    category: str  # "shared_resonance" | "phase" | "level" | "stereo" | "masking" | ...
    description: str
    affected_tracks: tuple[str, ...]
    suggested_fix_lane: str = ""  # which mix lane is best positioned to address it


@dataclass(frozen=True)
class HealthScore:
    """The user's primary cross-iteration progress indicator."""

    overall: float  # 0..100
    breakdown: tuple[tuple[str, float], ...]  # (category, score)


@dataclass(frozen=True)
class DiagnosticReport:
    """The structured output of mix-diagnostician.

    Consumed by every other mix agent — they never re-read the .als or
    the Excel directly once this report exists. Treat as immutable
    snapshot of project state at a given moment.
    """

    project_name: str
    full_mix: FullMixMetrics
    tracks: tuple[TrackInfo, ...]
    anomalies: tuple[Anomaly, ...]
    health_score: HealthScore
    routing_warnings: tuple[str, ...] = ()  # broken sidechain refs, "No Output", etc.


@dataclass(frozen=True)
class MixBlueprint:
    """The immutable carrier of all lane decisions for one mix session.

    Like SectionBlueprint on the composition side, but for an existing
    .als rather than a new one. The blueprint describes deltas to apply,
    not absolute state.

    Phase 4.1 ships only the diagnostic lane wiring; other lanes land
    as their producing agent materializes.
    """

    name: str
    diagnostic: Optional[MixDecision[DiagnosticReport]] = None
    # Future lanes (added with their producing agents):
    # routing: Optional[MixDecision[RoutingDecision]] = None
    # eq_corrective: Optional[MixDecision[EqCorrectiveDecision]] = None
    # ... etc per MIX_LANES

    def with_decision(self, lane: str, decision: MixDecision) -> "MixBlueprint":
        """Return a new MixBlueprint with `lane` filled by `decision`.

        Validates the lane name against MIX_LANES — typos raise rather
        than silently creating a phantom field.
        """
        if lane not in MIX_LANES:
            raise ValueError(
                f"Unknown mix lane {lane!r}. Valid lanes: {MIX_LANES}"
            )
        if lane != decision.lane:
            raise ValueError(
                f"Decision lane mismatch: blueprint slot {lane!r} but "
                f"decision.lane = {decision.lane!r}"
            )
        return replace(self, **{lane: decision})

    def filled_lanes(self) -> tuple[str, ...]:
        """Return the lane names whose decision is populated."""
        return tuple(
            lane for lane in MIX_LANES if getattr(self, lane, None) is not None
        )


__all__ = [
    "MIX_LANES",
    "MixCitation",
    "MixDecision",
    "TrackInfo",
    "FullMixMetrics",
    "Anomaly",
    "HealthScore",
    "DiagnosticReport",
    "MixBlueprint",
]
