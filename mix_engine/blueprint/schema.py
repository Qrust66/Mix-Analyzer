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


# ============================================================================
# CDE diagnostics absorption (Phase 4.2.8)
# ============================================================================
#
# Mix-diagnostician now reads `<projet>_diagnostics.json` produced by
# `cde_engine.py:1614` and exposes the structured diagnostics inside
# DiagnosticReport. eq-corrective-decider (and other Tier A agents)
# consume these typed CDEDiagnostic objects rather than parsing JSON
# at the agent level — clean decision/execution separation.

VALID_CDE_SEVERITIES = frozenset({"critical", "moderate"})

# CDE issue_type values (cde_engine.py emits these). Open-set : new ones
# may be added by future CDE detectors. The parser warns but does not
# raise on unknown — we want to forward novel diagnostics rather than
# silently drop them.
KNOWN_CDE_ISSUE_TYPES = frozenset({"masking_conflict", "accumulation_risk"})

# CDE confidence labels.
VALID_CDE_CONFIDENCES = frozenset({"low", "medium", "high"})

# CDE application_status values (None = never processed).
VALID_CDE_APPLICATION_STATUSES = frozenset({"pending", "applied", "rejected"})


@dataclass(frozen=True)
class CDEMeasurement:
    """The `measurement` block inside a CDE diagnostic.

    CDE writes more fields than `frequency_hz`; agents may not need all
    of them. We expose `frequency_hz` (the EQ-relevant one) plus a
    `raw` dict for forward-compat (anything the agent wants beyond
    frequency_hz can be read from `raw`).
    """

    frequency_hz: float
    raw: dict


@dataclass(frozen=True)
class CDETFPContext:
    """The `tfp_context` block inside a CDE diagnostic.

    `track_a_role` / `track_b_role` are pairs `(Importance, Function)`
    where Importance ∈ {"H", "S", ...} (Hero, Support) and Function is
    role-specific letter codes (see `tfp_parser.py`). None when CDE
    didn't have role info.
    """

    track_a_role: Optional[tuple[str, str]] = None
    track_b_role: Optional[tuple[str, str]] = None
    role_compatibility: str = ""


@dataclass(frozen=True)
class CDECorrectionRecipe:
    """The `primary_correction` (or `fallback_correction`) block.

    `parameters` is kept as a free-form dict because CDE writes
    different shapes per device (EQ8 vs Kickstart). Agents extract
    what they need (frequency_hz, gain_db, q, active_in_sections, etc.).
    """

    target_track: str
    device: str  # e.g., "EQ8 — Peak Resonance" or "Kickstart 2"
    approach: str  # e.g., "static_dip", "reciprocal_cuts", "musical_dip", "sidechain"
    parameters: dict
    applies_to_sections: tuple[int, ...]
    rationale: str
    confidence: str  # one of VALID_CDE_CONFIDENCES


@dataclass(frozen=True)
class CDEDiagnostic:
    """One CDE diagnostic, fully structured.

    Mix-diagnostician parses `<projet>_diagnostics.json` and produces
    one of these per entry in `diagnostics[]`. Tier A agents (e.g.,
    eq-corrective-decider) iterate `DiagnosticReport.cde_diagnostics`
    and apply the CDE DEFER MODE protocol.
    """

    diagnostic_id: str
    issue_type: str  # see KNOWN_CDE_ISSUE_TYPES
    severity: str  # one of VALID_CDE_SEVERITIES
    section: Optional[str] = None
    track_a: str = ""
    track_b: Optional[str] = None
    measurement: Optional[CDEMeasurement] = None
    tfp_context: Optional[CDETFPContext] = None
    primary_correction: Optional[CDECorrectionRecipe] = None
    fallback_correction: Optional[CDECorrectionRecipe] = None
    expected_outcomes: tuple[str, ...] = ()
    potential_risks: tuple[str, ...] = ()
    application_status: Optional[str] = None  # see VALID_CDE_APPLICATION_STATUSES


# ============================================================================
# Freq Conflicts metadata absorption (Phase 4.2.8)
# ============================================================================
#
# Mix-diagnostician reads B2 (threshold) and B3 (min_tracks) from the
# Freq Conflicts sheet, plus the band × track matrix and per-band
# conflict_count + status. Tier A agents read these typed structures
# rather than referencing Excel cells directly.


@dataclass(frozen=True)
class FreqConflictsMetadata:
    """Configurable parameters from Freq Conflicts sheet (B2, B3)."""

    threshold_pct: float  # cell B2 — % energy threshold for conflict
    min_tracks: int  # cell B3 — min tracks > threshold to flag conflict


