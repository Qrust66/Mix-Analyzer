"""Mix-side cohesion checks — declarative cross-lane rules.

Mirrors composition_engine.blueprint.cohesion. A "mix cohesion rule" is a
predicate that takes a MixBlueprint and returns either None (cohesive)
or a MixCohesionViolation. Rules are auto-collected via the
@mix_cohesion_rule decorator and skipped silently when their required
lanes aren't filled.

Phase 4.0 ships only the infrastructure. Concrete rules land alongside
the agent that motivates them — rule-with-consumer principle, identical
to the composition side.

Future rules expected (none implemented yet):

| Rule                                              | Severity | Lanes |
|---------------------------------------------------|----------|-------|
| eq_cuts_dont_create_phase_holes_with_neighbours   | warn     | eq_corrective × eq_corrective (cross-track) |
| sidechain_target_exists_in_routing                | block    | dynamics_corrective × routing |
| master_ceiling_below_minus_03_dbtp                | block    | mastering |
| automation_envelope_targets_active_param          | block    | automation × any device |
| chain_order_respects_signal_flow                  | warn     | chain × all devices |
"""
from __future__ import annotations
