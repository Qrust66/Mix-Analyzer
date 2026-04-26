"""Global humanization — Phase 4-3 of composition_engine.

Cross-track finalization pass: applied AFTER per-track humanization to ensure
the final composition feels coherent across tracks.

Functions:
    detect_collisions    — find notes across tracks that start within Nms of each other
    nudge_collisions     — slightly offset colliding non-anchor hits to avoid flam
    snap_anchors_to_grid — preserve specific anchor positions on-grid (downbeats)
    quantize_strength    — partial quantization toward grid (90% = strong, 50% = loose)
    finalization_pass    — apply standard end-of-pipeline cleanup
"""

import random
from typing import List, Dict, Any, Tuple


def detect_collisions(tracks: Dict[str, List[Dict[str, Any]]],
                      tolerance_ms: float = 5.0,
                      tempo_bpm: float = 108.0) -> List[Tuple[float, List[Tuple[str, Dict[str, Any]]]]]:
    """Find note-onsets across tracks that start within `tolerance_ms` of each other.

    These collisions sound like accidental flams. If they're INTENTIONAL (e.g. on
    downbeats where kick + bass hit together), they're musical. Off-grid collisions
    are usually unwanted.

    Args:
        tracks: dict of track_name → notes list.
        tolerance_ms: collision tolerance in milliseconds.
        tempo_bpm: tempo for ms→beats conversion.

    Returns:
        List of (time, [(track_name, note), ...]) tuples — each collision cluster.
    """
    tolerance_beats = tolerance_ms * tempo_bpm / 60000.0

    # Build flat list of (time, track_name, note) sorted by time
    flat = []
    for track_name, notes in tracks.items():
        for n in notes:
            flat.append((n['time'], track_name, n))
    flat.sort(key=lambda x: x[0])

    # Cluster adjacent notes within tolerance
    collisions = []
    i = 0
    while i < len(flat):
        cluster_start = flat[i][0]
        cluster = [(flat[i][1], flat[i][2])]
        j = i + 1
        while j < len(flat) and flat[j][0] - cluster_start <= tolerance_beats:
            cluster.append((flat[j][1], flat[j][2]))
            j += 1
        if len(cluster) > 1:
            collisions.append((cluster_start, cluster))
        i = j

    return collisions


def nudge_collisions(tracks: Dict[str, List[Dict[str, Any]]],
                     tolerance_ms: float = 5.0,
                     nudge_ms: float = 8.0,
                     tempo_bpm: float = 108.0,
                     anchor_tracks: List[str] = None,
                     rng_seed: int = None) -> Dict[str, List[Dict[str, Any]]]:
    """For each detected collision cluster, NUDGE non-anchor-track notes off the
    collision time by ±nudge_ms.

    Anchor tracks (default: kick / bass / drums) keep their timing. Other tracks
    get nudged to avoid flam-collisions.

    Args:
        tracks: dict of track_name → notes list.
        tolerance_ms: collision tolerance.
        nudge_ms: how far to nudge non-anchor notes.
        tempo_bpm: tempo for conversions.
        anchor_tracks: track names that DON'T get nudged (default ['DRUMS', 'KICK', 'SUB', 'BASS']).
        rng_seed: deterministic randomness.

    Returns:
        New dict of tracks with nudged collisions.
    """
    if anchor_tracks is None:
        anchor_tracks = ['DRUMS', 'KICK', 'SUB', 'BASS']

    rng = random.Random(rng_seed) if rng_seed is not None else random.Random()
    nudge_beats = nudge_ms * tempo_bpm / 60000.0

    # Detect collisions
    collisions = detect_collisions(tracks, tolerance_ms, tempo_bpm)

    # For each collision, nudge non-anchor notes
    # We need to mutate the right note instances. Build an id→nudge map
    nudge_map: Dict[int, float] = {}   # id(note) → nudge_amount
    for time, cluster in collisions:
        # Skip if all members are in anchor tracks (intentional collision)
        non_anchors = [(t, n) for t, n in cluster if t not in anchor_tracks]
        if not non_anchors:
            continue
        # Nudge each non-anchor note by ±nudge_ms (random direction per note)
        for track_name, note in non_anchors:
            direction = 1 if rng.random() > 0.5 else -1
            nudge_map[id(note)] = direction * nudge_beats

    # Apply nudges
    out: Dict[str, List[Dict[str, Any]]] = {}
    for track_name, notes in tracks.items():
        out_notes = []
        for n in notes:
            nudge = nudge_map.get(id(n), 0.0)
            if nudge != 0.0:
                out_notes.append({**n, 'time': max(0.0, n['time'] + nudge)})
            else:
                out_notes.append({**n})
        out[track_name] = out_notes
    return out


