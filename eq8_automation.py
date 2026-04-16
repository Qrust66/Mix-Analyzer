#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EQ8 Automation Engine — v2.5

Consumes features from spectral_evolution.py and writes dynamic EQ8
automations into Ableton .als files via als_utils.py.

Each write_* function follows the pattern:
    1. Backup the .als
    2. Parse, find track, find/create EQ8
    3. Allocate a band, configure it
    4. Convert features to breakpoints (seconds -> beats)
    5. Write automation envelopes
    6. Save the .als
    7. Return AutomationReport
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from als_utils import (
    parse_als,
    save_als_from_tree,
    backup_als,
    find_track_by_name,
    find_or_create_eq8,
    get_eq8_band,
    configure_eq8_band,
    get_automation_target_id,
    write_automation_envelope,
    get_next_id,
    seconds_to_beats,
    thin_breakpoints,
)

from spectral_evolution import (
    PeakTrajectory,
    TransientEvent,
    ZONE_RANGES,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TrackNotFoundError(Exception):
    """Raised when track_id does not exist in the .als file."""


class EQ8SlotFullError(Exception):
    """Raised when no EQ8 band is available for automation."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AutomationReport:
    """Result of a single automation write operation."""
    success: bool
    breakpoints_written: int
    eq8_band_index: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class MaskingReport:
    """Result of cross-track masking analysis."""
    zones: list[str]
    scores: dict[str, np.ndarray]
    severity: float
    times: np.ndarray


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_tempo(tree) -> float:
    """Read the project tempo from a parsed ALS ElementTree."""
    root = tree.getroot()
    tempo_elem = root.find(".//Tempo/Manual")
    if tempo_elem is not None:
        return float(tempo_elem.get("Value", "120"))
    return 120.0


def _find_available_band(
    eq8_element,
    track_element,
    exclude: list[int] | None = None,
) -> int:
    """Find the first EQ8 band not actively in use.

    Prefers bands 1-6, then 0 and 7 (which users often reserve for
    HPF/LPF).  A band is "available" if its Gain/Manual is 0 and no
    automation envelope targets any of its parameters.

    Args:
        eq8_element: The Eq8 XML Element.
        track_element: The track XML Element (to check existing envelopes).
        exclude: Band indices to skip.

    Returns:
        Band index (0-7).

    Raises:
        EQ8SlotFullError: If all 8 bands are occupied.
    """
    exclude = set(exclude or [])

    used_pointee_ids: set[str] = set()
    for envelope in track_element.iter("AutomationEnvelope"):
        pointee = envelope.find("EnvelopeTarget/PointeeId")
        if pointee is not None:
            used_pointee_ids.add(pointee.get("Value", ""))

    order = [1, 2, 3, 4, 5, 6, 0, 7]

    for band_idx in order:
        if band_idx in exclude:
            continue

        try:
            band_param = get_eq8_band(eq8_element, band_idx)
        except ValueError:
            continue

        gain_elem = band_param.find("Gain/Manual")
        if gain_elem is not None and float(gain_elem.get("Value", "0")) != 0:
            continue

        has_automation = False
        for param_name in ("Freq", "Gain", "Q", "IsOn"):
            try:
                target_id = get_automation_target_id(band_param, param_name)
                if target_id in used_pointee_ids:
                    has_automation = True
                    break
            except ValueError:
                continue

        if not has_automation:
            return band_idx

    raise EQ8SlotFullError(
        "All 8 EQ8 bands are in use or excluded. No slot available."
    )


def _remove_existing_envelope(track_element, target_id: str) -> bool:
    """Remove an existing AutomationEnvelope targeting the given PointeeId.

    Args:
        track_element: The track XML Element.
        target_id: The PointeeId value to match.

    Returns:
        True if an envelope was removed, False otherwise.
    """
    envelopes_node = track_element.find("AutomationEnvelopes/Envelopes")
    if envelopes_node is None:
        return False

    for envelope in list(envelopes_node):
        pointee = envelope.find("EnvelopeTarget/PointeeId")
        if pointee is not None and pointee.get("Value") == str(target_id):
            envelopes_node.remove(envelope)
            return True

    return False


def _feature_to_breakpoints(
    values: np.ndarray,
    times_sec: np.ndarray,
    tempo: float,
    max_points: int = 500,
) -> list[tuple[float, float]]:
    """Convert a feature curve + time axis to automation breakpoints.

    Args:
        values: Feature values (1-D array, same length as times_sec).
        times_sec: Timestamps in seconds.
        tempo: Project tempo in BPM.
        max_points: Maximum breakpoints (uses thin_breakpoints).

    Returns:
        List of (time_beats, value) tuples.
    """
    events: list[tuple[float, float]] = []
    n = min(len(values), len(times_sec))
    for i in range(n):
        t_beats = seconds_to_beats(float(times_sec[i]), tempo)
        events.append((t_beats, float(values[i])))
    return thin_breakpoints(events, max_points)


def _freq_to_eq8_value(freq_hz: float) -> float:
    """Clamp frequency to the EQ8 valid range (10 Hz - 22050 Hz).

    EQ8 stores frequency as raw Hz in the ALS XML.
    """
    return float(np.clip(freq_hz, 10.0, 22050.0))


def _gain_to_eq8_value(gain_db: float) -> float:
    """Clamp gain to the EQ8 valid range (-15 dB to +15 dB).

    EQ8 stores gain as raw dB in the ALS XML.
    """
    return float(np.clip(gain_db, -15.0, 15.0))


def _q_to_eq8_value(q: float) -> float:
    """Clamp Q to the EQ8 valid range (0.1 to 18.0).

    EQ8 stores Q as the raw factor in the ALS XML.
    """
    return float(np.clip(q, 0.1, 18.0))


def _zone_center_freq(zone: str) -> float:
    """Return the geometric center frequency of a perceptual zone."""
    if zone not in ZONE_RANGES:
        raise ValueError(f"Unknown zone: {zone}")
    lo, hi = ZONE_RANGES[zone]
    return float(np.sqrt(lo * hi))


def _prepare_track_eq8(
    als_path: Path | str,
    track_id: str,
    band_index: int | None = None,
    exclude_bands: list[int] | None = None,
) -> tuple:
    """Backup, parse, find track/EQ8, allocate band.

    Returns:
        (tree, track, eq8, band_idx, band_param, tempo, next_id_counter)
        where next_id_counter is a mutable [int] list.
    """
    als_path = Path(als_path)
    backup_als(str(als_path))
    tree = parse_als(str(als_path))

    try:
        track = find_track_by_name(tree, track_id)
    except ValueError as e:
        raise TrackNotFoundError(str(e)) from e

    eq8 = find_or_create_eq8(track, tree)

    if band_index is not None:
        bi = band_index
    else:
        bi = _find_available_band(eq8, track, exclude=exclude_bands)

    band_param = get_eq8_band(eq8, bi)
    tempo = _extract_tempo(tree)
    next_id = [get_next_id(tree)]

    return tree, track, eq8, bi, band_param, tempo, next_id


# ---------------------------------------------------------------------------
# Phase 3 — Adaptive filters (spec §5.A)
# ---------------------------------------------------------------------------

def write_adaptive_hpf(
    als_path: Path | str,
    track_id: str,
    low_rolloff_curve: np.ndarray,
    times: np.ndarray,
    valley_trajectories: list[PeakTrajectory] | None = None,
    safety_hz: float = 10.0,
    band_index: int | None = None,
) -> AutomationReport:
    """Write an adaptive high-pass filter automation.

    The HPF cutoff follows low_rolloff_curve minus safety_hz.
    Valley trajectories prevent cutting content above spectral gaps.

    Args:
        als_path: Path to the .als file.
        track_id: Track name in the Ableton project.
        low_rolloff_curve: Per-frame low rolloff frequency in Hz.
        times: Per-frame timestamps in seconds.
        valley_trajectories: Optional valley trajectories for safety.
        safety_hz: Safety margin below rolloff (Hz).
        band_index: Specific EQ8 band to use, or None for auto.

    Returns:
        AutomationReport.

    Raises:
        TrackNotFoundError: If track doesn't exist.
        EQ8SlotFullError: If no band is available.
    """
    tree, track, eq8, bi, band_param, tempo, next_id = _prepare_track_eq8(
        als_path, track_id, band_index
    )
    warnings: list[str] = []

    configure_eq8_band(band_param, mode=0, freq=80.0, q=0.71)
    ison = band_param.find("IsOn/Manual")
    if ison is not None:
        ison.set("Value", "true")

    cutoff = np.maximum(low_rolloff_curve - safety_hz, 20.0)

    if valley_trajectories:
        for traj in valley_trajectories:
            for frame_idx, freq, amp in traj.points:
                if 0 <= frame_idx < len(cutoff) and freq < cutoff[frame_idx]:
                    cutoff[frame_idx] = max(freq - safety_hz, 20.0)

    cutoff = np.array([_freq_to_eq8_value(f) for f in cutoff])

    breakpoints = _feature_to_breakpoints(cutoff, times, tempo)

    freq_target_id = get_automation_target_id(band_param, "Freq")
    _remove_existing_envelope(track, freq_target_id)
    write_automation_envelope(track, freq_target_id, breakpoints, next_id)

    save_als_from_tree(tree, str(als_path))

    return AutomationReport(
        success=True,
        breakpoints_written=len(breakpoints),
        eq8_band_index=bi,
        warnings=warnings,
    )


def write_adaptive_lpf(
    als_path: Path | str,
    track_id: str,
    high_rolloff_curve: np.ndarray,
    times: np.ndarray,
    safety_hz: float = 500.0,
    band_index: int | None = None,
) -> AutomationReport:
    """Write an adaptive low-pass filter automation.

    The LPF cutoff follows high_rolloff_curve plus safety_hz.

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        high_rolloff_curve: Per-frame high rolloff frequency in Hz.
        times: Per-frame timestamps in seconds.
        safety_hz: Safety margin above rolloff (Hz).
        band_index: Specific EQ8 band, or None for auto.

    Returns:
        AutomationReport.

    Raises:
        TrackNotFoundError: If track doesn't exist.
        EQ8SlotFullError: If no band is available.
    """
    tree, track, eq8, bi, band_param, tempo, next_id = _prepare_track_eq8(
        als_path, track_id, band_index
    )

    configure_eq8_band(band_param, mode=7, freq=16000.0, q=0.71)
    ison = band_param.find("IsOn/Manual")
    if ison is not None:
        ison.set("Value", "true")

    cutoff = np.array([
        _freq_to_eq8_value(f + safety_hz) for f in high_rolloff_curve
    ])

    breakpoints = _feature_to_breakpoints(cutoff, times, tempo)

    freq_target_id = get_automation_target_id(band_param, "Freq")
    _remove_existing_envelope(track, freq_target_id)
    write_automation_envelope(track, freq_target_id, breakpoints, next_id)

    save_als_from_tree(tree, str(als_path))

    return AutomationReport(
        success=True,
        breakpoints_written=len(breakpoints),
        eq8_band_index=bi,
        warnings=[],
    )


def write_safety_hpf(
    als_path: Path | str,
    track_id: str,
    sub_energy: np.ndarray,
    times: np.ndarray,
    threshold_db: float = -30.0,
    band_index: int | None = None,
) -> AutomationReport:
    """Write a safety HPF that engages only when sub energy is rumble.

    Fixed cutoff at 30 Hz.  Automates IsOn: active (1.0) when sub
    energy is below threshold (= rumble, not content), bypassed (0.0)
    when energy indicates real bass.

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        sub_energy: Per-frame sub zone energy in dB.
        times: Per-frame timestamps in seconds.
        threshold_db: Energy threshold below which HPF engages.
        band_index: Specific EQ8 band, or None for auto.

    Returns:
        AutomationReport.

    Raises:
        TrackNotFoundError: If track doesn't exist.
        EQ8SlotFullError: If no band is available.
    """
    tree, track, eq8, bi, band_param, tempo, next_id = _prepare_track_eq8(
        als_path, track_id, band_index
    )

    configure_eq8_band(band_param, mode=0, freq=30.0, q=0.71)
    ison_elem = band_param.find("IsOn/Manual")
    if ison_elem is not None:
        ison_elem.set("Value", "true")

    is_on_values = np.where(sub_energy < threshold_db, 1.0, 0.0)

    breakpoints = _feature_to_breakpoints(is_on_values, times, tempo)

    ison_target_id = get_automation_target_id(band_param, "IsOn")
    _remove_existing_envelope(track, ison_target_id)
    write_automation_envelope(track, ison_target_id, breakpoints, next_id)

    save_als_from_tree(tree, str(als_path))

    return AutomationReport(
        success=True,
        breakpoints_written=len(breakpoints),
        eq8_band_index=bi,
        warnings=[],
    )


# ---------------------------------------------------------------------------
# Phase 4 — Dynamic notches/bells (spec §5.B)
# ---------------------------------------------------------------------------

def write_dynamic_notch(
    als_path: Path | str,
    track_id: str,
    peak_trajectory: PeakTrajectory,
    times: np.ndarray,
    reduction_db: float = -4.0,
    band_index: int | None = None,
) -> AutomationReport:
    """Write a dynamic notch that tracks a peak trajectory.

    Automates both Freq (following the peak frequency) and Gain
    (reduction_db when the peak is present, 0 dB otherwise).
    Q is fixed at 8.0 for a narrow notch.

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        peak_trajectory: A single PeakTrajectory to follow.
        times: Per-frame timestamps in seconds.
        reduction_db: Notch depth in dB (negative).
        band_index: Specific EQ8 band, or None for auto.

    Returns:
        AutomationReport (breakpoints_written counts both Freq + Gain).

    Raises:
        TrackNotFoundError: If track doesn't exist.
        EQ8SlotFullError: If no band is available.
    """
    tree, track, eq8, bi, band_param, tempo, next_id = _prepare_track_eq8(
        als_path, track_id, band_index
    )

    configure_eq8_band(band_param, mode=4, q=8.0)
    ison = band_param.find("IsOn/Manual")
    if ison is not None:
        ison.set("Value", "true")

    n_frames = len(times)
    freq_curve = np.full(n_frames, peak_trajectory.mean_freq)
    gain_curve = np.zeros(n_frames)

    active_frames: set[int] = set()
    for frame_idx, freq_hz, amp_db in peak_trajectory.points:
        if 0 <= frame_idx < n_frames:
            freq_curve[frame_idx] = freq_hz
            gain_curve[frame_idx] = reduction_db
            active_frames.add(frame_idx)

    last_freq = peak_trajectory.mean_freq
    for i in range(n_frames):
        if i in active_frames:
            last_freq = freq_curve[i]
        else:
            freq_curve[i] = last_freq

    freq_curve = np.array([_freq_to_eq8_value(f) for f in freq_curve])
    gain_curve = np.array([_gain_to_eq8_value(g) for g in gain_curve])

    freq_bps = _feature_to_breakpoints(freq_curve, times, tempo)
    gain_bps = _feature_to_breakpoints(gain_curve, times, tempo)

    freq_target_id = get_automation_target_id(band_param, "Freq")
    gain_target_id = get_automation_target_id(band_param, "Gain")
    _remove_existing_envelope(track, freq_target_id)
    _remove_existing_envelope(track, gain_target_id)

    write_automation_envelope(track, freq_target_id, freq_bps, next_id)
    write_automation_envelope(track, gain_target_id, gain_bps, next_id)

    save_als_from_tree(tree, str(als_path))

    return AutomationReport(
        success=True,
        breakpoints_written=len(freq_bps) + len(gain_bps),
        eq8_band_index=bi,
        warnings=[],
    )


def write_dynamic_bell_cut(
    als_path: Path | str,
    track_id: str,
    zone_energy: np.ndarray,
    times: np.ndarray,
    zone_center_hz: float,
    threshold_db: float,
    max_cut_db: float = -6.0,
    band_index: int | None = None,
) -> AutomationReport:
    """Write a bell cut proportional to zone energy above a threshold.

    Freq is fixed at zone_center_hz.  Gain = 0 when energy is below
    threshold, proportional negative cut (up to max_cut_db) when above.

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        zone_energy: Per-frame zone energy in dB.
        times: Per-frame timestamps in seconds.
        zone_center_hz: Center frequency of the bell.
        threshold_db: Energy threshold above which cutting begins.
        max_cut_db: Maximum cut depth in dB (negative).
        band_index: Specific EQ8 band, or None for auto.

    Returns:
        AutomationReport.
    """
    tree, track, eq8, bi, band_param, tempo, next_id = _prepare_track_eq8(
        als_path, track_id, band_index
    )

    configure_eq8_band(
        band_param, mode=3, freq=_freq_to_eq8_value(zone_center_hz), q=2.0,
    )
    ison = band_param.find("IsOn/Manual")
    if ison is not None:
        ison.set("Value", "true")

    excess = np.maximum(zone_energy - threshold_db, 0.0)
    gain_curve = np.clip(-excess, max_cut_db, 0.0)
    gain_curve = np.array([_gain_to_eq8_value(g) for g in gain_curve])

    gain_bps = _feature_to_breakpoints(gain_curve, times, tempo)

    gain_target_id = get_automation_target_id(band_param, "Gain")
    _remove_existing_envelope(track, gain_target_id)
    write_automation_envelope(track, gain_target_id, gain_bps, next_id)

    save_als_from_tree(tree, str(als_path))

    return AutomationReport(
        success=True,
        breakpoints_written=len(gain_bps),
        eq8_band_index=bi,
        warnings=[],
    )


def write_resonance_suppression(
    als_path: Path | str,
    track_id: str,
    peak_trajectories: list[PeakTrajectory],
    times: np.ndarray,
    sensitivity: float = 0.5,
    max_bands: int = 3,
    band_index_start: int | None = None,
) -> list[AutomationReport]:
    """Soothe-style resonance suppression using multiple dynamic notches.

    Identifies the most resonant peaks (high amplitude, long duration)
    and creates one notch per peak, each on a separate EQ8 band.

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        peak_trajectories: All detected peak trajectories.
        times: Per-frame timestamps in seconds.
        sensitivity: Reduction aggressiveness (0.0 - 1.0).
        max_bands: Maximum number of EQ8 bands to use.
        band_index_start: First band index if specified, or None for auto.

    Returns:
        List of AutomationReport (one per band used).
    """
    scored: list[tuple[float, PeakTrajectory]] = []
    for peak in peak_trajectories:
        if peak.duration_frames < 5:
            continue
        strength = max(peak.mean_amplitude + 60, 0)
        score = strength * peak.duration_frames * sensitivity
        scored.append((score, peak))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = scored[:max_bands]

    if not selected:
        return [AutomationReport(
            success=True, breakpoints_written=0, eq8_band_index=-1,
            warnings=["No resonant peaks found"],
        )]

    als_path = Path(als_path)
    backup_als(str(als_path))
    tree = parse_als(str(als_path))

    try:
        track = find_track_by_name(tree, track_id)
    except ValueError as e:
        raise TrackNotFoundError(str(e)) from e

    eq8 = find_or_create_eq8(track, tree)
    tempo = _extract_tempo(tree)
    next_id = [get_next_id(tree)]

    reports: list[AutomationReport] = []
    exclude: list[int] = []
    n_frames = len(times)

    for i, (_score, peak) in enumerate(selected):
        if band_index_start is not None:
            bi = band_index_start + i
        else:
            bi = _find_available_band(eq8, track, exclude=exclude)
        exclude.append(bi)

        band_param = get_eq8_band(eq8, bi)
        configure_eq8_band(band_param, mode=4, q=8.0)
        ison = band_param.find("IsOn/Manual")
        if ison is not None:
            ison.set("Value", "true")

        freq_curve = np.full(n_frames, peak.mean_freq)
        gain_curve = np.zeros(n_frames)
        reduction = _gain_to_eq8_value(
            -sensitivity * max(peak.mean_amplitude + 60, 2)
        )

        active_frames: set[int] = set()
        for frame_idx, freq_hz, amp_db in peak.points:
            if 0 <= frame_idx < n_frames:
                freq_curve[frame_idx] = freq_hz
                gain_curve[frame_idx] = reduction
                active_frames.add(frame_idx)

        last_freq = peak.mean_freq
        for j in range(n_frames):
            if j in active_frames:
                last_freq = freq_curve[j]
            else:
                freq_curve[j] = last_freq

        freq_curve = np.array([_freq_to_eq8_value(f) for f in freq_curve])

        freq_bps = _feature_to_breakpoints(freq_curve, times, tempo)
        gain_bps = _feature_to_breakpoints(gain_curve, times, tempo)

        freq_target_id = get_automation_target_id(band_param, "Freq")
        gain_target_id = get_automation_target_id(band_param, "Gain")
        _remove_existing_envelope(track, freq_target_id)
        _remove_existing_envelope(track, gain_target_id)

        write_automation_envelope(track, freq_target_id, freq_bps, next_id)
        write_automation_envelope(track, gain_target_id, gain_bps, next_id)

        reports.append(AutomationReport(
            success=True,
            breakpoints_written=len(freq_bps) + len(gain_bps),
            eq8_band_index=bi,
            warnings=[],
        ))

    save_als_from_tree(tree, str(als_path))
    return reports


# ---------------------------------------------------------------------------
# Phase 5 — Adaptive boosts (spec §5.C)
# ---------------------------------------------------------------------------

def write_adaptive_presence_boost(
    als_path: Path | str,
    track_id: str,
    presence_energy: np.ndarray,
    times: np.ndarray,
    threshold_db: float = -18.0,
    max_boost_db: float = 3.0,
    band_index: int | None = None,
) -> AutomationReport:
    """Write an adaptive presence boost (2-4 kHz).

    Boosts when presence zone energy is below threshold.
    Bell at 3000 Hz, Q=1.0.

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        presence_energy: Per-frame presence zone energy in dB.
        times: Per-frame timestamps in seconds.
        threshold_db: Energy below which boost engages.
        max_boost_db: Maximum boost in dB (positive).
        band_index: Specific EQ8 band, or None for auto.

    Returns:
        AutomationReport.

    Raises:
        TrackNotFoundError: If track doesn't exist.
        EQ8SlotFullError: If no band is available.
    """
    tree, track, eq8, bi, band_param, tempo, next_id = _prepare_track_eq8(
        als_path, track_id, band_index
    )

    configure_eq8_band(band_param, mode=3, freq=3000.0, q=1.0)
    ison = band_param.find("IsOn/Manual")
    if ison is not None:
        ison.set("Value", "true")

    deficit = np.maximum(threshold_db - presence_energy, 0.0)
    gain_curve = np.minimum(deficit, max_boost_db)
    gain_curve = np.array([_gain_to_eq8_value(g) for g in gain_curve])

    gain_bps = _feature_to_breakpoints(gain_curve, times, tempo)

    gain_target_id = get_automation_target_id(band_param, "Gain")
    _remove_existing_envelope(track, gain_target_id)
    write_automation_envelope(track, gain_target_id, gain_bps, next_id)

    save_als_from_tree(tree, str(als_path))

    return AutomationReport(
        success=True,
        breakpoints_written=len(gain_bps),
        eq8_band_index=bi,
        warnings=[],
    )


def write_adaptive_air_boost(
    als_path: Path | str,
    track_id: str,
    high_rolloff_curve: np.ndarray,
    times: np.ndarray,
    threshold_hz: float = 8000.0,
    max_boost_db: float = 2.0,
    band_index: int | None = None,
) -> AutomationReport:
    """Write an adaptive air boost (high shelf).

    Boosts when high rolloff frequency is below threshold_hz,
    indicating the track lacks high-frequency content.
    HighShelf at 10000 Hz.

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        high_rolloff_curve: Per-frame high rolloff frequency in Hz.
        times: Per-frame timestamps in seconds.
        threshold_hz: Rolloff threshold below which boost engages.
        max_boost_db: Maximum boost in dB (positive).
        band_index: Specific EQ8 band, or None for auto.

    Returns:
        AutomationReport.

    Raises:
        TrackNotFoundError: If track doesn't exist.
        EQ8SlotFullError: If no band is available.
    """
    tree, track, eq8, bi, band_param, tempo, next_id = _prepare_track_eq8(
        als_path, track_id, band_index
    )

    configure_eq8_band(band_param, mode=5, freq=10000.0, q=0.71)
    ison = band_param.find("IsOn/Manual")
    if ison is not None:
        ison.set("Value", "true")

    deficit = np.maximum(threshold_hz - high_rolloff_curve, 0.0)
    scaling = max_boost_db / max(threshold_hz, 1.0)
    gain_curve = np.minimum(deficit * scaling, max_boost_db)
    gain_curve = np.array([_gain_to_eq8_value(g) for g in gain_curve])

    gain_bps = _feature_to_breakpoints(gain_curve, times, tempo)

    gain_target_id = get_automation_target_id(band_param, "Gain")
    _remove_existing_envelope(track, gain_target_id)
    write_automation_envelope(track, gain_target_id, gain_bps, next_id)

    save_als_from_tree(tree, str(als_path))

    return AutomationReport(
        success=True,
        breakpoints_written=len(gain_bps),
        eq8_band_index=bi,
        warnings=[],
    )
