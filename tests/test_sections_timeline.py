#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the _sections_timeline sheet (Feature 3 Phase C)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import Workbook  # noqa: E402

from section_detector import (  # noqa: E402
    Section,
    build_sections_timeline_sheet,
    detect_accumulations_in_section,
    detect_conflicts_in_section,
    enrich_sections_with_track_stats,
    generate_observations,
    get_zone_order,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@dataclass
class _FakePeakTraj:
    points: List[Tuple[int, float, float]] = field(default_factory=list)


def _make_section(index: int, start: int, end: int, total_energy_db: float) -> Section:
    return Section(
        index=index,
        name=f"Section {index}",
        start_bucket=start,
        end_bucket=end,
        start_seconds=float(start),
        end_seconds=float(end),
        start_beats=float(start * 2),
        end_beats=float(end * 2),
        total_energy_db=total_energy_db,
    )


def _zone_arrays_for(level_db: float, n_frames: int, zones_with_energy: List[str]) -> dict:
    """Build a {zone: array(n_frames)} dict where listed zones sit at level_db
    and every other zone is silent (-120 dB)."""
    zones = {
        z: np.full(n_frames, -120.0, dtype=float)
        for z in get_zone_order()
    }
    for z in zones_with_energy:
        zones[z] = np.full(n_frames, float(level_db), dtype=float)
    return zones


# ---------------------------------------------------------------------------
# Section enrichment + tracks_active / track_energy
# ---------------------------------------------------------------------------

def test_enrich_populates_tracks_active_and_track_energy():
    n = 30
    sections = [_make_section(1, 0, n - 1, total_energy_db=-20.0)]
    all_tracks = {
        "Kick":      _zone_arrays_for(-10.0, n, ["sub", "low"]),
        "Pad":       _zone_arrays_for(-35.0, n, ["mid", "presence"]),
        "Silent":    _zone_arrays_for(-80.0, n, ["air"]),
    }

    enrich_sections_with_track_stats(sections, all_tracks)

    section = sections[0]
    # Kick and Pad are active (above -40 dB in at least one zone). Silent is not.
    assert set(section.tracks_active) == {"Kick", "Pad"}
    # track_energy has every track and every zone
    assert set(section.track_energy.keys()) == {"Kick", "Pad", "Silent"}
    for zones in section.track_energy.values():
        assert set(zones.keys()) == set(get_zone_order())
    # sanity on values
    assert section.track_energy["Kick"]["sub"] == pytest.approx(-10.0, abs=0.01)
    assert section.track_energy["Pad"]["mid"] == pytest.approx(-35.0, abs=0.01)


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def test_detect_conflicts_scores_and_severity_order():
    n = 30
    section = _make_section(1, 0, n - 1, total_energy_db=-10.0)

    # Pair 1: near-identical high energy in the same zone -> critical
    # Pair 2: both above threshold but 20 dB apart -> moderate
    # Pair 3: one track below threshold -> skipped
    all_tracks = {
        "TrackA": _zone_arrays_for(-5.0,  n, ["low"]),
        "TrackB": _zone_arrays_for(-6.0,  n, ["low"]),
        "TrackC": _zone_arrays_for(-15.0, n, ["mid"]),
        "TrackD": _zone_arrays_for(-35.0, n, ["mid"]),
        "TrackE": _zone_arrays_for(-60.0, n, ["presence"]),
    }
    enrich_sections_with_track_stats([section], all_tracks)

    conflicts = detect_conflicts_in_section(section)

    # Must surface the critical A/B conflict first.
    assert conflicts[0]["track_a"] == "TrackA"
    assert conflicts[0]["track_b"] == "TrackB"
    assert conflicts[0]["severity"] == "critical"
    assert conflicts[0]["zone"] == "low"

    # TrackC/TrackD: overlap = 1 - 20/30 = 0.333, level_weight = (-25+40)/40 = 0.375
    #               score = 0.125 -> below 0.4 => skipped
    pair_c_d = [c for c in conflicts if {c["track_a"], c["track_b"]} == {"TrackC", "TrackD"}]
    assert pair_c_d == [], "weak conflict must be skipped"

    # Pairs involving TrackE (-60 dB) must never appear.
    assert all("TrackE" not in (c["track_a"], c["track_b"]) for c in conflicts)

    # severities are in order critical-first
    severity_order = [c["severity"] for c in conflicts]
    assert severity_order == sorted(
        severity_order, key=lambda s: 0 if s == "critical" else 1
    )


# ---------------------------------------------------------------------------
# Accumulation detection
# ---------------------------------------------------------------------------

def test_detect_accumulations_clusters_peaks_within_semitone():
    section = _make_section(1, 0, 99, total_energy_db=-15.0)
    # 5 tracks with peaks around 247 Hz (inside 1 semitone of each other)
    peaks = {
        "TrackA": [_FakePeakTraj(points=[(10, 246.0, -5.0)])],
        "TrackB": [_FakePeakTraj(points=[(20, 247.5, -8.0)])],
        "TrackC": [_FakePeakTraj(points=[(30, 248.0, -10.0)])],
        "TrackD": [_FakePeakTraj(points=[(40, 249.0, -12.0)])],
        # inside the section, plus an unrelated peak far away
        "TrackE": [_FakePeakTraj(points=[(50, 250.0, -14.0), (60, 4000.0, -20.0)])],
        # this track is outside the section frames -> must not count
        "Outsider": [_FakePeakTraj(points=[(500, 247.0, -5.0)])],
    }
    accs = detect_accumulations_in_section(section, peaks)

    assert len(accs) == 1
    assert accs[0]["n_tracks"] == 5
    assert accs[0]["freq_hz"] == pytest.approx(247.7, abs=1.0)
    assert set(accs[0]["track_names"]) == {"TrackA", "TrackB", "TrackC", "TrackD", "TrackE"}


# ---------------------------------------------------------------------------
# Observations
# ---------------------------------------------------------------------------

def test_observations_cap_at_five_and_cover_priority():
    n = 30
    sections = [
        _make_section(1, 0, 9,  total_energy_db=-40.0),   # low energy
        _make_section(2, 10, 19, total_energy_db=-20.0),  # mid
        _make_section(3, 20, 29, total_energy_db=-5.0),   # top energy (section under test)
    ]
    # lots of active tracks in section 3 to exceed density thresholds
    all_tracks = {
        f"Track{i:02d}": _zone_arrays_for(-5.0, n, ["low"]) for i in range(25)
    }
    # ensure some tracks appear only in section 1 (silent in section 3)
    all_tracks["Absentee"] = (
        {z: np.full(n, -120.0, dtype=float) for z in get_zone_order()}
    )
    all_tracks["Absentee"]["presence"] = np.concatenate(
        [np.full(10, -5.0), np.full(20, -120.0)]
    )

    enrich_sections_with_track_stats(sections, all_tracks)
    conflicts = detect_conflicts_in_section(sections[2])
    observations = generate_observations(
        sections[2],
        conflicts=conflicts,
        accumulations=[],
        all_sections=sections,
        all_tracks_zone_energy=all_tracks,
    )

    assert len(observations) <= 5
    assert len(observations) >= 2
    # Must mention density / energy qualification
    assert any("dense" in o.lower() or "densite" in o.lower() or "tracks actives" in o.lower()
               for o in observations)


# ---------------------------------------------------------------------------
# Sheet rendering
# ---------------------------------------------------------------------------

def test_build_sheet_silent_noop_when_no_sections():
    wb = Workbook()
    build_sections_timeline_sheet(
        workbook=wb,
        sections=[],
        all_tracks_zone_energy={},
    )
    assert "_sections_timeline" not in wb.sheetnames


def test_build_sheet_contains_master_view_and_per_section_blocks():
    n = 30
    sections = [
        _make_section(1, 0, 14,  total_energy_db=-25.0),
        _make_section(2, 15, 29, total_energy_db=-10.0),
    ]
    all_tracks = {
        "Kick":    _zone_arrays_for(-5.0,  n, ["sub", "low"]),
        "Bass":    _zone_arrays_for(-7.0,  n, ["low"]),
        "Pad":     _zone_arrays_for(-20.0, n, ["mid"]),
    }

    wb = Workbook()
    build_sections_timeline_sheet(
        workbook=wb,
        sections=sections,
        all_tracks_zone_energy=all_tracks,
    )
    assert "_sections_timeline" in wb.sheetnames

    ws = wb["_sections_timeline"]
    text = "\n".join(
        " | ".join(str(c.value) for c in row if c.value is not None)
        for row in ws.iter_rows()
    )

    # master view
    assert "VUE MAITRE" in text
    assert "Conflits crit." in text
    assert "Conflits mod." in text

    # per-section blocks
    assert "SECTION 1" in text
    assert "SECTION 2" in text
    assert "TRACKS ACTIVES PAR ZONE D'ENERGIE DOMINANTE" in text
    assert "CONFLITS DE FREQUENCES" in text
    assert "ACCUMULATIONS" in text
    assert "PEAK MAX PAR TRACK" in text
    assert "OBSERVATIONS" in text

    # no formula anywhere (read-only guarantee)
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None and isinstance(cell.value, str):
                assert not cell.value.lstrip().startswith("="), (
                    f"cell {cell.coordinate} contains a formula: {cell.value!r}"
                )


# ---------------------------------------------------------------------------
# Conflict severity helper — threshold boundaries
# ---------------------------------------------------------------------------

def test_conflict_severity_boundaries_match_spec():
    # Minimum level for a "critical" pair under our formula:
    # overlap=1 (equal energies) + level_weight=(avg+40)/40
    # score=1*level_weight; we need score>=0.7 => avg_db >= -12
    n = 10
    section = _make_section(1, 0, n - 1, total_energy_db=0.0)

    critical_tracks = {
        "A": _zone_arrays_for(-10.0, n, ["low"]),
        "B": _zone_arrays_for(-10.0, n, ["low"]),
    }
    enrich_sections_with_track_stats([section], critical_tracks)
    confs = detect_conflicts_in_section(section)
    assert confs and confs[0]["severity"] == "critical"
    assert confs[0]["score"] >= 0.7 - 1e-6
