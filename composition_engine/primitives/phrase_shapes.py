"""Phrase-shape primitives — Phase 3-1 of composition_engine.

Higher-level operations that shape MUSICAL PHRASES (groups of notes) rather than
individual notes. Built ON TOP OF Phase-2 transforms.

Phrase-shape primitives:
    apply_arc_to_phrase          — combined velocity + register arc (rise then fall)
    apply_call_response          — combine two motifs as A → silence → B
    apply_tension_release        — route phrase from dissonant pitches to consonant resolution
    apply_phrase_breath          — insert breath (silence) at specific positions
    apply_dynamic_arc_section    — section-level density arc (intro→build→peak→resolve)
"""

from typing import List, Dict, Any, Callable, Tuple
import sys
sys.path.insert(0, '/home/user/Mix-Analyzer')

from composition_engine.transforms.velocity import (
    velocity_contour_apply, accent_pattern, velocity_scale,
)
from composition_engine.transforms.pitch import octave_jump, fragment
from composition_engine.transforms.timing import rhythmic_displace
from composition_engine.transforms.pipeline import concat_motifs


# ============================================================================
# 1. apply_arc_to_phrase — combined velocity + register arc
# ============================================================================

def apply_arc_to_phrase(notes: List[Dict[str, Any]],
                        peak_position: float = 0.5,
                        velocity_low: int = 70, velocity_high: int = 120,
                        register_lift_octaves: int = 0,
                        register_lift_indices: List[int] = None) -> List[Dict[str, Any]]:
    """Apply a combined velocity + (optional) register arc across a phrase.

    The phrase rises in INTENSITY (velocity) toward peak_position, then falls.
    Optionally, specific notes near the peak get an octave lift for register-arc.

    This is the canonical "musical phrase shape" — a phrase that BREATHES has an
    arc (rise + fall) rather than constant velocity.

    Args:
        notes: list of note dicts.
        peak_position: 0.0-1.0, where the velocity peak sits in the phrase.
        velocity_low: minimum velocity at start/end.
        velocity_high: peak velocity at peak_position.
        register_lift_octaves: if > 0, lift specific notes by this many octaves.
        register_lift_indices: which notes to lift (default: notes near peak_position).

    Returns:
        New list with phrase-arc applied.
    """
    n = len(notes)
    if n == 0:
        return []

    # Compute velocity arc — triangular shape with peak at peak_position
    new_notes = []
    for i, note in enumerate(notes):
        if n == 1:
            t = 0.5
        else:
            t = i / (n - 1)
        # Distance from peak (0.0 = at peak, 1.0 = far from peak)
        dist = abs(t - peak_position) / max(peak_position, 1 - peak_position)
        dist = max(0.0, min(1.0, dist))
        v = velocity_high - (velocity_high - velocity_low) * dist
        new_notes.append({**note, 'velocity': max(1, min(127, int(round(v))))})

    # Apply register lift to specified indices (or auto-default near peak)
    if register_lift_octaves > 0:
        if register_lift_indices is None:
            # Auto: lift the single note CLOSEST to peak_position
            peak_idx = int(round(peak_position * (n - 1)))
            register_lift_indices = [peak_idx]
        new_notes = octave_jump(new_notes, register_lift_indices,
                                octaves=register_lift_octaves)

    return new_notes


# ============================================================================
# 2. apply_call_response — combine two motifs with breathing gap
# ============================================================================

