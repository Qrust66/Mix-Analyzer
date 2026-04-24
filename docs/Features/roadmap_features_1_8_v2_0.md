# Roadmap Mix Analyzer + Feature Corrections — vue d'ensemble

**Version :** 2.0
**Date dernière modification :** 2026-04-23
**Hérite de :** `documentation_discipline.md` (règles de rédaction)
**Statut :** Document vivant, mis à jour après chaque livraison de feature majeure ou décision structurante

**À l'attention de :** Alexandre Couture (auteur), toute IA conversationnelle (Claude Opus en session), toute IA d'exécution (Claude Code), tout futur collaborateur.

**Historique d'évolution :**
- v1.0 — création initiale (2026-04-23 après-midi). Couvrait philosophie globale, état d'avancement des features, dépendances, ordre suggéré (3 séquences), état du code source, documentation associée, prochaines décisions, métriques de succès.
- v2.0 (ce document) — restructuration majeure post-audit complétude. Préservation intégrale du contenu v1.0 + alignement avec architecture documentaire actuelle (`qrust_professional_context.md`, `project_acid_drops_context.md`, `documentation_discipline.md`, briefs et features en versions courantes). Ajouts : section "Décisions architecturales validées" (10 décisions), section "Comment utiliser cette roadmap", convention de versioning des features, métriques de succès enrichies, quick card. Mise à jour des références documentaires obsolètes.

**Principe de préservation :** ce document préserve intégralement le contenu de v1.0. Toutes les sections originales sont présentes — seulement étendues, mises à jour avec les bonnes références, et enrichies. Les ajouts de v2.0 sont signalés explicitement avec annotation "(nouveau en v2.0)" ou "(mis à jour en v2.0)".

**Purpose :** vue consolidée de toutes les Features, leurs dépendances, leur état d'avancement, l'ordre suggéré de livraison, et les décisions architecturales validées au fil du projet.

---

## 1 — Comment utiliser cette roadmap (nouveau en v2.0)

### 1.1 À qui s'adresse-t-elle

**Alexandre :** vue d'ensemble du projet pour planifier ses sessions, prioriser les features, suivre la progression.

**IA conversationnelle (Claude Opus en session) :** comprendre où en est le projet en début de session, identifier la prochaine feature à travailler, savoir quels documents charger.

**IA d'exécution (Claude Code) :** identifier la spec d'une feature à implémenter, comprendre ses dépendances avec les features livrées et à venir.

**Futur collaborateur (humain ou IA) :** onboarding rapide sur le projet, état de l'art à un moment donné.

### 1.2 Quand consulter cette roadmap

**Toujours** au début d'une session impliquant le projet Mix-Analyzer ou une feature spécifique.

**Toujours** avant de démarrer le développement d'une feature pour vérifier ses dépendances.

**Optionnellement** pour audit historique des décisions ou pour onboarding.

### 1.3 Quand mettre à jour cette roadmap

Mise à jour obligatoire après :

- **Livraison d'une feature** (passer de "Planifiée" à "Livrée", ajouter le commit hash)
- **Décision architecturale validée** (ajouter à Section 4)
- **Évolution d'une spec de feature** (mettre à jour la version dans le tableau)
- **Changement d'ordre de livraison** (mettre à jour Section 7)
- **Ajout d'une nouvelle feature** dans le scope

Mise à jour optionnelle :
- Mise à jour des MD5 du code source après refactoring
- Enrichissement des métriques de succès si nouvelles dimensions

### 1.4 Procédure de mise à jour

Suivre `documentation_discipline.md` section 4 :

1. Lire la roadmap intégralement
2. Identifier précisément ce qui doit changer
3. Modifier in-place en préservant l'existant
4. Incrémenter version + enrichir historique
5. Signaler nouveautés explicitement
6. Tester complétude
7. Archiver ancienne version dans `docs/archive/`
8. Livrer avec annonce de changements

---

## 2 — Philosophie globale

Le Mix Analyzer + Corrector Qrust vise à **remplacer les plugins commerciaux de traitement adaptatif** (Pro-Q 4 Dynamic, soothe2, Gullfoss) par une approche basée sur **Ableton EQ Eight natif piloté par automations précises**.

Avantages de cette approche :

