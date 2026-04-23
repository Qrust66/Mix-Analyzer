# Roadmap Mix Analyzer + Feature Corrections — vue d'ensemble

**Version :** 1.0
**Date :** 2026-04-23
**Purpose :** vue consolidée de toutes les Features, leurs dépendances, leur état d'avancement, l'ordre suggéré de livraison.

---

## Philosophie globale

Le Mix Analyzer + Corrector Qrust vise à **remplacer les plugins commerciaux de traitement adaptatif** (Pro-Q 4 Dynamic, soothe2, Gullfoss) par une approche basée sur **Ableton EQ Eight natif piloté par automations précises**.

Avantages de cette approche :

- Transparence totale — les courbes sont visibles, pas cachées dans un DSP propriétaire
- Contrôle granulaire — l'ingénieur peut modifier n'importe quelle automation
- Analyse amont robuste — Mix Analyzer drive les décisions avec métriques quantitatives
- Réversibilité — chaque feature peut être bypassée indépendamment
- Cohérence avec le workflow — tout vit dans le .als, pas dans des presets plugins

Vision finale : **100% du traitement spectral contextuel**, avec un minimum de plugins commerciaux non-mappés.

---

## État d'avancement des features

### Features livrées

| ID | Nom | Livrée | Description |
|---|---|---|---|
| 3 | Sections & Locators | ✓ | Détection automatique des sections via Locators Ableton |
| 3.5 | TFP (Track-Function-Profile) | ✓ | Classification Hero/Support/Ambient × R/H/M/T + score cohérence par section |
| 3.6 | CDE (Correction Decision Engine) | ✓ | Diagnostics structurés par conflit avec recommandations |
| 1 | CDE auto-apply (CLI) | ✓ | Applique automatiquement les corrections EQ des diagnostics CDE |
| — | AI Context sheet | ✓ | Sheet consolidée dans le rapport Mix Analyzer |
| — | Peak Resonance generator | ✓ | `write_resonance_suppression` qui produit les EQ8 Peak Resonance dynamiques |

### Features en roadmap (non démarrées)

| ID | Nom | Spec | Priorité | Effort estimé |
|---|---|---|---|---|
| 1.5 | Sidechain auto-apply (Kickstart 2) | non rédigée | haute | 4-6h |
| 6 | Dynamic HPF/LPF per section | `feature_6_dynamic_hpf_lpf.md` | haute | 5.5-7.5h |
| 7 | Dynamic musical enhancement | `feature_7_dynamic_enhancement.md` | moyenne | 6-7h |
| 8 | EQ8 consolidation / reconciliation | `feature_8_eq8_consolidation.md` | basse | 8-10h |
| 4 | EQ8 Stereo / M-S | spec existante `feature_4_eq8_stereo_ms.md` | basse | ? |
| 5 | Autres devices mappés | spec existante `feature_5_autres_devices.md` | basse | ? |
| 2 | Q dynamique intégré CDE | spec existante `feature_2_q_dynamique.md` | moyenne | ? |
| 9 | Genre profiles intégrés programmatiquement | non rédigée | basse | ? |

---

