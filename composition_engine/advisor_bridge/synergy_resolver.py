"""Synergy resolver — Phase 5-3 of composition_engine.

When the composer wants to apply MULTIPLE advisor recipes to a single composition,
this module:
  1. Loads advisor's `synergy_clusters` and `conflict_pairs` data
  2. Verifies recipes don't conflict
  3. Combines their strategies into a single deployment plan

API:
    resolve_recipe_set(recipe_ids) → resolved plan or conflict report
    check_conflicts(recipe_ids) → list of detected conflicts
    suggest_synergies(recipe_id) → recipes that pair well with this one
"""

import json
import os
from typing import List, Dict, Any, Set, Tuple, Optional

from composition_engine.advisor_bridge.recipe_to_strategy import strategy_for_recipe


# ============================================================================
# Lazy-load advisor synergy + conflict data
# ============================================================================

_ADVISOR_DATA = None


def _load_advisor() -> Dict[str, Any]:
    global _ADVISOR_DATA
    if _ADVISOR_DATA is None:
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'composition_advisor', 'composition_advisor.json',
        )
        with open(path) as f:
            _ADVISOR_DATA = json.load(f)
    return _ADVISOR_DATA


def _get_synergy_clusters() -> Dict[str, Dict[str, Any]]:
    """Get the synergy_clusters dict from advisor."""
    d = _load_advisor()
    return d['recipes_index']['synergy_clusters'].get('clusters', {})


def _get_conflict_pairs() -> List[Dict[str, Any]]:
    """Get the conflict_pairs list from advisor."""
    d = _load_advisor()
    return d['recipes_index']['conflict_pairs'].get('pairs', [])


# ============================================================================
# Conflict detection
# ============================================================================

def check_conflicts(recipe_ids: List[str],
                    only_mutual: bool = False) -> List[Dict[str, Any]]:
    """Find pairs of recipes in `recipe_ids` that the advisor flags as conflicting.

    Args:
        recipe_ids: list of recipe IDs to cross-check.
        only_mutual: if True, only return mutually-documented conflicts (higher confidence).
                     If False, include unilateral too.

    Returns:
        List of conflict dicts: [{recipe_a, recipe_b, mutually_documented, ...}]
    """
    pairs = _get_conflict_pairs()
    recipe_set = set(recipe_ids)
    out = []
    for p in pairs:
        a, b = p['recipe_a'], p['recipe_b']
        if a in recipe_set and b in recipe_set:
            if only_mutual and not p.get('mutually_documented', False):
                continue
            out.append(p)
    return out


# ============================================================================
# Synergy suggestions
# ============================================================================

def suggest_synergies(recipe_id: str,
                      max_suggestions: int = 5) -> List[Dict[str, Any]]:
    """Suggest other recipes that synergize well with this one (per advisor song-clusters).

    A recipe synergizes with another if both appear in the SAME song-cluster
    (= co-presence in a documented song's atom set).

    Args:
        recipe_id: source recipe.
        max_suggestions: cap on number of suggestions.

    Returns:
        List of {recipe_id, source_cluster, source_song} dicts.
    """
    clusters = _get_synergy_clusters()
    suggestions = []
    seen = set()
    for cluster_id, cluster in clusters.items():
        if recipe_id not in cluster.get('recipe_ids', []):
            continue
        # Cluster contains recipe_id → other recipes in same cluster are synergistic
        for other in cluster['recipe_ids']:
            if other != recipe_id and other not in seen:
                seen.add(other)
                source_song = cluster.get('parent_song', {}).get('song')
                if source_song is None:
                    source_song = cluster.get('parent_philosophy', cluster_id)
                suggestions.append({
                    'recipe_id': other,
                    'source_cluster': cluster_id,
                    'source_song': source_song,
                })
                if len(suggestions) >= max_suggestions:
                    return suggestions
    return suggestions


# ============================================================================
# Strategy combination
# ============================================================================