def apply_call_response(call: List[Dict[str, Any]],
                        response: List[Dict[str, Any]],
                        gap_beats: float = 1.0,
                        call_velocity_scale: float = 1.0,
                        response_velocity_scale: float = 0.85) -> List[Dict[str, Any]]:
    """Assemble two motifs as a CALL → GAP → RESPONSE phrase.

    The "call" is louder/stronger; the "response" answers it slightly softer
    (default 85% velocity) — like a question and a quieter answer. The GAP
    BETWEEN the two phrases IS what makes this feel musical (vs. running notes
    end-to-end).

    Args:
        call: notes for the calling phrase (rendered at time 0).
        response: notes for the responding phrase (rendered at time 0).
        gap_beats: silence between call's end and response's start.
        call_velocity_scale: optional scale for call (1.0 = no change).
        response_velocity_scale: scale for response (default 0.85 = softer).

    Returns:
        Combined note list with proper timing.
    """
    if not call:
        return response if not response else [{**n} for n in response]

    call_scaled = velocity_scale(call, call_velocity_scale) if call_velocity_scale != 1.0 else call
    response_scaled = velocity_scale(response, response_velocity_scale) if response_velocity_scale != 1.0 else response

    # Find call's end time
    call_end = max(n['time'] + n['duration'] for n in call_scaled)
    response_offset = call_end + gap_beats

    out = [{**n} for n in call_scaled]
    for n in response_scaled:
        out.append({**n, 'time': n['time'] + response_offset})
    return out


# ============================================================================
# 3. apply_tension_release — route phrase from dissonance to resolution
# ============================================================================

def apply_tension_release(notes: List[Dict[str, Any]],
                          tension_indices: List[int],
                          tension_pitch_offset: int = 1,
                          release_velocity_drop: int = 15) -> List[Dict[str, Any]]:
    """Mark specific notes as TENSION points (slightly off-pitch by N semitones).

    Tension notes get pitch shifted by `tension_pitch_offset` semitones
    (typically +1 or -1, creating dissonance), and accented in velocity. The
    NOTE AFTER each tension point gets a velocity drop (release).

    Used per advisor:
        - phrygian_inflection_dark_color (♭2 leans into Eb, releases to D)
        - mingus_freedom_chromatic_harmony_inspiration (chromatic surprises)

    Args:
        notes: list of note dicts.
        tension_indices: which notes to mark as tension points.
        tension_pitch_offset: pitch shift for tension notes (default +1 = ♭2 inflection).
        release_velocity_drop: velocity reduction for the note AFTER each tension.

    Returns:
        New list with tension/release applied.
    """
    tension_set = set(tension_indices)
    out = []
    for i, note in enumerate(notes):
        if i in tension_set:
            # Tension: shift pitch, accent velocity (+10)
            out.append({**note,
                        'pitch': note['pitch'] + tension_pitch_offset,
                        'velocity': max(1, min(127, note['velocity'] + 10))})
        elif (i - 1) in tension_set:
            # Release: drop velocity (release after tension)
            out.append({**note,
                        'velocity': max(1, note['velocity'] - release_velocity_drop)})
        else:
            out.append({**note})
    return out


# ============================================================================
# 4. apply_phrase_breath — insert silence (rest) at specific positions
# ============================================================================

def apply_phrase_breath(notes: List[Dict[str, Any]],
                        breath_after_indices: List[int],
                        breath_beats: float = 0.5) -> List[Dict[str, Any]]:
    """Insert silence (rest) AFTER specific note indices by shifting later notes.

    A phrase that BREATHES has rests between sub-phrases. This primitive lets
    you insert a breath after specific notes, pushing all subsequent notes later
    by `breath_beats`.

    Args:
        notes: list of note dicts (sorted by time).
        breath_after_indices: indices after which to insert a breath.
        breath_beats: how long each breath is (in beats).

    Returns:
        New list with breath inserted (subsequent notes shifted).
    """
    if not breath_after_indices:
        return [{**n} for n in notes]

    notes_sorted = sorted(notes, key=lambda n: n['time'])
    # Compute cumulative shift at each index
    breath_set = set(breath_after_indices)
    shift = 0.0
    out = []
    for i, note in enumerate(notes_sorted):
        out.append({**note, 'time': note['time'] + shift})
        if i in breath_set:
            shift += breath_beats
    return out


# ============================================================================
# 5. apply_dynamic_arc_section — section-level density arc
# ============================================================================

