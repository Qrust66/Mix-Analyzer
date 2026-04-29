"""routing-configurator — Tier B XML writer for sidechain routing repairs.

Phase 4.14 — translates a ``MixDecision[RoutingDecision]`` (produced by
``routing-and-sidechain-architect`` Tier A) into deterministic XML
patches editing ``<SideChain>/<RoutedInput>/<Routable>/<Target>`` and
``<SideChain>/<OnOff>/<Manual>`` values.

Architecture (mirror Phase 4.10/4.11/4.12) :
- Python module, deterministic, no LLM
- Reuse als_utils primitives
- REUSE-only for redirect + remove (the SideChain XML block must already
  exist on the track) ; Phase 4.14.X future will add sidechain_create

Phase 4.14 v1 supported fix_types :
- ``sidechain_redirect`` : update Target Value on a SideChain whose current
  Target points to the resolved ``current_trigger`` Id ; preserve the
  routing tap suffix (``/PostFxOut`` or ``/PreFxOut``)
- ``sidechain_remove`` : set Target Value to ``"AudioIn/None"`` AND
  OnOff/Manual Value to ``"false"``

Phase 4.14.X future (rule-with-consumer) :
- ``sidechain_create`` : insert new <SideChain> block on a device that
  doesn't have one (requires SideChain XML template — same constraint as
  Pluggin Mapping.als template absent in Phase 4.10/4.11/4.12)
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import als_utils
from mix_engine.blueprint import (
    MixDecision,
    RoutingDecision,
    SidechainRepair,
)


_LOGGER = logging.getLogger(__name__)


# ============================================================================
# Typed exceptions
# ============================================================================


class RoutingConfiguratorError(Exception):
    """Base exception for routing-configurator failures."""


class SidechainBlockNotFoundError(RoutingConfiguratorError):
    """Raised when REUSE-only mode cannot find a matching SideChain block.

    Phase 4.14 v1 : redirect + remove require an existing SideChain on the
    target track. If absent (or the current_trigger Id doesn't match any
    Target), the repair is skipped with reason.
    """


# ============================================================================
# Report dataclass
# ============================================================================


@dataclass(frozen=True)
class RoutingConfiguratorReport:
    """Audit trail of an apply_routing_decision invocation."""

    repairs_applied: tuple[str, ...] = ()
    """Per-repair identifiers (track:fix_type:current→new)."""

    repairs_skipped: tuple[tuple[str, str], ...] = ()
    """(repair_id, skip_reason)."""

    sidechain_blocks_modified: int = 0
    """Number of <SideChain> blocks that received Target/OnOff updates."""

    safety_guardian_status: str = "SKIPPED"

    warnings: tuple[str, ...] = ()

    output_path: str = ""


# ============================================================================
# Track name → Id resolution
# ============================================================================

# RoutingTarget XML format : "AudioIn/Track.<Id>/<Tap>"
# Tap is typically "PostFxOut" or "PreFxOut" ; default to PostFxOut for new
# refs (most common in Tier A routing decisions).
_TARGET_PATTERN = re.compile(r"^AudioIn/Track\.(\d+)(?:/(.+))?$")


def _resolve_track_id(tree: ET.ElementTree, track_name: str) -> str:
    """Resolve a track name to its XML Id attribute (str).

    Raises ValueError if the track is not found OR has no Id.
    """
    track_el = als_utils.find_track_by_name(tree, track_name)
    track_id = track_el.get("Id")
    if track_id is None:
        raise ValueError(
            f"Track {track_name!r} found but has no Id attribute — "
            f"unexpected XML structure."
        )
    return track_id


def _build_target_value(track_id: str, tap: str = "PostFxOut") -> str:
    """Build the AudioIn/Track.<Id>/<Tap> target string."""
    return f"AudioIn/Track.{track_id}/{tap}"


def _parse_target_value(value: str) -> tuple[Optional[str], Optional[str]]:
    """Parse an AudioIn/Track.<Id>/<Tap> string into (id, tap) or (None, None)."""
    m = _TARGET_PATTERN.match(value)
    if m is None:
        return None, None
    return m.group(1), (m.group(2) or "PostFxOut")


# ============================================================================
# SideChain block locators
# ============================================================================


def _find_sidechain_blocks_on_track(track_element: ET.Element) -> list[ET.Element]:
    """Return all <SideChain> blocks within the track's DeviceChain."""
    return track_element.findall(".//SideChain")


def _get_sidechain_target(sidechain: ET.Element) -> Optional[ET.Element]:
    """Return the <Target> Element inside a SideChain, or None if absent."""
    return sidechain.find("RoutedInput/Routable/Target")