def resolve_recipe_set(recipe_ids: List[str],
                       block_on_mutual_conflicts: bool = True) -> Dict[str, Any]:
    """Combine strategies for multiple recipes into a single deployment plan.

    Args:
        recipe_ids: list of advisor recipe IDs to integrate.
        block_on_mutual_conflicts: if True, raise an error if any mutual conflicts.
                                   If False, return them as warnings.

    Returns:
        {
            'tempo_bpm': int,                    # from any tempo_directive
            'total_bars': int,                   # from any form_directive
            'ending_type': str,                  # from any ending_directive
            'section_directives': dict,          # merged from all section_directive recipes
            'motif_strategies': [                # from each motif_based recipe
                {recipe_id, motif_choice, motif_type, transforms, primitives, humanization}
            ],
            'conflicts': [list of detected conflicts],
            'warnings': [list of issues],
            'unmapped_recipes': [recipes without a hand-crafted strategy],
        }

    Raises:
        ValueError: if block_on_mutual_conflicts and mutual conflicts found.
    """
    # 1. Conflict check
    conflicts = check_conflicts(recipe_ids, only_mutual=False)
    mutual_conflicts = [c for c in conflicts if c.get('mutually_documented', False)]
    if block_on_mutual_conflicts and mutual_conflicts:
        raise ValueError(
            f'Mutual conflicts detected in recipe set: '
            f'{[(c["recipe_a"], c["recipe_b"]) for c in mutual_conflicts]}'
        )

    plan: Dict[str, Any] = {
        'tempo_bpm': None,
        'total_bars': None,
        'ending_type': None,
        'section_directives': {},
        'motif_strategies': [],
        'conflicts': conflicts,
        'warnings': [],
        'unmapped_recipes': [],
    }

    # 2. Pull strategies for each recipe
    for rid in recipe_ids:
        s = strategy_for_recipe(rid)
        if s is None:
            plan['unmapped_recipes'].append(rid)
            continue

        # Merge tempo_directive
        if 'tempo_directive' in s:
            td = s['tempo_directive']
            if plan['tempo_bpm'] is None:
                plan['tempo_bpm'] = td['bpm']
            elif plan['tempo_bpm'] != td['bpm']:
                plan['warnings'].append(
                    f'Tempo conflict: {plan["tempo_bpm"]} BPM vs {td["bpm"]} BPM '
                    f'(from {rid}). Keeping {plan["tempo_bpm"]}.'
                )

        # Merge form_directive
        if 'form_directive' in s:
            fd = s['form_directive']
            if plan['total_bars'] is None:
                plan['total_bars'] = fd.get('total_bars')

        # Merge ending_directive
        if 'ending_directive' in s:
            ed = s['ending_directive']
            if plan['ending_type'] is None:
                plan['ending_type'] = ed.get('type')

        # Merge section_directives (deep-merge per section)
        if 'section_directives' in s:
            for sec_name, sec_dict in s['section_directives'].items():
                if sec_name not in plan['section_directives']:
                    plan['section_directives'][sec_name] = {}
                # Conflict-detect: if same key already set with different value, warn
                for k, v in sec_dict.items():
                    cur = plan['section_directives'][sec_name].get(k)
                    if cur is None:
                        plan['section_directives'][sec_name][k] = v
                    elif cur != v:
                        plan['warnings'].append(
                            f'Section directive conflict in {sec_name}.{k}: '
                            f'{cur!r} vs {v!r} (from {rid}). Keeping first.'
                        )

        # Add motif strategy
        if s.get('motif_choice'):
            plan['motif_strategies'].append({
                'recipe_id': rid,
                'motif_choice': s['motif_choice'],
                'motif_type': s['motif_type'],
                'transforms': s.get('transforms', []),
                'primitives': s.get('primitives', []),
                'humanization': s.get('humanization', {}),
                'rationale': s.get('rationale'),
            })

    return plan


# ============================================================================
# Self-test
# ============================================================================

if __name__ == '__main__':
    # Test 1: check_conflicts on a known-conflicting set
    print('=== Test 1: check_conflicts ===')
    test_set = [
        'mid_tempo_aggression_not_hardcore_speed',
        'unrelenting_aggression_no_dynamic_arc',
        'descending_riff_as_song_identity',
    ]
    conflicts = check_conflicts(test_set)
    print(f'Conflicts in {test_set}: {len(conflicts)}')
    for c in conflicts:
        marker = 'MUTUAL' if c.get('mutually_documented') else 'unilateral'
        print(f'  {marker}: {c["recipe_a"]} VS {c["recipe_b"]}')

    # Test 2: suggest_synergies for a popular recipe
    print('\n=== Test 2: suggest_synergies for descending_riff_as_song_identity ===')
    sugg = suggest_synergies('descending_riff_as_song_identity', max_suggestions=8)
    for s in sugg:
        print(f'  {s["recipe_id"]:60s} (from {s["source_song"]})')

    # Test 3: resolve_recipe_set
    print('\n=== Test 3: resolve_recipe_set (industrial-techno banger plan) ===')
    target_recipes = [
        'mid_tempo_aggression_not_hardcore_speed',
        'descending_riff_as_song_identity',
        'syncopated_kick_creates_implied_meter_within_4_4',
        'robot_rock_hypnotic_repetitive_riff_with_micro_variations',
        'drone_foundation_as_compositional_anchor',
        'hard_soft_hard_contrast_within_song',
        'density_arc_arrangement_sparse_to_wall',
        'compressed_economy_under_three_minutes_in_long_album',
        'abrupt_song_end_no_fade',
    ]
    plan = resolve_recipe_set(target_recipes, block_on_mutual_conflicts=False)
    print(f'Plan:')
    print(f'  Tempo:      {plan["tempo_bpm"]} BPM')
    print(f'  Total bars: {plan["total_bars"]}')
    print(f'  Ending:     {plan["ending_type"]}')
    print(f'  Section directives: {list(plan["section_directives"].keys())}')
    for sec_name, sec_dict in plan['section_directives'].items():
        print(f'    {sec_name}: {sec_dict}')
    print(f'  Motif strategies: {len(plan["motif_strategies"])}')
    for ms in plan['motif_strategies']:
        print(f'    [{ms["motif_type"]}] {ms["recipe_id"]} → {ms["motif_choice"]}')
    print(f'  Conflicts: {len(plan["conflicts"])}')
    print(f'  Warnings: {plan["warnings"]}')
    print(f'  Unmapped (no hand-crafted strategy): {plan["unmapped_recipes"]}')
