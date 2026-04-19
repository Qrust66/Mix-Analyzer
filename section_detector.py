#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section Detector v2.6.0 — Feature 3 (complete).

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
    # Fraction of buckets in the section where ``track_energy`` > presence
    # threshold, per track per zone. Populated by
    # :func:`enrich_sections_with_track_stats`. Used as the gate for
    # "dominant in zone" / "active in section" checks (Fix 2 — the
    # plain mean-based gate collapses under heavy NaN masking).
    track_presence: dict = field(default_factory=dict)
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


def _detect_energy_transitions(
    total_energy_db: np.ndarray,
    threshold_db: float = 6.0,
) -> List[int]:
    """Detect transitions from bucket-to-bucket total-energy jumps.

    Args:
        total_energy_db: 1-D array of total energy per bucket (dB). NaN-safe.
        threshold_db: A bucket is a transition when its absolute dB delta
            vs the previous bucket exceeds this value.

    Returns:
        Bucket indices flagged as transitions (the first of each jump).
    """
    arr = np.asarray(total_energy_db, dtype=float)
    if arr.size < 2:
        return []
    deltas = np.abs(np.diff(arr))
    # NaN deltas (either neighbour NaN) cannot flag a transition.
    return [int(i + 1) for i, d in enumerate(deltas) if np.isfinite(d) and d > threshold_db]


def _merge_close_transitions(transitions, min_frames_between: int) -> List[int]:
    """Merge transitions that are closer than ``min_frames_between`` apart.

    Keeps the earliest transition in each cluster so the first boundary is
    aligned with the first jump detected.
    """
    if not transitions:
        return []
    ordered = sorted(set(int(t) for t in transitions))
    merged = [ordered[0]]
    for t in ordered[1:]:
        if t - merged[-1] >= min_frames_between:
            merged.append(t)
    return merged


def detect_sections_from_audio(
    delta_spectrum: np.ndarray,
    zone_energy: np.ndarray,
    times: np.ndarray,
    threshold_multiplier: float = 1.5,
    energy_threshold_db: float = 6.0,
    tempo_events: Optional[List[Tuple[float, float]]] = None,
    smoothing_window: int = 3,
    min_frames_between: int = 4,
) -> List[Section]:
    """Detect sections from spectral-change + total-energy analysis.

    Algorithm:
        1. Spectral transitions: smooth ``delta_spectrum`` with a moving
           average, threshold = median(delta) * ``threshold_multiplier``,
           flag frames crossing the threshold (internal min-gap fusion).
        2. Energy transitions: flag buckets where the *total* zone energy
           jumps by more than ``energy_threshold_db`` vs. the previous bucket.
        3. Merge both sets, then fuse transitions closer than
           ``min_frames_between`` apart.
        4. Each segment between transitions becomes a ``Section``, named
           "Section 1" .. "Section N" (1-indexed).

    On dense mixes where every track plays throughout the song the spectral
    delta varies little — the energy-transition pass surfaces the drops and
    breaks that the spectral pass misses.

    Args:
        delta_spectrum: 1-D array of frame-to-frame spectral change (dB).
        zone_energy: Either a 1-D array (n_frames,) of total energy per
            frame in dB, or a 2-D array (n_zones, n_frames). 2-D inputs are
            collapsed via a NaN-safe linear sum before further analysis.
        times: 1-D array of frame timestamps (seconds).
        threshold_multiplier: Spectral-threshold multiplier applied to the
            delta median. Defaults to 1.5 (lowered from 2.5 — 2.5 was too
            strict for dense mixes, producing 1 section for a 4-minute song).
        energy_threshold_db: Minimum absolute dB delta between consecutive
            buckets' total energy to flag an energy transition.
        tempo_events: Optional tempo map. Defaults to 120 BPM constant.
        smoothing_window: Moving-average window size (frames) for delta.
        min_frames_between: Minimum gap between accepted transitions (frames).
    """
    delta = np.asarray(delta_spectrum, dtype=float)
    t = np.asarray(times, dtype=float)

    ze_arr = np.asarray(zone_energy, dtype=float)
    if ze_arr.ndim == 2:
        with np.errstate(all="ignore"):
            linear = np.nansum(np.power(10.0, ze_arr / 10.0), axis=0)
        total_energy_1d = 10.0 * np.log10(np.maximum(linear, 1e-12))
    elif ze_arr.ndim == 1:
        total_energy_1d = ze_arr
    else:
        raise ValueError(
            f"zone_energy must be 1-D or 2-D; got shape {ze_arr.shape}"
        )

    if delta.shape != t.shape or total_energy_1d.shape != delta.shape:
        raise ValueError(
            f"delta_spectrum, zone_energy (or its column axis) and times must "
            f"share the same frame count; got delta={delta.shape}, "
            f"energy={total_energy_1d.shape}, times={t.shape}"
        )
    if delta.size == 0:
        return []

    # --- Spectral transitions
    smoothed = _smooth_moving_average(delta, smoothing_window)
    threshold = float(np.median(delta)) * float(threshold_multiplier)
    spectral_transitions = [
        x for x in _collect_transition_frames(smoothed, threshold, min_frames_between)
        if x > 0
    ]

    # --- Energy transitions (NEW — dense-mix rescue)
    energy_transitions = [
        x for x in _detect_energy_transitions(total_energy_1d, energy_threshold_db)
        if x > 0
    ]

    # --- Merge both candidate sets, refuse anything closer than min_frames_between
    combined = _merge_close_transitions(
        spectral_transitions + energy_transitions, min_frames_between
    )

    n_frames = delta.size
    boundaries = sorted({0, *combined, n_frames})

    sections: List[Section] = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        if end <= start:
            continue
        start_s = float(t[start])
        end_s = float(t[end - 1]) if end - 1 < n_frames else float(t[-1])
        segment_energy = total_energy_1d[start:end]
        if segment_energy.size:
            with np.errstate(all="ignore"):
                total_db = float(np.nanmean(segment_energy))
            if not np.isfinite(total_db):
                total_db = -120.0
        else:
            total_db = -120.0
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


