"""Tests for composition_engine.blueprint.cohesion — rule registry,
partial-blueprint skipping, and the initial rule set."""
from composition_engine.blueprint import (
    ArrangementDecision,
    Decision,
    DynamicsDecision,
    HarmonyDecision,
    LayerSpec,
    SectionBlueprint,
    StructureDecision,
    SubSection,
    check_cohesion,
)


def _wrap(value, sphere: str) -> Decision:
    """Helper to wrap a sphere value in a minimal Decision."""
    return Decision(value=value, sphere=sphere)


def test_empty_blueprint_passes_cohesion_silently():
    bp = SectionBlueprint(name="intro")
    report = check_cohesion(bp)
    assert report.violations == ()
    assert report.is_clean


def test_cohesion_skips_rules_when_required_spheres_missing():
    """A rule that needs (arrangement, harmony) shouldn't fire when only
    arrangement is filled."""
    bp = SectionBlueprint(name="intro").with_decision(
        "arrangement",
        _wrap(ArrangementDecision(density_curve="sparse"), "arrangement"),
    )
    report = check_cohesion(bp)
    # Other rules might match the partial state (none should), but specifically
    # density_vs_harmonic_rhythm needs harmony too.
    assert all(v.rule != "density_vs_harmonic_rhythm" for v in report.violations)


def test_density_vs_harmonic_rhythm_fires_warning():
    bp = (
        SectionBlueprint(name="intro")
        .with_decision(
            "arrangement",
            _wrap(ArrangementDecision(density_curve="sparse"), "arrangement"),
        )
        .with_decision(
            "harmony",
            _wrap(
                HarmonyDecision(mode="Aeolian", key_root="A", harmonic_rhythm=2.0),
                "harmony",
            ),
        )
    )
    report = check_cohesion(bp)
    fired = [v for v in report.violations if v.rule == "density_vs_harmonic_rhythm"]
    assert len(fired) == 1
    assert fired[0].severity == "warn"
    assert report.is_clean  # warnings don't block


def test_dynamic_arc_within_section_bounds_blocks_invalid_peak():
    bp = (
        SectionBlueprint(name="intro")
        .with_decision(
            "structure", _wrap(StructureDecision(total_bars=16), "structure")
        )
        .with_decision(
            "dynamics",
            _wrap(DynamicsDecision(peak_bar=999), "dynamics"),  # out of range
        )
    )
    report = check_cohesion(bp)
    blockers = report.blockers
    assert len(blockers) == 1
    assert blockers[0].rule == "dynamic_arc_within_section_bounds"
    assert not report.is_clean


def test_layers_within_section_bounds_blocks_overflow():
    bp = (
        SectionBlueprint(name="verse")
        .with_decision(
            "structure", _wrap(StructureDecision(total_bars=16), "structure")
        )
        .with_decision(
            "arrangement",
            _wrap(
                ArrangementDecision(
                    layers=(
                        LayerSpec(
                            role="lead",
                            instrument="synth",
                            enters_at_bar=8,
                            exits_at_bar=32,  # past total_bars=16
                        ),
                    )
                ),
                "arrangement",
            ),
        )
    )
    report = check_cohesion(bp)
    assert any(v.rule == "layers_within_section_bounds" for v in report.blockers)


def test_sub_sections_within_total_blocks_invalid_subsection():
    bp = SectionBlueprint(name="intro").with_decision(
        "structure",
        _wrap(
            StructureDecision(
                total_bars=16,
                sub_sections=(
                    SubSection(name="bad", start_bar=20, end_bar=24),
                ),
            ),
            "structure",
        ),
    )
    report = check_cohesion(bp)
    assert any(v.rule == "sub_sections_within_total" for v in report.blockers)


def test_cohesion_report_separates_blockers_and_warnings():
    bp = (
        SectionBlueprint(name="intro")
        .with_decision(
            "structure", _wrap(StructureDecision(total_bars=16), "structure")
        )
        .with_decision(
            "arrangement",
            _wrap(ArrangementDecision(density_curve="sparse"), "arrangement"),
        )
        .with_decision(
            "harmony",
            _wrap(
                HarmonyDecision(mode="Aeolian", key_root="A", harmonic_rhythm=2.0),
                "harmony",
            ),
        )
        .with_decision(
            "dynamics",
            _wrap(DynamicsDecision(peak_bar=999), "dynamics"),
        )
    )
    report = check_cohesion(bp)
    assert len(report.warnings) >= 1
    assert len(report.blockers) >= 1
    assert not report.is_clean
