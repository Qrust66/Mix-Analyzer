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


# User-facing name of the per-section dashboard in the Excel report. Kept as
# a constant so renames do not drift across the codebase + tests.
# The sheet is positioned right after the Index (position 2 in the tab bar)
# so it is one of the first things the engineer sees when opening the report.
SECTIONS_TIMELINE_SHEET_NAME = "Sections Timeline"


# Threshold for listing a track in the per-section "PEAK MAX PAR TRACK" table.
# A track is shown when its fader-equivalent peak (TRACK PEAK column) exceeds
# this value in the section. At -60 dB a track is at the edge of mix
# audibility — below that, it's bleed / noise floor and adds clutter to the
# report without informative value. This decouples the table from
# section.tracks_active which was found unreliable (often empty despite
# clearly audible tracks in the section — a pre-existing Feature 3 issue).
SECTION_LISTING_THRESHOLD_DB = -60.0


# Minimum active_fraction required for a track to be listed in a section's
# rendered blocks ("TRACKS ACTIVES PAR ZONE D'ENERGIE DOMINANTE" and
# "PEAK MAX PAR TRACK"). Applied on top of the meter-based active fraction
# (see mix_analyzer.compute_track_active_fraction_by_section). Filters
# reverb tails and slight bleed from adjacent sections: Tambourine
# leaking ~2-6% into Chorus 1/2 on Acid Drops does not get listed.
# Paramétrable via build_sections_timeline_sheet kwarg.
MIN_ACTIVE_FRACTION_FOR_LISTING = 0.10


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
    # Raw Locator annotation text, e.g. ``"override: Kick 1=S"``. Populated
    # by :func:`_locators_to_sections`. Feature 3.5 (TFP) parses TFP
    # overrides from this field; empty string otherwise.
    annotation: str = ""
    # Effective TFP role per track for this section, resolved from the
    # Ableton name's prefix and this section's annotation overrides.
    # Populated by :func:`enrich_sections_with_track_roles`. Keyed by the
    # WAV filename (``ti['name']``) to stay aligned with every other
    # per-track structure in the sheet (all_tracks_zone_energy,
    # all_tracks_peak_by_section, etc.). Empty dict when no Ableton
    # automation maps were loaded.
    track_roles: dict = field(default_factory=dict)
    # True when an override from the annotation changed this track's role
    # away from its base prefix — used to flag "*" in the sheet.
    track_role_overridden: dict = field(default_factory=dict)
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
    threshold_db: float = 10.0,
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
    threshold_multiplier: float = 2.0,
    energy_threshold_db: float = 10.0,
    min_section_duration_s: float = 4.0,
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
        4. Filter transitions that would create a section shorter than
           ``min_section_duration_s`` — short bursts are rarely musical.
        5. Each segment between the remaining transitions becomes a
           ``Section``, named "Section 1" .. "Section N" (1-indexed).

    On dense mixes where every track plays throughout the song the spectral
    delta varies little — the energy-transition pass surfaces the drops and
    breaks that the spectral pass misses.  Defaults were retuned against
    Acid Drops validation (3min55 dark techno): 2.5/—/— produced 1 section,
    1.5/6.0/— produced 39 (many <3 s); 2.0/10.0/4.0 targets 6-12 sections
    with every section >= 4 s.

    Args:
        delta_spectrum: 1-D array of frame-to-frame spectral change (dB).
        zone_energy: Either a 1-D array (n_frames,) of total energy per
            frame in dB, or a 2-D array (n_zones, n_frames). 2-D inputs are
            collapsed via a NaN-safe linear sum before further analysis.
        times: 1-D array of frame timestamps (seconds).
        threshold_multiplier: Spectral-threshold multiplier applied to the
            delta median. Default 2.0.
        energy_threshold_db: Minimum absolute dB delta between consecutive
            buckets' total energy to flag an energy transition. Default 10.0.
        min_section_duration_s: Minimum duration in seconds of any detected
            section. Transitions closer than this in elapsed time are
            dropped (the later one is discarded).  Default 4.0.
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

    # --- Minimum-duration filter: drop transitions that would create a section
    # shorter than ``min_section_duration_s`` relative to the previous accepted
    # boundary.  Runs after the frame-gap fusion so we reject for *elapsed time*
    # regardless of the sampling density. Also trims a trailing short section
    # by dropping the last accepted transition when the tail is too short.
    if (
        min_section_duration_s > 0
        and combined
        and t.size >= 2
    ):
        filtered: List[int] = []
        last_time = float(t[0])
        for tr in combined:
            tr_time = float(t[min(tr, t.size - 1)])
            if tr_time - last_time >= min_section_duration_s:
                filtered.append(tr)
                last_time = tr_time

        end_time = float(t[-1])
        while filtered and (
            end_time - float(t[min(filtered[-1], t.size - 1)])
            < min_section_duration_s
        ):
            filtered.pop()

        combined = filtered

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
                annotation=ordered[i].get("annotation", "") or "",
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


