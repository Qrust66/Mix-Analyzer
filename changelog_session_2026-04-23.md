# Changelog des documents — session 2026-04-23

**Context :** suite à l'échange sur la philosophie "tout dynamique" et la règle "max 3 EQ8 correctifs par track".

---

## Documents mis à jour

### qrust_artistic_context v1.0 → v1.1

**Ajouts :**
- Section "Philosophie de production — Le traitement dynamique avant tout"
- Règle "max 3 EQ8 correctifs par track" avec rôles épistémiques (Static / Peak Resonance / CDE / Musical Enhancement)
- Liste des bannis étendue avec "traitement statique sans justification"
- 3 exceptions statiques autorisées documentées (rumble, ultra-sonique, parasite)
- Ordre de device chain proposé
- Section "Approche avant-gardiste" clarifiée
- Historique d'évolution interne

**Fichier :** `qrust_artistic_context_v1_1.md`

**Action :** remplacer l'ancien `qrust_artistic_context.md` par cette version v1.1 dans ton repo `docs/brief/`.

### mix_engineer_brief v2.1 → v2.2

**Ajouts :**
- Section "Principe de traitement dynamique par défaut" dans rôle et philosophie
- Section 2.5 enrichie avec roadmap Features 1.5, 6, 7, 8
- Nouvelles phases dans architecture (Phase 3 dynamic HPF/LPF, Phase 6 dynamic enhancement, Phase 7 consolidation EQ8)
- Règle 5.9 "max 3 EQ8 correctifs par track"
- Règle 5.10 "traitement dynamique par défaut"
- Quick reference card enrichie avec règle Qrust EQ8
- Section 8 avec liste des inputs mise à jour

**Fichier :** `mix_engineer_brief_v2_2.md`

**Action :** remplacer `mix_engineer_brief_v2_1.md` par cette version v2.2.

---

## Documents nouveaux

### feature_6_dynamic_hpf_lpf.md

Spec de la feature qui automatise HPF/LPF contextuellement par section.

**Scope :**
- Calcul des fréquences de coupe optimales par section
- Écriture d'automations Freq + IsOn sur bandes 0 (HPF) et 7 (LPF) d'un EQ8
- Respect des caps du profil genre (`hpf_max_hz`, `lpf_min_hz`)
- Crossfades entre sections pour éviter artifacts
- CLI wrapper avec flag `--peak-xlsx` et `--track`

**Effort estimé :** 5.5-7.5h, ~20-27 tests, 5 micro-commits

**Action :** commit dans `docs/features/`.

### feature_7_dynamic_enhancement.md

Spec de la feature qui automatise les boosts musicaux par section.

**Scope :**
- Dataclass `EnhancementIntent` pour décrire les boosts désirés
- Modes explicit / progressive / peaks_dense_mix / section_lock
- Cap par genre profile sur les boosts de présence
- Écriture dans EQ8 "Musical Enhancement" (4ème EQ8 autorisé)
- CLI wrapper avec config YAML/JSON

**Effort estimé :** 6-7h, ~25-34 tests, 6 micro-commits

**Action :** commit dans `docs/features/`.

### feature_8_eq8_consolidation.md

Spec de la feature qui réconcilie les EQ8 accumulés pour respecter la règle 3 max.

**Scope :**
- Classification par UserName ou heuristique
- Détection doublons, chevauchements, merges compatibles
- Merge de bandes avec préservation intégrale des automations
- Mode interactif avec arbitrage utilisateur pour conflits
- CLI wrapper avec mode batch --all-tracks

**Effort estimé :** 8-10h, ~39-51 tests, 6 micro-commits

**Action :** commit dans `docs/features/`.

### roadmap_features_1_8.md

Vue d'ensemble consolidée de toutes les features (livrées + en roadmap), leurs dépendances, l'ordre suggéré de livraison, l'état d'avancement du code source.

**Action :** commit à la racine de `docs/` (pas dans features/) pour lecture facile.

---

## Structure finale suggérée pour ton repo

```
Mix-Analyzer/
├── cde_engine.py
├── cde_apply.py
├── scripts/
│   └── apply_cde_corrections.py
├── docs/
│   ├── README.md (point d'entrée)
│   ├── roadmap_features_1_8.md       ← NOUVEAU (ce document de session)
│   ├── brief/
│   │   ├── mix_engineer_brief_v2_2.md     ← NOUVEAU (remplace v2.1)
│   │   ├── qrust_artistic_context_v1_1.md ← NOUVEAU (remplace v1.0)
│   │   ├── session_bootstrap_template.md
│   │   ├── genre_music_profiles.json
│   │   └── ableton_devices_mapping_v2_2.json
│   ├── archive/
│   │   ├── v1_8_ai_context_sheet_spec_ARCHIVED.md
│   │   ├── qrust_artistic_context_v1_0.md  ← (ancienne version)
│   │   └── mix_engineer_brief_v2_1.md      ← (ancienne version)
│   └── features/
│       ├── feature_1_correction_conditionnelle.md (livrée)
│       ├── feature_1_5_sidechain.md (à rédiger)
│       ├── feature_2_q_dynamique.md
│       ├── feature_3_sections_locators.md (livrée)
│       ├── feature_3_5_TFP.md (livrée)
│       ├── feature_3_6_CDE.md (livrée)
│       ├── feature_4_eq8_stereo_ms.md
│       ├── feature_5_autres_devices.md
│       ├── feature_6_dynamic_hpf_lpf.md      ← NOUVEAU
│       ├── feature_7_dynamic_enhancement.md  ← NOUVEAU
│       └── feature_8_eq8_consolidation.md    ← NOUVEAU
├── tests/
└── README.md
```

**Archivage suggéré :** les anciennes versions de `qrust_artistic_context_v1_0.md` et `mix_engineer_brief_v2_1.md` peuvent être déplacées dans `docs/archive/` plutôt que supprimées, pour traçabilité historique (comme tu as fait pour le spec v1.8).

---

## Commandes git suggérées

```bash
# Mise à jour des docs vivants
git mv docs/brief/qrust_artistic_context.md docs/archive/qrust_artistic_context_v1_0.md
git mv docs/brief/mix_engineer_brief_v2_1.md docs/archive/mix_engineer_brief_v2_1.md

# Ajout des nouveaux
git add docs/brief/qrust_artistic_context_v1_1.md
git add docs/brief/mix_engineer_brief_v2_2.md
git add docs/features/feature_6_dynamic_hpf_lpf.md
git add docs/features/feature_7_dynamic_enhancement.md
git add docs/features/feature_8_eq8_consolidation.md
git add docs/roadmap_features_1_8.md

# Commit
git commit -m "docs: brief v2.2, qrust context v1.1, specs F6/F7/F8, roadmap"
git push origin main
```

Note : le `session_bootstrap_template.md` devrait aussi être mis à jour pour pointer vers `brief_v2_2` et `qrust_context_v1_1`. À faire dans un commit séparé ou inclus dans celui-ci.

---

## Prochaine décision attendue

Avec ces documents en main, tu peux :

**Option A** — Relancer F1.5 session terrain sur Acid Drops avec la nouvelle documentation à jour

**Option B** — Rédiger la spec Feature 1.5 sidechain manquante avant de bouger

**Option C** — Valider les specs F6/F7/F8 et lancer la priorisation (laquelle développer en premier ?)

**Option D** — Autre direction

Dis-moi ce que tu veux faire ensuite.
