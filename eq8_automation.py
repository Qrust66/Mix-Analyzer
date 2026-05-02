#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EQ8 Automation Engine — v2.8.0

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

import json
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
# Ableton EQ8 mapping — single source of truth for validation
# ---------------------------------------------------------------------------

_MAPPING_PATH = Path(__file__).resolve().parent / "ableton" / "ableton_devices_mapping.json"


def _load_eq8_mapping() -> dict:
    """Load the EQ8 section of ableton_devices_mapping.json at module init.

    Raises:
        RuntimeError: If the mapping file is missing or malformed — we
            refuse to run without the ground truth since every write_*
            function validates against it.
    """
    try:
        with open(_MAPPING_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data["devices"]["Eq8"]
    except (OSError, json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(
            f"Cannot load EQ8 mapping from {_MAPPING_PATH}: {e}. "
            "eq8_automation.py requires this file to validate automation "
            "parameters against the Live device spec."
        ) from e


_EQ8_MAPPING = _load_eq8_mapping()
_EQ8_AUTOMATION_SPEC = _EQ8_MAPPING["automation_values"]
_GAIN_INOPERATIVE_MODES: set[int] = set(
    _EQ8_MAPPING["band_params"]["Mode"]["gain_inoperative_modes"]
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TrackNotFoundError(Exception):
    """Raised when track_id does not exist in the .als file."""


class EQ8SlotFullError(Exception):
    """Raised when no EQ8 band is available for automation."""


class EQ8ValidationError(Exception):
    """Raised when an automation parameter violates the EQ8 device spec.

    The spec is loaded from ableton_devices_mapping.json — see
    ``automation_values`` and ``band_params.Mode.gain_inoperative_modes``.
    """


# ---------------------------------------------------------------------------
# Validation helpers — run before every write_automation_envelope() call
# ---------------------------------------------------------------------------


def _band_mode(band_param) -> int:
    """Read the Mode/Manual integer value from an EQ8 band ParameterA."""
    manual = band_param.find("Mode/Manual")
    if manual is None or manual.get("Value") is None:
        raise EQ8ValidationError("Band ParameterA has no Mode/Manual value.")
    return int(manual.get("Value"))


def _validate_eq8_automation(
    band_param,
    param_name: str,
    breakpoints: list[tuple[float, float]],
) -> None:
    """Validate an automation envelope before writing it to the .als.

    Enforces three invariants from the Live device spec:
      1. ``param_name`` is a known EQ8 automatable parameter.
      2. All breakpoint values fall within the parameter's declared range.
      3. Gain automation is refused on modes listed in
         ``gain_inoperative_modes`` ([0, 1, 4, 6, 7] — LowCut, Notch, HighCut).

    Args:
        band_param: The ``ParameterA`` Element the automation targets.
        param_name: One of ``"Freq"``, ``"Gain"``, ``"Q"``, ``"IsOn"``.
        breakpoints: The ``[(time_beats, value), ...]`` list about to be
            written (the pre-song default event is NOT included here).

    Raises:
        EQ8ValidationError: If any invariant is violated.
    """
    if param_name not in _EQ8_AUTOMATION_SPEC:
        raise EQ8ValidationError(
            f"Unknown EQ8 automation parameter '{param_name}'. "
            f"Known: {sorted(_EQ8_AUTOMATION_SPEC)}"
        )

    spec = _EQ8_AUTOMATION_SPEC[param_name]

    if param_name == "Gain":
        mode = _band_mode(band_param)
        if mode in _GAIN_INOPERATIVE_MODES:
            raise EQ8ValidationError(
                f"Cannot write Gain automation on Mode {mode} "
                f"(gain_inoperative_modes = {sorted(_GAIN_INOPERATIVE_MODES)}). "
                "Use Bell (3), Low Shelf (2) or High Shelf (5) instead."
            )

    if not breakpoints:
        return  # nothing to validate

    values = [v for _, v in breakpoints]
    vmin, vmax = float(min(values)), float(max(values))

    if spec["encoding"] == "bool":
        # Callers pass numeric inputs (0/1, 0.0/1.0, np.bool_); the
        # write layer converts to "true"/"false" using the v1.8 BoolEvent
        # convention. Accept any value that round-trips to a strict 0 or 1.
        bad = [v for v in values if float(v) not in (0.0, 1.0)]
        if bad:
            raise EQ8ValidationError(
                f"{param_name} envelope contains non-boolean values "
                f"(must be 0 or 1; written as <BoolEvent Value=\"true|false\"/>): "
                f"first offending = {bad[0]}"
            )
        return

    rmin = float(spec["min"])
    rmax = float(spec["max"])
    if vmin < rmin or vmax > rmax:
        raise EQ8ValidationError(
            f"{param_name} envelope values {vmin:.3f}..{vmax:.3f} "
            f"outside declared range [{rmin}, {rmax}] {spec['unit']}."
        )


def _write_validated_env(
    track,
    band_param,
    param_name: str,
    breakpoints: list[tuple[float, float]],
    next_id_counter: list[int],
) -> None:
    """Validate an envelope against the EQ8 spec, then write it.

    Wraps the "remove existing + write new" pattern behind a single
    validation gate so every automation write in this module is
    guaranteed to have passed ``_validate_eq8_automation()``.

    Raises:
        EQ8ValidationError: If the envelope violates the spec.
    """
    _validate_eq8_automation(band_param, param_name, breakpoints)
    target_id = get_automation_target_id(band_param, param_name)
    _remove_existing_envelope(track, target_id)
    event_type = _EQ8_AUTOMATION_SPEC[param_name].get("event_type", "FloatEvent")
    write_automation_envelope(
        track, target_id, breakpoints, next_id_counter, event_type=event_type
    )


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


# Module-level tag stamped on EQ8 devices created by this module. Callers
# (e.g. smoke_test_corrections.py) can set this to identify generated devices
# in Ableton's UI.
NEW_EQ8_USER_NAME: str | None = None


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

    eq8 = find_or_create_eq8(track, tree, user_name=NEW_EQ8_USER_NAME)

    if band_index is not None:
        bi = band_index
    else:
        bi = _find_available_band(eq8, track, exclude=exclude_bands)

    band_param = get_eq8_band(eq8, bi)
    tempo = _extract_tempo(tree)
    next_id = [get_next_id(tree)]

    return tree, track, eq8, bi, band_param, tempo, next_id


# ---------------------------------------------------------------------------
# Audibility masking (v2.5.1)
# ---------------------------------------------------------------------------

def _mask_by_audibility(
    breakpoints: list[tuple[float, float]],
    automation_map,
    tempo: float,
) -> list[tuple[float, float]]:
    """Remove breakpoints where the track is inaudible.

    Uses the TrackAutomationMap to check if the track is audible at each
    breakpoint's timestamp. Breakpoints in muted sections are dropped.

    Args:
        breakpoints: List of (time_beats, value) tuples.
        automation_map: TrackAutomationMap for the track (or None to skip).
        tempo: Project tempo in BPM.

    Returns:
        Filtered list of breakpoints.
    """
    if automation_map is None or len(breakpoints) == 0:
        return breakpoints

    from als_utils import beats_to_seconds
    from automation_map import resample_audibility

    times_sec = np.array([beats_to_seconds(t, tempo) for t, _ in breakpoints])
    audible = resample_audibility(automation_map, times_sec)

    return [bp for bp, is_aud in zip(breakpoints, audible) if is_aud]


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
    automation_map=None,
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
        automation_map: Optional TrackAutomationMap to mask muted sections.

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
    breakpoints = _mask_by_audibility(breakpoints, automation_map, tempo)

    _write_validated_env(track, band_param, "Freq", breakpoints, next_id)

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
    automation_map=None,
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
    breakpoints = _mask_by_audibility(breakpoints, automation_map, tempo)

    _write_validated_env(track, band_param, "Freq", breakpoints, next_id)

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
    automation_map=None,
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
    breakpoints = _mask_by_audibility(breakpoints, automation_map, tempo)

    _write_validated_env(track, band_param, "IsOn", breakpoints, next_id)

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
    automation_map=None,
    proportional: bool = True,
    threshold_db: float = -40.0,
    q: float = 8.0,
) -> AutomationReport:
    """Write a dynamic notch that tracks a peak trajectory.

    The band is configured as a narrow Bell (Mode 3), not Notch (Mode 4),
    because EQ8's Gain parameter is inoperative on Mode in [0, 1, 4, 6, 7]
    (see ableton_devices_mapping.json "gain_inoperative_modes"). A narrow
    Bell with a negative Gain envelope produces an automatable notch.

    Automates both Freq (following the peak frequency) and Gain.

    When proportional=True (default), the cut depth scales with the peak's
    amplitude at each frame: louder peaks are cut more, up to reduction_db.
    When proportional=False, a flat reduction_db is applied whenever the
    peak is active.

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        peak_trajectory: A single PeakTrajectory to follow.
        times: Per-frame timestamps in seconds.
        reduction_db: Maximum notch depth in dB (negative).
        band_index: Specific EQ8 band, or None for auto.
        automation_map: Optional TrackAutomationMap to mask muted sections.
        proportional: Scale reduction with peak amplitude (default True).
        threshold_db: Amplitude floor below which no reduction is applied.
        q: Bell Q factor (default 8.0, narrow — mimics a notch).

    Returns:
        AutomationReport (breakpoints_written counts both Freq + Gain).
    """
    tree, track, eq8, bi, band_param, tempo, next_id = _prepare_track_eq8(
        als_path, track_id, band_index
    )

    # Mode 3 (Bell), not Mode 4 (Notch): the EQ8 Gain is inoperative on
    # Mode in [0, 1, 4, 6, 7] per ableton_devices_mapping.json. A narrow
    # Bell (Q>=8) with a negative Gain envelope produces a dynamic notch
    # whose depth is actually automatable.
    configure_eq8_band(band_param, mode=3, q=_q_to_eq8_value(q))
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
            if proportional:
                excess = max(amp_db - threshold_db, 0.0)
                scale = min(excess / max(-threshold_db, 1.0), 1.0)
                gain_curve[frame_idx] = reduction_db * scale
            else:
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
    freq_bps = _mask_by_audibility(freq_bps, automation_map, tempo)
    gain_bps = _mask_by_audibility(gain_bps, automation_map, tempo)

    _write_validated_env(track, band_param, "Freq", freq_bps, next_id)
    _write_validated_env(track, band_param, "Gain", gain_bps, next_id)

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
    automation_map=None,
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
    gain_bps = _mask_by_audibility(gain_bps, automation_map, tempo)

    _write_validated_env(track, band_param, "Gain", gain_bps, next_id)

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
    automation_map=None,
    threshold_db: float = -40.0,
    q: float = 8.0,
) -> list[AutomationReport]:
    """Soothe-style resonance suppression using multiple narrow Bells.

    Identifies the most resonant peaks and creates one narrow Bell per peak
    (Mode 3, not Mode 4 — see write_dynamic_notch for the rationale: EQ8
    Gain is inoperative on Mode in [0, 1, 4, 6, 7]).
    Reduction is proportional to each frame's amplitude: louder frames
    get cut more aggressively, scaled by sensitivity.

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        peak_trajectories: All detected peak trajectories.
        times: Per-frame timestamps in seconds.
        sensitivity: Reduction aggressiveness (0.0 - 1.0).
        max_bands: Maximum number of EQ8 bands to use.
        band_index_start: First band index if specified, or None for auto.
        automation_map: Optional TrackAutomationMap to mask muted sections.
        threshold_db: Amplitude floor below which no reduction is applied.
        q: Bell Q factor (default 8.0, narrow — mimics a notch).

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
        # Mode 3 (Bell), not Mode 4 (Notch): EQ8 Gain is inoperative on
        # Mode in [0, 1, 4, 6, 7] — see write_dynamic_notch for details.
        configure_eq8_band(band_param, mode=3, q=_q_to_eq8_value(q))
        ison = band_param.find("IsOn/Manual")
        if ison is not None:
            ison.set("Value", "true")

        freq_curve = np.full(n_frames, peak.mean_freq)
        gain_curve = np.zeros(n_frames)
        max_reduction = _gain_to_eq8_value(
            -sensitivity * max(peak.mean_amplitude + 60, 2)
        )

        active_frames: set[int] = set()
        for frame_idx, freq_hz, amp_db in peak.points:
            if 0 <= frame_idx < n_frames:
                freq_curve[frame_idx] = freq_hz
                excess = max(amp_db - threshold_db, 0.0)
                scale = min(excess / max(-threshold_db, 1.0), 1.0)
                gain_curve[frame_idx] = max_reduction * scale
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
        freq_bps = _mask_by_audibility(freq_bps, automation_map, tempo)
        gain_bps = _mask_by_audibility(gain_bps, automation_map, tempo)

        _write_validated_env(track, band_param, "Freq", freq_bps, next_id)
        _write_validated_env(track, band_param, "Gain", gain_bps, next_id)

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
    automation_map=None,
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
    gain_bps = _mask_by_audibility(gain_bps, automation_map, tempo)

    _write_validated_env(track, band_param, "Gain", gain_bps, next_id)

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
    automation_map=None,
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
    gain_bps = _mask_by_audibility(gain_bps, automation_map, tempo)

    _write_validated_env(track, band_param, "Gain", gain_bps, next_id)

    save_als_from_tree(tree, str(als_path))

    return AutomationReport(
        success=True,
        breakpoints_written=len(gain_bps),
        eq8_band_index=bi,
        warnings=[],
    )


# ---------------------------------------------------------------------------
# Phase 6 — Cross-track masking (spec §5.D)
# ---------------------------------------------------------------------------

def detect_masking(
    track_a_zone_energy: Dict[str, np.ndarray],
    track_b_zone_energy: Dict[str, np.ndarray],
    times: np.ndarray,
    zones: list[str] | None = None,
    threshold_db: float = -60.0,
) -> MaskingReport:
    """Detect frequency masking between two tracks.

    Pure analysis — no ALS modification.  For each zone, computes a
    per-frame masking score based on the overlap of energy from both
    tracks (both must be above threshold_db).

    Args:
        track_a_zone_energy: Zone energy dict for track A (zone -> dB array).
        track_b_zone_energy: Zone energy dict for track B (zone -> dB array).
        times: Per-frame timestamps in seconds.
        zones: Zones to analyse (default: low, mud, low_mid).
        threshold_db: Minimum energy for a zone to count as "active".

    Returns:
        MaskingReport with per-zone scores and overall severity.
    """
    if zones is None:
        zones = ["low", "mud", "low_mid"]

    scores: Dict[str, np.ndarray] = {}
    n = len(times)

    for zone in zones:
        a = track_a_zone_energy.get(zone, np.full(n, -120.0))
        b = track_b_zone_energy.get(zone, np.full(n, -120.0))
        min_len = min(len(a), len(b), n)
        a, b = a[:min_len], b[:min_len]

        gate = ((a > threshold_db) & (b > threshold_db)).astype(float)
        a_lin = np.power(10, a / 20.0)
        b_lin = np.power(10, b / 20.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.minimum(a_lin, b_lin) / (np.maximum(a_lin, b_lin) + 1e-12)
        score = ratio * gate

        padded = np.zeros(n)
        padded[:min_len] = score
        scores[zone] = np.round(padded, 3)

    zone_means = [float(np.mean(s)) for s in scores.values()]
    severity = float(max(zone_means)) if zone_means else 0.0
    zones_affected = [z for z in zones if float(np.mean(scores[z])) > 0.05]

    return MaskingReport(
        zones=zones_affected,
        scores=scores,
        severity=round(severity, 3),
        times=times,
    )


def write_masking_reciprocal_cuts(
    als_path: Path | str,
    track_a_id: str,
    track_b_id: str,
    masking_report: MaskingReport,
    zone_center_hz: float,
    times: np.ndarray,
    reduction_db: float = -3.0,
    band_index_a: int | None = None,
    band_index_b: int | None = None,
    automation_map_a=None,
    automation_map_b=None,
) -> tuple[AutomationReport, AutomationReport]:
    """Write reciprocal bell cuts on two tracks to reduce masking.

    Both tracks get a bell cut at zone_center_hz with gain proportional
    to the masking score from the MaskingReport.

    Args:
        als_path: Path to the .als file.
        track_a_id: First track name.
        track_b_id: Second track name.
        masking_report: Result of detect_masking().
        zone_center_hz: Center frequency for the bell cuts.
        times: Per-frame timestamps in seconds.
        reduction_db: Maximum cut depth per track (negative).
        band_index_a: EQ8 band for track A, or None for auto.
        band_index_b: EQ8 band for track B, or None for auto.

    Returns:
        Tuple of (report_a, report_b).
    """
    combined_score = np.zeros(len(times))
    for zone_score in masking_report.scores.values():
        min_len = min(len(zone_score), len(combined_score))
        combined_score[:min_len] += zone_score[:min_len]
    if masking_report.scores:
        combined_score /= len(masking_report.scores)

    als_path = Path(als_path)
    backup_als(str(als_path))
    tree = parse_als(str(als_path))
    tempo = _extract_tempo(tree)
    next_id = [get_next_id(tree)]

    reports: list[AutomationReport] = []
    auto_maps = [automation_map_a, automation_map_b]
    for idx_pair, (track_id, band_idx) in enumerate([(track_a_id, band_index_a),
                                                      (track_b_id, band_index_b)]):
        try:
            track = find_track_by_name(tree, track_id)
        except ValueError as e:
            raise TrackNotFoundError(str(e)) from e

        eq8 = find_or_create_eq8(track, tree)
        if band_idx is not None:
            bi = band_idx
        else:
            bi = _find_available_band(eq8, track)

        band_param = get_eq8_band(eq8, bi)
        configure_eq8_band(
            band_param, mode=3, freq=_freq_to_eq8_value(zone_center_hz), q=2.0,
        )
        ison = band_param.find("IsOn/Manual")
        if ison is not None:
            ison.set("Value", "true")

        gain_curve = np.array([
            _gain_to_eq8_value(reduction_db * s) for s in combined_score
        ])
        gain_bps = _feature_to_breakpoints(gain_curve, times, tempo)
        gain_bps = _mask_by_audibility(gain_bps, auto_maps[idx_pair], tempo)

        _write_validated_env(track, band_param, "Gain", gain_bps, next_id)

        reports.append(AutomationReport(
            success=True,
            breakpoints_written=len(gain_bps),
            eq8_band_index=bi,
            warnings=[],
        ))

    save_als_from_tree(tree, str(als_path))
    return (reports[0], reports[1])


def write_targeted_sidechain_eq(
    als_path: Path | str,
    ducking_track_id: str,
    trigger_zone_energy: np.ndarray,
    times: np.ndarray,
    zone_center_hz: float,
    reduction_db: float = -6.0,
    threshold_db: float = -20.0,
    band_index: int | None = None,
    automation_map=None,
) -> AutomationReport:
    """Write a sidechain-style bell cut triggered by another track's energy.

    When trigger_zone_energy exceeds threshold, the ducking track
    gets a proportional bell cut at zone_center_hz.

    Args:
        als_path: Path to the .als file.
        ducking_track_id: Track to apply the cut on.
        trigger_zone_energy: Per-frame zone energy from the trigger track (dB).
        times: Per-frame timestamps in seconds.
        zone_center_hz: Center frequency for the bell cut.
        reduction_db: Maximum cut depth (negative).
        threshold_db: Trigger energy threshold.
        band_index: Specific EQ8 band, or None for auto.

    Returns:
        AutomationReport.
    """
    tree, track, eq8, bi, band_param, tempo, next_id = _prepare_track_eq8(
        als_path, ducking_track_id, band_index
    )

    configure_eq8_band(
        band_param, mode=3, freq=_freq_to_eq8_value(zone_center_hz), q=2.0,
    )
    ison = band_param.find("IsOn/Manual")
    if ison is not None:
        ison.set("Value", "true")

    excess = np.maximum(trigger_zone_energy - threshold_db, 0.0)
    gain_curve = np.clip(-excess, reduction_db, 0.0)
    gain_curve = np.array([_gain_to_eq8_value(g) for g in gain_curve])

    gain_bps = _feature_to_breakpoints(gain_curve, times, tempo)
    gain_bps = _mask_by_audibility(gain_bps, automation_map, tempo)

    _write_validated_env(track, band_param, "Gain", gain_bps, next_id)

    save_als_from_tree(tree, str(als_path))

    return AutomationReport(
        success=True,
        breakpoints_written=len(gain_bps),
        eq8_band_index=bi,
        warnings=[],
    )


# ---------------------------------------------------------------------------
# Phase 7 — Events / vocal (spec §5.E-F)
# ---------------------------------------------------------------------------

def write_transient_aware_cut(
    als_path: Path | str,
    track_id: str,
    base_cut_db: float,
    freq_hz: float,
    transient_events: list[TransientEvent],
    times: np.ndarray,
    release_ms: float = 50.0,
    band_index: int | None = None,
    automation_map=None,
) -> AutomationReport:
    """Write a bell cut that backs off during transients.

    A constant base_cut_db is applied, except during transient events
    where gain ramps to 0 (letting the transient through) then decays
    back to base_cut_db over release_ms.

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        base_cut_db: Steady-state cut depth (negative dB).
        freq_hz: Bell center frequency.
        transient_events: Detected transient events.
        times: Per-frame timestamps in seconds.
        release_ms: Release time after transient (ms).
        band_index: Specific EQ8 band, or None for auto.

    Returns:
        AutomationReport.
    """
    tree, track, eq8, bi, band_param, tempo, next_id = _prepare_track_eq8(
        als_path, track_id, band_index
    )

    configure_eq8_band(
        band_param, mode=3, freq=_freq_to_eq8_value(freq_hz), q=2.0,
    )
    ison = band_param.find("IsOn/Manual")
    if ison is not None:
        ison.set("Value", "true")

    n_frames = len(times)
    gain_curve = np.full(n_frames, _gain_to_eq8_value(base_cut_db))

    frame_duration = float(times[1] - times[0]) if n_frames > 1 else 0.167
    release_sec = release_ms / 1000.0
    release_frames = max(1, int(release_sec / frame_duration))

    for ev in transient_events:
        fi = ev.frame_idx
        if 0 <= fi < n_frames:
            gain_curve[fi] = 0.0
            for r in range(1, release_frames + 1):
                idx = fi + r
                if idx < n_frames:
                    decay = _gain_to_eq8_value(base_cut_db) * (r / release_frames)
                    gain_curve[idx] = min(gain_curve[idx], decay)

    gain_bps = _feature_to_breakpoints(gain_curve, times, tempo)
    gain_bps = _mask_by_audibility(gain_bps, automation_map, tempo)

    _write_validated_env(track, band_param, "Gain", gain_bps, next_id)

    save_als_from_tree(tree, str(als_path))

    return AutomationReport(
        success=True,
        breakpoints_written=len(gain_bps),
        eq8_band_index=bi,
        warnings=[],
    )


def write_section_aware_eq(
    als_path: Path | str,
    track_id: str,
    delta_spectrum: np.ndarray,
    times: np.ndarray,
    threshold: float = 0.3,
    band_index: int | None = None,
    automation_map=None,
) -> AutomationReport:
    """Write staircase EQ automation based on section transitions.

    Detects section boundaries from delta_spectrum exceeding threshold,
    then generates step-wise gain automation (one constant value per
    section) rather than continuous modulation.

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        delta_spectrum: Per-frame spectral change magnitude.
        times: Per-frame timestamps in seconds.
        threshold: Delta threshold for section boundary detection.
        band_index: Specific EQ8 band, or None for auto.

    Returns:
        AutomationReport.
    """
    tree, track, eq8, bi, band_param, tempo, next_id = _prepare_track_eq8(
        als_path, track_id, band_index
    )

    configure_eq8_band(band_param, mode=3, freq=1000.0, q=1.0)
    ison = band_param.find("IsOn/Manual")
    if ison is not None:
        ison.set("Value", "true")

    n_frames = len(delta_spectrum)
    boundaries = [0]
    for i in range(1, n_frames):
        if delta_spectrum[i] > threshold:
            boundaries.append(i)
    boundaries.append(n_frames)

    gain_curve = np.zeros(n_frames)
    for seg_idx in range(len(boundaries) - 1):
        start = boundaries[seg_idx]
        end = boundaries[seg_idx + 1]
        seg_mean = float(np.mean(delta_spectrum[start:end]))
        gain_curve[start:end] = _gain_to_eq8_value(-seg_mean * 2)

    gain_bps = _feature_to_breakpoints(gain_curve, times, tempo)
    gain_bps = _mask_by_audibility(gain_bps, automation_map, tempo)

    _write_validated_env(track, band_param, "Gain", gain_bps, next_id)

    save_als_from_tree(tree, str(als_path))

    return AutomationReport(
        success=True,
        breakpoints_written=len(gain_bps),
        eq8_band_index=bi,
        warnings=[],
    )


def write_dynamic_deesser(
    als_path: Path | str,
    track_id: str,
    sibilance_energy: np.ndarray,
    times: np.ndarray,
    threshold_db: float = -18.0,
    reduction_db: float = -4.0,
    band_index: int | None = None,
    automation_map=None,
) -> AutomationReport:
    """Write a dynamic de-esser automation.

    Bell at 6500 Hz, Q=4.0.  Applies reduction when sibilance zone
    energy exceeds threshold, 0 dB otherwise.

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        sibilance_energy: Per-frame sibilance zone energy in dB.
        times: Per-frame timestamps in seconds.
        threshold_db: Sibilance threshold above which de-essing engages.
        reduction_db: Cut depth when active (negative).
        band_index: Specific EQ8 band, or None for auto.

    Returns:
        AutomationReport.
    """
    tree, track, eq8, bi, band_param, tempo, next_id = _prepare_track_eq8(
        als_path, track_id, band_index
    )

    configure_eq8_band(
        band_param, mode=3, freq=6500.0, q=_q_to_eq8_value(4.0),
    )
    ison = band_param.find("IsOn/Manual")
    if ison is not None:
        ison.set("Value", "true")

    gain_curve = np.where(
        sibilance_energy > threshold_db,
        _gain_to_eq8_value(reduction_db),
        0.0,
    )

    gain_bps = _feature_to_breakpoints(gain_curve, times, tempo)
    gain_bps = _mask_by_audibility(gain_bps, automation_map, tempo)

    _write_validated_env(track, band_param, "Gain", gain_bps, next_id)

    save_als_from_tree(tree, str(als_path))

    return AutomationReport(
        success=True,
        breakpoints_written=len(gain_bps),
        eq8_band_index=bi,
        warnings=[],
    )


# ---------------------------------------------------------------------------
# Phase 8 — Reference matching (spec §5.G, optional)
# ---------------------------------------------------------------------------

def write_spectral_match(
    als_path: Path | str,
    track_id: str,
    track_zone_energy: Dict[str, np.ndarray],
    target_zone_energy: Dict[str, np.ndarray],
    times: np.ndarray,
    zones: list[str] | None = None,
    max_correction_db: float = 6.0,
    automation_map=None,
) -> list[AutomationReport]:
    """Match a track's spectral profile to a reference target.

    For each zone, computes delta = target - track energy and writes
    a bell EQ at the zone center to correct the difference (clamped
    to +/- max_correction_db).

    Args:
        als_path: Path to the .als file.
        track_id: Track name.
        track_zone_energy: Zone energy dict for the track (zone -> dB array).
        target_zone_energy: Zone energy dict for the reference (zone -> dB array).
        times: Per-frame timestamps in seconds.
        zones: Zones to match (default: body, mid, presence, air).
        max_correction_db: Maximum correction per zone (dB, applied +/-).

    Returns:
        List of AutomationReport (one per zone corrected).
    """
    if zones is None:
        zones = ["body", "mid", "presence", "air"]

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
    n = len(times)

    for zone in zones:
        t_energy = track_zone_energy.get(zone, np.full(n, -60.0))
        r_energy = target_zone_energy.get(zone, np.full(n, -60.0))
        min_len = min(len(t_energy), len(r_energy), n)

        delta = r_energy[:min_len] - t_energy[:min_len]
        correction = np.clip(delta, -max_correction_db, max_correction_db)

        padded = np.zeros(n)
        padded[:min_len] = correction

        try:
            bi = _find_available_band(eq8, track, exclude=exclude)
        except EQ8SlotFullError:
            reports.append(AutomationReport(
                success=False, breakpoints_written=0, eq8_band_index=-1,
                warnings=[f"No band available for zone {zone}"],
            ))
            continue

        exclude.append(bi)
        band_param = get_eq8_band(eq8, bi)

        center = _zone_center_freq(zone)
        configure_eq8_band(
            band_param, mode=3, freq=_freq_to_eq8_value(center), q=1.5,
        )
        ison = band_param.find("IsOn/Manual")
        if ison is not None:
            ison.set("Value", "true")

        gain_curve = np.array([_gain_to_eq8_value(g) for g in padded])
        gain_bps = _feature_to_breakpoints(gain_curve, times, tempo)
        gain_bps = _mask_by_audibility(gain_bps, automation_map, tempo)

        _write_validated_env(track, band_param, "Gain", gain_bps, next_id)

        reports.append(AutomationReport(
            success=True,
            breakpoints_written=len(gain_bps),
            eq8_band_index=bi,
            warnings=[],
        ))

    save_als_from_tree(tree, str(als_path))
    return reports