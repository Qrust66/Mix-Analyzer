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
    """One track's identity, routing, and chain state.

    Phase 4.7 extension : optional ``audio_metrics`` field exposes per-track
    audio character (loudness/spectrum/temporal/stereo/musical) computed
    by mix_analyzer.py:analyze_track. mix-diagnostician populates this
    via lazy absorption (only for tracks consumed by downstream Tier A
    agents — anomalies, CDE diagnostics, brief mentions).
    """

    name: str
    track_type: str  # "Audio" | "MIDI" | "Group" | "Return" | "Master"
    parent_bus: Optional[str]
    color: str  # hex or Ableton index
    devices: tuple[str, ...]  # device names in chain order
    volume_db: float  # converted from XML logarithmic value
    pan: float  # -1.0 (full L) to +1.0 (full R)
    sidechain_targets: tuple[str, ...]  # tracks this one ducks
    activator: bool  # track-on
    # Phase 4.7 — per-track audio character (Optional ; lazy absorption)
    audio_metrics: Optional["TrackAudioMetrics"] = None


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


# ============================================================================
# Phase 4.7 — Per-track audio metrics + genre context absorption
# ============================================================================
#
# Phase 4.7 layer extension : exposes per-track audio character that
# mix_analyzer.py:analyze_track computes but DiagnosticReport previously
# omitted. Parallel pattern to Phase 4.2.8 (CDE + Freq Conflicts).
#
# Audit Pass 1 findings applied :
# - CANONICAL_BAND_LABELS / CANONICAL_BAND_COUNT match mix_analyzer.py:382-390
#   FREQ_BANDS exactly (7 bands : sub/bass/low_mid/mid/high_mid/presence/air ;
#   not the fictive 6-band split the plan originally used)
# - band_energies as tuple[float] len 7 ordered per CANONICAL_BAND_LABELS
#   (mix-diagnostician converts mix_analyzer dict to ordered tuple)
# - SPECTRAL_PEAKS_MAX = 10 (generous ; mix_analyzer caps internally at 6)
# - is_tonal exposed separately (mirrors analyze_musical structure)
# - onsets_per_second is mix-diagnostician-derived (num_onsets / duration)


# Canonical 7-band frequency split per mix_analyzer.py:382-390 FREQ_BANDS.
# Order is fixed ; index ↔ semantic enforced via this tuple.
CANONICAL_BAND_LABELS: tuple[str, ...] = (
    "sub",        # 20-60 Hz
    "bass",       # 60-250 Hz
    "low_mid",    # 250-500 Hz
    "mid",        # 500-2000 Hz
    "high_mid",   # 2000-4000 Hz
    "presence",   # 4000-8000 Hz
    "air",        # 8000-20000 Hz
)
CANONICAL_BAND_COUNT: int = 7

# Cap to prevent payload bloat ; mix_analyzer.py:543 internally caps at 6.
SPECTRAL_PEAKS_MAX: int = 10

# Genre profiles per mix_analyzer.py:267-274 FAMILY_PROFILES (8 families).
VALID_GENRE_FAMILIES = frozenset({
    "generic", "acoustic", "rock",
    "electronic_soft", "electronic_dance", "electronic_aggressive",
    "urban", "pop",
})
VALID_DENSITY_TOLERANCES = frozenset({"low", "normal", "high", "very_high"})


# Audio-physics range bounds (parser-enforced).
LOUDNESS_DB_MIN: float = -150.0
LOUDNESS_DB_MAX: float = 20.0
LUFS_MIN: float = -100.0
LUFS_MAX: float = 0.0
LRA_MIN: float = 0.0
LRA_MAX: float = 60.0
CREST_FACTOR_MIN: float = 0.0
CREST_FACTOR_MAX: float = 50.0
PLR_PSR_MIN: float = -30.0
PLR_PSR_MAX: float = 30.0
CENTROID_HZ_MIN: float = 0.0
# Phase 4.7.0.1 audit Finding 2 : bumped from 22050 to 24000 to cover
# 48 kHz Nyquist (pro-audio standard sample rate). 22050 was 44.1 kHz Nyquist
# only ; 48 kHz files would have produced legitimate centroid > 22050 rejected.
CENTROID_HZ_MAX: float = 24000.0
SPECTRAL_FLATNESS_MIN: float = 0.0
SPECTRAL_FLATNESS_MAX: float = 1.0
ONSETS_PER_SECOND_MIN: float = 0.0
ONSETS_PER_SECOND_MAX: float = 50.0
TONAL_STRENGTH_MIN: float = 0.0
TONAL_STRENGTH_MAX: float = 1.0
TARGET_LUFS_MIX_MIN: float = -30.0
TARGET_LUFS_MIX_MAX: float = 0.0
TYPICAL_CREST_MIX_MIN: float = 0.0
TYPICAL_CREST_MIX_MAX: float = 30.0


@dataclass(frozen=True)
class SpectralPeak:
    """One peak in per-track spectrum (from analyze_spectrum.peaks).

    Convention : when used in TrackAudioMetrics.spectral_peaks, peaks
    are ordered by magnitude_db DESCENDING (most prominent first ;
    parser enforces this ordering — Phase 4.7 audit Pass 1 Finding 7).
    """
    frequency_hz: float    # in [16, 22050]
    magnitude_db: float    # in [-150, 0]


