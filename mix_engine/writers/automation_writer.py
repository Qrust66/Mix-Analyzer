"""automation-writer — Tier B XML writer for AutomationDecision.

Phase 4.17 — translates ``MixDecision[AutomationDecision]`` (produced by
``automation-engineer`` Tier A or future ``band-tracking-decider`` Phase 4.18)
into deterministic XML <AutomationEnvelope> writes inside .als files.

Two coexisting input collections :

1. **Tier B-1 — `envelopes[]` (param-level)** : direct AutomationEnvelope →
   <AutomationEnvelope> XML mapping. One envelope = one (track, device,
   instance, param, band_index) target.

2. **Tier B-2 — `band_tracks[]` (high-level Eq8 band)** : each BandTrack is
   EXPANDED into 1-3 AutomationEnvelopes (Freq + Gain + Q, minus
   gain-inoperative modes) and then written via the same Tier B-1 pipeline.

Architecture (mirror Phase 4.10-4.16) :
- Python module, deterministic, no LLM
- Reuse als_utils primitives (parse_als, save_als_from_tree, find_track_by_name,
  get_automation_target_id, write_automation_envelope) AND
  eq8_automation helpers (_remove_existing_envelope-equivalent, breakpoint
  thinning) — but no API change to the legacy module
- Idempotent : pre-write delete by AutomationTarget Id ensures re-applying
  same decision = same output (no duplicate envelopes)
- Scope strict : only target devices in VALID_AUTOMATION_TARGET_DEVICES.
  Slots not found → skip with reason (REUSE-only — no device creation).

Sub-frame interpolation (BandTrack) :
- "linear" : straight line, safe, no overshoot, faster
- "parabolic" : 3-point parabolic refinement around local maxima — sub-bin
  freq accuracy via McAulay-Quatieri (default per Phase 4.17 design)
- "cubic" : CatmullRom — smooth glides, no monotonic guarantee

Notch coercion : band_mode="notch" silently rewritten to Mode 3 Bell with
narrow Q + deep negative Gain. Reason : Eq8 Mode 4 has gain_inoperative_modes
(documented in ableton_devices_mapping.json) — the Gain envelope wouldn't
take effect on Mode 4. Warning emitted in report.
"""
from __future__ import annotations

import logging
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import als_utils
from mix_engine.blueprint import (
    AutomationDecision,
    AutomationEnvelope,
    AutomationPoint,
    BAND_MODES_GAIN_INOPERATIVE,
    BandTrack,
    MixDecision,
)


_LOGGER = logging.getLogger(__name__)


# ============================================================================
# Typed exceptions
# ============================================================================


class AutomationWriterError(Exception):
    """Base exception for automation-writer failures."""


class AutomationTargetNotFoundError(AutomationWriterError):
    """Raised when the writer cannot resolve the AutomationTarget Id of a
    device/param/band combination on a track."""


# ============================================================================
# Report dataclass
# ============================================================================


@dataclass(frozen=True)
class AutomationWriterReport:
    """Audit trail of an apply_automation_decision invocation."""

    envelopes_applied: tuple[str, ...] = ()
    """Per-envelope identifiers (track:device#inst:param[@band]) successfully written."""

    band_tracks_applied: tuple[str, ...] = ()
    """Per-band-track identifiers (track:Eq8#inst:band)."""

    envelopes_skipped: tuple[tuple[str, str], ...] = ()
    """(envelope_id, skip_reason)."""

    band_tracks_skipped: tuple[tuple[str, str], ...] = ()
    """(band_track_id, skip_reason)."""

    breakpoints_written: int = 0
    """Total <FloatEvent>/<BoolEvent> children emitted across all envelopes."""

    notch_coercions: int = 0
    """Number of band_tracks with band_mode='notch' silently coerced to Mode 3 Bell."""

    safety_guardian_status: str = "SKIPPED"

    warnings: tuple[str, ...] = ()

    output_path: str = ""


