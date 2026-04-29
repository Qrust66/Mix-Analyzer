# TEST_DRIVE_GUIDE.md — Test drive end-to-end mix_engine

Phase 4.13 livre le CLI orchestrateur `scripts/apply_mix_decisions.py` qui
permet d'appliquer des décisions Tier A (EQ corrective, dynamics corrective,
stereo/spatial) à un `.als` réel via les Tier B writers.

## Prérequis

3 Tier B writers Phase 4.10-4.12 livrés et testés :
- `eq8-configurator` (Eq8 device, 8 modes filtres)
- `dynamics-configurator` (GlueCompressor + Limiter — Phase 4.11 v1 scope)
- `spatial-configurator` (StereoGain + Mixer.Pan, 7 move types)

Tous REUSE-only (n'inserrent pas de nouveaux devices — la track doit déjà
posséder le device cible). Phase future ajoutera CREATE paths via Pluggin
Mapping.als template.

## Workflow test drive

### 1. Préparer ton .als source

Garde une copie de sauvegarde — le CLI peut écraser le source si tu
n'utilises pas `--output`.

### 2. Générer les décisions Tier A (3 fichiers JSON)

Pour chaque lane, invoque l'agent Tier A correspondant et sauvegarde
le JSON output :

| Lane | Subagent Claude Code | Output JSON shape |
|---|---|---|
| EQ corrective | `eq-corrective-decider` | `{"schema_version":"1.0", "eq_corrective":{"bands":[...]}}` |
| Dynamics corrective | `dynamics-corrective-decider` | `{"schema_version":"1.0", "dynamics_corrective":{"corrections":[...]}}` |
| Spatial | `stereo-and-spatial-engineer` | `{"schema_version":"1.0", "stereo_spatial":{"moves":[...]}}` |

Exemples canoniques de décisions dans `tests/fixtures/sample_decisions/` :
- `eq_corrective_sample.json` — bell cut + HPF
- `dynamics_corrective_sample.json` — bus glue + limit
- `spatial_sample.json` — bass-mono + center pan

### 3. Run le CLI

```bash
python scripts/apply_mix_decisions.py \
    --als ton_projet.als \
    --eq-json eq_decision.json \
    --dynamics-json dynamics_decision.json \
    --spatial-json spatial_decision.json \
    --output ton_projet_modified.als
```

### 4. Vérifier le report

Le CLI imprime un report par lane :
- `output:` chemin du `.als` modifié
- `safety:` PASS / FAIL / SKIPPED
- `bands/corrections/moves applied:` liste verbatim
- `skipped:` (track manquante, scope Phase X v1, etc.)
- `warnings:` non-fatal (params ignored, sections deferred, etc.)

Resultat final : `=== RESULT : OK ===` ou `=== RESULT : FAIL ===`.

### 5. Ouvrir dans Ableton Live

Le `.als` modifié doit ouvrir sans erreur. Vérifie :
- Eq8 bandes activées avec les params déclarés (Mode/Freq/Gain/Q)
- GlueCompressor / Limiter params à jour
- StereoGain (BassMono/Width/Balance/MidSide/PhaseInvert)
- Mixer.Pan position correcte

## Options CLI utiles

| Flag | Description |
|---|---|
| `--dry-run` | Validation sans écriture (rapport produit, .als intact) |
| `--no-safety` | Désactive le safety_guardian post-write (déconseillé) |
| Décisions optionnelles | Tu peux ne fournir qu'1, 2, ou 3 lanes ; les absents sont skippés |

Exemples :

```bash
# EQ-only (autres lanes ignorées)
python scripts/apply_mix_decisions.py \
    --als input.als --eq-json eq.json --output output.als

# Dry-run pour pré-valider sans toucher fichier
python scripts/apply_mix_decisions.py \
    --als input.als \
    --eq-json eq.json --dynamics-json dyn.json --spatial-json sp.json \
    --dry-run
```

## Limitations Phase 4.13

- **REUSE-only** : si la track n'a pas le device requis (Eq8, GlueComp,
  Limiter, StereoGain), la décision est skipped. Le CLI imprime la raison.
- **Pas de routing-configurator** : sidechain refs, bus structure → Phase
  4.14+ (futur).
- **Pas de master-bus-configurator** : moves master (mastering-engineer
  Tier A) → Phase futur.
- **automation-writer extension** partielle : envelopes Eq8 + GlueComp ; les
  envelopes spatial pas encore (out-of-scope SpatialMove schema).
- **Sample decisions** ciblent `[H/R] Bass Rythm` + `[H/R] Kick 1` qui
  existent dans reference_project.als. Pour ton `.als`, ajuste les
  noms de tracks dans les JSONs.

## Dépannage

| Erreur | Cause | Fix |
|---|---|---|
| `track 'X' has no Eq8 device` | REUSE-only — track sans device | Ajoute le device dans Ableton OU élimine la décision |
| `chain_position='X' but no Eq8 at this position` | REUSE-only avec position spécifique | Change `chain_position: "default"` dans le JSON |
| `safety: FAIL` | Param hors range Ableton | Vérifier les warnings ; le `.als` est probablement encore loadable |
| `track 'X' not found` | Nom track typo | Match exact requis (case-sensitive) |
| `MixAgentOutputError` | JSON malformé / clé manquante | Vérifier shape JSON contre `tests/fixtures/sample_decisions/*` |

## Référence

- Tests CLI : `tests/test_apply_mix_decisions_cli.py` (9 tests, smoke +
  full pipeline)
- CLI source : `scripts/apply_mix_decisions.py`
- Sample fixtures : `tests/fixtures/sample_decisions/`
- Tier B writers : `mix_engine/writers/`
- Architecture : `docs/MIX_ENGINE_ARCHITECTURE.md`
- Roadmap : `docs/MIX_ENGINE_ROADMAP.md`