@dataclass(frozen=True)
class TrackAudioMetrics:
    """Per-track audio metrics from mix_analyzer.py:analyze_track.

    Phase 4.7 absorption layer — typed exposure of per-track audio
    character. Source mapping :
    - Loudness scalars : analyze_loudness (mix_analyzer.py:451)
    - Spectrum scalars : analyze_spectrum (mix_analyzer.py:511)
    - Temporal scalars : analyze_temporal (mix_analyzer.py:579)
    - Stereo scalars  : analyze_stereo (mix_analyzer.py:769)
    - Musical scalars : analyze_musical (mix_analyzer.py:746)

    LAZY ABSORPTION (Phase 4.7 Risk #5 mitigation) : mix-diagnostician
    populates this Optional field only for tracks that downstream Tier A
    agents will consume (typically tracks with anomalies, CDE diagnostics,
    or explicit user brief mention). For projects with N>20 tracks,
    partial population is the norm.

    NaN HANDLING (Risk #9) : mix-diagnostician MUST normalize NaN values
    to null before emit. Parser rejects NaN explicitly — these always
    indicate a measurement edge case (silent track, mono-summed-stereo)
    that the agent should treat as "not measured" rather than "value 0".

    CROSS-FIELD is_stereo COHERENCE (Risk #8 — parser-enforced) :
    - is_stereo=False : correlation, width_overall, width_per_band MUST be None
    - is_stereo=True  : correlation + width_overall mandatory ;
                        width_per_band optional
    """

    # === Loudness scalars (analyze_loudness — 9 fields, mix_analyzer.py:451) ===
    peak_db: float                   # in [LOUDNESS_DB_MIN, LOUDNESS_DB_MAX]
    true_peak_db: float
    rms_db: float
    lufs_integrated: float           # in [LUFS_MIN, LUFS_MAX]
    lufs_short_term_max: float
    lra: float                       # in [LRA_MIN, LRA_MAX] — per-track Loudness Range
    crest_factor: float              # in [CREST_FACTOR_MIN, CREST_FACTOR_MAX]
    plr: float                       # in [PLR_PSR_MIN, PLR_PSR_MAX] — Peak-to-Loudness
    psr: float                       # in [PLR_PSR_MIN, PLR_PSR_MAX] — Peak-to-Short-Term-Loudness

    # === Spectrum scalars + bounded tuples (analyze_spectrum, mix_analyzer.py:511) ===
    dominant_band: str                            # in CANONICAL_BAND_LABELS (7 values)
    centroid_hz: float                            # mix_analyzer field name : 'centroid'
    rolloff_hz: float                             # mix_analyzer field name : 'rolloff'
    spectral_flatness: float                      # mix_analyzer field name : 'flatness'
    band_energies: tuple[float, ...]              # len == CANONICAL_BAND_COUNT (7)
                                                  # ordered per CANONICAL_BAND_LABELS index
    spectral_peaks: tuple[SpectralPeak, ...]      # len ≤ SPECTRAL_PEAKS_MAX, magnitude descending

    # === Temporal scalars (analyze_temporal, mix_analyzer.py:579) ===
    num_onsets: int                  # in [0, ∞)
    onsets_per_second: float         # mix-diagnostician derived (num_onsets / duration_seconds)

    # === Stereo scalars (analyze_stereo, mix_analyzer.py:769) ===
    is_stereo: bool
    correlation: Optional[float] = None           # in [-1, 1] when is_stereo=True
    width_overall: Optional[float] = None         # in [0, 1] when is_stereo=True
    width_per_band: Optional[tuple[float, ...]] = None  # len == 7 when set

    # === Musical scalars (analyze_musical, mix_analyzer.py:746) ===
    is_tonal: bool = False                        # mix_analyzer 'is_tonal' field
    dominant_note: Optional[str] = None           # e.g., "C", "F#" or None if non-tonal
    tonal_strength: float = 0.0                   # in [0, 1]


@dataclass(frozen=True)
class GenreContext:
    """Project-level genre context from mix_analyzer.py:267 FAMILY_PROFILES.

    Project-level (one genre per project) ; lives on DiagnosticReport,
    not TrackInfo. Auto-modulates downstream Tier A decisions when
    populated (e.g., dynamics ratio×, stereo width tendency, mastering
    target_lufs).
    """
    family: str                       # in VALID_GENRE_FAMILIES (8 values exact)
    target_lufs_mix: float            # in [TARGET_LUFS_MIX_MIN, TARGET_LUFS_MIX_MAX]
    typical_crest_mix: float          # in [TYPICAL_CREST_MIX_MIN, TYPICAL_CREST_MIX_MAX]
    density_tolerance: str            # in VALID_DENSITY_TOLERANCES


# ============================================================================
# Analysis configuration — Phase F10h (v2.8.0)
# ============================================================================
#
# Mirrors the 14 key/value pairs of the hidden ``_analysis_config`` Excel
# sheet produced by mix_analyzer.py:_build_analysis_config_sheet (line
# 3392+). Tier A agents read this sheet to know which preset generated
# the report and adapt their decisions / rationale to the actual
# spectral resolution achieved.
#
# Optional on DiagnosticReport — pre-F10h reports without the sheet
# resolve to None ; downstream consumers MUST treat None as "v2.7.0
# baseline = standard preset" for backward compatibility.

VALID_PRESET_NAMES: frozenset[str] = frozenset({
    "economy", "standard", "fine", "ultra", "maximum",
})


@dataclass(frozen=True)
class AnalysisConfig:
    """Analysis configuration metadata read from the ``_analysis_config``
    sheet (Phase F10h). 14 fields mirror the sheet's key/value pairs
    1:1, in the same order as ``mix_analyzer.py:3398`` for predictable
    cross-referencing.

    Methods ``cqt_frames_per_beat_at(bpm)`` and ``stft_delta_freq_hz_at(sr)``
    rescale the stored ``_at_128bpm`` / ``_at_44k`` reference values to
    arbitrary tempo / sample rate. Single source of truth = the stored
    fields ; methods are pure derivations.
    """

    preset_name: str                          # in VALID_PRESET_NAMES
    stft_n_fft: int                           # > 0
    stft_hop_samples: int                     # > 0
    stft_hop_ms_at_44k: float                 # > 0
    stft_delta_freq_hz_at_44k: float          # > 0
    cqt_target_fps: int                       # > 0
    cqt_bins_per_octave: int                  # > 0
    cqt_n_bins: int                           # > 0
    cqt_frames_per_beat_at_128bpm: float      # > 0
    sample_rate: int                          # > 0
    peak_threshold_db: float                  # in [-80, -40]
    is_shareable_version: bool                # True for filtered SHAREABLE report
    mix_analyzer_version: str                 # e.g. "v2.8.0"
    generated_at: str                         # ISO 8601 timespec=seconds

    def cqt_frames_per_beat_at(self, bpm: float) -> float:
        """Rescale the stored at-128-BPM frames/beat to arbitrary BPM.

        At 128 BPM, one beat lasts 60/128 = 0.46875 s and contains
        ``cqt_target_fps × 0.46875`` frames. At any other tempo, the
        ratio scales as 128/bpm. Used by band-tracking-decider to know
        the realistic upper bound of its frame_times_sec resolution.
        """
        if bpm <= 0:
            raise ValueError(f"bpm must be positive, got {bpm}")
        return self.cqt_frames_per_beat_at_128bpm * (128.0 / bpm)

    def stft_delta_freq_hz_at(self, sample_rate: int) -> float:
        """Rescale the stored at-44.1k delta-freq to arbitrary sample rate.

        delta_freq = sr / n_fft ; the stored at_44k value assumes
        sr=44100. For any other sr, ``stored × (sr/44100)``. Used by
        eq-corrective for narrow-band cut precision sanity checks.
        """
        if sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {sample_rate}")
        return self.stft_delta_freq_hz_at_44k * (sample_rate / 44100.0)