# ---------------------------------------------------------------------------
# Phase C — per-section analysis helpers
# ---------------------------------------------------------------------------

# Standard zone order (matches spectral_evolution.ZONE_LABELS).
_ZONE_ORDER: Tuple[str, ...] = (
    "sub", "low", "mud", "body", "low_mid",
    "mid", "presence", "sibilance", "air",
)
_ZONE_LABELS: dict = {
    "sub":       "Sub (20-80 Hz)",
    "low":       "Low (80-250 Hz)",
    "mud":       "Mud (200-500 Hz)",
    "body":      "Body (250-800 Hz)",
    "low_mid":   "Low-Mid (500-2 kHz)",
    "mid":       "Mid (1-4 kHz)",
    "presence":  "Presence (2-5 kHz)",
    "sibilance": "Sibilance (5-10 kHz)",
    "air":       "Air (10-20 kHz)",
}

ACTIVE_THRESHOLD_DB = -40.0  # deprecated alias; prefer PRESENCE_THRESHOLD_DB
PRESENCE_THRESHOLD_DB = -30.0
MIN_PRESENCE_RATIO = 0.20
CONFLICT_CRITICAL = 0.7
CONFLICT_MODERATE = 0.4

# Accumulation defaults tuned against real Acid Drops data (smoke test run):
# with min_tracks=4 / min_amp=-30 dB we got ~65 accumulations per section
# (signal lost in noise). Raising both filters keeps only the real buildups.
# Fix 3: ``min_duration_buckets`` keeps one-bucket flashes from surfacing as
# accumulations — a real musical buildup must persist for a few buckets.
ACCUMULATION_MIN_TRACKS = 6
ACCUMULATION_MIN_AMP_DB = -25.0
ACCUMULATION_MIN_DURATION = 3

# Track names that almost certainly represent bounces / busses rather than
# individual instruments. Used by build_sections_timeline_sheet to warn the
# caller when filtering was apparently forgotten upstream.
_SUSPECT_NON_INDIVIDUAL_PATTERNS: Tuple[str, ...] = (
    "BUS ",
    "_HIRES_ALL",
    "Full Mix",
    "FullMix",
    "Master",
)


def _as_zone_arrays(zone_energy_entry) -> dict:
    """Coerce a per-track entry into ``{zone_name: np.ndarray}``.

    Accepts a ``ZoneEnergy`` dataclass (with a ``.zones`` attribute) or a plain
    dict of arrays. Non-matching shapes are left to the caller to validate.
    """
    if hasattr(zone_energy_entry, "zones"):
        return dict(zone_energy_entry.zones)
    if isinstance(zone_energy_entry, dict):
        return zone_energy_entry
    raise TypeError(
        f"Unsupported zone-energy entry: {type(zone_energy_entry).__name__}; "
        "expected ZoneEnergy or dict[str, ndarray]."
    )


def _section_frame_slice(section: Section, n_frames: int) -> slice:
    start = max(0, min(int(section.start_bucket), n_frames - 1))
    end = max(start, min(int(section.end_bucket) + 1, n_frames))
    return slice(start, end)


def _track_segment_stats(
    zone_arrays: dict,
    frame_slice: slice,
    presence_threshold_db: float,
) -> tuple:
    """Return ``({zone: representative_db}, {zone: presence_ratio})`` for one
    track restricted to ``frame_slice``.

    The representative dB is a NaN-safe ``nanmax`` over the segment so a
    track masked in 80% of the section still reports the level it plays at
    when audible.  ``presence_ratio`` is the fraction of buckets whose
    energy is finite AND above ``presence_threshold_db``.
    """
    level: dict = {}
    presence: dict = {}
    for zone in _ZONE_ORDER:
        arr = zone_arrays.get(zone)
        if arr is None:
            level[zone] = -120.0
            presence[zone] = 0.0
            continue
        segment = np.asarray(arr, dtype=float)[frame_slice]
        if segment.size == 0:
            level[zone] = -120.0
            presence[zone] = 0.0
            continue
        with np.errstate(all="ignore"):
            finite_mask = np.isfinite(segment)
            if finite_mask.any():
                level[zone] = float(np.nanmax(segment))
                present = finite_mask & (segment > presence_threshold_db)
                presence[zone] = float(np.sum(present)) / float(segment.size)
            else:
                level[zone] = -120.0
                presence[zone] = 0.0
    return level, presence


def _is_track_active_in_section(
    zone_arrays_slice: dict,
    presence_threshold_db: float = PRESENCE_THRESHOLD_DB,
    min_presence_ratio: float = MIN_PRESENCE_RATIO,
) -> bool:
    """True when the track plays ``min_presence_ratio`` of the section in >=1 zone.

    NaN-friendly: masked frames (``np.nan``) count as neither present nor
    absent; the ratio is measured against the segment length.

    Args:
        zone_arrays_slice: ``{zone_name: np.ndarray of bucket dB}`` already
            restricted to the section.
        presence_threshold_db: Bucket is "present" when its energy is above
            this level in at least one zone.
        min_presence_ratio: Minimum fraction of buckets that must be
            "present" for the track to count as active.
    """
    if not zone_arrays_slice:
        return False
    n_buckets = max((len(a) for a in zone_arrays_slice.values()), default=0)
    if n_buckets == 0:
        return False
    stacked = np.stack(
        [np.asarray(a, dtype=float) for a in zone_arrays_slice.values()]
    )
    # Short-circuit on fully-masked tracks so ``nanmax`` does not emit a
    # ``RuntimeWarning: All-NaN slice`` during normal runs.
    if not np.isfinite(stacked).any():
        return False
    import warnings as _warnings
    with np.errstate(all="ignore"), _warnings.catch_warnings():
        _warnings.simplefilter("ignore", RuntimeWarning)
        max_per_bucket = np.nanmax(stacked, axis=0)
    present = np.isfinite(max_per_bucket) & (max_per_bucket > presence_threshold_db)
    return bool(np.sum(present) / float(n_buckets) >= min_presence_ratio)


