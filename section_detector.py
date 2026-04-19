#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section Detector v2.5.2 — Feature 3 Phase A.

Detects musical sections from spectral analysis, or reads existing Locators
from an Ableton .als file when the user has already placed them.

Workflow (see docs/prompts/prompt_claude_code_feature_3.md):

    SI le .als ne contient AUCUN Locator :
      → detection automatique
      → ecriture des Locators "Section 1", "Section 2", ...

    SI le .als contient au moins 1 Locator :
      → skip detection, lecture des Locators existants (source de verite)

The low-level Locator XML manipulation implemented here is a minimal shim
used by Phase A only. Phase B moves the production read/write into
`als_utils.py`.
"""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Section:
    """One detected or user-defined musical section.

    Indexing is 1-based to match the auto-generated names "Section 1" .. "Section N".
    `tracks_active`, `track_energy`, `tfp_summary`, `diagnostic_summary`
    stay empty/None in Phase A and are populated later by Phase C / future features.
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
# Tempo-aware conversion helpers
# ---------------------------------------------------------------------------

_DEFAULT_BPM = 120.0


def _normalize_tempo_events(
    tempo_events: Optional[List[Tuple[float, float]]],
) -> List[Tuple[float, float]]:
    """Return a sorted, deduplicated list of (time_s, bpm) starting at t=0.

    Guarantees at least one entry. A missing or empty input falls back to
    a constant 120 BPM tempo map starting at t=0.
    """
    if not tempo_events:
        return [(0.0, _DEFAULT_BPM)]

    cleaned: List[Tuple[float, float]] = []
    for t, bpm in tempo_events:
        if bpm is None or bpm <= 0:
            continue
        cleaned.append((float(max(t, 0.0)), float(bpm)))

    if not cleaned:
        return [(0.0, _DEFAULT_BPM)]

    cleaned.sort(key=lambda e: e[0])
    if cleaned[0][0] > 0.0:
        cleaned.insert(0, (0.0, cleaned[0][1]))
    return cleaned


def seconds_to_beats(
    time_s: float,
    tempo_events: Optional[List[Tuple[float, float]]] = None,
) -> float:
    """Convert a time in seconds to beats using a piecewise-constant tempo map.

    Args:
        time_s: Target time in seconds (>= 0).
        tempo_events: Sorted list of (time_s, bpm). If None/empty, 120 BPM.

    Returns:
        Beats elapsed from t=0 to time_s.
    """
    if time_s <= 0.0:
        return 0.0

    events = _normalize_tempo_events(tempo_events)
    beats = 0.0
    for i, (t_start, bpm) in enumerate(events):
        t_end = events[i + 1][0] if i + 1 < len(events) else float("inf")
        if time_s <= t_start:
            break
        segment_end = min(time_s, t_end)
        beats += (segment_end - t_start) * (bpm / 60.0)
        if time_s <= t_end:
            break
    return beats


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
        # local peak inside [i, j]
        local_peak = i + int(np.argmax(delta_smoothed[i : j + 1]))
        if not transitions or (local_peak - transitions[-1]) >= min_frames_between:
            transitions.append(local_peak)
        else:
            # keep the stronger of the two neighbouring transitions
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
        zone_energy: 1-D array of total energy per frame (dB). Must match
            delta_spectrum in length.
        times: 1-D array of frame timestamps (seconds). Must match length.
        threshold_multiplier: Multiplier applied to the delta median to build
            the adaptive threshold.
        tempo_events: Optional tempo map (list of (time_s, bpm)) used to
            compute beat positions. Defaults to a constant 120 BPM.
        smoothing_window: Moving-average window size (frames).
        min_frames_between: Minimum gap between accepted transitions (frames).

    Returns:
        List of `Section` in temporal order. At least one section is always
        returned for non-empty input.
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
    transitions = _collect_transition_frames(smoothed, threshold, min_frames_between)

    # Drop a transition right at frame 0 — there is no "previous" section.
    transitions = [x for x in transitions if x > 0]

    n_frames = delta.size
    boundaries = [0, *transitions, n_frames]
    # dedupe while preserving order
    seen = set()
    unique_boundaries = []
    for b in boundaries:
        if b not in seen:
            seen.add(b)
            unique_boundaries.append(b)
    unique_boundaries.sort()

    sections: List[Section] = []
    for i in range(len(unique_boundaries) - 1):
        start = unique_boundaries[i]
        end = unique_boundaries[i + 1]
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
# Locator I/O — minimal Phase A shim (replaced by als_utils in Phase B)
# ---------------------------------------------------------------------------