def enrich_sections_with_track_roles(
    sections: List[Section],
    wav_to_ableton: dict,
) -> List[Section]:
    """Populate ``section.track_roles`` using the Ableton track names.

    Feature 3.5 — for each track we have features for (keyed by its WAV
    filename, as everywhere else in the sheet), look up the corresponding
    Ableton track name, parse its TFP prefix, apply any per-section
    override from the Locator annotation, and store the final
    ``(Importance, Function)`` keyed by the WAV filename.

    Tracks whose Ableton name could not be resolved fall back to
    :data:`tfp_parser.DEFAULT_ROLE` (Support / Rhythm) — the same
    behaviour as tracks without a TFP prefix. The caller (builder)
    collects those into a single "tracks sans préfixe" warning.

    Args:
        sections: Sections to enrich, modified in place.
        wav_to_ableton: ``{wav_filename: ableton_track_name}`` where the
            value is the raw EffectiveName (still carrying any
            ``"[H/R] "`` prefix). Pass ``{}`` when no .als was loaded —
            every track gets DEFAULT_ROLE.

    Returns:
        The same list of sections, now carrying ``track_roles`` and
        ``track_role_overridden`` per entry.
    """
    from tfp_parser import DEFAULT_ROLE, parse_tfp_overrides, resolve_track_role

    for section in sections:
        overrides = parse_tfp_overrides(section.annotation or "")
        for wav_name, ableton_name in wav_to_ableton.items():
            if ableton_name is None:
                # No Ableton counterpart found — fall back silently; the
                # warning "tracks sans préfixe" is produced upstream by
                # the builder based on the ableton_name being missing.
                section.track_roles[wav_name] = DEFAULT_ROLE
                section.track_role_overridden[wav_name] = False
                continue

            resolved = resolve_track_role(ableton_name, overrides, DEFAULT_ROLE)
            section.track_roles[wav_name] = resolved

            # Flag whether the annotation changed the role vs the base
            # (prefix-derived or default). The "*" marker in the sheet
            # reflects this boolean.
            base_resolved = resolve_track_role(ableton_name, {}, DEFAULT_ROLE)
            section.track_role_overridden[wav_name] = (
                resolved != base_resolved
            )
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
# Phase C — Excel sheet rendering (Sections Timeline)
# ---------------------------------------------------------------------------

def _format_time_mmss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    return f"{total // 60}:{total % 60:02d}"


