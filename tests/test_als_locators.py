#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for als_utils Locator I/O (Feature 3 Phase B)."""

from __future__ import annotations

import gzip
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from als_utils import (  # noqa: E402
    beats_to_seconds,
    read_locators,
    seconds_to_beats,
    write_locators,
)
from section_detector import get_or_detect_sections  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _minimal_als_xml(locators_inner: str = "") -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Ableton MajorVersion=\"5\" MinorVersion=\"11.0_11300\">\n"
        "<LiveSet>\n"
        "\t<Locators>\n"
        "\t\t<Locators>"
        + (f"\n{locators_inner}\n\t\t" if locators_inner else "\n\t\t")
        + "</Locators>\n"
        "\t</Locators>\n"
        "</LiveSet>\n"
        "</Ableton>\n"
    )


def _als_without_locators_block_xml() -> str:
    """An .als that has no <Locators> block at all — write_locators must create one."""
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Ableton MajorVersion=\"5\" MinorVersion=\"11.0_11300\">\n"
        "<LiveSet>\n"
        "</LiveSet>\n"
        "</Ableton>\n"
    )


def _write_als(path: Path, xml: str) -> None:
    path.write_bytes(gzip.compress(xml.encode("utf-8")))


def _user_locator_xml(loc_id: int, time_beats: float, name: str) -> str:
    return (
        f"\t\t\t<Locator Id=\"{loc_id}\">\n"
        f"\t\t\t\t<Time Value=\"{time_beats}\" />\n"
        f"\t\t\t\t<Name Value=\"{name}\" />\n"
        f"\t\t\t\t<Annotation Value=\"\" />\n"
        f"\t\t\t\t<IsSongStart Value=\"false\" />\n"
        f"\t\t\t\t<LockEnvelope Value=\"0\" />\n"
        f"\t\t\t</Locator>"
    )


# ---------------------------------------------------------------------------
# Test 1 — round-trip: write 5 Locators, read back the same data
# ---------------------------------------------------------------------------

def test_write_then_read_roundtrip_five_locators(tmp_path):
    als_path = tmp_path / "empty.als"
    _write_als(als_path, _minimal_als_xml())

    wanted = [
        {"time_beats": 0.0, "name": "Section 1", "annotation": ""},
        {"time_beats": 16.0, "name": "Section 2", "annotation": "drop"},
        {"time_beats": 32.0, "name": "Section 3", "annotation": ""},
        {"time_beats": 48.0, "name": "Section 4", "annotation": ""},
        {"time_beats": 64.0, "name": "Outro", "annotation": "fade"},
    ]

    count = write_locators(als_path, wanted)
    assert count == 5

    output = als_path.with_name(als_path.stem + "_with_sections.als")
    assert output.exists()

    # sanity: output decompresses to XML (guard against double-gzip)
    with gzip.open(output, "rb") as f:
        xml = f.read().decode("utf-8")
    assert xml.startswith("<?xml")

    got = read_locators(output)
    assert len(got) == 5
    for want, got_loc in zip(wanted, got):
        assert got_loc["time_beats"] == pytest.approx(want["time_beats"], abs=1e-6)
        assert got_loc["name"] == want["name"]
        assert got_loc["annotation"] == want["annotation"]

    # Ids are unique and contiguous starting from 0 (no prior Locators)
    ids = [loc["id"] for loc in got]
    assert len(set(ids)) == 5
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Test 2 — empty list write on an .als with existing Locators: file untouched
# ---------------------------------------------------------------------------

def test_empty_write_preserves_existing_locators(tmp_path):
    als_path = tmp_path / "with_existing.als"
    xml = _minimal_als_xml(
        "\n".join(
            [
                _user_locator_xml(10, 0.0, "Intro user"),
                _user_locator_xml(11, 16.0, "Drop user"),
            ]
        )
    )
    _write_als(als_path, xml)
    original_bytes = als_path.read_bytes()

    # write_locators with an empty list must be a no-op
    count = write_locators(als_path, [])
    assert count == 0

    # Source file unchanged — byte-for-byte.
    assert als_path.read_bytes() == original_bytes
    # No sidecar file generated.
    assert not als_path.with_name(als_path.stem + "_with_sections.als").exists()

    # Re-reading the source still returns both user Locators verbatim.
    existing = read_locators(als_path)
    assert [e["name"] for e in existing] == ["Intro user", "Drop user"]


# ---------------------------------------------------------------------------
# Test 3 — appending to existing Locators preserves them and uses max(id)+1
# ---------------------------------------------------------------------------