@dataclass(frozen=True)
class BandConflict:
    """One row of the Freq Conflicts matrix.

    `energy_per_track` is a tuple of (track_name, energy_pct) pairs
    (frozen-friendly form of dict). `conflict_count` is the COUNTIF
    (tracks > threshold) ; `status` is the textual classification
    (e.g., "Conflict", "OK").
    """

    band_label: str  # e.g., "low-mid (200-500Hz)"
    energy_per_track: tuple[tuple[str, float], ...]
    conflict_count: int
    status: str


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
    # Phase 4.2.8 : CDE + Freq Conflicts absorption
    cde_diagnostics: tuple[CDEDiagnostic, ...] = ()  # parsed from <projet>_diagnostics.json
    freq_conflicts_meta: Optional[FreqConflictsMetadata] = None  # B2/B3 from sheet
    freq_conflicts_bands: tuple[BandConflict, ...] = ()  # rows of the matrix

    def get_health_category_score(self, category: str) -> Optional[float]:
        """Lookup a Mix Health Score category score by name (case-insensitive).

        Phase 4.3 helper consumed by every Tier A agent that conditions on a
        single canonical category. The 5 categories emitted by
        ``mix_analyzer.py:4869`` are: Loudness, Dynamics, Spectral Balance,
        Stereo Image, Anomalies. mix-diagnostician normalizes them to lowercase
        in ``health_score.breakdown`` ; this method matches case-insensitively
        so it works on either form.

        Returns None if no breakdown entry matches.
        """
        target = category.strip().lower()
        for cat, score in self.health_score.breakdown:
            if cat.strip().lower() == target:
                return score
        return None


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

# Stereo processing mode for the EQ band. Eq8 supports global Stereo,
# Mid, Side modes — one mode per Eq8 instance. The decider thinks per
# band ("cut sub on Sides only") and Tier B groups bands by mode,
# instantiating multiple Eq8 devices on the same track when needed.
VALID_PROCESSING_MODES = frozenset({
    "stereo",  # Full L/R (default — most common)
    "mid",     # Mid only (L+R)/2 — center / mono content
    "side",    # Side only (L-R)/2 — stereo information / extremes
})


# Position of the corrective EQ within the track's existing device chain.
# Refined Phase 4.2.5 from the audio engineer audit : the previous
# pre_dynamics / post_dynamics lumping was too coarse to express the
# actual musical sweet spot for corrective EQ on percussive tracks.
#
# Device categorization for placement (Tier B reads this):
# - Gate       : standalone, often first on percussion
# - Compressor : Compressor2, GlueCompressor, Limiter
# - DrumBuss   : treated as Saturation (hybrid, but character = saturation)
# - Saturator  : AND DrumBuss
# - AutoFilter2: filter (rarely interacts with corrective EQ — defaults)
VALID_CHAIN_POSITIONS = frozenset({
    "default",                    # Tier B picks based on chain content
    "chain_start",                # First device in the chain
    "post_gate_pre_compressor",   # ⭐ Sweet spot for corrective EQ on
                                  #   percussive tracks (after gate cleans
                                  #   transients, before comp glues them)
    "pre_compressor",             # Before any Compressor2/GlueComp/Limiter
                                  #   (alias of post_gate_pre_compressor
                                  #   when no Gate exists)
    "post_compressor",            # After last compressor (typically just
                                  #   before any Limiter finalizer)
    "pre_saturation",             # Before any Saturator OR DrumBuss
    "post_saturation",            # After last Saturator/DrumBuss — clean
                                  #   harmonic artifacts generated
    "pre_eq_creative",            # Before another EQ Eight downstream that
                                  #   serves a creative role (boost/tilt)
    "post_eq_creative",           # After the creative EQ (uncommon)
    "chain_end",                  # Last device — final corrective sweep
})

# Deprecated chain_position values from Phase 4.2.3. The parser raises
# with a redirect message rather than silently mapping (would mask
# intent ambiguity that this refactor is meant to fix).
DEPRECATED_CHAIN_POSITIONS_REDIRECT = {
    "pre_dynamics": (
        "Use 'post_gate_pre_compressor' (after Gate, before Comp — "
        "sweet spot for corrective EQ on percussive tracks) or "
        "'pre_compressor' (when no Gate exists)."
    ),
    "post_dynamics": (
        "Use 'post_compressor' (after Comp/GlueComp, typically before "
        "Limiter) or 'chain_end' (truly last)."
    ),
}

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

    # Where in the track's existing device chain the new EQ should sit.
    # Default "default" means Tier B picks based on chain content
    # (typically pre_dynamics if any compressor exists, else chain_end).
    # Critical for musical correctness : pre-comp HPF cleans the
    # compressor's input, post-comp HPF catches comp-generated sub
    # artifacts — different jobs.
    chain_position: str = "default"

    # Stereo processing mode for this band. Default "stereo" = full
    # L/R. "mid" = center only ; "side" = stereo extremes only. Tier B
    # may need to instantiate multiple Eq8 devices when bands on the
    # same track ask for different modes (each Eq8 has a single
    # Mode_global). Critical for solving conflicts that only exist on
    # one stereo dimension (e.g., sub buildup on Sides without losing
    # mono kick punch).
    processing_mode: str = "stereo"

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