def _peak_max_per_track(
    section: Section,
    all_tracks_zone_energy: dict,
    all_tracks_peak_trajectories: Optional[dict],
    active_threshold_db: float,
    all_tracks_peak_by_section: Optional[dict] = None,
    all_tracks_active_fraction: Optional[dict] = None,
    min_active_fraction_for_listing: float = MIN_ACTIVE_FRACTION_FOR_LISTING,
) -> List[dict]:
    """Build the "Peak max par track" rows for one section.

    When ``all_tracks_peak_by_section`` is provided
    (``{track_name: {section_index: peak_dbfs_or_None}}``), iterates **every
    track** for which a TRACK PEAK exists and keeps those above
    :data:`SECTION_LISTING_THRESHOLD_DB` (default -60 dB). Rows are sorted by
    TRACK PEAK descending — loudest contributor first — which makes the
    hero/support/atmos gradient immediately readable. Each row carries a
    ``track_peak_db`` field = fader-equivalent peak (WAV × effective_gain).

    Without ``all_tracks_peak_by_section`` (backwards compatibility), falls
    back to iterating ``section.tracks_active`` and sorting by spectral
    amplitude — the pre-v2.6.x behaviour.

    Design note: ``section.tracks_active`` was found to be almost always
    empty on real projects (Feature 3 symptom pre-dating this change), which
    caused the table to list no tracks even in busy sections. Using
    TRACK PEAK as both the gate and the sort key bypasses that issue.

    Args:
        section: The section to render a table for.
        all_tracks_zone_energy: ``{track_name: ZoneEnergy-or-dict[zone, arr]}``.
            Used for the DUREE ACTIVE column and the dominant-zone fallback.
        all_tracks_peak_trajectories: ``{track_name: [PeakTrajectory, ...]}``.
            Used to pick the single loudest spectral peak per track (FREQ +
            AMP ZONE columns).
        active_threshold_db: Zone-energy threshold used by DUREE ACTIVE.
        all_tracks_peak_by_section: ``{track_name: {section_index: dBFS}}``.
            Source of truth for the TRACK PEAK column and for the row gate.
    """
    # Determine number of frames in the time axis, used for duration fractions.
    n_frames = 0
    for entry in all_tracks_zone_energy.values():
        for arr in _as_zone_arrays(entry).values():
            n_frames = max(n_frames, len(arr))
        if n_frames:
            break
    frame_slice = _section_frame_slice(section, n_frames) if n_frames else slice(0, 0)
    section_frames = max(frame_slice.stop - frame_slice.start, 1)

    # Decide which tracks to list:
    #   - if we have TRACK PEAK data: every track whose TRACK PEAK in this
    #     section exceeds SECTION_LISTING_THRESHOLD_DB (mix audibility floor)
    #   - else: fall back to section.tracks_active (legacy behaviour)
    if all_tracks_peak_by_section:
        tracks_to_list = []
        for track_name in all_tracks_zone_energy.keys():
            per_section = all_tracks_peak_by_section.get(track_name) or {}
            tp = per_section.get(section.index)
            if tp is None:
                continue  # silent (below -90 dB floor set upstream)
            if tp < SECTION_LISTING_THRESHOLD_DB:
                continue  # audibly negligible in this section
            tracks_to_list.append(track_name)
    else:
        tracks_to_list = list(section.tracks_active)

    rows: List[dict] = []
    for track_name in tracks_to_list:
        if track_name not in all_tracks_zone_energy:
            continue
        zone_arrays = _as_zone_arrays(all_tracks_zone_energy[track_name])

        # Active fraction source of truth (option H, v2.6.5):
        # - Prefer ``all_tracks_active_fraction`` when provided — this is
        #   the WAV-meter-based calculation from mix_analyzer, which
        #   matches Ableton's meter behaviour and correctly reports
        #   continuous percussion patterns as ~95%+ active.
        # - Fall back to the CQT zone_energy-based helper
        #   ``_track_active_fraction`` when no pre-computed dict is
        #   available (tests, offline tools, backwards compat). This
        #   legacy path under-counts percussion transients but keeps the
        #   function usable without a WAV pre-compute pipeline.
        active_frac: Optional[float] = None
        if all_tracks_active_fraction is not None:
            per_section = all_tracks_active_fraction.get(track_name) or {}
            active_frac = per_section.get(section.index)
        if active_frac is None:
            active_frac = _track_active_fraction(
                section, zone_arrays, active_threshold_db
            )

        # Second gate (applied only when TRACK PEAK drives the listing):
        # require active_fraction >= min_active_fraction_for_listing
        # (default 10% — see MIN_ACTIVE_FRACTION_FOR_LISTING). Filters
        # bleed / reverb tails / plugin noise floors that pass the -60 dB
        # TRACK PEAK gate but only tickle the meter above -40 dB for a
        # few hundred ms. Observed on Acid Drops: Tambourine Hi-Hat
        # leaking 2-6% into Chorus 1/2 (reverb tail from the preceding
        # Acid section) — now filtered out so the user sees only
        # musically meaningful contributors per section.
        if all_tracks_peak_by_section and active_frac < min_active_fraction_for_listing:
            continue

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

        track_peak_db = None
        if all_tracks_peak_by_section:
            track_peak_db = (all_tracks_peak_by_section.get(track_name) or {}).get(
                section.index
            )

        # Feature 3.5: TFP role for this track in this section (resolved
        # upstream by enrich_sections_with_track_roles; empty dict when
        # no .als was loaded).
        role_pair = section.track_roles.get(track_name)
        role_overridden = bool(section.track_role_overridden.get(track_name, False))

        rows.append(
            {
                "track": track_name,
                "peak_freq_hz": peak_freq,
                "peak_amplitude_db": peak_amp,
                "active_fraction": active_frac,
                "track_peak_db": track_peak_db,
                "role": role_pair,
                "role_overridden": role_overridden,
            }
        )

    # Sort by TRACK PEAK descending when available — makes the loudest
    # contributor to the section appear first. Fall back to AMP ZONE when
    # TRACK PEAK is missing (legacy path).
    if all_tracks_peak_by_section:
        rows.sort(key=lambda r: (r.get("track_peak_db") or -120.0), reverse=True)
    else:
        rows.sort(key=lambda r: (r["peak_amplitude_db"] or -120.0), reverse=True)
    return rows


