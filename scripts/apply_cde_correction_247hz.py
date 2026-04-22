#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_cde_correction_247hz.py — one-shot application of the CDE
247 Hz cut recommendation on the ``[A/T] Ambience`` track.

Context:
    Feature 3.6 (CDE) flagged 10 accumulation diagnostics at 247 Hz on
    Acid_Drops_Sections_TFP.als, all targeting the same Ambience track.
    The song key is B (fundamental 246.94 Hz) and the Ambience layer
    resonates continuously there, piling up with every other element
    during the dense sections (Build 2, Drop 2, Fall 2, Chorus 1).

Correction applied:
    EQ8 static cut on the Ambience track — band 4 in Bell mode,
    247 Hz, -6 dB, Q=4, always-on (not section-local since the
    resonance is transversal). Rule 3 (role-appropriate max cut)
    authorises up to -12 dB on a ``[A/T]`` track — -6 dB is
    conservative.

Usage:
    python scripts/apply_cde_correction_247hz.py [als_path]

    Without an argument the script defaults to
    ``Rapports test développement/Acid_Drops_Sections_TFP.als``.

Idempotence:
    Stops cleanly (exit 2) when an EQ8 already named
    ``"CDE 247Hz Cut"`` sits on the Ambience track — the correction
    is not re-applied.

Safety:
    A ``.als.v24.bak`` is written by :func:`als_utils.backup_als`
    before any modification. If the save fails after the tree is
    modified, no partial file is written (``save_als_from_tree``
    writes atomically via ``gzip.open``).
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

# Make project modules importable when the script is run from either
# the repo root or the scripts/ directory.
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
    save_als_from_tree,
)


# ---------------------------------------------------------------------------
# Constants — the CDE-derived correction parameters
# ---------------------------------------------------------------------------

DEFAULT_ALS_PATH = (
    _REPO_ROOT
    / "Rapports test développement"
    / "Acid_Drops_Sections_TFP.als"
)

TARGET_TRACK_NAME = "[A/T] Ambience"   # exact EffectiveName in the .als
EQ8_DEVICE_NAME = "CDE 247Hz Cut"      # UserName of the new EQ8

BAND_INDEX = 3          # 0-indexed — band 4 in Ableton's UI
BAND_MODE_BELL = 3      # EQ8 mode 3 = Bell
BAND_FREQ_HZ = 247.0
BAND_GAIN_DB = -6.0
BAND_Q = 4.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_cde_eq8(track) -> bool:
    """Return True when the track already carries an EQ8 whose
    ``<UserName>`` matches :data:`EQ8_DEVICE_NAME` — the idempotence
    guard."""
    for eq8 in track.findall(".//Eq8"):
        un = eq8.find("UserName")
        if un is not None and un.get("Value") == EQ8_DEVICE_NAME:
            return True
    return False


def _get_devices_container(track):
    """Return the ``Devices`` container for a track.

    Handles both XML shapes surfaced by Ableton:

        * ``DeviceChain/DeviceChain/Devices`` — the doubled path (tracks
          that already carry at least one device)
        * ``DeviceChain/Devices`` — rare fallback

    The ``<Devices />`` self-closing form (track without any device)
    is already materialised as an empty container by ElementTree — we
    append directly.
    """
    devices = track.find(".//DeviceChain/DeviceChain/Devices")
    if devices is None:
        devices = track.find(".//DeviceChain/Devices")
    if devices is None:
        raise RuntimeError(
            "Cannot locate a Devices container on the target track — "
            "the project structure is unexpected."
        )
    return devices


def _activate_band(band_param) -> None:
    """Flip a band's IsOn/Manual flag to ``true`` — the cloned EQ8
    template ships with every band disabled by default."""
    ison = band_param.find("IsOn/Manual")
    if ison is None:
        raise RuntimeError(
            "Band has no IsOn/Manual element — the cloned EQ8 template "
            "is malformed."
        )
    ison.set("Value", "true")


# Neutral band defaults used when we fall back to cloning an in-project
# EQ8. Frequencies are spread across the 8-band range so Ableton's UI
# shows points at sensible positions; gain=0 and IsOn=false makes every
# band inert until the caller explicitly activates one.
_NEUTRAL_BAND_FREQS_HZ = (60.0, 150.0, 400.0, 1000.0,
                          2500.0, 6000.0, 12000.0, 18000.0)