def snap_anchors_to_grid(notes: List[Dict[str, Any]],
                         anchor_grid_beats: float = 4.0,
                         tolerance_ms: float = 30.0,
                         tempo_bpm: float = 108.0) -> List[Dict[str, Any]]:
    """Snap notes that fall NEAR an anchor-grid position (downbeats) to exactly on-grid.

    Used as final cleanup: even with humanization, downbeat hits should align
    exactly so the listener can find the 1.

    Args:
        notes: list of note dicts.
        anchor_grid_beats: anchor positions every N beats (default 4 = bar starts).
        tolerance_ms: max distance for snapping (notes further away are preserved).
        tempo_bpm: tempo for conversions.

    Returns:
        New list with near-anchor notes snapped.
    """
    tolerance_beats = tolerance_ms * tempo_bpm / 60000.0
    out = []
    for n in notes:
        # Nearest anchor
        nearest = round(n['time'] / anchor_grid_beats) * anchor_grid_beats
        if abs(n['time'] - nearest) <= tolerance_beats:
            out.append({**n, 'time': nearest})
        else:
            out.append({**n})
    return out


def quantize_strength(notes: List[Dict[str, Any]],
                      grid_beats: float = 0.25,
                      strength: float = 0.5) -> List[Dict[str, Any]]:
    """Partial quantization: pull notes toward grid by `strength` (0.0=no, 1.0=full).

    Args:
        notes: list of note dicts.
        grid_beats: grid resolution (0.25 = 16th notes).
        strength: 0.0 to 1.0 (default 0.5 = halfway pull to grid).

    Returns:
        New list with partially-quantized timing.
    """
    if not 0 <= strength <= 1:
        raise ValueError(f'strength must be in [0,1], got {strength}')
    out = []
    for n in notes:
        nearest = round(n['time'] / grid_beats) * grid_beats
        new_t = n['time'] + (nearest - n['time']) * strength
        out.append({**n, 'time': max(0.0, new_t)})
    return out