def _write_row(ws, row_idx: int, values: List[str]) -> None:
    for col_idx, value in enumerate(values, start=1):
        ws.cell(row=row_idx, column=col_idx, value=value)


def _format_role(
    role_pair: Optional[tuple],
    overridden: bool = False,
) -> str:
    """Format a (Importance, Function) pair as ``"H/R"`` (or ``"H/R*"``
    when an annotation override changed the role).

    ``role_pair`` may be ``None`` — e.g. when no .als was loaded. We fall
    back to the string ``"?"`` rather than guessing so the user can tell
    the difference between "default S/R" and "we don't know".
    """
    if role_pair is None:
        return "?"
    try:
        imp, fn = role_pair
        imp_code = imp.value if hasattr(imp, "value") else str(imp)
        fn_code = fn.value if hasattr(fn, "value") else str(fn)
        return f"{imp_code}/{fn_code}{'*' if overridden else ''}"
    except Exception:
        return "?"


def _format_track_with_role(
    track_name: str,
    role_pair: Optional[tuple],
    overridden: bool,
) -> str:
    """Build ``"[H/R] Kick 1"`` for a single track — used in the
    "TRACKS ACTIVES PAR ZONE" block where tracks are comma-joined with
    their role badge inlined. ``*`` appended inside the bracket when an
    annotation override changed the role for this section.
    """
    if role_pair is None:
        return track_name
    badge = _format_role(role_pair, overridden=overridden)
    return f"[{badge}] {track_name}"