def enrich_sections_with_track_stats(
    sections: List[Section],
    all_tracks_zone_energy: dict,
    presence_threshold_db: float = PRESENCE_THRESHOLD_DB,
    min_presence_ratio: float = MIN_PRESENCE_RATIO,
) -> List[Section]:
    """Populate ``tracks_active``, ``track_energy`` and ``track_presence``
    on each section in place.

    Fix 2 — a track is "active" in a section when it has energy above
    ``presence_threshold_db`` in at least ``min_presence_ratio`` of the
    section's buckets, in *any* zone.  The previous "mean > threshold"
    rule collapsed under heavy NaN masking (tracks with an active
    audibility mask showed a misleadingly low mean and dropped out).

    ``track_energy[track][zone]`` stores the representative level (NaN-safe
    ``nanmax`` over the segment) so per-zone listings and conflict scoring
    can still display meaningful dB values.  ``track_presence[track][zone]``
    carries the per-zone presence ratio for downstream gating.

    Args:
        sections: Sections to enrich (modified in place).
        all_tracks_zone_energy: ``{track_name: ZoneEnergy or dict[zone, ndarray]}``.
        presence_threshold_db: dB threshold used when counting "present" buckets.
        min_presence_ratio: Minimum bucket ratio above threshold to count
            a track as active.
    """
    if not sections:
        return sections

    # derive n_frames from any track
    n_frames = 0
    for entry in all_tracks_zone_energy.values():
        arrays = _as_zone_arrays(entry)
        for arr in arrays.values():
            n_frames = max(n_frames, len(arr))
        if n_frames:
            break

    for section in sections:
        section.track_energy = {}
        section.track_presence = {}
        section.tracks_active = []
        if n_frames == 0:
            continue
        frame_slice = _section_frame_slice(section, n_frames)
        for track_name, entry in all_tracks_zone_energy.items():
            arrays = _as_zone_arrays(entry)
            level, presence = _track_segment_stats(
                arrays, frame_slice, presence_threshold_db
            )
            section.track_energy[track_name] = {
                z: round(v, 2) for z, v in level.items()
            }
            section.track_presence[track_name] = {
                z: round(v, 3) for z, v in presence.items()
            }
            # Active if the track crosses presence in at least one zone
            if any(ratio >= min_presence_ratio for ratio in presence.values()):
                section.tracks_active.append(track_name)
    return sections


def _severity(score: float) -> Optional[str]:
    if score >= CONFLICT_CRITICAL:
        return "critical"
    if score >= CONFLICT_MODERATE:
        return "moderate"
    return None


def detect_conflicts_in_section(
    section: Section,
    min_presence_ratio: float = MIN_PRESENCE_RATIO,
) -> List[dict]:
    """Pair-wise, zone-wise conflicts within this section.

    Score formula (see feature_3 Phase C Q3):
        overlap      = max(0, 1 - abs(A_db - B_db) / 30)
        level_weight = max(0, (avg_db + 40) / 40)
        score        = overlap * level_weight

    Gate (Fix 2): both tracks must have ``track_presence[zone] >=
    min_presence_ratio`` in the zone under consideration.  Gating on the
    presence ratio rather than on the stored dB level keeps the conflict
    count aligned with the "dominant in zone" listings: a track that only
    flashes loudly once in the section no longer triggers a false conflict.

    Args:
        section: Section enriched via :func:`enrich_sections_with_track_stats`.
        min_presence_ratio: Both tracks must reach this presence ratio in
            the zone to be considered in conflict.

    Returns:
        Conflict dicts sorted by severity (critical first) then score desc.
        Each dict: ``{track_a, track_b, zone, energy_a, energy_b, score, severity}``.
    """
    if not section.track_energy:
        return []

    track_presence = section.track_presence or {}

    conflicts: List[dict] = []
    tracks = list(section.track_energy.keys())
    for i in range(len(tracks)):
        for j in range(i + 1, len(tracks)):
            a = tracks[i]
            b = tracks[j]
            for zone in _ZONE_ORDER:
                pa = track_presence.get(a, {}).get(zone, 0.0)
                pb = track_presence.get(b, {}).get(zone, 0.0)
                if pa < min_presence_ratio or pb < min_presence_ratio:
                    continue
                ea = section.track_energy[a].get(zone, -120.0)
                eb = section.track_energy[b].get(zone, -120.0)
                overlap = max(0.0, 1.0 - abs(ea - eb) / 30.0)
                avg_db = (ea + eb) / 2.0
                level_weight = max(0.0, (avg_db + 40.0) / 40.0)
                score = overlap * level_weight
                severity = _severity(score)
                if severity is None:
                    continue
                conflicts.append(
                    {
                        "track_a": a,
                        "track_b": b,
                        "zone": zone,
                        "energy_a": round(ea, 2),
                        "energy_b": round(eb, 2),
                        "score": round(score, 3),
                        "severity": severity,
                    }
                )

    severity_rank = {"critical": 0, "moderate": 1}
    conflicts.sort(key=lambda c: (severity_rank[c["severity"]], -c["score"]))
    return conflicts


