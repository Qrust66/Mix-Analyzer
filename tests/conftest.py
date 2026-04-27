"""Shared pytest fixtures for the composition_engine tests.

Centralizes blueprint construction helpers so each test file doesn't
re-invent its own _minimal_blueprint() variant. (Audit fix from
Phase 2.2 self-review #5.)
"""
import pytest

from composition_engine.blueprint import (
    ArrangementDecision,
    Decision,
    HarmonyDecision,
    LayerSpec,
    RhythmDecision,
    SectionBlueprint,
    StructureDecision,
)


def _wrap(value, sphere: str) -> Decision:
    """Wrap a sphere value in a minimal Decision with default provenance."""
    return Decision(value=value, sphere=sphere)


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