- **Transparence totale** — les courbes sont visibles, pas cachées dans un DSP propriétaire
- **Contrôle granulaire** — l'ingénieur peut modifier n'importe quelle automation
- **Analyse amont robuste** — Mix Analyzer drive les décisions avec métriques quantitatives
- **Réversibilité** — chaque feature peut être bypassée indépendamment
- **Cohérence avec le workflow** — tout vit dans le .als, pas dans des presets plugins
- **Auditabilité** (nouveau en v2.0) — un autre ingénieur (ou une IA en session future) peut lire les décisions dans le .als
- **Commercialisable à terme** (nouveau en v2.0) — angle unique sur le marché, pas un clone d'outils existants

Vision finale : **100% du traitement spectral contextuel**, avec un minimum de plugins commerciaux non-mappés.

Cette philosophie est formalisée en détail dans `qrust_professional_context.md` section 4.1.

---

## 3 — État d'avancement des features

### 3.1 Features livrées (mis à jour en v2.0)

| ID | Nom | Livrée | Description | Spec |
|---|---|---|---|---|
| 3 | Sections & Locators | ✓ | Détection automatique des sections via Locators Ableton | `feature_3_sections_locators.md` |
| 3.5 | TFP (Track-Function-Profile) | ✓ | Classification Hero/Support/Ambient × R/H/M/T + score cohérence par section | `feature_3_5_TFP.md` |
| 3.6 | CDE (Correction Decision Engine) | ✓ | Diagnostics structurés par conflit avec recommandations | `feature_3_6_CDE.md` |
| 1 | CDE auto-apply (CLI) | ✓ | Applique automatiquement les corrections EQ des diagnostics CDE | `feature_1_correction_conditionnelle.md` |
| — | AI Context sheet | ✓ | Sheet consolidée dans le rapport Mix Analyzer | (intégré au Mix Analyzer core) |
| — | Peak Resonance generator | ✓ | `write_resonance_suppression` qui produit les EQ8 Peak Resonance dynamiques | (intégré au Mix Analyzer core) |

**Détails livraisons récentes :**

- **Feature 1 livrée le 2026-04-23 :** dernier commit `be371f7`, 429/429 tests passants, CLI complet avec dry-run, peak-following, revert, filtering. Couvre ~530 des ~1050 diagnostics typiques (les approches EQ).

### 3.2 Features en roadmap (mis à jour en v2.0)

| ID | Nom | Spec courante | Statut spec | Priorité | Effort estimé | Tests cibles |
|---|---|---|---|---|---|---|
| 1.5 | Sidechain auto-apply (Kickstart 2) | non rédigée | À créer | haute | 4-6h (estimé) | ~15-20 |
| 6 | Dynamic HPF/LPF per section | `feature_6_dynamic_hpf_lpf_v1_1.md` | v1.1 — Q1-Q5 en attente | haute | 5.5-7.5h | ~20-27 |
| 7 | Dynamic musical enhancement | `feature_7_dynamic_enhancement_v1_1.md` | v1.1 — Q1-Q4 en attente | moyenne | 6-7h | ~25-34 |
| 8 | EQ8 consolidation / reconciliation | `feature_8_eq8_consolidation_v1_1.md` | v1.1 — Q1-Q4 en attente | basse | 8-10h | ~39-51 |
| 4 | EQ8 Stereo / M-S | `feature_4_eq8_stereo_ms.md` | v1.0 (à auditer) | basse | non estimé | non estimé |
| 5 | Autres devices mappés | `feature_5_autres_devices.md` | v1.0 (à auditer) | basse | non estimé | non estimé |
| 2 | Q dynamique intégré CDE | `feature_2_q_dynamique.md` | v1.0 (à auditer) | moyenne | non estimé | non estimé |
| 9 | Genre profiles intégrés programmatiquement | non rédigée | À créer | basse | non estimé | non estimé |

### 3.3 Convention de versioning des specs (nouveau en v2.0)

Pour suivre l'évolution des specs de features :

