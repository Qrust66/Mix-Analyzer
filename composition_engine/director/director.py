"""Director — the conductor of the per-sphere agents.

The Director is *not* a creative agent. It is a thin orchestrator with two
responsibilities:

    1. Make sure the right sphere agent runs at the right time (DAG of
       sphere dependencies).
    2. Aggregate the per-sphere Decisions into a complete SectionBlueprint
       and run cohesion checks. Loop until clean or budget exhausted.

Two modes:

- DirectorMode.GHOST  — accept a pre-filled SectionBlueprint, run cohesion
                        only. No LLM. Used for testing the pipeline and for
                        manual override of any sphere.
- DirectorMode.LIVE   — invoke per-sphere subagents (Phase 2+). Currently
                        raises NotImplementedError.

Sphere dependency graph (Phase 1 design):

    structure  ──┐
                 ├──> arrangement ──> dynamics ──> performance ──> fx
    harmony    ──┤
    rhythm     ──┘

  - structure is the macro shape; arrangement layers within it.
  - harmony and rhythm are independent of structure but feed arrangement.
  - dynamics shapes arrangement over time.
  - performance and fx are surface concerns, applied last.

The DAG is encoded in `SPHERE_DEPENDENCIES` so that future live mode can
schedule agent invocations correctly.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from composition_engine.blueprint.cohesion import CohesionReport, check_cohesion
from composition_engine.blueprint.schema import SPHERES, SectionBlueprint


# ============================================================================
# Sphere DAG
# ============================================================================
#
# Each entry maps a sphere to the set of spheres that must complete before
# it can run. Used by the live-mode scheduler. Ghost mode ignores the DAG
# (the user pre-fills everything).

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
        # Pick spheres whose deps are all already done (or not requested)
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
        # Process the lowest-priority ready sphere first (stable)
        next_sphere = ready[0]
        done.append(next_sphere)
        remaining.discard(next_sphere)
    return tuple(done)


# ============================================================================
# Director
# ============================================================================


class DirectorMode(Enum):
    GHOST = "ghost"
    LIVE = "live"


@dataclass(frozen=True)
class CompositionResult:
    """The output of one Director.compose_section() call."""

    blueprint: SectionBlueprint
    cohesion: CohesionReport
    iterations: int  # how many cohesion loops the Director ran (0 in ghost)

    @property
    def ok(self) -> bool:
        return self.blueprint.is_complete() and self.cohesion.is_clean


class Director:
    """Orchestrate per-sphere agents into a coherent SectionBlueprint."""

    def __init__(
        self,
        mode: DirectorMode = DirectorMode.GHOST,
        max_cohesion_iterations: int = 3,
    ) -> None:
        self.mode = mode
        self.max_cohesion_iterations = max_cohesion_iterations

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compose_section(
        self,
        name: str,
        brief: str,
        references: tuple[str, ...] = (),
        previous_sections: tuple[SectionBlueprint, ...] = (),
        ghost_blueprint: Optional[SectionBlueprint] = None,
    ) -> CompositionResult:
        """Run the per-section orchestration loop.

        Phase 1: ghost mode requires `ghost_blueprint`. The Director
        validates it (cohesion check) and returns. No LLM is invoked.

        Phase 2+: live mode will dispatch sphere agents in topological
        order, merge their outputs, and re-run cohesion until clean or
        max_cohesion_iterations is reached.
        """
        if self.mode is DirectorMode.GHOST:
            return self._ghost_compose(name, brief, references, ghost_blueprint)
        if self.mode is DirectorMode.LIVE:
            return self._live_compose(name, brief, references, previous_sections)
        raise ValueError(f"Unknown mode: {self.mode}")

    # ------------------------------------------------------------------
    # Ghost mode (Phase 1)
    # ------------------------------------------------------------------

    @staticmethod
    def _ghost_compose(
        name: str,
        brief: str,
        references: tuple[str, ...],
        ghost_blueprint: Optional[SectionBlueprint],
    ) -> CompositionResult:
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
        if not ghost_blueprint.brief and brief:
            ghost_blueprint = SectionBlueprint(
                name=ghost_blueprint.name,
                references=ghost_blueprint.references or references,
                brief=brief,
                previous_section_names=ghost_blueprint.previous_section_names,
                structure=ghost_blueprint.structure,
                harmony=ghost_blueprint.harmony,
                rhythm=ghost_blueprint.rhythm,
                arrangement=ghost_blueprint.arrangement,
                dynamics=ghost_blueprint.dynamics,
                performance=ghost_blueprint.performance,
                fx=ghost_blueprint.fx,
            )
        report = check_cohesion(ghost_blueprint)
        return CompositionResult(
            blueprint=ghost_blueprint,
            cohesion=report,
            iterations=0,
        )

    # ------------------------------------------------------------------
    # Live mode (Phase 2+)
    # ------------------------------------------------------------------

    def _live_compose(
        self,
        name: str,
        brief: str,
        references: tuple[str, ...],
        previous_sections: tuple[SectionBlueprint, ...],
    ) -> CompositionResult:
        raise NotImplementedError(
            "Live mode (LLM-driven sphere agents) is Phase 2+. "
            "For now use Director(mode=DirectorMode.GHOST) with a "
            "pre-filled blueprint."
        )
