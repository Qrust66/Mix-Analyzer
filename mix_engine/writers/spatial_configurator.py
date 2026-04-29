"""spatial-configurator — Tier B XML writer for spatial / stereo decisions.

Phase 4.12 — translates a ``MixDecision[SpatialDecision]`` (produced by
``stereo-and-spatial-engineer`` Tier A) into deterministic XML patches.

Architecture (mirror of Phase 4.10/4.11 pattern, methodology compressed
to 2 steps as patterns mature) :
- Python module, deterministic, no LLM
- Reuse als_utils primitives
- REUSE-only (no create paths) for StereoGain — same constraint as
  dynamics-configurator (no Pluggin Mapping.als template)
- ``move_type='pan'`` writes Mixer/Pan directly (no device needed) ;
  always supported regardless of fixture devices

Phase 4.12 v1 supports all 7 move types from VALID_SPATIAL_MOVE_TYPES :
- pan        → track's Mixer/Pan/Manual (NO device)
- width      → StereoGain.StereoWidth/Manual (REUSE)
- mono       → StereoGain.Mono/Manual = "true" (REUSE)
- bass_mono  → StereoGain.BassMono + BassMonoFrequency (REUSE)
- balance    → StereoGain.Balance/Manual (REUSE)
- ms_balance → StereoGain.MidSideBalance + MidSideBalanceOn (REUSE)
- phase_flip → StereoGain.PhaseInvertL or PhaseInvertR (REUSE)
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import als_utils
from mix_engine.blueprint import (
    SpatialDecision,
    SpatialMove,
    MixDecision,
)


_LOGGER = logging.getLogger(__name__)


# ============================================================================
# Typed exceptions
# ============================================================================


class SpatialConfiguratorError(Exception):
    """Base exception for spatial-configurator failures."""


class SpatialDeviceNotFoundError(SpatialConfiguratorError):
    """Raised when REUSE-only mode cannot find StereoGain on the track.

    Phase 4.12 v1 doesn't create new StereoGain (no template available).
    Pan moves don't need a device ; only width/mono/bass_mono/balance/
    ms_balance/phase_flip require StereoGain.
    """


# ============================================================================
# Report dataclass
# ============================================================================


@dataclass(frozen=True)
class SpatialConfiguratorReport:
    """Audit trail of an apply_spatial_decision invocation."""

    moves_applied: tuple[str, ...] = ()
    """Per-move identifiers (track:move_type) successfully written."""

    moves_skipped: tuple[tuple[str, str], ...] = ()
    """(move_id, skip_reason)."""

    stereo_gains_reused: int = 0
    """Number of existing StereoGain devices reused."""

    pans_written: int = 0
    """Number of Mixer.Pan writes (no device involved)."""

    safety_guardian_status: str = "SKIPPED"
    """'PASS' | 'FAIL' | 'SKIPPED'."""

    warnings: tuple[str, ...] = ()

    output_path: str = ""


# ============================================================================
# Per-move-type writers
# ============================================================================


def _write_track_pan(track_element: ET.Element, pan_value: float) -> bool:
    """Write Mixer/Pan/Manual on the track. Returns True on success."""
    pan_el = track_element.find(".//DeviceChain/Mixer/Pan/Manual")
    if pan_el is None:
        # Try alternative path (Group tracks may differ)
        pan_el = track_element.find(".//Mixer/Pan/Manual")
    if pan_el is None:
        return False
    pan_el.set("Value", str(float(pan_value)))
    return True


def _write_stereo_gain_width(sg: ET.Element, width: float) -> bool:
    manual = sg.find("StereoWidth/Manual")
    if manual is None:
        return False
    manual.set("Value", str(float(width)))
    return True


def _write_stereo_gain_mono(sg: ET.Element) -> bool:
    """Set Mono toggle to true. No 'mono off' move (Tier A only emits when
    mono should be enabled — disabling mono is creative scope, not corrective)."""
    manual = sg.find("Mono/Manual")
    if manual is None:
        return False
    manual.set("Value", "true")
    return True


def _write_stereo_gain_bass_mono(sg: ET.Element, freq_hz: float) -> bool:
    """Enable BassMono + set BassMonoFrequency."""
    bm_manual = sg.find("BassMono/Manual")
    if bm_manual is None:
        return False
    bm_manual.set("Value", "true")
    freq_manual = sg.find("BassMonoFrequency/Manual")
    if freq_manual is None:
        return False
    freq_manual.set("Value", str(float(freq_hz)))
    return True


def _write_stereo_gain_balance(sg: ET.Element, balance: float) -> bool:
    manual = sg.find("Balance/Manual")
    if manual is None:
        return False
    manual.set("Value", str(float(balance)))
    return True


def _write_stereo_gain_ms_balance(sg: ET.Element, ms_value: float) -> bool:
    """Enable MidSideBalanceOn + write MidSideBalance value."""
    on_el = sg.find("MidSideBalanceOn")
    if on_el is None:
        return False
    on_el.set("Value", "true")
    manual = sg.find("MidSideBalance/Manual")
    if manual is None:
        return False
    manual.set("Value", str(float(ms_value)))
    return True


def _write_stereo_gain_phase_flip(sg: ET.Element, channel: str) -> bool:
    """Toggle PhaseInvertL or PhaseInvertR (channel ∈ {'L', 'R'})."""
    if channel not in ("L", "R"):
        return False
    target_tag = "PhaseInvertL" if channel == "L" else "PhaseInvertR"
    manual = sg.find(f"{target_tag}/Manual")
    if manual is None:
        return False
    manual.set("Value", "true")
    return True


def _find_existing_stereo_gain(
    track_element: ET.Element, chain_position: str = "default",
) -> Optional[ET.Element]:
    """REUSE-only : find existing StereoGain honoring chain_position semantics.

    Phase 4.12.1 audit fix : prior version ignored chain_position entirely.
    Now respects the 5 VALID_SPATIAL_CHAIN_POSITIONS values :

    - 'default'                  → first StereoGain found (any position)
    - 'chain_start'              → StereoGain at chain index 0 (typically for
                                    phase_flip — fix polarity before processing)
    - 'post_eq_corrective'       → StereoGain placed AFTER any Eq8
    - 'post_dynamics_corrective' → StereoGain AFTER any Compressor2/
                                    GlueCompressor/Limiter/Gate/DrumBuss
    - 'chain_end'                → StereoGain at the last index (no device
                                    after it ; typical pan-stage / width slot)

    Returns the matching StereoGain Element, or None if no match in the
    requested region (caller skips with reason).
    """
    devices_container = track_element.find(".//DeviceChain/DeviceChain/Devices")
    if devices_container is None:
        devices_container = track_element.find(".//DeviceChain/Devices")
    if devices_container is None:
        return None

    children = list(devices_container)
    sg_indices = [i for i, c in enumerate(children) if c.tag == "StereoGain"]
    if not sg_indices:
        return None

    if chain_position == "default":
        return children[sg_indices[0]]

    if chain_position == "chain_start":
        return children[sg_indices[0]] if sg_indices[0] == 0 else None

    if chain_position == "chain_end":
        # Last device in chain must be StereoGain
        return (children[sg_indices[-1]]
                if sg_indices[-1] == len(children) - 1 else None)

    if chain_position == "post_eq_corrective":
        eq8_indices = [i for i, c in enumerate(children) if c.tag == "Eq8"]
        if not eq8_indices:
            return None  # no Eq8 to anchor against
        last_eq8 = eq8_indices[-1]
        for idx in sg_indices:
            if idx > last_eq8:
                return children[idx]
        return None

    if chain_position == "post_dynamics_corrective":
        dyn_tags = ("Compressor2", "GlueCompressor", "Limiter", "Gate", "DrumBuss")
        dyn_indices = [
            i for i, c in enumerate(children) if c.tag in dyn_tags
        ]
        if not dyn_indices:
            return None  # no dynamics device to anchor against
        last_dyn = dyn_indices[-1]
        for idx in sg_indices:
            if idx > last_dyn:
                return children[idx]
        return None

    raise ValueError(
        f"Unknown spatial chain_position={chain_position!r}. Valid : default, "
        f"chain_start, post_eq_corrective, post_dynamics_corrective, chain_end."
    )


# ============================================================================
# Public API
# ============================================================================


def apply_spatial_decision(
    als_path: str | Path,
    decision: MixDecision[SpatialDecision],
    output_path: str | Path | None = None,
    dry_run: bool = False,
    invoke_safety_guardian: bool = True,
) -> SpatialConfiguratorReport:
    """Apply a spatial / stereo decision to an .als file.

    Phase 4.12 v1 SCOPE :
    - pan moves : write Mixer/Pan directly on track (always supported)
    - other 6 move types : require existing StereoGain (REUSE-only)
    - If StereoGain absent, move is skipped with reason ; pan moves on
      same track are still applied.

    Args:
        als_path: Source .als file.
        decision: Tier A spatial decision (typed).
        output_path: Where to write modified .als. None = overwrite source.
        dry_run: Validate without writing.
        invoke_safety_guardian: Run post-write deterministic checks.

    Returns:
        :class:`SpatialConfiguratorReport`.

    Raises:
        SpatialConfiguratorError: Generic failure.
        ValueError: Track not found OR phase_flip with invalid phase_channel.
    """
    als_path = Path(als_path)
    if not als_path.exists():
        raise SpatialConfiguratorError(f"Source .als not found : {als_path}")

    if output_path is None and not dry_run:
        output_path = als_path
    output_path = Path(output_path) if output_path else als_path

    moves = decision.value.moves
    if not moves:
        return SpatialConfiguratorReport(
            output_path=str(als_path if dry_run else output_path),
        )

    tree = als_utils.parse_als(str(als_path))

    moves_applied: list[str] = []
    moves_skipped: list[tuple[str, str]] = []
    warnings: list[str] = []
    stereo_gains_reused: int = 0
    pans_written: int = 0

    # Pre-scan : tracks whose StereoGain we've already reused this run
    # (count uniquely per track).
    tracks_with_sg_reused_this_run: set[str] = set()

    for move in moves:
        move_id = f"{move.track}:{move.move_type}"

        try:
            track_el = als_utils.find_track_by_name(tree, move.track)
        except ValueError:
            raise  # propagate Tier A misalignment

        # ---- pan : no device required ----
        if move.move_type == "pan":
            if move.pan is None:
                moves_skipped.append((move_id, "pan move missing pan value"))
                continue
            ok = _write_track_pan(track_el, move.pan)
            if not ok:
                moves_skipped.append(
                    (move_id, "track has no Mixer/Pan structure")
                )
                continue
            pans_written += 1
            moves_applied.append(move_id)
            _LOGGER.info("Applied pan on %r value=%s", move.track, move.pan)
            continue

        # ---- all other move types : need StereoGain ----
        # Phase 4.12.1 audit fix : honor chain_position for StereoGain lookup
        sg = _find_existing_stereo_gain(track_el, chain_position=move.chain_position)
        if sg is None:
            if move.chain_position == "default":
                reason = (
                    f"track {move.track!r} has no StereoGain device. Phase 4.12 v1 "
                    f"is REUSE-only ; user must add a StereoGain to the track "
                    f"manually (or future Phase will add create paths via template)."
                )
            else:
                reason = (
                    f"track {move.track!r} has no StereoGain at chain_position="
                    f"{move.chain_position!r}. Phase 4.12 v1 is REUSE-only — "
                    f"Tier B cannot insert a new device at the requested position "
                    f"without a template."
                )
            moves_skipped.append((move_id, reason))
            warnings.append(f"{move_id} skipped : {reason}")
            continue

        if move.track not in tracks_with_sg_reused_this_run:
            stereo_gains_reused += 1
            tracks_with_sg_reused_this_run.add(move.track)

        # Dispatch by move_type
        ok: bool = False
        if move.move_type == "width":
            ok = _write_stereo_gain_width(sg, move.stereo_width)
        elif move.move_type == "mono":
            ok = _write_stereo_gain_mono(sg)
        elif move.move_type == "bass_mono":
            ok = _write_stereo_gain_bass_mono(sg, move.bass_mono_freq_hz)
        elif move.move_type == "balance":
            ok = _write_stereo_gain_balance(sg, move.balance)
        elif move.move_type == "ms_balance":
            ok = _write_stereo_gain_ms_balance(sg, move.mid_side_balance)
        elif move.move_type == "phase_flip":
            if move.phase_channel not in ("L", "R"):
                moves_skipped.append((
                    move_id,
                    f"phase_flip requires phase_channel ∈ {{L,R}} (got "
                    f"{move.phase_channel!r})",
                ))
                continue
            ok = _write_stereo_gain_phase_flip(sg, move.phase_channel)
        else:
            moves_skipped.append((
                move_id,
                f"Unknown move_type={move.move_type!r}",
            ))
            continue

        if not ok:
            moves_skipped.append((
                move_id,
                f"StereoGain XML missing required param for "
                f"move_type={move.move_type}",
            ))
            warnings.append(
                f"{move_id} : XML write failed (param structure missing)"
            )
            continue

        moves_applied.append(move_id)
        _LOGGER.info("Applied %s on %r", move_id, move.track)

    if dry_run:
        return SpatialConfiguratorReport(
            moves_applied=tuple(moves_applied),
            moves_skipped=tuple(moves_skipped),
            stereo_gains_reused=stereo_gains_reused,
            pans_written=pans_written,
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

    return SpatialConfiguratorReport(
        moves_applied=tuple(moves_applied),
        moves_skipped=tuple(moves_skipped),
        stereo_gains_reused=stereo_gains_reused,
        pans_written=pans_written,
        safety_guardian_status=safety_status,
        warnings=tuple(warnings),
        output_path=str(final_als),
    )


# ============================================================================
# Phase 4.12 Step 2 — Safety guardian
# ============================================================================


_SPATIAL_SAFETY_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "StereoGain": {
        "StereoWidth":         (0.0, 4.0),
        "MidSideBalance":      (0.0, 2.0),
        "Balance":             (-1.0, 1.0),
        "BassMonoFrequency":   (50.0, 500.0),
        "Gain":                (0.0, 2.0),  # native StereoGain Gain range
    },
}


def _run_safety_checks(als_path: str | Path) -> tuple[str, list[str]]:
    """Deterministic post-write safety checks for spatial XML.

    Phase 4.12 Step 2 checks :
    1. File exists, gunzippable, parses as XML
    2. NextPointeeId > max(Id)
    3. StereoGain params within audio-physics bounds
    4. Track Mixer.Pan within [-1, 1]
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
            next_pid_val = int(next_pid_el.get("Value", "0"))
            if next_pid_val <= max_id:
                issues.append(
                    f"NextPointeeId={next_pid_val} ≤ max Id ({max_id})"
                )
        except ValueError:
            pass

    # StereoGain ranges
    for sg in root.findall(".//StereoGain"):
        for param_name, (lo, hi) in _SPATIAL_SAFETY_RANGES["StereoGain"].items():
            manual = sg.find(f"{param_name}/Manual")
            if manual is None:
                continue
            try:
                val = float(manual.get("Value", "0"))
                if not (lo <= val <= hi):
                    issues.append(
                        f"StereoGain/{param_name}={val} out of [{lo}, {hi}]"
                    )
            except ValueError:
                pass

    # Mixer.Pan range
    for track in root.findall(".//AudioTrack") + root.findall(".//MidiTrack"):
        pan_manual = track.find(".//Mixer/Pan/Manual")
        if pan_manual is None:
            continue
        try:
            val = float(pan_manual.get("Value", "0"))
            if not (-1.0 <= val <= 1.0):
                issues.append(
                    f"Track Mixer.Pan={val} out of [-1, 1]"
                )
        except ValueError:
            pass

    return ("PASS" if not issues else "FAIL"), issues