def apply_dynamic_arc_section(notes: List[Dict[str, Any]],
                              section_role: str = 'verse',
                              global_velocity_scale: float = 1.0) -> List[Dict[str, Any]]:
    """Apply a section-level dynamic profile based on its role in the song arc.

    Section roles + their dynamic profiles:
        'intro'      — start at 60% velocity, swell to 80%
        'build'      — climb from 70% to 95% (climax shape)
        'verse'      — flat at 90% velocity (anchored)
        'breakdown'  — drop to 60% velocity (hard-soft contrast)
        'drop'       — peak at 100% velocity (full intensity)
        'outro'      — release shape (high, then sudden drop on final notes)

    Args:
        notes: list of note dicts.
        section_role: role in song arc.
        global_velocity_scale: overall multiplier on top of profile (1.0 = no change).

    Returns:
        New list with section-level velocity profile applied.
    """
    profiles = {
        'intro':     ('cresc', 60, 80),
        'build':     ('climax', 70, 95),
        'verse':     ('flat', 90, 90),
        'breakdown': ('flat', 50, 65),
        'drop':      ('flat', 105, 115),
        'outro':     ('release', 30, 90),    # release: stay at 90, sudden drop to 30 on last note
    }
    if section_role not in profiles:
        raise ValueError(f'unknown section_role {section_role!r}, must be one of {list(profiles.keys())}')
    shape, low, high = profiles[section_role]
    new = velocity_contour_apply(notes, shape, low, high)
    if global_velocity_scale != 1.0:
        new = velocity_scale(new, global_velocity_scale)
    return new


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    from composition_engine.motifs.melodic import MELODIC_MOTIFS, render

    motif = MELODIC_MOTIFS['aeolian_descending_4_steps']
    base = render(motif, tonic_pitch=50)
    print('=== Base velocities/pitches ===')
    print('  pitches:    ', [n['pitch'] for n in base])
    print('  velocities: ', [n['velocity'] for n in base])

    # Test 1: apply_arc_to_phrase
    print('\n=== apply_arc_to_phrase peak=0.5 (middle) ===')
    arc = apply_arc_to_phrase(base, peak_position=0.5,
                              velocity_low=70, velocity_high=120)
    print('  velocities:', [n['velocity'] for n in arc])

    print('\n=== apply_arc_to_phrase peak=0.7 with register lift on note 2 ===')
    arc2 = apply_arc_to_phrase(base, peak_position=0.7,
                               velocity_low=60, velocity_high=125,
                               register_lift_octaves=1, register_lift_indices=[2])
    print('  pitches:    ', [n['pitch'] for n in arc2])
    print('  velocities: ', [n['velocity'] for n in arc2])

    # Test 2: apply_call_response
    motif_a = MELODIC_MOTIFS['aeolian_descending_4_steps']
    motif_b = MELODIC_MOTIFS['outro_chant_fragment_repeating']
    call_notes = render(motif_a, tonic_pitch=50)
    response_notes = render(motif_b, tonic_pitch=50)
    print('\n=== apply_call_response (gap=1.0 beat) ===')
    cr = apply_call_response(call_notes, response_notes, gap_beats=1.0)
    for n in cr:
        print(f'  time={n["time"]:.2f}  pitch={n["pitch"]}  vel={n["velocity"]}')

    # Test 3: apply_tension_release
    print('\n=== apply_tension_release on indices [1] (note 2 leans into Eb, note 3 releases) ===')
    tr = apply_tension_release(base, tension_indices=[1],
                               tension_pitch_offset=1, release_velocity_drop=20)
    for n in tr:
        print(f'  pitch={n["pitch"]}  vel={n["velocity"]}')

    # Test 4: apply_phrase_breath
    print('\n=== apply_phrase_breath after index 1 (gap=0.5 beats) ===')
    br = apply_phrase_breath(base, breath_after_indices=[1], breath_beats=0.5)
    for n in br:
        print(f'  time={n["time"]}  pitch={n["pitch"]}')

    # Test 5: apply_dynamic_arc_section
    print('\n=== apply_dynamic_arc_section per role ===')
    for role in ['intro', 'build', 'verse', 'breakdown', 'drop', 'outro']:
        v = apply_dynamic_arc_section(base, section_role=role)
        print(f'  {role:10s}: velocities = {[n["velocity"] for n in v]}')