# ============================================================================
# Diagnostic lane DiagnosticReport — Phase 4.1 + extensions Phase 4.2.8 + 4.7
# ============================================================================


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
    # Phase 4.7 : project-level genre context
    genre_context: Optional[GenreContext] = None    # FAMILY_PROFILES typed
    # Phase F10h (v2.8.0) : analysis configuration metadata from
    # ``_analysis_config`` Excel sheet. None = pre-F10h report ; treat as
    # the v2.7.0 baseline (= ``standard`` preset) for backward compat.
    analysis_config: Optional[AnalysisConfig] = None

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


# ============================================================================
# Chain build lane — Phase 4.6
# ============================================================================
#
# Tier A schema for SECOND-ORDER reconciliation : reads filled MixBlueprint
# Tier A slots (eq_corrective + dynamics_corrective + stereo_spatial +
# routing) and produces an absolute per-track device chain order plus
# consumption refs. Tier B (per-device configurators : eq8-configurator,
# dynamics-configurator, etc.) reads these plans to know which device
# instance materializes which Tier A decision and at what slot.
#
# Phase 4.6 partial scope (rule-with-consumer) :
# - Reads available Tier A : eq_corrective, dynamics_corrective,
#   stereo_spatial, routing (all built Phase 4.2-4.5)
# - Skips Tier A not yet built : eq_creative, saturation_color
#   (when these arrive Phase 4.7+, chain-builder extends to consume them)
#
# Audit findings applied (cf. Pass 1 + Pass 2 audits) :
# - is_preexisting: bool flag replaces sentinel string "preexisting"
#   (Pass 1 Finding B) — clean separation between "device the agent
#   inserts" (validated against VALID_CHAIN_DEVICES) and "device already
#   present in track.devices" (any name allowed for preservation)
# - VALID_CHAIN_DEVICES restricted to 9 mapped Ableton devices ; preexisting
#   slots bypass this check (Pass 1 Finding C — real .als chains contain
#   Reverb/Tuner/3rd-party VSTs not in the mapping catalog)
# - Limiter terminal placement : enforced as "max position within plan",
#   not hardcoded "slot 10" (Pass 2 Finding 3)
# - Hard semantic rules > brief override > canonical mapping > lane
#   priority (Pass 2 Finding 2 hierarchy)
# - move_type="pan" skipped (Mixer.Pan, no chain device — Pass 2 Finding 6)
# - Preservation transversal across all scenarios (Pass 2 Finding 1)


VALID_CHAIN_DEVICES = frozenset({
    # 9 mapped Ableton devices (Phase 4.6 scope) — used when is_preexisting=False
    "Eq8",
    "Compressor2",
    "GlueCompressor",
    "Limiter",
    "Gate",
    "DrumBuss",
    "Saturator",
    "AutoFilter2",
    "StereoGain",
})

VALID_CONSUMES_LANES = frozenset({
    "eq_corrective",
    "dynamics_corrective",
    "stereo_spatial",
    "routing",          # for Compressor2 sidechain wiring referencing routing.repairs
})

CHAIN_MAX_POSITION: int = 31
EQ8_MAX_BANDS_PER_INSTANCE: int = 8


@dataclass(frozen=True)
class ChainSlot:
    """One device slot in a track's absolute chain order.

    Per-slot validation conditional on ``is_preexisting`` :

    - ``is_preexisting=False`` (chain-builder inserts a NEW device) :
      ``device`` must be in VALID_CHAIN_DEVICES, ``consumes_lane`` must
      be in VALID_CONSUMES_LANES, ``consumes_indices`` must be non-empty.
    - ``is_preexisting=True`` (preserves a device already in
      ``track.devices``) : ``device`` is free-form (may be Reverb,
      Tuner, 3rd-party VST3, etc. — any string name from the .als),
      ``consumes_lane`` must be None, ``consumes_indices`` must be empty.

    Multiple instances of the same device on a track (e.g., 2 Eq8 cascaded
    when bands > 8 OR processing_modes vary) are distinguished by
    ``instance`` (0-indexed).
    """

    position: int                              # 0-indexed absolute slot
    device: str                                # see is_preexisting validation rule
    is_preexisting: bool = False
    instance: int = 0                          # 0-indexed for cascade
    consumes_lane: Optional[str] = None        # None when is_preexisting=True
    consumes_indices: tuple[int, ...] = ()     # empty when is_preexisting=True
    purpose: str = ""                          # short descriptor (e.g., "corrective_eq")


