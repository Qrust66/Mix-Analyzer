"""master-bus-configurator — Tier B XML writer for mastering decisions.

Phase 4.15 — translates a ``MixDecision[MasteringDecision]`` (produced by
``mastering-engineer`` Tier A, Phase 4.9) into deterministic XML patches
on the master track and sub-bus tracks.

Architecture (mirror Phase 4.10-4.14) :
- Python module, deterministic, no LLM
- REUSE-only : the master/sub-bus track must already have the target
  device (Eq8, GlueCompressor, Limiter, Saturator, Utility, StereoGain).
  Phase 4.15.X future will add CREATE paths once a device template
  fixture is available.

KEY DISCOVERY : Ableton's master bus XML node is ``<MainTrack>`` at
``LiveSet/MainTrack`` — NOT ``<MasterTrack>``. find_track_by_name() only
scans LiveSet/Tracks/* and won't find the master ; this writer adds a
dedicated ``_find_master_track()`` resolver.

Master move types (6 supported in v1) :
- ``limiter_target``    → Limiter (or SmartLimit) on master ; sets Ceiling
- ``glue_compression``  → GlueCompressor (or Compressor2) on master ; sets
                          Threshold/Ratio/Attack/Release/Makeup
- ``master_eq_band``    → Eq8 on master ; one band write
- ``stereo_enhance``    → Utility/StereoGain on master ; width/balance/bass_mono
- ``saturation_color``  → Saturator on master ; Drive (DryWet)
- ``bus_glue``          → GlueCompressor on sub-bus track (target_track ≠ "Master")

OUT-OF-SCOPE Phase 4.15 v1 :
- multiband_band : not yet in VALID_MASTER_MOVE_TYPES (Phase 4.9.X future)
- Reference matching workflow : Phase 4.X TBD
- Mid/Side EQ master : Eq8 Mode_global already supported via processing_mode
  field (Phase 4.10 step 4 pattern reused)
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import als_utils
from mix_engine.blueprint import (
    MASTER_TRACK_NAME,
    MasteringDecision,
    MasterMove,
    MixDecision,
)


_LOGGER = logging.getLogger(__name__)


# ============================================================================
# Typed exceptions
# ============================================================================


class MasterBusConfiguratorError(Exception):
    """Base exception for master-bus-configurator failures."""


class MasterTrackNotFoundError(MasterBusConfiguratorError):
    """Raised when MainTrack cannot be resolved (unexpected XML structure)."""


class MasterDeviceNotFoundError(MasterBusConfiguratorError):
    """Raised when REUSE-only mode cannot find the target device on master."""


# ============================================================================
# Report dataclass
# ============================================================================


@dataclass(frozen=True)
class MasterBusConfiguratorReport:
    """Audit trail of an apply_mastering_decision invocation."""

    moves_applied: tuple[str, ...] = ()
    """Per-move identifiers (target:type:device)."""

    moves_skipped: tuple[tuple[str, str], ...] = ()
    """(move_id, skip_reason)."""

    devices_reused: int = 0
    """Number of master/sub-bus devices reused (REUSE-only design)."""

    safety_guardian_status: str = "SKIPPED"

    warnings: tuple[str, ...] = ()

    output_path: str = ""


# ============================================================================
# Master track resolution
# ============================================================================


def _find_master_track(tree: ET.ElementTree) -> Optional[ET.Element]:
    """Resolve master bus → MainTrack XML element.

    Ableton stores master bus at ``LiveSet/MainTrack`` (NOT MasterTrack).
    Returns None if not found (caller raises MasterTrackNotFoundError).
    """
    return tree.getroot().find(".//LiveSet/MainTrack")


def _resolve_target(tree: ET.ElementTree, move: MasterMove) -> ET.Element:
    """Resolve move.target_track to its XML element.

    - If target_track == MASTER_TRACK_NAME ("Master") → MainTrack
    - Else → sub-bus track via find_track_by_name (Group track, parent=Master)
    """
    if move.target_track == MASTER_TRACK_NAME:
        master = _find_master_track(tree)
        if master is None:
            raise MasterTrackNotFoundError(
                f"LiveSet/MainTrack not found in .als — unexpected XML structure."
            )
        return master
    # Sub-bus glue : target_track is a Group track in LiveSet/Tracks
    return als_utils.find_track_by_name(tree, move.target_track)


# ============================================================================
# Per-type writers
# ============================================================================


def _set_param(device: ET.Element, param_name: str, value: float) -> bool:
    """Write Manual Value on a named device param. Returns True if found."""
    param = device.find(param_name)
    if param is None:
        return False
    manual = param.find("Manual")
    if manual is None:
        return False
    manual.set("Value", str(float(value)))
    return True


def _find_device(track: ET.Element, allowed_tags: frozenset[str]) -> tuple[Optional[ET.Element], Optional[str]]:
    """Find first device on track matching any of the allowed tags.
    Returns (element, tag) or (None, None) if absent.
    """
    for tag in allowed_tags:
        d = track.find(f".//{tag}")
        if d is not None:
            return d, tag
    return None, None


def _find_master_eq_at_chain_position(
    master_track: ET.Element, chain_position: str,
) -> Optional[ET.Element]:
    """Phase 4.15.1 audit fix : find a specific Eq8 on master per chain_position.

    Master can have up to 2 Eq8 instances :
    - master_corrective : 1st Eq8 (subtractive cleanup, before dynamics)
    - master_tonal      : 2nd Eq8 (additive tilt, after dynamics)

    For 'default' or single-Eq8 masters, returns the first found.
    For 'master_corrective', returns the first Eq8 (assumes corrective comes first
    by convention).
    For 'master_tonal', returns the LAST Eq8 (tonal is later in chain).

    Returns None if no Eq8 on master.
    """
    devices_container = master_track.find(".//DeviceChain/DeviceChain/Devices")
    if devices_container is None:
        devices_container = master_track.find(".//DeviceChain/Devices")
    if devices_container is None:
        return None

    eq8s = [c for c in list(devices_container) if c.tag == "Eq8"]
    if not eq8s:
        return None

    if chain_position == "master_corrective" or chain_position == "default":
        return eq8s[0]
    if chain_position == "master_tonal":
        return eq8s[-1] if len(eq8s) >= 2 else eq8s[0]
    # Other chain_positions don't apply to Eq8 ; return first as fallback
    return eq8s[0]


def _set_eq8_mode_global_for_processing_mode(
    eq8: ET.Element, processing_mode: Optional[str],
) -> None:
    """Phase 4.15.1 audit fix : set Eq8 Mode_global per processing_mode.

    Mapping (matching eq8-configurator Phase 4.10 step 4 conventions) :
    - "stereo" or None → Mode 0 (Stereo)
    - "mid"            → Mode 2 (M/S, write to ParameterA)
    - "side"           → Mode 2 (M/S, write to ParameterB)
    """
    if processing_mode is None or processing_mode == "stereo":
        target_mode = 0
    elif processing_mode in ("mid", "side"):
        target_mode = 2
    else:
        return  # unknown mode, leave Mode_global untouched

    als_utils.set_eq8_mode_global(eq8, target_mode)


def _write_limiter_target(device: ET.Element, move: MasterMove, device_tag: str) -> list[str]:
    """Write Limiter or SmartLimit params (Ceiling, Release, lookahead)."""
    warnings: list[str] = []
    if device_tag == "Limiter":
        if move.ceiling_dbtp is not None:
            if not _set_param(device, "Ceiling", move.ceiling_dbtp):
                warnings.append("Ceiling param missing on Limiter")
        if move.lookahead_ms is not None:
            warnings.append(
                f"lookahead_ms={move.lookahead_ms} ignored : Ableton Limiter "
                f"has no Lookahead Manual param (fixed internal value)"
            )
        # gain_drive_db : agent guidance only ; native Limiter has Gain Manual
        if move.gain_drive_db is not None:
            if not _set_param(device, "Gain", move.gain_drive_db):
                warnings.append("Gain param missing on Limiter")
    elif device_tag == "SmartLimit":
        # SmartLimit uses different param names (General_*)
        if move.ceiling_dbtp is not None:
            if not _set_param(device, "General_limiterThreshold", move.ceiling_dbtp):
                warnings.append("General_limiterThreshold missing on SmartLimit")
        if move.lookahead_ms is not None:
            # SmartLimit has lookahead too — try
            warnings.append(
                f"lookahead_ms write on SmartLimit not yet calibrated — Tier B "
                f"v1 sets ceiling only ; verify in Ableton if needed"
            )
    return warnings


def _write_glue_compression(device: ET.Element, move: MasterMove, device_tag: str) -> list[str]:
    """Write GlueCompressor or Compressor2 params."""
    warnings: list[str] = []
    if move.threshold_db is not None:
        if not _set_param(device, "Threshold", move.threshold_db):
            warnings.append("Threshold missing")
    if move.ratio is not None:
        if not _set_param(device, "Ratio", move.ratio):
            warnings.append("Ratio missing")
    if move.attack_ms is not None:
        if not _set_param(device, "Attack", move.attack_ms):
            warnings.append("Attack missing")
    if move.release_ms is not None:
        if not _set_param(device, "Release", move.release_ms):
            warnings.append("Release missing")
    if move.makeup_db is not None:
        if not _set_param(device, "Makeup", move.makeup_db):
            warnings.append("Makeup missing")
    if move.gr_target_db is not None:
        # gr_target_db is agent guidance, not a native Manual param ; informative
        warnings.append(
            f"gr_target_db={move.gr_target_db} is agent guidance (Tier B has "
            f"no direct GR target param ; Threshold + Ratio drive actual GR)"
        )
    return warnings


def _write_master_eq_band(device: ET.Element, move: MasterMove) -> list[str]:
    """Write one Eq8 band on master. Translates band_type → Mode integer.

    Phase 4.15.1 audit fix : honors move.processing_mode :
    - "stereo" or None → Mode_global=0, write ParameterA
    - "mid"            → Mode_global=2 (M/S), write ParameterA
    - "side"           → Mode_global=2 (M/S), write ParameterB
    """
    warnings: list[str] = []
    # Translate band_type + slope → Eq8 Mode
    mode_map = {
        ("bell", None): 3,
        ("notch", None): 4,
        ("low_shelf", None): 2,
        ("high_shelf", None): 5,
        ("highpass", 48.0): 0,
        ("highpass", 12.0): 1,
        ("lowpass", 12.0): 6,
        ("lowpass", 48.0): 7,
    }
    key = (move.band_type, move.slope_db_per_oct)
    if key not in mode_map:
        warnings.append(
            f"band_type={move.band_type!r} + slope={move.slope_db_per_oct} : "
            f"no Eq8 Mode mapping. Skipped."
        )
        return warnings
    mode = mode_map[key]

    # Phase 4.15.1 : set Eq8 Mode_global per processing_mode
    _set_eq8_mode_global_for_processing_mode(device, move.processing_mode)

    # Find first inactive band slot on the master Eq8
    slot = None
    for i in range(8):
        try:
            band = als_utils.get_eq8_band(device, i)
        except (ValueError, IndexError):
            continue
        is_on = band.find("IsOn/Manual")
        if is_on is None or is_on.get("Value", "false") == "false":
            slot = i
            break
    if slot is None:
        warnings.append(
            "All 8 Eq8 band slots active on master ; cannot allocate new band"
        )
        return warnings

    # Phase 4.15.1 : choose ParameterA (Mid/Stereo) vs ParameterB (Side)
    if move.processing_mode == "side":
        band_param = als_utils.get_eq8_band_param_b(device, slot)
    else:
        band_param = als_utils.get_eq8_band(device, slot)

    als_utils.configure_eq8_band(
        band_param,
        mode=mode,
        freq=move.center_hz,
        gain=move.gain_db,
        q=move.q,
    )
    is_on = band_param.find("IsOn/Manual")
    if is_on is not None:
        is_on.set("Value", "true")

    return warnings


def _write_stereo_enhance(device: ET.Element, move: MasterMove, device_tag: str) -> list[str]:
    """Write StereoGain or Utility params. width / mid_side_balance / bass_mono."""
    warnings: list[str] = []

    if move.width is not None:
        # Both StereoGain and Utility have StereoWidth
        if not _set_param(device, "StereoWidth", move.width):
            warnings.append(f"StereoWidth missing on {device_tag}")

    if move.mid_side_balance is not None:
        if not _set_param(device, "MidSideBalance", move.mid_side_balance):
            warnings.append(f"MidSideBalance missing on {device_tag}")
        # Enable MidSideBalanceOn flag
        on_el = device.find("MidSideBalanceOn")
        if on_el is not None:
            on_el.set("Value", "true")

    if move.bass_mono_freq_hz is not None:
        bm_manual = device.find("BassMono/Manual")
        if bm_manual is None:
            warnings.append(f"BassMono missing on {device_tag}")
        else:
            bm_manual.set("Value", "true")
            if not _set_param(device, "BassMonoFrequency", move.bass_mono_freq_hz):
                warnings.append(f"BassMonoFrequency missing on {device_tag}")

    return warnings


def _write_saturation_color(device: ET.Element, move: MasterMove) -> list[str]:
    """Write Saturator params. drive_pct + saturation_type + dry_wet.

    ⚠️ Phase 4.15.1 audit flag : Saturator XML param names + Type enum
    values are UNVERIFIED. Reference fixture lacks Saturator instances ;
    proper mapping requires consultation of device-mapping-oracle and/or
    a fixture project containing Saturator. Tier B v1 attempts best-guess
    names ('Drive', 'Type', 'DryWet', 'Output') and emits warnings on
    write failure. Phase 4.15.X v2 should verify against catalog.
    """
    warnings: list[str] = []

    if move.drive_pct is not None:
        # ⚠️ unverified : Saturator's Drive Manual likely encodes dB, NOT %.
        # drive_pct=8 will write Drive=8.0 which may overdrive significantly.
        # Schema documents drive_pct ∈ [0.5, 25.0] so we cap interpretation
        # by trusting Tier A's range, but Ableton's actual scale may differ.
        warnings.append(
            f"drive_pct={move.drive_pct} written verbatim to Saturator/Drive — "
            f"unit calibration unverified (likely dB, not % ; Phase 4.15.X "
            f"should consult device-mapping-oracle to confirm)"
        )
        if not _set_param(device, "Drive", move.drive_pct):
            # Saturator may use "Pre" or "Drive" — try fallback names
            if not _set_param(device, "PreDrive", move.drive_pct):
                warnings.append("Drive/PreDrive missing on Saturator")

    if move.saturation_type is not None:
        # Saturator's Type is an enum field (Manual Value=0..5)
        # Map saturation_type names → enum positions (Ableton Saturator types) :
        type_map = {
            "analog_clip": 0,   # Analog Clip
            "soft_sine": 1,     # Soft Sine
            "digital_clip": 2,  # Digital Clip
            "tape": 5,          # Vintage / Tape
            "tube": 4,          # Tube
        }
        enum_val = type_map.get(move.saturation_type)
        if enum_val is not None:
            if not _set_param(device, "Type", float(enum_val)):
                warnings.append(
                    f"Type param missing on Saturator (saturation_type "
                    f"={move.saturation_type})"
                )
        else:
            warnings.append(
                f"saturation_type={move.saturation_type!r} unmapped"
            )

    if move.dry_wet is not None:
        if not _set_param(device, "DryWet", move.dry_wet):
            warnings.append("DryWet missing on Saturator")

    if move.output_db is not None:
        if not _set_param(device, "Output", move.output_db):
            warnings.append("Output missing on Saturator")

    return warnings


# ============================================================================
# Public API
# ============================================================================


def apply_mastering_decision(
    als_path: str | Path,
    decision: MixDecision[MasteringDecision],
    output_path: str | Path | None = None,
    dry_run: bool = False,
    invoke_safety_guardian: bool = True,
) -> MasterBusConfiguratorReport:
    """Apply a mastering decision (master bus + sub-bus glue) to an .als.

    Phase 4.15 v1 supports all 6 MasterMove types (limiter_target,
    glue_compression, master_eq_band, stereo_enhance, saturation_color,
    bus_glue) but REUSE-only. If the master/sub-bus track lacks the
    target device, the move is skipped with reason.

    Args:
        als_path: Source .als file.
        decision: Tier A mastering decision.
        output_path: Where to write modified .als. None = overwrite.
        dry_run: Validate without writing.
        invoke_safety_guardian: Run post-write checks.

    Returns:
        :class:`MasterBusConfiguratorReport`.

    Raises:
        MasterBusConfiguratorError: Generic failure.
        MasterTrackNotFoundError: LiveSet/MainTrack absent (unexpected).
        ValueError: Sub-bus track not found.
    """
    als_path = Path(als_path)
    if not als_path.exists():
        raise MasterBusConfiguratorError(f"Source .als not found : {als_path}")

    if output_path is None and not dry_run:
        output_path = als_path
    output_path = Path(output_path) if output_path else als_path

    moves = decision.value.moves
    if not moves:
        return MasterBusConfiguratorReport(
            output_path=str(als_path if dry_run else output_path),
        )

    tree = als_utils.parse_als(str(als_path))

    moves_applied: list[str] = []
    moves_skipped: list[tuple[str, str]] = []
    warnings: list[str] = []
    devices_reused: int = 0

    # Per-type → allowed device tags (mirror MASTER_DEVICES_BY_TYPE)
    type_to_tags: dict[str, frozenset[str]] = {
        "limiter_target": frozenset({"Limiter", "SmartLimit"}),
        "glue_compression": frozenset({"GlueCompressor", "Compressor2"}),
        "master_eq_band": frozenset({"Eq8"}),
        "stereo_enhance": frozenset({"Utility", "StereoGain"}),
        "saturation_color": frozenset({"Saturator"}),
        "bus_glue": frozenset({"GlueCompressor", "Compressor2"}),
    }

    for move in moves:
        move_id = f"{move.target_track}:{move.type}:{move.device}"

        try:
            track_el = _resolve_target(tree, move)
        except (MasterTrackNotFoundError, ValueError) as exc:
            moves_skipped.append((move_id, f"target resolution failed : {exc}"))
            continue

        # Find device on track
        allowed_tags = type_to_tags.get(move.type)
        if allowed_tags is None:
            moves_skipped.append((move_id, f"unknown move.type={move.type!r}"))
            continue

        # Filter to the specific device the move asks for (e.g., move.device='Limiter'
        # but allowed_tags also contains 'SmartLimit' — prefer move.device first)
        device, device_tag = None, None

        # Phase 4.15.1 audit fix : chain_position dispatch for master_eq_band
        # (master can have multiple Eq8 instances : master_corrective vs master_tonal)
        if (move.type == "master_eq_band"
                and move.target_track == MASTER_TRACK_NAME):
            eq8 = _find_master_eq_at_chain_position(track_el, move.chain_position)
            if eq8 is not None:
                device, device_tag = eq8, "Eq8"

        # 1st pass : find exact device requested by move.device
        if device is None and move.device in allowed_tags:
            d = track_el.find(f".//{move.device}")
            if d is not None:
                device, device_tag = d, move.device
        # 2nd pass : fall back to any allowed device
        if device is None:
            device, device_tag = _find_device(track_el, allowed_tags)

        if device is None:
            reason = (
                f"track {move.target_track!r} has no {sorted(allowed_tags)} "
                f"device. Phase 4.15 v1 is REUSE-only — user must add the "
                f"device manually OR Phase 4.15.X will add CREATE paths."
            )
            moves_skipped.append((move_id, reason))
            warnings.append(f"{move_id} skipped : {reason}")
            continue

        devices_reused += 1

        # Dispatch by type
        if move.type == "limiter_target":
            type_warns = _write_limiter_target(device, move, device_tag)
        elif move.type in ("glue_compression", "bus_glue"):
            type_warns = _write_glue_compression(device, move, device_tag)
        elif move.type == "master_eq_band":
            type_warns = _write_master_eq_band(device, move)
        elif move.type == "stereo_enhance":
            type_warns = _write_stereo_enhance(device, move, device_tag)
        elif move.type == "saturation_color":
            type_warns = _write_saturation_color(device, move)
        else:
            moves_skipped.append((move_id, f"unhandled type={move.type}"))
            continue

        for w in type_warns:
            warnings.append(f"{move_id}: {w}")

        moves_applied.append(move_id)
        _LOGGER.info("Applied %s on %r", move_id, move.target_track)

    if dry_run:
        return MasterBusConfiguratorReport(
            moves_applied=tuple(moves_applied),
            moves_skipped=tuple(moves_skipped),
            devices_reused=devices_reused,
            warnings=tuple(warnings),
            output_path=str(als_path),
        )

    final_als = als_utils.save_als_from_tree(tree, str(output_path))

    safety_status = "SKIPPED"
    if invoke_safety_guardian:
        safety_status, safety_issues = _run_safety_checks(final_als)
        if safety_issues:
            for issue in safety_issues:
                warnings.append(f"safety_guardian: {issue}")

    return MasterBusConfiguratorReport(
        moves_applied=tuple(moves_applied),
        moves_skipped=tuple(moves_skipped),
        devices_reused=devices_reused,
        safety_guardian_status=safety_status,
        warnings=tuple(warnings),
        output_path=str(final_als),
    )


# ============================================================================
# Safety guardian
# ============================================================================


def _run_safety_checks(als_path: str | Path) -> tuple[str, list[str]]:
    """Deterministic post-write safety checks for mastering XML.

    Phase 4.15 checks :
    1. File exists, gunzippable, parses as XML
    2. NextPointeeId > max(Id)
    3. MainTrack present (master not deleted)
    4. Master Limiter Ceiling ∈ [-3.0, -0.1] dBTP (industry-standard cap)
    5. Master GlueCompressor Threshold valid
    6. Master Eq8 bands valid (Mode 0-7, Freq [30, 22000], Gain ±15)
    """
    issues: list[str] = []
    als_path = Path(als_path)

    if not als_path.exists():
        return "FAIL", [f"File does not exist: {als_path}"]

    try:
        tree = als_utils.parse_als(str(als_path))
    except Exception as exc:
        return "FAIL", [f"Cannot parse as .als: {type(exc).__name__}: {exc}"]

    root = tree.getroot()

    # NextPointeeId
    next_pid_el = root.find(".//NextPointeeId")
    max_id = 0
    for elem in root.iter():
        raw = elem.get("Id")
        if raw is not None:
            try:
                v = int(raw)
                if v > max_id:
                    max_id = v
            except ValueError:
                pass
    if next_pid_el is not None:
        try:
            v = int(next_pid_el.get("Value", "0"))
            if v <= max_id:
                issues.append(f"NextPointeeId={v} ≤ max Id ({max_id})")
        except ValueError:
            pass

    # MainTrack present
    main = root.find(".//LiveSet/MainTrack")
    if main is None:
        issues.append("LiveSet/MainTrack not found — master bus structure broken")
        return "FAIL", issues

    # Master Limiter Ceiling cap : never above -0.1 dBTP (streaming)
    for limiter in main.findall(".//Limiter"):
        ceiling = limiter.find("Ceiling/Manual")
        if ceiling is not None:
            try:
                v = float(ceiling.get("Value", "0"))
                if v > -0.1:
                    issues.append(
                        f"Master Limiter Ceiling={v} dBTP > -0.1 — NEVER "
                        f"acceptable for streaming output"
                    )
                if v < -3.0:
                    issues.append(
                        f"Master Limiter Ceiling={v} dBTP < -3.0 — overly "
                        f"conservative (vinyl ceiling = -1.0 typical)"
                    )
            except ValueError:
                pass

    # Master GlueCompressor Threshold range
    for glue in main.findall(".//GlueCompressor"):
        th = glue.find("Threshold/Manual")
        if th is not None:
            try:
                v = float(th.get("Value", "0"))
                if not (-60.0 <= v <= 0.0):
                    issues.append(
                        f"Master GlueCompressor Threshold={v} dB out of "
                        f"[-60, 0]"
                    )
            except ValueError:
                pass

    # Master Eq8 bands
    for eq8 in main.findall(".//Eq8"):
        for i in range(8):
            band = eq8.find(f"Bands.{i}")
            if band is None:
                continue
            for param in (band.find("ParameterA"), band.find("ParameterB")):
                if param is None:
                    continue
                # Mode 0..7
                mode = param.find("Mode/Manual")
                if mode is not None:
                    try:
                        v = int(mode.get("Value", "0"))
                        if not (0 <= v <= 7):
                            issues.append(
                                f"Master Eq8 Bands.{i} Mode={v} not in 0..7"
                            )
                    except ValueError:
                        pass
                # Freq [30, 22000]
                freq = param.find("Freq/Manual")
                if freq is not None:
                    try:
                        v = float(freq.get("Value", "0"))
                        if not (30.0 <= v <= 22000.0):
                            issues.append(
                                f"Master Eq8 Bands.{i} Freq={v} out of [30, 22000]"
                            )
                    except ValueError:
                        pass
                # Gain ±15
                gain = param.find("Gain/Manual")
                if gain is not None:
                    try:
                        v = float(gain.get("Value", "0"))
                        if not (-15.0 <= v <= 15.0):
                            issues.append(
                                f"Master Eq8 Bands.{i} Gain={v} out of "
                                f"[-15, +15] dB"
                            )
                    except ValueError:
                        pass

    return ("PASS" if not issues else "FAIL"), issues
