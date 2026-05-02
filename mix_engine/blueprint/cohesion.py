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
| eq_cuts_redundant_across_tracks                   | warn     | eq_corrective (cluster across tracks) |
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


# ============================================================================
# Phase 4.19.4 — master_ceiling_below_minus_03_dbtp
# ============================================================================
#
# Streaming-codec safety ceiling. The PARSER allows up to MASTER_CEILING_MAX_DBTP
# = -0.1 dBTP (audio-physics PCM limit). Lossy codecs (mp3, AAC, Opus) however
# can produce inter-sample peaks +1-2 dB above the PCM peak ; mastering at
# -0.1 dBTP routinely clips on consumer playback gear after codec re-encoding.
# AES + Spotify Loudness Penalty + Apple Sound Check all converge on -0.3 dBTP
# as the conservative streaming-safe ceiling.
#
# This is a CONTEXT-DEPENDENT recommendation — CD/vinyl-only deliveries don't
# go through a lossy codec downstream and can legitimately push to -0.1 dBTP.
# That's why severity is "block" (per archi doc §7) WITH --force override
# rather than a hard parser bound.
_STREAMING_SAFE_CEILING_DBTP: float = -0.3


@mix_cohesion_rule(lanes=("mastering",))
def master_ceiling_below_minus_03_dbtp(
    bp: MixBlueprint,
) -> Optional[MixCohesionViolation]:
    """Block when any mastering ``limiter_target`` move sets a ceiling
    above -0.3 dBTP.

    See module-level comment for the audio rationale (streaming codec
    inter-sample peaks). Boundary semantics : strict ``>`` — exactly
    -0.3 dBTP does not fire.

    Empty mastering decisions (no moves), decisions without any
    ``limiter_target`` move, and ``limiter_target`` moves with
    ``ceiling_dbtp is None`` (Tier B picks default) all silently
    pass — there's nothing for cohesion to flag.

    --force override is the documented escape hatch for CD / vinyl /
    no-codec-downstream contexts.
    """
    mastering = bp.mastering
    assert mastering is not None  # decorator-guaranteed

    for i, move in enumerate(mastering.value.moves):
        if move.type != "limiter_target":
            continue
        if move.ceiling_dbtp is None:
            continue
        if move.ceiling_dbtp > _STREAMING_SAFE_CEILING_DBTP:
            return MixCohesionViolation(
                rule="master_ceiling_below_minus_03_dbtp",
                severity="block",
                message=(
                    f"limiter_target move #{i} on track {move.target_track!r} "
                    f"sets ceiling_dbtp={move.ceiling_dbtp} > "
                    f"{_STREAMING_SAFE_CEILING_DBTP} (streaming-safe ceiling). "
                    f"Lossy codecs (mp3/AAC/Opus) can produce inter-sample "
                    f"peaks +1-2 dB above the PCM ceiling, causing clipping "
                    f"on consumer playback. Lower the ceiling to <= "
                    f"{_STREAMING_SAFE_CEILING_DBTP} dBTP. For CD/vinyl-only "
                    f"deliveries (no codec downstream) this warning is "
                    f"informational — pass --force to apply anyway."
                ),
                lanes=("mastering",),
            )
    return None


# ============================================================================
# Phase 4.19.5 — eq_cuts_redundant_across_tracks
# ============================================================================
#
# Naming note : the original archi doc §7 listed this rule as
# "eq_cuts_dont_create_phase_holes_with_neighbours". After a Pass 2 audit it
# was renamed to "eq_cuts_redundant_across_tracks" because the
# phase-hole terminology is audio-incorrect : per-track EQ cuts on different
# tracks do NOT sum logarithmically into a deeper bus cut (the way intra-track
# stacked cuts would). Phase holes are comb filtering of correlated signals
# with time/phase offsets — a different physical phenomenon.
#
# What this rule TRULY catches is the redundant cleanup pattern : when N tracks
# all cut the same narrow freq band, the cleanup is often better expressed
# as a single bus EQ cut (cleaner, less phase smear from N filter passes,
# easier to revisit). Severity warn because cluster carving is sometimes
# intentional (carving space for a featured element).

