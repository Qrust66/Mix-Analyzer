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