@dataclass(frozen=True)
class TrackChainPlan:
    """Ordered chain plan for one track.

    Slots must have strictly monotone-increasing ``position`` values.
    Limiter device (when present) MUST be at the maximum position within
    this plan (terminal placement enforced, but absolute slot number
    varies per track chain length).

    ``cross_lane_notes`` documents potential composition effects when
    Tier A decisions interact in non-trivial ways (e.g., EQ
    processing_mode="mid" + spatial ms_balance — composition, not conflict).
    chain-builder DOCUMENTS, does NOT resolve.
    """

    track: str                                  # must match TrackInfo.name
    slots: tuple[ChainSlot, ...]                # position strictly ascending
    rationale: str = ""                          # depth-light ≥ 50 chars
    inspired_by: tuple[MixCitation, ...] = ()    # ≥ 1 cite
    cross_lane_notes: tuple[str, ...] = ()       # composition awareness


@dataclass(frozen=True)
class ChainBuildDecision:
    """All chain plans for the project.

    `plans` is the list of per-track ordered chain plans. Each track
    appears at most once (duplicate-key check).
    """

    plans: tuple[TrackChainPlan, ...] = ()


# ============================================================================
# Automation lane — Phase 4.8 (corrective + mastering scope only)
# ============================================================================
#
# Tier A schema for SECTION-DRIVEN dynamic automation envelopes that
# Tier A correctives don't naturally produce :
# - Corrective per-section : converts static Tier A param to dynamic
#   envelope when per-section signal variation justifies it (e.g.,
#   sibilance only in chorus sections, dynamics range varies per section)
# - Mastering master bus : envelopes on master bus that no Tier A
#   handles directly (Limiter ceiling per-section, master EQ tilt,
#   master stereo width)
#
# Phase 4.8 OOS (rule-with-consumer) :
# - Creative envelopes (riser, drop buildup, fx swell, filter sweep,
#   pan automation, send level automation) — separate creative-automation
#   agent will be built later
# - Reverb tail automation (FX scope, future fx-decider)
#
# Source : Sections Timeline (Feature 3.5+) — section indices used
# (cohérent avec EQBandCorrection.sections / DynamicsCorrection.sections
# patterns from Phase 4.2/4.3).


VALID_AUTOMATION_PURPOSES = frozenset({
    "corrective_per_section",   # Convert static Tier A param to dynamic per-section
    "mastering_master_bus",     # Master bus envelope (Limiter, EQ tilt, etc.)
    # OOS Phase 4.8 (creative scope — future creative-automation agent) :
    # "creative_riser", "creative_drop_buildup", "creative_fx_swell",
    # "creative_pan", "creative_send_level"
})


# Target devices that automation-engineer can address.
# Phase 4.8.3 — extended to cover ALL mapped automatable devices in the
# catalog (was 7 in Phase 4.8 ; now 9 Ableton native + 1 VST3 mastering).
# Trackspacer (VST3 dynamic spectral carving) explicitly OOS — eq-creative
# scope (cf. Phase 4.5.x docs).
VALID_AUTOMATION_TARGET_DEVICES = frozenset({
    # 9 Ableton native mapped devices
    "Eq8", "Compressor2", "GlueCompressor", "Limiter",
    "Gate", "DrumBuss", "StereoGain",
    "AutoFilter2",          # Phase 4.8.3 added — filter cutoff sweeps (corrective LPF resonance hunt)
    "Saturator",            # Phase 4.8.3 added — Drive/Output per-section corrective modulation
    # VST3 mastering plugin
    "SmartLimit",           # Phase 4.8.3 added — alternative to native Limiter for mastering
})


# Sample of common automatable parameter names per device family.
# Phase 4.8.3 — covers ALL automatable devices in VALID_AUTOMATION_TARGET_DEVICES.
# Parser accepts any non-empty string for target_param (validation per-param
# delegated to Tier B automation-writer + device-mapping-oracle).
#
# Eq8 NOTE : the 5 per-band params (Mode, Frequency, Gain, Q, On) work for
# ANY band_type (bell/notch/HPF/LPF/shelves). However :
# - Gain meaningful only for bell/shelf bands (Notch = -inf, HPF/LPF = n/a)
# - Q meaningful for bell/notch (HPF/LPF use slope_db_per_oct enum, not Q)
# - Mode (band_type itself) automatable but unusual ; agent typically sets
#   band_type statically and automates only the active params
# Agent-prompt enforces band_type/param compatibility (parser permissive).
COMMON_AUTOMATION_PARAMS_BY_DEVICE = {
    "Eq8": ("Gain", "Frequency", "Q"),  # the 3 typically automated ; Mode/On rare
    "Compressor2": ("Threshold", "Ratio", "Attack", "Release",
                    "Makeup", "Knee", "DryWet"),
    "GlueCompressor": ("Threshold", "Range", "Makeup", "DryWet"),
    "Limiter": ("Ceiling", "Gain", "Release"),
    "Gate": ("Threshold", "Return", "Attack", "Hold", "Release"),
    "DrumBuss": ("Drive", "Transients", "DampFreq", "BoostFreq", "Output"),
    "StereoGain": ("StereoWidth", "Balance", "MidSideBalance",
                    "BassMonoFrequency", "Gain"),
    # Phase 4.8.3 additions
    "AutoFilter2": ("Filter_Frequency", "Filter_Resonance", "Filter_Drive",
                    "Filter_Morph", "Envelope_Amount", "Lfo_Amount",
                    "Output", "DryWet"),
    "Saturator": ("PreDrive", "PostDrive", "DryWet", "Type"),
    "SmartLimit": ("General_inputGain", "General_outputGain",
                    "General_limiterThreshold", "General_attack",
                    "General_release", "General_saturation"),
}


# Master track name reserved (used when purpose=mastering_master_bus).
# Cohérent avec Ableton convention "Master" track in LiveSet/MasterTrack.
MASTER_TRACK_NAME: str = "Master"

AUTOMATION_MIN_POINTS: int = 3                 # Min envelope length (parallel to EQ/Dynamics envelopes)
AUTOMATION_MAX_POINTS: int = 256                # Sanity cap on envelope size
AUTOMATION_MAX_TIME_BEATS: float = 39996.0      # Cap = 9999 bars × 4 beats/bar (covers ~10h song @ 4/4 120 BPM)