_LOCATOR_BLOCK_RE = re.compile(
    r"<Locators>\s*<Locators>(?P<body>.*?)</Locators>\s*</Locators>",
    re.DOTALL,
)
_LOCATOR_ENTRY_RE = re.compile(r"<Locator\s+Id=\"(?P<id>\d+)\">(?P<inner>.*?)</Locator>", re.DOTALL)


def _read_als_xml(als_path: Path) -> str:
    with gzip.open(als_path, "rb") as f:
        return f.read().decode("utf-8")


def _extract_value(tag: str, xml_fragment: str) -> Optional[str]:
    m = re.search(rf"<{tag}\s+Value=\"(?P<v>[^\"]*)\"\s*/>", xml_fragment)
    return m.group("v") if m else None


def _parse_locators(xml: str) -> List[dict]:
    block = _LOCATOR_BLOCK_RE.search(xml)
    if not block:
        return []
    locators: List[dict] = []
    for m in _LOCATOR_ENTRY_RE.finditer(block.group("body")):
        inner = m.group("inner")
        locators.append(
            {
                "id": int(m.group("id")),
                "time_beats": float(_extract_value("Time", inner) or 0.0),
                "name": _extract_value("Name", inner) or "",
                "annotation": _extract_value("Annotation", inner) or "",
            }
        )
    return locators


def _locators_to_sections(
    locators: List[dict],
    tempo_events: Optional[List[Tuple[float, float]]],
    total_duration_s: float,
    delta_spectrum: np.ndarray,
    zone_energy: np.ndarray,
    times: np.ndarray,
) -> List[Section]:
    """Convert existing Locators into Sections, using beats as the source of truth.

    Each Locator marks the START of a section; the next Locator (or end-of-track)
    marks the end. Section names are taken verbatim from the user's Locator names.
    """
    if not locators:
        return []

    # Build inverse beats->seconds lookup via the tempo map
    ordered = sorted(locators, key=lambda l: l["time_beats"])
    boundaries_s = [_beats_to_seconds(l["time_beats"], tempo_events) for l in ordered]
    # Append the track end as the final boundary
    boundaries_s.append(max(total_duration_s, boundaries_s[-1]))

    n_frames = delta_spectrum.size
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
        sections.append(
            Section(
                index=i + 1,
                name=ordered[i]["name"] or f"Section {i + 1}",
                start_bucket=start_bucket,
                end_bucket=end_bucket,
                start_seconds=round(start_s, 3),
                end_seconds=round(end_s, 3),
                start_beats=round(ordered[i]["time_beats"], 4),
                end_beats=round(
                    ordered[i + 1]["time_beats"]
                    if i + 1 < len(ordered)
                    else seconds_to_beats(end_s, tempo_events),
                    4,
                ),
                total_energy_db=round(total_db, 2),
            )
        )
    return sections


def _beats_to_seconds(
    beats: float,
    tempo_events: Optional[List[Tuple[float, float]]],
) -> float:
    """Inverse of seconds_to_beats over a piecewise-constant tempo map."""
    if beats <= 0.0:
        return 0.0
    events = _normalize_tempo_events(tempo_events)
    accumulated_beats = 0.0
    t = 0.0
    for i, (t_start, bpm) in enumerate(events):
        t_end = events[i + 1][0] if i + 1 < len(events) else float("inf")
        segment_duration = t_end - t_start if t_end != float("inf") else None
        segment_beats = (
            segment_duration * (bpm / 60.0) if segment_duration is not None else float("inf")
        )
        if accumulated_beats + segment_beats >= beats:
            remaining = beats - accumulated_beats
            t = t_start + remaining * (60.0 / bpm)
            return t
        accumulated_beats += segment_beats
        t = t_end
    return t


