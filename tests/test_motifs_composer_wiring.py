"""Unit tests for the composer_adapter wiring of motif decisions
(Phase 2.7 + Phase 2.7.1 dynamics envelope).

These pin the agent-decision → composer plumbing so future refactors
of composer_adapter don't silently break it.
"""
import pytest

from composition_engine.blueprint import (
    Decision,
    DynamicsDecision,
    LayerMotif,
    MotifsDecision,
    Note,
)
from composition_engine.blueprint.composer_adapter import (
    _dynamics_velocity_multiplier,
    _find_layer_motif,
    _motif_render_from_decision,
)


# ============================================================================
# _motif_render_from_decision — basic mapping
# ============================================================================


def _make_motif(role="kick", instrument="kit", bars=(0, 1)) -> LayerMotif:
    return LayerMotif(
        layer_role=role,
        layer_instrument=instrument,
        notes=tuple(
            Note(bar=b, beat=0.0, pitch=36,
                 duration_beats=0.25, velocity=100)
            for b in bars
        ),
        rationale="adequate-length rationale that satisfies parser depth",
        inspired_by=(),
    )


def test_render_returns_notes_for_matching_bar():
    motif = _make_motif(bars=(0, 1, 2, 3))
    render = _motif_render_from_decision(motif)
    notes_bar0 = render(0)
    assert len(notes_bar0) == 1
    assert notes_bar0[0]["pitch"] == 36
    assert notes_bar0[0]["velocity"] == 100


def test_render_returns_empty_for_bar_with_no_notes():
    motif = _make_motif(bars=(0, 2))  # bars 1 and 3 empty
    render = _motif_render_from_decision(motif)
    assert render(1) == []
    assert render(3) == []


def test_render_returns_empty_for_bar_beyond_motif_range():
    motif = _make_motif(bars=(0, 1))
    render = _motif_render_from_decision(motif)
    assert render(5) == []


def test_render_independent_of_call_order():
    """Same cycle_idx returns same notes regardless of call sequence."""
    # Use distinct beats per bar so the lookup return values differ
    motif = LayerMotif(
        layer_role="kick", layer_instrument="kit",
        notes=(
            Note(bar=0, beat=0.0, pitch=36, duration_beats=0.25, velocity=100),
            Note(bar=2, beat=1.5, pitch=36, duration_beats=0.25, velocity=100),
        ),
        rationale="adequate-length rationale that satisfies parser depth",
        inspired_by=(),
    )
    render = _motif_render_from_decision(motif)
    a = render(0)
    b = render(2)
    a_again = render(0)
    assert a == a_again
    assert a != b
    assert a[0]["time"] == 0.0
    assert b[0]["time"] == 1.5


def test_render_returns_a_copy_not_the_internal_list():
    """Mutating the returned list must not affect later calls."""
    motif = _make_motif(bars=(0,))
    render = _motif_render_from_decision(motif)
    first = render(0)
    first.clear()  # mutate
    second = render(0)
    assert second != first  # second must still have notes


# ============================================================================
# _find_layer_motif — match priority
# ============================================================================


def test_find_layer_motif_exact_role_and_instrument_match():
    decision = MotifsDecision(by_layer=(
        _make_motif(role="kick", instrument="kit_a"),
        _make_motif(role="kick", instrument="kit_b"),
    ))
    found = _find_layer_motif(decision, "kick", "kit_b")
    assert found is not None
    assert found.layer_instrument == "kit_b"


def test_find_layer_motif_role_only_match_when_instrument_differs():
    """Composer falls back to role-only if instrument doesn't match."""
    decision = MotifsDecision(by_layer=(
        _make_motif(role="kick", instrument="kit_a"),
    ))
    found = _find_layer_motif(decision, "kick", "kit_unknown")
    assert found is not None
    assert found.layer_instrument == "kit_a"


def test_find_layer_motif_returns_none_for_unknown_role():
    decision = MotifsDecision(by_layer=(
        _make_motif(role="kick", instrument="kit"),
    ))
    found = _find_layer_motif(decision, "trumpet", "horn")
    assert found is None


def test_find_layer_motif_case_insensitive():
    decision = MotifsDecision(by_layer=(
        _make_motif(role="Kick", instrument="Kit"),
    ))
    found = _find_layer_motif(decision, "KICK", "kit")
    assert found is not None


# ============================================================================
# _dynamics_velocity_multiplier — Phase 2.7.1
# ============================================================================


def test_dynamics_multiplier_flat_returns_constant():
    dyn = Decision(
        value=DynamicsDecision(arc_shape="flat", start_db=-12.0, end_db=-12.0),
        sphere="dynamics",
    )
    a = _dynamics_velocity_multiplier(dyn, total_bars=4, bar_idx=0)
    b = _dynamics_velocity_multiplier(dyn, total_bars=4, bar_idx=3)
    assert a == b


def test_dynamics_multiplier_rising_increases_with_bar():
    dyn = Decision(
        value=DynamicsDecision(arc_shape="rising", start_db=-18.0, end_db=-6.0),
        sphere="dynamics",
    )
    bars = [
        _dynamics_velocity_multiplier(dyn, total_bars=4, bar_idx=b)
        for b in range(4)
    ]
    assert bars == sorted(bars)  # ascending
    assert bars[0] < bars[-1]


def test_dynamics_multiplier_descending_decreases_with_bar():
    dyn = Decision(
        value=DynamicsDecision(arc_shape="descending", start_db=-6.0, end_db=-18.0),
        sphere="dynamics",
    )
    bars = [
        _dynamics_velocity_multiplier(dyn, total_bars=4, bar_idx=b)
        for b in range(4)
    ]
    assert bars == sorted(bars, reverse=True)


def test_dynamics_multiplier_inflection_point_overrides_interpolation():
    """An inflection point on the queried bar wins over linear interp."""
    dyn = Decision(
        value=DynamicsDecision(
            arc_shape="rising", start_db=-18.0, end_db=-6.0,
            inflection_points=((2, 0.0),),  # 0 dB = max at bar 2
        ),
        sphere="dynamics",
    )
    interp_at_2 = _dynamics_velocity_multiplier(dyn, total_bars=4, bar_idx=2)
    # 0 dB → 1.0 multiplier (full velocity)
    assert interp_at_2 == pytest.approx(1.0, abs=0.001)


def test_dynamics_multiplier_none_returns_unity():
    """No dynamics → no-op multiplier."""
    assert _dynamics_velocity_multiplier(None, total_bars=4, bar_idx=0) == 1.0


def test_render_with_dynamics_clamps_velocity_to_midi_range():
    """Velocities post-multiplier must stay in [1, 127]."""
    motif = LayerMotif(
        layer_role="kick", layer_instrument="kit",
        notes=(Note(bar=0, beat=0.0, pitch=36, duration_beats=0.25, velocity=100),),
        rationale="adequate-length rationale that satisfies parser depth",
        inspired_by=(),
    )
    # -60 dB = silent ; multiplier ≈ 0.001 ; 100 * 0.001 = 0.1 → clamped to 1
    dyn = Decision(
        value=DynamicsDecision(arc_shape="flat", start_db=-60.0, end_db=-60.0),
        sphere="dynamics",
    )
    render = _motif_render_from_decision(motif, dynamics_decision=dyn, total_bars=4)
    notes = render(0)
    assert all(1 <= n["velocity"] <= 127 for n in notes)
