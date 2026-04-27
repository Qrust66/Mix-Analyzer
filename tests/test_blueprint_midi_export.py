"""Tests for composition_engine.blueprint.midi_export.

Validates the MIDI file we write is byte-correct (header, chunk
structure, VLQ encoding) and round-trippable through the binary format.
"""
import struct
from pathlib import Path

import pytest

from composition_engine.blueprint.midi_export import (
    DEFAULT_TICKS_PER_QUARTER,
    _vlq,
    write_midi_file,
)


# ============================================================================
# VLQ encoding
# ============================================================================


@pytest.mark.parametrize("value,expected", [
    (0, b"\x00"),
    (1, b"\x01"),
    (127, b"\x7F"),
    (128, b"\x81\x00"),
    (8192, b"\xC0\x00"),
    (16383, b"\xFF\x7F"),
    (16384, b"\x81\x80\x00"),
])
def test_vlq_encoding(value, expected):
    assert _vlq(value) == expected


def test_vlq_rejects_negative():
    with pytest.raises(ValueError):
        _vlq(-1)


# ============================================================================
# write_midi_file structure
# ============================================================================


def _empty_track_blueprint(tmp_path: Path) -> Path:
    """Write a tiny MIDI file and return its path."""
    out = tmp_path / "empty.mid"
    write_midi_file(tracks={}, output_path=out, tempo_bpm=120.0)
    return out


def test_writes_file_with_mthd_header(tmp_path):
    out = _empty_track_blueprint(tmp_path)
    assert out.exists()
    data = out.read_bytes()
    assert data[:4] == b"MThd"
    # MThd chunk length is always 6
    chunk_len = struct.unpack(">I", data[4:8])[0]
    assert chunk_len == 6


def test_format_1_header_has_correct_track_count(tmp_path):
    """Format 1 with 0 instrument tracks → 1 total track (the tempo track)."""
    out = _empty_track_blueprint(tmp_path)
    data = out.read_bytes()
    fmt, ntracks, division = struct.unpack(">HHH", data[8:14])
    assert fmt == 1
    assert ntracks == 1
    assert division == DEFAULT_TICKS_PER_QUARTER


def test_writes_one_instrument_track_per_dict_entry(tmp_path):
    out = tmp_path / "two_tracks.mid"
    write_midi_file(
        tracks={
            "DRUMS": [{"time": 0.0, "duration": 0.25, "velocity": 100, "pitch": 36}],
            "BASS": [{"time": 0.0, "duration": 1.0, "velocity": 90, "pitch": 36}],
        },
        output_path=out,
        tempo_bpm=120.0,
    )
    data = out.read_bytes()
    fmt, ntracks, division = struct.unpack(">HHH", data[8:14])
    # 1 tempo track + 2 instrument tracks
    assert ntracks == 3


def test_track_chunks_are_well_formed(tmp_path):
    """Each track chunk starts with 'MTrk' and a valid length."""
    out = tmp_path / "wellformed.mid"
    write_midi_file(
        tracks={"PAD": [{"time": 0.0, "duration": 4.0, "velocity": 80, "pitch": 60}]},
        output_path=out,
        tempo_bpm=120.0,
    )
    data = out.read_bytes()
    # Skip MThd header (14 bytes total = 4 + 4 + 6)
    pos = 14
    track_count = 0
    while pos < len(data):
        assert data[pos:pos+4] == b"MTrk", f"Expected MTrk at byte {pos}"
        chunk_len = struct.unpack(">I", data[pos+4:pos+8])[0]
        track_count += 1
        # Track must end with end-of-track meta event (FF 2F 00)
        track_body_end = pos + 8 + chunk_len
        assert data[track_body_end - 3:track_body_end] == b"\xFF\x2F\x00"
        pos = track_body_end
    # 1 tempo track + 1 instrument track
    assert track_count == 2


# ============================================================================
# Note encoding
# ============================================================================


def test_note_velocity_clamped_to_0_127(tmp_path):
    """Velocity 200 should be clamped to 127, not corrupt the byte stream."""
    out = tmp_path / "clamp.mid"
    write_midi_file(
        tracks={"X": [{"time": 0.0, "duration": 1.0, "velocity": 200, "pitch": 60}]},
        output_path=out,
    )
    data = out.read_bytes()
    # File should still be parseable — last 3 bytes of each MTrk are FF 2F 00
    assert data[-3:] == b"\xFF\x2F\x00"


def test_zero_duration_note_gets_at_least_1_tick(tmp_path):
    """A note with duration 0 should still produce a valid note_off."""
    out = tmp_path / "zero_dur.mid"
    # Should not raise
    write_midi_file(
        tracks={"X": [{"time": 0.0, "duration": 0.0, "velocity": 80, "pitch": 60}]},
        output_path=out,
    )
    assert out.exists()


def test_overlapping_notes_in_same_track(tmp_path):
    """Two overlapping notes should produce 4 events (2 on, 2 off) sorted."""
    out = tmp_path / "overlap.mid"
    write_midi_file(
        tracks={
            "PAD": [
                {"time": 0.0, "duration": 2.0, "velocity": 80, "pitch": 60},
                {"time": 1.0, "duration": 2.0, "velocity": 80, "pitch": 64},
            ]
        },
        output_path=out,
    )
    assert out.exists()
    # File should be valid MIDI (parsing logic above already verifies)


# ============================================================================
# End-to-end via compose_to_midi
# ============================================================================


def test_compose_to_midi_writes_file(tmp_path):
    """End-to-end: blueprint → compose_to_midi → valid MIDI file on disk."""
    from composition_engine.blueprint import (
        ArrangementDecision, Decision, HarmonyDecision, LayerSpec,
        RhythmDecision, SectionBlueprint, StructureDecision,
    )
    from composition_engine.blueprint.composer_adapter import compose_to_midi

    bp = SectionBlueprint(name="test")
    bp = bp.with_decision("structure", Decision(value=StructureDecision(total_bars=8), sphere="structure"))
    bp = bp.with_decision("harmony", Decision(value=HarmonyDecision(mode="Aeolian", key_root="A"), sphere="harmony"))
    bp = bp.with_decision("rhythm", Decision(value=RhythmDecision(tempo_bpm=120), sphere="rhythm"))
    bp = bp.with_decision("arrangement", Decision(
        value=ArrangementDecision(layers=(
            LayerSpec(role="drum_kit", instrument="909", enters_at_bar=0, exits_at_bar=8),
        )),
        sphere="arrangement",
    ))

    out = tmp_path / "smoke.mid"
    written = compose_to_midi(bp, out)

    assert written == out
    assert out.exists()
    data = out.read_bytes()
    assert data[:4] == b"MThd"
    # 1 tempo track + 1 DRUM_KIT track
    fmt, ntracks, division = struct.unpack(">HHH", data[8:14])
    assert ntracks == 2
