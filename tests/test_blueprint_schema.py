"""Tests for composition_engine.blueprint.schema — immutability,
provenance, partial-fill semantics."""
import pytest

from composition_engine.blueprint import (
    SPHERES,
    Citation,
    Decision,
    HarmonyDecision,
    LayerSpec,
    SectionBlueprint,
    StructureDecision,
    SubSection,
)


def test_empty_blueprint_has_no_filled_spheres():
    bp = SectionBlueprint(name="intro")
    assert bp.filled_spheres() == ()
    assert bp.missing_spheres() == SPHERES
    assert not bp.is_complete()


def test_blueprint_is_immutable():
    bp = SectionBlueprint(name="intro")
    with pytest.raises(Exception):  # FrozenInstanceError
        bp.name = "verse"  # type: ignore[misc]


def test_with_decision_returns_new_blueprint():
    bp = SectionBlueprint(name="intro")
    dec = Decision(
        value=StructureDecision(total_bars=16),
        sphere="structure",
        rationale="stock 16-bar intro",
    )
    bp2 = bp.with_decision("structure", dec)
    assert bp.structure is None  # original untouched
    assert bp2.structure is dec
    assert "structure" in bp2.filled_spheres()


def test_with_decision_rejects_unknown_sphere():
    bp = SectionBlueprint(name="x")
    dec = Decision(value=None, sphere="nonexistent")
    with pytest.raises(ValueError, match="Unknown sphere"):
        bp.with_decision("nonexistent", dec)


def test_with_decision_rejects_sphere_mismatch():
    bp = SectionBlueprint(name="x")
    dec = Decision(value=None, sphere="harmony")
    with pytest.raises(ValueError, match="claims sphere"):
        bp.with_decision("structure", dec)


def test_decision_carries_provenance():
    cit = Citation(
        song="Nirvana/Heart_Shaped_Box",
        path="composition.harmonic_motion",
        excerpt="Modal Aeolian cycle...",
    )
    dec = Decision(
        value=HarmonyDecision(mode="Aeolian", key_root="A"),
        sphere="harmony",
        inspired_by=(cit,),
        rationale="Aeolian fits the introspective brief.",
        confidence=0.9,
    )
    assert dec.inspired_by == (cit,)
    assert dec.confidence == 0.9
    assert dec.value.mode == "Aeolian"


def test_complete_blueprint_recognized_as_complete():
    """A blueprint with all 7 spheres filled reports complete."""
    from composition_engine.blueprint import (
        ArrangementDecision,
        DynamicsDecision,
        FxDecision,
        PerformanceDecision,
        RhythmDecision,
    )
    bp = SectionBlueprint(name="intro")
    # Fill each sphere with a minimal Decision
    for sphere, value in [
        ("structure", StructureDecision(total_bars=16)),
        ("harmony", HarmonyDecision(mode="Aeolian", key_root="A")),
        ("rhythm", RhythmDecision(tempo_bpm=100)),
        ("arrangement", ArrangementDecision()),
        ("dynamics", DynamicsDecision()),
        ("performance", PerformanceDecision()),
        ("fx", FxDecision()),
    ]:
        bp = bp.with_decision(sphere, Decision(value=value, sphere=sphere))
    assert bp.is_complete()
    assert bp.missing_spheres() == ()
    assert set(bp.filled_spheres()) == set(SPHERES)


def test_layer_spec_is_value():
    """LayerSpec is hashable (frozen dataclass), enables set/dict membership."""
    a = LayerSpec(role="bass", instrument="sub", enters_at_bar=0, exits_at_bar=16)
    b = LayerSpec(role="bass", instrument="sub", enters_at_bar=0, exits_at_bar=16)
    assert a == b
    assert hash(a) == hash(b)


def test_sub_section_is_value():
    s1 = SubSection(name="build", start_bar=8, end_bar=16, role="build")
    s2 = SubSection(name="build", start_bar=8, end_bar=16, role="build")
    assert s1 == s2
    assert {s1, s2} == {s1}
