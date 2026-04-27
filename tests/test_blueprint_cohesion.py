"""Tests for composition_engine.blueprint.cohesion — the rule registry
infrastructure. Concrete rules are tested alongside the agents that
motivate them; Phase 1 only ships infrastructure."""
import pytest

from composition_engine.blueprint import (
    ArrangementDecision,
    Decision,
    HarmonyDecision,
    SectionBlueprint,
    StructureDecision,
    check_cohesion,
    cohesion_rule,
)
from composition_engine.blueprint.cohesion import _RULES, CohesionViolation


@pytest.fixture
def isolated_rules():
    """Save and restore _RULES so tests don't leak registrations into each other."""
    saved = list(_RULES)
    _RULES.clear()
    yield _RULES
    _RULES.clear()
    _RULES.extend(saved)


def _wrap(value, sphere: str) -> Decision:
    return Decision(value=value, sphere=sphere)


def test_empty_blueprint_passes_cohesion_silently(isolated_rules):
    bp = SectionBlueprint(name="intro")
    report = check_cohesion(bp)
    assert report.violations == ()
    assert report.is_clean


def test_cohesion_rule_decorator_registers_callable(isolated_rules):
    @cohesion_rule(spheres=("structure",))
    def my_rule(bp):
        return None

    assert my_rule in isolated_rules
    assert getattr(my_rule, "_spheres", None) == ("structure",)


def test_cohesion_runs_registered_rule_when_spheres_filled(isolated_rules):
    @cohesion_rule(spheres=("structure",))
    def total_bars_must_be_positive(bp):
        if bp.structure.value.total_bars <= 0:
            return CohesionViolation(
                rule="total_bars_must_be_positive",
                severity="block",
                message="bars must be > 0",
                spheres=("structure",),
            )
        return None

    bp = SectionBlueprint(name="x").with_decision(
        "structure", _wrap(StructureDecision(total_bars=0), "structure")
    )
    report = check_cohesion(bp)
    assert len(report.violations) == 1
    assert report.violations[0].rule == "total_bars_must_be_positive"
    assert not report.is_clean


def test_cohesion_skips_rules_when_required_spheres_missing(isolated_rules):
    """A rule needing (structure, harmony) is silently skipped when only
    structure is filled."""
    triggered = []

    @cohesion_rule(spheres=("structure", "harmony"))
    def needs_both(bp):
        triggered.append(True)
        return None

    bp = SectionBlueprint(name="x").with_decision(
        "structure", _wrap(StructureDecision(total_bars=16), "structure")
    )
    check_cohesion(bp)
    assert triggered == []  # rule was not invoked


def test_cohesion_skips_only_unsatisfied_rules(isolated_rules):
    """A rule whose deps ARE satisfied still runs even when other rules don't."""
    skipped = []
    ran = []

    @cohesion_rule(spheres=("structure", "harmony"))
    def skipped_rule(bp):
        skipped.append(True)
        return None

    @cohesion_rule(spheres=("structure",))
    def runs_rule(bp):
        ran.append(True)
        return None

    bp = SectionBlueprint(name="x").with_decision(
        "structure", _wrap(StructureDecision(total_bars=16), "structure")
    )
    check_cohesion(bp)
    assert ran == [True]
    assert skipped == []


def test_cohesion_report_separates_blockers_warnings_info(isolated_rules):
    @cohesion_rule(spheres=("structure",))
    def block_rule(bp):
        return CohesionViolation("block_rule", "block", "no", ("structure",))

    @cohesion_rule(spheres=("structure",))
    def warn_rule(bp):
        return CohesionViolation("warn_rule", "warn", "meh", ("structure",))

    @cohesion_rule(spheres=("structure",))
    def info_rule(bp):
        return CohesionViolation("info_rule", "info", "fyi", ("structure",))

    bp = SectionBlueprint(name="x").with_decision(
        "structure", _wrap(StructureDecision(total_bars=16), "structure")
    )
    report = check_cohesion(bp)
    assert len(report.blockers) == 1
    assert len(report.warnings) == 1
    assert not report.is_clean


def test_cohesion_passes_when_rule_returns_none(isolated_rules):
    @cohesion_rule(spheres=("structure", "harmony"))
    def always_clean(bp):
        return None

    bp = (
        SectionBlueprint(name="x")
        .with_decision(
            "structure", _wrap(StructureDecision(total_bars=16), "structure")
        )
        .with_decision(
            "harmony", _wrap(HarmonyDecision(mode="Aeolian", key_root="A"), "harmony")
        )
    )
    report = check_cohesion(bp)
    assert report.violations == ()
    assert report.is_clean


# Sanity: the production registry has no rules in Phase 1
def test_phase1_ships_no_concrete_rules():
    """Concrete cohesion rules will be added alongside their agent.
    Phase 1 must ship infrastructure only."""
    assert len(_RULES) == 0, (
        f"Phase 1 expected zero rules but found: {[r.__name__ for r in _RULES]}"
    )