def _cluster_frequencies(
    freqs: List[float],
    tolerance_semitones: float,
) -> List[Tuple[float, float]]:
    """Group sorted frequencies into ``(lo, hi)`` bins at most ``tolerance_semitones`` wide.

    Chained clustering: a new frequency joins the current bin if it is within
    ``tolerance_semitones`` of the bin's *first* frequency (not the running
    mean), which keeps bin widths bounded under the stated tolerance.
    """
    if not freqs:
        return []
    ordered = sorted(set(round(f, 2) for f in freqs if f > 0))
    bins: List[List[float]] = [[ordered[0]]]
    for f in ordered[1:]:
        ref = bins[-1][0]
        semitones = abs(12.0 * np.log2(f / ref)) if ref > 0 else float("inf")
        if semitones <= tolerance_semitones:
            bins[-1].append(f)
        else:
            bins.append([f])
    return [(b[0], b[-1]) for b in bins]


def detect_accumulations_in_section(
    section: Section,
    all_tracks_peak_trajectories: Optional[dict],
    frequency_tolerance_semitones: float = 1.0,
    min_tracks_simultaneous: int = ACCUMULATION_MIN_TRACKS,
    min_amplitude_db: float = ACCUMULATION_MIN_AMP_DB,
    min_duration_buckets: int = ACCUMULATION_MIN_DURATION,
    min_tracks: Optional[int] = None,
) -> List[dict]:
    """Find frequencies where ``min_tracks_simultaneous`` or more tracks play
    *at the same bucket* for at least ``min_duration_buckets`` consecutive buckets.

    Fix 3: the previous algo counted every track that had a peak at a given
    frequency at any point in the section, producing impossible numbers on
    real mixes (Acid Drops reported 32 tracks competing at 370 Hz although
    no more than 6 played simultaneously).  Accumulations are now flagged
    only when the collision is *temporally real*.

    Algorithm:
        1. For every bucket in the section, collect ``(freq, track)`` pairs
           from every peak whose ``frame_idx`` equals the bucket and whose
           amplitude exceeds ``min_amplitude_db``. A track contributes at
           most one pair per (bucket, freq-bin).
        2. Cluster all observed frequencies into bins of at most
           ``frequency_tolerance_semitones`` wide.
        3. For each bin, count unique active tracks per bucket.
        4. Emit an accumulation when the per-bucket count stays at or above
           ``min_tracks_simultaneous`` for at least ``min_duration_buckets``
           consecutive buckets.

    Args:
        section: Section to scope to (start_bucket..end_bucket inclusive).
        all_tracks_peak_trajectories: ``{track_name: list[PeakTrajectory]}``;
            each trajectory must expose ``points`` as
            ``[(frame_idx, freq_hz, amplitude_db), ...]``.
        frequency_tolerance_semitones: Bin width for clustering nearby peaks.
        min_tracks_simultaneous: Minimum unique tracks active at the same
            bucket for the bin to qualify (default 6 — kept from Phase C
            retuning to keep sheets readable on dense mixes).
        min_amplitude_db: Peaks below this amplitude are ignored.
        min_duration_buckets: Minimum consecutive-bucket run for the
            accumulation to qualify (default 3 — one-bucket flashes are
            not musically meaningful).
        min_tracks: Deprecated alias for ``min_tracks_simultaneous``; when
            provided it overrides the new name for backwards compatibility
            with Phase C callers (test suite still uses it).

    Returns:
        Accumulation dicts sorted by ``n_tracks_simultaneous`` desc then
        duration desc. Each dict carries::

            {
                "freq_hz": float,             # cluster median freq
                "n_tracks_simultaneous": int, # max unique tracks at any bucket
                "duration_buckets": int,      # run length in buckets
                "start_bucket": int,          # first bucket of the run
                "end_bucket": int,            # last bucket of the run
                "track_names": list[str],     # union over the run
            }
    """
    if not all_tracks_peak_trajectories:
        return []
    if min_tracks is not None:
        min_tracks_simultaneous = int(min_tracks)

    start = int(section.start_bucket)
    end = int(section.end_bucket)
    if end < start:
        return []

    # (1) Collect (bucket, freq, track) triples.
    triples: List[Tuple[int, float, str]] = []
    for track_name, trajectories in all_tracks_peak_trajectories.items():
        for traj in trajectories or []:
            points = getattr(traj, "points", None) or []
            for point in points:
                try:
                    frame_idx, freq_hz, amp_db = point
                except Exception:
                    continue
                bucket = int(frame_idx)
                if bucket < start or bucket > end:
                    continue
                if amp_db < min_amplitude_db:
                    continue
                if freq_hz <= 0:
                    continue
                triples.append((bucket, float(freq_hz), track_name))

    if not triples:
        return []

    # (2) Cluster the unique frequencies observed in the section.
    freq_bins = _cluster_frequencies(
        [f for _, f, _ in triples], frequency_tolerance_semitones
    )

    def _bin_for(freq: float) -> int:
        for idx, (lo, hi) in enumerate(freq_bins):
            # bin bounds are the inclusive first/last sorted rounded freqs
            lo_s = 12.0 * np.log2(freq / lo) if lo > 0 else float("inf")
            hi_s = 12.0 * np.log2(freq / hi) if hi > 0 else float("inf")
            if (
                -frequency_tolerance_semitones <= lo_s
                and hi_s <= frequency_tolerance_semitones
            ):
                return idx
        return -1

    # (3) Per-bin per-bucket unique track sets.
    n_bins = len(freq_bins)
    n_buckets = end - start + 1
    # bucket_tracks[bin_idx][local_bucket_idx] -> set(track_names)
    bucket_tracks: List[List[set]] = [
        [set() for _ in range(n_buckets)] for _ in range(n_bins)
    ]
    # bucket_freqs[bin_idx][local_bucket_idx] -> [observed freqs] for median
    bucket_freqs: List[List[List[float]]] = [
        [[] for _ in range(n_buckets)] for _ in range(n_bins)
    ]

    for bucket, freq, track in triples:
        b = _bin_for(freq)
        if b < 0:
            continue
        local = bucket - start
        bucket_tracks[b][local].add(track)
        bucket_freqs[b][local].append(freq)

    # (4) Scan each bin for runs of consecutive buckets meeting the threshold.
    accumulations: List[dict] = []
    for b_idx in range(n_bins):
        counts = [len(s) for s in bucket_tracks[b_idx]]
        local = 0
        while local < n_buckets:
            if counts[local] < min_tracks_simultaneous:
                local += 1
                continue
            run_start = local
            while local < n_buckets and counts[local] >= min_tracks_simultaneous:
                local += 1
            run_end = local - 1
            run_length = run_end - run_start + 1
            if run_length < min_duration_buckets:
                continue

            freqs_in_run: List[float] = []
            tracks_in_run: set = set()
            max_simult = 0
            for lb in range(run_start, run_end + 1):
                freqs_in_run.extend(bucket_freqs[b_idx][lb])
                tracks_in_run.update(bucket_tracks[b_idx][lb])
                if counts[lb] > max_simult:
                    max_simult = counts[lb]

            accumulations.append(
                {
                    "freq_hz": round(float(np.median(freqs_in_run)), 1),
                    "n_tracks_simultaneous": int(max_simult),
                    "duration_buckets": int(run_length),
                    "start_bucket": int(run_start + start),
                    "end_bucket": int(run_end + start),
                    "track_names": sorted(tracks_in_run),
                }
            )

    accumulations.sort(
        key=lambda a: (-a["n_tracks_simultaneous"], -a["duration_buckets"], a["freq_hz"])
    )
    return accumulations