@dataclass(frozen=True)
class AutomationPoint:
    """One time-indexed automation point in BEATS (Ableton native unit).

    Phase 4.8.2 extension : `time_beats: float` replaces the original
    Phase 4.8 `bar: int` to support sub-bar resolution that aligns with
    mix_analyzer.py's frame-level analysis precision (analyze_temporal
    rms_envelope ≈ 11.6 ms ; analyze_multiband_timeline 200 segments
    per song).

    Conventions :
    - `time_beats` is project-absolute position in BEATS (Ableton's
      native XML Time unit ; <FloatEvent Time="X.XX"/>).
    - In 4/4 time signature : 1 bar = 4 beats. So bar 16 = 64.0 beats.
    - In 8/8 time signature : 1 bar = 8 beats. So bar 16 = 128.0 beats.
    - Sub-beat precision allowed : 0.25 = sixteenth-note within beat 0.
    - For sample-accurate alignment with mix_analyzer time_seconds : use
      formula `time_beats = (time_seconds / 60) × tempo_bpm` where
      tempo_bpm is from `analyze_tempo_dynamic` (project-level constant).

    `value` is the parameter value at this point — meaning depends on
    the target_param (dB for Gain/Threshold, Hz for Frequency,
    dimensionless for Q, seconds/ms for Attack/Release, 0..1 for DryWet).

    Tier B automation-writer writes <FloatEvent Time="time_beats"
    Value="value"/> directly — no unit conversion needed (Ableton-native).
    """

    time_beats: float
    value: float


@dataclass(frozen=True)
class AutomationEnvelope:
    """One automation envelope on one parameter of one device on one track.

    Phase 4.8 scope :
    - ``purpose="corrective_per_section"`` : converts a Tier A static
      decision to dynamic. ``target_track`` matches a TrackInfo.name ;
      typically references a device that chain-builder placed.
    - ``purpose="mastering_master_bus"`` : ``target_track`` MUST be
      ``"Master"`` ; addresses master bus device parameters that no
      Tier A handles (Limiter ceiling envelope, master EQ tilt, etc.).

    For Eq8 envelopes, ``target_band_index`` (0-7) identifies which
    band of the Eq8 instance is being automated. None for non-Eq8
    devices or when targeting global Eq8 params (Mode_global, On).

    For cascaded device instances (e.g., 2 Eq8 instances on same track
    when 8-band budget overflowed), ``target_device_instance`` (0-indexed)
    identifies which instance.
    """

    purpose: str                                # in VALID_AUTOMATION_PURPOSES
    target_track: str                           # TrackInfo.name OR "Master"
    target_device: str                          # in VALID_AUTOMATION_TARGET_DEVICES
    target_param: str                           # device parameter name (e.g., "Gain", "Threshold")
    target_device_instance: int = 0             # 0-indexed for cascaded instances
    target_band_index: Optional[int] = None     # for Eq8 only ; in [0, 7]

    points: tuple[AutomationPoint, ...] = ()    # ≥ 3 ; bar-ascending strict ; no duplicates
    sections: tuple[int, ...] = ()              # Sections Timeline indices ; required for corrective_per_section

    rationale: str = ""                         # ≥ 50 chars (depth-light)
    inspired_by: tuple[MixCitation, ...] = ()    # ≥ 1 cite


# ============================================================================
# BandTrack — Phase 4.17 high-level Eq8 band-tracking primitive
# ============================================================================
#
# A BandTrack is a HIGH-LEVEL automation directive that the Tier B
# automation-writer EXPANDS into 1-3 AutomationEnvelopes (Freq + Gain + Q,
# minus envelopes that would target gain-inoperative modes).
#
# Use cases (the 8 Eq8 modes) :
# - "bell" cut    : follow a peak/resonance ; freq glides, gain dips when peak loud
# - "bell" boost  : follow a fundamental ; gain lifts when source weak (presence)
# - "lowshelf" / "highshelf" : track the shelf transition + gain
# - "lowcut_*" / "highcut_*" : automate the cutoff frequency (filter sweep)
# - "notch" : silently coerced to "bell" Mode 3 with deep gain
#   (Eq8 Mode 4 has gain_inoperative_modes — known mitigation)
#
# Each BandTrack consumes exactly ONE Eq8 band. Tier A chain-builder is
# responsible for cascading Eq8 instances when n_band_tracks_for_track > 8.

VALID_BAND_MODES = frozenset({
    "lowcut_48",   # Mode 0 — gain inop ; envelope Freq + Q (resonance)
    "lowcut_12",   # Mode 1 — gain inop ; envelope Freq + Q
    "lowshelf",    # Mode 2 — envelope Freq + Gain + Q (slope)
    "bell",        # Mode 3 — envelope Freq + Gain + Q (the workhorse)
    "notch",       # Mode 4 — coerced to Mode 3 Bell with deep Gain (writer warns)
    "highshelf",   # Mode 5 — envelope Freq + Gain + Q
    "highcut_12",  # Mode 6 — gain inop ; envelope Freq + Q
    "highcut_48",  # Mode 7 — gain inop ; envelope Freq + Q
})

# Modes where Gain is inoperative in Eq8 hardware (gain envelope skipped by writer)
BAND_MODES_GAIN_INOPERATIVE = frozenset({
    "lowcut_48", "lowcut_12", "highcut_12", "highcut_48",
})

VALID_BAND_TRACK_PURPOSES = frozenset({
    "follow_peak",        # cut a moving resonance/peak
    "follow_dip",         # boost a moving valley (fill the gap)
    "boost_resonance",    # supportive boost on a moving fundamental
    "shelf_track",        # animate a shelf gain/slope
    "cutoff_track",       # animate a filter cutoff
    "sweep_filter",       # creative-feeling sweep (corrective scope only Phase 4.17)
})

VALID_INTERPOLATIONS = frozenset({
    "linear",       # straight line between consecutive points
    "parabolic",    # 3-point parabolic refinement around local max ; sub-bin freq
    "cubic",        # CatmullRom — smooth glides ; no monotonic guarantee
})