def _render_tfp_warning_banner(
    ws, tracks_without_prefix: List[str], row: int,
) -> int:
    """Render the "tracks sans préfixe TFP" warning banner.

    Feature 3.5 — appears at the top of the Sections Timeline sheet when
    one or more tracks lack a TFP prefix in their Ableton name. Those
    tracks fall back to ``DEFAULT_ROLE`` (S/R) which may not reflect the
    user's intent. The banner lists every offending track so the user
    can fix the names in Ableton and re-run. Absent when every track is
    correctly prefixed.
    """
    n = len(tracks_without_prefix)
    _write_row(ws, row, [f"⚠ WARNING TFP — {n} TRACK(S) SANS PRÉFIXE"])
    row += 1
    _write_row(ws, row, ["─" * 72])
    row += 1
    _write_row(ws, row, [
        f"{n} tracks n'ont pas de préfixe TFP dans leur nom Ableton "
        "— classifiées par défaut [S/R] :"
    ])
    row += 1
    # List first 15 to avoid flooding; append "+N more" for the rest.
    sample = tracks_without_prefix[:15]
    for name in sample:
        _write_row(ws, row, [f"  • {name}"])
        row += 1
    if n > len(sample):
        _write_row(ws, row, [f"  ... +{n - len(sample)} autres"])
        row += 1
    _write_row(ws, row, [
        "Pour classifier correctement, renommer dans Ableton avec le "
        "format [X/Y] avant les prochaines analyses."
    ])
    row += 2
    return row


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
    all_tracks_peak_by_section: Optional[dict] = None,
    all_tracks_active_fraction: Optional[dict] = None,
    min_active_fraction_for_listing: float = MIN_ACTIVE_FRACTION_FOR_LISTING,
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
            # Secondary filter (v2.6.6): reject tracks musically inactive in
            # this section even if their spectral presence in the zone met
            # the bucket-level gate. Applied only when the meter-based
            # active-fraction dict is available. Mirrors the same gate used
            # in the PEAK MAX block so both views stay consistent.
            if all_tracks_active_fraction is not None:
                per_section = all_tracks_active_fraction.get(track) or {}
                afrac = per_section.get(section.index, 0.0)
                if afrac < min_active_fraction_for_listing:
                    continue
            db = zones.get(zone, -120.0)
            dominants.append((track, db))
        dominants.sort(key=lambda t: -t[1])
        if dominants:
            # Feature 3.5: prepend TFP role badge to each track name.
            # "[H/R] Kick 1 (-2 dB)". Asterisk inside the badge when an
            # annotation override changed the role for this section.
            parts = []
            for name, db in dominants:
                role_pair = section.track_roles.get(name)
                overridden = bool(section.track_role_overridden.get(name, False))
                badged = _format_track_with_role(name, role_pair, overridden)
                parts.append(f"{badged} ({db:+.0f} dB)")
            text = ", ".join(parts)
        else:
            text = "(aucune track significative)"
        _write_row(ws, row, [_ZONE_LABELS.get(zone, zone), text])
        row += 1
    row += 1

    # --- Conflicts
    _write_row(ws, row, ["CONFLITS DE FREQUENCES (par severite)"]); row += 1
    _write_row(ws, row, ["\u2500" * 72]); row += 1
    if conflicts:
        # Feature 3.5: COMBO column = "RoleA x RoleB". Track names carry
        # the role badge via _format_track_with_role so the user reads
        # "[H/R] Kick 1 <-> [S/H] Sub Bass" directly.
        _write_row(ws, row, [
            "SEVERITE", "ZONE", "TRACKS EN CONFLIT", "COMBO", "SCORE",
        ])
        row += 1
        for conf in conflicts:
            role_a = section.track_roles.get(conf["track_a"])
            role_b = section.track_roles.get(conf["track_b"])
            over_a = bool(section.track_role_overridden.get(conf["track_a"], False))
            over_b = bool(section.track_role_overridden.get(conf["track_b"], False))
            name_a = _format_track_with_role(conf["track_a"], role_a, over_a)
            name_b = _format_track_with_role(conf["track_b"], role_b, over_b)
            combo = f"{_format_role(role_a)} x {_format_role(role_b)}"
            _write_row(ws, row, [
                conf["severity"].upper(),
                _ZONE_LABELS.get(conf["zone"], conf["zone"]),
                f"{name_a} ({conf['energy_a']:+.0f} dB) <-> "
                f"{name_b} ({conf['energy_b']:+.0f} dB)",
                combo,
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
        all_tracks_peak_by_section=all_tracks_peak_by_section,
        all_tracks_active_fraction=all_tracks_active_fraction,
        min_active_fraction_for_listing=min_active_fraction_for_listing,
    )
    if peak_rows:
        # "RÔLE" = TFP role from Feature 3.5 (Importance/Function). "*"
        # suffix indicates a per-section annotation override vs the
        # base prefix-derived role.
        # "AMP ZONE" = peak amplitude within the track's dominant band
        # (spectral, per-band). "TRACK PEAK" = fader-equivalent sample peak
        # of the whole track after gain. The two can differ by 15-25 dB on
        # tracks where a narrow band dominates — see the commit that added
        # the TRACK PEAK column for context.
        _write_row(ws, row, [
            "TRACK", "RÔLE", "FREQ DU PEAK MAX", "AMP ZONE",
            "TRACK PEAK", "DUREE ACTIVE",
        ])
        row += 1
        duration_s = max(section.end_seconds - section.start_seconds, 0.001)
        for pr in peak_rows:
            role_text = _format_role(
                pr.get("role"), overridden=pr.get("role_overridden", False)
            )
            freq_text = f"{pr['peak_freq_hz']:.0f} Hz" if pr["peak_freq_hz"] is not None else "-"
            amp_text = f"{pr['peak_amplitude_db']:+.1f} dB" if pr["peak_amplitude_db"] is not None else "-"
            if pr.get("track_peak_db") is None:
                track_peak_text = "--"
            else:
                track_peak_text = f"{pr['track_peak_db']:+.1f} dB"
            active_seconds = pr["active_fraction"] * duration_s
            active_text = (
                f"{active_seconds:.0f} / {duration_s:.0f}s "
                f"({pr['active_fraction'] * 100:.0f}%)"
            )
            _write_row(ws, row, [
                pr["track"], role_text, freq_text, amp_text,
                track_peak_text, active_text,
            ])
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
        f"    WARNING: {SECTIONS_TIMELINE_SHEET_NAME} received {len(suspects)} track(s) "
        f"that look like BUS / Full-Mix stems: {sample}{more}. Upstream "
        f"filtering on Individual tracks was likely skipped; conflicts and "
        f"accumulations will over-count."
    )