def _track_active_fraction(
    section: Section,
    zone_arrays: dict,
    active_threshold_db: float,
) -> float:
    """Fraction of section frames where *any* zone of this track exceeds threshold."""
    n_frames = 0
    for arr in zone_arrays.values():
        n_frames = max(n_frames, len(arr))
    if n_frames == 0:
        return 0.0
    frame_slice = _section_frame_slice(section, n_frames)
    segment_length = max(frame_slice.stop - frame_slice.start, 1)
    stacked = np.stack([
        np.asarray(zone_arrays[z], dtype=float)[frame_slice]
        for z in _ZONE_ORDER if z in zone_arrays
    ]) if zone_arrays else np.empty((0, segment_length))
    if stacked.size == 0:
        return 0.0
    frame_active = np.any(stacked > active_threshold_db, axis=0)
    return float(np.mean(frame_active))


def generate_observations(
    section: Section,
    conflicts: List[dict],
    accumulations: List[dict],
    all_sections: List[Section],
    all_tracks_zone_energy: Optional[dict] = None,
    max_observations: int = 5,
    active_threshold_db: float = ACTIVE_THRESHOLD_DB,
) -> List[str]:
    """Generate up to ``max_observations`` short observations in priority order.

    Priority (user-confirmed Phase C Q4):
        1. Section extreme (>80th or <20th percentile in total_energy_db)
        2. Density qualification (calme/moyenne/dense)
        3. Top critical conflict (if any)
        4. Top accumulation (if any)
        5. Most crowded zone (most active tracks)
        6. Tracks playing continuously (>90% of the section)
        7. Silent tracks (active elsewhere but absent in this section)
    """
    observations: List[str] = []

    # P1 — Section extreme
    if len(all_sections) >= 3:
        energies = sorted(s.total_energy_db for s in all_sections)
        p80 = energies[int(0.8 * (len(energies) - 1))]
        p20 = energies[int(0.2 * (len(energies) - 1))]
        if section.total_energy_db >= p80:
            observations.append(
                f"Section a haute energie ({section.total_energy_db:+.1f} dB) "
                f"- dans le top 20% du morceau"
            )
        elif section.total_energy_db <= p20:
            observations.append(
                f"Section a basse energie ({section.total_energy_db:+.1f} dB) "
                f"- dans le bas 20% du morceau"
            )

    # P2 — Density
    n_active = len(section.tracks_active)
    if n_active <= 7:
        density_label = "Section calme"
    elif n_active >= 20:
        density_label = "Section dense"
    else:
        density_label = "Section de densite moyenne"
    observations.append(
        f"{density_label} ({n_active} tracks actives, "
        f"energie {section.total_energy_db:+.1f} dB)"
    )

    # P3 — Top critical conflict
    critical = [c for c in conflicts if c["severity"] == "critical"]
    if critical:
        top = critical[0]
        observations.append(
            f"Conflit critique: {top['track_a']} <-> {top['track_b']} "
            f"dans {_ZONE_LABELS.get(top['zone'], top['zone'])} "
            f"(score {top['score']:.2f})"
        )

    # P4 — Top accumulation (temporal simultaneity, Fix 3)
    if accumulations:
        top_acc = accumulations[0]
        observations.append(
            f"{top_acc['n_tracks_simultaneous']} tracks simultanees autour de "
            f"{top_acc['freq_hz']:.0f} Hz pendant {top_acc['duration_buckets']} buckets"
        )

    # P5 — Most crowded zone
    zone_track_counts: dict = {z: 0 for z in _ZONE_ORDER}
    for track, zones in section.track_energy.items():
        for zone, db in zones.items():
            if db > active_threshold_db:
                zone_track_counts[zone] = zone_track_counts.get(zone, 0) + 1
    if zone_track_counts:
        busiest_zone, busiest_count = max(
            zone_track_counts.items(), key=lambda kv: kv[1]
        )
        if busiest_count >= 3:
            observations.append(
                f"Zone la plus chargee: {_ZONE_LABELS.get(busiest_zone, busiest_zone)} "
                f"({busiest_count} tracks)"
            )

    # P6 — Continuously playing tracks
    if all_tracks_zone_energy:
        continuous = []
        for track_name in section.tracks_active:
            entry = all_tracks_zone_energy.get(track_name)
            if entry is None:
                continue
            fraction = _track_active_fraction(
                section, _as_zone_arrays(entry), active_threshold_db
            )
            if fraction > 0.9:
                continuous.append(track_name)
        if continuous:
            sample = ", ".join(continuous[:3])
            more = "" if len(continuous) <= 3 else f" (+{len(continuous) - 3})"
            observations.append(f"Tracks en continu: {sample}{more}")

    # P7 — Silent tracks active elsewhere
    if len(all_sections) >= 2:
        active_elsewhere = set()
        for other in all_sections:
            if other is section:
                continue
            active_elsewhere.update(other.tracks_active)
        silent_here = sorted(active_elsewhere - set(section.tracks_active))
        if silent_here:
            sample = ", ".join(silent_here[:3])
            more = "" if len(silent_here) <= 3 else f" (+{len(silent_here) - 3})"
            observations.append(f"Silencieuses ici: {sample}{more}")

    return observations[:max_observations]