- **v1.0** — création initiale, draft non auditée
- **v1.1** — audit complétude appliqué, conforme à `documentation_discipline.md`, prête pour validation utilisateur
- **v1.2** — Q1-QN validées par utilisateur, spec figée pour démarrage dev
- **v1.3+** — ajustements pendant le dev (rare, à éviter sauf découverte technique)
- **v2.0** — refactoring majeur de la spec (changement d'API, nouveau scope)

**Statut courant de la roadmap :**
- F6, F7, F8 : en v1.1 (audit complétude fait), Q en attente avant v1.2

### 3.4 État détaillé par feature en attente (nouveau en v2.0)

**Feature 1.5 — Sidechain auto-apply**

- **Statut :** spec à rédiger
- **Bloqueurs :** aucun, mais probablement pertinent d'attendre validation terrain F1 d'abord
- **Effort spec :** 1-2h pour rédaction + audit
- **Priorité :** haute (complète Feature 1 sur les 520 diagnostics sidechain restants)

**Feature 6 — Dynamic HPF/LPF**

- **Statut :** spec v1.1 livrée, Q1-Q5 en attente
- **Q1 :** convention bande 0 = HPF, bande 7 = LPF par défaut ?
- **Q2 :** cible Peak Resonance existant ou nouvel EQ8 dédié ?
- **Q3 :** crossfade par défaut 2.0 beats ?
- **Q4 :** stratégie IsOn (constant vs alternant) ?
- **Q5 :** priorité dans la roadmap ?
- **Bloqueurs :** validation Q1-Q5
- **Modules à créer :** `mix_analyzer/dynamic_hpf_lpf.py`, `mix_analyzer/dynamic_hpf_lpf_helpers.py`, `scripts/apply_dynamic_hpf_lpf.py`

**Feature 7 — Dynamic musical enhancement**

- **Statut :** spec v1.1 livrée, Q1-Q4 en attente
- **Q1 :** YAML par défaut acceptable pour config ?
- **Q2 :** convention "Musical Enhancement" comme 4ème EQ8 ?
- **Q3 :** mode `peaks_dense_mix` livré v1 (experimental) ou reporté v2 ?
- **Q4 :** priorité dans la roadmap ?
- **Bloqueurs :** validation Q1-Q4 + Q1 de F6 (convention bandes 0/7)
- **Modules à créer :** `mix_analyzer/dynamic_enhancement.py`, `mix_analyzer/dynamic_enhancement_helpers.py`, `mix_analyzer/dynamic_enhancement_loader.py`, `scripts/apply_dynamic_enhancement.py`

**Feature 8 — EQ8 consolidation**

- **Statut :** spec v1.1 livrée, Q1-Q4 en attente
- **Q1 :** mode interactive=True par défaut ?
- **Q2 :** seuil de confiance heuristique 75% ?
- **Q3 :** dry_run=True par défaut ?
- **Q4 :** priorité dans la roadmap ?
- **Bloqueurs :** validation Q1-Q4 + idéalement F1, F1.5, F6, F7 livrées d'abord
- **Modules à créer :** `mix_analyzer/eq8_consolidation.py`, `mix_analyzer/eq8_consolidation_classifier.py`, `mix_analyzer/eq8_consolidation_planner.py`, `mix_analyzer/eq8_consolidation_merger.py`, `scripts/consolidate_eq8_chain.py`

---

## 4 — Décisions architecturales validées (nouveau en v2.0)

Toutes les décisions structurantes prises au cours du projet, tracées pour audit historique et onboarding.

### Décision 1 — Architecture documentaire scindée

**Date :** 2026-04-23
**Décision :** scinder l'ancien `qrust_artistic_context.md` (qui mélangeait identité professionnelle et paramètres projet) en deux documents distincts :
- `qrust_professional_context.md` — invariant Qrust (identité, setup, philosophie, règles collaboration)
- `project_<nom>_context.md` — paramètres spécifiques par projet (genre, targets, références, état)

**Justification :** scalabilité pour futurs projets, charge cognitive réduite, séparation claire des responsabilités, hiérarchie claire en cas de nuance projet vs invariant.

**Documents impactés :** création des deux nouveaux documents, archivage de `qrust_artistic_context_v1_1.md` avec fichier de redirection `qrust_artistic_context_v1_1_DEPRECATED.md`.

### Décision 2 — Convention "max 3 EQ8 correctifs par track"

**Date :** 2026-04-23
**Décision :** chaque track porte maximum 3 EQ8 correctifs (Static / Peak Resonance / CDE Correction) + 1 EQ8 Musical Enhancement optionnel.

**Justification :** séparation épistémique claire, bypass indépendant possible, revert granulaire, pas de risque de casser le travail précédent, permet aux features suivantes de cibler leur EQ8 sans interférer.

**Documents impactés :** `qrust_professional_context.md` section 4.2, `mix_engineer_brief_v2_3.md` section 5.9.

### Décision 3 — Philosophie "100% dynamique par défaut"

**Date :** 2026-04-23
**Décision :** aucun traitement spectral statique sans justification documentée. Seules 3 exceptions autorisées : sub-sonique < 20 Hz, ultra-sonique > 20 kHz, parasites constants.

**Justification :** un traitement statique fige un compromis non-optimal, le dynamique permet d'adapter à chaque section et à chaque moment du morceau. Approche cohérente avec processeurs commerciaux (Pro-Q 4 Dynamic, soothe2, Gullfoss) mais via automation EQ8 native (transparence + contrôle).

**Documents impactés :** `qrust_professional_context.md` section 4.1, `mix_engineer_brief_v2_3.md` sections 1 et 5.10, specs F6/F7/F8.

### Décision 4 — Approche track-par-track pour les features automatisées

**Date :** 2026-04-23
**Décision :** par défaut, les features qui modifient plusieurs tracks (F1, F6, F7) procèdent en mode track-par-track avec validation après chaque, plutôt que batch multi-track.

**Justification :** un essai antérieur de batch sur 4 tracks a généré des erreurs. Track-par-track permet de valider à l'oreille et d'isoler les problèmes. Le batch n'est acceptable qu'après plusieurs tracks validées en single mode.

**Documents impactés :** `qrust_professional_context.md` section 4.3, `mix_engineer_brief_v2_3.md` section 4 Phase 2/3/6, specs F1.5/F6/F7/F8.

### Décision 5 — Approche EQ Eight + automation au lieu de plugins commerciaux dynamiques

**Date :** 2026-04-23
**Décision :** EQ Eight natif Ableton avec automations précises est préféré aux plugins commerciaux (Pro-Q 4 Dynamic, soothe2, Gullfoss) pour les corrections automatisées par les Features 1-8.

**Justification :** transparence totale, contrôle granulaire, auditabilité, réversibilité, cohérence avec analyse amont, pas de dépendance plugins commerciaux. Approche avant-gardiste — angle commercialisable à terme.

**Documents impactés :** `qrust_professional_context.md` section 4.4, `roadmap_features_1_8.md` section 2.

### Décision 6 — Pattern micro-commits anti-timeout

**Date :** 2026-04-23
**Décision :** les features sont développées en micro-commits courts (~30 min chacun), avec séparation stricte entre commits de code et commits de tests pour éviter les timeouts API Claude Code.

**Justification :** essais antérieurs avec commits de plus de 1h ont généré des timeouts. Micro-commits avec séparation code/tests permet de garder chaque session courte et focalisée.

**Documents impactés :** specs F6/F7/F8 (12 commits chacune avec séparation), `documentation_discipline.md` section 3.2.

### Décision 7 — Création de `documentation_discipline.md` comme méta-règle

**Date :** 2026-04-23
**Décision :** création d'un document permanent `documentation_discipline.md` qui formalise les 7 règles de rédaction et la procédure d'évolution des documents.

**Trigger :** découverte d'une condensation silencieuse du brief v2.1 → v2.2 (35 Ko → 16 Ko sans annonce). Besoin de formaliser le standard de complétude pour les 3 intervenants (Alexandre, IA conversationnelle, Claude Code).

**Documents impactés :** tous les documents du repo héritent maintenant de `documentation_discipline.md`.

### Décision 8 — Cible loudness Acid Drops -10 LUFS / -14 LUFS

**Date :** validée précédemment (avant cette session)
**Décision :** Acid Drops aura deux masters partageant le même mix :
- Master club : -10 LUFS, PLR 8-10, TP -1 dBFS
- Master Spotify : -14 LUFS, PLR 10-13, TP -1 dBFS

**Justification :** -10 LUFS pour usage SoundCloud + DJ pool, -14 LUFS pour normalisation streaming.

**Documents impactés :** `project_acid_drops_context.md` section 4.1.

### Décision 9 — F8 séparation épistémique préférée à consolidation agressive

**Date :** 2026-04-23
**Décision :** F8 préfère garder les EQ8 séparés (Static / Peak Resonance / CDE / Musical) si possible, plutôt que tout fusionner dans un EQ8 unique.

**Justification :** bypass indépendant, clarté audit, revert granulaire, séparation des responsabilités épistémiques. Consolidation agressive seulement si demandée explicitement par l'utilisateur.

**Documents impactés :** `feature_8_eq8_consolidation_v1_1.md` section 2.2 (Cas 2).

### Décision 10 — Validation utilisateur Q1-QN avant démarrage dev

**Date :** 2026-04-23
**Décision :** chaque spec de feature contient une section "Dépendances validation utilisateur avant dev" listant les questions Q1-QN à trancher. Le dev ne démarre pas avant que ces Q soient résolues.

**Justification :** évite que Claude Code prenne des décisions par défaut qui ne correspondraient pas à la vision d'Alexandre. Force l'arbitrage explicite des choix de design.

**Documents impactés :** `feature_6_dynamic_hpf_lpf_v1_1.md` section 12, `feature_7_dynamic_enhancement_v1_1.md` section 13, `feature_8_eq8_consolidation_v1_1.md` section 12.

---

## 5 — Dépendances entre features

```
                              Feature 3 (sections)
                                      │
                      ┌───────────────┼───────────────┐
                      ▼               ▼               ▼
                Feature 3.5 (TFP)  Feature 3.6 (CDE)  Mix Analyzer core
                      │               │
                      └───────┬───────┘
                              ▼
                       Feature 1 (CDE apply)  ← LIVRÉE, point de bascule
                              │
          ┌───────────────────┼───────────────────────┐
          ▼                   ▼                       ▼
   Feature 1.5        Feature 6            Feature 7
   (sidechain)        (HPF/LPF dynamic)    (musical enhancement)
          │                   │                       │
          └───────────────────┼───────────────────────┘
                              ▼
                       Feature 8 (consolidation)
                              │
                              ▼
                      [Features 2, 4, 5 selon priorité]
```

**Points clés (mis à jour en v2.0) :**

- Feature 1 est le **pivot** : toutes les features correctives suivantes en bénéficient
- Features 1.5, 6, 7 sont **techniquement indépendantes entre elles** mais ont des interactions :
  - F6 et F7 partagent `_compute_crossfade_for_boundary` (réutilisation)
  - F7 hérite de la convention bandes 0/7 réservées HPF/LPF de F6 (Q1 de F6 affecte F7)
- Feature 8 attend **idéalement** que F1, F1.5, F6, F7 existent pour avoir matière à consolider
- Feature 8 peut techniquement tourner avec seulement F1 (consolidation simple), mais bénéfice maximal après toutes les autres
- Feature 2 (Q dynamique) peut être fusionnée dans Feature 6 ou Feature 7 selon implémentation, à arbitrer

---

## 6 — Ordre suggéré de livraison

### 6.1 Séquence A — Validation terrain d'abord (recommandée)

**Avantage :** valider empiriquement avant d'investir dans le dev supplémentaire.

1. **F1.5 terrain sur Acid Drops** (priorité absolue)
   - Session mastering réelle avec Feature 1 livrée
   - Observation de l'impact à l'oreille
   - Décision : approche validée ou à ajuster ?
   - Durée : 1-2 sessions, 1-2h chacune

2. **Feature 1.5 sidechain** (si F1 validée)
   - Élargit la couverture à ~520 diagnostics sidechain
   - Complète Feature 1 sur le périmètre CDE complet

3. **Feature 6 HPF/LPF dynamic**
   - Ajoute la couche HPF/LPF contextuelle
   - Test terrain sur une section puis élargissement

4. **Feature 7 enhancement**
   - Ajoute les boosts musicaux dynamiques
   - Test terrain comparatif avec et sans

5. **Feature 8 consolidation**
   - Consolide les EQ8 accumulés si surnombre

6. **Features 2, 4, 5** (selon besoin terrain)
   - Q dynamique intégré au CDE
   - Stereo/MS
   - Autres devices

### 6.2 Séquence B — Dev avant session (risque élevé)

Tout développer avant de toucher Acid Drops. Déconseillé car risque d'accumuler 3-4 features non validées terrain.

### 6.3 Séquence C — Parallélisation (si plusieurs sessions possible)

- Session mastering Acid Drops en cours (toi)
- Feature 6 en dev parallèle (Claude Code)
- Feature 1.5 rédaction spec (moi)
- Puis intégration progressive

Viable si tu as la bande passante pour gérer plusieurs chantiers en parallèle.

### 6.4 Ma recommandation

**Séquence A, avec F1.5 terrain immédiate comme prochaine étape.**

Raison : les 3 semaines de dev récentes n'ont pas encore été validées par ton oreille sur ton vrai mix. Avant d'investir 20+ heures dans F6/F7/F8/1.5, il faut confirmer que F1 produit un résultat musicalement satisfaisant.

Si F1 terrain est concluante, on enchaîne avec confiance. Si F1 révèle des problèmes, on les corrige avant de construire par-dessus.

---

## 7 — État d'avancement du code source

**Repo :** Mix-Analyzer (privé)
**Branche principale :** `main`
**Tests totaux :** 429/429 passants (post-Feature 1, 2026-04-23)
**Dernier commit Feature 1 :** `be371f7`

### 7.1 Modules courants Mix Analyzer v2.7.0

| Module | MD5 | Description |
|---|---|---|
| `mix_analyzer.py` | 7619b779 | Module principal, orchestration |
| `section_detector.py` | 5f71605a | Détection sections via Locators |
| `tfp_parser.py` | 09ca84af | Parser des préfixes TFP |
| `tfp_coherence.py` | d7044505 | Score de cohérence TFP |
| `cde_engine.py` | b0e07898 | Correction Decision Engine |
| `cde_apply.py` | (dans la branche main) | CLI Feature 1 |
| `automation_map.py` | ead15094 | Mapping audibility |
| `als_utils.py` | c2de7487 | Helpers XML .als |
| `feature_storage.py` | 7dd0be7e | Stockage des features extraites |
| `spectral_evolution.py` | 3ccc5c12 | Évolution spectrale |
| `user_config.py` | e19e9b1e | Config utilisateur |
| `eq8_automation.py` | e8d64de7 | Helpers d'écriture EQ8 |

### 7.2 Modules à créer (planifiés) (nouveau en v2.0)

| Module | Feature | Statut |
|---|---|---|
| `mix_analyzer/sidechain_apply.py` | F1.5 | À créer après spec |
| `mix_analyzer/dynamic_hpf_lpf.py` | F6 | À créer après v1.2 |
| `mix_analyzer/dynamic_hpf_lpf_helpers.py` | F6 | À créer après v1.2 |
| `mix_analyzer/dynamic_enhancement.py` | F7 | À créer après v1.2 |
| `mix_analyzer/dynamic_enhancement_helpers.py` | F7 | À créer après v1.2 |
| `mix_analyzer/dynamic_enhancement_loader.py` | F7 | À créer après v1.2 |
| `mix_analyzer/eq8_consolidation.py` | F8 | À créer après v1.2 |
| `mix_analyzer/eq8_consolidation_classifier.py` | F8 | À créer après v1.2 |
| `mix_analyzer/eq8_consolidation_planner.py` | F8 | À créer après v1.2 |
| `mix_analyzer/eq8_consolidation_merger.py` | F8 | À créer après v1.2 |

### 7.3 Scripts CLI à créer (planifiés) (nouveau en v2.0)

| Script | Feature | Statut |
|---|---|---|
| `scripts/apply_sidechain_corrections.py` | F1.5 | À créer après spec |
| `scripts/apply_dynamic_hpf_lpf.py` | F6 | À créer après v1.2 |
| `scripts/apply_dynamic_enhancement.py` | F7 | À créer après v1.2 |
| `scripts/consolidate_eq8_chain.py` | F8 | À créer après v1.2 |

---

## 8 — Documentation associée (mis à jour en v2.0)

### 8.1 Documents méta

- `docs/documentation_discipline.md` v1.0 — règles permanentes de rédaction et d'évolution

### 8.2 Documents brief / contextuels (vivants)

- `docs/brief/qrust_professional_context.md` v1.0 — socle invariant Qrust (identité, setup, philosophie, règles collaboration)
- `docs/brief/mix_engineer_brief_v2_3.md` — méthodologie mix/mastering générique
- `docs/brief/projects/project_acid_drops_context.md` v1.0 — contexte spécifique Acid Drops

### 8.3 Documents techniques de référence (partagés)

- `docs/brief/genre_music_profiles.json` — calibration par genre et track type
- `docs/brief/ableton_devices_mapping_v2_2.json` — mapping programmatique des devices

### 8.4 Documents projet (par projet)

- `Acid_Drops_CHANGELOG.md` (à créer en racine projet) — historique des sessions Acid Drops

### 8.5 Specs des Features

| Feature | Document | Version courante | Statut |
|---|---|---|---|
| F3 Sections | `docs/features/feature_3_sections_locators.md` | (livrée, version originale) | ✓ |
| F3.5 TFP | `docs/features/feature_3_5_TFP.md` | (livrée, version originale) | ✓ |
| F3.6 CDE | `docs/features/feature_3_6_CDE.md` | (livrée, version originale) | ✓ |
| F1 CDE apply | `docs/features/feature_1_correction_conditionnelle.md` | (livrée, version originale) | ✓ |
| F1.5 Sidechain | `docs/features/feature_1_5_sidechain.md` | À rédiger | ✗ |
| F2 Q dynamique | `docs/features/feature_2_q_dynamique.md` | v1.0 (à auditer) | ⚠️ |
| F4 Stereo MS | `docs/features/feature_4_eq8_stereo_ms.md` | v1.0 (à auditer) | ⚠️ |
| F5 Autres devices | `docs/features/feature_5_autres_devices.md` | v1.0 (à auditer) | ⚠️ |
| F6 HPF/LPF dynamique | `docs/features/feature_6_dynamic_hpf_lpf_v1_1.md` | v1.1 (Q en attente) | ⚠️ |
| F7 Enhancement | `docs/features/feature_7_dynamic_enhancement_v1_1.md` | v1.1 (Q en attente) | ⚠️ |
| F8 Consolidation | `docs/features/feature_8_eq8_consolidation_v1_1.md` | v1.1 (Q en attente) | ⚠️ |
| Roadmap | `docs/roadmap_features_1_8.md` (ce document) | v2.0 | ✓ |

### 8.6 Documents archivés (mis à jour en v2.0)

| Document archivé | Date archivage | Remplacé par |
|---|---|---|
| `docs/archive/v1_8_ai_context_sheet_spec_ARCHIVED.md` | (avant 2026-04-23) | Mix Analyzer v2.7.0 live |
| `docs/archive/qrust_artistic_context_v1_0.md` | 2026-04-23 | `qrust_artistic_context_v1_1.md` puis split |
| `docs/archive/qrust_artistic_context_v1_1_DEPRECATED.md` | 2026-04-23 | `qrust_professional_context.md` + `project_acid_drops_context.md` (avec fichier de redirection) |
| `docs/archive/mix_engineer_brief_v2.md` | 2026-04-23 | `mix_engineer_brief_v2_1.md` |
| `docs/archive/mix_engineer_brief_v2_1.md` | 2026-04-23 | `mix_engineer_brief_v2_2_complet.md` |
| `docs/archive/mix_engineer_brief_v2_2.md` (défectueux) | 2026-04-23 | `mix_engineer_brief_v2_2_complet.md` (illustre violation `documentation_discipline.md`) |
| `docs/archive/mix_engineer_brief_v2_2_complet.md` | 2026-04-23 | `mix_engineer_brief_v2_3.md` |
| `docs/archive/feature_6_dynamic_hpf_lpf.md` (v1.0) | 2026-04-23 | `feature_6_dynamic_hpf_lpf_v1_1.md` |
| `docs/archive/feature_7_dynamic_enhancement.md` (v1.0) | 2026-04-23 | `feature_7_dynamic_enhancement_v1_1.md` |
| `docs/archive/feature_8_eq8_consolidation.md` (v1.0) | 2026-04-23 | `feature_8_eq8_consolidation_v1_1.md` |
| `docs/archive/roadmap_features_1_8_v1_0.md` | 2026-04-23 | `roadmap_features_1_8.md` (ce document, v2.0) |

---

## 9 — Prochaines décisions structurantes (mis à jour en v2.0)

### 9.1 Décisions immédiates (cette session ou prochaine)

1. **Validation Q1-Q5 de Feature 6** — bandes 0/7 réservées, EQ8 cible, crossfade, IsOn, priorité
2. **Validation Q1-Q4 de Feature 7** — format YAML, convention 4ème EQ8, mode peaks_dense_mix, priorité
3. **Validation Q1-Q4 de Feature 8** — interactive default, seuil heuristique, dry_run default, priorité
4. **Confirmation séquence de livraison** — A (recommandée) ou autre

### 9.2 Décisions à moyen terme

5. **Rédaction spec Feature 1.5 sidechain** — à faire dans une session future
6. **Audit complétude des specs F2, F4, F5** — à faire si on prévoit de les développer prochainement
7. **Planification de la première session terrain F1.5 sur Acid Drops** — date et scope

### 9.3 Décisions à long terme

8. **Stratégie commercialisation outil** — partage avec autres producteurs industrial ?
9. **Reproductibilité sur d'autres genres** — tester sur Techno, Bass Music, Experimental ?
10. **Évolution Mix Analyzer vers Feature 9** (genre profiles intégrés au CDE engine programmatiquement) ?

---

## 10 — Métriques de succès du projet global (enrichies en v2.0)

### 10.1 Niveau technique

- ✅ Feature set complet (F1 + F1.5 + F6 + F7 + F8 livrés et testés)
- ✅ Tests : >500 passants après F8 (cible cumulative)
- ✅ Coverage > 85% sur les modules de chaque feature (nouveau en v2.0)
- ✅ Zero régression sur Acid Drops après passe complète
- ✅ Stratégie anti-timeout respectée (12 commits par feature avec séparation code/tests) (nouveau en v2.0)

### 10.2 Niveau artistique

- ✅ Acid Drops atteint Mix Health Score > 75 (actuellement 51.1)
- ✅ TFP Coherence Drop 1/Drop 2/Chorus moyens > 70
- ✅ Target loudness -10 LUFS atteint avec PLR 8-10 dB préservé
- ✅ Validation à l'oreille sur système club et casque
- ✅ Validation auditive Alexandre sur tous les enhancements appliqués (nouveau en v2.0)

### 10.3 Niveau documentaire (nouveau en v2.0)

- ✅ Conformité 100% à `documentation_discipline.md` sur tous les documents vivants
- ✅ Aucune condensation silencieuse détectée (red flag taille)
- ✅ Tous les documents passent le test du nouvel intervenant
- ✅ Archivage propre avec fichiers de redirection si nécessaire
- ✅ Historique d'évolution explicite sur chaque document

### 10.4 Niveau collaboration (nouveau en v2.0)

- ✅ Cohérence entre les 3 intervenants (Alexandre, IA conv, Claude Code)
- ✅ Aucune ambiguïté irréductible dans les specs avant démarrage dev
- ✅ Q1-QN résolues avant chaque dev de feature
- ✅ Changelog projet (`<project>_CHANGELOG.md`) maintenu à jour

### 10.5 Niveau commercial (objectif long terme)

- ✅ Outil utilisable par d'autres producteurs industrial
- ✅ Documentation complète pour onboarding
- ✅ Reproductibilité sur d'autres genres (au moins Techno, Bass Music, Experimental)
- ✅ Article ou démonstration publique de l'approche avant-gardiste (nouveau en v2.0)

---

## 11 — Référence rapide (quick card, nouveau en v2.0)

**Statut global du projet :**
- Features livrées : F3, F3.5, F3.6, F1, AI Context, Peak Resonance generator
- Features en attente Q : F6, F7, F8 (specs v1.1 prêtes)
- Features à créer : F1.5 (spec), F2/F4/F5 (à auditer), F9 (future)

**Prochaine action recommandée :**
Validation Q1-Q5 de F6 + Q1-Q4 de F7 + Q1-Q4 de F8, puis démarrage dev selon Séquence A.

**Documents vivants à charger pour toute session :**
1. `documentation_discipline.md`
2. `qrust_professional_context.md`
3. `mix_engineer_brief_v2_3.md`
4. `project_<nom>_context.md` (du projet courant)
5. `roadmap_features_1_8.md` (ce document)

**Effort total restant pour features en attente :**
- F1.5 : ~4-6h (estimé, spec à rédiger)
- F6 : 5.5-7.5h
- F7 : 6-7h
- F8 : 8-10h
- **Total : ~24-30h** de dev + validations terrain entre chaque

**Roadmap sur 1-2 mois selon le rythme.**

**Décisions architecturales validées :** 10 (voir Section 4)

**Documents archivés :** 11 (voir Section 8.6)

---

**Fin roadmap v2.0. Mise à jour attendue après validation Q1-QN des features F6/F7/F8, ou après livraison d'une nouvelle feature, ou après décision architecturale structurante.**