def test_append_preserves_existing_and_assigns_max_plus_one_ids(tmp_path):
    als_path = tmp_path / "append.als"
    _write_als(
        als_path,
        _minimal_als_xml(
            "\n".join(
                [
                    _user_locator_xml(42, 0.0, "Intro user"),
                    _user_locator_xml(43, 16.0, "Break user"),
                ]
            )
        ),
    )

    new = [
        {"time_beats": 8.0, "name": "Auto-added A"},
        {"time_beats": 24.0, "name": "Auto-added B"},
    ]
    count = write_locators(als_path, new)
    assert count == 2

    output = als_path.with_name(als_path.stem + "_with_sections.als")
    all_locs = read_locators(output)

    # Both user Locators must still be there verbatim.
    names = [l["name"] for l in all_locs]
    assert "Intro user" in names
    assert "Break user" in names
    # Plus the 2 newly added.
    assert "Auto-added A" in names
    assert "Auto-added B" in names
    assert len(all_locs) == 4

    # New Ids follow max(existing) + 1 rule: 44, 45.
    new_locs = [l for l in all_locs if l["name"].startswith("Auto-added")]
    new_ids = sorted(l["id"] for l in new_locs)
    assert new_ids == [44, 45]


# ---------------------------------------------------------------------------
# Test 4 — Time values match beats under a non-trivial tempo map
# ---------------------------------------------------------------------------

def test_time_values_match_non_trivial_tempo_map(tmp_path):
    als_path = tmp_path / "tempo.als"
    _write_als(als_path, _minimal_als_xml())

    tempo_events = [(0.0, 120.0), (10.0, 90.0)]
    # Boundaries we want in seconds: 0s, 10s, 20s
    seconds = [0.0, 10.0, 20.0]
    beats = [seconds_to_beats(s, tempo_events) for s in seconds]
    assert beats == pytest.approx([0.0, 20.0, 35.0], abs=1e-6)

    new = [
        {"time_beats": beats[i], "name": f"S{i+1}"} for i in range(3)
    ]
    write_locators(als_path, new)

    output = als_path.with_name(als_path.stem + "_with_sections.als")
    got = read_locators(output)
    got_beats = [l["time_beats"] for l in got]
    assert got_beats == pytest.approx(beats, abs=1e-6)

    # And the inverse: beats -> seconds recovers our boundaries.
    recovered_seconds = [beats_to_seconds(b, tempo_events) for b in got_beats]
    assert recovered_seconds == pytest.approx(seconds, abs=1e-6)


# ---------------------------------------------------------------------------
# Test 5 — user's question: one manual Locator at an odd position is preserved
# ---------------------------------------------------------------------------

def test_single_user_locator_at_odd_position_is_never_overwritten(tmp_path):
    """User adds "Intro quiet" manually at 0:12 where auto-detection would not
    have placed a boundary. get_or_detect_sections must read it verbatim,
    skip detection, and leave the source file untouched.
    """
    als_path = tmp_path / "one_user_locator.als"
    # 0:12 @ 120 BPM = 24 beats
    _write_als(
        als_path,
        _minimal_als_xml(_user_locator_xml(99, 24.0, "Intro quiet")),
    )
    original_bytes = als_path.read_bytes()

    # Audio where auto would split at ~5s and ~10s (NOT at 12s).
    n = 120
    rng = np.random.default_rng(7)
    delta = rng.uniform(0.0, 0.3, size=n)
    delta[30] = 8.0  # transition ~5s
    delta[60] = 8.0  # transition ~10s
    zone = np.full(n, -30.0)
    times = np.linspace(0.0, 20.0, n)

    sections, were_written = get_or_detect_sections(
        als_path=als_path,
        delta_spectrum=delta,
        zone_energy=zone,
        times=times,
        tempo_events=[(0.0, 120.0)],
    )

    assert were_written is False
    assert len(sections) == 1
    assert sections[0].name == "Intro quiet"
    assert sections[0].start_beats == pytest.approx(24.0, abs=1e-3)
    # section spans from the user Locator to end-of-track
    assert sections[0].start_seconds == pytest.approx(12.0, abs=1e-3)
    assert sections[0].end_seconds == pytest.approx(20.0, abs=1e-3)

    # Source file is byte-identical (no write at all on the read path).
    assert als_path.read_bytes() == original_bytes
    # No sidecar either.
    assert not als_path.with_name(als_path.stem + "_with_sections.als").exists()


# ---------------------------------------------------------------------------
# Test 6 — .als with no <Locators> block at all: write_locators creates one
# ---------------------------------------------------------------------------

def test_write_creates_locators_block_when_absent(tmp_path):
    als_path = tmp_path / "no_block.als"
    _write_als(als_path, _als_without_locators_block_xml())

    count = write_locators(als_path, [{"time_beats": 0.0, "name": "Section 1"}])
    assert count == 1

    output = als_path.with_name(als_path.stem + "_with_sections.als")
    got = read_locators(output)
    assert len(got) == 1
    assert got[0]["name"] == "Section 1"


# ---------------------------------------------------------------------------
# Test 7 — seconds_to_beats stays backwards-compatible with a float tempo
# ---------------------------------------------------------------------------

def test_seconds_to_beats_float_tempo_backwards_compat():
    # legacy eq8_automation.py call style: seconds_to_beats(t, tempo_float)
    assert seconds_to_beats(2.0, 120.0) == pytest.approx(4.0, abs=1e-6)
    assert beats_to_seconds(4.0, 120.0) == pytest.approx(2.0, abs=1e-6)
