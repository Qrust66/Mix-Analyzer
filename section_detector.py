#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section Detector v2.5.2 — Feature 3 Phase A/B.

Detects musical sections from spectral analysis, or reads existing Locators
from an Ableton .als file when the user has already placed them.

Workflow (see docs/prompts/prompt_claude_code_feature_3.md):

    SI le .als ne contient AUCUN Locator :
      → detection automatique
      → ecriture des Locators "Section 1", "Section 2", ...

    SI le .als contient au moins 1 Locator :
      → skip detection, lecture des Locators existants (source de verite)

Phase B: Locator XML I/O and tempo-map conversion live in ``als_utils``.
This module delegates to that public API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from als_utils import (
    beats_to_seconds,
    read_locators,
    seconds_to_beats,
    write_locators,
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Section:
    """One detected or user-defined musical section.

    Indexing is 1-based to match the auto-generated names "Section 1" .. "Section N".
    `tracks_active`, `track_energy`, `tfp_summary`, `diagnostic_summary`
    stay empty/None in Phase A/B and are populated later by Phase C / future features.
    """

    index: int
    name: str
    start_bucket: int
    end_bucket: int
    start_seconds: float
    end_seconds: float
    start_beats: float
    end_beats: float
    total_energy_db: float
    tracks_active: List[str] = field(default_factory=list)
    track_energy: dict = field(default_factory=dict)
    tfp_summary: Optional[dict] = None
    diagnostic_summary: Optional[dict] = None


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _smooth_moving_average(arr: np.ndarray, window: int) -> np.ndarray:
    """Symmetric moving-average smoothing, preserving array length."""
    if window <= 1 or arr.size == 0:
        return arr.astype(float, copy=True)
    kernel = np.ones(int(window), dtype=float) / float(window)
    return np.convolve(arr.astype(float), kernel, mode="same")


def _collect_transition_frames(
    delta_smoothed: np.ndarray,
    threshold: float,
    min_frames_between: int,
) -> List[int]:
    """Pick frame indices where delta exceeds threshold, keeping the local peak
    within any cluster and enforcing a minimum gap between accepted transitions.
    """
    if delta_smoothed.size == 0:
        return []

    above = delta_smoothed > threshold
    transitions: List[int] = []
    i = 0
    n = delta_smoothed.size
    while i < n:
        if not above[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and above[j + 1]:
            j += 1
        local_peak = i + int(np.argmax(delta_smoothed[i : j + 1]))
        if not transitions or (local_peak - transitions[-1]) >= min_frames_between:
            transitions.append(local_peak)
        else:
            if delta_smoothed[local_peak] > delta_smoothed[transitions[-1]]:
                transitions[-1] = local_peak
        i = j + 1
    return transitions


def detect_sections_from_audio(
    delta_spectrum: np.ndarray,
    zone_energy: np.ndarray,
    times: np.ndarray,
    threshold_multiplier: float = 2.5,
    tempo_events: Optional[List[Tuple[float, float]]] = None,
    smoothing_window: int = 3,
    min_frames_between: int = 4,
) -> List[Section]:
    """Detect sections from spectral-change analysis.

    Algorithm:
        1. Smooth delta_spectrum with a moving average (window = smoothing_window).
        2. Threshold = median(delta_spectrum) * threshold_multiplier.
        3. Frames where smoothed delta > threshold are candidate transitions.
        4. Transitions closer than min_frames_between are merged.
        5. Each segment between transitions becomes a Section, named
           "Section 1" .. "Section N" (1-indexed).

    Args:
        delta_spectrum: 1-D array of frame-to-frame spectral change (dB).
        zone_energy: 1-D array of total energy per frame (dB), same length.
        times: 1-D array of frame timestamps (seconds), same length.
        threshold_multiplier: Multiplier applied to the delta median.
        tempo_events: Optional tempo map. Defaults to 120 BPM constant.
        smoothing_window: Moving-average window size (frames).
        min_frames_between: Minimum gap between accepted transitions (frames).
    """
    delta = np.asarray(delta_spectrum, dtype=float)
    energy = np.asarray(zone_energy, dtype=float)
    t = np.asarray(times, dtype=float)
    if not (delta.shape == energy.shape == t.shape):
        raise ValueError(
            f"delta_spectrum, zone_energy and times must have the same shape; "
            f"got {delta.shape}, {energy.shape}, {t.shape}"
        )
    if delta.size == 0:
        return []

    smoothed = _smooth_moving_average(delta, smoothing_window)
    threshold = float(np.median(delta)) * float(threshold_multiplier)
    transitions = [x for x in _collect_transition_frames(smoothed, threshold, min_frames_between) if x > 0]

    n_frames = delta.size
    boundaries = sorted({0, *transitions, n_frames})

    sections: List[Section] = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        if end <= start:
            continue
        start_s = float(t[start])
        end_s = float(t[end - 1]) if end - 1 < n_frames else float(t[-1])
        segment_energy = energy[start:end]
        total_db = float(np.mean(segment_energy)) if segment_energy.size else -120.0
        sections.append(
            Section(
                index=len(sections) + 1,
                name=f"Section {len(sections) + 1}",
                start_bucket=int(start),
                end_bucket=int(end - 1),
                start_seconds=round(start_s, 3),
                end_seconds=round(end_s, 3),
                start_beats=round(seconds_to_beats(start_s, tempo_events), 4),
                end_beats=round(seconds_to_beats(end_s, tempo_events), 4),
                total_energy_db=round(total_db, 2),
            )
        )
    return sections


# ---------------------------------------------------------------------------
# Reading existing Locators into Sections
# ---------------------------------------------------------------------------

def _locators_to_sections(
    locators: List[dict],
    tempo_events: Optional[List[Tuple[float, float]]],
    total_duration_s: float,
    zone_energy: np.ndarray,
    times: np.ndarray,
) -> List[Section]:
    """Convert existing Locators into Sections.

    Each Locator marks the START of a section; the next Locator (or end-of-track)
    marks the end. Names come verbatim from the user's Locators — no renaming.
    """
    if not locators:
        return []

    ordered = sorted(locators, key=lambda l: l["time_beats"])
    boundaries_s = [beats_to_seconds(l["time_beats"], tempo_events) for l in ordered]
    boundaries_s.append(max(total_duration_s, boundaries_s[-1]))

    n_frames = times.size
    sections: List[Section] = []
    for i in range(len(ordered)):
        start_s = boundaries_s[i]
        end_s = boundaries_s[i + 1]
        start_bucket = int(np.searchsorted(times, start_s, side="left"))
        end_bucket = int(np.searchsorted(times, end_s, side="left")) - 1
        start_bucket = max(0, min(start_bucket, n_frames - 1))
        end_bucket = max(start_bucket, min(end_bucket, n_frames - 1))
        segment_energy = zone_energy[start_bucket : end_bucket + 1]
        total_db = float(np.mean(segment_energy)) if segment_energy.size else -120.0
        end_beats = (
            ordered[i + 1]["time_beats"]
            if i + 1 < len(ordered)
            else seconds_to_beats(end_s, tempo_events)
        )
        sections.append(
            Section(
                index=i + 1,
                name=ordered[i]["name"] or f"Section {i + 1}",
                start_bucket=start_bucket,
                end_bucket=end_bucket,
                start_seconds=round(start_s, 3),
                end_seconds=round(end_s, 3),
                start_beats=round(ordered[i]["time_beats"], 4),
                end_beats=round(end_beats, 4),
                total_energy_db=round(total_db, 2),
            )
        )
    return sections


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------

def get_or_detect_sections(
    als_path: Path,
    delta_spectrum: np.ndarray,
    zone_energy: np.ndarray,
    times: np.ndarray,
    tempo_events: Optional[List[Tuple[float, float]]] = None,
    write_output_path: Optional[Path] = None,
) -> Tuple[List[Section], bool]:
    """Read Locators from the .als if present; otherwise detect and write new ones.

    Args:
        als_path: Path to the source .als file (never overwritten).
        delta_spectrum, zone_energy, times: Audio analysis arrays, same shape.
        tempo_events: Optional piecewise-constant tempo map.
        write_output_path: Optional destination for the newly-generated .als.

    Returns:
        ``(sections, were_written)``. ``were_written`` is True iff Locators did
        not exist and we wrote them.
    """
    als_path = Path(als_path)
    existing = read_locators(als_path)
    zone_arr = np.asarray(zone_energy, dtype=float)
    times_arr = np.asarray(times, dtype=float)

    if existing:
        total_duration = float(times_arr[-1]) if times_arr.size else 0.0
        sections = _locators_to_sections(
            existing,
            tempo_events=tempo_events,
            total_duration_s=total_duration,
            zone_energy=zone_arr,
            times=times_arr,
        )
        return sections, False

    sections = detect_sections_from_audio(
        delta_spectrum=delta_spectrum,
        zone_energy=zone_energy,
        times=times,
        tempo_events=tempo_events,
    )
    if sections:
        locator_dicts = [
            {"time_beats": s.start_beats, "name": s.name, "annotation": ""}
            for s in sections
        ]
        write_locators(
            als_path=als_path,
            new_locators=locator_dicts,
            output_path=write_output_path,
        )
    return sections, True