# ============================================================================
# Dynamics corrective lane — Phase 4.3
# ============================================================================
#
# Tier A schema for compression / gating / limiting / sidechain ducking /
# transient shaping moves. Sister of EQCorrectiveDecision but for the
# dynamics domain. Tier B (dynamics-configurator, future) reads these
# decisions and writes Compressor2 / GlueCompressor / Limiter / Gate /
# DrumBuss XML. automation-writer (Tier B) consumes the *_envelope tuples.
#
# Design notes from the audit (Phase 4.3 Pass 2):
# 1. Tier A emits intent (e.g. ``sidechain.depth_db = -8.0``) ; Tier B
#    translates to the right Compressor2 threshold/ratio combo. Same
#    separation as eq-corrective.
# 2. Kickstart 2 is NOT in ``ableton_devices_mapping.json`` (only 9 native
#    devices + 2 VST3). CDE emits ``device="Kickstart 2"`` symbolically ;
#    dynamics-corrective-decider's defer mode translates to
#    ``device="Compressor2"`` with ``sidechain.mode="external"``.
# 3. ``release_auto: bool`` separates from ``release_ms`` because GlueComp
#    encodes auto via enum value 6 and Limiter via a bool — different
#    mechanisms not unifiable as a single float sentinel.
# 4. Per-track audio metrics (crest_factor) are NOT typed in TrackInfo
#    today (rule-with-consumer : extend mix-diagnostician when a 2nd
#    consumer arises). Brief explicit on a track is therefore the primary
#    trigger for Scenario A (standard compression).


# Type of dynamic move — categorizes intent musically. Each maps to one
# or more devices ; some devices serve multiple types (Compressor2 covers
# compress/sidechain_duck/parallel_compress/deess).
VALID_DYNAMICS_TYPES = frozenset({
    "compress",            # Standard track compression (Compressor2)
    "sidechain_duck",      # External sidechain ducking (kick → bass typique) — CDE Kickstart 2 maps here
    "bus_glue",            # GlueCompressor on Group/bus — 1-3 dB GR, low ratio
    "gate",                # Noise floor / bleed cleanup (Gate)
    "limit",               # Per-track peak control (Limiter ; rare ; master = mastering scope)
    "transient_shape",     # DrumBuss.Transients enhance/tame transients
    "parallel_compress",   # DryWet < 100% — sustain without killing transients
    "deess",               # Multi-band dynamic via Compressor2 with internal_filtered sidechain
})

# Device family — Tier B maps to the actual Ableton plugin.
# Kickstart 2 is intentionally absent (not mapped in catalog).
VALID_DYNAMICS_DEVICES = frozenset({
    "Compressor2",         # Le couteau suisse — incl. external + internal_filtered sidechain
    "GlueCompressor",      # SSL-style bus glue ; sidechain natif
    "Limiter",             # Peak control finalizer
    "Gate",                # Noise floor / bleed cleanup
    "DrumBuss",            # Hybrid ; corrective lane uses Transients section only
})

# Sidechain mode (when dynamics_type involves sidechain).
VALID_SIDECHAIN_MODES = frozenset({
    "none",                # No sidechain
    "external",            # Trigger from another track (ducking)
    "internal_filtered",   # Sidechain filter on the same track's signal (de-essing)
})