# A "cut" is a band that drops gain enough to be musically audible. -3 dB is
# the perceptual threshold (3 dB doubling/halving rule of thumb).
_REDUNDANT_CUT_GAIN_THRESHOLD_DB: float = -3.0
# 1/3 octave window (factor 2^(1/3) ≈ 1.26). Two centre frequencies F1, F2 are
# considered "the same band" when F2/F1 ∈ [1/1.26, 1.26]. We implement that
# by checking whether F2 falls inside the window [F1 / 2^(1/6), F1 * 2^(1/6)]
# (centred ±1/6 octave) which is identical mathematically.
_REDUNDANT_CUT_HALF_OCTAVE_WINDOW: float = 2.0 ** (1.0 / 6.0)
# Minimum number of distinct tracks in the cluster to fire the warning. 2 is
# the natural threshold (1 track cutting a freq is just a normal EQ move).
_REDUNDANT_CUT_MIN_TRACKS: int = 2


@mix_cohesion_rule(lanes=("eq_corrective",))
def eq_cuts_redundant_across_tracks(
    bp: MixBlueprint,
) -> Optional[MixCohesionViolation]:
    """Warn when the same narrow freq band is being cut on multiple tracks.

    Audio rationale (the HONEST version) :
        When tracks A, B, C all cut a bell at ~250 Hz, the cleanup is
        often better done with a SINGLE bus EQ cut. Reasons :
        (1) one filter pass instead of N → less cumulative phase smear ;
        (2) one place to revisit if the cut needs adjustment ;
        (3) addresses a bus-level masking issue at the bus, not by
        guessing which tracks contribute the freq buildup.

    This is NOT a phase-hole detector — per-track EQ cuts on DIFFERENT
    tracks do not sum logarithmically into a deeper bus cut. The
    original archi doc name was audio-incorrect ; renamed in Phase
    4.19.5 audit cycle.

    What we DO check :
    - Filter to bell cuts (band_type == "bell" AND intent == "cut" AND
      gain_db <= -3 dB)
    - For each band's centre freq, find all OTHER bands within ±1/6
      octave (total 1/3 octave window)
    - If the cluster includes ≥ 2 distinct tracks → warn (one cluster
      per blueprint, first match wins)

    What we INTENTIONALLY skip :
    - Non-bell band types (shelves and filters span wide ranges, not
      narrow cluster targets)
    - Boost bands (intent != "cut" — different concern)
    - Shallow cuts (gain_db > -3 dB — under perceptual threshold)
    - Single-track clusters (one track cutting a freq is normal EQ)
    """
    eq = bp.eq_corrective
    assert eq is not None  # decorator-guaranteed

    bell_cuts = [
        band for band in eq.value.bands
        if band.band_type == "bell"
        and band.intent == "cut"
        and band.gain_db <= _REDUNDANT_CUT_GAIN_THRESHOLD_DB
    ]
    if len(bell_cuts) < _REDUNDANT_CUT_MIN_TRACKS:
        return None

    # Sort by centre freq to make cluster walking deterministic.
    sorted_cuts = sorted(bell_cuts, key=lambda b: b.center_hz)

    for anchor in sorted_cuts:
        if anchor.center_hz <= 0:
            continue
        f_lo = anchor.center_hz / _REDUNDANT_CUT_HALF_OCTAVE_WINDOW
        f_hi = anchor.center_hz * _REDUNDANT_CUT_HALF_OCTAVE_WINDOW
        cluster = [
            b for b in sorted_cuts
            if f_lo <= b.center_hz <= f_hi
        ]
        cluster_tracks = sorted({b.track for b in cluster})
        if len(cluster_tracks) < _REDUNDANT_CUT_MIN_TRACKS:
            continue
        # Geometric mean of cluster freqs is a stable cluster centre summary.
        product = 1.0
        for b in cluster:
            product *= b.center_hz
        cluster_centre_hz = product ** (1.0 / len(cluster))
        return MixCohesionViolation(
            rule="eq_cuts_redundant_across_tracks",
            severity="warn",
            message=(
                f"{len(cluster_tracks)} tracks ({cluster_tracks}) all cut a "
                f"bell band within 1/3 octave of {cluster_centre_hz:.0f} Hz. "
                f"Often this pattern is cleaner expressed as a single bus EQ "
                f"cut (one filter pass, less cumulative phase smear, one "
                f"place to revisit). If each track really has the freq "
                f"problem independently (e.g., shared resonance from same "
                f"sample/synth) ignore this warning."
            ),
            lanes=("eq_corrective",),
        )
    return None
