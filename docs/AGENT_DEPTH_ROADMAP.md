# Agent Depth & Completeness Roadmap

Plan pour transformer le système d'un scaffolding **70/30 (LLM hand-craft post-hoc, agents ne contribuent que le squelette)** en pipeline multi-agent profond où chaque décision est traçable au corpus + aux mappings + à la banque MIDI.

> **Statut** : en cours. À jour au commit qui ajoute ce doc.

## Pourquoi ce roadmap existe

Audit Phase 4.1 a confirmé : les agents existants sont des **scaffolds** — schema strict, parser strict, ranges enforcés, MAIS aucune contrainte sur la profondeur du raisonnement. Un agent peut produire un `rationale: "Build à la Pyramid_Song"` (3 mots) et passer le parser. Résultat : compositions plates, mix superficiels, pipeline cérémonieuse.

La banque `ableton/banque_midi_qrust.xlsx` (10 sheets : drum_mapping, rhythm_patterns, scales, progressions, qrust_profiles, velocity, tempo, basslines, notes_usage) ajoutée par l'utilisateur est le matériel concret manquant.

## Statut par bloc

| Bloc | Titre | Effort | Statut |
|------|-------|--------|--------|
| **0** | Banque MIDI loader (préalable) | ~3h | ✅ |
| **1** | Contrat de profondeur machine-vérifiable | ~3.5h | ⚪ pas commencé |
| **2** | Motif-decider PROFOND | ~14h | ⚪ |
| **3** | Wirage des sphères descriptives au rendu | ~7h | ⚪ |
| **4** | Approfondir les agents existants creux | ~13h | ⚪ |
| **5** | Mix engine continuation | ~27h | ⚪ |
| **6** | Sphères restantes côté compo | ~6h | ⚪ |
| **7** | Agents avancés / innovation | ~7h | ⚪ |
| **TOTAL** | | **~80h** | |

Premier livrable testable musicalement : fin Bloc 3 (~24h cumul).

## Bloc 0 — Banque MIDI loader (PRÉALABLE BLOQUANT)

Sans interface Python sur `banque_midi_qrust.xlsx`, aucun agent ne peut piocher tes mappings.

| # | Tâche | Effort | Statut |
|---|---|---|---|
| 0.1 | `composition_engine/banque_bridge/banque_loader.py` — slicing par sheet (drum_mapping, rhythm_patterns, scales, progressions, qrust_profiles, velocity, tempo, basslines) | ~2h | ✅ |
| 0.2 | Tests du loader (chaque sheet retourne du JSON structuré, profils Qrust accessibles par nom) | ~1h | ✅ (30 tests passent) |

## Bloc 1 — Définir "profondeur" comme contrat machine-vérifiable

Sans ça, les agents retombent dans le scaffolding creux.

| # | Tâche | Effort | Statut |
|---|---|---|---|
| 1.1 | `docs/AGENT_DEPTH_CONTRACT.md` — règles minimales : triple-rationale (causal/interactionnel/idiomatique), `rationale.length ≥ 200`, `inspired_by ≥ 2 sources distinctes`, `excerpt ≥ 50 chars`, citations avec **bar/timestamp/cell-ref précis** | ~1h | ⚪ |
| 1.2 | `composition_engine/agent_depth_linter.py` — scanne un Decision JSON et FAIL si profondeur insuffisante | ~2h | ⚪ |
| 1.3 | Hook `pre-commit` qui lance le linter sur les agent outputs | ~30min | ⚪ |

## Bloc 2 — Motif-decider PROFOND

Le seul agent qui peut résoudre le 70/30 — celui qui décide les NOTES.

| # | Tâche | Effort | Statut |
|---|---|---|---|
| 2.1 | Schema `MotifsDecision`, `LayerMotif`, `Note` (avec microtiming offset, articulation hint, accent type, role-in-phrase) | ~1h | ⚪ |
| 2.2 | Parser `parse_motifs_decision` strict + linter profondeur intégré | ~2h | ⚪ |
| 2.3 | `.claude/agents/motif-decider.md` — **6-8 in-context examples** musicalement substantiels, citant banque + corpus, triple-rationale visible | ~4h | ⚪ |
| 2.4 | Cohesion rules (motifs cohérents avec arrangement.density_curve, harmony.scale, rhythm.subdivisions) | ~1.5h | ⚪ |
| 2.5 | Wirage `composer_adapter` (remplace `_default_motif`) | ~1.5h | ⚪ |
| 2.6 | Test d'intégration end-to-end : .mid produit, vérifier notes match décisions | ~2h | ⚪ |
| 2.7 | Audit + Phase 2.7.1 cleanup | ~2h | ⚪ |