def _clone_in_project_eq8(tree, user_name: str):
    """Fallback when ``Pluggin Mapping.als`` is not available in the
    local environment.

    Deep-copies an existing EQ8 element from the target project,
    renumbers non-zero ``Id`` attributes so no collisions remain, and
    resets every band to a neutral state (Bell, gain 0, Q 0.71, off).
    The caller then configures the one band it needs.
    """
    source = tree.getroot().find(".//Eq8")
    if source is None:
        raise RuntimeError(
            "No Eq8 element found anywhere in the project — "
            "cannot clone an in-project EQ8 template."
        )

    eq8 = copy.deepcopy(source)

    # Renumber every non-zero Id so the clone does not collide with
    # the source device.
    next_id = get_next_id(tree)
    for elem in eq8.iter():
        raw = elem.get("Id")
        if raw is not None and raw != "0":
            elem.set("Id", str(next_id))
            next_id += 1

    un = eq8.find("UserName")
    if un is not None:
        un.set("Value", user_name)

    # Reset every band to neutral — mode 3 Bell, freq spread, 0 dB gain,
    # Q 0.71, off. The caller will configure the specific band.
    for i in range(8):
        band = eq8.find(f"Bands.{i}/ParameterA")
        if band is None:
            continue
        for tag, value in (
            ("Mode/Manual", "3"),
            ("Freq/Manual", str(_NEUTRAL_BAND_FREQS_HZ[i])),
            ("Gain/Manual", "0.0"),
            ("Q/Manual",    "0.7071067095"),
            ("IsOn/Manual", "false"),
        ):
            elem = band.find(tag)
            if elem is not None:
                elem.set("Value", value)

    return eq8


def _build_fresh_eq8(tree, user_name: str):
    """Try the canonical ``Pluggin Mapping.als`` template first, then
    fall back to cloning an in-project EQ8. The fallback is the
    sandbox-friendly path — the user's real machine should hit the
    canonical one.
    """
    try:
        return _clone_eq8_with_unique_ids(tree, user_name=user_name)
    except RuntimeError as e:
        if "template file not found" not in str(e):
            raise
        print(f"NOTE:  {EQ8_DEVICE_NAME} — Pluggin Mapping.als template "
              f"absent; cloning an in-project EQ8 instead.")
        return _clone_in_project_eq8(tree, user_name=user_name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def apply_correction(als_path: Path) -> int:
    """Run the end-to-end CDE correction. Returns a process exit code."""
    als_path = Path(als_path)
    if not als_path.exists():
        print(f"ERROR: .als file not found: {als_path}")
        return 1

    print(f"=> Source  : {als_path}")

    # 1. Backup
    try:
        backup_path = backup_als(str(als_path))
    except Exception as e:
        print(f"ERROR: backup failed: {type(e).__name__}: {e}")
        return 1

    # 2. Parse
    tree = parse_als(str(als_path))

    # 3. Locate the Ambience track
    try:
        track = find_track_by_name(tree, TARGET_TRACK_NAME)
    except ValueError:
        print(f"ERROR: no track named {TARGET_TRACK_NAME!r} found.")
        print("       Aborting without touching the project.")
        return 1

    # 4. Idempotence guard
    if _has_cde_eq8(track):
        print(f"STOP:  track already carries an EQ8 named "
              f"{EQ8_DEVICE_NAME!r}. Nothing to do.")
        return 2

    # 5. Clone + append the new EQ8
    devices = _get_devices_container(track)
    eq8 = _build_fresh_eq8(tree, user_name=EQ8_DEVICE_NAME)
    devices.append(eq8)

    # 6. Configure band 4 (0-indexed 3) — Bell, 247 Hz, -6 dB, Q=4, on
    band = get_eq8_band(eq8, BAND_INDEX)
    configure_eq8_band(
        band,
        mode=BAND_MODE_BELL,
        freq=BAND_FREQ_HZ,
        gain=BAND_GAIN_DB,
        q=BAND_Q,
    )
    _activate_band(band)

    # 7. Save
    save_als_from_tree(tree, str(als_path))

    # 8. Report
    print()
    print("CDE CORRECTION APPLIED")
    print("========================")
    print(f"Backup              : {backup_path}")
    print(f"Track modifiée      : {TARGET_TRACK_NAME}")
    print(f"Device ajouté       : {EQ8_DEVICE_NAME} (EQ Eight)")
    print(f"Bande 4 configurée  : Bell, {BAND_FREQ_HZ:.0f} Hz, "
          f"{BAND_GAIN_DB} dB, Q={BAND_Q}")
    print(f"Chemin de sortie    : {als_path}")
    print()
    print("Validation suggérée :")
    print("  1. Fermer Ableton si ouvert")
    print("  2. Ouvrir le .als modifié")
    print(f"  3. Vérifier la track {TARGET_TRACK_NAME} → "
          f"nouveau EQ '{EQ8_DEVICE_NAME}' en fin de chaîne")
    print("  4. Bounce la track Ambience en WAV (post-fader)")
    print("  5. Re-run Mix Analyzer pour valider la disparition des "
          "accumulations à 247 Hz")
    return 0


def main(argv: list[str]) -> int:
    als_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_ALS_PATH
    return apply_correction(als_path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
