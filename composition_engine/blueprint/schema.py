"""SectionBlueprint schema — the data contract between sphere agents and
the composer.

Design tenets:

1. **Immutability** — every dataclass is `frozen=True`, every collection is a
   tuple. A blueprint is a value, not a mutable bag. Composition becomes a
   pure pipeline of transformations.

2. **Provenance is first-class** — every sphere decision is wrapped in
   `Decision[T]` carrying citations to the JSON references, a short
   rationale, and a confidence score. When you listen to the result and
   say "this rhythm is weird", you can trace exactly which song inspired
   it and why the agent chose it.

3. **Partial-fill friendly** — every sphere field on `SectionBlueprint` is
   `Optional`. An agent fills its sphere; the rest stay None. Cohesion
   rules silently skip when their sphere dependencies are missing. This
   lets us iterate one sphere at a time without breaking the pipeline.

4. **Narrative + structured** — fields use a mix of categorical strings
   ('sparse', 'Aeolian'), quantitative values (bars, dB, BPM), and
   free-form descriptions. The agents that fill these come from prose
   narrative source data, so we don't over-quantify.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


# ============================================================================
# Provenance primitives
# ============================================================================


@dataclass(frozen=True)
class Citation:
    """A single reference back to the song corpus.

    Example:
        Citation(
            song="Nirvana/Heart_Shaped_Box",
            path="composition.harmonic_motion",
            excerpt="Modal Aeolian cycle. Verse uses 4-chord cycle in minor...",
        )
    """

    song: str
    path: str
    excerpt: str


@dataclass(frozen=True)
class Decision(Generic[T]):
    """Wraps a sphere-level value with full provenance.

    `value`        — the actual decision (a sphere dataclass)
    `sphere`       — which sphere produced this ("structure", "harmony", ...)
    `inspired_by`  — citations from the song corpus that informed the choice
    `rationale`    — short LLM-readable explanation (also human-readable)
    `confidence`   — 0.0 (pure guess) to 1.0 (strong corpus evidence)
    """

    value: T
    sphere: str
    inspired_by: tuple[Citation, ...] = ()
    rationale: str = ""
    confidence: float = 1.0


# ============================================================================
# Sphere helper types
# ============================================================================


@dataclass(frozen=True)
class SubSection:
    """An internal subdivision of a section (e.g. a build, a drop, a tag)."""

    name: str
    start_bar: int
    end_bar: int
    role: str = ""  # free-form: "build", "drop", "breath", "tag"


@dataclass(frozen=True)
class LayerSpec:
    """A single instrument layer active during the section."""

    role: str  # "bass", "lead", "pad", "drum_kit", "fx"
    instrument: str  # free-form: "Roland TR-909 kick", "Aphex sub", ...
    enters_at_bar: int
    exits_at_bar: int  # exclusive
    base_velocity: int = 100  # 0-127


@dataclass(frozen=True)
class InstChange:
    """Describes an event-level arrangement change inside a section."""

    bar: int
    change: str  # "filter sweep on lead", "drop bass", "add hi-hats"


# ============================================================================
# Per-sphere decisions
# ============================================================================


@dataclass(frozen=True)
class StructureDecision:
    """Macroscopic shape of the section."""

    total_bars: int
    sub_sections: tuple[SubSection, ...] = ()
    breath_points: tuple[int, ...] = ()  # bar indices where the section "breathes"
    transition_in: str = ""  # narrative: how this section enters
    transition_out: str = ""  # narrative: how it exits / leads to next


@dataclass(frozen=True)
class HarmonyDecision:
    """Pitch material: mode, progression, voicings, harmonic rhythm."""

    mode: str  # "Aeolian", "Dorian", "Phrygian dominant", ...
    key_root: str  # "A", "F#", ...
    progression: tuple[str, ...] = ()  # roman numerals: ("i", "bVI", "bVII", "i")
    harmonic_rhythm: float = 1.0  # chords per bar
    voicing_strategy: str = ""  # free-form: "close-voiced piano + open fifth bass"
    cadence_at_end: str = ""  # "plagal", "deceptive", "open", "none"


@dataclass(frozen=True)
class RhythmDecision:
    """Drum/percussion patterns and groove."""

    tempo_bpm: int
    time_signature: str = "4/4"
    drum_pattern: str = ""  # narrative: "kick on 1 & 3, syncopated snare on 4..."
    subdivisions: int = 16  # 16 = sixteenth-note grid, 8 = eighth, etc.
    swing: float = 0.0  # 0.0 (straight) to ~0.6 (heavy swing)
    polyrhythms: tuple[str, ...] = ()  # e.g. ("3:4 hihat over 4/4 kick",)


@dataclass(frozen=True)
class ArrangementDecision:
    """Who plays, when, with what density."""

    layers: tuple[LayerSpec, ...] = ()
    density_curve: str = "medium"  # "sparse", "medium", "dense", "build", "valley"
    instrumentation_changes: tuple[InstChange, ...] = ()
    register_strategy: str = ""  # "low+mid only", "wide spread bass-to-air", ...


# Section-baseline dB. 0 dB = max perceived intensity; this baseline is
# the default a section sits at when no dynamic arc is specified. The
# parser falls back to this value for missing start_db/end_db, the
# composer uses it as the "is this dynamics decision actually doing
# anything?" sentinel, and the dataclass default sets the same level.
# Single source of truth — Phase 2.6.1 hoist.
DYNAMICS_BASELINE_DB: float = -12.0


@dataclass(frozen=True)
class DynamicsDecision:
    """The volume/intensity arc across the section."""

    arc_shape: str = "flat"  # "rising", "valley", "flat", "exponential", "sawtooth"
    start_db: float = DYNAMICS_BASELINE_DB  # relative to section baseline
    end_db: float = DYNAMICS_BASELINE_DB
    peak_bar: Optional[int] = None  # bar of the dynamic peak, if any
    inflection_points: tuple[tuple[int, float], ...] = ()  # (bar, db) pairs


@dataclass(frozen=True)
class PerformanceDecision:
    """Feel and articulation."""

    feel: str = "neutral"  # "laid-back", "pushed", "robotic", "loose"
    humanization_jitter_ms: float = 0.0  # 0 = quantized, 5-15 = light human, 30+ = sloppy
    velocity_range: tuple[int, int] = (60, 110)  # (min, max) MIDI velocity
    articulation_notes: str = ""  # free-form: "ghost notes on snare", "staccato lead"
    anti_patterns: tuple[str, ...] = ()  # things explicitly avoided


@dataclass(frozen=True)
class FxDecision:
    """Effects, mixing intent, stereo image."""

    reverb: Optional[str] = None  # "large hall, 4s decay" / None
    filter_envelope: Optional[str] = None  # "lowpass sweep 8kHz -> 400Hz over 16 bars"
    saturation: Optional[str] = None  # "tape saturation on master bus"
    stereo_strategy: str = "natural"  # "narrow", "natural", "wide", "binaural"
    sidechain: Optional[str] = None  # "kick triggers pad duck, 100ms release"
    notes: str = ""  # free-form for things that escape the categories above


# ============================================================================
# The blueprint itself
# ============================================================================


SPHERES: tuple[str, ...] = (
    "structure",
    "harmony",
    "rhythm",
    "arrangement",
    "dynamics",
    "performance",
    "fx",
)


@dataclass(frozen=True)
class SectionBlueprint:
    """A complete (or partial) section specification.

    All sphere fields are Optional. An empty SectionBlueprint is a valid
    starting point; agents fill spheres one at a time. The composer can
    only run on a blueprint where the spheres it needs are filled — but
    that is the composer's concern, not the blueprint's.
    """

    name: str  # "intro", "verse_1", "drop", ...
    references: tuple[str, ...] = ()  # ["Nirvana/Heart_Shaped_Box", ...]
    brief: str = ""  # the human-language directive that started this section

    structure: Optional[Decision[StructureDecision]] = None
    harmony: Optional[Decision[HarmonyDecision]] = None
    rhythm: Optional[Decision[RhythmDecision]] = None
    arrangement: Optional[Decision[ArrangementDecision]] = None
    dynamics: Optional[Decision[DynamicsDecision]] = None
    performance: Optional[Decision[PerformanceDecision]] = None
    fx: Optional[Decision[FxDecision]] = None

    def filled_spheres(self) -> tuple[str, ...]:
        """Return the names of spheres that have a Decision filled."""
        return tuple(s for s in SPHERES if getattr(self, s) is not None)

    def missing_spheres(self) -> tuple[str, ...]:
        return tuple(s for s in SPHERES if getattr(self, s) is None)

    def is_complete(self) -> bool:
        return not self.missing_spheres()

    def with_decision(self, sphere: str, decision: Decision) -> "SectionBlueprint":
        """Return a new blueprint with `sphere` replaced. Pure (no mutation).

        Useful for the director's reduce step over per-sphere agent outputs.
        """
        if sphere not in SPHERES:
            raise ValueError(f"Unknown sphere {sphere!r}. Known: {SPHERES}")
        if decision.sphere != sphere:
            raise ValueError(
                f"Decision claims sphere={decision.sphere!r} but assigned to {sphere!r}"
            )
        return replace(self, **{sphere: decision})
