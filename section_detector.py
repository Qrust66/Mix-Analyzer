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

ACTIVE_THRESHOLD_DB = -40.0
CONFLICT_CRITICAL = 0.7
CONFLICT_MODERATE = 0.4


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


def _mean_track_energy(
    zone_arrays: dict,
    frame_slice: slice,
) -> dict:
    """Return ``{zone_name: mean_db}`` restricted to ``frame_slice``.

    Frames below -120 dB are treated as silence and excluded from the mean.
    A zone with no non-silent frames returns -120 dB.
    """
    out: dict = {}
    for zone in _ZONE_ORDER:
        arr = zone_arrays.get(zone)
        if arr is None:
            out[zone] = -120.0
            continue
        segment = np.asarray(arr, dtype=float)[frame_slice]
        if segment.size == 0:
            out[zone] = -120.0
            continue
        audible = segment[segment > -119.0]
        out[zone] = float(np.mean(audible)) if audible.size else -120.0
    return out


def enrich_sections_with_track_stats(
    sections: List[Section],
    all_tracks_zone_energy: dict,
    active_threshold_db: float = ACTIVE_THRESHOLD_DB,
) -> List[Section]:
    """Populate ``tracks_active`` and ``track_energy`` on each section in place.

    A track is "active" in a section if its mean energy is above
    ``active_threshold_db`` in at least one zone.
    ``track_energy[track][zone] = mean_db`` for every track in
    ``all_tracks_zone_energy`` (not only the active ones).
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
        section.tracks_active = []
        if n_frames == 0:
            continue
        frame_slice = _section_frame_slice(section, n_frames)
        for track_name, entry in all_tracks_zone_energy.items():
            arrays = _as_zone_arrays(entry)
            means = _mean_track_energy(arrays, frame_slice)
            section.track_energy[track_name] = {
                z: round(v, 2) for z, v in means.items()
            }
            if any(v > active_threshold_db for v in means.values()):
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
    active_threshold_db: float = ACTIVE_THRESHOLD_DB,
) -> List[dict]:
    """Pair-wise, zone-wise conflicts within this section.

    Score formula (see feature_3 Phase C Q3):
        overlap      = max(0, 1 - abs(A_db - B_db) / 30)
        level_weight = max(0, (avg_db + 40) / 40)
        score        = overlap * level_weight

    Args:
        section: Section enriched with ``track_energy`` (via
            :func:`enrich_sections_with_track_stats`).
        active_threshold_db: Both tracks must reach this level in the zone.

    Returns:
        Conflict dicts sorted by severity (critical first) then score desc.
        Each dict: ``{track_a, track_b, zone, energy_a, energy_b, score, severity}``.
    """
    if not section.track_energy:
        return []

    conflicts: List[dict] = []
    tracks = list(section.track_energy.keys())
    for i in range(len(tracks)):
        for j in range(i + 1, len(tracks)):
            a = tracks[i]
            b = tracks[j]
            for zone in _ZONE_ORDER:
                ea = section.track_energy[a].get(zone, -120.0)
                eb = section.track_energy[b].get(zone, -120.0)
                if ea <= active_threshold_db or eb <= active_threshold_db:
                    continue
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


def detect_accumulations_in_section(
    section: Section,
    all_tracks_peak_trajectories: Optional[dict],
    frequency_tolerance_semitones: float = 1.0,
    min_tracks: int = 4,
    min_amplitude_db: float = -30.0,
) -> List[dict]:
    """Find frequencies where ``min_tracks`` or more tracks have a significant peak.

    Args:
        section: Section to scope to via ``start_bucket``/``end_bucket``.
        all_tracks_peak_trajectories: ``{track_name: list[PeakTrajectory]}``.
            Each ``PeakTrajectory`` must expose ``points`` as
            ``[(frame_idx, freq_hz, amplitude_db), ...]``.
        frequency_tolerance_semitones: Peaks within this distance are clustered.
        min_tracks: Minimum unique tracks required to call it an accumulation.
        min_amplitude_db: Skip peaks quieter than this.

    Returns:
        Accumulation dicts sorted by track count desc, each with
        ``{freq_hz, n_tracks, track_names}``.
    """
    if not all_tracks_peak_trajectories:
        return []

    start, end = section.start_bucket, section.end_bucket
    peak_points: List[Tuple[float, str]] = []  # (freq_hz, track_name)
    for track_name, trajectories in all_tracks_peak_trajectories.items():
        seen_freqs = set()
        for traj in trajectories or []:
            points = getattr(traj, "points", None) or []
            for point in points:
                try:
                    frame_idx, freq_hz, amp_db = point
                except Exception:
                    continue
                if frame_idx < start or frame_idx > end:
                    continue
                if amp_db < min_amplitude_db:
                    continue
                rounded_key = round(float(freq_hz), 1)
                if rounded_key in seen_freqs:
                    continue
                seen_freqs.add(rounded_key)
                peak_points.append((float(freq_hz), track_name))

    if not peak_points:
        return []

    # Cluster by log-frequency within tolerance.
    peak_points.sort(key=lambda p: p[0])
    clusters: List[List[Tuple[float, str]]] = [[peak_points[0]]]
    for freq, name in peak_points[1:]:
        ref_freq, _ = clusters[-1][0]
        ratio = freq / ref_freq if ref_freq > 0 else 1.0
        semitones = abs(12.0 * np.log2(ratio)) if ratio > 0 else float("inf")
        if semitones <= frequency_tolerance_semitones:
            clusters[-1].append((freq, name))
        else:
            clusters.append([(freq, name)])

    accumulations: List[dict] = []
    for cluster in clusters:
        unique_tracks = sorted({name for _, name in cluster})
        if len(unique_tracks) < min_tracks:
            continue
        mean_freq = float(np.mean([f for f, _ in cluster]))
        accumulations.append(
            {
                "freq_hz": round(mean_freq, 1),
                "n_tracks": len(unique_tracks),
                "track_names": unique_tracks,
            }
        )

    accumulations.sort(key=lambda a: (-a["n_tracks"], a["freq_hz"]))
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

    # P4 — Top accumulation
    if accumulations:
        top_acc = accumulations[0]
        observations.append(
            f"{top_acc['n_tracks']} tracks competent autour de "
            f"{top_acc['freq_hz']:.0f} Hz - zone encombree"
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
    active_threshold_db: float,
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

    # --- Zone dominantes
    _write_row(ws, row, ["TRACKS ACTIVES PAR ZONE D'ENERGIE DOMINANTE"]); row += 1
    _write_row(ws, row, ["\u2500" * 72]); row += 1
    _write_row(ws, row, ["ZONE", "TRACKS DOMINANTES"]); row += 1
    for zone in _ZONE_ORDER:
        dominants = []
        for track, zones in section.track_energy.items():
            db = zones.get(zone, -120.0)
            if db > active_threshold_db:
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

    # --- Accumulations
    _write_row(ws, row, ["ACCUMULATIONS (4+ tracks a la meme frequence)"]); row += 1
    _write_row(ws, row, ["\u2500" * 72]); row += 1
    if accumulations:
        _write_row(ws, row, ["FREQUENCE", "N TRACKS", "TRACKS"])
        row += 1
        for acc in accumulations:
            _write_row(ws, row, [
                f"{acc['freq_hz']:.0f} Hz",
                str(acc["n_tracks"]),
                ", ".join(acc["track_names"]),
            ])
            row += 1
    else:
        _write_row(ws, row, ["(Aucune accumulation dans cette section)"])
        row += 1
    row += 1

    # --- Peak max per track
    _write_row(ws, row, ["PEAK MAX PAR TRACK DANS CETTE SECTION"]); row += 1
    _write_row(ws, row, ["\u2500" * 72]); row += 1
    peak_rows = _peak_max_per_track(
        section,
        all_tracks_zone_energy,
        all_tracks_peak_trajectories,
        active_threshold_db,
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


def build_sections_timeline_sheet(
    workbook,
    sections: List[Section],
    all_tracks_zone_energy: dict,
    all_tracks_peak_trajectories: Optional[dict] = None,
    active_threshold_db: float = ACTIVE_THRESHOLD_DB,
    log_fn=None,
) -> None:
    """Build the ``_sections_timeline`` sheet.

    Silent no-op if ``sections`` is empty (the sheet is simply not created).
    The sheet is read-only for the user: every cell is plain text, no formulas,
    no colors, no conditional formatting.

    Args:
        workbook: An openpyxl ``Workbook``.
        sections: Detected or user-defined sections (see :class:`Section`).
        all_tracks_zone_energy: ``{track_name: ZoneEnergy or dict[zone, ndarray]}``.
        all_tracks_peak_trajectories: Optional ``{track_name: [PeakTrajectory, ...]}``
            used to populate the "Peak max par track" block with frequency data.
        active_threshold_db: Energy threshold for "active"/"significative" labels.
        log_fn: Optional logger callable.
    """
    if log_fn is None:
        log_fn = lambda msg: None
    if not sections:
        log_fn("    Excel: no sections -> _sections_timeline sheet skipped")
        return

    enrich_sections_with_track_stats(
        sections, all_tracks_zone_energy, active_threshold_db=active_threshold_db
    )

    conflicts_by_idx: dict = {
        s.index: detect_conflicts_in_section(s, active_threshold_db=active_threshold_db)
        for s in sections
    }
    accumulations_by_idx: dict = {
        s.index: detect_accumulations_in_section(s, all_tracks_peak_trajectories)
        for s in sections
    }
    observations_by_idx: dict = {
        s.index: generate_observations(
            section=s,
            conflicts=conflicts_by_idx[s.index],
            accumulations=accumulations_by_idx[s.index],
            all_sections=sections,
            all_tracks_zone_energy=all_tracks_zone_energy,
            active_threshold_db=active_threshold_db,
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
            active_threshold_db=active_threshold_db,
            row=row,
        )

    ws.sheet_state = "visible"  # user needs to see it; editing is discouraged via format
    log_fn(f"    Excel: _sections_timeline done ({len(sections)} sections)")