def get_zone_label(zone_key: str) -> str:
    """Human-readable label for a zone key (e.g. ``'sub'`` -> ``'Sub (20-80 Hz)'``)."""
    return _ZONE_LABELS.get(zone_key, zone_key)


def get_zone_order() -> Tuple[str, ...]:
    """Canonical zone ordering used by the timeline report."""
    return _ZONE_ORDER


# ---------------------------------------------------------------------------
# Phase C — Excel sheet rendering (_sections_timeline)
# ---------------------------------------------------------------------------

def _format_time_mmss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    return f"{total // 60}:{total % 60:02d}"


def _peak_max_per_track(
    section: Section,
    all_tracks_zone_energy: dict,
    all_tracks_peak_trajectories: Optional[dict],
    active_threshold_db: float,
) -> List[dict]:
    """Build the "Peak max par track" rows for one section.

    Uses ``all_tracks_peak_trajectories`` when available to identify the single
    loudest peak per track within the section bounds. Falls back to the
    dominant zone when no peak-trajectory data is passed in.
    ``duree_active_frac`` is the fraction of section frames where the track
    exceeds ``active_threshold_db`` in any zone.
    """
    rows: List[dict] = []
    # Determine number of frames in the time axis, used for duration fractions.
    n_frames = 0
    for entry in all_tracks_zone_energy.values():
        for arr in _as_zone_arrays(entry).values():
            n_frames = max(n_frames, len(arr))
        if n_frames:
            break
    frame_slice = _section_frame_slice(section, n_frames) if n_frames else slice(0, 0)
    section_frames = max(frame_slice.stop - frame_slice.start, 1)

    for track_name in section.tracks_active:
        zone_arrays = _as_zone_arrays(all_tracks_zone_energy[track_name])
        active_frac = _track_active_fraction(section, zone_arrays, active_threshold_db)

        peak_freq: Optional[float] = None
        peak_amp: Optional[float] = None

        trajectories = (all_tracks_peak_trajectories or {}).get(track_name)
        if trajectories:
            for traj in trajectories:
                for frame_idx, freq_hz, amp_db in getattr(traj, "points", []) or []:
                    if frame_idx < section.start_bucket or frame_idx > section.end_bucket:
                        continue
                    if peak_amp is None or amp_db > peak_amp:
                        peak_amp = float(amp_db)
                        peak_freq = float(freq_hz)

        if peak_freq is None:
            # fall back: pick the zone with max mean energy in this section
            zones = section.track_energy.get(track_name, {})
            if zones:
                best_zone, best_db = max(zones.items(), key=lambda kv: kv[1])
                peak_freq = None
                peak_amp = best_db

        rows.append(
            {
                "track": track_name,
                "peak_freq_hz": peak_freq,
                "peak_amplitude_db": peak_amp,
                "active_fraction": active_frac,
            }
        )

    rows.sort(key=lambda r: (r["peak_amplitude_db"] or -120.0), reverse=True)
    return rows


def _write_row(ws, row_idx: int, values: List[str]) -> None:
    for col_idx, value in enumerate(values, start=1):
        ws.cell(row=row_idx, column=col_idx, value=value)


def _render_master_view(ws, sections: List[Section], conflicts_by_idx: dict, row: int) -> int:
    _write_row(ws, row, ["\u2550" * 72]); row += 1
    _write_row(ws, row, ["VUE MAITRE - TOUTES LES SECTIONS"]); row += 1
    _write_row(ws, row, ["\u2550" * 72]); row += 2

    header = ["#", "Section", "Start", "End", "Duree", "Tracks", "Energie",
              "Conflits crit.", "Conflits mod."]
    _write_row(ws, row, header); row += 1

    for section in sections:
        section_conflicts = conflicts_by_idx.get(section.index, [])
        n_crit = sum(1 for c in section_conflicts if c["severity"] == "critical")
        n_mod = sum(1 for c in section_conflicts if c["severity"] == "moderate")
        duration = section.end_seconds - section.start_seconds
        _write_row(ws, row, [
            str(section.index),
            section.name,
            _format_time_mmss(section.start_seconds),
            _format_time_mmss(section.end_seconds),
            f"{int(round(duration))}s",
            str(len(section.tracks_active)),
            f"{section.total_energy_db:+.1f} dB",
            str(n_crit),
            str(n_mod),
        ])
        row += 1
    return row + 1


