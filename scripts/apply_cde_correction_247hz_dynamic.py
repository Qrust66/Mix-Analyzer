#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_cde_correction_247hz_dynamic.py — section-locked 247 Hz cut
on the ``[A/T] Ambience`` track, written in the production pattern.

The CDE accumulation detector flagged 10 pile-ups at ~247 Hz all
targeting Ambience (B3 fundamental of the song). This script applies
a band 4 Bell cut at 247 Hz with depth -6 dB, active ONLY during the
six flagged sections.

Why the dense pattern (v3):

    The first two attempts used sparse FloatEvents with 0.001-beat
    epsilon pairs around step transitions. That XML structure is
    valid but Ableton's playback engine renders the steps as slow
    ramps — the user reported the gain drifting rather than
    switching. The root cause is that Live's audio engine smooths
    between events over a perceptible window regardless of their
    proximity.

    The "Peak Resonance" EQ8 already on Ambience (written by Mix
    Analyzer's ``write_dynamic_notch``) has 471 events per envelope,
    sampled at ~0.5 s intervals, with continuous frame-by-frame
    values. Ableton handles this flawlessly.

    This v3 mimics that pattern exactly. For each frame in a dense
    time grid (one sample every ``GRID_SPACING_SEC`` seconds, capped
    at 500 via ``thin_breakpoints``) we write the target gain: -6 dB
    when the frame falls inside a cut range, 0 dB outside. Step
    transitions happen in one frame-width (~0.5 s) — imperceptible
    in practice.

Reuses the production writer path:
    ``_write_validated_env(track, band_param, "Gain", bps, next_id)``
    — same function every ``write_dynamic_notch`` / ``write_section_aware_eq``
    calls, which guarantees the same validation, the same idempotent
    removal of any existing envelope on that target, and the same
    ``FloatEvent`` emission via ``write_automation_envelope``.

Usage:
    python scripts/apply_cde_correction_247hz_dynamic.py [als_path]

Idempotence — self-healing:
    Re-running overwrites any previous ``"CDE 247Hz Cut"`` /
    ``"CDE 247Hz Cut (dynamic)"`` device (including every envelope
    targeting its AutomationTargets) before re-inserting the v3 one.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from als_utils import (  # noqa: E402
    _clone_eq8_with_unique_ids,
    backup_als,
    configure_eq8_band,
    find_track_by_name,
    get_eq8_band,
    get_next_id,
    parse_als,
    read_locators,
    save_als_from_tree,
)
from eq8_automation import (  # noqa: E402
    _extract_tempo,
    _feature_to_breakpoints,
    _remove_existing_envelope,
    _write_validated_env,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_ALS_PATH = (
    _REPO_ROOT
    / "Rapports test développement"
    / "Acid_Drops_Sections_TFP.als"
)

TARGET_TRACK_NAME = "[A/T] Ambience"
DYNAMIC_DEVICE_NAME = "CDE 247Hz Cut (dynamic)"
STATIC_DEVICE_NAME = "CDE 247Hz Cut"               # legacy v1 static
PEAK_RESONANCE_NAME = "Peak Resonance"             # insertion anchor

BAND_INDEX = 3                 # 0-indexed — band 4 in Ableton's UI
BAND_MODE_BELL = 3
BAND_FREQ_HZ = 247.0
BAND_Q = 4.0
CUT_GAIN_DB = -6.0
NO_CUT_GAIN_DB = 0.0

# Target sections (CDE accumulation detector output).
TARGET_SECTIONS = ("Build 2", "Drop 1", "Chorus 1", "Fall 2", "Drop 2",
                   "Chorus 2")
MERGE_GAP_BEATS = 4.0  # merge consecutive targets whose gap is <= 4 beats

# Dense-sampling grid. Production Peak Resonance uses ~0.5 s per event;
# we match that density. ``_feature_to_breakpoints`` + ``thin_breakpoints``
# will cap at 500 breakpoints if the grid overshoots.
GRID_SPACING_SEC = 0.5


# ---------------------------------------------------------------------------
# Track-chain helpers
# ---------------------------------------------------------------------------

def _find_device_by_username(track, username):
    for eq8 in track.findall(".//Eq8"):
        un = eq8.find("UserName")
        if un is not None and un.get("Value") == username:
            return eq8
    return None


def _devices_container(track):
    devices = track.find(".//DeviceChain/DeviceChain/Devices")
    if devices is None:
        devices = track.find(".//DeviceChain/Devices")
    if devices is None:
        raise RuntimeError("No Devices container on the target track.")
    return devices


def _remove_device(devices, device):
    for i, child in enumerate(list(devices)):
        if child is device:
            devices.remove(child)
            return i
    raise RuntimeError("Device not found in container.")


def _insert_after(devices, anchor, new_device):
    children = list(devices)
    anchor_idx = children.index(anchor)
    for c in children:
        devices.remove(c)
    for i, c in enumerate(children):
        devices.append(c)
        if i == anchor_idx:
            devices.append(new_device)
    return anchor_idx + 1


# ---------------------------------------------------------------------------
# EQ8 clone — safe fallback when Pluggin Mapping.als is absent
# ---------------------------------------------------------------------------

_NEUTRAL_BAND_FREQS_HZ = (60.0, 150.0, 400.0, 1000.0,
                          2500.0, 6000.0, 12000.0, 18000.0)


def _clone_in_project_eq8(tree, user_name):
    source = tree.getroot().find(".//Eq8")
    if source is None:
        raise RuntimeError("No Eq8 in project to clone from.")
    eq8 = copy.deepcopy(source)
    next_id = get_next_id(tree)
    for elem in eq8.iter():
        raw = elem.get("Id")
        if raw is not None and raw != "0":
            elem.set("Id", str(next_id))
            next_id += 1
    un = eq8.find("UserName")
    if un is not None:
        un.set("Value", user_name)
    # Reset every band to neutral — Bell / 0 dB / Q 0.71 / off.
    for i in range(8):
        band = eq8.find(f"Bands.{i}/ParameterA")
        if band is None:
            continue
        for tag, value in (("Mode/Manual", "3"),
                           ("Freq/Manual", str(_NEUTRAL_BAND_FREQS_HZ[i])),
                           ("Gain/Manual", "0.0"),
                           ("Q/Manual", "0.7071067095"),
                           ("IsOn/Manual", "false")):
            el = band.find(tag)
            if el is not None:
                el.set("Value", value)
    return eq8


def _build_fresh_eq8(tree, user_name):
    try:
        return _clone_eq8_with_unique_ids(tree, user_name=user_name)
    except RuntimeError as e:
        if "template file not found" not in str(e):
            raise
        print(f"NOTE:  Pluggin Mapping.als template absent; "
              f"cloning an in-project EQ8 instead.")
        return _clone_in_project_eq8(tree, user_name)


def _activate_band(band_param):
    ison = band_param.find("IsOn/Manual")
    if ison is None:
        raise RuntimeError("Band has no IsOn/Manual.")
    ison.set("Value", "true")


# ---------------------------------------------------------------------------
# Target range computation — section locators → merged cut ranges
# ---------------------------------------------------------------------------

def _compute_target_ranges_beats(locators):
    """Return ``(start_beats, end_beats, names)`` for each merged target
    section. Merges neighbours whose gap ≤ :data:`MERGE_GAP_BEATS`."""
    sorted_locs = sorted(locators, key=lambda L: L["time_beats"])
    ranges = []
    for i, loc in enumerate(sorted_locs):
        start = float(loc["time_beats"])
        end = (float(sorted_locs[i + 1]["time_beats"])
               if i + 1 < len(sorted_locs) else start + 32.0)
        ranges.append((loc["name"], start, end))

    target_set = set(TARGET_SECTIONS)
    targets = [(n, s, e) for (n, s, e) in ranges if n in target_set]

    merged = []
    for name, start, end in targets:
        if merged and (start - merged[-1][1]) <= MERGE_GAP_BEATS:
            prev_start, _prev_end, prev_names = merged[-1]
            merged[-1] = (prev_start, end, prev_names + [name])
        else:
            merged.append((start, end, [name]))
    return merged


# ---------------------------------------------------------------------------
# Dense gain curve — production pattern (§2.4 adapted)
# ---------------------------------------------------------------------------

def _build_dense_gain_curve(
    ranges_beats,
    tempo_bpm: float,
    song_end_beats: float,
    spacing_sec: float = GRID_SPACING_SEC,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample a dense per-frame gain curve + per-frame time axis (seconds).

    The grid runs from 0 to the end of the song at ``spacing_sec``
    intervals. Gain at each frame is -6 dB when the frame time falls
    inside any cut range, 0 dB otherwise. Consumed by
    :func:`_feature_to_breakpoints`.

    Returns:
        (gain_curve_db, times_sec) — two parallel 1-D arrays.
    """
    beats_per_sec = tempo_bpm / 60.0
    song_end_sec = song_end_beats / beats_per_sec

    n_frames = int(np.ceil(song_end_sec / spacing_sec)) + 1
    times_sec = np.arange(n_frames) * spacing_sec

    # Convert cut ranges to seconds.
    cut_ranges_sec = [
        (start / beats_per_sec, end / beats_per_sec)
        for (start, end, _names) in ranges_beats
    ]

    # Vectorised per-frame cut membership test.
    in_cut = np.zeros(n_frames, dtype=bool)
    for (start_s, end_s) in cut_ranges_sec:
        in_cut |= (times_sec >= start_s) & (times_sec < end_s)

    gain_curve = np.where(in_cut, CUT_GAIN_DB, NO_CUT_GAIN_DB).astype(float)
    return gain_curve, times_sec


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def apply_correction(als_path: Path) -> int:
    als_path = Path(als_path)
    if not als_path.exists():
        print(f"ERROR: .als file not found: {als_path}")
        return 1

    print(f"=> Source  : {als_path}")

    locators = read_locators(str(als_path))
    if not locators:
        print("ERROR: no locators.")
        return 1

    ranges = _compute_target_ranges_beats(locators)
    if not ranges:
        print(f"ERROR: none of {TARGET_SECTIONS!r} found in locators.")
        return 1

    print()
    print(f"Target cut ranges (merged, gap ≤ {MERGE_GAP_BEATS} beats):")
    for start, end, names in ranges:
        print(f"  {start:8.3f} → {end:8.3f}  "
              f"({end - start:5.1f} beats)  {' + '.join(names)}")

    song_end_beats = max(float(loc["time_beats"]) for loc in locators) + 32.0

    backup_path = backup_als(str(als_path))
    tree = parse_als(str(als_path))

    try:
        track = find_track_by_name(tree, TARGET_TRACK_NAME)
    except ValueError:
        print(f"ERROR: no track {TARGET_TRACK_NAME!r}.")
        return 1

    devices = _devices_container(track)

    # Self-healing — purge any previous CDE EQ (dynamic or static) + its envelopes.
    for legacy_name in (DYNAMIC_DEVICE_NAME, STATIC_DEVICE_NAME):
        legacy = _find_device_by_username(track, legacy_name)
        if legacy is None:
            continue
        stale_target_ids = {
            at.get("Id") for at in legacy.iter("AutomationTarget")
            if at.get("Id") is not None
        }
        for tid in stale_target_ids:
            _remove_existing_envelope(track, tid)
        idx = _remove_device(devices, legacy)
        print(f"NOTE:  purged legacy {legacy_name!r} from chain "
              f"position [{idx}] ({len(stale_target_ids)} envelope "
              f"target(s) removed).")

    # Anchor — the existing Peak Resonance EQ8. Canonical corrective #1 slot.
    anchor = _find_device_by_username(track, PEAK_RESONANCE_NAME)
    if anchor is None:
        print(f"ERROR: anchor {PEAK_RESONANCE_NAME!r} not found.")
        return 1

    # Fresh EQ8 + manual baseline on band 4.
    eq8 = _build_fresh_eq8(tree, user_name=DYNAMIC_DEVICE_NAME)
    band_param = get_eq8_band(eq8, BAND_INDEX)
    configure_eq8_band(
        band_param, mode=BAND_MODE_BELL, freq=BAND_FREQ_HZ,
        gain=NO_CUT_GAIN_DB, q=BAND_Q,
    )
    _activate_band(band_param)

    insertion_idx = _insert_after(devices, anchor, eq8)
    print(f"=> Inserted {DYNAMIC_DEVICE_NAME!r} at chain position "
          f"[{insertion_idx}] (right after {PEAK_RESONANCE_NAME!r}).")

    # Dense gain curve — production pattern matching Peak Resonance density.
    tempo = _extract_tempo(tree)
    gain_curve, times_sec = _build_dense_gain_curve(
        ranges, tempo_bpm=tempo, song_end_beats=song_end_beats,
    )
    print(f"=> Dense grid: {len(gain_curve)} frames at "
          f"{GRID_SPACING_SEC} s spacing "
          f"(song end ~{song_end_beats:.0f} beats, tempo {tempo:.1f} BPM).")

    # Convert to beat-space breakpoints + thin to 500 (production default).
    gain_bps = _feature_to_breakpoints(gain_curve, times_sec, tempo)
    print(f"=> Breakpoints: {len(gain_bps)} "
          f"({int(sum(1 for _, v in gain_bps if v < -0.1))} at cut, "
          f"{int(sum(1 for _, v in gain_bps if abs(v) < 0.1))} at 0 dB).")

    # Write via the production pipeline — validate, remove existing, emit.
    next_id_counter = [get_next_id(tree)]
    _write_validated_env(
        track, band_param, "Gain", gain_bps, next_id_counter,
    )

    save_als_from_tree(tree, str(als_path))

    # Report.
    print()
    print("CDE DYNAMIC CORRECTION APPLIED (v3 — dense production pattern)")
    print("================================================================")
    print(f"Backup              : {backup_path}")
    print(f"Track modifiée      : {TARGET_TRACK_NAME}")
    print(f"Device ajouté       : {DYNAMIC_DEVICE_NAME}")
    print(f"Position dans chain : [{insertion_idx}] (après "
          f"{PEAK_RESONANCE_NAME!r})")
    print(f"Bande 4 manual      : Bell, {BAND_FREQ_HZ:.0f} Hz, Q={BAND_Q}, "
          f"0 dB baseline")
    print(f"Gain automation     : {len(gain_bps)} breakpoints, "
          f"{len(ranges)} cut ranges, grid {GRID_SPACING_SEC} s")
    for start, end, names in ranges:
        print(f"  - {start:7.2f} → {end:7.2f}  "
              f"({CUT_GAIN_DB} dB)  {' + '.join(names)}")
    print(f"Chemin de sortie    : {als_path}")
    print()
    print("Validation suggérée :")
    print("  1. Ouvrir le .als dans Ableton")
    print(f"  2. Track {TARGET_TRACK_NAME} → chain doit être :")
    print(f"     [0] {PEAK_RESONANCE_NAME}  [1] {DYNAMIC_DEVICE_NAME}  "
          f"...  Limiter (dernier)")
    print("  3. Clic sur le device → Arrangement automation lane Band 4 Gain")
    print("     doit montrer une courbe dense (des points tous les ~0.5 s),")
    print("     plate à 0 dB hors sections, plate à -6 dB dans les 4 plages.")
    print("  4. Bounce la track Ambience et re-run Mix Analyzer.")
    return 0


def main(argv):
    als_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_ALS_PATH
    return apply_correction(als_path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