# Chain position — dynamics-specific vocabulary. Co-designed with
# eq-corrective's VALID_CHAIN_POSITIONS so that absolute device order is
# unambiguous when both agents emit corrections for the same track.
# Tier B reconciles the absolute slot ordering.
VALID_DYNAMICS_CHAIN_POSITIONS = frozenset({
    "default",                  # Tier B picks based on chain content
    "gate_first",               # Gate must be 1st (pre-cleanup before any other processing)
    "pre_eq_corrective",        # Before the corrective EQ8 (rare ; used for gate before EQ to avoid amplifying noise)
    "post_eq_corrective",       # After the corrective EQ8 (typical compressor placement)
    "pre_saturation",           # Before Saturator/DrumBuss — compress clean signal before coloration
    "post_saturation",          # After last Saturator/DrumBuss — clamp peaks generated by saturation
    "pre_limiter",              # Before the Limiter finalizer (typical : final comp then limit)
    "chain_end",                # Last device — generic, used for bus_glue (GlueComp on Group typically last)
                                # ; semantic "no further processing planned for this track"
    "chain_end_limiter",        # Limiter-specific terminal slot (mandatory for Limiter device, distinct
                                # from generic chain_end for clarity when both could apply)
})


# ============================================================================
# Dynamics value ranges — audio-physics bounds (parser-enforced)
# ============================================================================

DYN_THRESHOLD_MIN_DB: float = -60.0
DYN_THRESHOLD_MAX_DB: float = 0.0
DYN_RATIO_MIN: float = 1.0          # 1:1 = no compression (legal but caught by cross-field if dynamics_type=compress)
DYN_RATIO_MAX: float = 100.0        # brick-wall ratio (Limiter territory)
DYN_ATTACK_MIN_MS: float = 0.01
DYN_ATTACK_MAX_MS: float = 200.0
DYN_RELEASE_MIN_MS: float = 1.0
DYN_RELEASE_MAX_MS: float = 5000.0  # 5s (incl. very long release for ambient/cinematic)
DYN_MAKEUP_MIN_DB: float = -24.0
DYN_MAKEUP_MAX_DB: float = 24.0
DYN_KNEE_MIN_DB: float = 0.0        # hard knee
DYN_KNEE_MAX_DB: float = 24.0       # very soft knee
DYN_DRY_WET_MIN: float = 0.0        # 0 = full dry (bypass)
DYN_DRY_WET_MAX: float = 1.0        # 1 = full wet
DYN_SIDECHAIN_DEPTH_MIN_DB: float = -24.0
DYN_SIDECHAIN_DEPTH_MAX_DB: float = 0.0
DYN_CEILING_MIN_DB: float = -12.0
DYN_CEILING_MAX_DB: float = 0.0     # Limiter ceiling must be ≤ 0 dBFS
DYN_TRANSIENTS_MIN: float = -1.0    # DrumBuss.Transients (tame)
DYN_TRANSIENTS_MAX: float = 1.0     # DrumBuss.Transients (enhance)


@dataclass(frozen=True)
class DynamicsAutomationPoint:
    """One key point in a dynamics parameter automation envelope.

    Bar is the section-relative bar (0-indexed). Value's meaning depends
    on which envelope this point belongs to :
    - in `threshold_envelope`: dB
    - in `makeup_envelope`: dB
    - in `dry_wet_envelope`: 0..1
    - in `sidechain_depth_envelope`: dB (negative)
    """

    bar: int
    value: float


@dataclass(frozen=True)
class SidechainConfig:
    """Sidechain configuration block.

    Required when ``dynamics_type == "sidechain_duck"`` (cross-field
    enforced). Optional for ``deess`` (uses ``mode="internal_filtered"``).

    `depth_db` is the agent's INTENT (e.g. -8 dB = "duck the target by
    8 dB on each trigger hit"). Tier B translates to Compressor2
    threshold + ratio + attack/release combo that achieves that depth
    given the trigger envelope shape.

    `filter_freq_hz` / `filter_q` configure the Compressor2 sidechain
    EQ section (used for de-essing : filter the sidechain so the comp
    only triggers on sibilance freqs).
    """

    mode: str                                 # in VALID_SIDECHAIN_MODES
    trigger_track: Optional[str] = None       # required if mode == "external"
    depth_db: Optional[float] = None          # intent dB ; required if external sidechain_duck
    filter_freq_hz: Optional[float] = None    # for internal_filtered (de-ess) or external EQ shaping
    filter_q: Optional[float] = None


