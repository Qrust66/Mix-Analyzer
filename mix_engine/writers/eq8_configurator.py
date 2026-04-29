"""eq8-configurator — Tier B XML writer for EQ corrective decisions.

Phase 4.10 — translates a ``MixDecision[EQCorrectiveDecision]`` (produced
by ``eq-corrective-decider`` Tier A) into deterministic XML patches
applied to an .als file.

This is a Python module, not an LLM subagent. Rationale (cf.
docs/MIX_ENGINE_ROADMAP.md Phase 4.10 design Pass 1) :
- Determinism : same input → same XML output (pytest assertable)
- Safety : no LLM hallucination of XML
- Idempotency : detect existing state, no-op or update
- Type safety : EQCorrectiveDecision in, EqConfiguratorReport out

Reuses primitives from ``als_utils`` (decompress, parse, find_track_by_name,
find_or_create_eq8, configure_eq8_band, write_automation_envelope, etc.).

Phase 4.10 Step 1 (this commit) :
- Module skeleton + Translation table (band_type → Eq8 Mode 0-7)
- EqConfiguratorReport dataclass
- Typed exceptions (EqConfiguratorError + subclasses)
- ``apply_eq_corrective_decision`` basic API (no chain_position routing yet,
  no envelopes yet, no M/S yet — those land in Step 2/3/4)

Phase 4.10 Step 2-5 incremental landings (cf. tasks 12-15) :
- Step 2 : chain_position (find_or_create_eq8_at_position parallel)
- Step 3 : envelope writing (gain/freq/Q automation)
- Step 4 : processing_mode (M/S) + idempotence
- Step 5 : safety-guardian integration
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import als_utils
from mix_engine.blueprint import (
    EQBandCorrection,
    EQCorrectiveDecision,
    MixDecision,
)


_LOGGER = logging.getLogger(__name__)


# ============================================================================
# Translation table : EQBandCorrection.band_type + slope_db_per_oct → Eq8 Mode
# ============================================================================
#
# Eq8 Mode integer encoding (Ableton native) :
#   0 = 48 dB Low Cut    → highpass + slope=48
#   1 = 12 dB Low Cut    → highpass + slope=12
#   2 = Low Shelf        → low_shelf
#   3 = Bell             → bell
#   4 = Notch            → notch
#   5 = High Shelf       → high_shelf
#   6 = 12 dB High Cut   → lowpass + slope=12
#   7 = 48 dB High Cut   → lowpass + slope=48
#
# Source : eq-corrective-decider.md Section 5 "Eq8 device mapping".

_BAND_TYPE_TO_MODE: dict[tuple[str, Optional[float]], int] = {
    ("bell", None): 3,
    ("notch", None): 4,
    ("low_shelf", None): 2,
    ("high_shelf", None): 5,
    ("highpass", 48.0): 0,
    ("highpass", 12.0): 1,
    ("lowpass", 12.0): 6,
    ("lowpass", 48.0): 7,
}


def _resolve_eq8_mode(band: EQBandCorrection) -> int:
    """Translate semantic (band_type, slope) → Eq8 Mode 0-7.

    Bell/notch/shelves : slope_db_per_oct must be None.
    Highpass/lowpass : slope_db_per_oct must be 12 or 48.

    Raises EqConfiguratorError if combination is invalid (parser should
    have caught this in Tier A but we double-check at write time).
    """
    if band.band_type in {"bell", "notch", "low_shelf", "high_shelf"}:
        if band.slope_db_per_oct is not None:
            raise EqConfiguratorError(
                f"band_type={band.band_type!r} must NOT have "
                f"slope_db_per_oct (got {band.slope_db_per_oct}). "
                f"Slope only applies to highpass/lowpass."
            )
        key = (band.band_type, None)
    elif band.band_type in {"highpass", "lowpass"}:
        if band.slope_db_per_oct not in (12.0, 48.0):
            raise EqConfiguratorError(
                f"band_type={band.band_type!r} requires slope_db_per_oct "
                f"in {{12.0, 48.0}}, got {band.slope_db_per_oct}."
            )
        key = (band.band_type, float(band.slope_db_per_oct))
    else:
        raise EqConfiguratorError(
            f"Unknown band_type={band.band_type!r} (cannot translate to Eq8 Mode)."
        )

    if key not in _BAND_TYPE_TO_MODE:
        raise EqConfiguratorError(
            f"No Eq8 Mode mapping for {key}. Bug : translation table incomplete."
        )
    return _BAND_TYPE_TO_MODE[key]


# ============================================================================
# Typed exceptions
# ============================================================================


class EqConfiguratorError(Exception):
    """Base exception for eq8-configurator failures.

    Specific subclasses for actionable failure modes — Tier B caller
    can catch the parent to handle generic failures or specific subclasses
    for targeted recovery.
    """


# ChainPositionUnresolvedError is defined in als_utils (subclass of ValueError)
# so existing ``except ValueError`` blocks catch it. Re-exported below for
# convenience — callers can use either als_utils.ChainPositionUnresolvedError
# or mix_engine.writers.ChainPositionUnresolvedError.
from als_utils import ChainPositionUnresolvedError  # noqa: E402, F401


# ============================================================================
# Report dataclass
# ============================================================================


@dataclass(frozen=True)
class EqConfiguratorReport:
    """Audit trail of an apply_eq_corrective_decision invocation.

    Every applied / skipped operation is traceable back to the originating
    EQBandCorrection. Fail-fast errors raise EqConfiguratorError (not
    captured here — the .als state is left untouched if any band fails
    Phase 4.10 Step 1 ; partial-apply with rollback is a Step 5 concern).
    """

    bands_applied: tuple[str, ...] = ()
    """Per-band identifiers (track:band_type@center_hz) successfully written."""

    bands_skipped: tuple[tuple[str, str], ...] = ()
    """(band_id, skip_reason) for bands that were no-op (idempotency, etc.)."""

    eq8_created: int = 0
    """Number of new Eq8 device instances inserted into device chains."""

    eq8_reused: int = 0
    """Number of existing Eq8 instances reused (band added to existing slot)."""

    automations_written: int = 0
    """Number of <AutomationEnvelope> blocks written (Phase 4.10 Step 3+)."""

    safety_guardian_status: str = "SKIPPED"
    """'PASS' | 'FAIL' | 'SKIPPED' (Phase 4.10 Step 5+)."""

    warnings: tuple[str, ...] = ()
    """Non-fatal observations (e.g., 'rationale references PDF section X
    not found in current PDF version')."""

    output_path: str = ""
    """Final .als path written (or input path if dry_run=True)."""


# ============================================================================
# Public API
# ============================================================================


def apply_eq_corrective_decision(
    als_path: str | Path,
    decision: MixDecision[EQCorrectiveDecision],
    output_path: str | Path | None = None,
    dry_run: bool = False,
) -> EqConfiguratorReport:
    """Apply an EQ corrective decision to an .als file.

    Phase 4.10 Step 1 : basic apply path. Each ``EQBandCorrection`` is
    translated to an Eq8 band write via :func:`als_utils.find_or_create_eq8`
    + :func:`als_utils.configure_eq8_band`. The first available band slot
    on the (existing or newly-created) Eq8 receives the configuration.

    LIMITATIONS Phase 4.10 Step 1 (addressed in subsequent steps) :
    - chain_position semantics ignored (always uses first Eq8 found, or
      appends new Eq8 to chain end). Step 2 adds chain_position routing.
    - processing_mode (M/S) ignored (Eq8.Mode_global stays at default).
      Step 4 adds M/S support.
    - Envelopes (gain/freq/Q) ignored. Step 3 wires write_automation_envelope.
    - No idempotency check : re-running adds new bands to next slots.
      Step 4 adds detection of identical existing bands.
    - No safety-guardian invocation. Step 5 adds post-write verification.

    Args:
        als_path: Path to source .als file.
        decision: Tier A EQ corrective decision (typed).
        output_path: Where to write the modified .als. If None, overwrites
            ``als_path``. If ``dry_run=True``, no file is written and
            ``output_path`` is ignored.
        dry_run: If True, validates the decision against the .als state
            without writing. Returns a report describing what *would* be
            applied. The .als is not modified.

    Returns:
        :class:`EqConfiguratorReport` summarizing the operation.

    Raises:
        EqConfiguratorError: Translation failure (invalid band_type/slope
            combo, etc.).
        als_utils.TrackNotFoundError: A band targets a track not present
            in the .als.
        als_utils.EQ8SlotFullError: An Eq8 instance has all 8 bands used
            and no slot is available.
        ValueError: Track structure unexpected (no DeviceChain/Devices).
    """
    als_path = Path(als_path)
    if not als_path.exists():
        raise EqConfiguratorError(f"Source .als not found : {als_path}")

    if output_path is None and not dry_run:
        output_path = als_path
    output_path = Path(output_path) if output_path else als_path

    bands = decision.value.bands
    if not bands:
        # No-op decision — nothing to apply but still return a valid report.
        _LOGGER.info("apply_eq_corrective_decision : empty decision (bands=()), no-op")
        return EqConfiguratorReport(
            output_path=str(als_path if dry_run else output_path),
        )

    # Parse the .als (gunzip + ET.parse). save_als_from_tree() in als_utils
    # writes directly back to .als (gzipped) when we save — no intermediate
    # XML file roundtrip needed.
    tree = als_utils.parse_als(str(als_path))

    bands_applied: list[str] = []
    bands_skipped: list[tuple[str, str]] = []
    warnings: list[str] = []

    # Pre-scan : record which tracks have an Eq8 BEFORE this run.
    # Used to partition unique-tracks-with-bands into created vs reused.
    tracks_with_eq8_before_run: set[str] = set()
    for band in bands:
        track_el = als_utils.find_track_by_name(tree, band.track)
        if track_el.find(".//Eq8") is not None:
            tracks_with_eq8_before_run.add(band.track)

    unique_tracks_in_decision = {band.track for band in bands}
    eq8_created = sum(
        1 for t in unique_tracks_in_decision
        if t not in tracks_with_eq8_before_run
    )
    eq8_reused = sum(
        1 for t in unique_tracks_in_decision
        if t in tracks_with_eq8_before_run
    )

    for band in bands:
        band_id = f"{band.track}:{band.band_type}@{band.center_hz}Hz"
        try:
            mode = _resolve_eq8_mode(band)
            track_el = als_utils.find_track_by_name(tree, band.track)

            had_eq8_before = band.track in tracks_with_eq8_before_run

            # Phase 4.10 Step 2 : route through chain_position-aware function
            # when band.chain_position != "default". 'default' falls back to
            # legacy first-Eq8-or-append behavior (backward-compat with Step 1).
            eq8 = als_utils.find_or_create_eq8_at_position(
                track_el, tree,
                target_chain_position=band.chain_position,
                user_name="eq-configurator" if not had_eq8_before else None,
            )
            # Mark the track as having an Eq8 now (so subsequent bands on the
            # same track reuse it instead of attempting another create).
            tracks_with_eq8_before_run.add(band.track)

            # Find first available band slot (Phase 4.10 Step 1 : naive — uses
            # first inactive band). Step 4 adds idempotency check.
            slot_index = _find_available_band_slot(eq8)
            band_param = als_utils.get_eq8_band(eq8, slot_index)

            als_utils.configure_eq8_band(
                band_param,
                mode=mode,
                freq=band.center_hz,
                gain=band.gain_db if band.intent != "filter" else None,
                q=band.q,
            )
            # Activate the band (IsOn = true).
            is_on_manual = band_param.find("IsOn/Manual")
            if is_on_manual is not None:
                is_on_manual.set("Value", "true")

            bands_applied.append(band_id)
            _LOGGER.info(
                "Applied %s on %r slot=%d Mode=%d", band_id, band.track,
                slot_index, mode,
            )

        except EqConfiguratorError:
            raise
        except ValueError:
            # als_utils.find_track_by_name raises ValueError for missing tracks ;
            # propagate verbatim (Tier A should have caught this).
            raise
        except Exception as exc:
            # Unexpected — wrap in EqConfiguratorError with band context.
            raise EqConfiguratorError(
                f"Failed to apply {band_id} : {type(exc).__name__}: {exc}"
            ) from exc

    if dry_run:
        _LOGGER.info("dry_run=True : skipping save")
        return EqConfiguratorReport(
            bands_applied=tuple(bands_applied),
            bands_skipped=tuple(bands_skipped),
            eq8_created=eq8_created,
            eq8_reused=eq8_reused,
            warnings=tuple(warnings),
            output_path=str(als_path),
        )

    # save_als_from_tree() writes directly to .als (gzipped, with bumped
    # NextPointeeId + Ableton-native XML declaration).
    final_als = als_utils.save_als_from_tree(tree, str(output_path))

    return EqConfiguratorReport(
        bands_applied=tuple(bands_applied),
        bands_skipped=tuple(bands_skipped),
        eq8_created=eq8_created,
        eq8_reused=eq8_reused,
        warnings=tuple(warnings),
        output_path=str(final_als),
    )


# ============================================================================
# Internal helpers
# ============================================================================


_EQ8_BANDS_PER_INSTANCE: int = 8


def _find_available_band_slot(eq8_element: ET.Element) -> int:
    """Find the first inactive (IsOn=false) band slot in an Eq8.

    Eq8 has 8 bands (indices 0-7). A "slot" is available if its IsOn/Manual
    is "false" or unset. Phase 4.10 Step 1 uses the first available slot ;
    Step 4 adds idempotency (detect identical-params band → reuse slot).

    Raises EQ8SlotFullError if all 8 are active.
    """
    for i in range(_EQ8_BANDS_PER_INSTANCE):
        try:
            band = als_utils.get_eq8_band(eq8_element, i)
        except (ValueError, IndexError):
            continue
        is_on = band.find("IsOn/Manual")
        if is_on is None:
            return i
        if is_on.get("Value", "false") == "false":
            return i
    raise als_utils.EQ8SlotFullError(
        f"All {_EQ8_BANDS_PER_INSTANCE} Eq8 band slots active. "
        f"Tier A should split the EQCorrectiveDecision into multiple "
        f"chain_positions OR escalate to chain-builder for additional Eq8."
    )
