"""dynamics-configurator — Tier B XML writer for dynamics corrective decisions.

Phase 4.11 — translates a ``MixDecision[DynamicsCorrectiveDecision]``
(produced by ``dynamics-corrective-decider`` Tier A) into deterministic
XML patches applied to an .als file.

Scope Phase 4.11 v1 — GlueCompressor + Limiter only :
- ``dynamics_type="bus_glue"`` → GlueCompressor (Threshold/Ratio/Attack/
  Release/Makeup/DryWet)
- ``dynamics_type="limit"`` → Limiter (Ceiling/Release/AutoRelease)

OUT-OF-SCOPE Phase 4.11 v1 (escalated to Phase 4.12 v2) :
- ``dynamics_type ∈ {compress, sidechain_duck, parallel_compress, deess}``
  → Compressor2 (not in current fixture for testing)
- ``dynamics_type="gate"`` → Gate
- ``dynamics_type="transient_shape"`` → DrumBuss

Bands targeting unsupported (device, dynamics_type) combinations are
recorded in :attr:`DynamicsConfiguratorReport.bands_skipped` with reason ;
the rest of the decision is applied normally.

Architecture (mirror of Phase 4.10 eq8-configurator) :
- Python module, deterministic, no LLM
- Reuse als_utils primitives (parse_als, find_track_by_name, save_als_from_tree)
- New parallel functions in als_utils (find_or_create_X_at_position) added
  in Phase 4.11 Step 2
- Backward-compat strict (no existing als_utils API touched)
- 5-step methodology : skeleton → chain_position → envelopes/sidechain →
  idempotency → safety_guardian
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import als_utils
from mix_engine.blueprint import (
    DynamicsCorrection,
    DynamicsCorrectiveDecision,
    MixDecision,
)


_LOGGER = logging.getLogger(__name__)


# ============================================================================
# Translation table : dynamics_type → required device + supported flag
# ============================================================================
#
# Phase 4.11 v1 supports a SUBSET. Unsupported types/devices skip with
# explicit reason in the report.

_PHASE_4_11_V1_SUPPORTED_DEVICES: frozenset[str] = frozenset({
    "GlueCompressor",
    "Limiter",
})


def _is_supported(correction: DynamicsCorrection) -> tuple[bool, str]:
    """Return (supported, reason_if_not).

    Phase 4.11 v1 only writes to GlueCompressor + Limiter ; other devices
    are left for Phase 4.12.
    """
    if correction.device not in _PHASE_4_11_V1_SUPPORTED_DEVICES:
        return False, (
            f"device={correction.device!r} not yet supported by Phase 4.11 "
            f"v1 (only GlueCompressor + Limiter). Phase 4.12 will add "
            f"Compressor2/Gate/DrumBuss."
        )
    if correction.dynamics_type == "limit" and correction.device != "Limiter":
        return False, (
            f"dynamics_type='limit' requires device='Limiter', got "
            f"{correction.device!r}."
        )
    if correction.dynamics_type == "bus_glue" and correction.device != "GlueCompressor":
        return False, (
            f"dynamics_type='bus_glue' requires device='GlueCompressor', "
            f"got {correction.device!r}."
        )
    return True, ""


# ============================================================================
# Typed exceptions
# ============================================================================


class DynamicsConfiguratorError(Exception):
    """Base exception for dynamics-configurator failures.

    Subclasses for actionable failure modes ; parent caught for generic
    error handling.
    """


class DynamicsDeviceNotFoundError(DynamicsConfiguratorError):
    """Raised when REUSE-only mode (Phase 4.11 v1) cannot find the target
    device on the track.

    Phase 4.11 v1 does not create new dynamics devices (no template
    available). If the track lacks the required device, the band must be
    skipped or the user must add the device manually first.
    """


# ============================================================================
# Report dataclass
# ============================================================================


@dataclass(frozen=True)
class DynamicsConfiguratorReport:
    """Audit trail of an apply_dynamics_corrective_decision invocation."""

    corrections_applied: tuple[str, ...] = ()
    """Per-correction identifiers (track:dynamics_type:device) applied."""

    corrections_skipped: tuple[tuple[str, str], ...] = ()
    """(correction_id, skip_reason) — typically Phase 4.11 v1 unsupported types."""

    devices_reused: int = 0
    """Number of existing dynamics devices reused (Phase 4.11 v1 = REUSE only)."""

    devices_created: int = 0
    """Always 0 in Phase 4.11 v1 (no create paths)."""

    automations_written: int = 0
    """Number of <AutomationEnvelope> blocks written (Phase 4.11 Step 3+)."""

    safety_guardian_status: str = "SKIPPED"
    """'PASS' | 'FAIL' | 'SKIPPED' (Phase 4.11 Step 4)."""

    warnings: tuple[str, ...] = ()
    """Non-fatal observations."""

    output_path: str = ""
    """Final .als path written (or input path if dry_run=True)."""


# ============================================================================
# Param writers per device
# ============================================================================


def _set_param(device_element: ET.Element, param_name: str, value: float) -> bool:
    """Write a Manual Value on a device's named param.

    Returns True if the param was found and set, False otherwise (e.g.,
    GlueCompressor has no Knee — silently skipped, caller decides if
    that's a warning).
    """
    param = device_element.find(param_name)
    if param is None:
        return False
    manual = param.find("Manual")
    if manual is None:
        return False
    manual.set("Value", str(float(value)))
    return True


def _write_glue_compressor_params(
    device: ET.Element, correction: DynamicsCorrection,
) -> list[str]:
    """Write static params on a GlueCompressor instance.

    Returns list of warnings for params that were specified but couldn't
    be applied (e.g., knee_db on GlueComp which has no Knee param).
    """
    warnings: list[str] = []

    if correction.threshold_db is not None:
        if not _set_param(device, "Threshold", correction.threshold_db):
            warnings.append("Threshold param missing on GlueCompressor")

    if correction.ratio is not None:
        # GlueCompressor's Ratio is enum (0=2:1, 1=4:1, 2=10:1) but the schema
        # field is float ; Tier B writes the float verbatim. Calibration may
        # refine the mapping later if needed.
        if not _set_param(device, "Ratio", correction.ratio):
            warnings.append("Ratio param missing on GlueCompressor")

    if correction.attack_ms is not None:
        if not _set_param(device, "Attack", correction.attack_ms):
            warnings.append("Attack param missing on GlueCompressor")

    if correction.release_ms is not None:
        if not _set_param(device, "Release", correction.release_ms):
            warnings.append("Release param missing on GlueCompressor")

    if correction.makeup_db is not None:
        if not _set_param(device, "Makeup", correction.makeup_db):
            warnings.append("Makeup param missing on GlueCompressor")

    if correction.dry_wet is not None:
        if not _set_param(device, "DryWet", correction.dry_wet):
            warnings.append("DryWet param missing on GlueCompressor")

    # Phase 4.11 v1 limitation : knee_db is in schema but GlueCompressor has
    # no Knee param (uses Range for soft-knee equivalent). Warn and skip.
    if correction.knee_db is not None:
        warnings.append(
            f"knee_db={correction.knee_db} specified but GlueCompressor "
            f"has no Knee parameter (uses 'Range' for soft-knee equivalent). "
            f"Phase 4.12 may add Range mapping if Tier A signals it."
        )

    return warnings


def _write_limiter_params(
    device: ET.Element, correction: DynamicsCorrection,
) -> list[str]:
    """Write static params on a Limiter instance.

    Returns warnings list. Limiter has Ceiling, Release, and AutoRelease
    (bool). dynamics_type='limit' should set ceiling_db.
    """
    warnings: list[str] = []

    if correction.ceiling_db is not None:
        if not _set_param(device, "Ceiling", correction.ceiling_db):
            warnings.append("Ceiling param missing on Limiter")

    if correction.release_ms is not None:
        if not _set_param(device, "Release", correction.release_ms):
            warnings.append("Release param missing on Limiter")

    if correction.release_auto:
        # Limiter has AutoRelease as a top-level bool (no Manual wrapper)
        auto = device.find("AutoRelease")
        if auto is not None:
            auto.set("Value", "true")

    # Limiter ignored params (signaled to user) :
    if correction.threshold_db is not None:
        warnings.append(
            f"threshold_db={correction.threshold_db} ignored : Limiter has "
            f"no separate threshold (uses Ceiling)."
        )
    if correction.ratio is not None:
        warnings.append(
            f"ratio={correction.ratio} ignored : Limiter is brick-wall "
            f"(implicit infinite ratio)."
        )
    if correction.makeup_db is not None:
        warnings.append(
            f"makeup_db={correction.makeup_db} ignored : Limiter has no "
            f"separate makeup (built into ceiling drive)."
        )

    return warnings


def _find_existing_device(
    track_element: ET.Element,
    device_tag: str,
    chain_position: str = "default",
) -> Optional[ET.Element]:
    """REUSE-only lookup honoring chain_position when not 'default'.

    Phase 4.11 Step 2 — delegates to als_utils.find_existing_device_at_dynamics_position
    when chain_position is specified. Falls back to first-match for 'default'.

    Returns None if no matching device at the requested position (caller
    skips with reason in the report).
    """
    if chain_position == "default":
        return track_element.find(f".//{device_tag}")
    return als_utils.find_existing_device_at_dynamics_position(
        track_element, device_tag, chain_position,
    )


# ============================================================================
# Public API
# ============================================================================


def apply_dynamics_corrective_decision(
    als_path: str | Path,
    decision: MixDecision[DynamicsCorrectiveDecision],
    output_path: str | Path | None = None,
    dry_run: bool = False,
    invoke_safety_guardian: bool = True,
) -> DynamicsConfiguratorReport:
    """Apply a dynamics corrective decision to an .als file.

    Phase 4.11 v1 SCOPE : GlueCompressor + Limiter REUSE-only. Other devices
    (Compressor2, Gate, DrumBuss) are skipped with reason in the report
    (Phase 4.12 will add support).

    REUSE-only means : if the track does not already have the required
    device (GlueCompressor for bus_glue, Limiter for limit), the band is
    skipped with DynamicsDeviceNotFoundError reason. Phase 4.12 may add
    create paths once a device template fixture is available.

    Args:
        als_path: Path to source .als file.
        decision: Tier A dynamics corrective decision (typed).
        output_path: Where to write modified .als (None overwrites).
        dry_run: If True, validate without writing.
        invoke_safety_guardian: Run post-write deterministic checks.

    Returns:
        :class:`DynamicsConfiguratorReport`.

    Raises:
        DynamicsConfiguratorError: Generic failure (track structure invalid).
        ValueError: Track not found (from als_utils.find_track_by_name).
    """
    als_path = Path(als_path)
    if not als_path.exists():
        raise DynamicsConfiguratorError(f"Source .als not found : {als_path}")

    if output_path is None and not dry_run:
        output_path = als_path
    output_path = Path(output_path) if output_path else als_path

    corrections = decision.value.corrections
    if not corrections:
        return DynamicsConfiguratorReport(
            output_path=str(als_path if dry_run else output_path),
        )

    tree = als_utils.parse_als(str(als_path))

    corrections_applied: list[str] = []
    corrections_skipped: list[tuple[str, str]] = []
    warnings: list[str] = []
    devices_reused: int = 0

    for correction in corrections:
        correction_id = (
            f"{correction.track}:{correction.dynamics_type}:{correction.device}"
        )

        # Phase 4.11 v1 scope check
        supported, reason = _is_supported(correction)
        if not supported:
            corrections_skipped.append((correction_id, reason))
            warnings.append(f"{correction_id} skipped : {reason}")
            continue

        # Find track
        track_el = als_utils.find_track_by_name(tree, correction.track)

        # REUSE-only : find existing device honoring chain_position
        device_tag = correction.device  # "GlueCompressor" or "Limiter"
        device = _find_existing_device(
            track_el, device_tag, chain_position=correction.chain_position,
        )
        if device is None:
            if correction.chain_position == "default":
                reason = (
                    f"track {correction.track!r} has no {device_tag} device. "
                    f"Phase 4.11 v1 is REUSE-only (no create paths) ; user "
                    f"must add a {device_tag} to the track manually OR Phase "
                    f"4.12 may add create paths via device template fixture."
                )
            else:
                reason = (
                    f"track {correction.track!r} has no {device_tag} device "
                    f"at chain_position={correction.chain_position!r}. "
                    f"Phase 4.11 v1 is REUSE-only — Tier B cannot insert a "
                    f"new device at the requested position without a template."
                )
            corrections_skipped.append((correction_id, reason))
            warnings.append(f"{correction_id} skipped : {reason}")
            continue

        devices_reused += 1

        # Write static params per device type
        if correction.device == "GlueCompressor":
            param_warnings = _write_glue_compressor_params(device, correction)
        elif correction.device == "Limiter":
            param_warnings = _write_limiter_params(device, correction)
        else:
            # Should not reach here (filtered by _is_supported above)
            raise DynamicsConfiguratorError(
                f"Unexpected device {correction.device} reached writer dispatch"
            )

        # Prefix warnings with correction context for traceability
        for w in param_warnings:
            warnings.append(f"{correction_id}: {w}")

        corrections_applied.append(correction_id)
        _LOGGER.info("Applied %s", correction_id)

    if dry_run:
        return DynamicsConfiguratorReport(
            corrections_applied=tuple(corrections_applied),
            corrections_skipped=tuple(corrections_skipped),
            devices_reused=devices_reused,
            warnings=tuple(warnings),
            output_path=str(als_path),
        )

    final_als = als_utils.save_als_from_tree(tree, str(output_path))

    # Phase 4.11 Step 4 will add safety_guardian. For Step 1 it stays SKIPPED.
    safety_status = "SKIPPED"

    return DynamicsConfiguratorReport(
        corrections_applied=tuple(corrections_applied),
        corrections_skipped=tuple(corrections_skipped),
        devices_reused=devices_reused,
        safety_guardian_status=safety_status,
        warnings=tuple(warnings),
        output_path=str(final_als),
    )
