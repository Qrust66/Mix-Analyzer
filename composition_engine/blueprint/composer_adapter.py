"""Composer adapter — Phase 2.1 of the multi-agent composition system.

Converts a SectionBlueprint (declarative description from sphere agents)
into a Composition (the dataclass that composer.compose() consumes).

Phase 2.1 scope (intentionally minimal):
- Only the four essential spheres are wired: structure, harmony, rhythm,
  arrangement. The other three (dynamics, performance, fx) are not yet
  consumed — they will be Phase 2.2+ as their downstream consumers
  (envelope shaping, humanization, FX rendering) get built or surfaced.
- Each blueprint LayerSpec produces a default motif based on its role
  (drum_kit / bass / lead / pad / etc.). These are placeholder motifs —
  Phase 2.2+ will let sphere agents generate richer note patterns.
- The composer pipeline (resolve_recipe_set, layer_track,
  finalization_pass) is reused as-is. No modification to composer.compose().

Public API:
    key_root_to_midi(key_root, octave=3) -> int
    blueprint_to_composition(bp) -> Composition
    compose_from_blueprint(bp) -> dict (composer's output dict)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List

from composition_engine.blueprint.midi_export import write_midi_file
from composition_engine.blueprint.schema import (
    LayerSpec as BlueprintLayer,
    SectionBlueprint,
)
from composition_engine.composer.composer import Composition, compose
from composition_engine.composer.track_layerer import LayerSpec as ComposerLayer

_LOG = logging.getLogger(__name__)


# ============================================================================
# Note-name → MIDI pitch class
# ============================================================================

_NOTE_TO_PITCH_CLASS: Dict[str, int] = {
    "C": 0, "C#": 1, "Db": 1,
    "D": 2, "D#": 3, "Eb": 3,
    "E": 4,
    "F": 5, "F#": 6, "Gb": 6,
    "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10,
    "B": 11,
}


def key_root_to_midi(key_root: str, octave: int = 3) -> int:
    """Convert a key-root letter to a MIDI pitch.

    'A' at default octave 3 → 57 (A3). 'C' → 48 (C3). 'F#' → 54.

    Falls back to C tonic if the key_root is unrecognized — defensive,
    not strict, because key_root may come from prose data with formatting
    quirks ('F#m', 'A minor', etc.). Strip flatness/minor markers first
    via key_root.replace('m', '').strip().split()[0] if needed.
    """
    pitch_class = _NOTE_TO_PITCH_CLASS.get(key_root, 0)
    # MIDI: C-1 = 0, so C{octave} = 12 * (octave + 1) + 0
    return 12 * (octave + 1) + pitch_class


# ============================================================================
# Default motif renderers per role
# ============================================================================
#
# These are placeholder motifs. They produce note-lists at time 0 that the
# track_layerer will then place at each cycle position across the layer's
# active bar range. Phase 2.2+ will replace these with sphere-agent-generated
# motifs.
#
# Each renderer takes a cycle_idx (which the track_layerer passes) and returns
# a list of note dicts: {'time', 'duration', 'velocity', 'pitch'}.


def _drum_kit_motif(tonic_pitch: int) -> Callable[[int], List[Dict[str, Any]]]:
    """Four-on-the-floor kick on a four-beat cycle. MIDI pitch 36 (kick)."""
    def render(cycle_idx: int) -> List[Dict[str, Any]]:
        return [
            {"time": float(beat), "duration": 0.25, "velocity": 100, "pitch": 36}
            for beat in (0, 1, 2, 3)
        ]
    return render


def _bass_motif(tonic_pitch: int) -> Callable[[int], List[Dict[str, Any]]]:
    """Sustained tonic note one octave below the tonic, full cycle."""
    def render(cycle_idx: int) -> List[Dict[str, Any]]:
        return [{"time": 0.0, "duration": 4.0, "velocity": 90, "pitch": tonic_pitch - 12}]
    return render


def _lead_motif(tonic_pitch: int) -> Callable[[int], List[Dict[str, Any]]]:
    """Single 5th-above note, quarter-note duration on beat 1."""
    def render(cycle_idx: int) -> List[Dict[str, Any]]:
        return [{"time": 0.0, "duration": 1.0, "velocity": 80, "pitch": tonic_pitch + 7}]
    return render


def _pad_motif(tonic_pitch: int) -> Callable[[int], List[Dict[str, Any]]]:
    """Sustained minor triad (root + minor 3rd + 5th) for the full cycle."""
    def render(cycle_idx: int) -> List[Dict[str, Any]]:
        return [
            {"time": 0.0, "duration": 4.0, "velocity": 70, "pitch": tonic_pitch + interval}
            for interval in (0, 3, 7)
        ]
    return render


def _default_motif(tonic_pitch: int) -> Callable[[int], List[Dict[str, Any]]]:
    """Single tonic note for the cycle — fallback for unknown roles."""
    def render(cycle_idx: int) -> List[Dict[str, Any]]:
        return [{"time": 0.0, "duration": 4.0, "velocity": 80, "pitch": tonic_pitch}]
    return render


def _motif_for_role(role: str, tonic_pitch: int) -> Callable[[int], List[Dict[str, Any]]]:
    """Pick a placeholder motif renderer based on the layer's role string."""
    role_lc = (role or "").lower()
    if any(kw in role_lc for kw in ("drum", "kit", "kick", "perc")):
        return _drum_kit_motif(tonic_pitch)
    if any(kw in role_lc for kw in ("bass", "sub")):
        return _bass_motif(tonic_pitch)
    if any(kw in role_lc for kw in ("lead", "melody", "vocal")):
        return _lead_motif(tonic_pitch)
    if any(kw in role_lc for kw in ("pad", "chord", "harmony")):
        return _pad_motif(tonic_pitch)
    return _default_motif(tonic_pitch)


