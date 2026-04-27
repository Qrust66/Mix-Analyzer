"""Shared pytest fixtures for the composition_engine tests.

Centralizes blueprint construction helpers so each test file doesn't
re-invent its own _minimal_blueprint() variant. (Audit fix from
Phase 2.2 self-review #5.)
"""
import pytest

from composition_engine.blueprint import (
    ArrangementDecision,
    Citation,
    Decision,
    DynamicsDecision,
    FxDecision,
    HarmonyDecision,
    LayerSpec,
    PerformanceDecision,
    RhythmDecision,
    SectionBlueprint,
    StructureDecision,
    SubSection,
)


def _wrap(value, sphere: str) -> Decision:
    """Wrap a sphere value in a minimal Decision with default provenance."""
    return Decision(value=value, sphere=sphere)


@pytest.fixture
def wrap_decision():
    """Expose the _wrap helper to test files for ad-hoc Decision construction."""
    return _wrap


@pytest.fixture
def minimal_blueprint() -> SectionBlueprint:
    """Returns a 4-sphere-filled SectionBlueprint suitable for composer pipeline tests.

    Structure : 16 bars in A minor at 100 BPM with two layers (drum_kit, bass).
    Other spheres (dynamics, performance, fx) are intentionally left empty.
    """
    bp = SectionBlueprint(name="test_intro")
    bp = bp.with_decision("structure", _wrap(StructureDecision(total_bars=16), "structure"))
    bp = bp.with_decision(
        "harmony",
        _wrap(
            HarmonyDecision(
                mode="Aeolian",
                key_root="A",
                progression=("i", "bVI", "bVII", "i"),
                harmonic_rhythm=1.0,
            ),
            "harmony",
        ),
    )
    bp = bp.with_decision("rhythm", _wrap(RhythmDecision(tempo_bpm=100), "rhythm"))
    bp = bp.with_decision(
        "arrangement",
        _wrap(
            ArrangementDecision(
                layers=(
                    LayerSpec(role="drum_kit", instrument="909",
                              enters_at_bar=0, exits_at_bar=16, base_velocity=100),
                    LayerSpec(role="bass", instrument="sub",
                              enters_at_bar=4, exits_at_bar=16, base_velocity=90),
                ),
                density_curve="medium",
            ),
            "arrangement",
        ),
    )
    return bp


@pytest.fixture
def complete_blueprint() -> SectionBlueprint:
    """Returns a fully-filled 7-sphere SectionBlueprint with provenance citations.

    Used by tests that need to exercise the full pipeline (cohesion checks,
    director ghost mode validation, provenance preservation).
    """
    cit = Citation(
        song="Nirvana/Heart_Shaped_Box",
        path="composition.section_count_and_lengths",
        excerpt="Intro 8 bars sparse, building...",
    )
    bp = SectionBlueprint(name="intro", references=("Nirvana/Heart_Shaped_Box",))
    bp = bp.with_decision(
        "structure",
        Decision(
            value=StructureDecision(
                total_bars=16,
                sub_sections=(
                    SubSection(name="hush", start_bar=0, end_bar=8, role="breath"),
                    SubSection(name="build", start_bar=8, end_bar=16, role="build"),
                ),
                breath_points=(7, 15),
            ),
            sphere="structure",
            inspired_by=(cit,),
            rationale="16 bars split 8+8 mirrors verse pacing of refs.",
        ),
    )
    bp = bp.with_decision(
        "harmony",
        _wrap(
            HarmonyDecision(
                mode="Aeolian", key_root="A",
                progression=("i", "bVI", "bVII", "i"), harmonic_rhythm=0.5,
            ),
            "harmony",
        ),
    )
    bp = bp.with_decision(
        "rhythm", _wrap(RhythmDecision(tempo_bpm=100, time_signature="4/4"), "rhythm"),
    )
    bp = bp.with_decision(
        "arrangement",
        _wrap(
            ArrangementDecision(
                layers=(
                    LayerSpec(role="pad", instrument="warm pad",
                              enters_at_bar=0, exits_at_bar=16),
                ),
                density_curve="sparse",
            ),
            "arrangement",
        ),
    )
    bp = bp.with_decision(
        "dynamics",
        _wrap(
            DynamicsDecision(
                arc_shape="rising", start_db=-18.0, end_db=-6.0, peak_bar=15,
            ),
            "dynamics",
        ),
    )
    bp = bp.with_decision(
        "performance",
        _wrap(
            PerformanceDecision(feel="laid-back", humanization_jitter_ms=8.0),
            "performance",
        ),
    )
    bp = bp.with_decision(
        "fx",
        _wrap(
            FxDecision(reverb="large hall, 4s", stereo_strategy="wide"),
            "fx",
        ),
    )
    return bp