## Bloc 3 — Wirer les sphères descriptives au rendu

Aujourd'hui dynamics/rhythm/harmony sont 50% descriptifs. Sans ça, motif-decider sort des notes mais le composer ignore l'arc dB et le swing.

| # | Tâche | Effort | Statut |
|---|---|---|---|
| 3.1 | dynamics arc → velocity envelope appliqué aux notes du motif | ~2h | ⚪ |
| 3.2 | rhythm.swing + subdivisions → grid réelle (pas hardcoded 16ths) | ~2h | ⚪ |
| 3.3 | harmony.progression → chord changes pendant la section | ~3h | ⚪ |

## Bloc 4 — Approfondir les agents existants creux

Audit a confirmé : tous les agents sphère + oracles + diagnostician sont scaffolds. Reprise un par un.

| # | Tâche | Effort | Statut |
|---|---|---|---|
| 4.1 | dynamics-decider — Phase 2.6.2 profondeur (cross-layer awareness, banque velocity citations) | ~2h | ⚪ |
| 4.2 | structure-decider — audit + cleanup profondeur | ~1.5h | ⚪ |
| 4.3 | harmony-decider — audit + profondeur (citer scales étoilées de la banque) | ~1.5h | ⚪ |
| 4.4 | rhythm-decider — audit + profondeur (citer 02_Rhythm_Patterns + 05_Qrust_Profiles) | ~2h | ⚪ |
| 4.5 | arrangement-decider — audit + profondeur | ~2h | ⚪ |
| 4.6 | mix-diagnostician — Phase 4.1.2 profondeur causale (pas juste transcription Excel) | ~2h | ⚪ |
| 4.7 | device-mapping-oracle / als-manipulation-oracle — raisonnement contextuel | ~2h | ⚪ |

## Bloc 5 — Mix engine continuation

| # | Tâche | Effort | Statut |
|---|---|---|---|
| 5.1 | `excel_loader.py` (Mix Analyzer report) implémenté | ~3h | ⚪ |
| 5.2 | eq-corrective-engineer ULTRA-DÉTAILLÉ (résonances, masking matrix, voice leading EQ) | ~4h | ⚪ |
| 5.3 | dynamics-corrective-engineer (sidechain, glue, multiband) | ~4h | ⚪ |
| 5.4 | routing-and-sidechain-architect | ~3h | ⚪ |
| 5.5 | automation-engineer (creative + corrective modes — lit la banque pour patterns d'automation idiomatiques) | ~5h | ⚪ |
| 5.6 | chain-builder | ~2h | ⚪ |
| 5.7 | mastering-engineer | ~3h | ⚪ |
| 5.8 | mix-orchestrator (Director) + mix-safety-guardian | ~3h | ⚪ |

## Bloc 6 — Sphères restantes côté compo

| # | Tâche | Effort | Statut |
|---|---|---|---|
| 6.1 | performance-decider (Phase 2.8) — consomme `06_Velocity_Dynamics` de la banque | ~3h | ⚪ |
| 6.2 | fx-decider (Phase 2.9) | ~3h | ⚪ |

## Bloc 7 — Agents avancés / innovation

| # | Tâche | Effort | Statut |
|---|---|---|---|
| 7.1 | story-decider — narratif → arc émotionnel par section, nourrit les autres agents en briefs riches | ~4h | ⚪ |
| 7.2 | inter-section-coherence-decider — assure que 2 sections consécutives s'enchaînent | ~3h | ⚪ |

## Légende statut

- ⚪ Pas commencé
- 🟡 En cours
- ✅ Terminé
- 🔴 Bloqué (raison expliquée inline)

## Discipline

Chaque tâche **terminée** :
1. Met à jour le statut ici (⚪ → ✅)
2. CHANGELOG.md entry
3. Commit conventionnel
4. Audit obligatoire si ≥ 3h d'effort (5-7 faiblesses identifiées → cleanup phase)