def _get_sidechain_onoff(sidechain: ET.Element) -> Optional[ET.Element]:
    """Return the <Manual> Element inside SideChain/OnOff, or None."""
    return sidechain.find("OnOff/Manual")


def _find_matching_sidechain_for_redirect(
    track_element: ET.Element,
    current_trigger_id: str,
) -> Optional[ET.Element]:
    """Find the first SideChain on the track whose Target points to the
    current_trigger Id. Returns None if no match.
    """
    for sc in _find_sidechain_blocks_on_track(track_element):
        target = _get_sidechain_target(sc)
        if target is None:
            continue
        target_id, _ = _parse_target_value(target.get("Value", ""))
        if target_id == current_trigger_id:
            return sc
    return None


def _find_first_active_sidechain_for_remove(
    track_element: ET.Element,
    current_trigger_id: str,
) -> Optional[ET.Element]:
    """Find the first SideChain on the track currently pointing to
    current_trigger_id (any tap). Same matcher as redirect."""
    return _find_matching_sidechain_for_redirect(track_element, current_trigger_id)


# ============================================================================
# Public API
# ============================================================================


def apply_routing_decision(
    als_path: str | Path,
    decision: MixDecision[RoutingDecision],
    output_path: str | Path | None = None,
    dry_run: bool = False,
    invoke_safety_guardian: bool = True,
) -> RoutingConfiguratorReport:
    """Apply a routing decision (sidechain repairs) to an .als file.

    Phase 4.14 v1 supports :
    - sidechain_redirect : changes Target on existing SideChain (preserves
      tap PostFxOut/PreFxOut)
    - sidechain_remove : sets Target=AudioIn/None + OnOff=false on the
      matching SideChain

    sidechain_create is deferred to Phase 4.14.X (no SideChain XML template
    available — same REUSE-only constraint as the other writers).

    Args:
        als_path: Source .als file.
        decision: Tier A routing decision (typed).
        output_path: Where to write modified .als. None = overwrite source.
        dry_run: Validate without writing.
        invoke_safety_guardian: Run post-write checks.

    Returns:
        :class:`RoutingConfiguratorReport`.

    Raises:
        RoutingConfiguratorError: Generic failure.
        ValueError: Track not found.
    """
    als_path = Path(als_path)
    if not als_path.exists():
        raise RoutingConfiguratorError(f"Source .als not found : {als_path}")

    if output_path is None and not dry_run:
        output_path = als_path
    output_path = Path(output_path) if output_path else als_path

    repairs = decision.value.repairs
    if not repairs:
        return RoutingConfiguratorReport(
            output_path=str(als_path if dry_run else output_path),
        )

    tree = als_utils.parse_als(str(als_path))

    repairs_applied: list[str] = []
    repairs_skipped: list[tuple[str, str]] = []
    warnings: list[str] = []
    sidechain_blocks_modified: int = 0

    for repair in repairs:
        # ASCII repair_id (avoid Unicode arrows for Windows cp1252 console compat)
        repair_id = (
            f"{repair.track}:{repair.fix_type}:"
            f"{repair.current_trigger or '<none>'}->{repair.new_trigger or '<none>'}"
        )

        try:
            track_el = als_utils.find_track_by_name(tree, repair.track)
        except ValueError:
            raise  # propagate Tier A misalignment

        # ---- sidechain_create : deferred ----
        if repair.fix_type == "sidechain_create":
            reason = (
                f"sidechain_create deferred to Phase 4.14.X (requires "
                f"SideChain XML template). Tier B v1 only supports "
                f"redirect + remove on existing SideChain blocks."
            )
            repairs_skipped.append((repair_id, reason))
            warnings.append(f"{repair_id} skipped : {reason}")
            continue

        # ---- sidechain_redirect ----
        if repair.fix_type == "sidechain_redirect":
            try:
                current_id = _resolve_track_id(tree, repair.current_trigger)
                new_id = _resolve_track_id(tree, repair.new_trigger)
            except ValueError as exc:
                repairs_skipped.append((
                    repair_id,
                    f"track resolution failed : {exc}",
                ))
                continue

            sc = _find_matching_sidechain_for_redirect(track_el, current_id)
            if sc is None:
                reason = (
                    f"track {repair.track!r} has no SideChain currently "
                    f"pointing to {repair.current_trigger!r} (Id={current_id}). "
                    f"REUSE-only — cannot redirect a non-existent ref."
                )
                repairs_skipped.append((repair_id, reason))
                warnings.append(f"{repair_id} skipped : {reason}")
                continue

            target = _get_sidechain_target(sc)
            old_value = target.get("Value", "")
            _, tap = _parse_target_value(old_value)
            tap = tap or "PostFxOut"
            new_value = _build_target_value(new_id, tap)
            target.set("Value", new_value)

            sidechain_blocks_modified += 1
            repairs_applied.append(repair_id)
            _LOGGER.info(
                "Redirected %r SideChain : %s → %s",
                repair.track, old_value, new_value,
            )
            continue

        # ---- sidechain_remove ----
        if repair.fix_type == "sidechain_remove":
            try:
                current_id = _resolve_track_id(tree, repair.current_trigger)
            except ValueError as exc:
                repairs_skipped.append((
                    repair_id,
                    f"current_trigger track resolution failed : {exc}",
                ))
                continue

            sc = _find_first_active_sidechain_for_remove(track_el, current_id)
            if sc is None:
                reason = (
                    f"track {repair.track!r} has no SideChain currently "
                    f"pointing to {repair.current_trigger!r} (Id={current_id}). "
                    f"Nothing to remove."
                )
                repairs_skipped.append((repair_id, reason))
                warnings.append(f"{repair_id} skipped : {reason}")
                continue

            target = _get_sidechain_target(sc)
            target.set("Value", "AudioIn/None")

            onoff = _get_sidechain_onoff(sc)
            if onoff is not None:
                onoff.set("Value", "false")

            sidechain_blocks_modified += 1
            repairs_applied.append(repair_id)
            _LOGGER.info("Removed sidechain on %r", repair.track)
            continue

        # Unknown fix_type
        repairs_skipped.append((
            repair_id,
            f"unknown fix_type={repair.fix_type!r}",
        ))

    if dry_run:
        return RoutingConfiguratorReport(
            repairs_applied=tuple(repairs_applied),
            repairs_skipped=tuple(repairs_skipped),
            sidechain_blocks_modified=sidechain_blocks_modified,
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

    return RoutingConfiguratorReport(
        repairs_applied=tuple(repairs_applied),
        repairs_skipped=tuple(repairs_skipped),
        sidechain_blocks_modified=sidechain_blocks_modified,
        safety_guardian_status=safety_status,
        warnings=tuple(warnings),
        output_path=str(final_als),
    )


# ============================================================================
# Safety guardian
# ============================================================================


def _run_safety_checks(als_path: str | Path) -> tuple[str, list[str]]:
    """Deterministic post-write safety checks for routing XML.

    Phase 4.14 checks :
    1. File exists, gunzippable, parses as XML
    2. NextPointeeId > max(Id)
    3. All SideChain Target values match AudioIn/None | AudioIn/Track.<Id>/<Tap>
       | AudioIn/Bus.<Id> | AudioIn/Master | AudioIn/Returns/<Id>
       (no malformed references)
    4. SideChain Target referencing Track.<Id> — verify the Id exists in the
       project (no dangling references)
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
    all_track_ids: set[str] = set()
    for elem in root.iter():
        raw = elem.get("Id")
        if raw is not None:
            try:
                v = int(raw)
                if v > max_id:
                    max_id = v
            except ValueError:
                pass
        # Capture track Ids while iterating
        if elem.tag in ("AudioTrack", "MidiTrack", "GroupTrack", "ReturnTrack"):
            tid = elem.get("Id")
            if tid is not None:
                all_track_ids.add(tid)
    if next_pid_el is not None:
        try:
            v = int(next_pid_el.get("Value", "0"))
            if v <= max_id:
                issues.append(
                    f"NextPointeeId={v} ≤ max Id ({max_id}) ; "
                    f"Ableton refuses to load."
                )
        except ValueError:
            pass

    # SideChain Target validation — well-formed + no dangling Track refs
    valid_anchors = {"AudioIn/None", "AudioIn/Master"}
    valid_prefixes = ("AudioIn/Bus.", "AudioIn/Returns/", "AudioIn/Track.")
    for target in root.findall(".//SideChain/RoutedInput/Routable/Target"):
        val = target.get("Value", "")
        if val in valid_anchors:
            continue
        # Track ref : verify Id exists
        m = _TARGET_PATTERN.match(val)
        if m is not None:
            track_id = m.group(1)
            if track_id not in all_track_ids:
                issues.append(
                    f"SideChain Target={val!r} references non-existent "
                    f"track Id={track_id} (dangling ref — track may have "
                    f"been deleted)"
                )
            continue
        # Bus / Returns ref
        if any(val.startswith(p) for p in valid_prefixes):
            continue
        # Anything else is unexpected
        if val:  # non-empty mismatched
            issues.append(
                f"SideChain Target={val!r} — unrecognized format "
                f"(expected AudioIn/None | AudioIn/Track.<Id>/<Tap> | "
                f"AudioIn/Bus.<Id> | AudioIn/Master | AudioIn/Returns/<Id>)"
            )

    return ("PASS" if not issues else "FAIL"), issues
