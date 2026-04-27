"""Tests for composition_engine.director — ghost mode, DAG sanity,
and a Phase 1 end-to-end smoke through a complete blueprint."""
import pytest

from composition_engine.blueprint import (
    ArrangementDecision,
    Citation,
    Decision,
    DynamicsDecision,
    FxDecision,
    HarmonyDecision,
    LayerSpec,
    PerformanceDecision,
    RhythmDecision,
    SectionBlueprint,
    StructureDecision,
    SubSection,
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
    assert pos["structure"] < pos["arrangement"]
    assert pos["harmony"] < pos["arrangement"]


def test_topological_order_singleton():
    order = topological_order(frozenset({"structure"}))
    assert order == ("structure",)


def test_topological_order_empty():
    assert topological_order(frozenset()) == ()


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
        name="intro", brief="my brief", ghost_blueprint=bp
    )
    assert result.blueprint is bp


def test_ghost_mode_enriches_blueprint_with_brief_and_references():
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


def test_ghost_mode_keeps_existing_references_over_new_ones():
    """If the blueprint already has references, the call argument doesn't override."""
    bp = SectionBlueprint(name="intro", references=("Original/Ref",))
    director = Director(mode=DirectorMode.GHOST)
    result = director.compose_section(
        name="intro",
        brief="x",
        references=("New/Ref",),
        ghost_blueprint=bp,
    )
    assert result.blueprint.references == ("Original/Ref",)


def test_ghost_mode_rejects_name_mismatch():
    bp = SectionBlueprint(name="verse")
    director = Director(mode=DirectorMode.GHOST)
    with pytest.raises(ValueError, match="does not match"):
        director.compose_section(name="intro", brief="x", ghost_blueprint=bp)


def test_ghost_mode_partial_blueprint_is_not_ok_but_passes_cohesion():
    bp = SectionBlueprint(name="intro").with_decision(
        "structure",
        Decision(value=StructureDecision(total_bars=16), sphere="structure"),
    )
    director = Director(mode=DirectorMode.GHOST)
    result = director.compose_section(name="intro", brief="x", ghost_blueprint=bp)
    assert result.cohesion.is_clean
    assert not result.blueprint.is_complete()
    assert not result.ok


# ============================================================================
# Phase 1 end-to-end — full pipeline on a complete blueprint
# (Uses the `complete_blueprint` fixture from tests/conftest.py.)
# ============================================================================


def test_full_pipeline_complete_blueprint_through_director_is_ok(complete_blueprint):
    """End-to-end: build a complete blueprint, run through Director ghost mode,
    verify the result is complete and cohesion-clean."""
    bp = complete_blueprint
    assert bp.is_complete()

    director = Director(mode=DirectorMode.GHOST)
    result = director.compose_section(
        name="intro",
        brief="ambient introspective intro",
        ghost_blueprint=bp,
    )

    assert result.blueprint.is_complete()
    assert result.cohesion.is_clean
    assert result.cohesion.violations == ()
    assert result.ok


def test_full_pipeline_provenance_is_preserved(complete_blueprint):
    """The Director must not strip provenance citations off Decisions."""
    bp = complete_blueprint
    director = Director(mode=DirectorMode.GHOST)
    result = director.compose_section(name="intro", brief="x", ghost_blueprint=bp)
    structure_dec = result.blueprint.structure
    assert structure_dec is not None
    assert len(structure_dec.inspired_by) == 1
    assert structure_dec.inspired_by[0].song == "Nirvana/Heart_Shaped_Box"
    assert structure_dec.rationale.startswith("16 bars split")