@dataclass(frozen=True)
class DynamicsCorrection:
    """One dynamics correction targeting one track.

    Tier A (dynamics-corrective-decider) emits these without knowing how
    Compressor2/GlueCompressor/Gate/Limiter/DrumBuss encode them in XML.
    Tier B reconciles with the existing chain (track.devices), allocates
    the device, writes XML, and hands envelopes off to automation-writer.

    Static-only correction : envelopes are empty tuples. Dynamic
    correction : at least one envelope is non-empty ; the static fields
    are the baseline.

    Param defaults are None (= "device default, Tier B picks"). At least
    one parameter must be set unless ``dynamics_type`` is ``transient_shape``
    (which sets only DrumBuss.Transients) or ``gate``/``limit`` (which
    have device-specific required fields enforced by cross-field checks).
    """

    track: str                              # must match an existing TrackInfo.name
    dynamics_type: str                      # in VALID_DYNAMICS_TYPES
    device: str                             # in VALID_DYNAMICS_DEVICES

    # Static (baseline) params — None = device default
    threshold_db: Optional[float] = None    # in [DYN_THRESHOLD_MIN_DB, DYN_THRESHOLD_MAX_DB]
    ratio: Optional[float] = None           # in [DYN_RATIO_MIN, DYN_RATIO_MAX]
    attack_ms: Optional[float] = None       # in [DYN_ATTACK_MIN_MS, DYN_ATTACK_MAX_MS]
    release_ms: Optional[float] = None      # in [DYN_RELEASE_MIN_MS, DYN_RELEASE_MAX_MS]
    release_auto: bool = False              # Tier B encodes per device : GlueComp enum=6 ; Limiter AutoRelease=true ; Compressor2 raises (no auto)
    makeup_db: Optional[float] = None       # in [DYN_MAKEUP_MIN_DB, DYN_MAKEUP_MAX_DB]
    knee_db: Optional[float] = None         # in [DYN_KNEE_MIN_DB, DYN_KNEE_MAX_DB]
    dry_wet: Optional[float] = None         # in [DYN_DRY_WET_MIN, DYN_DRY_WET_MAX]
    ceiling_db: Optional[float] = None      # Limiter only ; in [DYN_CEILING_MIN_DB, DYN_CEILING_MAX_DB]
    transients: Optional[float] = None      # DrumBuss only ; in [DYN_TRANSIENTS_MIN, DYN_TRANSIENTS_MAX]

    # Sidechain configuration (required for sidechain_duck and deess)
    sidechain: Optional[SidechainConfig] = None

    # Placement
    chain_position: str = "default"         # in VALID_DYNAMICS_CHAIN_POSITIONS
    processing_mode: str = "stereo"         # stereo / mid / side (M/S rare in dynamics — see anti-patterns)

    # Dynamic envelopes — empty tuple = static-only ; ≥ 3 points if non-empty
    threshold_envelope: tuple[DynamicsAutomationPoint, ...] = ()
    makeup_envelope: tuple[DynamicsAutomationPoint, ...] = ()
    dry_wet_envelope: tuple[DynamicsAutomationPoint, ...] = ()
    sidechain_depth_envelope: tuple[DynamicsAutomationPoint, ...] = ()

    # Sections this correction applies to (Sections Timeline indices,
    # 0-based). Empty tuple = "always" (whole project). Required if any
    # envelope is non-empty (cross-field enforced).
    sections: tuple[int, ...] = ()

    rationale: str = ""
    inspired_by: tuple[MixCitation, ...] = ()


@dataclass(frozen=True)
class DynamicsCorrectiveDecision:
    """All dynamics corrective decisions for a track set.

    `corrections` is the list of moves (one per track per dynamics_type).
    Multiple corrections on the same track must have distinct
    ``dynamics_type`` (cross-field enforced) — stacking 2 plain
    compressors is a pumping mess.
    """

    corrections: tuple[DynamicsCorrection, ...] = ()


# ============================================================================
# Routing & sidechain lane — Phase 4.4
# ============================================================================
#
# Tier A schema for sidechain reference repairs / creations / removals.
# Foundation lane in the Mix Director DAG : runs BEFORE the corrective
# trio (eq / dynamics / stereo) so that downstream agents see a clean
# routing graph.
#
# Phase 4.4 scope is intentionally narrow (rule-with-consumer) :
# ONLY sidechain refs. Send / Group / Master output routing are
# explicitly out-of-scope until a downstream consumer requires them.
#
# Tier B (routing-configurator, future) consumes these decisions to
# update <SideChain>/<AudioInputProcessing>/<AudioIn>/<RoutingTarget>
# text in the .als XML.
#
# Audit findings applied (cf. Pass 1 + Pass 2 audits) :
# - Drop "sidechain_validate" fix_type (informational noise — Pass 1 D)
# - Drop als_path_hint field (premature, no Tier B consumer — Pass 1 C)
# - Drop ROUTING_MAX_REPAIRS_PER_TRACK constant (becomes agent-prompt
#   anti-pattern, not parser-enforced — Pass 1 F)
# - Drop TFP Hero/Support inference fallback (redundant with CDE
#   primary_correction match — Pass 2 #1)
# - Detection regex STALE_SIDECHAIN_REGEX exposed for parser cross-field
#   checks AND agent-side detection logic


