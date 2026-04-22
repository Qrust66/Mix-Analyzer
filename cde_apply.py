#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cde_apply.py — v2.7.0 — Feature 1 phase F1a (clustering + data prep).

Bridges Feature 3.6 (CDE) and the EQ8 automation engine: consumes
``CorrectionDiagnostic`` instances, groups them by target track,
clusters them by frequency, and matches them to peak trajectories
read from the Mix Analyzer Excel report.

F1a ships the **read-only** side of the bridge:

    - Dataclasses ``FreqCluster`` and ``CdeApplicationReport``
    - ``_group_diagnostics_by_target``     — filters sidechain / empty
                                             recipes, groups by target_track
    - ``_cluster_diagnostics_by_frequency`` — single-link clustering with
                                             centroid-distance matching,
                                             default tolerance 2 semitones
    - ``_match_peak_trajectories_to_cluster`` — filter trajectories whose
                                             ``mean_freq`` sits inside the
                                             cluster's tolerance band
    - ``load_peak_trajectories_from_excel`` — parse the
                                             ``_track_peak_trajectories``
                                             sheet

No EQ8 insertion, no automation write, no ``.als`` mutation. Those
ship in F1b (section-locked writer) and F1c (peak-following mode).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from cde_engine import CorrectionDiagnostic
from spectral_evolution import PeakTrajectory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Vocabulary — approach strings the writer can handle vs skip
# ---------------------------------------------------------------------------

# F1 scope: EQ8-cut-style corrections. Every other approach rides a
# different device and is therefore out of scope for this module.
CUT_APPROACHES: Tuple[str, ...] = (
    "static_dip", "musical_dip", "reciprocal_cuts",
)
SIDECHAIN_APPROACH: str = "sidechain"

# Clustering defaults. 2 semitones = ×2^(2/12) ≈ ×1.122 — narrow enough
# to keep distinct tonal centres apart (the user's call after Phase A).
DEFAULT_FREQ_CLUSTER_TOLERANCE_SEMITONES = 2.0

# Peak-trajectory matching — by default shares the same tolerance as
# the cluster itself. Caller can override.
DEFAULT_PEAK_MATCH_TOLERANCE_SEMITONES = 2.0

# EQ8 conventions. Bands 0 and 7 are reserved by
# ``eq8_automation._find_available_band`` for HPF/LPF.
MAX_CDE_BANDS = 6


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FreqCluster:
    """A bundle of diagnostics that should ride a single EQ8 band.

    Produced by :func:`_cluster_diagnostics_by_frequency` — each cluster's
    member diagnostics share a central frequency within the clustering
    tolerance and will share one band in F1b/F1c.

    Attributes:
        centroid_hz:  median of member frequencies (in Hz).
        diagnostics:  the source ``CorrectionDiagnostic`` list.
        severest_gain_db:  the most-negative ``gain_db`` across members —
            used as the cut depth for the produced band (Rule 3 already
            capped it at CDE-matrix time).
        median_q:  the median ``q`` across members — used as the band Q.
        applies_to_sections: union of every member's
            ``applies_to_sections`` list, deduplicated and sorted.
    """
    centroid_hz: float
    diagnostics: List[CorrectionDiagnostic]
    severest_gain_db: float
    median_q: float
    applies_to_sections: List[str]

    @property
    def member_ids(self) -> List[str]:
        return [d.diagnostic_id for d in self.diagnostics]