def finalization_pass(tracks: Dict[str, List[Dict[str, Any]]],
                      tempo_bpm: float = 108.0,
                      anchor_tracks: List[str] = None,
                      collision_tolerance_ms: float = 5.0,
                      collision_nudge_ms: float = 8.0,
                      anchor_snap_tolerance_ms: float = 30.0,
                      rng_seed: int = None) -> Dict[str, List[Dict[str, Any]]]:
    """Standard end-of-pipeline cleanup: nudge collisions + snap anchor-tracks to grid.

    Order:
        1. Snap anchor-track notes near downbeats to exactly on-grid.
        2. Detect cross-track collisions and nudge non-anchor notes off them.

    Args:
        tracks: dict of track_name → notes list.
        tempo_bpm: tempo.
        anchor_tracks: tracks to preserve on-grid (default ['DRUMS','KICK','SUB','BASS']).
        collision_tolerance_ms: detect-cluster threshold.
        collision_nudge_ms: nudge distance for non-anchors.
        anchor_snap_tolerance_ms: snap-distance for downbeat hits.
        rng_seed: deterministic randomness.

    Returns:
        Cleaned-up tracks dict.
    """
    if anchor_tracks is None:
        anchor_tracks = ['DRUMS', 'KICK', 'SUB', 'BASS']

    # Step 1: snap anchor-track downbeat hits to grid
    snapped = {}
    for tname, notes in tracks.items():
        if tname in anchor_tracks:
            snapped[tname] = snap_anchors_to_grid(notes, anchor_grid_beats=4.0,
                                                  tolerance_ms=anchor_snap_tolerance_ms,
                                                  tempo_bpm=tempo_bpm)
        else:
            snapped[tname] = list(notes)

    # Step 2: nudge non-anchor collisions
    nudged = nudge_collisions(snapped,
                              tolerance_ms=collision_tolerance_ms,
                              nudge_ms=collision_nudge_ms,
                              tempo_bpm=tempo_bpm,
                              anchor_tracks=anchor_tracks,
                              rng_seed=rng_seed)
    return nudged


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    # Build two tracks with deliberate collision at beat 1.0 (off-grid micro-jitter)
    track_drums = [
        {'time': 0.0, 'duration': 0.25, 'velocity': 120, 'pitch': 36},   # downbeat
        {'time': 1.003, 'duration': 0.25, 'velocity': 110, 'pitch': 36}, # beat 2 with +3ms jitter
        {'time': 2.0, 'duration': 0.25, 'velocity': 110, 'pitch': 36},
    ]
    track_pad = [
        {'time': 0.0, 'duration': 4.0, 'velocity': 80, 'pitch': 50},     # sustained chord
        {'time': 1.001, 'duration': 0.25, 'velocity': 90, 'pitch': 53},  # collides with drums beat 2 (+1ms)
    ]
    track_lead = [
        {'time': 1.005, 'duration': 0.5, 'velocity': 100, 'pitch': 70},  # collides with drums beat 2 (+5ms)
    ]
    tracks = {'DRUMS': track_drums, 'PAD': track_pad, 'LEAD': track_lead}

    print('=== Detect collisions (tolerance 5ms @ 108 BPM) ===')
    collisions = detect_collisions(tracks, tolerance_ms=5, tempo_bpm=108)
    for time, cluster in collisions:
        print(f'  collision @ time {time:.4f}: {[(t,n["pitch"]) for t,n in cluster]}')

    print('\n=== nudge_collisions (anchor=DRUMS, nudge=8ms) ===')
    nudged = nudge_collisions(tracks, tolerance_ms=5, nudge_ms=8, tempo_bpm=108,
                              anchor_tracks=['DRUMS'], rng_seed=42)
    for tname, notes in nudged.items():
        print(f'  {tname}:')
        for n in notes:
            print(f'    time={n["time"]:.4f}  pitch={n["pitch"]}')

    # Verify drums unchanged, others shifted
    print('\n=== Re-detect collisions after nudge ===')
    collisions2 = detect_collisions(nudged, tolerance_ms=5, tempo_bpm=108)
    print(f'  Remaining collisions: {len(collisions2)}')

    # Test snap_anchors_to_grid
    print('\n=== snap_anchors_to_grid (within 30ms) ===')
    drift = [
        {'time': 0.005, 'duration': 0.25, 'velocity': 120, 'pitch': 36},   # 5ms off
        {'time': 4.020, 'duration': 0.25, 'velocity': 120, 'pitch': 36},   # 20ms off
        {'time': 8.080, 'duration': 0.25, 'velocity': 120, 'pitch': 36},   # 80ms off (NOT snapped, beyond tol)
    ]
    snapped = snap_anchors_to_grid(drift, anchor_grid_beats=4.0, tolerance_ms=30, tempo_bpm=108)
    for n in snapped:
        print(f'  time={n["time"]:.4f}')

    # Test quantize_strength
    print('\n=== quantize_strength 50% ===')
    loose = [{'time': 0.04, 'duration': 0.25, 'velocity': 100, 'pitch': 60},
             {'time': 0.31, 'duration': 0.25, 'velocity': 100, 'pitch': 62}]
    q = quantize_strength(loose, grid_beats=0.25, strength=0.5)
    for orig, new in zip(loose, q):
        print(f'  {orig["time"]:.4f} → {new["time"]:.4f} (grid 0.25, half-pull)')

    # Test finalization_pass full pipeline
    print('\n=== finalization_pass full pipeline ===')
    final = finalization_pass(tracks, tempo_bpm=108, anchor_tracks=['DRUMS'],
                              rng_seed=42)
    for tname, notes in final.items():
        print(f'  {tname}:')
        for n in notes:
            print(f'    time={n["time"]:.4f}  pitch={n["pitch"]}')