def _detect_tracks_without_prefix(wav_to_ableton: dict) -> List[str]:
    """Return WAV filenames whose Ableton track has no TFP prefix.

    Feature 3.5 — used to populate the "⚠ WARNING TFP" banner at the top
    of the Sections Timeline sheet. A missing prefix falls back to
    ``DEFAULT_ROLE`` (Support / Rhythm) which is fine but may not reflect
    the user's intent; surfacing the list lets them fix the names in
    Ableton before the next run.

    Tracks whose Ableton counterpart is not known (``wav_to_ableton[w]``
    is ``None``) also count — a missing match means we could not check
    the prefix at all. Returned in the order they appear in
    ``wav_to_ableton``.
    """
    from tfp_parser import parse_tfp_prefix

    missing: List[str] = []
    for wav_name, ableton_name in wav_to_ableton.items():
        if ableton_name is None:
            missing.append(wav_name)
            continue
        if parse_tfp_prefix(ableton_name) is None:
            missing.append(wav_name)
    return missing


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
    all_tracks_peak_by_section: Optional[dict] = None,
    all_tracks_active_fraction: Optional[dict] = None,
    min_active_fraction_for_listing: float = MIN_ACTIVE_FRACTION_FOR_LISTING,
    wav_to_ableton: Optional[dict] = None,
    log_fn=None,
) -> None:
    """Build the ``Sections Timeline`` sheet (positioned right after Index).

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
        log_fn(
            f"    Excel: no sections -> {SECTIONS_TIMELINE_SHEET_NAME} sheet skipped"
        )
        return

    _warn_non_individual_tracks(all_tracks_zone_energy, log_fn)

    enrich_sections_with_track_stats(
        sections,
        all_tracks_zone_energy,
        presence_threshold_db=presence_threshold_db,
        min_presence_ratio=min_presence_ratio,
    )

    # Feature 3.5 — resolve TFP roles per section from the Ableton track
    # names + each Locator annotation. If no mapping was passed, we still
    # populate track_roles with the default (S, R) for every track so
    # downstream rendering code can assume the dict is complete.
    _wav_to_ableton = wav_to_ableton or {
        name: None for name in all_tracks_zone_energy
    }
    enrich_sections_with_track_roles(sections, _wav_to_ableton)

    tracks_without_prefix = _detect_tracks_without_prefix(_wav_to_ableton)

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

    if SECTIONS_TIMELINE_SHEET_NAME in workbook.sheetnames:
        del workbook[SECTIONS_TIMELINE_SHEET_NAME]
    ws = workbook.create_sheet(SECTIONS_TIMELINE_SHEET_NAME)

    # Position the sheet right after the Index tab (index 1) so it appears in
    # the top of the tab bar instead of after all global sheets. If Index is
    # not at position 0 (unexpected), fall back to whatever order openpyxl
    # gave us — best-effort, never crash the report.
    try:
        target_index = 1
        current_index = workbook.sheetnames.index(SECTIONS_TIMELINE_SHEET_NAME)
        if current_index != target_index:
            workbook._sheets.insert(
                target_index, workbook._sheets.pop(current_index)
            )
    except (ValueError, IndexError) as e:
        log_fn(f"    {SECTIONS_TIMELINE_SHEET_NAME}: could not reposition tab: {e}")

    # Feature 3.5 — TFP warning banner in rows 1-3 when any track lacks
    # a prefix. Displayed before the master view so the user sees the
    # warning immediately when the sheet opens. No-op when every track
    # is properly prefixed.
    next_row = 1
    if tracks_without_prefix:
        next_row = _render_tfp_warning_banner(ws, tracks_without_prefix, 1)

    row = _render_master_view(ws, sections, conflicts_by_idx, row=next_row)
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
            all_tracks_peak_by_section=all_tracks_peak_by_section,
            all_tracks_active_fraction=all_tracks_active_fraction,
            min_active_fraction_for_listing=min_active_fraction_for_listing,
        )

    ws.sheet_state = "visible"  # user needs to see it; editing is discouraged via format
    log_fn(
        f"    Excel: {SECTIONS_TIMELINE_SHEET_NAME} done ({len(sections)} sections)"
    )
