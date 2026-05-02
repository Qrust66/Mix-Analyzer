#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automation Map — v2.8.0

Extracts gain-affecting automations (volume fader, Utility gain, Speaker mute,
device on/off) from Ableton .als files and computes per-track effective gain
curves.  Used to mask inaudible sections in the v2.5 feature/EQ8 pipeline.
"""

from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from als_utils import parse_als, beats_to_seconds


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AutomationCurve:
    """A single automation parameter extracted from the .als."""
    target_id: int
    param_name: str
    device_name: str
    times_beats: np.ndarray
    values: np.ndarray


@dataclass
class TrackAutomationMap:
    """All gain-affecting automations for one track."""
    track_name: str
    curves: list[AutomationCurve] = field(default_factory=list)
    effective_gain: np.ndarray = field(default_factory=lambda: np.array([]))
    effective_gain_times: np.ndarray = field(default_factory=lambda: np.array([]))
    is_audible: np.ndarray = field(default_factory=lambda: np.array([], dtype=bool))


AUDIBILITY_THRESHOLD = 0.001  # ~-60 dB


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_tempo(tree: ET.ElementTree) -> float:
    """Read project tempo from a parsed ALS tree."""
    tempo_elem = tree.getroot().find(".//Tempo/Manual")
    if tempo_elem is not None:
        return float(tempo_elem.get("Value", "120"))
    return 120.0


def _get_song_length_beats(tree: ET.ElementTree) -> float:
    """Estimate song length in beats from the furthest automation event."""
    max_time = 0.0
    for ev in tree.getroot().iter("FloatEvent"):
        t = float(ev.get("Time", "0"))
        if t > max_time:
            max_time = t
    # Fall back to a reasonable minimum
    return max(max_time, 16.0)


def _extract_envelope_curve(
    track_element: ET.Element,
    target_id: str,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Extract automation events for a given AutomationTarget Id.

    Returns (times_beats, values) arrays, or None if no envelope found.
    """
    for envelope in track_element.iter("AutomationEnvelope"):
        pointee = envelope.find("EnvelopeTarget/PointeeId")
        if pointee is None or pointee.get("Value") != str(target_id):
            continue
        events_node = envelope.find("Automation/Events")
        if events_node is None:
            continue
        times = []
        values = []
        for ev in events_node:
            if ev.tag != "FloatEvent":
                continue
            t = float(ev.get("Time", "0"))
            v = float(ev.get("Value", "0"))
            times.append(t)
            values.append(v)
        if not times:
            return None
        return np.array(times), np.array(values)
    return None


def _find_automation_target_id(param_element: ET.Element) -> str | None:
    """Return the AutomationTarget Id for a parameter element, or None."""
    target = param_element.find("AutomationTarget")
    if target is not None:
        return target.get("Id")
    return None


