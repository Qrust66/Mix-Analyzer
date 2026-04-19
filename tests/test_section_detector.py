#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for section_detector (Feature 3 Phase A)."""

from __future__ import annotations

import gzip
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from section_detector import (  # noqa: E402
    Section,
    _beats_to_seconds,
    _parse_locators,
    _read_als_xml,
    detect_sections_from_audio,
    get_or_detect_sections,
    seconds_to_beats,
)


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------

def _synthetic_four_sections():
    """Build a delta/zone/times set with 3 transitions (=> 4 sections).

    Each section spans 30 frames and is internally stable (low delta).
    At the boundary frames we inject spikes to simulate abrupt spectral change.
    """
    n_per = 30
    n_sections = 4
    rng = np.random.default_rng(seed=42)

    delta = rng.uniform(0.0, 0.3, size=n_per * n_sections)
    # zone energy distinguishes sections but is not used for detection
    energies = [-45.0, -20.0, -35.0, -10.0]
    zone = np.concatenate([
        np.full(n_per, e) + rng.normal(0, 0.2, size=n_per) for e in energies
    ])
    # Inject transition spikes at boundaries
    for boundary in (n_per, 2 * n_per, 3 * n_per):
        delta[boundary] = 8.0
        delta[boundary + 1] = 6.0

    times = np.linspace(0.0, 20.0, len(delta))
    return delta, zone, times


def _minimal_als_xml(with_locators: bool = False) -> str:
    locators_block = ""
    if with_locators:
        locators_block = (
            "\t<Locators>\n"
            "\t\t<Locators>\n"
            "\t\t\t<Locator Id=\"10\">\n"
            "\t\t\t\t<Time Value=\"0.0\" />\n"
            "\t\t\t\t<Name Value=\"Intro perso\" />\n"
            "\t\t\t\t<Annotation Value=\"\" />\n"
            "\t\t\t\t<IsSongStart Value=\"true\" />\n"
            "\t\t\t\t<LockEnvelope Value=\"0\" />\n"
            "\t\t\t</Locator>\n"
            "\t\t\t<Locator Id=\"11\">\n"
            "\t\t\t\t<Time Value=\"16.0\" />\n"
            "\t\t\t\t<Name Value=\"Drop\" />\n"
            "\t\t\t\t<Annotation Value=\"\" />\n"
            "\t\t\t\t<IsSongStart Value=\"false\" />\n"
            "\t\t\t\t<LockEnvelope Value=\"0\" />\n"
            "\t\t\t</Locator>\n"
            "\t\t</Locators>\n"
            "\t</Locators>\n"
        )
    else:
        locators_block = "\t<Locators>\n\t\t<Locators>\n\t\t</Locators>\n\t</Locators>\n"
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Ableton MajorVersion=\"5\" MinorVersion=\"11.0_11300\">\n"
        "<LiveSet>\n"
        + locators_block
        + "</LiveSet>\n"
        "</Ableton>\n"
    )


def _write_als(path: Path, xml: str) -> None:
    path.write_bytes(gzip.compress(xml.encode("utf-8")))


# ---------------------------------------------------------------------------
# Test 1 — synthetic audio with 4 sections
# ---------------------------------------------------------------------------

def test_detects_four_sections_on_synthetic_audio():
    delta, zone, times = _synthetic_four_sections()
    sections = detect_sections_from_audio(
        delta_spectrum=delta,
        zone_energy=zone,
        times=times,
        threshold_multiplier=2.5,
    )

    assert len(sections) == 4, f"expected 4 sections, got {len(sections)}: {sections}"
    assert [s.name for s in sections] == [
        "Section 1", "Section 2", "Section 3", "Section 4",
    ]
    # 1-indexed
    assert [s.index for s in sections] == [1, 2, 3, 4]
    # non-overlapping, contiguous buckets
    for a, b in zip(sections, sections[1:]):
        assert a.end_bucket < b.start_bucket or a.end_bucket + 1 == b.start_bucket
    # monotonic time
    assert all(s.start_seconds < s.end_seconds for s in sections)
    assert all(
        a.end_seconds <= b.start_seconds + 1e-6
        for a, b in zip(sections, sections[1:])
    )


# ---------------------------------------------------------------------------
# Test 2 — .als without Locators: detection runs and Locators are written
# ---------------------------------------------------------------------------

def test_als_without_locators_triggers_detection_and_write(tmp_path):
    als_path = tmp_path / "no_locators.als"
    _write_als(als_path, _minimal_als_xml(with_locators=False))

    delta, zone, times = _synthetic_four_sections()

    sections, were_written = get_or_detect_sections(
        als_path=als_path,
        delta_spectrum=delta,
        zone_energy=zone,
        times=times,
        tempo_events=[(0.0, 120.0)],
    )

    assert were_written is True
    assert len(sections) >= 2  # at least a few transitions detected
    assert all(s.name.startswith("Section ") for s in sections)

    # The output file must exist, be valid gzip XML, and contain the new locators.
    output = als_path.with_name(als_path.stem + "_with_sections.als")
    assert output.exists(), "expected a <stem>_with_sections.als output file"
    xml = _read_als_xml(output)
    assert xml.startswith("<?xml"), "gzip content must decode to XML (guards against double-gzip)"

    parsed = _parse_locators(xml)
    assert len(parsed) == len(sections)
    # Names are preserved, Ids are positive and unique
    assert [p["name"] for p in parsed] == [s.name for s in sections]
    ids = [p["id"] for p in parsed]
    assert len(set(ids)) == len(ids)


# ---------------------------------------------------------------------------
# Test 3 — .als with Locators: detection is skipped, Locators are read as-is
# ---------------------------------------------------------------------------

def test_als_with_existing_locators_skips_detection(tmp_path):
    als_path = tmp_path / "with_locators.als"
    _write_als(als_path, _minimal_als_xml(with_locators=True))

    delta, zone, times = _synthetic_four_sections()

    sections, were_written = get_or_detect_sections(
        als_path=als_path,
        delta_spectrum=delta,
        zone_energy=zone,
        times=times,
        tempo_events=[(0.0, 120.0)],
    )

    assert were_written is False
    # The fixture has 2 locators → 2 sections
    assert len(sections) == 2
    # User-provided names must be preserved verbatim, NOT renamed to "Section N"
    assert sections[0].name == "Intro perso"
    assert sections[1].name == "Drop"
    # Beats taken from the fixture's Time values
    assert sections[0].start_beats == pytest.approx(0.0, abs=1e-3)
    assert sections[1].start_beats == pytest.approx(16.0, abs=1e-3)

    # The source .als must not have been overwritten with a "_with_sections" variant
    assert not als_path.with_name(als_path.stem + "_with_sections.als").exists()


# ---------------------------------------------------------------------------
# Tempo map round-trip sanity check
# ---------------------------------------------------------------------------

def test_seconds_beats_roundtrip_piecewise_tempo():
    tempo_events = [(0.0, 120.0), (10.0, 90.0)]
    # 120 BPM for the first 10 s → 20 beats
    assert seconds_to_beats(10.0, tempo_events) == pytest.approx(20.0, abs=1e-6)
    # + 90 BPM for next 10 s → 20 + 15 = 35 beats
    assert seconds_to_beats(20.0, tempo_events) == pytest.approx(35.0, abs=1e-6)
    # inverse
    assert _beats_to_seconds(20.0, tempo_events) == pytest.approx(10.0, abs=1e-6)
    assert _beats_to_seconds(35.0, tempo_events) == pytest.approx(20.0, abs=1e-6)