VALID_ROUTING_FIX_TYPES = frozenset({
    "sidechain_redirect",     # Change trigger_track of an existing sidechain (stale ref repair)
    "sidechain_remove",       # Disable broken sidechain (no good target available)
    "sidechain_create",       # Add new sidechain wiring (brief-driven)
})

# RoutingTarget format convention used by Ableton XML for inter-track refs.
# When a track is renamed, mix-diagnostician keeps the raw form (rather
# than resolving) and adds an entry to ``routing_warnings`` ; the raw
# form is the stale-ref signal for routing-and-sidechain-architect.
#
# Patterns matched : ``AudioIn/Track.4/PostFxOut``, ``AudioIn/Track.10``,
# ``AudioIn/Track.0/PostMixerOut``, etc.
#
# Patterns NOT matched (intentional — these refs target permanent
# destinations that don't get renamed) :
# - ``AudioIn/Bus.N/...`` (busses)
# - ``AudioIn/Master/...`` (master)
# - ``AudioIn/Returns/...`` (returns)
# - Resolved track names like ``Kick A``
STALE_SIDECHAIN_REGEX: str = r"^AudioIn/Track\.\d+(/.*)?$"


@dataclass(frozen=True)
class SidechainRepair:
    """One sidechain routing repair, creation, or removal.

    Phase 4.4 scope : sidechain refs only. Send / Group / Master routing
    out-of-scope until a downstream consumer demands them.

    Field requirements per fix_type (parser-enforced) :
    - ``sidechain_redirect`` : both ``current_trigger`` and ``new_trigger``
      required (non-empty), and they must differ.
    - ``sidechain_remove``   : ``current_trigger`` required ; ``new_trigger``
      must be None.
    - ``sidechain_create``   : ``new_trigger`` required ; ``current_trigger``
      must be None.

    For redirect/create, ``new_trigger`` must be a resolved track name
    (not a raw ``AudioIn/Track.N`` form — recreating a stale ref is a
    contradiction). Parser validates via STALE_SIDECHAIN_REGEX.
    """

    track: str                                    # the track owning the sidechain (target of the duck)
    fix_type: str                                 # in VALID_ROUTING_FIX_TYPES
    current_trigger: Optional[str] = None         # see field requirements above
    new_trigger: Optional[str] = None             # see field requirements above
    rationale: str = ""
    inspired_by: tuple[MixCitation, ...] = ()


@dataclass(frozen=True)
class RoutingDecision:
    """All routing decisions for the project.

    `repairs` is the list of sidechain wiring fixes/creations/removals.
    Tier B applies them in order ; the design is idempotent : re-running
    routing-and-sidechain-architect on a .als post-Tier-B-applied
    produces ``repairs=()`` because gates require stale signals that no
    longer exist after fixes apply.
    """

    repairs: tuple[SidechainRepair, ...] = ()


# ============================================================================
# Stereo & spatial lane — Phase 4.5
# ============================================================================
#
# Tier A schema for pan / width / phase / mono / balance / mid-side moves.
# Parallel sibling of eq-corrective and dynamics-corrective. Tier B
# (spatial-configurator, future) writes Mixer.Pan OR StereoGain.* params
# per move_type.
#
# Phase 4.5 scope (rule-with-consumer) :
# 7 move types covering the StereoGain swiss-army-knife capabilities :
#   pan, width, mono, bass_mono, phase_flip, balance, ms_balance.
# Out-of-scope (Phase 4.5.x extensions) :
#   ChannelMode (Left/Right/Swap routing) — sound design / repair
#   Trackspacer VST3 dynamic spectral carving — eq-creative scope
#   Reverb/delay sends spatial depth — fx-decider scope
#   Per-track stereo_state typed exposure — when 2nd consumer needs it
#
# Audit findings applied (cf. Pass 1 v2 + Pass 2 audits) :
# - StereoWidth range corrected to [0, 4] (catalog real range, was [0, 2])
# - MidSideBalance range corrected to [0, 2] with neutral=1.0
#   (was [-1, 1] with neutral=0 — fictive encoding, real catalog uses
#    0='100M' / 1='neutre' / 2='100S')
# - BassMonoFrequency range corrected to [50, 500] (was [60, 250])
# - Scenario C (phase_flip) requires is_stereo gate (mix_analyzer.py:856
#   only fires Phase correlation anomaly on stereo content)


