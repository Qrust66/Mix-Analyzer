"""chain-assembler — Tier B XML writer for absolute device chain ordering.

Phase 4.16 — translates a ``MixDecision[ChainBuildDecision]`` (produced by
``chain-builder`` Tier A) into deterministic XML reorderings of each
track's ``<DeviceChain/Devices>`` children.

Architecture (mirror Phase 4.10/4.11/4.12/4.14/4.15) :
- Python module, deterministic, no LLM
- Reuse als_utils primitives (parse_als, find_track_by_name, save_als_from_tree)
- REUSE-only : chain-assembler does NOT create devices. Per-device writers
  (eq8-configurator, dynamics-configurator, spatial-configurator) handle
  device materialization. chain-assembler runs AFTER them and finalizes
  the absolute order. If a slot's device cannot be found in the chain,
  the slot is skipped with reason.
- Idempotent : re-applying the same plan when children are already in the
  target order is a no-op (zero XML mutations).

Slot-to-child matching :
- ``device`` field equals the XML tag (e.g., "Eq8", "Compressor2", "Reverb")
- ``instance`` field disambiguates multiple occurrences of the same tag
  (instance=0 → first child with that tag, instance=1 → second, etc.)
- Children present in the chain but not in the plan are preserved at the
  end (post-planned-slots) in their original relative order, with a warning
  (matches chain-builder spec : "Track has devices NOT matched ... document
  'unexpected state ; verify .als manually'")

Phase 4.16 v1 SCOPE :
- Reorder children to match plan.slots order
- Skip slots whose device+instance is absent from the chain
- Preserve unplanned children at end + warn

Phase 4.16.X future :
- Cascade Eq8 instance creation when Tier A plan demands more Eq8 than
  present (currently delegated to eq8-configurator)
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import als_utils
from mix_engine.blueprint import (
    ChainBuildDecision,
    ChainSlot,
    MixDecision,
    TrackChainPlan,
)


_LOGGER = logging.getLogger(__name__)


# ============================================================================
# Typed exceptions
# ============================================================================


class ChainAssemblerError(Exception):
    """Base exception for chain-assembler failures."""


# ============================================================================
# Report dataclass
# ============================================================================


@dataclass(frozen=True)
class ChainAssemblerReport:
    """Audit trail of an apply_chain_decision invocation."""

    plans_applied: tuple[str, ...] = ()
    """Per-plan track names successfully reordered (or already-ordered)."""

    plans_no_op: tuple[str, ...] = ()
    """Plans where the chain already matched the target order (idempotency)."""

    plans_skipped: tuple[tuple[str, str], ...] = ()
    """(track_name, skip_reason) for plans we couldn't apply at all."""

    slots_unmatched: tuple[tuple[str, str], ...] = ()
    """(track:device:instance, reason) for individual slots whose device
    couldn't be located in the chain."""

    devices_reordered: int = 0
    """Total count of XML children whose chain index changed."""

    extras_preserved: tuple[tuple[str, str], ...] = ()
    """(track, device_tag) for chain children not referenced by any slot,
    preserved at the end of the chain."""

    safety_guardian_status: str = "SKIPPED"
    """'PASS' | 'FAIL' | 'SKIPPED'."""

    warnings: tuple[str, ...] = ()

    output_path: str = ""


# ============================================================================
# Devices container locator
# ============================================================================


def _find_devices_container(track_element: ET.Element) -> Optional[ET.Element]:
    """Locate the <Devices> container that owns the track's DeviceChain.

    Ableton stores the chain at ``DeviceChain/DeviceChain/Devices`` in most
    track types. Some shapes nest at ``DeviceChain/Devices``. Returns the
    first match or None.
    """
    container = track_element.find(".//DeviceChain/DeviceChain/Devices")
    if container is None:
        container = track_element.find(".//DeviceChain/Devices")
    return container


def _slot_id(plan_track: str, slot: ChainSlot) -> str:
    """Stable identifier for a slot, used in skip reports."""
    return f"{plan_track}:{slot.device}#{slot.instance}@pos{slot.position}"


# ============================================================================
# Core reorder algorithm
# ============================================================================