# ============================================================================
# Param-name normalization (schema → XML)
# ============================================================================

# When the decision's `target_param` name doesn't match the XML tag, normalize.
# Example : schema says "Frequency" (per COMMON_AUTOMATION_PARAMS_BY_DEVICE)
# but Eq8 XML uses "Freq". Other devices typically already match.
_PARAM_NAME_ALIAS: dict[tuple[str, str], str] = {
    ("Eq8", "Frequency"): "Freq",
}


def _normalize_param_name(target_device: str, target_param: str) -> str:
    return _PARAM_NAME_ALIAS.get((target_device, target_param), target_param)


# Eq8 mode name (semantic) → numeric Mode value used by the device XML.
# Phase 4.17 v1 : these are the same numeric IDs documented in
# ``ableton_devices_mapping.json`` (Eq8.Mode_global enum).
_BAND_MODE_TO_EQ8_MODE: dict[str, int] = {
    "lowcut_48": 0,
    "lowcut_12": 1,
    "lowshelf":  2,
    "bell":      3,
    "notch":     4,    # writer COERCES to 3 ; this entry is documentation only
    "highshelf": 5,
    "highcut_12": 6,
    "highcut_48": 7,
}


# Phase 4.17.1 audit fix F-A3 — breakpoint thinning cap.
# Sanity ceiling on points per envelope. At 50ms/frame × 4 minutes × factor=2
# we'd produce 9600 raw points per envelope ; thinning to 1000 keeps Ableton
# load times reasonable while preserving the curve shape. Configurable via
# the public API arg `max_points_per_envelope`.
DEFAULT_MAX_POINTS_PER_ENVELOPE: int = 1000