VALID_SPATIAL_MOVE_TYPES = frozenset({
    "pan",            # Mixer.Pan adjustment (track-level, no device needed)
    "width",          # StereoGain.StereoWidth ∈ [0, 4] — narrow (<1) OR wide (>1)
    "mono",           # StereoGain.Mono = True (full mono summing)
    "bass_mono",      # StereoGain.BassMono = True + BassMonoFrequency cutoff
    "phase_flip",     # StereoGain.PhaseInvertL OR .PhaseInvertR (one channel only)
    "balance",        # StereoGain.Balance L/R level adjustment (≠ Pan, for stereo sources)
    "ms_balance",     # StereoGain.MidSideBalance — mid vs side energy carving
})

VALID_SPATIAL_CHAIN_POSITIONS = frozenset({
    "default",                       # Tier B picks
    "chain_start",                   # phase_flip — fix early before processing
    "post_eq_corrective",            # standard placement post-EQ
    "post_dynamics_corrective",      # post-dynamics (after compression shapes signal)
    "chain_end",                     # last device — typical pan-stage / width
})

VALID_PHASE_CHANNELS = frozenset({"L", "R"})  # which single channel to flip
                                              # (both flipped = no-op, agent picks one)


# ============================================================================
# Stereo value ranges — audio-physics bounds (parser-enforced)
# ============================================================================
#
# All ranges verified against ableton/ableton_devices_mapping.json
# StereoGain.params (Phase 4.5 audit Pass 1 v2 Findings A/B/C).

PAN_MIN: float = -1.0           # full L (Mixer.Pan native)
PAN_MAX: float = 1.0            # full R

STEREO_WIDTH_MIN: float = 0.0   # full mono
STEREO_WIDTH_NEUTRAL: float = 1.0   # 100% (default neutre — no-op identity)
STEREO_WIDTH_MAX: float = 4.0   # 400% (catalog real max ; ear-candy beyond 2.5)

BALANCE_MIN: float = -1.0       # full attenuation R (= more L)
BALANCE_NEUTRAL: float = 0.0    # center (no-op identity)
BALANCE_MAX: float = 1.0        # full attenuation L (= more R)

MS_BALANCE_MIN: float = 0.0     # full mid (no side) — '100M' in catalog
MS_BALANCE_NEUTRAL: float = 1.0 # neutral — no-op identity
MS_BALANCE_MAX: float = 2.0     # full side (no center) — '100S' in catalog

BASS_MONO_FREQ_MIN_HZ: float = 50.0    # catalog real min
BASS_MONO_FREQ_MAX_HZ: float = 500.0   # catalog real max


@dataclass(frozen=True)
class SpatialMove:
    """One spatial / stereo move on a track.

    Phase 4.5 scope : 7 move types (pan / width / mono / bass_mono /
    phase_flip / balance / ms_balance). Tier B (spatial-configurator,
    future) writes Mixer.Pan OR StereoGain.* params per move_type.

    Field requirements per move_type (parser-enforced) :
    - pan        : ``pan`` in [-1, 1] required ; other value-fields None
    - width      : ``stereo_width`` in [0, 4] \\ {1.0} required ; others None
    - mono       : (no value field — the move_type itself signals Mono=True) ;
                   all other value-fields must be None
    - bass_mono  : ``bass_mono_freq_hz`` in [50, 500] required ; others None
    - phase_flip : ``phase_channel`` in {"L", "R"} required ; others None
    - balance    : ``balance`` in [-1, 1] \\ {0.0} required ; others None
    - ms_balance : ``mid_side_balance`` in [0, 2] \\ {1.0} required ; others None
    """

    track: str                                  # must match TrackInfo.name
    move_type: str                              # in VALID_SPATIAL_MOVE_TYPES

    # Per-move-type value fields (Optional ; cross-field enforced)
    pan: Optional[float] = None                 # for "pan"
    stereo_width: Optional[float] = None        # for "width"
    bass_mono_freq_hz: Optional[float] = None   # for "bass_mono"
    phase_channel: Optional[str] = None         # for "phase_flip" — "L" or "R"
    balance: Optional[float] = None             # for "balance"
    mid_side_balance: Optional[float] = None    # for "ms_balance"

    chain_position: str = "default"             # in VALID_SPATIAL_CHAIN_POSITIONS
    rationale: str = ""
    inspired_by: tuple[MixCitation, ...] = ()