def _get_manual_value(param_element: ET.Element) -> float | None:
    """Read the Manual value of a parameter element."""
    manual = param_element.find("Manual")
    if manual is not None:
        raw = manual.get("Value", "0")
        if raw.lower() == "true":
            return 1.0
        if raw.lower() == "false":
            return 0.0
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def _interpolate_at(times_beats: np.ndarray, values: np.ndarray,
                    query_beats: np.ndarray) -> np.ndarray:
    """Step-interpolate automation values at query times.

    Ableton automations use step (hold) interpolation by default for
    on/off parameters, and linear for continuous. We use step (forward-fill)
    for simplicity and correctness with mute/on-off curves.
    """
    result = np.full(len(query_beats), values[0] if len(values) > 0 else 0.0)
    # Filter out pre-song events for interpolation
    real_mask = times_beats > -1e6
    t_real = times_beats[real_mask]
    v_real = values[real_mask]
    if len(t_real) == 0:
        # Only pre-song events: use the last pre-song value
        return np.full(len(query_beats), values[-1] if len(values) > 0 else 0.0)

    # For each query point, find the last event at or before it
    indices = np.searchsorted(t_real, query_beats, side='right') - 1
    # Points before first real event get the pre-song value
    pre_value = values[0] if len(values) > 0 else 0.0
    for i, idx in enumerate(indices):
        if idx < 0:
            result[i] = pre_value
        else:
            result[i] = v_real[idx]
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_track_automations(
    track_element: ET.Element,
    tempo: float,
    song_length_beats: float = 0.0,
) -> TrackAutomationMap:
    """Extract all gain-affecting automations for a single track.

    Scans:
      a) Volume fader (MixerDevice → Volume)
      b) Utility gain (StereoGain devices → Gain)
      c) Speaker / track activator (MixerDevice → Speaker)

    Computes effective_gain = volume × utility_gains × speaker.

    Args:
        track_element: XML Element of the track.
        tempo: Project tempo in BPM.
        song_length_beats: Estimated song length in beats (for time grid).

    Returns:
        TrackAutomationMap with curves and effective gain.
    """
    name_elem = track_element.find(".//EffectiveName")
    if name_elem is None:
        name_elem = track_element.find(".//UserName")
    track_name = name_elem.get("Value", "Unknown") if name_elem is not None else "Unknown"

    curves: list[AutomationCurve] = []

    # Build a beat-resolution time grid for combining
    if song_length_beats <= 0:
        song_length_beats = 128.0
    n_grid = max(int(song_length_beats), 128)
    grid_beats = np.linspace(0, song_length_beats, n_grid)

    # Start with all-ones for multiplicative combining
    combined_gain = np.ones(n_grid)

    # --- a) Volume fader ---
    volume_gain = _extract_mixer_param(
        track_element, "Volume", "MixerDevice", curves, grid_beats
    )
    if volume_gain is not None:
        combined_gain *= volume_gain

    # --- b) Utility gain (StereoGain devices) ---
    devices_node = track_element.find(".//DeviceChain/DeviceChain/Devices")
    if devices_node is None:
        devices_node = track_element.find(".//DeviceChain/Devices")
    if devices_node is not None:
        util_idx = 0
        for device in devices_node:
            if device.tag != "StereoGain":
                continue
            util_idx += 1
            dev_name = f"Utility{'.' + str(util_idx) if util_idx > 1 else ''}"
            gain_param = device.find("Gain")
            if gain_param is None:
                continue
            util_gain = _extract_param_curve(
                track_element, gain_param, "Utility.Gain", dev_name,
                curves, grid_beats,
            )
            if util_gain is not None:
                combined_gain *= util_gain

    # --- c) Speaker (track mute) ---
    speaker_gain = _extract_mixer_param(
        track_element, "Speaker", "MixerDevice", curves, grid_beats,
        is_boolean=True
    )
    if speaker_gain is not None:
        combined_gain *= speaker_gain

    # Convert grid to seconds
    grid_seconds = grid_beats * (60.0 / tempo) if tempo > 0 else grid_beats

    is_audible = combined_gain >= AUDIBILITY_THRESHOLD

    return TrackAutomationMap(
        track_name=track_name,
        curves=curves,
        effective_gain=combined_gain,
        effective_gain_times=grid_seconds,
        is_audible=is_audible,
    )


def _utility_gain_to_linear(db_value: float) -> float:
    """Convert Utility Gain dB value to linear multiplier."""
    return 10.0 ** (db_value / 20.0)


def _extract_mixer_param(
    track_element: ET.Element,
    param_tag: str,
    device_name: str,
    curves: list[AutomationCurve],
    grid_beats: np.ndarray,
    is_boolean: bool = False,
) -> np.ndarray | None:
    """Extract a MixerDevice parameter (Volume or Speaker).

    Returns the interpolated curve on grid_beats, or None if not found.
    """
    mixer = track_element.find(".//DeviceChain/Mixer")
    if mixer is None:
        mixer = track_element.find(".//MixerDevice")
    if mixer is None:
        return None

    param_elem = mixer.find(param_tag)
    if param_elem is None:
        return None

    return _extract_param_curve(
        track_element, param_elem, param_tag, device_name,
        curves, grid_beats, is_boolean=is_boolean
    )


