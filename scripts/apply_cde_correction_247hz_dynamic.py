#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_cde_correction_247hz_dynamic.py — section-aware version of
the 247 Hz accumulation cut on the ``[A/T] Ambience`` track.

Supersedes ``apply_cde_correction_247hz.py`` (static always-on):

    * Removes the previously-installed static ``"CDE 247Hz Cut"`` EQ8
      (which the first pass landed at the END of the chain, after the
      Limiter — the wrong spot per §effect_chain_placement).
    * Inserts a fresh EQ8 named ``"CDE 247Hz Cut (dynamic)"`` right
      AFTER the existing ``"Peak Resonance"`` corrective EQ — the
      canonical "EQ8 #1 correctif, avant compresseur" slot described in
      ``ableton_devices_mapping_v2_3.json``.
    * Configures band 4 in Bell mode at 247 Hz / Q=4, manual gain 0 dB,
      IsOn=true. The cut depth is driven entirely by a Gain automation
      envelope — the band is "inert" by default and only digs the
      Ambience in sections where the CDE flagged an accumulation.
    * Writes a staircase Gain envelope with two-event bookends
      (``t`` and ``t+0.001`` beats) at each section boundary so the
      transitions read as near-instantaneous switches rather than
      linear sweeps.

Target sections — merged when adjacent with gap ≤ 4 beats:

    Build 2              104.000 → 136.000   ( 32.0 beats, 5 acc)
    Drop 1 + Chorus 1    168.000 → 232.000   ( 64.0 beats, 6 acc — Fall 1 gap 1b)
    Fall 2 + Drop 2      310.500 → 342.000   ( 31.5 beats, 9 acc — adjacent)
    Chorus 2             376.000 → 408.000   ( 32.0 beats, 3 acc)

Outside these ranges the Ambience runs at full amplitude on 247 Hz —
no unnecessary thinning in Intro, Break 1, Breakdown 1, Outro, etc.

Usage:
    python scripts/apply_cde_correction_247hz_dynamic.py [als_path]