BAND_TRACK_MIN_FRAMES: int = 3
BAND_TRACK_MAX_FRAMES: int = 24000   # 20fps × 20 minutes (very long song budget)
BAND_TRACK_MAX_SUB_FRAME_FACTOR: int = 8


@dataclass(frozen=True)
class BandTrack:
    """One Eq8 band tracked dynamically across time.

    Phase 4.17 — translated by Tier B automation-writer into 1-3 AutomationEnvelopes
    (Freq + Gain + Q, minus envelopes targeting gain-inoperative modes).

    Time series MUST all share the same length n_frames :
    - frame_times_sec : absolute project time per frame (seconds)
    - freqs_hz : freq target per frame (Hz, in [10, 22050])
    - gains_db : gain target per frame (dB) ; None when band_mode is gain-inop
                 OR when caller wants static gain at the current band default
    - q_values : Q target per frame ; None = static Q (use q_static)
    - source_amps_db : source signal amplitude (dBFS) ; OPTIONAL — when present,
                       writer can derive gains_db proportionally
                       (gain ∝ (amp - threshold_db) / -threshold_db × gain_max_db)

    Sub-frame interpolation : when sub_frame_factor > 1, the writer densifies
    each pair of adjacent frames into k points using `interpolation` mode.
    Parabolic interp uses 3-point centered window and yields sub-bin freq accuracy.
    """

    target_track: str
    target_eq8_instance: int                    # 0-indexed for cascade
    target_band_index: int                      # 0-7
    band_mode: str                              # in VALID_BAND_MODES
    purpose: str                                # in VALID_BAND_TRACK_PURPOSES

    frame_times_sec: tuple[float, ...]
    freqs_hz: tuple[float, ...]
    gains_db: Optional[tuple[float, ...]] = None
    q_values: Optional[tuple[float, ...]] = None
    source_amps_db: Optional[tuple[float, ...]] = None

    q_static: float = 8.0                       # used when q_values is None
    gain_max_db: float = 6.0                    # |gain| cap (positive for boosts)
    threshold_db: float = -40.0                 # source_amp floor for prop. gain
    interpolation: str = "parabolic"
    sub_frame_factor: int = 1

    rationale: str = ""
    inspired_by: tuple[MixCitation, ...] = ()


@dataclass(frozen=True)
class AutomationDecision:
    """All automation decisions for the project.

    Two coexisting collections (Phase 4.17) :

    - `envelopes` : param-level envelopes. Multiple envelopes on the same
      (track, device, instance, param, band_index) tuple are rejected
      (parser duplicate check).
    - `band_tracks` : high-level Eq8 band tracking directives expanded by
      Tier B into 1-3 envelopes per BandTrack. Multiple BandTracks on the
      same (track, eq8_instance, band_index) are rejected (parser
      duplicate check) — would target the same Eq8 band with conflicting
      time series.
    """

    envelopes: tuple[AutomationEnvelope, ...] = ()
    band_tracks: tuple[BandTrack, ...] = ()


# ============================================================================
# Mastering lane — Phase 4.9
# ============================================================================
#
# Tier A schema for master-bus-only decisions : LUFS targeting, true peak
# ceiling, LRA control, master corrective/tonal EQ, glue compression,
# stereo enhancement, saturation color, sub-bus glue.
#
# Static-only by design — envelope overlay (per-section ramps, intro/outro
# fades) handled by automation-engineer Phase 4.8 via
# AutomationEnvelope(purpose="mastering_master_bus", target_track="Master").
# This avoids capability duplication and keeps Tier A static / Tier A
# automation cleanly separated.
#
# Out-of-scope Phase 4.9 (rule-with-consumer) :
# - MultibandDynamics device (not yet mapped in VALID_DYNAMICS_DEVICES) →
#   "multiband_band" type deferred Phase 4.9.X
# - Reference matching workflow (curve/RMS match) — agent prompt skeleton
#   only ; future schema extension if usage justifies
# - Dither (export config, not chain device — out-of-band)


# Master move types — discriminator for MasterMove dataclass.
VALID_MASTER_MOVE_TYPES = frozenset({
    "limiter_target",       # MASTER-A, MASTER-B (Limiter / SmartLimit terminal)
    "glue_compression",     # MASTER-C, MASTER-G (GlueCompressor / Compressor2 master glue)
    "master_eq_band",       # MASTER-D (Eq8 master corrective + tonal)
    "stereo_enhance",       # MASTER-F (Utility / StereoGain master width)
    "saturation_color",     # MASTER-H (Saturator subtle harmonic excitement)
    "bus_glue",             # MASTER-I (sub-bus GlueCompressor — drum bus, vocal bus)
    # Phase 4.9.X future :
    # "multiband_band",
})


# Devices acceptables par type. Cross-field parser enforces type → device.
MASTER_DEVICES_BY_TYPE: dict[str, frozenset[str]] = {
    "limiter_target": frozenset({"Limiter", "SmartLimit"}),
    "glue_compression": frozenset({"GlueCompressor", "Compressor2"}),
    "master_eq_band": frozenset({"Eq8"}),
    "stereo_enhance": frozenset({"Utility", "StereoGain"}),
    "saturation_color": frozenset({"Saturator"}),
    "bus_glue": frozenset({"GlueCompressor", "Compressor2"}),
}


# Chain positions valides côté master bus.
VALID_MASTER_CHAIN_POSITIONS = frozenset({
    "master_corrective",    # 1er Eq8 master — subtractive cleanup
    "master_tonal",         # 2e Eq8 master (rare) — additive tilt
    "master_glue",          # GlueCompressor / Compressor2 master
    "master_color",         # Saturator master
    "master_stereo",        # Utility / StereoGain master
    "master_limiter",       # Limiter / SmartLimit terminal
    "bus_glue",             # Sub-bus glue (NOT master)
    "default",              # Tier B picks based on chain content
})