@dataclass(frozen=True)
class SpatialDecision:
    """All spatial / stereo decisions for the project.

    `moves` is the list of spatial adjustments (one per track per move_type).
    Multiple moves on the same track must have distinct ``move_type``
    (cross-field enforced) — re-emitting same move_type with different
    values = duplicate ambiguity.

    Idempotence note : only ``move_type="pan"`` is FULLY idempotent
    (verified via ``report.tracks[track].pan``). Other move types have
    PARTIAL idempotence via ``track.devices`` StereoGain presence
    detection — the agent cannot read StereoGain param state today
    (TrackInfo.devices exposes names only, not params).
    Phase 4.5.x extension may add ``TrackInfo.stereo_state`` typed.
    """

    moves: tuple[SpatialMove, ...] = ()


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
    routing: Optional[MixDecision[RoutingDecision]] = None
    eq_corrective: Optional[MixDecision[EQCorrectiveDecision]] = None
    dynamics_corrective: Optional[MixDecision[DynamicsCorrectiveDecision]] = None
    stereo_spatial: Optional[MixDecision[SpatialDecision]] = None
    # Future lanes (added with their producing agents):
    # eq_creative: Optional[MixDecision[EQCreativeDecision]] = None
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
    # CDE + Freq Conflicts absorption (Phase 4.2.8)
    "VALID_CDE_SEVERITIES",
    "KNOWN_CDE_ISSUE_TYPES",
    "VALID_CDE_CONFIDENCES",
    "VALID_CDE_APPLICATION_STATUSES",
    "CDEMeasurement",
    "CDETFPContext",
    "CDECorrectionRecipe",
    "CDEDiagnostic",
    "FreqConflictsMetadata",
    "BandConflict",
    # EQ corrective lane (Phase 4.2)
    "VALID_EQ_BAND_TYPES",
    "VALID_EQ_INTENTS",
    "VALID_FILTER_SLOPES_DB_PER_OCT",
    "VALID_CHAIN_POSITIONS",
    "DEPRECATED_CHAIN_POSITIONS_REDIRECT",
    "VALID_PROCESSING_MODES",
    "EQ_Q_MIN",
    "EQ_Q_MAX",
    "EQ_FREQ_MIN_HZ",
    "EQ_FREQ_MAX_HZ",
    "EQ_GAIN_MIN_DB",
    "EQ_GAIN_MAX_DB",
    "EQAutomationPoint",
    "EQBandCorrection",
    "EQCorrectiveDecision",
    # Dynamics corrective lane (Phase 4.3)
    "VALID_DYNAMICS_TYPES",
    "VALID_DYNAMICS_DEVICES",
    "VALID_SIDECHAIN_MODES",
    "VALID_DYNAMICS_CHAIN_POSITIONS",
    "DYN_THRESHOLD_MIN_DB",
    "DYN_THRESHOLD_MAX_DB",
    "DYN_RATIO_MIN",
    "DYN_RATIO_MAX",
    "DYN_ATTACK_MIN_MS",
    "DYN_ATTACK_MAX_MS",
    "DYN_RELEASE_MIN_MS",
    "DYN_RELEASE_MAX_MS",
    "DYN_MAKEUP_MIN_DB",
    "DYN_MAKEUP_MAX_DB",
    "DYN_KNEE_MIN_DB",
    "DYN_KNEE_MAX_DB",
    "DYN_DRY_WET_MIN",
    "DYN_DRY_WET_MAX",
    "DYN_SIDECHAIN_DEPTH_MIN_DB",
    "DYN_SIDECHAIN_DEPTH_MAX_DB",
    "DYN_CEILING_MIN_DB",
    "DYN_CEILING_MAX_DB",
    "DYN_TRANSIENTS_MIN",
    "DYN_TRANSIENTS_MAX",
    "DynamicsAutomationPoint",
    "SidechainConfig",
    "DynamicsCorrection",
    "DynamicsCorrectiveDecision",
    # Routing & sidechain lane (Phase 4.4)
    "VALID_ROUTING_FIX_TYPES",
    "STALE_SIDECHAIN_REGEX",
    "SidechainRepair",
    "RoutingDecision",
    # Stereo & spatial lane (Phase 4.5)
    "VALID_SPATIAL_MOVE_TYPES",
    "VALID_SPATIAL_CHAIN_POSITIONS",
    "VALID_PHASE_CHANNELS",
    "PAN_MIN",
    "PAN_MAX",
    "STEREO_WIDTH_MIN",
    "STEREO_WIDTH_NEUTRAL",
    "STEREO_WIDTH_MAX",
    "BALANCE_MIN",
    "BALANCE_NEUTRAL",
    "BALANCE_MAX",
    "MS_BALANCE_MIN",
    "MS_BALANCE_NEUTRAL",
    "MS_BALANCE_MAX",
    "BASS_MONO_FREQ_MIN_HZ",
    "BASS_MONO_FREQ_MAX_HZ",
    "SpatialMove",
    "SpatialDecision",
]