# ============================================================================
# Blueprint → Composition
# ============================================================================


def blueprint_to_composition(bp: SectionBlueprint) -> Composition:
    """Convert a SectionBlueprint into a composer Composition.

    Phase 2.1 minimum-viable: maps the essential sphere decisions
    (structure, harmony, rhythm, arrangement) into a Composition that
    composer.compose() can render. The other three spheres (dynamics,
    performance, fx) are not yet consumed.

    Raises ValueError if any of the four essential spheres is unfilled.
    """
    missing = [
        s for s in ("structure", "harmony", "rhythm", "arrangement")
        if getattr(bp, s) is None
    ]
    if missing:
        raise ValueError(
            f"Cannot compose: missing essential sphere(s) {missing}. "
            f"Phase 2.1 requires structure, harmony, rhythm, arrangement to be filled."
        )

    # Asserts for type narrowing — guaranteed not None by the check above.
    assert bp.structure is not None
    assert bp.harmony is not None
    assert bp.rhythm is not None
    assert bp.arrangement is not None

    structure = bp.structure.value
    harmony = bp.harmony.value
    rhythm = bp.rhythm.value
    arrangement = bp.arrangement.value

    # Phase 2.1 only consumes the 4 essential spheres. If the caller filled
    # dynamics / performance / fx, log it explicitly so they don't think
    # those decisions are silently being applied.
    not_yet_wired = [
        s for s in ("dynamics", "performance", "fx")
        if getattr(bp, s) is not None
    ]
    if not_yet_wired:
        _LOG.warning(
            "[composer_adapter] Phase 2.1 ignores sphere(s) %s — values present "
            "in the blueprint but not yet applied to the rendered output. "
            "Phase 2.2+ will wire them.",
            not_yet_wired,
        )

    tonic_pitch = key_root_to_midi(harmony.key_root, octave=3)

    # Group blueprint layers by their role string into "tracks" the composer
    # expects. Multiple layers with the same role share a track.
    layers_per_track: Dict[str, List[ComposerLayer]] = {}
    for bp_layer in arrangement.layers:
        track_name = (bp_layer.role or "default").upper().replace(" ", "_")
        composer_layer = ComposerLayer(
            motif_render_func=_motif_for_role(bp_layer.role, tonic_pitch),
            motif_id=f"{bp_layer.role}_{bp_layer.instrument}".replace(" ", "_"),
            # The composer's track_layerer uses 1-indexed bar positions; the
            # blueprint uses 0-indexed. Shift by +1.
            entry_at_bar=bp_layer.enters_at_bar + 1,
            exit_at_bar=bp_layer.exits_at_bar + 1,
            cycle_duration_beats=4.0,
            base_volume=bp_layer.base_velocity / 127.0,
            target_track=track_name,
        )
        layers_per_track.setdefault(track_name, []).append(composer_layer)

    return Composition(
        recipe_ids=[],  # blueprint-driven; no advisor recipes consulted
        tonic_pitch=tonic_pitch,
        total_bars=structure.total_bars,
        tempo_bpm=float(rhythm.tempo_bpm),
        layers_per_track=layers_per_track,
        apply_finalization=True,
        rng_seed=0,
    )


def compose_from_blueprint(bp: SectionBlueprint) -> Dict[str, Any]:
    """Render a SectionBlueprint into the composer's output dict.

    Equivalent to:
        composition = blueprint_to_composition(bp)
        return compose(composition)
    """
    return compose(blueprint_to_composition(bp))


def compose_to_midi(bp: SectionBlueprint, output_path: str | Path) -> Path:
    """Render a SectionBlueprint all the way to a Standard MIDI File.

    The full Phase 2.1 pipeline:

        SectionBlueprint
            ↓ blueprint_to_composition
        Composition
            ↓ compose (track_layerer, finalization)
        {tracks, tempo_bpm, …}
            ↓ write_midi_file
        .mid file on disk

    Args:
        bp: complete SectionBlueprint with at least the 4 essential
            spheres filled (structure, harmony, rhythm, arrangement).
        output_path: destination .mid path.

    Returns:
        The Path written.
    """
    result = compose_from_blueprint(bp)
    return write_midi_file(
        tracks=result["tracks"],
        output_path=output_path,
        tempo_bpm=float(result["tempo_bpm"]),
    )


__all__ = [
    "key_root_to_midi",
    "blueprint_to_composition",
    "compose_from_blueprint",
    "compose_to_midi",
]