# Cross-field : type → required chain_position (when not "default").
MASTER_CHAIN_POSITION_BY_TYPE: dict[str, frozenset[str]] = {
    "limiter_target": frozenset({"master_limiter", "default"}),
    "glue_compression": frozenset({"master_glue", "default"}),
    "master_eq_band": frozenset({"master_corrective", "master_tonal", "default"}),
    "stereo_enhance": frozenset({"master_stereo", "default"}),
    "saturation_color": frozenset({"master_color", "default"}),
    "bus_glue": frozenset({"bus_glue", "default"}),
}


# Saturation type discriminator.
VALID_SATURATION_TYPES = frozenset({
    "analog_clip",          # Hard analog clipping curve
    "soft_sine",            # Sine waveshaping
    "digital_clip",         # Hard digital clip
    "tape",                 # Tape saturation simulation
    "tube",                 # Tube/valve simulation
})


# Master-scope value bounds (parser-enforced).
MASTER_LUFS_MIN: float = -23.0          # LUFS-I min for mastering target (very quiet)
MASTER_LUFS_MAX: float = -5.0           # LUFS-I max (very loud, club-aggressive)
MASTER_CEILING_MIN_DBTP: float = -3.0   # Conservative vinyl ceiling
MASTER_CEILING_MAX_DBTP: float = -0.1   # Streaming standard upper limit (NEVER above)
MASTER_GLUE_RATIO_MIN: float = 1.0      # 1:1 = no compression (legal but caught by cross-field)
MASTER_GLUE_RATIO_MAX: float = 4.0      # > 4 = creative scope (escalate)
MASTER_GLUE_GR_TARGET_MIN_DB: float = 0.0
MASTER_GLUE_GR_TARGET_MAX_DB: float = 6.0
MASTER_EQ_GAIN_MIN_DB: float = -3.0     # Master EQ gentle range (cohérent agent prompt)
MASTER_EQ_GAIN_MAX_DB: float = 3.0      # > 3 = mix problem ; escalate to eq-corrective
MASTER_SATURATION_DRIVE_MIN_PCT: float = 0.5    # > 0 (cross-field) ; au moins 0.5%
MASTER_SATURATION_DRIVE_MAX_PCT: float = 25.0   # > 25 = creative scope (escalate)
MASTER_STEREO_WIDTH_MIN: float = 0.5    # Subtle narrow
MASTER_STEREO_WIDTH_MAX: float = 1.5    # Subtle widen ; > 1.5 = creative
MASTER_BASS_MONO_FREQ_MIN_HZ: float = 50.0
MASTER_BASS_MONO_FREQ_MAX_HZ: float = 500.0


@dataclass(frozen=True)
class MasterMove:
    """One master-bus or sub-bus mastering move (static, no envelopes).

    Discriminator-based : `type` field selects which subset of fields
    applies. Cross-field parser checks enforce coherence.

    Phase 4.9 : envelopes are NOT carried here — automation-engineer
    Phase 4.8 handles temporal overlay via AutomationEnvelope with
    purpose='mastering_master_bus'. If a master move needs section-aware
    variation, agent prompt rationale must escalate to automation-engineer.
    """

    # === Discriminator + targeting (always required) ===
    type: str                                       # in VALID_MASTER_MOVE_TYPES
    target_track: str                               # MASTER_TRACK_NAME OR sub-bus name (bus_glue only)
    device: str                                     # in MASTER_DEVICES_BY_TYPE[type]
    chain_position: str                             # in VALID_MASTER_CHAIN_POSITIONS
    rationale: str                                  # ≥ 50 chars (depth-light)
    inspired_by: tuple[MixCitation, ...]            # ≥ 1 cite

    # === limiter_target fields ===
    target_lufs_i: Optional[float] = None           # in [MASTER_LUFS_MIN, MASTER_LUFS_MAX]
    ceiling_dbtp: Optional[float] = None            # in [MASTER_CEILING_MIN_DBTP, MASTER_CEILING_MAX_DBTP]
    lookahead_ms: Optional[float] = None            # in [0.5, 5.0] typical
    gain_drive_db: Optional[float] = None           # Limiter input drive ; agent guidance, Tier B may recompute

    # === glue_compression / bus_glue shared fields ===
    ratio: Optional[float] = None                   # in [MASTER_GLUE_RATIO_MIN, MASTER_GLUE_RATIO_MAX]
    threshold_db: Optional[float] = None            # reuses DYN_THRESHOLD_MIN_DB / MAX_DB
    attack_ms: Optional[float] = None               # reuses DYN_ATTACK_MIN_MS / MAX_MS
    release_ms: Optional[float] = None              # reuses DYN_RELEASE_MIN_MS / MAX_MS
    gr_target_db: Optional[float] = None            # in [MASTER_GLUE_GR_TARGET_MIN_DB, MAX_DB]
    makeup_db: Optional[float] = None               # reuses DYN_MAKEUP_MIN_DB / MAX_DB

    # === master_eq_band fields ===
    band_type: Optional[str] = None                 # in VALID_EQ_BAND_TYPES
    center_hz: Optional[float] = None               # in [EQ_FREQ_MIN_HZ, EQ_FREQ_MAX_HZ]
    q: Optional[float] = None                       # in [EQ_Q_MIN, EQ_Q_MAX]
    gain_db: Optional[float] = None                 # in [MASTER_EQ_GAIN_MIN_DB, MAX_DB] (master cap)
    slope_db_per_oct: Optional[float] = None        # in VALID_FILTER_SLOPES_DB_PER_OCT (HPF/LPF only)
    processing_mode: Optional[str] = None           # in VALID_PROCESSING_MODES (default "stereo")

    # === stereo_enhance fields (at least one required) ===
    width: Optional[float] = None                   # in [MASTER_STEREO_WIDTH_MIN, MAX]
    mid_side_balance: Optional[float] = None        # in [0, 2] ; neutral=1.0 (StereoGain native range)
    bass_mono_freq_hz: Optional[float] = None       # in [MASTER_BASS_MONO_FREQ_MIN_HZ, MAX_HZ]

    # === saturation_color fields ===
    drive_pct: Optional[float] = None               # in [MASTER_SATURATION_DRIVE_MIN_PCT, MAX_PCT]
    saturation_type: Optional[str] = None           # in VALID_SATURATION_TYPES
    dry_wet: Optional[float] = None                 # in [0, 1] ; default 1.0 = full wet
    output_db: Optional[float] = None               # Saturator output trim ; in [-24, 24]


