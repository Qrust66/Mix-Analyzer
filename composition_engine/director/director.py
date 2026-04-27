"""Director — the conductor of the per-sphere agents.

The Director is *not* a creative agent. It is a thin orchestrator with two
responsibilities:

    1. Make sure the right sphere agent runs at the right time (DAG of
       sphere dependencies).
    2. Aggregate the per-sphere Decisions into a complete SectionBlueprint
       and run cohesion checks.

Phase 1 ships ghost mode only: the Director accepts a hand-filled
SectionBlueprint and runs cohesion checks on it. No LLM. This validates
the entire blueprint -> composer -> .als pipeline before any agent is
wired in. Live mode (LLM-driven sphere agents) lands in Phase 2 with the
agents themselves; we add the API surface then.

Sphere dependency graph:

    structure  ──┐
                 ├──> arrangement ──> dynamics ──> performance ──> fx
    harmony    ──┤
    rhythm     ──┘

  - structure is the macro shape; arrangement layers within it.
  - harmony and rhythm are independent of structure but feed arrangement.
  - dynamics shapes arrangement over time.
  - performance and fx are surface concerns, applied last.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional

from composition_engine.blueprint.cohesion import CohesionReport, check_cohesion
from composition_engine.blueprint.schema import SPHERES, SectionBlueprint


SPHERE_DEPENDENCIES: dict[str, frozenset[str]] = {
    "structure": frozenset(),
    "harmony": frozenset(),
    "rhythm": frozenset(),
    "arrangement": frozenset({"structure", "harmony", "rhythm"}),
    "dynamics": frozenset({"structure", "arrangement"}),
    "performance": frozenset({"rhythm", "arrangement"}),
    "fx": frozenset({"arrangement", "dynamics"}),
}

assert set(SPHERE_DEPENDENCIES) == set(SPHERES), (
    "SPHERE_DEPENDENCIES is out of sync with the SPHERES tuple"
)


def topological_order(spheres: frozenset[str]) -> tuple[str, ...]:
    """Return a valid execution order for the given subset of spheres.

    Pure topological sort over SPHERE_DEPENDENCIES restricted to `spheres`.
    Deterministic (stable order matches the SPHERES tuple).
    """
    remaining = set(spheres)
    done: list[str] = []
    while remaining:
        ready = [
            s
            for s in SPHERES
            if s in remaining
            and all(d in done or d not in spheres for d in SPHERE_DEPENDENCIES[s])
        ]
        if not ready:
            raise ValueError(
                f"Cycle in SPHERE_DEPENDENCIES restricted to {spheres}; "
                f"already done: {done}"
            )
        done.append(ready[0])
        remaining.discard(ready[0])
    return tuple(done)


class DirectorMode(Enum):
    GHOST = "ghost"


@dataclass(frozen=True)
class CompositionResult:
    """The output of one Director.compose_section() call."""

    blueprint: SectionBlueprint
    cohesion: CohesionReport

    @property
    def ok(self) -> bool:
        return self.blueprint.is_complete() and self.cohesion.is_clean


class Director:
    """Orchestrate per-sphere agents into a coherent SectionBlueprint."""

    def __init__(self, mode: DirectorMode = DirectorMode.GHOST) -> None:
        self.mode = mode

    def compose_section(
        self,
        name: str,
        brief: str,
        references: tuple[str, ...] = (),
        ghost_blueprint: Optional[SectionBlueprint] = None,
    ) -> CompositionResult:
        """Run the per-section orchestration loop.

        Phase 1 (ghost mode): requires `ghost_blueprint`. The Director
        validates it and returns. No LLM is invoked.
        """
        if self.mode is not DirectorMode.GHOST:
            raise ValueError(f"Unknown mode: {self.mode}")
        if ghost_blueprint is None:
            raise ValueError(
                "Director(mode=GHOST) requires `ghost_blueprint` to be provided."
            )
        if ghost_blueprint.name != name:
            raise ValueError(
                f"Ghost blueprint name {ghost_blueprint.name!r} does not match "
                f"requested section name {name!r}."
            )

        # Light enrichment: stash brief and references onto the blueprint if
        # they were not already set, so downstream tools see consistent data.
        enriched = ghost_blueprint
        if not enriched.brief and brief:
            enriched = replace(enriched, brief=brief)
        if not enriched.references and references:
            enriched = replace(enriched, references=references)

        return CompositionResult(
            blueprint=enriched,
            cohesion=check_cohesion(enriched),
        )
