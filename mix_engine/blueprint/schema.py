"""Mix-side blueprint schema — design tenets parallel to composition_engine.

A `MixBlueprint` is the immutable, partial-fill-friendly carrier of every
decision a multi-agent mix session produces. Each lane (routing, EQ
corrective, dynamics, …) attaches its `MixDecision[T]` independently;
cohesion rules cross-check them after the fact.

Design tenets (identical to composition_engine.blueprint.schema):

1. **Immutability** — every dataclass is frozen, every collection a tuple.
2. **Provenance is first-class** — every decision carries citations to
   the diagnostic point or the device-mapping rule that motivates it.
3. **Partial-fill friendly** — every lane is Optional. Cohesion rules
   skip silently when their dependencies aren't filled yet.
4. **Read what's there, decide what to change** — mix agents start from
   the existing .als state (via `mix-diagnostician`) and propose
   *deltas*, not full re-syntheses. The blueprint records the deltas.

Phase 4.0 ships ONLY the foundation types (MixDecision, MixCitation,
MIX_LANES). The 12 lane-specific decision dataclasses (RoutingDecision,
EqCorrectiveDecision, …) are added one-by-one as their producing agent
materializes — same rule-with-consumer discipline as composition.
"""
from __future__ import annotations

from typing import Generic, Optional, TypeVar


# Mix lanes — keep in sync with the Mix Director DAG and the cohesion
# registry. Adding a lane requires also: adding the *Decision dataclass,
# extending MixBlueprint, updating MIX_DEPENDENCIES, and re-running tests.
MIX_LANES: tuple[str, ...] = (
    "diagnostic",
    "routing",
    "eq_corrective",
    "eq_creative",
    "dynamics_corrective",
    "saturation_color",
    "stereo_spatial",
    "automation",
    "chain",
    "mastering",
)


T = TypeVar("T")


# Phase 4.0 — types are sketched. Concrete dataclasses materialize as
# the producing agents land. Importing from here will work for the
# generic MixDecision/MixCitation; lane-specific types raise on import
# until added.

# from dataclasses import dataclass
# @dataclass(frozen=True)
# class MixCitation:
#     """A pointer back to the source that justified a mix decision —
#     a row in the Excel diagnostic, an entry in the device mapping,
#     or a passage from the mix engineer prompt PDF."""
#     source: str  # "diagnostic", "device_mapping", "pdf", "user_brief"
#     path: str    # locator inside the source
#     excerpt: str # the actual text/value cited

# @dataclass(frozen=True)
# class MixDecision(Generic[T]):
#     """The provenance-carrying envelope around any lane decision."""
#     value: T
#     lane: str
#     cited_by: tuple[MixCitation, ...] = ()
#     rationale: str = ""
#     confidence: float = 0.0
#     mode: str = ""  # "creative" | "corrective" — used by automation lane


# @dataclass(frozen=True)
# class MixBlueprint:
#     """The immutable carrier of all lane decisions for one mix session.
#
#     Like SectionBlueprint on the composition side, but for an existing
#     .als rather than a new one. The blueprint describes deltas to apply,
#     not absolute state.
#     """
#     name: str
#     # diagnostic: Optional[MixDecision[DiagnosticReport]] = None
#     # routing: Optional[MixDecision[RoutingDecision]] = None
#     # ... (12 lanes — added as agents land)


__all__ = ["MIX_LANES"]