@dataclass(frozen=True)
class MasteringDecision:
    """All mastering decisions for the project (static, master-bus + sub-bus glue).

    Phase 4.9 contract :
    - ≤ 1 limiter_target move (cross-field check)
    - moves[] empty when no master-level signal justifies intervention
      (do-no-harm rule)
    - Envelopes NOT here — handed off to automation-engineer when section
      variation justifies (rationale must escalate explicitly).
    """

    moves: tuple[MasterMove, ...] = ()


@dataclass(frozen=True)
class MixBlueprint:
    """The immutable carrier of all lane decisions for one mix session.

    Like SectionBlueprint on the composition side, but for an existing
    .als rather than a new one. The blueprint describes deltas to apply,
    not absolute state.
    """

    name: str
    diagnostic: Optional[MixDecision[DiagnosticReport]] = None
    routing: Optional[MixDecision[RoutingDecision]] = None
    eq_corrective: Optional[MixDecision[EQCorrectiveDecision]] = None
    dynamics_corrective: Optional[MixDecision[DynamicsCorrectiveDecision]] = None
    stereo_spatial: Optional[MixDecision[SpatialDecision]] = None
    chain: Optional[MixDecision[ChainBuildDecision]] = None
    automation: Optional[MixDecision[AutomationDecision]] = None
    mastering: Optional[MixDecision[MasteringDecision]] = None
    # Future lanes (added with their producing agents):
    # eq_creative: Optional[MixDecision[EQCreativeDecision]] = None
    # saturation_color: Optional[MixDecision[...]] = None

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
    # Chain build lane (Phase 4.6)
    "VALID_CHAIN_DEVICES",
    "VALID_CONSUMES_LANES",
    "CHAIN_MAX_POSITION",
    "EQ8_MAX_BANDS_PER_INSTANCE",
    "ChainSlot",
    "TrackChainPlan",
    "ChainBuildDecision",
    # Per-track audio metrics + genre context absorption (Phase 4.7)
    "CANONICAL_BAND_LABELS",
    "CANONICAL_BAND_COUNT",
    "SPECTRAL_PEAKS_MAX",
    "VALID_GENRE_FAMILIES",
    "VALID_DENSITY_TOLERANCES",
    "LOUDNESS_DB_MIN",
    "LOUDNESS_DB_MAX",
    "LUFS_MIN",
    "LUFS_MAX",
    "LRA_MIN",
    "LRA_MAX",
    "CREST_FACTOR_MIN",
    "CREST_FACTOR_MAX",
    "PLR_PSR_MIN",
    "PLR_PSR_MAX",
    "CENTROID_HZ_MIN",
    "CENTROID_HZ_MAX",
    "SPECTRAL_FLATNESS_MIN",
    "SPECTRAL_FLATNESS_MAX",
    "ONSETS_PER_SECOND_MIN",
    "ONSETS_PER_SECOND_MAX",
    "TONAL_STRENGTH_MIN",
    "TONAL_STRENGTH_MAX",
    "TARGET_LUFS_MIX_MIN",
    "TARGET_LUFS_MIX_MAX",
    "TYPICAL_CREST_MIX_MIN",
    "TYPICAL_CREST_MIX_MAX",
    "SpectralPeak",
    "TrackAudioMetrics",
    "GenreContext",
    # Automation lane (Phase 4.8 — corrective + mastering scope)
    "VALID_AUTOMATION_PURPOSES",
    "VALID_AUTOMATION_TARGET_DEVICES",
    "COMMON_AUTOMATION_PARAMS_BY_DEVICE",
    "MASTER_TRACK_NAME",
    "AUTOMATION_MIN_POINTS",
    "AUTOMATION_MAX_POINTS",
    "AUTOMATION_MAX_TIME_BEATS",
    "AutomationPoint",
    "AutomationEnvelope",
    "AutomationDecision",
    # BandTrack — Phase 4.17 (high-level Eq8 band tracking primitive)
    "VALID_BAND_MODES",
    "BAND_MODES_GAIN_INOPERATIVE",
    "VALID_BAND_TRACK_PURPOSES",
    "VALID_INTERPOLATIONS",
    "BAND_TRACK_MIN_FRAMES",
    "BAND_TRACK_MAX_FRAMES",
    "BAND_TRACK_MAX_SUB_FRAME_FACTOR",
    "BandTrack",
    # Mastering lane (Phase 4.9 — master bus + sub-bus glue, static-only)
    "VALID_MASTER_MOVE_TYPES",
    "MASTER_DEVICES_BY_TYPE",
    "VALID_MASTER_CHAIN_POSITIONS",
    "MASTER_CHAIN_POSITION_BY_TYPE",
    "VALID_SATURATION_TYPES",
    "MASTER_LUFS_MIN",
    "MASTER_LUFS_MAX",
    "MASTER_CEILING_MIN_DBTP",
    "MASTER_CEILING_MAX_DBTP",
    "MASTER_GLUE_RATIO_MIN",
    "MASTER_GLUE_RATIO_MAX",
    "MASTER_GLUE_GR_TARGET_MIN_DB",
    "MASTER_GLUE_GR_TARGET_MAX_DB",
    "MASTER_EQ_GAIN_MIN_DB",
    "MASTER_EQ_GAIN_MAX_DB",
    "MASTER_SATURATION_DRIVE_MIN_PCT",
    "MASTER_SATURATION_DRIVE_MAX_PCT",
    "MASTER_STEREO_WIDTH_MIN",
    "MASTER_STEREO_WIDTH_MAX",
    "MASTER_BASS_MONO_FREQ_MIN_HZ",
    "MASTER_BASS_MONO_FREQ_MAX_HZ",
    "MasterMove",
    "MasteringDecision",
]