def _extract_param_curve(
    track_element: ET.Element,
    param_elem: ET.Element,
    param_name: str,
    device_name: str,
    curves: list[AutomationCurve],
    grid_beats: np.ndarray,
    is_boolean: bool = False,
    default_scale=None,
) -> np.ndarray | None:
    """Extract a parameter's automation or static value as an interpolated curve.

    Returns the curve array on grid_beats, or None if the parameter is missing.
    """
    target_id_str = _find_automation_target_id(param_elem)
    manual_val = _get_manual_value(param_elem)

    if manual_val is None:
        manual_val = 1.0 if is_boolean else 0.85

    envelope_data = None
    if target_id_str is not None:
        envelope_data = _extract_envelope_curve(track_element, target_id_str)

    if envelope_data is not None:
        times_beats, values = envelope_data
        if default_scale is not None:
            values = np.array([default_scale(v) for v in values])
        elif is_boolean:
            values = np.where(values >= 0.5, 1.0, 0.0)

        curve = AutomationCurve(
            target_id=int(target_id_str) if target_id_str else 0,
            param_name=param_name,
            device_name=device_name,
            times_beats=times_beats,
            values=values,
        )
        curves.append(curve)
        return _interpolate_at(times_beats, values, grid_beats)
    else:
        # Static value — constant curve
        static_val = manual_val
        if default_scale is not None:
            static_val = default_scale(manual_val)
        elif is_boolean:
            static_val = 1.0 if manual_val >= 0.5 else 0.0

        curve = AutomationCurve(
            target_id=int(target_id_str) if target_id_str else 0,
            param_name=param_name,
            device_name=device_name,
            times_beats=np.array([0.0]),
            values=np.array([static_val]),
        )
        curves.append(curve)
        return np.full(len(grid_beats), static_val)


def extract_all_track_automations(
    als_path: str | Path,
) -> dict[str, TrackAutomationMap]:
    """Parse a .als file and extract automation maps for all tracks.

    Args:
        als_path: Path to the Ableton .als file.

    Returns:
        Dict mapping track_name → TrackAutomationMap.
    """
    tree = parse_als(str(als_path))
    tempo = _extract_tempo(tree)
    song_length = _get_song_length_beats(tree)

    root = tree.getroot()
    live_set = root.find("LiveSet")
    if live_set is None:
        return {}

    tracks_node = live_set.find("Tracks")
    if tracks_node is None:
        return {}

    result: dict[str, TrackAutomationMap] = {}
    for track in tracks_node:
        auto_map = extract_track_automations(track, tempo, song_length)
        result[auto_map.track_name] = auto_map

    return result


def resample_effective_gain(
    automation_map: TrackAutomationMap,
    target_times: np.ndarray,
) -> np.ndarray:
    """Resample effective gain onto an arbitrary time axis.

    Uses step (zero-order hold) interpolation aligned to the automation map's
    time grid.

    Args:
        automation_map: The track's automation map.
        target_times: Target time axis in seconds (e.g. 64 bucket centers).

    Returns:
        Array of effective gain values, same length as target_times.
    """
    if len(automation_map.effective_gain) == 0 or len(automation_map.effective_gain_times) == 0:
        return np.ones(len(target_times))

    src_times = automation_map.effective_gain_times
    src_values = automation_map.effective_gain

    indices = np.searchsorted(src_times, target_times, side='right') - 1
    result = np.ones(len(target_times))
    for i, idx in enumerate(indices):
        if idx < 0:
            result[i] = src_values[0]
        elif idx >= len(src_values):
            result[i] = src_values[-1]
        else:
            result[i] = src_values[idx]
    return result


def resample_audibility(
    automation_map: TrackAutomationMap,
    target_times: np.ndarray,
) -> np.ndarray:
    """Resample audibility mask onto target time axis.

    Returns bool array: True where track is audible.
    """
    gain = resample_effective_gain(automation_map, target_times)
    return gain >= AUDIBILITY_THRESHOLD