def _render_section_block(
    ws,
    section: Section,
    conflicts: List[dict],
    accumulations: List[dict],
    observations: List[str],
    all_tracks_zone_energy: dict,
    all_tracks_peak_trajectories: Optional[dict],
    presence_threshold_db: float,
    min_presence_ratio: float,
    row: int,
) -> int:
    duration = section.end_seconds - section.start_seconds
    header_line = (
        f"SECTION {section.index} - \"{section.name}\" "
        f"({_format_time_mmss(section.start_seconds)} - {_format_time_mmss(section.end_seconds)}, "
        f"duree {int(round(duration))}s, {len(section.tracks_active)} tracks actives)"
    )
    _write_row(ws, row, ["\u2550" * 72]); row += 1
    _write_row(ws, row, [header_line]); row += 1
    _write_row(ws, row, ["\u2550" * 72]); row += 2

    # --- Zone dominantes — gated on per-zone presence ratio (Fix 2).
    _write_row(ws, row, ["TRACKS ACTIVES PAR ZONE D'ENERGIE DOMINANTE"]); row += 1
    _write_row(ws, row, ["\u2500" * 72]); row += 1
    _write_row(ws, row, ["ZONE", "TRACKS DOMINANTES"]); row += 1
    track_presence = section.track_presence or {}
    for zone in _ZONE_ORDER:
        dominants = []
        for track, zones in section.track_energy.items():
            ratio = track_presence.get(track, {}).get(zone, 0.0)
            if ratio < min_presence_ratio:
                continue
            db = zones.get(zone, -120.0)
            dominants.append((track, db))
        dominants.sort(key=lambda t: -t[1])
        if dominants:
            text = ", ".join(f"{name} ({db:+.0f} dB)" for name, db in dominants)
        else:
            text = "(aucune track significative)"
        _write_row(ws, row, [_ZONE_LABELS.get(zone, zone), text])
        row += 1
    row += 1

    # --- Conflicts
    _write_row(ws, row, ["CONFLITS DE FREQUENCES (par severite)"]); row += 1
    _write_row(ws, row, ["\u2500" * 72]); row += 1
    if conflicts:
        _write_row(ws, row, ["SEVERITE", "ZONE", "TRACKS EN CONFLIT", "SCORE"])
        row += 1
        for conf in conflicts:
            _write_row(ws, row, [
                conf["severity"].upper(),
                _ZONE_LABELS.get(conf["zone"], conf["zone"]),
                f"{conf['track_a']} ({conf['energy_a']:+.0f} dB) <-> "
                f"{conf['track_b']} ({conf['energy_b']:+.0f} dB)",
                f"{conf['score']:.2f}",
            ])
            row += 1
    else:
        _write_row(ws, row, ["(Aucun conflit significatif dans cette section)"])
        row += 1
    row += 1

    # --- Accumulations (temporal simultaneity, Fix 3)
    _write_row(
        ws, row,
        ["ACCUMULATIONS (N+ tracks simultanees, duree minimale M buckets)"],
    )
    row += 1
    _write_row(ws, row, ["\u2500" * 72]); row += 1
    if accumulations:
        _write_row(ws, row, ["FREQ", "N SIMULT", "DUREE", "TRACKS IMPLIQUEES"])
        row += 1
        for acc in accumulations:
            _write_row(ws, row, [
                f"{acc['freq_hz']:.0f} Hz",
                str(acc["n_tracks_simultaneous"]),
                f"{acc['duration_buckets']} buck.",
                ", ".join(acc["track_names"]),
            ])
            row += 1
    else:
        _write_row(ws, row, ["(Aucune accumulation simultanee dans cette section)"])
        row += 1
    row += 1

    # --- Peak max per track
    _write_row(ws, row, ["PEAK MAX PAR TRACK DANS CETTE SECTION"]); row += 1
    _write_row(ws, row, ["\u2500" * 72]); row += 1
    peak_rows = _peak_max_per_track(
        section,
        all_tracks_zone_energy,
        all_tracks_peak_trajectories,
        presence_threshold_db,
    )
    if peak_rows:
        _write_row(ws, row, ["TRACK", "FREQ DU PEAK MAX", "AMPLITUDE", "DUREE ACTIVE"])
        row += 1
        duration_s = max(section.end_seconds - section.start_seconds, 0.001)
        for pr in peak_rows:
            freq_text = f"{pr['peak_freq_hz']:.0f} Hz" if pr["peak_freq_hz"] is not None else "-"
            amp_text = f"{pr['peak_amplitude_db']:+.1f} dB" if pr["peak_amplitude_db"] is not None else "-"
            active_seconds = pr["active_fraction"] * duration_s
            active_text = (
                f"{active_seconds:.0f} / {duration_s:.0f}s "
                f"({pr['active_fraction'] * 100:.0f}%)"
            )
            _write_row(ws, row, [pr["track"], freq_text, amp_text, active_text])
            row += 1
    else:
        _write_row(ws, row, ["(Aucune track active)"])
        row += 1
    row += 1

    # --- Observations
    _write_row(ws, row, ["OBSERVATIONS"]); row += 1
    _write_row(ws, row, ["\u2500" * 72]); row += 1
    if observations:
        for obs in observations:
            _write_row(ws, row, [f"- {obs}"])
            row += 1
    else:
        _write_row(ws, row, ["(aucune observation)"])
        row += 1
    row += 1
    return row


