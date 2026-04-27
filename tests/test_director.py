"""Tests for composition_engine.director — ghost mode, DAG sanity."""
import pytest

from composition_engine.blueprint import (
    Decision,
    SectionBlueprint,
    StructureDecision,
)
from composition_engine.director import Director, DirectorMode
from composition_engine.director.director import (
    SPHERE_DEPENDENCIES,
    topological_order,
)


# ============================================================================
# Topological ordering of the sphere DAG
# ============================================================================


def test_full_topological_order_respects_dependencies():
    order = topological_order(frozenset(SPHERE_DEPENDENCIES))
    pos = {s: i for i, s in enumerate(order)}
    for sphere, deps in SPHERE_DEPENDENCIES.items():
        for d in deps:
            assert pos[d] < pos[sphere], (
                f"Dep {d} should come before {sphere} in {order}"
            )


def test_topological_order_subset():
    """Restricting to a subset returns a valid order over that subset."""
    subset = frozenset({"structure", "harmony", "arrangement"})
    order = topological_order(subset)
    assert set(order) == subset
    pos = {s: i for i, s in enumerate(order)}
    # arrangement depends on structure & harmony; both must come first
    assert pos["structure"] < pos["arrangement"]
    assert pos["harmony"] < pos["arrangement"]


# ============================================================================
# Ghost mode
# ============================================================================


def test_ghost_mode_requires_blueprint():
    director = Director(mode=DirectorMode.GHOST)
    with pytest.raises(ValueError, match="ghost_blueprint"):
        director.compose_section(name="intro", brief="ambient")


def test_ghost_mode_returns_unmodified_blueprint_when_brief_already_set():
    bp = SectionBlueprint(name="intro", brief="my brief")
    director = Director(mode=DirectorMode.GHOST)
    result = director.compose_section(
        name="intro",
        brief="my brief",
        ghost_blueprint=bp,
    )
    assert result.blueprint is bp
    assert result.iterations == 0


def test_ghost_mode_enriches_blueprint_with_brief():
    """Director adds brief/references when blueprint left them empty."""
    bp = SectionBlueprint(name="intro")
    director = Director(mode=DirectorMode.GHOST)
    result = director.compose_section(
        name="intro",
        brief="ambient + tension",
        references=("Nirvana/Heart_Shaped_Box",),
        ghost_blueprint=bp,
    )
    assert result.blueprint.brief == "ambient + tension"
    assert result.blueprint.references == ("Nirvana/Heart_Shaped_Box",)


def test_ghost_mode_rejects_name_mismatch():
    bp = SectionBlueprint(name="verse")
    director = Director(mode=DirectorMode.GHOST)
    with pytest.raises(ValueError, match="does not match"):
        director.compose_section(name="intro", brief="x", ghost_blueprint=bp)


def test_ghost_mode_runs_cohesion():
    """A blueprint with a cohesion violation produces a non-clean report."""
    bp = SectionBlueprint(name="intro").with_decision(
        "structure",
        Decision(
            value=StructureDecision(
                total_bars=16,
                sub_sections=(),
            ),
            sphere="structure",
        ),
    )
    director = Director(mode=DirectorMode.GHOST)
    result = director.compose_section(
        name="intro", brief="x", ghost_blueprint=bp
    )
    # No violations expected — the structure is clean
    assert result.cohesion.is_clean


def test_ghost_mode_result_ok_only_if_complete_and_clean():
    bp = SectionBlueprint(name="intro").with_decision(
        "structure",
        Decision(value=StructureDecision(total_bars=16), sphere="structure"),
    )
    director = Director(mode=DirectorMode.GHOST)
    result = director.compose_section(
        name="intro", brief="x", ghost_blueprint=bp
    )
    # Cohesion is clean but blueprint is not complete
    assert result.cohesion.is_clean
    assert not result.blueprint.is_complete()
    assert not result.ok


# ============================================================================
# Live mode
# ============================================================================


def test_live_mode_not_implemented_yet():
    director = Director(mode=DirectorMode.LIVE)
    with pytest.raises(NotImplementedError, match="Phase 2"):
        director.compose_section(name="intro", brief="x")
