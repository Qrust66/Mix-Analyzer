"""Tests for composition_engine.blueprint.composer_adapter — Phase 2.1
end-to-end pipeline from a SectionBlueprint through composer.compose()."""
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
from composition_engine.blueprint.composer_adapter import (
    blueprint_to_composition,
    compose_from_blueprint,
    key_root_to_midi,
)


# ============================================================================
# key_root_to_midi
# ============================================================================


@pytest.mark.parametrize("key_root,octave,expected", [
    ("C", 3, 48),
    ("D", 3, 50),
    ("A", 3, 57),
    ("F#", 3, 54),
    ("Gb", 3, 54),  # enharmonic
    ("Bb", 3, 58),
    ("C", 4, 60),  # middle C
])
def test_key_root_to_midi(key_root, octave, expected):
    assert key_root_to_midi(key_root, octave=octave) == expected


def test_unknown_key_root_falls_back_to_C():
    """Defensive: prose data may have quirks. Falling back is preferable to
    crashing the pipeline on minor formatting issues."""
    assert key_root_to_midi("???", octave=3) == 48  # C3


# ============================================================================
# Helpers — minimal complete blueprint
# ============================================================================


def _wrap(value, sphere):
    return Decision(value=value, sphere=sphere)


# Note: the 4-sphere _minimal_blueprint() helper formerly here has been
# moved to tests/conftest.py as the `minimal_blueprint` pytest fixture
# (Phase 2.3.1 deduplication). Tests that need a custom variant build
# from scratch using `_wrap` and the schema dataclasses, or transform the
# fixture via with_decision() in the test body.


# ============================================================================
# blueprint_to_composition
# ============================================================================


def test_blueprint_to_composition_basic(minimal_blueprint):
    bp = minimal_blueprint
    composition = blueprint_to_composition(bp)
    assert composition.total_bars == 16
    assert composition.tempo_bpm == 100.0
    assert composition.tonic_pitch == 57  # A3
    assert "DRUM_KIT" in composition.layers_per_track
    assert "BASS" in composition.layers_per_track


def test_blueprint_to_composition_groups_layers_per_track(minimal_blueprint):
    """Multiple LayerSpecs with the same role end up in the same track."""
    bp = minimal_blueprint.with_decision(
        "arrangement",
        _wrap(
            ArrangementDecision(
                layers=(
                    LayerSpec(role="bass", instrument="sub_low",
                              enters_at_bar=0, exits_at_bar=8),
                    LayerSpec(role="bass", instrument="sub_high",
                              enters_at_bar=8, exits_at_bar=16),
                ),
            ),
            "arrangement",
        ),
    )
    composition = blueprint_to_composition(bp)
    assert "BASS" in composition.layers_per_track
    assert len(composition.layers_per_track["BASS"]) == 2


def test_blueprint_to_composition_shifts_bars_to_one_indexed(minimal_blueprint):
    """Blueprint uses 0-indexed bars; composer's LayerSpec uses 1-indexed."""
    composition = blueprint_to_composition(minimal_blueprint)
    # First drum_kit layer: blueprint enters_at_bar=0 → composer entry_at_bar=1
    drum_layer = composition.layers_per_track["DRUM_KIT"][0]
    assert drum_layer.entry_at_bar == 1
    assert drum_layer.exit_at_bar == 17


@pytest.mark.parametrize("missing_sphere", ["structure", "harmony", "rhythm", "arrangement"])
def test_blueprint_to_composition_requires_essential_spheres(minimal_blueprint, missing_sphere):
    bp = minimal_blueprint
    # Drop one essential sphere and check error
    kwargs = {s: getattr(bp, s) for s in ["structure", "harmony", "rhythm", "arrangement"]}
    kwargs[missing_sphere] = None
    incomplete = SectionBlueprint(name=bp.name, references=bp.references, brief=bp.brief, **kwargs)
    with pytest.raises(ValueError, match=missing_sphere):
        blueprint_to_composition(incomplete)


# ============================================================================
# compose_from_blueprint — end-to-end pipeline
# ============================================================================


def test_compose_from_blueprint_returns_composer_dict(minimal_blueprint):
    result = compose_from_blueprint(minimal_blueprint)
    assert "tracks" in result
    assert "tempo_bpm" in result
    assert "total_bars" in result
    assert "diagnostics" in result
    assert result["total_bars"] == 16
    assert result["tempo_bpm"] == 100.0


def test_compose_from_blueprint_renders_notes_per_track(minimal_blueprint):
    """The pipeline should produce non-empty note-lists for each track."""
    result = compose_from_blueprint(minimal_blueprint)
    assert len(result["tracks"]) == 2  # DRUM_KIT and BASS
    for track_name, notes in result["tracks"].items():
        assert len(notes) > 0, f"Track {track_name} produced no notes"
        # Each note has the canonical shape
        for n in notes:
            assert "time" in n
            assert "duration" in n
            assert "velocity" in n
            assert "pitch" in n


def test_compose_from_blueprint_drum_pitch_is_36(minimal_blueprint):
    """drum_kit role generates kick on MIDI pitch 36."""
    result = compose_from_blueprint(minimal_blueprint)
    drum_notes = result["tracks"]["DRUM_KIT"]
    assert all(n["pitch"] == 36 for n in drum_notes), \
        "drum_kit motif should produce only kick (pitch 36)"


def test_compose_from_blueprint_bass_below_tonic(minimal_blueprint):
    """bass role plays one octave below the tonic. A3=57 → bass=A2=45."""
    result = compose_from_blueprint(minimal_blueprint)
    bass_notes = result["tracks"]["BASS"]
    assert all(n["pitch"] == 45 for n in bass_notes), \
        "bass motif should produce A2 (pitch 45) given tonic A3=57"
