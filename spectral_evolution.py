#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spectral Evolution Engine — v2.5.2

Generates a transient CQT matrix from audio and extracts compact features
(zone energy, spectral descriptors, trajectories, transients) that downstream
modules consume for dynamic EQ automation.

The CQT matrix lives in RAM only; after feature extraction it is discarded.
"""

from __future__ import annotations

import numpy as np
import librosa
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CQT_N_BINS = 256
CQT_BINS_PER_OCTAVE = 24
TARGET_FRAMES_PER_SEC = 6
FMIN = 20.0  # Hz – lowest CQT bin

# Perceptual zones (v2.5 spec §4.3) — intentionally overlapping
ZONE_RANGES: Dict[str, Tuple[float, float]] = {
    'sub':       (20, 80),
    'low':       (80, 250),
    'mud':       (200, 500),
    'body':      (250, 800),
    'low_mid':   (500, 2000),
    'mid':       (1000, 4000),
    'presence':  (2000, 5000),
    'sibilance': (5000, 10000),
    'air':       (10000, 20000),
}

ZONE_LABELS: Dict[str, str] = {
    'sub':       'Sub (20–80 Hz)',
    'low':       'Low (80–250 Hz)',
    'mud':       'Mud (200–500 Hz)',
    'body':      'Body (250–800 Hz)',
    'low_mid':   'Low-Mid (500–2 kHz)',
    'mid':       'Mid (1–4 kHz)',
    'presence':  'Presence (2–5 kHz)',
    'sibilance': 'Sibilance (5–10 kHz)',
    'air':       'Air (10–20 kHz)',
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SpectralMatrix:
    """Transient CQT matrix — discarded after feature extraction."""
    cqt_db: np.ndarray          # shape (n_bins, n_frames), dBFS
    freqs: np.ndarray           # shape (n_bins,), Hz per bin
    times: np.ndarray           # shape (n_frames,), seconds
    sr: int
    hop_length: int

    @property
    def n_bins(self) -> int:
        return self.cqt_db.shape[0]

    @property
    def n_frames(self) -> int:
        return self.cqt_db.shape[1]

    @property
    def duration(self) -> float:
        return float(self.times[-1]) if len(self.times) > 0 else 0.0


@dataclass
class ZoneEnergy:
    """RMS energy per perceptual zone over time (dB)."""
    times: np.ndarray                          # shape (n_frames,)
    zones: Dict[str, np.ndarray] = field(default_factory=dict)  # zone_name -> (n_frames,)


@dataclass
class SpectralDescriptors:
    """Per-frame spectral descriptor curves."""
    times: np.ndarray
    centroid: np.ndarray       # Hz
    spread: np.ndarray         # Hz
    flatness: np.ndarray       # 0..1
    low_rolloff: np.ndarray    # Hz — freq where cumulative energy from bottom reaches threshold
    high_rolloff: np.ndarray   # Hz — freq where cumulative energy from top reaches threshold


@dataclass
class PeakTrajectory:
    """A single tracked spectral peak across frames."""
    points: List[Tuple[int, float, float]]  # [(frame_idx, freq_hz, amplitude_db), ...]

    @property
    def mean_freq(self) -> float:
        if not self.points:
            return 0.0
        return float(np.mean([p[1] for p in self.points]))

    @property
    def mean_amplitude(self) -> float:
        if not self.points:
            return -120.0
        return float(np.mean([p[2] for p in self.points]))

    @property
    def duration_frames(self) -> int:
        return len(self.points)


@dataclass
class TransientEvent:
    """A detected transient event."""
    frame_idx: int
    time_sec: float
    dominant_zone: str
    magnitude_db: float


@dataclass
class TrackFeatures:
    """All v2.5 features for a single track."""
    zone_energy: ZoneEnergy
    descriptors: SpectralDescriptors
    peak_trajectories: Optional[List[PeakTrajectory]] = None
    valley_trajectories: Optional[List[PeakTrajectory]] = None
    crest_by_zone: Optional[Dict[str, np.ndarray]] = None
    delta_spectrum: Optional[np.ndarray] = None
    transient_events: Optional[List[TransientEvent]] = None


# ---------------------------------------------------------------------------
# Matrix generation
# ---------------------------------------------------------------------------

def _safe_n_bins(sr: int) -> int:
    """Compute max CQT bins that fit within Nyquist for the given sample rate."""
    nyquist = sr / 2.0
    max_octaves = np.log2(nyquist / FMIN) - 0.1  # small margin for filter rolloff
    max_bins = int(np.floor(max_octaves * CQT_BINS_PER_OCTAVE))
    return min(CQT_N_BINS, max_bins)


def generate_matrix(mono: np.ndarray, sr: int) -> SpectralMatrix:
    """Generate a CQT spectral matrix from mono audio.

    Args:
        mono: 1-D mono audio signal.
        sr: Sample rate in Hz.

    Returns:
        SpectralMatrix with dBFS amplitudes, frequency axis, and time axis.
    """
    hop_length = _compute_hop_length(sr)
    n_bins = _safe_n_bins(sr)

    cqt_complex = librosa.cqt(
        y=mono,
        sr=sr,
        hop_length=hop_length,
        fmin=FMIN,
        n_bins=n_bins,
        bins_per_octave=CQT_BINS_PER_OCTAVE,
    )

    cqt_mag = np.abs(cqt_complex)
    cqt_db = librosa.amplitude_to_db(cqt_mag, ref=1.0)

    freqs = librosa.cqt_frequencies(
        n_bins=n_bins,
        fmin=FMIN,
        bins_per_octave=CQT_BINS_PER_OCTAVE,
    )

    n_frames = cqt_db.shape[1]
    times = librosa.frames_to_time(
        np.arange(n_frames), sr=sr, hop_length=hop_length,
    )

    return SpectralMatrix(
        cqt_db=cqt_db,
        freqs=freqs,
        times=times,
        sr=sr,
        hop_length=hop_length,
    )


def _compute_hop_length(sr: int) -> int:
    """Compute hop_length targeting ~6 frames/sec."""
    target = sr / TARGET_FRAMES_PER_SEC
    hop = int(round(target))
    hop = max(hop, 512)
    return hop


# ---------------------------------------------------------------------------
# Feature extraction — Zone Energy (Phase 1)
# ---------------------------------------------------------------------------

def extract_zone_energy(matrix: SpectralMatrix) -> ZoneEnergy:
    """Extract per-zone RMS energy curves from the CQT matrix.

    Args:
        matrix: SpectralMatrix from generate_matrix().

    Returns:
        ZoneEnergy with one dB curve per perceptual zone.
    """
    freqs = matrix.freqs
    cqt_linear = librosa.db_to_amplitude(matrix.cqt_db)

    zones: Dict[str, np.ndarray] = {}
    for zone_name, (f_lo, f_hi) in ZONE_RANGES.items():
        mask = (freqs >= f_lo) & (freqs < f_hi)
        if np.any(mask):
            zone_mag = cqt_linear[mask, :]
            rms = np.sqrt(np.mean(zone_mag ** 2, axis=0))
            zone_db = librosa.amplitude_to_db(rms, ref=1.0)
            zones[zone_name] = np.round(zone_db, 1)
        else:
            zones[zone_name] = np.full(matrix.n_frames, -120.0)

    return ZoneEnergy(times=matrix.times, zones=zones)


# ---------------------------------------------------------------------------
# Feature extraction — Spectral Descriptors (Phase 1)
# ---------------------------------------------------------------------------

def extract_spectral_descriptors(matrix: SpectralMatrix,
                                  rolloff_threshold_db: float = -40.0,
                                  ) -> SpectralDescriptors:
    """Extract per-frame spectral descriptor curves from the CQT matrix.

    Args:
        matrix: SpectralMatrix from generate_matrix().
        rolloff_threshold_db: Threshold relative to frame max for rolloff calculation.

    Returns:
        SpectralDescriptors with centroid, spread, flatness, and rolloff curves.
    """
    freqs = matrix.freqs
    cqt_linear = librosa.db_to_amplitude(matrix.cqt_db)
    n_frames = matrix.n_frames

    centroid = np.zeros(n_frames)
    spread = np.zeros(n_frames)
    flatness = np.zeros(n_frames)
    low_rolloff = np.zeros(n_frames)
    high_rolloff = np.zeros(n_frames)

    for t in range(n_frames):
        mag = cqt_linear[:, t]
        total = np.sum(mag) + 1e-12

        # Centroid
        c = np.sum(freqs * mag) / total
        centroid[t] = c

        # Spread (std dev of frequency distribution)
        spread[t] = np.sqrt(np.sum(((freqs - c) ** 2) * mag) / total)

        # Flatness: geometric mean / arithmetic mean
        log_mag = np.log(mag + 1e-12)
        geo_mean = np.exp(np.mean(log_mag))
        arith_mean = np.mean(mag)
        flatness[t] = geo_mean / (arith_mean + 1e-12)

        # Low rolloff — cumulative energy from bottom
        energy = mag ** 2
        cumulative = np.cumsum(energy)
        max_energy = librosa.amplitude_to_db(np.array([np.max(mag)]), ref=1.0)[0]
        threshold_linear = librosa.db_to_amplitude(
            np.array([max_energy + rolloff_threshold_db])
        )[0]
        threshold_energy = threshold_linear ** 2
        above = np.where(cumulative >= threshold_energy)[0]
        low_rolloff[t] = freqs[above[0]] if len(above) > 0 else freqs[0]

        # High rolloff — cumulative energy from top
        cumulative_rev = np.cumsum(energy[::-1])
        above_rev = np.where(cumulative_rev >= threshold_energy)[0]
        if len(above_rev) > 0:
            high_rolloff[t] = freqs[len(freqs) - 1 - above_rev[0]]
        else:
            high_rolloff[t] = freqs[-1]

    return SpectralDescriptors(
        times=matrix.times,
        centroid=np.round(centroid, 1),
        spread=np.round(spread, 1),
        flatness=np.round(flatness, 4),
        low_rolloff=np.round(low_rolloff, 1),
        high_rolloff=np.round(high_rolloff, 1),
    )


# ---------------------------------------------------------------------------
# Feature extraction — Trajectories (Phase 2)
# ---------------------------------------------------------------------------

def extract_peak_trajectories(matrix: SpectralMatrix,
                               n_peaks: int = 6,
                               min_prominence_db: float = 6.0,
                               max_semitone_drift: float = 1.0,
                               min_duration_frames: int = 10,
                               ) -> List[PeakTrajectory]:
    """Track the N most salient spectral peaks across frames.

    Args:
        matrix: SpectralMatrix from generate_matrix().
        n_peaks: Max number of trajectories to return.
        min_prominence_db: Minimum peak prominence in dB.
        max_semitone_drift: Max frequency migration between adjacent frames (semitones).
        min_duration_frames: Minimum trajectory length to keep.

    Returns:
        List of PeakTrajectory sorted by mean amplitude (loudest first).
    """
    from scipy.signal import find_peaks

    freqs = matrix.freqs
    log_freqs = np.log2(freqs + 1e-12)
    semitone_threshold = max_semitone_drift / 12.0

    # Detect peaks per frame
    per_frame_peaks: List[List[Tuple[int, float, float]]] = []
    for t in range(matrix.n_frames):
        spectrum = matrix.cqt_db[:, t]
        peak_indices, props = find_peaks(
            spectrum,
            prominence=min_prominence_db,
            distance=3,
        )
        frame_peaks = [
            (int(idx), float(freqs[idx]), float(spectrum[idx]))
            for idx in peak_indices
        ]
        frame_peaks.sort(key=lambda p: p[2], reverse=True)
        per_frame_peaks.append(frame_peaks if n_peaks is None else frame_peaks[:n_peaks * 3])

    # Link peaks across frames
    active_trajectories: List[List[Tuple[int, float, float]]] = []
    completed: List[List[Tuple[int, float, float]]] = []

    for t, frame_peaks in enumerate(per_frame_peaks):
        used_peaks = set()
        new_active = []

        for traj in active_trajectories:
            last_bin_idx, last_freq, last_amp = traj[-1]
            last_log_freq = np.log2(last_freq + 1e-12)
            best_match = None
            best_dist = float('inf')

            for pi, (bin_idx, freq, amp) in enumerate(frame_peaks):
                if pi in used_peaks:
                    continue
                dist = abs(np.log2(freq + 1e-12) - last_log_freq)
                if dist < semitone_threshold and dist < best_dist:
                    best_match = pi
                    best_dist = dist

            if best_match is not None:
                used_peaks.add(best_match)
                bm = frame_peaks[best_match]
                traj.append((bm[0], bm[1], bm[2]))
                # Store with frame index instead of bin index
                traj[-1] = (t, bm[1], bm[2])
                new_active.append(traj)
            else:
                completed.append(traj)

        # Start new trajectories for unmatched peaks
        for pi, (bin_idx, freq, amp) in enumerate(frame_peaks):
            if pi not in used_peaks:
                new_active.append([(t, freq, amp)])

        active_trajectories = new_active

    completed.extend(active_trajectories)

    # Filter by duration and sort by mean amplitude
    trajectories = [
        PeakTrajectory(points=traj)
        for traj in completed
        if len(traj) >= min_duration_frames
    ]
    trajectories.sort(key=lambda t: t.mean_amplitude, reverse=True)
    return trajectories if n_peaks is None else trajectories[:n_peaks]


def extract_valley_trajectories(matrix: SpectralMatrix,
                                 n_valleys: int = 6,
                                 min_prominence_db: float = 6.0,
                                 max_semitone_drift: float = 1.0,
                                 min_duration_frames: int = 10,
                                 ) -> List[PeakTrajectory]:
    """Track the N deepest spectral valleys across frames.

    Same algorithm as peak trajectories but on inverted spectrum.

    Args:
        matrix: SpectralMatrix from generate_matrix().
        n_valleys: Max number of valley trajectories to return.
        min_prominence_db: Minimum valley depth in dB.
        max_semitone_drift: Max frequency migration (semitones).
        min_duration_frames: Minimum trajectory length.

    Returns:
        List of PeakTrajectory representing valleys (sorted by depth).
    """
    inverted = SpectralMatrix(
        cqt_db=-matrix.cqt_db,
        freqs=matrix.freqs,
        times=matrix.times,
        sr=matrix.sr,
        hop_length=matrix.hop_length,
    )
    valleys = extract_peak_trajectories(
        inverted,
        n_peaks=n_valleys,
        min_prominence_db=min_prominence_db,
        max_semitone_drift=max_semitone_drift,
        min_duration_frames=min_duration_frames,
    )
    # Restore original amplitudes
    for v in valleys:
        v.points = [(f, freq, -amp) for f, freq, amp in v.points]
    return valleys


# ---------------------------------------------------------------------------
# Feature extraction — Dynamics (Phase 2)
# ---------------------------------------------------------------------------

def extract_crest_by_zone(matrix: SpectralMatrix) -> Dict[str, np.ndarray]:
    """Compute crest factor (peak/RMS ratio in dB) per zone over time.

    Args:
        matrix: SpectralMatrix from generate_matrix().

    Returns:
        Dict mapping zone name to array of crest factor values per frame.
    """
    freqs = matrix.freqs
    cqt_linear = librosa.db_to_amplitude(matrix.cqt_db)
    result: Dict[str, np.ndarray] = {}

    for zone_name, (f_lo, f_hi) in ZONE_RANGES.items():
        mask = (freqs >= f_lo) & (freqs < f_hi)
        if not np.any(mask):
            result[zone_name] = np.zeros(matrix.n_frames)
            continue
        zone_mag = cqt_linear[mask, :]
        peak_per_frame = np.max(zone_mag, axis=0)
        rms_per_frame = np.sqrt(np.mean(zone_mag ** 2, axis=0))
        with np.errstate(divide='ignore', invalid='ignore'):
            crest_db = 20 * np.log10(
                (peak_per_frame + 1e-12) / (rms_per_frame + 1e-12)
            )
        result[zone_name] = np.round(crest_db, 1)

    return result


def extract_delta_spectrum(matrix: SpectralMatrix) -> np.ndarray:
    """Compute frame-to-frame spectral change magnitude.

    Args:
        matrix: SpectralMatrix from generate_matrix().

    Returns:
        1-D array of length n_frames with delta magnitude per frame (dB).
    """
    if matrix.n_frames < 2:
        return np.zeros(max(matrix.n_frames, 1))

    diff = np.diff(matrix.cqt_db, axis=1)
    delta = np.sqrt(np.mean(diff ** 2, axis=0))
    delta = np.concatenate([[0.0], delta])
    return np.round(delta, 2)


def extract_transients(matrix: SpectralMatrix,
                       delta_spectrum: np.ndarray,
                       threshold_factor: float = 2.5,
                       ) -> List[TransientEvent]:
    """Detect transient events from delta spectrum using local peak detection.

    Uses scipy peak detection on the delta curve rather than a flat threshold,
    which handles both sparse and dense transient content correctly.

    Args:
        matrix: SpectralMatrix from generate_matrix().
        delta_spectrum: Output of extract_delta_spectrum().
        threshold_factor: Prominence factor — peaks must have prominence >=
                          mean(delta) / threshold_factor.

    Returns:
        List of TransientEvent sorted by time.
    """
    from scipy.signal import find_peaks

    freqs = matrix.freqs
    positive = delta_spectrum[delta_spectrum > 0]
    if len(positive) == 0:
        return []

    min_prominence = np.mean(positive) / threshold_factor
    peak_indices, props = find_peaks(
        delta_spectrum,
        prominence=min_prominence,
        distance=2,
    )

    events: List[TransientEvent] = []
    for t in peak_indices:
        diff_col = np.abs(np.diff(matrix.cqt_db[:, max(0, t - 1):t + 1], axis=1)).flatten() \
            if t > 0 else np.abs(matrix.cqt_db[:, t])

        dominant_zone = 'mid'
        max_energy = -np.inf
        for zone_name, (f_lo, f_hi) in ZONE_RANGES.items():
            mask = (freqs >= f_lo) & (freqs < f_hi)
            if np.any(mask) and len(diff_col) == len(freqs):
                zone_energy = np.sum(diff_col[mask])
                if zone_energy > max_energy:
                    max_energy = zone_energy
                    dominant_zone = zone_name

        events.append(TransientEvent(
            frame_idx=int(t),
            time_sec=round(float(matrix.times[t]), 3),
            dominant_zone=dominant_zone,
            magnitude_db=round(float(delta_spectrum[t]), 1),
        ))

    return events


# ---------------------------------------------------------------------------
# Rolloff curves (Phase 2)
# ---------------------------------------------------------------------------

def extract_rolloff_curves(matrix: SpectralMatrix,
                           threshold_db: float = -40.0,
                           ) -> Tuple[np.ndarray, np.ndarray]:
    """Extract low and high rolloff frequency curves.

    Args:
        matrix: SpectralMatrix from generate_matrix().
        threshold_db: Energy threshold relative to frame max.

    Returns:
        Tuple of (low_rolloff, high_rolloff) arrays in Hz, shape (n_frames,).
    """
    desc = extract_spectral_descriptors(matrix, rolloff_threshold_db=threshold_db)
    return desc.low_rolloff, desc.high_rolloff


# ---------------------------------------------------------------------------
# Full extraction pipeline
# ---------------------------------------------------------------------------

def extract_all_features(mono: np.ndarray, sr: int) -> TrackFeatures:
    """Run complete v2.5 feature extraction pipeline for one track.

    Generates CQT matrix, extracts all features, then discards the matrix.

    Args:
        mono: 1-D mono audio signal (must be at least 0.1 s long).
        sr: Sample rate in Hz.

    Returns:
        TrackFeatures with all extracted features.

    Raises:
        ValueError: If the signal is too short for CQT analysis.
    """
    min_samples = max(sr // 10, 4096)
    if len(mono) < min_samples:
        raise ValueError(
            f"Audio too short for CQT analysis: {len(mono)} samples "
            f"(need >= {min_samples} at sr={sr})"
        )

    mono = np.asarray(mono, dtype=np.float32)
    matrix = generate_matrix(mono, sr)

    zone_energy = extract_zone_energy(matrix)
    descriptors = extract_spectral_descriptors(matrix)
    peak_traj = extract_peak_trajectories(matrix, n_peaks=None, min_prominence_db=1.0, min_duration_frames=1)
    valley_traj = extract_valley_trajectories(matrix, n_valleys=None, min_prominence_db=1.0, min_duration_frames=1)
    crest = extract_crest_by_zone(matrix)
    delta = extract_delta_spectrum(matrix)
    transients = extract_transients(matrix, delta)

    # Matrix is now discarded (goes out of scope)
    return TrackFeatures(
        zone_energy=zone_energy,
        descriptors=descriptors,
        peak_trajectories=peak_traj,
        valley_trajectories=valley_traj,
        crest_by_zone=crest,
        delta_spectrum=delta,
        transient_events=transients,
    )
