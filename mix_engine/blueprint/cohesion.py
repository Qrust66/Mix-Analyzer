"""Mix-side cohesion checks — declarative cross-lane rules.

Mirrors composition_engine.blueprint.cohesion. A "mix cohesion rule" is a
predicate that takes a MixBlueprint and returns either None (cohesive)
or a MixCohesionViolation. Rules are auto-collected via the
@mix_cohesion_rule decorator and silently skipped when their required
lanes aren't filled — safe to run on partial blueprints.

Phase 4.19 ships the infrastructure ; Phase 4.19.1 ships the first
concrete rule (`sidechain_target_exists_in_routing`). Subsequent rules
land alongside the agent that motivates each one (rule-with-consumer
principle) — speculative rules drift away from real schema fields.

Future rules expected (not yet implemented — listed in
docs/MIX_ENGINE_ARCHITECTURE.md §7) :

| Rule                                              | Severity | Lanes |
|---------------------------------------------------|----------|-------|
| eq_cuts_dont_create_phase_holes_with_neighbours   | warn     | eq_corrective × eq_corrective (cross-track) |
| master_ceiling_below_minus_03_dbtp                | block    | mastering |
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional

from mix_engine.blueprint.schema import MixBlueprint


@dataclass(frozen=True)
class MixCohesionViolation:
    """One coherence issue detected in a MixBlueprint."""

    rule: str
    severity: Literal["info", "warn", "block"]
    message: str
    lanes: tuple[str, ...]


@dataclass(frozen=True)
class MixCohesionReport:
    """The full set of violations for a MixBlueprint."""

    violations: tuple[MixCohesionViolation, ...] = ()

    @property
    def is_clean(self) -> bool:
        """True if no rule blocked. Warnings + infos are allowed."""
        return not any(v.severity == "block" for v in self.violations)

    @property
    def blockers(self) -> tuple[MixCohesionViolation, ...]:
        return tuple(v for v in self.violations if v.severity == "block")

    @property
    def warnings(self) -> tuple[MixCohesionViolation, ...]:
        return tuple(v for v in self.violations if v.severity == "warn")


MixCohesionFn = Callable[[MixBlueprint], Optional[MixCohesionViolation]]
_RULES: list[MixCohesionFn] = []


def mix_cohesion_rule(
    lanes: tuple[str, ...],
) -> Callable[[MixCohesionFn], MixCohesionFn]:
    """Register a cohesion rule that depends on the listed mix lanes.

    The rule will be auto-skipped when any of ``lanes`` is not filled in
    the MixBlueprint passed to :func:`check_mix_cohesion`.

    Usage::

        @mix_cohesion_rule(lanes=("dynamics_corrective", "routing"))
        def sidechain_target_exists(bp):
            ...
    """

    def decorator(fn: MixCohesionFn) -> MixCohesionFn:
        fn._lanes = lanes  # type: ignore[attr-defined]
        _RULES.append(fn)
        return fn

    return decorator


def check_mix_cohesion(bp: MixBlueprint) -> MixCohesionReport:
    """Run every registered rule whose required lanes are filled."""
    violations: list[MixCohesionViolation] = []
    filled = set(bp.filled_lanes())
    for rule in _RULES:
        required = getattr(rule, "_lanes", ())
        if not all(lane in filled for lane in required):
            continue
        result = rule(bp)
        if result is not None:
            violations.append(result)
    return MixCohesionReport(violations=tuple(violations))


# ============================================================================
# Concrete rules (Phase 4.19.1+)
# ============================================================================
#
# Each rule lands together with the agent whose output it constrains, per
# the project's "rule-with-consumer" principle.


@mix_cohesion_rule(lanes=("dynamics_corrective", "routing"))
def sidechain_target_exists_in_routing(
    bp: MixBlueprint,
) -> Optional[MixCohesionViolation]:
    """Block when ``dynamics_corrective`` references an external sidechain
    trigger that ``routing`` is removing in the same blueprint.

    Failure mode caught :
        dynamics-corrective-decider says "duck Bass when Kick triggers"
        (DynamicsCorrection.sidechain.mode == "external",
         .trigger_track == "Kick")
        AND
        routing-and-sidechain-architect says "remove the sidechain on
        Bass" (SidechainRepair.fix_type == "sidechain_remove",
         .current_trigger == "Kick", .track == "Bass" or any).

    Both can be individually valid, but together they leave Tier B in
    contradiction — dynamics writer would configure a Compressor2
    sidechain pointing at Kick, routing writer would unwire it. Result :
    a half-configured sidechain block with no input, silent in Ableton.

    Other failure modes (sidechain_redirect targeting the same trigger
    name, internal-mode sidechains, etc.) are out of scope for v1 — the
    redirect case is ambiguous (the dynamics decision may already
    operate on the post-redirect state) and would warn at most.
    """
    dynamics = bp.dynamics_corrective
    routing = bp.routing
    assert dynamics is not None and routing is not None  # decorator-guaranteed

    removed_triggers: set[str] = {
        repair.current_trigger
        for repair in routing.value.repairs
        if repair.fix_type == "sidechain_remove"
        and repair.current_trigger is not None
    }
    if not removed_triggers:
        return None

    for correction in dynamics.value.corrections:
        sc = correction.sidechain
        if sc is None or sc.mode != "external" or sc.trigger_track is None:
            continue
        if sc.trigger_track in removed_triggers:
            return MixCohesionViolation(
                rule="sidechain_target_exists_in_routing",
                severity="block",
                message=(
                    f"DynamicsCorrection on track {correction.track!r} uses "
                    f"external sidechain triggered by {sc.trigger_track!r}, "
                    f"but routing.repairs contains a sidechain_remove on "
                    f"trigger {sc.trigger_track!r}. Tier B would write a "
                    f"Compressor2 sidechain block with no live input. "
                    f"Either drop the dynamics correction OR drop the "
                    f"routing remove."
                ),
                lanes=("dynamics_corrective", "routing"),
            )
    return None


@mix_cohesion_rule(lanes=("automation", "chain"))
def automation_envelope_targets_active_param(
    bp: MixBlueprint,
) -> Optional[MixCohesionViolation]:
    """Block when an automation envelope (or BandTrack) targets a device
    that the matching ``chain`` plan does not contain.

    Failure mode caught :
        automation-engineer says "envelope Eq8 instance 1 band 2 Gain on
        track 'Bass'" while chain-builder's plan for 'Bass' contains
        only ONE Eq8 (instance 0). Tier B (automation-writer) skips with
        reason ; the user gets a silent partial mix.

    What we DO check :
    - For each AutomationEnvelope and each BandTrack, the target track's
      chain plan must contain the required (target_device,
      target_device_instance) pair.
    - Both ``envelopes[]`` and ``band_tracks[]`` are validated. For
      band_tracks the device is implicit "Eq8" and the instance comes
      from ``target_eq8_instance``.

    What we INTENTIONALLY skip (out of scope, would be false positives) :
    - ``target_track == "Master"`` : the master bus is not modeled in
      chain.plans (mastering writer handles it directly via MainTrack).
    - Tracks that have no entry in chain.plans : chain-builder didn't
      decide on them, so the envelope may legitimately target a device
      pre-existing in the .als chain. Defer validation to runtime
      (automation-writer reports `envelopes_skipped` at apply time).
    - ``target_param`` validity : not checked here — the device-mapping
      oracle (or the writer's per-device validator) catches that ; we'd
      duplicate the param schema badly.
    """
    automation = bp.automation
    chain = bp.chain
    assert automation is not None and chain is not None  # decorator-guaranteed

    # {track_name: {device_name: {instance values present in plan}}}
    available: dict[str, dict[str, set[int]]] = {}
    for plan in chain.value.plans:
        per_device: dict[str, set[int]] = {}
        for slot in plan.slots:
            per_device.setdefault(slot.device, set()).add(slot.instance)
        available[plan.track] = per_device

    def _check(
        target_track: str,
        target_device: str,
        target_instance: int,
        kind: str,
        identifier: str,
    ) -> Optional[str]:
        if target_track == "Master":
            return None
        per_device = available.get(target_track)
        if per_device is None:
            return None  # no chain plan for this track ; defer to runtime
        present_instances = per_device.get(target_device, set())
        if not present_instances:
            return (
                f"{kind} {identifier} targets {target_device} on track "
                f"{target_track!r}, but the chain plan for {target_track!r} "
                f"has no {target_device} slot. Tier B would skip the envelope."
            )
        if target_instance not in present_instances:
            return (
                f"{kind} {identifier} targets {target_device}#{target_instance} "
                f"on track {target_track!r}, but the chain plan for "
                f"{target_track!r} only has {target_device} at instance(s) "
                f"{sorted(present_instances)}."
            )
        return None

    for i, env in enumerate(automation.value.envelopes):
        msg = _check(
            env.target_track, env.target_device, env.target_device_instance,
            kind="AutomationEnvelope",
            identifier=f"#{i} (param={env.target_param!r})",
        )
        if msg is not None:
            return MixCohesionViolation(
                rule="automation_envelope_targets_active_param",
                severity="block",
                message=msg,
                lanes=("automation", "chain"),
            )

    for i, bt in enumerate(automation.value.band_tracks):
        msg = _check(
            bt.target_track, "Eq8", bt.target_eq8_instance,
            kind="BandTrack",
            identifier=f"#{i} (band={bt.target_band_index})",
        )
        if msg is not None:
            return MixCohesionViolation(
                rule="automation_envelope_targets_active_param",
                severity="block",
                message=msg,
                lanes=("automation", "chain"),
            )

    return None


# Compressor-family device names. Reuse only here ; if other rules need
# this list later we can promote it to schema.py.
_DYNAMICS_DEVICES_THAT_AMPLIFY_PRE_EQ_NOISE: frozenset[str] = frozenset({
    "Compressor2",
    "GlueCompressor",
})


@mix_cohesion_rule(lanes=("chain",))
def chain_order_respects_signal_flow(
    bp: MixBlueprint,
) -> Optional[MixCohesionViolation]:
    """Warn when a chain plan places corrective EQ AFTER a compressor on
    the same track.

    Audio rationale :
        Corrective EQ removes problem frequencies (resonances, mud,
        sibilance). If you compress FIRST, the compressor grabs those
        problem freqs along with the rest of the signal and amplifies
        their relative weight in the residual. The downstream EQ then
        cuts them, but the dynamic damage (pumping, transient
        flattening) is already baked in. Canonical signal flow puts
        corrective EQ BEFORE compression.

    Severity is **warn**, not block : creative chain orderings exist
    (e.g., parallel comp on a Group with EQ taste afterwards) and we
    don't want to halt the apply on a stylistic call. The cohesion
    report surfaces the issue ; user decides.

    What we DO check :
    - Per chain plan, find slots that are :
        * is_preexisting=False AND device == "Eq8"
          AND consumes_lane == "eq_corrective"
        * is_preexisting=False AND device IN
          _DYNAMICS_DEVICES_THAT_AMPLIFY_PRE_EQ_NOISE
    - If ANY corrective EQ slot's position > ANY compressor slot's
      position on the same track → warn (one violation per blueprint,
      first match wins).

    What we INTENTIONALLY skip :
    - Pre-existing slots (is_preexisting=True) — we can't know what
      they're doing semantically (consumes_lane is None)
    - Eq8 slots whose consumes_lane != "eq_corrective" — creative EQ
      AFTER compression is a legitimate flavour move
    - Limiter/Gate/DrumBuss positioning — out of scope for v1 (the
      Limiter terminal-position rule is enforced upstream by the
      chain-builder parser)
    """
    chain = bp.chain
    assert chain is not None  # decorator-guaranteed

    for plan in chain.value.plans:
        corrective_eq_positions: list[int] = []
        compressor_positions: list[int] = []
        for slot in plan.slots:
            if slot.is_preexisting:
                continue
            if (slot.device == "Eq8"
                    and slot.consumes_lane == "eq_corrective"):
                corrective_eq_positions.append(slot.position)
            elif slot.device in _DYNAMICS_DEVICES_THAT_AMPLIFY_PRE_EQ_NOISE:
                compressor_positions.append(slot.position)

        if not corrective_eq_positions or not compressor_positions:
            continue

        first_comp = min(compressor_positions)
        late_eqs = [p for p in corrective_eq_positions if p > first_comp]
        if late_eqs:
            return MixCohesionViolation(
                rule="chain_order_respects_signal_flow",
                severity="warn",
                message=(
                    f"Track {plan.track!r} : corrective Eq8 at position(s) "
                    f"{late_eqs} is placed AFTER a compressor at position "
                    f"{first_comp}. Canonical signal flow puts corrective EQ "
                    f"BEFORE compression so the comp doesn't amplify the "
                    f"problem freqs that the EQ is meant to remove. If this "
                    f"order is intentional (parallel processing, creative "
                    f"chain) flag it in the chain plan rationale ; otherwise "
                    f"swap the slot positions."
                ),
                lanes=("chain",),
            )
    return None