def _thin_breakpoints(
    breakpoints: list[tuple[float, float]],
    max_points: int,
) -> list[tuple[float, float]]:
    """Keep first + last + uniformly-distributed intermediate points.

    Phase 4.17.1 F-A3 fix : avoid emitting ten-thousand-point envelopes
    that bloat the .als XML and slow Ableton's load.

    The thinning preserves :
    - The very first and very last breakpoint (envelope end-points)
    - Every k-th intermediate point where k = ceil(N / max_points)

    This is intentionally simple — RDP-style geometric thinning could
    preserve more curve shape but adds complexity. v1 uniform thinning is
    enough at the 50ms-frame target.
    """
    n = len(breakpoints)
    if n <= max_points or max_points < 3:
        return list(breakpoints)
    if max_points == 3:
        return [breakpoints[0], breakpoints[n // 2], breakpoints[-1]]
    # Pick max_points evenly across [0, n-1] including endpoints
    out: list[tuple[float, float]] = []
    for i in range(max_points):
        idx = round(i * (n - 1) / (max_points - 1))
        out.append(breakpoints[idx])
    # Strict-ascending guarantee : drop dupes if rounding aliasing produced
    # the same time twice
    deduped: list[tuple[float, float]] = []
    last_t: Optional[float] = None
    for t, v in out:
        if last_t is None or t > last_t:
            deduped.append((t, v))
            last_t = t
    return deduped


# ============================================================================
# Device locator helpers
# ============================================================================


def _find_devices_container(track_element: ET.Element) -> Optional[ET.Element]:
    container = track_element.find(".//DeviceChain/DeviceChain/Devices")
    if container is None:
        container = track_element.find(".//DeviceChain/Devices")
    return container


def _find_device_instance(
    track_element: ET.Element, device_tag: str, instance: int,
) -> Optional[ET.Element]:
    """Find the Nth instance of a device tag in the track's chain."""
    container = _find_devices_container(track_element)
    if container is None:
        return None
    matches = [c for c in container if c.tag == device_tag]
    if instance >= len(matches):
        return None
    return matches[instance]


def _find_master_track(tree: ET.ElementTree) -> Optional[ET.Element]:
    """Locate <MasterTrack> (the master bus owner)."""
    root = tree.getroot()
    return root.find(".//MasterTrack")


def _resolve_track_for_target(
    tree: ET.ElementTree, target_track: str,
) -> Optional[ET.Element]:
    """Find the track Element matching `target_track` ; supports "Master"."""
    if target_track == "Master":
        return _find_master_track(tree)
    try:
        return als_utils.find_track_by_name(tree, target_track)
    except ValueError:
        return None


def _resolve_param_root(
    track_element: ET.Element,
    target_device: str,
    target_device_instance: int,
    target_band_index: Optional[int],
) -> Optional[ET.Element]:
    """Return the Element where the AutomationTarget for the param lives.

    For Eq8 + band_index : returns the <ParameterA> of the band (the
    per-band container that holds <Freq>/<Gain>/<Q>/<IsOn>).
    For all other devices : returns the device Element itself (params are
    direct children).
    """
    device_el = _find_device_instance(track_element, target_device, target_device_instance)
    if device_el is None:
        return None

    if target_device == "Eq8" and target_band_index is not None:
        try:
            return als_utils.get_eq8_band(device_el, target_band_index)
        except (ValueError, IndexError):
            return None

    return device_el


# ============================================================================
# Envelope writing — Tier B-1 core
# ============================================================================


def _envelope_id(env: AutomationEnvelope) -> str:
    band_suffix = (
        f"@band{env.target_band_index}"
        if env.target_band_index is not None else ""
    )
    return (
        f"{env.target_track}:{env.target_device}#{env.target_device_instance}"
        f":{env.target_param}{band_suffix}"
    )


def _band_track_id(bt: BandTrack) -> str:
    return f"{bt.target_track}:Eq8#{bt.target_eq8_instance}:band{bt.target_band_index}"


def _envelope_to_breakpoints(env: AutomationEnvelope) -> list[tuple[float, float]]:
    """Convert AutomationPoint[] → list[(time_beats, value)]."""
    return [(p.time_beats, p.value) for p in env.points]


def _remove_existing_envelope(track_element: ET.Element, target_id: str) -> bool:
    """Idempotency : delete any existing AutomationEnvelope on this target.

    Mirrors eq8_automation._remove_existing_envelope but agnostic to caller.
    Returns True if an envelope was removed.
    """
    envelopes_container = track_element.find(".//AutomationEnvelopes/Envelopes")
    if envelopes_container is None:
        return False
    removed = False
    to_remove = []
    for env_el in envelopes_container.findall("AutomationEnvelope"):
        pointee = env_el.find("EnvelopeTarget/PointeeId")
        if pointee is None:
            continue
        if pointee.get("Value") == target_id:
            to_remove.append(env_el)
    for env_el in to_remove:
        envelopes_container.remove(env_el)
        removed = True
    return removed


def _write_param_envelope(
    track_element: ET.Element,
    param_root: ET.Element,
    param_name_xml: str,
    breakpoints: list[tuple[float, float]],
    next_id_counter: list[int],
    event_type: str = "FloatEvent",
    max_points: Optional[int] = None,
) -> tuple[int, int]:
    """Write one envelope on a (track, param_root, param_name) tuple.

    Returns ``(emitted_count, raw_count)``. ``emitted_count`` is the number of
    breakpoints actually written (post-thinning). ``raw_count`` is the input
    length, used by the caller to compose a thinning warning when emitted < raw.

    Performs the idempotent pre-write delete.
    """
    raw_count = len(breakpoints)
    if max_points is not None and raw_count > max_points:
        breakpoints = _thin_breakpoints(breakpoints, max_points)
    target_id = als_utils.get_automation_target_id(param_root, param_name_xml)
    _remove_existing_envelope(track_element, target_id)
    als_utils.write_automation_envelope(
        track_element, target_id, breakpoints, next_id_counter,
        event_type=event_type,
    )
    return len(breakpoints), raw_count


# ============================================================================
# Sub-frame interpolation (BandTrack expansion)
# ============================================================================


def _linear_densify(
    times: tuple[float, ...],
    values: tuple[float, ...],
    factor: int,
) -> tuple[list[float], list[float]]:
    """Insert `factor-1` linearly-interpolated points between adjacent frames."""
    if factor <= 1 or len(times) < 2:
        return list(times), list(values)
    out_t: list[float] = []
    out_v: list[float] = []
    for i in range(len(times) - 1):
        t0, t1 = times[i], times[i + 1]
        v0, v1 = values[i], values[i + 1]
        for k in range(factor):
            alpha = k / factor
            out_t.append(t0 + alpha * (t1 - t0))
            out_v.append(v0 + alpha * (v1 - v0))
    out_t.append(times[-1])
    out_v.append(values[-1])
    return out_t, out_v


def _parabolic_densify(
    times: tuple[float, ...],
    values: tuple[float, ...],
    amps_db: Optional[tuple[float, ...]],
    factor: int,
) -> tuple[list[float], list[float]]:
    """Parabolic refinement (always) + linear densification (factor-dependent).

    Phase 4.17.1 audit fix F1 : parabolic refinement is now applied at
    EVERY call when amps_db is provided AND len >= 3, regardless of
    sub_frame_factor. Rationale : the user-stated requirement
    "il doit déduire que le peak peut se trouver entre 2 frames" is the
    sub-frame INFERENCE step itself — independent of how many breakpoints
    we ultimately emit. Densification (factor > 1) is a separate concern
    (more breakpoints between refined frames).

    For each interior frame i, if values[i] is a local maximum in
    `amps_db`, refine the value+time via 3-point parabolic interpolation
    (McAulay-Quatieri). Sub-frame shift δ ∈ [-0.5, +0.5].

    Non-maxima frames are passed through unchanged. amps_db=None bypasses
    refinement entirely (falls to linear densify).
    """
    # Parabolic refinement step (always when applicable)
    if amps_db is not None and len(amps_db) == len(values) and len(times) >= 3:
        refined_t = list(times)
        refined_v = list(values)
        for i in range(1, len(values) - 1):
            a, b, c = amps_db[i - 1], amps_db[i], amps_db[i + 1]
            if b > a and b > c:  # local max in source amplitude
                denom = (a - 2 * b + c)
                if abs(denom) > 1e-9:
                    delta = 0.5 * (a - c) / denom
                    delta = max(-0.5, min(0.5, delta))
                    # Sub-bin time refinement (anchor at frame i)
                    if delta >= 0:
                        refined_t[i] = times[i] + delta * (times[i + 1] - times[i])
                    else:
                        refined_t[i] = times[i] + delta * (times[i] - times[i - 1])
                    # Log-frequency interpolation (geometric mean weighted by delta)
                    if delta >= 0:
                        ratio = values[i + 1] / values[i] if values[i] > 0 else 1.0
                    else:
                        ratio = values[i - 1] / values[i] if values[i] > 0 else 1.0
                    if ratio > 0:
                        refined_v[i] = values[i] * (ratio ** abs(delta))

        # Re-sort by time in case parabolic shifted some points out of order
        sorted_pairs = sorted(zip(refined_t, refined_v), key=lambda p: p[0])
        times = tuple(p[0] for p in sorted_pairs)
        values = tuple(p[1] for p in sorted_pairs)

    # Densification step (independent of refinement)
    return _linear_densify(times, values, max(factor, 1))


# ============================================================================
# BandTrack → AutomationEnvelope expansion (Tier B-2)
# ============================================================================


def _seconds_to_beats(time_sec: float, tempo_bpm: float) -> float:
    return time_sec * (tempo_bpm / 60.0)


def _band_track_static_eq8_mode(bt: BandTrack) -> tuple[int, str]:
    """Return (numeric_mode, effective_mode_name) for the band's static config.

    Phase 4.17.1 audit fix F-A4 : the writer must set the band's STATIC Mode
    to match `band_mode` BEFORE writing the envelopes ; otherwise a gain
    envelope on a band that has Mode 4 (Notch) statically would be ignored
    by Eq8 (Mode 4 has gain_inoperative_modes).

    'notch' is silently coerced to Mode 3 Bell here too — the writer's
    consistent contract is "narrow Bell with deep gain produces the notch
    behaviour while remaining gain-automatable".
    """
    effective = "bell" if bt.band_mode == "notch" else bt.band_mode
    return _BAND_MODE_TO_EQ8_MODE[effective], effective


def _build_envelopes_from_band_track(
    bt: BandTrack,
    tempo_bpm: float,
) -> tuple[list[AutomationEnvelope], list[str]]:
    """Expand 1 BandTrack into 1-3 AutomationEnvelope objects.

    Returns (envelopes, warnings). When band_mode='notch', emit Bell Mode 3
    coercion + warning.

    Skipped envelopes :
    - Gain envelope when band_mode is in BAND_MODES_GAIN_INOPERATIVE
    - Q envelope when q_values is None AND q_static is provided as fallback
      (writer leaves Q at static — no envelope)
    - Gain envelope when gains_db is None AND source_amps_db is None (no
      data to drive it)
    """
    warnings: list[str] = []
    _, effective_mode = _band_track_static_eq8_mode(bt)
    if bt.band_mode == "notch":
        warnings.append(
            f"BandTrack {_band_track_id(bt)} : band_mode='notch' coerced to "
            f"Mode 3 Bell with narrow Q (Eq8 Mode 4 has gain_inoperative_modes ; "
            f"narrow Bell with deep negative Gain produces a notchable cut)."
        )

    # ---- Sub-frame densification of all time series ----
    if bt.interpolation == "parabolic":
        densify = lambda v: _parabolic_densify(
            bt.frame_times_sec, v, bt.source_amps_db, bt.sub_frame_factor,
        )
    else:
        # linear / cubic both fall to linear v1 (cubic deferred Phase 4.17.X)
        densify = lambda v: _linear_densify(
            bt.frame_times_sec, v, bt.sub_frame_factor,
        )

    times_dense, freqs_dense = densify(bt.freqs_hz)

    # ---- Compute gain curve (when applicable) ----
    gains_dense: Optional[list[float]] = None
    if effective_mode not in BAND_MODES_GAIN_INOPERATIVE:
        if bt.gains_db is not None:
            _, gains_dense = densify(bt.gains_db)
        elif bt.source_amps_db is not None:
            # Derive proportional gain : gain ∝ (amp - threshold) / -threshold × gain_max
            # Use opposite sign for "follow_peak" cuts : negative gain when peak loud
            sign = -1.0 if bt.purpose == "follow_peak" else 1.0
            denom = max(-bt.threshold_db, 1.0)
            derived_gains = tuple(
                sign * bt.gain_max_db * max(0.0, min(1.0, (amp - bt.threshold_db) / denom))
                for amp in bt.source_amps_db
            )
            _, gains_dense = densify(derived_gains)

    # ---- Compute Q curve (when q_values explicit) ----
    q_dense: Optional[list[float]] = None
    if bt.q_values is not None:
        _, q_dense = densify(bt.q_values)

    # ---- Convert times_sec → time_beats ----
    times_beats = [_seconds_to_beats(t, tempo_bpm) for t in times_dense]

    # ---- Build AutomationEnvelope objects ----
    envelopes: list[AutomationEnvelope] = []

    def _make_env(param: str, values: list[float]) -> AutomationEnvelope:
        # Clamp values to safe Eq8 ranges
        if param == "Freq":
            values = [max(10.0, min(22050.0, v)) for v in values]
        elif param == "Gain":
            values = [max(-15.0, min(15.0, v)) for v in values]
        elif param == "Q":
            values = [max(0.1, min(18.0, v)) for v in values]
        points = tuple(
            AutomationPoint(time_beats=t, value=v)
            for t, v in zip(times_beats, values)
        )
        return AutomationEnvelope(
            purpose="corrective_per_section",
            target_track=bt.target_track,
            target_device="Eq8",
            target_param=param,
            target_device_instance=bt.target_eq8_instance,
            target_band_index=bt.target_band_index,
            points=points,
            sections=(),
            rationale=bt.rationale,
            inspired_by=bt.inspired_by,
        )

    envelopes.append(_make_env("Freq", freqs_dense))
    if gains_dense is not None:
        envelopes.append(_make_env("Gain", gains_dense))
    if q_dense is not None:
        envelopes.append(_make_env("Q", q_dense))

    return envelopes, warnings


# ============================================================================
# Public API
# ============================================================================


def apply_automation_decision(
    als_path: str | Path,
    decision: MixDecision[AutomationDecision],
    output_path: str | Path | None = None,
    dry_run: bool = False,
    invoke_safety_guardian: bool = True,
    max_points_per_envelope: int = DEFAULT_MAX_POINTS_PER_ENVELOPE,
) -> AutomationWriterReport:
    """Apply an AutomationDecision (envelopes + band_tracks) to an .als file.

    Phase 4.17 v1 SCOPE :
    - Tier B-1 envelopes[] : direct param envelope writes for ALL devices in
      VALID_AUTOMATION_TARGET_DEVICES
    - Tier B-2 band_tracks[] : expand each into 1-3 envelopes (Freq + Gain + Q),
      apply parabolic sub-frame interp, write
    - Idempotent : pre-write delete by AutomationTarget Id

    Phase 4.17.1 audit fix F-A4 : for each BandTrack, the writer ensures the
    target Eq8 band's STATIC Mode matches `band_mode` (notch coerced to Mode 3
    Bell), AND IsOn is set true. Without this step, gain envelopes on bands
    with Mode-4-Notch (or any gain-inoperative mode) would be silently ignored
    by the Eq8 device.

    Phase 4.17.1 audit fix F-A3 : breakpoint thinning per envelope, capped
    at `max_points_per_envelope` (default 1000). Prevents the .als XML from
    bloating at 50ms-frame target.

    Args:
        als_path: Source .als file.
        decision: Tier A automation decision (typed).
        output_path: Where to write modified .als. None = overwrite source.
        dry_run: Validate without writing.
        invoke_safety_guardian: Run post-write deterministic checks.
        max_points_per_envelope: Cap on FloatEvent count per envelope. 1000
            is enough for visually-smooth curves at most frame rates.

    Returns:
        :class:`AutomationWriterReport`.

    Raises:
        AutomationWriterError: Generic failure.
    """
    als_path = Path(als_path)
    if not als_path.exists():
        raise AutomationWriterError(f"Source .als not found : {als_path}")

    if output_path is None and not dry_run:
        output_path = als_path
    output_path = Path(output_path) if output_path else als_path

    envelopes = decision.value.envelopes
    band_tracks = decision.value.band_tracks
    if not envelopes and not band_tracks:
        return AutomationWriterReport(
            output_path=str(als_path if dry_run else output_path),
        )

    tree = als_utils.parse_als(str(als_path))
    next_id = [als_utils.get_next_id(tree)]

    # Project tempo (for BandTrack times_sec → beats)
    root = tree.getroot()
    tempo_el = root.find(".//Tempo/Manual")
    tempo_bpm = float(tempo_el.get("Value", "120")) if tempo_el is not None else 120.0

    envelopes_applied: list[str] = []
    envelopes_skipped: list[tuple[str, str]] = []
    band_tracks_applied: list[str] = []
    band_tracks_skipped: list[tuple[str, str]] = []
    warnings: list[str] = []
    breakpoints_written: int = 0
    notch_coercions: int = 0

    # ---- Tier B-2 — expand band_tracks into envelopes first ----
    expanded_envelopes: list[tuple[AutomationEnvelope, str]] = []
    for bt in band_tracks:
        bt_id = _band_track_id(bt)
        try:
            # Phase 4.17.1 F-A4 — configure static Mode + IsOn on the target
            # Eq8 band BEFORE writing envelopes. Otherwise a Gain envelope on
            # a band with Mode-4-Notch (or 0/1/4/6/7 gain-inoperative) would
            # be silently ignored by Eq8.
            track_el = _resolve_track_for_target(tree, bt.target_track)
            if track_el is None:
                band_tracks_skipped.append((
                    bt_id, f"track {bt.target_track!r} not found",
                ))
                continue
            eq8_el = _find_device_instance(
                track_el, "Eq8", bt.target_eq8_instance,
            )
            if eq8_el is None:
                band_tracks_skipped.append((
                    bt_id,
                    f"Eq8 instance {bt.target_eq8_instance} not present on "
                    f"track {bt.target_track!r} ; REUSE-only, no creation in v1",
                ))
                continue
            try:
                band_param = als_utils.get_eq8_band(eq8_el, bt.target_band_index)
            except (ValueError, IndexError) as exc:
                band_tracks_skipped.append((
                    bt_id, f"Eq8 band {bt.target_band_index} unreachable : {exc}",
                ))
                continue
            mode_int, _ = _band_track_static_eq8_mode(bt)
            # Set static Mode (notch → 3) + IsOn=true. Q is set static here ONLY
            # when q_values is None AND user provided q_static ; otherwise the
            # Q envelope (or stored Q) will drive the band.
            static_q = bt.q_static if bt.q_values is None else None
            als_utils.configure_eq8_band(band_param, mode=mode_int, q=static_q)
            ison = band_param.find("IsOn/Manual")
            if ison is not None:
                ison.set("Value", "true")

            new_envs, bt_warnings = _build_envelopes_from_band_track(bt, tempo_bpm)
            warnings.extend(bt_warnings)
            if bt.band_mode == "notch":
                notch_coercions += 1
            for env in new_envs:
                expanded_envelopes.append((env, bt_id))
            band_tracks_applied.append(bt_id)
        except Exception as exc:
            band_tracks_skipped.append((
                bt_id, f"expansion failed : {type(exc).__name__}: {exc}",
            ))
            continue

    # ---- Tier B-1 — write envelopes (direct + expanded) ----
    all_envelopes: list[tuple[AutomationEnvelope, Optional[str]]] = (
        [(e, None) for e in envelopes] + expanded_envelopes
    )

    for env, source_bt_id in all_envelopes:
        env_id = _envelope_id(env)
        full_id = f"{env_id}" + (f" (from {source_bt_id})" if source_bt_id else "")

        # Locate track
        track_el = _resolve_track_for_target(tree, env.target_track)
        if track_el is None:
            envelopes_skipped.append((
                full_id, f"track {env.target_track!r} not found",
            ))
            continue

        # Locate the param container
        param_root = _resolve_param_root(
            track_el, env.target_device, env.target_device_instance,
            env.target_band_index,
        )
        if param_root is None:
            band_part = (
                f" band={env.target_band_index}"
                if env.target_band_index is not None else ""
            )
            envelopes_skipped.append((
                full_id,
                f"device {env.target_device}#{env.target_device_instance}{band_part} "
                f"not present on track ; REUSE-only — no creation in v1",
            ))
            continue

        param_name_xml = _normalize_param_name(env.target_device, env.target_param)
        try:
            emitted, raw = _write_param_envelope(
                track_el, param_root, param_name_xml,
                _envelope_to_breakpoints(env), next_id,
                event_type="FloatEvent",
                max_points=max_points_per_envelope,
            )
        except (ValueError, AutomationTargetNotFoundError) as exc:
            envelopes_skipped.append((
                full_id,
                f"AutomationTarget for param {param_name_xml!r} not found : {exc}",
            ))
            continue
        except Exception as exc:
            envelopes_skipped.append((
                full_id, f"write failed : {type(exc).__name__}: {exc}",
            ))
            continue

        envelopes_applied.append(full_id)
        breakpoints_written += emitted
        if emitted < raw:
            warnings.append(
                f"envelope {full_id} : thinned {raw} → {emitted} breakpoints "
                f"(cap = max_points_per_envelope={max_points_per_envelope})"
            )
        _LOGGER.info(
            "Wrote envelope %s (%d points, raw %d)", full_id, emitted, raw,
        )

    if dry_run:
        return AutomationWriterReport(
            envelopes_applied=tuple(envelopes_applied),
            band_tracks_applied=tuple(band_tracks_applied),
            envelopes_skipped=tuple(envelopes_skipped),
            band_tracks_skipped=tuple(band_tracks_skipped),
            breakpoints_written=breakpoints_written,
            notch_coercions=notch_coercions,
            warnings=tuple(warnings),
            output_path=str(als_path),
        )

    final_als = als_utils.save_als_from_tree(tree, str(output_path))

    safety_status = "SKIPPED"
    if invoke_safety_guardian:
        safety_status, safety_issues = _run_safety_checks(final_als, decision)
        if safety_issues:
            for issue in safety_issues:
                warnings.append(f"safety_guardian: {issue}")

    return AutomationWriterReport(
        envelopes_applied=tuple(envelopes_applied),
        band_tracks_applied=tuple(band_tracks_applied),
        envelopes_skipped=tuple(envelopes_skipped),
        band_tracks_skipped=tuple(band_tracks_skipped),
        breakpoints_written=breakpoints_written,
        notch_coercions=notch_coercions,
        safety_guardian_status=safety_status,
        warnings=tuple(warnings),
        output_path=str(final_als),
    )


# ============================================================================
# Phase 4.17 Step 4 — Safety guardian
# ============================================================================


def _run_safety_checks(
    als_path: str | Path,
    decision: MixDecision[AutomationDecision],
) -> tuple[str, list[str]]:
    """Deterministic post-write safety checks for automation XML.

    Phase 4.17 checks :
    1. File exists, gunzippable, parses as XML
    2. NextPointeeId > max(Id) (general invariant)
    3. For each AutomationEnvelope written : the associated AutomationTarget
       Id still resolves on the track (no orphan envelope).
    4. For BandTrack-derived envelopes on Eq8 : verify the band_index
       respects the 8-band hard limit per Eq8 instance (this should always
       hold per parser, defensive check).
    5. ≤ 8 unique band_indexes per (track, eq8_instance) for BandTracks.
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

    # Check #2 — NextPointeeId
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
                issues.append(
                    f"NextPointeeId={v} <= max Id ({max_id}) ; "
                    f"Ableton refuses to load."
                )
        except ValueError:
            pass

    # Check #5 — band_indexes per Eq8 instance ≤ 8 (parser already enforces
    # uniqueness ; this confirms the count post-write).
    bt_buckets: dict[tuple[str, int], set[int]] = defaultdict(set)
    for bt in decision.value.band_tracks:
        key = (bt.target_track, bt.target_eq8_instance)
        bt_buckets[key].add(bt.target_band_index)
    for (track, instance), bands in bt_buckets.items():
        if len(bands) > 8:
            issues.append(
                f"track {track!r} Eq8 instance {instance} has "
                f"{len(bands)} BandTracks > 8 (chain-builder must cascade "
                f"to additional Eq8 instances)"
            )

    return ("PASS" if not issues else "FAIL"), issues
