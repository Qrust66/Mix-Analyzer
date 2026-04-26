"""Recipe → motif index — Phase 5-1 of composition_engine.

Inverts the motif → advisor_recipes declarations (encoded in Phase 1) to build
a forward index: given an advisor recipe ID, return the list of candidate motifs
that implement it.

This is the BRIDGE between the advisor's natural-language documented recipes
and the composition_engine's concrete motif library.

API:
    motifs_for_recipe(recipe_id, motif_type=None) → {melodic, rhythmic, harmonic}
    recipes_covered() → sorted list of recipe IDs with at least one motif
    recipes_uncovered() → sorted list of advisor recipes with NO motif yet
    coverage_summary() → dict with counts
"""

import json
import os
from typing import Dict, List, Any, Optional

from composition_engine.motifs.melodic import MELODIC_MOTIFS
from composition_engine.motifs.rhythmic import RHYTHMIC_MOTIFS
from composition_engine.motifs.harmonic import HARMONIC_PROGRESSIONS


def _build_recipe_index() -> Dict[str, Dict[str, List[str]]]:
    """Invert motif → advisor_recipes declarations into recipe → motifs index."""
    index: Dict[str, Dict[str, List[str]]] = {}

    def add(recipe_id: str, motif_type: str, motif_id: str):
        if recipe_id not in index:
            index[recipe_id] = {'melodic': [], 'rhythmic': [], 'harmonic': []}
        index[recipe_id][motif_type].append(motif_id)

    for mid, m in MELODIC_MOTIFS.items():
        for r in m.get('advisor_recipes', []):
            add(r, 'melodic', mid)

    for mid, m in RHYTHMIC_MOTIFS.items():
        for r in m.get('advisor_recipes', []):
            add(r, 'rhythmic', mid)

    for pid, p in HARMONIC_PROGRESSIONS.items():
        for r in p.get('advisor_recipes', []):
            add(r, 'harmonic', pid)

    return index


# Eager build at module load
RECIPE_TO_MOTIFS: Dict[str, Dict[str, List[str]]] = _build_recipe_index()


def motifs_for_recipe(recipe_id: str,
                      motif_type: Optional[str] = None) -> Any:
    """Get candidate motifs for an advisor recipe.

    Args:
        recipe_id: e.g. 'syncopated_kick_creates_implied_meter_within_4_4'
        motif_type: 'melodic' / 'rhythmic' / 'harmonic' or None for all.

    Returns:
        If motif_type is given: list of motif IDs.
        If None: dict {melodic: [...], rhythmic: [...], harmonic: [...]}.

    Returns empty list/dict if recipe has no motif coverage.
    """
    entry = RECIPE_TO_MOTIFS.get(recipe_id, {'melodic': [], 'rhythmic': [], 'harmonic': []})
    if motif_type:
        if motif_type not in ('melodic', 'rhythmic', 'harmonic'):
            raise ValueError(f'motif_type must be melodic/rhythmic/harmonic, got {motif_type!r}')
        return entry.get(motif_type, [])
    return entry


def recipes_covered() -> List[str]:
    """All advisor recipes that have at least one motif implementation."""
    return sorted(RECIPE_TO_MOTIFS.keys())


def _load_advisor_recipes() -> List[str]:
    """Load all atom IDs from composition_advisor.json."""
    advisor_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'composition_advisor', 'composition_advisor.json',
    )
    with open(advisor_path) as f:
        d = json.load(f)
    recipes = d['recipes_index']['recipes']
    return [r for r, v in recipes.items()
            if isinstance(v, dict) and 'rule' in v]


def recipes_uncovered() -> List[str]:
    """Advisor recipes with NO motif coverage in the engine yet (future work)."""
    all_advisor_recipes = set(_load_advisor_recipes())
    covered = set(RECIPE_TO_MOTIFS.keys())
    return sorted(all_advisor_recipes - covered)


def coverage_summary() -> Dict[str, Any]:
    """Diagnostic: how many recipes have motifs, what's missing?"""
    advisor_total = len(_load_advisor_recipes())
    covered = len(RECIPE_TO_MOTIFS)
    return {
        'advisor_recipes_total': advisor_total,
        'recipes_with_motif_coverage': covered,
        'recipes_uncovered': advisor_total - covered,
        'coverage_pct': round(covered / advisor_total * 100, 1) if advisor_total else 0,
        'melodic_motifs': len(MELODIC_MOTIFS),
        'rhythmic_motifs': len(RHYTHMIC_MOTIFS),
        'harmonic_progressions': len(HARMONIC_PROGRESSIONS),
    }


def recipes_with_full_coverage(min_motifs_per_type: int = 1) -> List[str]:
    """Recipes that have AT LEAST `min_motifs_per_type` in EACH of melodic/rhythmic/harmonic.

    Useful for finding recipes the composer can deploy as a complete vertical
    (full track stack: melody + rhythm + harmony all present).
    """
    out = []
    for r, entry in RECIPE_TO_MOTIFS.items():
        if all(len(entry[t]) >= min_motifs_per_type for t in ('melodic', 'rhythmic', 'harmonic')):
            out.append(r)
    return sorted(out)


# ============================================================================
# Self-test / coverage report
# ============================================================================

if __name__ == '__main__':
    summary = coverage_summary()
    print('=== Recipe → motif coverage summary ===')
    for k, v in summary.items():
        print(f'  {k}: {v}')

    print(f'\n=== Recipes WITH at least one motif: {len(recipes_covered())} ===')
    for r in recipes_covered()[:25]:
        entry = motifs_for_recipe(r)
        m = len(entry['melodic'])
        rh = len(entry['rhythmic'])
        h = len(entry['harmonic'])
        print(f'  {r:60s} M={m} R={rh} H={h}')
    if len(recipes_covered()) > 25:
        print(f'  ... and {len(recipes_covered()) - 25} more')

    print(f'\n=== Recipes covered in ALL THREE motif categories (mel + rhy + har) ===')
    full = recipes_with_full_coverage(min_motifs_per_type=1)
    for r in full:
        entry = motifs_for_recipe(r)
        print(f'  {r:60s}')
        print(f'    melodic:  {entry["melodic"]}')
        print(f'    rhythmic: {entry["rhythmic"]}')
        print(f'    harmonic: {entry["harmonic"]}')

    print(f'\n=== Sample recipe lookup: descending_riff_as_song_identity ===')
    res = motifs_for_recipe('descending_riff_as_song_identity')
    print(f'  All:      {res}')
    print(f'  Melodic:  {motifs_for_recipe("descending_riff_as_song_identity", "melodic")}')

    print(f'\n=== TOP 10 uncovered recipes (gaps to fill in future) ===')
    uncovered = recipes_uncovered()
    print(f'Total uncovered: {len(uncovered)}')
    for r in uncovered[:10]:
        print(f'  - {r}')
