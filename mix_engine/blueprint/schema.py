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


# ============================================================================
# EQ corrective lane — Phase 4.2
# ============================================================================
#
# Tier A schema : decisions only, no XML. Tier B (eq8-configurator)
# consumes these and writes the .als ; automation-writer consumes any
# *_envelope tuples and writes the AutomationEnvelope XML.
#
# A single EQBandCorrection can describe BOTH a static cut AND a
# dynamic gain/freq/Q envelope. The static fields are the baseline
# (what the band sits at when no envelope is active); the *_envelope
# tuples list (bar, value) keypoints. Tier B decides whether to wire
# them as static-only (envelopes empty) or static+automated.


# Acceptable EQ band types. Semantic terms — Tier B (eq8-configurator)
# maps these to Eq8's 8 filter Modes (0=48dB LowCut, 1=12dB LowCut,
# 2=LowShelf, 3=Bell, 4=Notch, 5=HighShelf, 6=12dB HighCut, 7=48dB HighCut),
# using `slope_db_per_oct` to disambiguate steep vs gentle filters.
VALID_EQ_BAND_TYPES = frozenset({
    "bell",         # parametric peak/cut at frequency (Eq8 mode 3)
    "low_shelf",    # boost/cut everything below a corner (Eq8 mode 2)
    "high_shelf",   # boost/cut everything above a corner (Eq8 mode 5)
    "highpass",     # remove low frequencies below corner (Eq8 mode 0 or 1)
    "lowpass",      # remove high frequencies above corner (Eq8 mode 6 or 7)
    "notch",        # very narrow cut (Eq8 mode 4)
})

# Slopes available on Eq8's HPF/LPF filters. The decider can request
# either ; Tier B picks the right Eq8 Mode index. Semantic null: the
# band is not a steepness-bearing filter (bell/notch/shelves).
VALID_FILTER_SLOPES_DB_PER_OCT = frozenset({12.0, 48.0})

# Acceptable intent labels.
VALID_EQ_INTENTS = frozenset({
    "cut",      # negative gain — remove problem (resonance, masking, mud)
    "boost",    # positive gain — enhance presence/character
    "shape",    # complex tilt / multi-band tone shaping
    "filter",   # highpass/lowpass/notch — full band removal
})

# Reasonable Q range for parametric EQ. Below 0.1 = barely audible ;
# above 18 = extreme notch. Mix Analyzer typical resonance fixes use
# Q ∈ [3, 8] ; surgical notches use Q ∈ [10, 18].
EQ_Q_MIN: float = 0.1
EQ_Q_MAX: float = 18.0

# Audible frequency range bounds (slightly wider than 20-20000 Hz to
# allow for sub-bass shelf corners and sibilance ranges).
EQ_FREQ_MIN_HZ: float = 16.0
EQ_FREQ_MAX_HZ: float = 22000.0

# Gain range — Eq8 supports up to ±15 dB per band. Beyond ±12 dB is
# almost always a sign that the move belongs upstream (saturator,
# dynamics, level) rather than EQ.
EQ_GAIN_MIN_DB: float = -15.0
EQ_GAIN_MAX_DB: float = 15.0


@dataclass(frozen=True)
class EQAutomationPoint:
    """One key point in an EQ parameter automation envelope.

    Bar is the section-relative bar (0-indexed). Value's meaning depends
    on which envelope this point belongs to :
    - in `gain_envelope`: dB
    - in `freq_envelope`: Hz
    - in `q_envelope`: dimensionless Q
    """

    bar: int
    value: float


@dataclass(frozen=True)
class EQBandCorrection:
    """One EQ correction targeting one track + one frequency range.

    Tier A (eq-corrective-decider) emits these without knowing how Eq8
    encodes them in XML. Tier B (eq8-configurator) chooses which Eq8
    band slot (1-8) hosts each correction, allocates AutomationTarget
    Ids for envelope-bearing fields, and hands envelopes off to
    automation-writer.

    Static-only correction : envelopes are empty tuples. Dynamic
    correction : at least one envelope is non-empty ; the static
    `gain_db` / `center_hz` / `q` fields are the baseline (the value
    the param sits at when no envelope event has fired yet).
    """

    track: str  # must match an existing TrackInfo.name
    band_type: str  # in VALID_EQ_BAND_TYPES
    intent: str  # in VALID_EQ_INTENTS

    # Static (baseline) params — always set
    center_hz: float  # in [EQ_FREQ_MIN_HZ, EQ_FREQ_MAX_HZ]
    q: float  # in [EQ_Q_MIN, EQ_Q_MAX]
    gain_db: float  # in [EQ_GAIN_MIN_DB, EQ_GAIN_MAX_DB]

    # Slope steepness for highpass/lowpass filters (12 or 48 dB/oct in
    # Eq8). Set ONLY when band_type ∈ {highpass, lowpass} ; None for
    # all other types. None default = Tier B picks based on context
    # (gentle 12 dB for cleanup, steep 48 dB for surgical sub control).
    slope_db_per_oct: Optional[float] = None

    # Dynamic envelopes — empty tuple = static-only
    gain_envelope: tuple[EQAutomationPoint, ...] = ()
    freq_envelope: tuple[EQAutomationPoint, ...] = ()
    q_envelope: tuple[EQAutomationPoint, ...] = ()

    # Sections this correction applies to (Sections Timeline indices,
    # 0-based). Empty tuple = "always" (whole project).
    sections: tuple[int, ...] = ()

    rationale: str = ""
    inspired_by: tuple[MixCitation, ...] = ()


@dataclass(frozen=True)
class EQCorrectiveDecision:
    """All EQ corrective decisions for a track set.

    `bands` is the list of corrections (one band per anomaly / per
    spectral move). Tier B will pack them into Eq8 bands per track,
    respecting Eq8's 8-band limit.
    """

    bands: tuple[EQBandCorrection, ...] = ()


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
    eq_corrective: Optional[MixDecision[EQCorrectiveDecision]] = None
    # Future lanes (added with their producing agents):
    # routing: Optional[MixDecision[RoutingDecision]] = None
    # eq_creative: Optional[MixDecision[EQCreativeDecision]] = None
    # dynamics_corrective: Optional[MixDecision[DynamicsCorrectiveDecision]] = None
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
    # EQ corrective lane (Phase 4.2)
    "VALID_EQ_BAND_TYPES",
    "VALID_EQ_INTENTS",
    "VALID_FILTER_SLOPES_DB_PER_OCT",
    "EQ_Q_MIN",
    "EQ_Q_MAX",
    "EQ_FREQ_MIN_HZ",
    "EQ_FREQ_MAX_HZ",
    "EQ_GAIN_MIN_DB",
    "EQ_GAIN_MAX_DB",
    "EQAutomationPoint",
    "EQBandCorrection",
    "EQCorrectiveDecision",
]