def _build_target_order(
    children: list[ET.Element],
    plan: TrackChainPlan,
) -> tuple[list[ET.Element], list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (new_order, unmatched_slots, extras_preserved).

    Walks ``plan.slots`` in position order, claiming for each slot the
    matching child by ``(device, instance)`` — instance counted as
    "n-th occurrence of this tag in original children list".

    Children not claimed by any slot are :
    - inserted **BEFORE** the last Limiter when the plan contains a Limiter
      slot (preserves the chain-builder hard rule "Limiter terminal absolute"
      — extras must not process post-Limiter signal).
    - appended at the end of new_order otherwise.
    Either way, extras keep their original relative order and are reported
    in extras_preserved.

    Slots whose device+instance can't be located in the chain are returned
    in unmatched_slots with a human reason.
    """
    # Index children by tag with their original order index
    by_tag: dict[str, list[int]] = {}
    for i, child in enumerate(children):
        by_tag.setdefault(child.tag, []).append(i)

    claimed_indices: set[int] = set()
    # claimed_order tracks the new_order positions of slots that were
    # successfully claimed, so we can locate the Limiter slot and insert
    # extras before it.
    new_order: list[ET.Element] = []
    limiter_new_order_idx: Optional[int] = None
    unmatched: list[tuple[str, str]] = []

    # Sort slots by position to enforce monotone order in the new chain.
    # (Tier A parser already enforces monotone ; sort defensively for safety.)
    sorted_slots = sorted(plan.slots, key=lambda s: s.position)

    for slot in sorted_slots:
        tag_indices = by_tag.get(slot.device, [])
        if slot.instance >= len(tag_indices):
            # Not enough occurrences of this tag in the chain
            available = len(tag_indices)
            reason = (
                f"chain has {available} {slot.device!r} device(s) but slot "
                f"requests instance={slot.instance} (0-indexed)"
            )
            unmatched.append((_slot_id(plan.track, slot), reason))
            continue

        original_idx = tag_indices[slot.instance]
        if original_idx in claimed_indices:
            # Defensive — should not happen given monotone instance counting
            reason = (
                f"child at index {original_idx} ({slot.device}) already "
                f"claimed by an earlier slot"
            )
            unmatched.append((_slot_id(plan.track, slot), reason))
            continue

        claimed_indices.add(original_idx)
        new_order.append(children[original_idx])
        # Track the LAST matched Limiter — chain-builder hard rule says
        # Limiter at max position in plan, so the last sorted-slot Limiter
        # is the terminal one we must protect.
        if slot.device == "Limiter":
            limiter_new_order_idx = len(new_order) - 1

    # Build the extras list (un-claimed children, original relative order)
    extras_elements: list[ET.Element] = []
    extras_report: list[tuple[str, str]] = []
    for i, child in enumerate(children):
        if i not in claimed_indices:
            extras_elements.append(child)
            extras_report.append((plan.track, child.tag))

    # Insert extras : BEFORE the terminal Limiter when plan has one,
    # otherwise APPEND at end.
    if limiter_new_order_idx is not None and extras_elements:
        # Splice extras at index limiter_new_order_idx (just before Limiter)
        new_order = (
            new_order[:limiter_new_order_idx]
            + extras_elements
            + new_order[limiter_new_order_idx:]
        )
    else:
        new_order.extend(extras_elements)

    return new_order, unmatched, extras_report


def _apply_plan_to_track(
    track_element: ET.Element,
    plan: TrackChainPlan,
) -> dict:
    """Apply one TrackChainPlan to a single track element.

    Returns a result dict :
    - status: 'applied' | 'no_op' | 'skipped'
    - reason: str (when skipped)
    - reordered: int (count of children whose index changed)
    - unmatched: list[(slot_id, reason)]
    - extras: list[(track, device_tag)]
    """
    container = _find_devices_container(track_element)
    if container is None:
        return {
            "status": "skipped",
            "reason": (
                f"track {plan.track!r} has no DeviceChain/Devices container "
                f"— unexpected XML structure"
            ),
            "reordered": 0,
            "unmatched": [],
            "extras": [],
        }

    children = list(container)
    if not children and not plan.slots:
        return {
            "status": "no_op",
            "reason": "empty chain, empty plan",
            "reordered": 0,
            "unmatched": [],
            "extras": [],
        }

    new_order, unmatched, extras = _build_target_order(children, plan)

    # Idempotency check : if order is unchanged, no-op
    if [id(c) for c in new_order] == [id(c) for c in children]:
        return {
            "status": "no_op",
            "reason": "chain already in target order",
            "reordered": 0,
            "unmatched": unmatched,
            "extras": extras,
        }

    # Count children whose index changed
    reordered = sum(
        1 for i, c in enumerate(new_order)
        if i >= len(children) or children[i] is not c
    )

    # Replace container children with new order. ET doesn't allow reordering
    # in place — clear and re-append. This preserves all XML attributes
    # since we keep the same Element objects.
    for child in children:
        container.remove(child)
    for child in new_order:
        container.append(child)

    return {
        "status": "applied",
        "reason": "",
        "reordered": reordered,
        "unmatched": unmatched,
        "extras": extras,
    }


# ============================================================================
# Public API
# ============================================================================


def apply_chain_decision(
    als_path: str | Path,
    decision: MixDecision[ChainBuildDecision],
    output_path: str | Path | None = None,
    dry_run: bool = False,
    invoke_safety_guardian: bool = True,
) -> ChainAssemblerReport:
    """Apply a chain-build decision (per-track absolute orderings) to an .als file.

    Phase 4.16 v1 SCOPE :
    - Reorders existing children of each track's <Devices> container to
      match the plan.slots ordering (by position).
    - REUSE-only : does not create devices. Slots whose device cannot be
      matched by tag+instance in the chain are skipped with reason.
    - Children present in the chain but not referenced by any slot are
      preserved at the end of the chain (warning emitted).

    Args:
        als_path: Source .als file.
        decision: Tier A chain-build decision (typed).
        output_path: Where to write modified .als. None = overwrite source.
        dry_run: Validate without writing.
        invoke_safety_guardian: Run post-write deterministic checks.

    Returns:
        :class:`ChainAssemblerReport`.

    Raises:
        ChainAssemblerError: Generic failure.
        ValueError: Track named in a plan does not exist in the .als.
    """
    als_path = Path(als_path)
    if not als_path.exists():
        raise ChainAssemblerError(f"Source .als not found : {als_path}")

    if output_path is None and not dry_run:
        output_path = als_path
    output_path = Path(output_path) if output_path else als_path

    plans = decision.value.plans
    if not plans:
        return ChainAssemblerReport(
            output_path=str(als_path if dry_run else output_path),
        )

    tree = als_utils.parse_als(str(als_path))

    plans_applied: list[str] = []
    plans_no_op: list[str] = []
    plans_skipped: list[tuple[str, str]] = []
    slots_unmatched: list[tuple[str, str]] = []
    extras_preserved: list[tuple[str, str]] = []
    warnings: list[str] = []
    devices_reordered = 0

    # Defensive : duplicate-track plans (Tier A parser should reject these
    # via duplicate-key check, but enforce here too — apply only the first).
    seen_tracks: set[str] = set()

    for plan in plans:
        if plan.track in seen_tracks:
            plans_skipped.append((
                plan.track,
                "duplicate plan for this track in decision (first applied, rest ignored)",
            ))
            continue
        seen_tracks.add(plan.track)

        try:
            track_el = als_utils.find_track_by_name(tree, plan.track)
        except ValueError:
            raise  # propagate Tier A misalignment ; track must exist

        result = _apply_plan_to_track(track_el, plan)

        slots_unmatched.extend(result["unmatched"])
        extras_preserved.extend(result["extras"])
        for slot_id, reason in result["unmatched"]:
            warnings.append(f"{slot_id} unmatched : {reason}")
        for track, tag in result["extras"]:
            warnings.append(
                f"{track} : {tag} present in chain but not in plan — "
                f"preserved at end (verify .als manually)"
            )

        if result["status"] == "applied":
            plans_applied.append(plan.track)
            devices_reordered += result["reordered"]
            _LOGGER.info(
                "Reordered chain on %r : %d device(s) repositioned",
                plan.track, result["reordered"],
            )
        elif result["status"] == "no_op":
            plans_no_op.append(plan.track)
            _LOGGER.debug(
                "No-op on %r : %s", plan.track, result["reason"]
            )
        else:
            plans_skipped.append((plan.track, result["reason"]))
            warnings.append(f"{plan.track} skipped : {result['reason']}")

    if dry_run:
        return ChainAssemblerReport(
            plans_applied=tuple(plans_applied),
            plans_no_op=tuple(plans_no_op),
            plans_skipped=tuple(plans_skipped),
            slots_unmatched=tuple(slots_unmatched),
            devices_reordered=devices_reordered,
            extras_preserved=tuple(extras_preserved),
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

    return ChainAssemblerReport(
        plans_applied=tuple(plans_applied),
        plans_no_op=tuple(plans_no_op),
        plans_skipped=tuple(plans_skipped),
        slots_unmatched=tuple(slots_unmatched),
        devices_reordered=devices_reordered,
        extras_preserved=tuple(extras_preserved),
        safety_guardian_status=safety_status,
        warnings=tuple(warnings),
        output_path=str(final_als),
    )


# ============================================================================
# Phase 4.16 Step 2 — Safety guardian
# ============================================================================


def _run_safety_checks(
    als_path: str | Path,
    decision: MixDecision[ChainBuildDecision],
) -> tuple[str, list[str]]:
    """Deterministic post-write safety checks for chain-assembler XML.

    Phase 4.16 checks :
    1. File exists, gunzippable, parses as XML
    2. NextPointeeId > max(Id) (general .als invariant)
    3. For each plan : the matched devices appear in the chain in the
       order requested by the plan (monotone preserved post-reorder)
    4. For each plan : no device referenced by a non-preexisting slot was
       removed from the chain (verify slot.device tag still present at
       requested instance index)
    5. For each plan with a Limiter slot : the corresponding Limiter must
       be the LAST device in the post-write chain (chain-builder hard rule
       "chain_end_limiter — Limiter terminal absolute"). Phase 4.16.1
       audit fix.
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
                issues.append(
                    f"NextPointeeId={v} <= max Id ({max_id}) ; "
                    f"Ableton refuses to load."
                )
        except ValueError:
            pass

    # Per-plan order verification
    for plan in decision.value.plans:
        try:
            track_el = als_utils.find_track_by_name(tree, plan.track)
        except ValueError:
            issues.append(
                f"plan track {plan.track!r} not found in .als post-write "
                f"(should never happen — Tier B raised earlier)"
            )
            continue

        container = _find_devices_container(track_el)
        if container is None:
            continue

        children = list(container)
        # Expected sequence : tag of each slot (sorted by position),
        # restricted to slots whose device exists at requested instance.
        sorted_slots = sorted(plan.slots, key=lambda s: s.position)
        tag_counter: Counter[str] = Counter()
        expected_sequence: list[tuple[str, int]] = []
        for slot in sorted_slots:
            expected_sequence.append((slot.device, slot.instance))
            tag_counter[slot.device] = max(
                tag_counter[slot.device], slot.instance + 1
            )

        # Build actual sequence : (tag, instance) walking children in order.
        actual_seq: list[tuple[str, int]] = []
        seen: Counter[str] = Counter()
        for child in children:
            actual_seq.append((child.tag, seen[child.tag]))
            seen[child.tag] += 1

        # Each expected (tag, instance) must appear in actual_seq, AND the
        # subsequence formed by intersecting expected with actual must
        # preserve order.
        actual_index_by_pair: dict[tuple[str, int], int] = {
            pair: i for i, pair in enumerate(actual_seq)
        }
        prev_idx = -1
        for pair in expected_sequence:
            idx = actual_index_by_pair.get(pair)
            if idx is None:
                # Slot's device+instance missing from chain post-write.
                # Note : missing-pre-write slots were already skipped in
                # apply path ; if missing here, only a real bug or
                # external mutation could cause it. Report as FAIL.
                issues.append(
                    f"plan {plan.track!r} : expected {pair[0]} instance "
                    f"{pair[1]} not found in chain post-write"
                )
                continue
            if idx <= prev_idx:
                issues.append(
                    f"plan {plan.track!r} : {pair[0]} instance {pair[1]} "
                    f"out of order (chain index {idx} <= prev {prev_idx})"
                )
            prev_idx = idx

        # Phase 4.16.1 audit fix — Limiter-terminal hard rule check.
        # Chain-builder enforces "chain_end_limiter — Limiter terminal
        # absolute" at plan level. Verify the post-write chain still
        # honors it : if any slot is a Limiter, that Limiter instance
        # must be the LAST child of the Devices container.
        limiter_slots = [s for s in plan.slots if s.device == "Limiter"]
        if limiter_slots and children:
            last_child = children[-1]
            if last_child.tag != "Limiter":
                # Some non-Limiter device sits after the planned Limiter
                issues.append(
                    f"plan {plan.track!r} : Limiter not terminal in "
                    f"post-write chain (last device is {last_child.tag!r}). "
                    f"Hard rule 'chain_end_limiter' violated."
                )

    return ("PASS" if not issues else "FAIL"), issues