def _build_locator_xml(
    sections: List[Section],
    existing_max_id: int,
) -> str:
    """Build the inner XML for the Locators block from a list of Sections."""
    lines = []
    next_id = existing_max_id + 1
    for sec in sections:
        lines.append(
            f"\t\t\t<Locator Id=\"{next_id}\">\n"
            f"\t\t\t\t<Time Value=\"{sec.start_beats}\" />\n"
            f"\t\t\t\t<Name Value=\"{sec.name}\" />\n"
            f"\t\t\t\t<Annotation Value=\"\" />\n"
            f"\t\t\t\t<IsSongStart Value=\"false\" />\n"
            f"\t\t\t\t<LockEnvelope Value=\"0\" />\n"
            f"\t\t\t</Locator>"
        )
        next_id += 1
    return "\n".join(lines)


def _inject_locators(xml: str, sections: List[Section]) -> Tuple[str, int]:
    """Insert Locator entries into LiveSet/Locators/Locators, preserving existing ones.

    Returns (new_xml, locators_written).
    """
    if not sections:
        return xml, 0

    existing = _parse_locators(xml)
    existing_max_id = max((loc["id"] for loc in existing), default=-1)
    new_entries = _build_locator_xml(sections, existing_max_id)

    block = _LOCATOR_BLOCK_RE.search(xml)
    if block:
        body = block.group("body").rstrip()
        if body.strip():
            merged_body = f"{body}\n{new_entries}\n\t\t"
        else:
            merged_body = f"\n{new_entries}\n\t\t"
        new_block = (
            f"<Locators>\n\t\t<Locators>{merged_body}</Locators>\n\t</Locators>"
        )
        new_xml = (
            xml[: block.start()]
            + new_block
            + xml[block.end() :]
        )
        return new_xml, len(sections)

    # No Locators block at all — insert a fresh one inside <LiveSet>.
    inner = f"<Locators>\n\t\t<Locators>\n{new_entries}\n\t\t</Locators>\n\t</Locators>"
    # Heuristic: place right before </LiveSet>. Fall back to appending.
    idx = xml.rfind("</LiveSet>")
    if idx == -1:
        return xml + inner, len(sections)
    return xml[:idx] + "\t" + inner + "\n" + xml[idx:], len(sections)


def _write_locators_minimal(
    als_path: Path,
    sections: List[Section],
    output_path: Optional[Path] = None,
) -> Tuple[Path, int]:
    """Phase A helper: inject Locators and save to a sibling .als file.

    Never overwrites the source. Phase B replaces this with a fully featured
    implementation in `als_utils.py`.
    """
    als_path = Path(als_path)
    if output_path is None:
        output_path = als_path.with_name(als_path.stem + "_with_sections.als")
    xml = _read_als_xml(als_path)
    new_xml, written = _inject_locators(xml, sections)
    Path(output_path).write_bytes(gzip.compress(new_xml.encode("utf-8")))
    return Path(output_path), written


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
        als_path: Path to the source .als file.
        delta_spectrum, zone_energy, times: Audio analysis arrays, same shape.
        tempo_events: Optional piecewise-constant tempo map.
        write_output_path: Optional destination for the newly-generated .als.
            Defaults to `<als_path stem>_with_sections.als` in the same folder.

    Returns:
        (sections, were_written).
        `were_written` is True when Locators did not exist and we wrote them.
    """
    als_path = Path(als_path)
    xml = _read_als_xml(als_path)
    existing = _parse_locators(xml)
    total_duration = float(times[-1]) if len(times) else 0.0

    if existing:
        sections = _locators_to_sections(
            existing,
            tempo_events,
            total_duration_s=total_duration,
            delta_spectrum=np.asarray(delta_spectrum, dtype=float),
            zone_energy=np.asarray(zone_energy, dtype=float),
            times=np.asarray(times, dtype=float),
        )
        return sections, False

    sections = detect_sections_from_audio(
        delta_spectrum=delta_spectrum,
        zone_energy=zone_energy,
        times=times,
        tempo_events=tempo_events,
    )
    if sections:
        _write_locators_minimal(als_path, sections, output_path=write_output_path)
    return sections, True
