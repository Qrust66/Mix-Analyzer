"""Regression test for the Phase 2.7 fix in track_layerer.

`_bars_to_cycles(0)` originally returned 1 (because of `max(1, ...)`),
which caused even layers with `entry_fade_bars=0` to apply a 1-cycle
fade-in/fade-out, silently filtering out cycles 0 and N-1.

This test pins the fix so a future refactor doesn't accidentally
re-introduce the bug.
"""
from composition_engine.composer.track_layerer import LayerSpec, render_layer


def _flat_render(cycle_idx: int):
    """Trivial 4-note motif per cycle, all velocity 100."""
    return [
        {"time": float(i), "duration": 0.25, "velocity": 100, "pitch": 36}
        for i in range(4)
    ]


def test_zero_fade_bars_renders_all_cycles():
    """With entry_fade_bars=0 + exit_fade_bars=0, every cycle in range
    must produce notes — no silent fade-induced filtering."""
    spec = LayerSpec(
        motif_render_func=_flat_render,
        motif_id="test_no_fade",
        entry_at_bar=1, exit_at_bar=5,        # 4 active cycles
        cycle_duration_beats=4.0,
        base_volume=1.0,
        entry_fade_bars=0,                     # NO fade
        exit_fade_bars=0,                      # NO fade
        target_track="DRUM",
    )
    notes = render_layer(spec, tempo_bpm=120.0)
    # 4 cycles * 4 notes per cycle = 16 expected
    assert len(notes) == 16, (
        f"With zero fade bars, all cycles should render. Got {len(notes)} "
        f"notes — likely a regression of the Phase 2.7 fix in "
        f"_bars_to_cycles(0)."
    )


def test_explicit_fade_in_still_works():
    """If the user EXPLICITLY asks for a fade-in, the system must still
    apply it — the Phase 2.7 fix only changed zero-fade behavior."""
    spec = LayerSpec(
        motif_render_func=_flat_render,
        motif_id="test_with_fade",
        entry_at_bar=1, exit_at_bar=5,        # 4 active cycles
        cycle_duration_beats=4.0,
        base_volume=1.0,
        entry_fade_bars=2,                     # 2-bar fade-in requested
        exit_fade_bars=0,
        target_track="DRUM",
    )
    notes = render_layer(spec, tempo_bpm=120.0)
    # Fade-in IS applied — first cycle's notes have lower velocity than later
    assert len(notes) >= 4, "Fade-in shouldn't drop all notes"
    early = [n["velocity"] for n in notes if n["time"] < 4.0]
    late = [n["velocity"] for n in notes if n["time"] >= 8.0]
    if early and late:
        # Average velocity should rise from early to late (fade-in)
        assert sum(early) / len(early) < sum(late) / len(late)


def test_one_bar_layer_with_zero_fade_renders():
    """Edge case : a 1-cycle layer with no fade must render its single cycle."""
    spec = LayerSpec(
        motif_render_func=_flat_render,
        motif_id="single",
        entry_at_bar=1, exit_at_bar=2,        # 1 active cycle
        cycle_duration_beats=4.0,
        base_volume=1.0,
        entry_fade_bars=0, exit_fade_bars=0,
        target_track="DRUM",
    )
    notes = render_layer(spec, tempo_bpm=120.0)
    assert len(notes) == 4