@dataclass
class CdeApplicationReport:
    """Summary of one CDE batch application run.

    The writer (F1b/c) populates the fields as it goes. ``skipped`` is
    a list of ``(diagnostic_id, reason)`` pairs so the caller can show
    the user WHY something was not applied without reverse-engineering.
    """
    applied: List[str] = field(default_factory=list)
    skipped: List[Tuple[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # {track_name: device_user_name} — shows which devices were inserted.
    devices_created: Dict[str, str] = field(default_factory=dict)
    envelopes_written: int = 0
    backup_path: Optional[Path] = None

    def sidechain_count(self) -> int:
        """How many diagnostics were skipped because they needed
        Kickstart 2 — reported separately so the user sees what
        Feature 1.5 will need to cover."""
        return sum(
            1 for (_, reason) in self.skipped
            if "Kickstart 2" in reason or "sidechain" in reason.lower()
        )


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def _group_diagnostics_by_target(
    diagnostics: List[CorrectionDiagnostic],
    report: Optional[CdeApplicationReport] = None,
) -> Dict[str, List[CorrectionDiagnostic]]:
    """Filter cut-approach diagnostics and group them by
    ``primary_correction.target_track``.

    Skipped diagnostics (with reasons appended to ``report.skipped`` when
    ``report`` is provided):

        - ``primary_correction is None``
          (R2 sub-integrity skip, all-Hero accumulation awareness)
        - ``approach == "sidechain"``
          (Kickstart 2 device; Feature 1.5 scope)
        - Any approach outside :data:`CUT_APPROACHES`
          (future detectors; explicit opt-in required)

    Args:
        diagnostics: Raw CDE diagnostics list (e.g. deserialised from
            ``<project>_diagnostics.json``).
        report: Optional report to collect skip reasons into. When
            ``None``, skipped diagnostics are silently dropped.

    Returns:
        ``{target_track: [diagnostic, diagnostic, ...]}`` — track names
        are taken verbatim from ``primary_correction.target_track`` so
        they match the raw WAV filename the CDE stored.
    """
    grouped: Dict[str, List[CorrectionDiagnostic]] = {}
    for d in diagnostics:
        pc = d.primary_correction
        if pc is None:
            if report is not None:
                report.skipped.append((
                    d.diagnostic_id, "primary_correction is None",
                ))
            continue
        if pc.approach == SIDECHAIN_APPROACH:
            if report is not None:
                report.skipped.append((
                    d.diagnostic_id,
                    "requires Kickstart 2 — scope Feature 1.5",
                ))
            continue
        if pc.approach not in CUT_APPROACHES:
            if report is not None:
                report.skipped.append((
                    d.diagnostic_id,
                    f"unsupported approach {pc.approach!r}",
                ))
            continue
        grouped.setdefault(pc.target_track, []).append(d)
    return grouped


# ---------------------------------------------------------------------------
# Frequency clustering
# ---------------------------------------------------------------------------

def _semitone_ratio(tolerance_semitones: float) -> float:
    """Convert a tolerance in semitones to a frequency ratio factor."""
    return 2.0 ** (float(tolerance_semitones) / 12.0)


def _freq_distance_semitones(f1: float, f2: float) -> float:
    """Return ``|log2(f2/f1)| * 12`` — the semitone distance between
    two positive frequencies."""
    if f1 <= 0 or f2 <= 0:
        return float("inf")
    return abs(float(np.log2(f2 / f1))) * 12.0


# Floating-point slack for inclusive boundary comparisons — ``247 Hz``
# and ``247 * 2^(2/12) Hz`` are musically exactly 2 semitones apart but
# the round-trip through ``np.log2`` drifts by ~4e-16.
_CLUSTER_EPSILON_SEMITONES = 1e-9


def _cluster_diagnostics_by_frequency(
    diagnostics: List[CorrectionDiagnostic],
    tolerance_semitones: float = DEFAULT_FREQ_CLUSTER_TOLERANCE_SEMITONES,
) -> List[FreqCluster]:
    """Centroid-link cluster the diagnostics' frequencies.

    Algorithm:

        1. Sort members by their ``measurement.frequency_hz``.
        2. Walk the sorted list, appending each freq to the current
           cluster when its distance to the cluster's **median** is
           within ``tolerance_semitones``; otherwise start a new cluster.
        3. Build one :class:`FreqCluster` per resulting group with:
            - ``centroid_hz``   = median of member frequencies
            - ``severest_gain_db`` = most negative ``gain_db`` among members
            - ``median_q``      = median of member Q values
            - ``applies_to_sections`` = sorted union of each member's
              ``applies_to_sections``

    Members with missing / non-positive frequencies are dropped
    silently — a frequency is mandatory for a cut recipe, so a
    diagnostic without one cannot ride an EQ8 band.

    Args:
        diagnostics: a group of diagnostics on the **same target track**
            (call :func:`_group_diagnostics_by_target` first).
        tolerance_semitones: clustering tolerance (default 2.0).

    Returns:
        Clusters sorted by ``centroid_hz`` ascending.
    """
    if not diagnostics:
        return []

    # Only keep diagnostics with a usable frequency.
    freq_items: List[Tuple[float, CorrectionDiagnostic]] = []
    for d in diagnostics:
        meas = d.measurement
        f = float(meas.frequency_hz) if (meas and meas.frequency_hz) else None
        if f is None or f <= 0:
            continue
        freq_items.append((f, d))
    freq_items.sort(key=lambda x: x[0])

    if not freq_items:
        return []

    # Single-link walk using the running median as the comparison anchor.
    clusters_raw: List[List[Tuple[float, CorrectionDiagnostic]]] = []
    for f, d in freq_items:
        if not clusters_raw:
            clusters_raw.append([(f, d)])
            continue
        current_freqs = [p[0] for p in clusters_raw[-1]]
        centroid = float(np.median(current_freqs))
        if (_freq_distance_semitones(centroid, f)
                <= tolerance_semitones + _CLUSTER_EPSILON_SEMITONES):
            clusters_raw[-1].append((f, d))
        else:
            clusters_raw.append([(f, d)])

    # Materialise the cluster dataclasses.
    out: List[FreqCluster] = []
    for group in clusters_raw:
        freqs = [p[0] for p in group]
        diags = [p[1] for p in group]
        gains = [
            float(d.primary_correction.parameters.get("gain_db", 0.0))
            for d in diags
            if d.primary_correction is not None
        ]
        qs = [
            float(d.primary_correction.parameters.get("q", 1.0))
            for d in diags
            if d.primary_correction is not None
        ]
        sections_set: set = set()
        for d in diags:
            if d.primary_correction is None:
                continue
            sections_set.update(d.primary_correction.applies_to_sections)

        out.append(FreqCluster(
            centroid_hz=float(np.median(freqs)),
            diagnostics=diags,
            severest_gain_db=float(min(gains)) if gains else 0.0,
            median_q=float(np.median(qs)) if qs else 1.0,
            applies_to_sections=sorted(sections_set),
        ))
    return out


# ---------------------------------------------------------------------------
# Peak-trajectory matching
# ---------------------------------------------------------------------------

def _match_peak_trajectories_to_cluster(
    trajectories: List[PeakTrajectory],
    cluster: FreqCluster,
    tolerance_semitones: float = DEFAULT_PEAK_MATCH_TOLERANCE_SEMITONES,
) -> List[PeakTrajectory]:
    """Return the subset of trajectories whose ``mean_freq`` falls
    within ``tolerance_semitones`` of the cluster's centroid.

    Used in F1c (peak-following mode) to decide which trajectories to
    drive the Freq + Gain envelopes with. When no trajectory matches,
    the caller falls back to the section-locked mode (F1b).
    """
    matched: List[PeakTrajectory] = []
    for traj in trajectories or []:
        mean_freq = float(traj.mean_freq)
        if mean_freq <= 0:
            continue
        if (_freq_distance_semitones(cluster.centroid_hz, mean_freq)
                <= tolerance_semitones + _CLUSTER_EPSILON_SEMITONES):
            matched.append(traj)
    return matched


# ---------------------------------------------------------------------------
# Excel reader — _track_peak_trajectories sheet
# ---------------------------------------------------------------------------

_PEAK_SHEET_NAME = "_track_peak_trajectories"
_PEAK_SHEET_HEADER = ("Track", "Traj#", "Frame", "Time (s)",
                      "Freq (Hz)", "Amp (dB)")


def load_peak_trajectories_from_excel(
    xlsx_path,
    track_name_filter: Optional[Callable[[str], str]] = None,
) -> Dict[str, List[PeakTrajectory]]:
    """Parse the ``_track_peak_trajectories`` sheet of a Mix Analyzer
    Excel report.

    The sheet shape (verified on the Acid Drops production report):

        Track | Traj# | Frame | Time (s) | Freq (Hz) | Amp (dB)

    Rows are grouped by ``(Track, Traj#)`` and each group materialises
    as one :class:`spectral_evolution.PeakTrajectory` with its
    ``points = [(frame_idx, freq_hz, amp_db), ...]`` list. Points are
    kept in the sheet's row order (which is already frame-ascending in
    the production reports).

    Args:
        xlsx_path: Path to the Mix Analyzer ``.xlsx`` report.
        track_name_filter: Optional callable applied to each row's
            Track name — useful to normalise ``"Acid_Drops [H_R]
            Kick 1.wav"`` into ``"[H/R] Kick 1"`` so names match the
            Ableton EffectiveName used by ``find_track_by_name``. When
            ``None``, names are kept verbatim.

    Returns:
        ``{track_name: [PeakTrajectory, PeakTrajectory, ...]}``.
        Trajectories preserve the sheet's Traj# ordering implicitly
        (Python dict insertion order).

    Raises:
        FileNotFoundError: if ``xlsx_path`` does not exist.
        ValueError: if the expected sheet is absent from the workbook.
    """
    from openpyxl import load_workbook

    path = Path(xlsx_path)
    if not path.exists():
        raise FileNotFoundError(f"Report not found: {path}")

    wb = load_workbook(str(path), read_only=True, data_only=True)
    if _PEAK_SHEET_NAME not in wb.sheetnames:
        raise ValueError(
            f"Sheet {_PEAK_SHEET_NAME!r} not found in {path.name}. "
            f"Available: {wb.sheetnames}"
        )
    ws = wb[_PEAK_SHEET_NAME]

    grouped: Dict[Tuple[str, int], List[Tuple[int, float, float]]] = {}
    track_order: List[str] = []
    traj_order_seen: set = set()

    rows = ws.iter_rows(values_only=True)
    header = next(rows, None)
    if header is None or tuple(header[: len(_PEAK_SHEET_HEADER)]) != _PEAK_SHEET_HEADER:
        logger.warning(
            "Unexpected header in %s: %r (expected %r). Parsing anyway.",
            _PEAK_SHEET_NAME, header, _PEAK_SHEET_HEADER,
        )

    for row in rows:
        if not row or row[0] is None or row[1] is None:
            continue
        track_raw = str(row[0])
        traj_num_raw = row[1]
        frame_raw = row[2]
        freq_raw = row[4]
        amp_raw = row[5]
        if freq_raw is None or amp_raw is None:
            continue

        track = (track_name_filter(track_raw) if track_name_filter
                 else track_raw)
        try:
            traj_num = int(traj_num_raw)
            frame_idx = int(frame_raw) if frame_raw is not None else 0
            freq_hz = float(freq_raw)
            amp_db = float(amp_raw)
        except (TypeError, ValueError):
            continue

        key = (track, traj_num)
        if key not in grouped:
            grouped[key] = []
            if track not in traj_order_seen:
                track_order.append(track)
                traj_order_seen.add(track)
        grouped[key].append((frame_idx, freq_hz, amp_db))

    # Build PeakTrajectory per (track, traj_num), respecting first-seen
    # track order + ascending traj_num within each track.
    result: Dict[str, List[PeakTrajectory]] = {t: [] for t in track_order}
    for (track, traj_num) in sorted(grouped.keys(), key=lambda k: (track_order.index(k[0]), k[1])):
        result[track].append(PeakTrajectory(points=grouped[(track, traj_num)]))

    return result