## Dépendances entre features

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
```

**Points clés :**

- Feature 1 est le **pivot** : toutes les features correctives suivantes en bénéficient
- Features 1.5, 6, 7 sont **indépendantes entre elles** — peuvent être développées en parallèle si envie
- Feature 8 attend que 6 et 7 existent pour avoir matière à consolider
- Feature 2 (Q dynamique) peut être fusionnée dans Feature 6 ou Feature 7 selon implémentation

---

## Ordre suggéré de livraison

### Séquence A — Validation terrain d'abord (recommandée)

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

### Séquence B — Dev avant session (risque élevé)

Tout développer avant de toucher Acid Drops. Déconseillé car risque d'accumuler 3-4 features non validées terrain.

### Séquence C — Parallélisation (si plusieurs sessions possible)

- Session mastering Acid Drops en cours (toi)
- Feature 6 en dev parallèle (Claude Code)
- Feature 1.5 rédaction spec (moi)
- Puis intégration progressive

Viable si tu as la bande passante pour gérer plusieurs chantiers en parallèle.

### Ma recommandation

**Séquence A, avec F1.5 terrain immédiate comme prochaine étape.**

Raison : les 3 semaines de dev récentes n'ont pas encore été validées par ton oreille sur ton vrai mix. Avant d'investir 20+ heures dans F6/F7/F8/1.5, il faut confirmer que F1 produit un résultat musicalement satisfaisant.

Si F1 terrain est concluante, on enchaîne avec confiance. Si F1 révèle des problèmes, on les corrige avant de construire par-dessus.

---

## État d'avancement du code source

**Repo :** Mix-Analyzer (privé)
**Branche principale :** `main`
**Tests totaux :** 429/429 passants (post-Feature 1)
**Dernier commit Feature 1 :** `be371f7`
**Git SHA des modules courants (Mix Analyzer v2.7.0) :**

| Module | MD5 |
|---|---|
| mix_analyzer.py | 7619b779 |
| section_detector.py | 5f71605a |
| tfp_parser.py | 09ca84af |
| tfp_coherence.py | d7044505 |
| cde_engine.py | b0e07898 |
| cde_apply.py | (dans la branche main) |
| automation_map.py | ead15094 |
| als_utils.py | c2de7487 |
| feature_storage.py | 7dd0be7e |
| spectral_evolution.py | 3ccc5c12 |
| user_config.py | e19e9b1e |
| eq8_automation.py | e8d64de7 |

---

## Documentation associée

### Documents vivants (à jour avec la roadmap)

- `docs/brief/mix_engineer_brief_v2_2.md` — méthodologie mastering, règle 3 EQ8 max, philosophie 100% dynamique
- `docs/brief/qrust_artistic_context_v1_1.md` — identité artistique Qrust, targets, philosophie de production
- `docs/brief/session_bootstrap_template.md` — template démarrage session
- `docs/brief/genre_music_profiles.json` — calibration par genre et track type
- `docs/brief/ableton_devices_mapping_v2_2.json` — mapping programmatique des devices

### Specs des Features

- `docs/features/feature_3_sections_locators.md` (livrée)
- `docs/features/feature_3_5_TFP.md` (livrée)
- `docs/features/feature_3_6_CDE.md` (livrée)
- `docs/features/feature_1_correction_conditionnelle.md` (livrée — version originale)
- `docs/features/feature_1_5_sidechain.md` (à rédiger)
- `docs/features/feature_2_q_dynamique.md` (spec existante, à enrichir)
- `docs/features/feature_4_eq8_stereo_ms.md` (spec existante)
- `docs/features/feature_5_autres_devices.md` (spec existante)
- `docs/features/feature_6_dynamic_hpf_lpf.md` (spec nouvelle, à valider)
- `docs/features/feature_7_dynamic_enhancement.md` (spec nouvelle, à valider)
- `docs/features/feature_8_eq8_consolidation.md` (spec nouvelle, à valider)
- `docs/roadmap_features_1_8.md` (ce document)

### Documents archivés

- `docs/archive/v1_8_ai_context_sheet_spec_ARCHIVED.md` (spec historique, remplacée par v2.7.0 live)

---

## Prochaines décisions structurantes

1. **Confirmer la séquence de livraison** — A, B, C ou autre ?
2. **Valider les specs F6, F7, F8** ou demander ajustements
3. **Planifier F1.5 session terrain** sur Acid Drops ou reporter
4. **Identifier le rédacteur de la spec Feature 1.5 sidechain** (probablement moi dans une prochaine conversation)

---

## Métriques de succès du projet global

Ce qui constituera une "réussite" du Mix Analyzer + Corrector Qrust :

**Niveau technique :**
- Feature set complet (F1 + F1.5 + F6 + F7 + F8 livrés et testés)
- Tests : >500 passants après F8
- Zero régression sur Acid Drops après passe complète

**Niveau artistique :**
- Acid Drops atteint Mix Health Score > 75 (actuellement 51.1)
- TFP Coherence Drop 1/Drop 2/Chorus moyens > 70
- Target loudness -10 LUFS atteint avec PLR 8-10 dB préservé
- Validation à l'oreille sur système club et casque

**Niveau commercial (objectif long terme) :**
- Outil utilisable par d'autres producteurs industrial
- Documentation complète pour onboarding
- Reproductibilité sur d'autres genres (au moins Techno, Bass Music, Experimental)

---

**Fin roadmap v1.0. Mise à jour attendue après chaque livraison de feature majeure ou décision structurante.**
