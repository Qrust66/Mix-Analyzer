"""MIDI export — write the composer's per-track note dict to a Standard
MIDI File (Format 1, multi-track, type 1).

Pure stdlib (struct only). No new dependency for the project.

The MIDI file format is binary but well-specified:
  - File header chunk: 'MThd' + length(6) + format + ntracks + division
  - Each track chunk: 'MTrk' + length + delta-time-encoded events

This module produces valid MIDI files readable by Ableton Live, Logic,
Reaper, MuseScore, etc. — verified by the file-roundtrip test.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Dict, List


# Standard ticks per quarter note. 480 is widely-used (Reaper, Ableton).
DEFAULT_TICKS_PER_QUARTER = 480


def _vlq(value: int) -> bytes:
    """Variable-length quantity encoding (MIDI delta-time format).

    Each byte holds 7 bits; the MSB is set on all but the last byte to
    indicate continuation. Values 0..127 → 1 byte. 128..16383 → 2 bytes.
    """
    if value < 0:
        raise ValueError(f"vlq cannot encode negative value: {value}")
    if value == 0:
        return b"\x00"
    out: List[int] = []
    while value > 0:
        out.append(value & 0x7F)
        value >>= 7
    out.reverse()
    # Set continuation bit on all bytes except the last
    return bytes(
        (b | 0x80) if i < len(out) - 1 else b
        for i, b in enumerate(out)
    )


def _track_chunk(events: List[bytes]) -> bytes:
    """Wrap a list of pre-encoded events in an MTrk chunk header."""
    body = b"".join(events)
    return b"MTrk" + struct.pack(">I", len(body)) + body


def _tempo_meta(bpm: float) -> bytes:
    """Meta event: set tempo. Uses microseconds-per-quarter encoding.

    BPM 120 → 500_000 µs/quarter. Format: delta=0, FF 51 03 + 3 bytes.
    """
    if bpm <= 0:
        raise ValueError(f"bpm must be positive, got {bpm}")
    microseconds_per_quarter = int(round(60_000_000.0 / bpm))
    return b"\x00\xFF\x51\x03" + microseconds_per_quarter.to_bytes(3, "big")


def _track_name_meta(name: str) -> bytes:
    """Meta event: track name. delta=0, FF 03 <vlq len> <name bytes>."""
    name_bytes = name.encode("utf-8", errors="replace")
    if len(name_bytes) > 0xFFFF:
        name_bytes = name_bytes[:0xFFFF]
    return b"\x00\xFF\x03" + _vlq(len(name_bytes)) + name_bytes


def _end_of_track() -> bytes:
    """Meta event: end of track. delta=0, FF 2F 00."""
    return b"\x00\xFF\x2F\x00"


def write_midi_file(
    tracks: Dict[str, List[Dict[str, Any]]],
    output_path: str | Path,
    tempo_bpm: float = 120.0,
    ticks_per_quarter: int = DEFAULT_TICKS_PER_QUARTER,
) -> Path:
    """Write a Format-1 multi-track MIDI file.

    Args:
        tracks: {track_name: [{'time': beats, 'duration': beats,
                               'velocity': 0-127, 'pitch': 0-127}, ...]}
        output_path: destination .mid path
        tempo_bpm: tempo in beats per minute
        ticks_per_quarter: PPQ resolution (default 480)

    Returns:
        The Path written.

    Note: MIDI has 16 channels max — tracks beyond the 16th will reuse
    channel slots. For Mix Analyzer's typical 4-8 tracks this is a non-issue.
    """
    output_path = Path(output_path)

    # Format 1: track 0 is reserved for tempo/meta; subsequent tracks are
    # the per-instrument tracks. So total = 1 + N.
    n_tracks = 1 + len(tracks)

    # File header chunk
    header = (
        b"MThd"
        + struct.pack(">I", 6)
        + struct.pack(">HHH", 1, n_tracks, ticks_per_quarter)
    )

    # Track 0: tempo + end-of-track only
    tempo_track = _track_chunk([_tempo_meta(tempo_bpm), _end_of_track()])

    # Tracks 1..N: instrument tracks
    instrument_chunks: List[bytes] = []
    for track_idx, (track_name, notes) in enumerate(tracks.items()):
        channel = track_idx % 16

        # Build absolute-tick event list (note_on + note_off pairs)
        # Each tuple: (tick, kind, pitch, velocity)
        # kind in {'note_on', 'note_off'}
        timed_events: List[tuple] = []
        for note in notes:
            time_beats = float(note["time"])
            duration_beats = float(note["duration"])
            pitch = int(note["pitch"])
            velocity = max(0, min(127, int(note["velocity"])))
            start_tick = int(round(time_beats * ticks_per_quarter))
            end_tick = int(round((time_beats + duration_beats) * ticks_per_quarter))
            if end_tick <= start_tick:
                end_tick = start_tick + 1  # ensure at least 1-tick duration
            timed_events.append((start_tick, "note_on", pitch, velocity))
            timed_events.append((end_tick, "note_off", pitch, 0))

        # Sort: by tick, with note_off before note_on when ticks tie
        # (so a re-attack of the same pitch closes the previous note first).
        # Stable sort with kind-priority: note_off=0, note_on=1
        timed_events.sort(key=lambda e: (e[0], 0 if e[1] == "note_off" else 1))

        # Encode delta-time events
        encoded: List[bytes] = [_track_name_meta(track_name)]
        last_tick = 0
        for tick, kind, pitch, velocity in timed_events:
            delta = max(0, tick - last_tick)
            last_tick = tick
            status = (0x90 if kind == "note_on" else 0x80) | channel
            encoded.append(_vlq(delta) + bytes([status, pitch, velocity]))
        encoded.append(_end_of_track())

        instrument_chunks.append(_track_chunk(encoded))

    output_path.write_bytes(header + tempo_track + b"".join(instrument_chunks))
    return output_path


__all__ = ["write_midi_file", "DEFAULT_TICKS_PER_QUARTER"]