def _warn_non_individual_tracks(
    all_tracks_zone_energy: dict,
    log_fn,
) -> None:
    """Warn when track names look like busses / stems rather than individuals."""
    suspects = [
        name for name in all_tracks_zone_energy
        if any(pat in name for pat in _SUSPECT_NON_INDIVIDUAL_PATTERNS)
    ]
    if not suspects:
        return
    sample = ", ".join(suspects[:5])
    more = f" (+{len(suspects) - 5} more)" if len(suspects) > 5 else ""
    log_fn(
        f"    WARNING: _sections_timeline received {len(suspects)} track(s) "
        f"that look like BUS / Full-Mix stems: {sample}{more}. Upstream "
        f"filtering on Individual tracks was likely skipped; conflicts and "
        f"accumulations will over-count."
    )


def build_sections_timeline_sheet(
    workbook,
    sections: List[Section],
    all_tracks_zone_energy: dict,
    all_tracks_peak_trajectories: Optional[dict] = None,
    presence_threshold_db: float = PRESENCE_THRESHOLD_DB,
    min_presence_ratio: float = MIN_PRESENCE_RATIO,
    min_tracks_for_accumulation: int = ACCUMULATION_MIN_TRACKS,
    min_amplitude_for_accumulation_db: float = ACCUMULATION_MIN_AMP_DB,
    min_duration_buckets_accumulation: int = ACCUMULATION_MIN_DURATION,
    log_fn=None,
) -> None:
    """Build the ``_sections_timeline`` sheet.

    Silent no-op if ``sections`` is empty (the sheet is simply not created).
    The sheet is read-only for the user: every cell is plain text, no formulas,
    no colors, no conditional formatting.

    Expected input: ``all_tracks_zone_energy`` is the *audibility-masked*
    zone-energy produced by ``mix_analyzer._apply_audibility_mask`` — inaudible
    frames carry NaN, which the analysis helpers ignore. When a track has no
    automation map, its zone energy is raw (from WAV).

    Args:
        workbook: An openpyxl ``Workbook``.
        sections: Detected or user-defined sections (see :class:`Section`).
        all_tracks_zone_energy: ``{track_name: ZoneEnergy or dict[zone, ndarray]}``.
            Must contain Individual tracks only — pass in BUS / Full-Mix stems
            and you will over-count conflicts; a warning is emitted in that case.
        all_tracks_peak_trajectories: Optional ``{track_name: [PeakTrajectory, ...]}``
            used to populate the "Peak max par track" block with frequency data.
        presence_threshold_db: dB above which a bucket counts as "present"
            when computing activity / zone-dominante gates (Fix 2; default
            -30 dB).  Previously ``active_threshold_db`` with a mean-based
            gate — the new gate is NaN-robust under audibility masking.
        min_presence_ratio: Minimum fraction of section buckets a track
            must reach in a zone to count as dominant / active there
            (Fix 2 default 0.20 — 20% presence).
        min_tracks_for_accumulation: Minimum distinct tracks required to
            call a frequency cluster an accumulation (default 6).
        min_amplitude_for_accumulation_db: Skip peaks quieter than this when
            computing accumulations (default -25 dB).
        log_fn: Optional logger callable.
    """
    if log_fn is None:
        log_fn = lambda msg: None
    if not sections:
        log_fn("    Excel: no sections -> _sections_timeline sheet skipped")
        return

    _warn_non_individual_tracks(all_tracks_zone_energy, log_fn)

    enrich_sections_with_track_stats(
        sections,
        all_tracks_zone_energy,
        presence_threshold_db=presence_threshold_db,
        min_presence_ratio=min_presence_ratio,
    )

    conflicts_by_idx: dict = {
        s.index: detect_conflicts_in_section(s, min_presence_ratio=min_presence_ratio)
        for s in sections
    }
    accumulations_by_idx: dict = {
        s.index: detect_accumulations_in_section(
            s,
            all_tracks_peak_trajectories,
            min_tracks_simultaneous=min_tracks_for_accumulation,
            min_amplitude_db=min_amplitude_for_accumulation_db,
            min_duration_buckets=min_duration_buckets_accumulation,
        )
        for s in sections
    }
    observations_by_idx: dict = {
        s.index: generate_observations(
            section=s,
            conflicts=conflicts_by_idx[s.index],
            accumulations=accumulations_by_idx[s.index],
            all_sections=sections,
            all_tracks_zone_energy=all_tracks_zone_energy,
            active_threshold_db=presence_threshold_db,
        )
        for s in sections
    }

    if "_sections_timeline" in workbook.sheetnames:
        del workbook["_sections_timeline"]
    ws = workbook.create_sheet("_sections_timeline")

    row = _render_master_view(ws, sections, conflicts_by_idx, row=1)
    for section in sections:
        row = _render_section_block(
            ws,
            section=section,
            conflicts=conflicts_by_idx[section.index],
            accumulations=accumulations_by_idx[section.index],
            observations=observations_by_idx[section.index],
            all_tracks_zone_energy=all_tracks_zone_energy,
            all_tracks_peak_trajectories=all_tracks_peak_trajectories,
            presence_threshold_db=presence_threshold_db,
            min_presence_ratio=min_presence_ratio,
            row=row,
        )

    ws.sheet_state = "visible"  # user needs to see it; editing is discouraged via format
    log_fn(f"    Excel: _sections_timeline done ({len(sections)} sections)")