Idempotence:
    Stops cleanly (exit 2) if ``"CDE 247Hz Cut (dynamic)"`` is already
    present. Silently removes the older static ``"CDE 247Hz Cut"``
    before inserting the dynamic version — so running this script once
    supersedes the static one-shot cleanly.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from als_utils import (  # noqa: E402
    _clone_eq8_with_unique_ids,
    backup_als,
    configure_eq8_band,
    find_track_by_name,
    get_automation_target_id,
    get_eq8_band,
    get_next_id,
    parse_als,
    read_locators,
    save_als_from_tree,
    write_automation_envelope,
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
STATIC_DEVICE_NAME = "CDE 247Hz Cut"               # the v1 static cut to purge
PEAK_RESONANCE_NAME = "Peak Resonance"             # insertion anchor

BAND_INDEX = 3                 # 0-indexed — band 4 in Ableton's UI
BAND_MODE_BELL = 3
BAND_FREQ_HZ = 247.0
BAND_Q = 4.0
CUT_GAIN_DB = -6.0
NO_CUT_GAIN_DB = 0.0

# Target sections (as flagged by the CDE accumulation detector).
# Times in beats are read from the project locators at runtime; this
# list carries the names only.
TARGET_SECTIONS = ("Build 2", "Drop 1", "Chorus 1", "Fall 2", "Drop 2",
                   "Chorus 2")

# Merge neighbours when the gap between two target sections is at most
# ``MERGE_GAP_BEATS`` — avoids sub-bar dips when one untouched section
# (e.g. Fall 1, 1 beat long) sits between two consecutive targets.
MERGE_GAP_BEATS = 4.0

# A near-instant step at a section boundary is produced with two
# breakpoints this far apart (in beats). 0.001 beats ≈ 0.47 ms at
# 128 BPM — well below the ear's resolution, visually a staircase
# in Live's arrangement view.
STEP_EPSILON_BEATS = 0.001


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_device_by_username(track, username: str):
    """Return the first EQ8 device on the track whose ``<UserName>``
    matches, or ``None``."""
    for eq8 in track.findall(".//Eq8"):
        un = eq8.find("UserName")
        if un is not None and un.get("Value") == username:
            return eq8
    return None


def _devices_container(track):
    """Return the ``<Devices>`` container (handles both doubled +
    single DeviceChain paths)."""
    devices = track.find(".//DeviceChain/DeviceChain/Devices")
    if devices is None:
        devices = track.find(".//DeviceChain/Devices")
    if devices is None:
        raise RuntimeError("No Devices container on the target track.")
    return devices


def _remove_device(devices, device):
    """Remove ``device`` from its ``Devices`` parent. Raises if absent."""
    for i, child in enumerate(list(devices)):
        if child is device:
            devices.remove(child)
            return i
    raise RuntimeError("Device not found in container — cannot remove.")


def _neutral_bands(eq8):
    """Reset every band to neutral (Bell, 0 dB gain, off). Used after
    cloning an in-project EQ8 to produce a clean slate before we
    configure band 4."""
    # Frequencies spread across the 8 bands so Ableton's UI shows points
    # in sensible positions even when every band is off.
    default_freqs = (60.0, 150.0, 400.0, 1000.0,
                     2500.0, 6000.0, 12000.0, 18000.0)
    for i in range(8):
        band = eq8.find(f"Bands.{i}/ParameterA")
        if band is None:
            continue
        for tag, value in (
            ("Mode/Manual", "3"),
            ("Freq/Manual", str(default_freqs[i])),
            ("Gain/Manual", "0.0"),
            ("Q/Manual", "0.7071067095"),
            ("IsOn/Manual", "false"),
        ):
            elem = band.find(tag)
            if elem is not None:
                elem.set("Value", value)


def _clone_fresh_eq8(tree, user_name: str):
    """Get a clean EQ8 — canonical template if available, otherwise
    in-project clone with neutral bands. Same fallback pattern as the
    static script."""
    try:
        return _clone_eq8_with_unique_ids(tree, user_name=user_name)
    except RuntimeError as e:
        if "template file not found" not in str(e):
            raise
        print(f"NOTE:  Pluggin Mapping.als template absent; "
              f"cloning an in-project EQ8 instead.")
        # Fallback path
        source = tree.getroot().find(".//Eq8")
        if source is None:
            raise RuntimeError("No Eq8 in project; cannot clone.")
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
        _neutral_bands(eq8)
        return eq8


def _insert_after(devices, anchor, new_device) -> int:
    """Insert ``new_device`` right after ``anchor`` in the ``Devices``
    container. Returns the resulting index of the new device."""
    children = list(devices)
    anchor_idx = None
    for i, child in enumerate(children):
        if child is anchor:
            anchor_idx = i
            break
    if anchor_idx is None:
        raise RuntimeError("Anchor device not found in container.")

    # Rebuild the container with new_device inserted after anchor.
    for child in children:
        devices.remove(child)
    for i, child in enumerate(children):
        devices.append(child)
        if i == anchor_idx:
            devices.append(new_device)
    return anchor_idx + 1


def _compute_target_ranges(locators) -> list[tuple[float, float, list[str]]]:
    """From the project's locators, return ``(start, end, [names])``
    tuples for each merged target range.

    Locators are sorted by time; each section's end = the next
    locator's start. Only the sections named in :data:`TARGET_SECTIONS`
    are kept. Consecutive targets separated by a gap ≤
    :data:`MERGE_GAP_BEATS` are coalesced into one range.
    """
    sorted_locs = sorted(locators, key=lambda L: L["time_beats"])
    # Build (name, start, end) triples.
    ranges: list[tuple[str, float, float]] = []
    for i, loc in enumerate(sorted_locs):
        start = float(loc["time_beats"])
        end = (float(sorted_locs[i + 1]["time_beats"])
               if i + 1 < len(sorted_locs) else start + 32.0)
        ranges.append((loc["name"], start, end))

    # Keep only target sections, preserving chronological order.
    target_set = set(TARGET_SECTIONS)
    targets = [(name, s, e) for (name, s, e) in ranges if name in target_set]

    # Merge consecutive entries whose gap ≤ MERGE_GAP_BEATS.
    merged: list[tuple[float, float, list[str]]] = []
    for name, start, end in targets:
        if merged and (start - merged[-1][1]) <= MERGE_GAP_BEATS:
            prev_start, _prev_end, prev_names = merged[-1]
            merged[-1] = (prev_start, end, prev_names + [name])
        else:
            merged.append((start, end, [name]))
    return merged


def _build_gain_breakpoints(
    ranges: list[tuple[float, float, list[str]]],
) -> list[tuple[float, float]]:
    """Turn merged cut ranges into Ableton FloatEvent breakpoints.

    Emits a staircase (t, -6 dB) / (t + ε, -6 dB) / (end - ε, -6 dB) /
    (end, 0 dB) for each range — very-short ramps that read as
    instantaneous switches in Live.

    The pre-song default (``Time=-63072000``, Value=0 dB) is NOT
    included here — ``write_automation_envelope`` prepends it
    automatically using the first event's value. We therefore emit an
    opening ``(ε, 0.0)`` event so the pre-song default lands at 0 dB.
    """
    events: list[tuple[float, float]] = []
    # Explicit 0 dB floor before the first cut so the envelope is
    # unambiguous from the project start.
    events.append((0.0, NO_CUT_GAIN_DB))

    for start, end, _names in ranges:
        events.append((start, CUT_GAIN_DB))
        events.append((start + STEP_EPSILON_BEATS, CUT_GAIN_DB))
        events.append((end - STEP_EPSILON_BEATS, CUT_GAIN_DB))
        events.append((end, NO_CUT_GAIN_DB))

    return events


def _activate_band(band_param):
    ison = band_param.find("IsOn/Manual")
    if ison is None:
        raise RuntimeError("Band has no IsOn/Manual.")
    ison.set("Value", "true")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def apply_correction(als_path: Path) -> int:
    als_path = Path(als_path)
    if not als_path.exists():
        print(f"ERROR: .als file not found: {als_path}")
        return 1

    print(f"=> Source  : {als_path}")

    # 1. Locators first — they come from the file before we touch it.
    locators = read_locators(str(als_path))
    if not locators:
        print("ERROR: no locators found in the project — "
              "cannot derive section ranges.")
        return 1

    ranges = _compute_target_ranges(locators)
    if not ranges:
        print("ERROR: none of the CDE-flagged sections "
              f"{TARGET_SECTIONS!r} found in the project's locators.")
        return 1

    print()
    print("Target cut ranges (merged, gap ≤ "
          f"{MERGE_GAP_BEATS} beats):")
    for start, end, names in ranges:
        print(f"  {start:8.3f} → {end:8.3f}  "
              f"({end - start:5.1f} beats)  {' + '.join(names)}")

    # 2. Backup before any tree mutation.
    backup_path = backup_als(str(als_path))

    # 3. Parse + locate the track.
    tree = parse_als(str(als_path))
    try:
        track = find_track_by_name(tree, TARGET_TRACK_NAME)
    except ValueError:
        print(f"ERROR: no track named {TARGET_TRACK_NAME!r}.")
        return 1

    # 4. Idempotence guard.
    if _find_device_by_username(track, DYNAMIC_DEVICE_NAME) is not None:
        print(f"STOP:  {DYNAMIC_DEVICE_NAME!r} already on the track — "
              f"nothing to do.")
        return 2

    devices = _devices_container(track)

    # 5. Remove the static v1 cut if still present. This keeps the chain
    # sane when replaying the correction — the dynamic version
    # supersedes the static one.
    static_old = _find_device_by_username(track, STATIC_DEVICE_NAME)
    if static_old is not None:
        idx = _remove_device(devices, static_old)
        print(f"NOTE:  removed legacy static {STATIC_DEVICE_NAME!r} "
              f"from chain position [{idx}].")

    # 6. Find the Peak Resonance anchor for insertion.
    anchor = _find_device_by_username(track, PEAK_RESONANCE_NAME)
    if anchor is None:
        print(f"ERROR: anchor device {PEAK_RESONANCE_NAME!r} not found "
              f"on the track. Cannot determine where to insert the new "
              f"corrective EQ.")
        return 1

    # 7. Clone a fresh EQ8, configure band 4 manual state, activate.
    eq8 = _clone_fresh_eq8(tree, user_name=DYNAMIC_DEVICE_NAME)
    band_param = get_eq8_band(eq8, BAND_INDEX)
    configure_eq8_band(
        band_param,
        mode=BAND_MODE_BELL,
        freq=BAND_FREQ_HZ,
        gain=NO_CUT_GAIN_DB,   # baseline 0 dB — cuts come from the envelope
        q=BAND_Q,
    )
    _activate_band(band_param)

    # 8. Insert the EQ right after Peak Resonance.
    insertion_idx = _insert_after(devices, anchor, eq8)
    print(f"=> Inserted {DYNAMIC_DEVICE_NAME!r} at chain position "
          f"[{insertion_idx}] (immediately after {PEAK_RESONANCE_NAME!r}).")

    # 9. Build & write the Gain automation envelope.
    events = _build_gain_breakpoints(ranges)
    gain_target_id = get_automation_target_id(band_param, "Gain")
    next_id_counter = [get_next_id(tree)]
    write_automation_envelope(
        track_element=track,
        pointee_id=gain_target_id,
        events=events,
        next_id_counter=next_id_counter,
        event_type="FloatEvent",
    )
    print(f"=> Wrote {len(events)} gain breakpoints targeting band 4 "
          f"(AutomationTarget Id={gain_target_id}).")

    # 10. Save.
    save_als_from_tree(tree, str(als_path))

    # 11. Report.
    print()
    print("CDE DYNAMIC CORRECTION APPLIED")
    print("================================")
    print(f"Backup              : {backup_path}")
    print(f"Track modifiée      : {TARGET_TRACK_NAME}")
    print(f"Device ajouté       : {DYNAMIC_DEVICE_NAME}")
    print(f"Position dans chain : [{insertion_idx}] (juste après "
          f"{PEAK_RESONANCE_NAME!r})")
    print(f"Bande 4 manual      : Bell, {BAND_FREQ_HZ:.0f} Hz, "
          f"Q={BAND_Q}, 0 dB baseline")
    print(f"Gain automation     : {len(events)} points, "
          f"{len(ranges)} cut ranges")
    for start, end, names in ranges:
        print(f"  - {start:7.2f} → {end:7.2f}  "
              f"({CUT_GAIN_DB} dB)  {' + '.join(names)}")
    print(f"Chemin de sortie    : {als_path}")
    print()
    print("Validation suggérée :")
    print("  1. Fermer Ableton si ouvert")
    print("  2. Ouvrir le .als modifié")
    print(f"  3. Track {TARGET_TRACK_NAME} → chain doit être :")
    print(f"     [0] {PEAK_RESONANCE_NAME}  [1] {DYNAMIC_DEVICE_NAME}  "
          f"...  Limiter (dernier)")
    print(f"  4. Arrangement view → Automation lane 'Eq8 — Gain (band 4)' "
          f"montre la courbe staircase")
    print("  5. Bounce la track Ambience")
    print("  6. Re-run Mix Analyzer pour valider la disparition des "
          "accumulations à 247 Hz")
    return 0


def main(argv: list[str]) -> int:
    als_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_ALS_PATH
    return apply_correction(als_path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
