# Prompt Claude Code — Développement Feature 10 (High-Resolution Spectral Engine)

**Pour Alexandre :** copie le bloc entre `===PROMPT===` dans une nouvelle conversation Claude Code, en joignant les fichiers listés.

**Documents à joindre (dans cet ordre) :**

1. `documentation_discipline.md` (Section 7 critique pour Claude Code)
2. `qrust_professional_context.md` v1.0
3. `mix_engineer_brief_v2_3.md` (pour contexte philosophique)
4. `roadmap_features_1_8_v2_1.md` (si mise à jour produite) OU `roadmap_features_1_8_v2_0.md`
5. **`feature_10_high_resolution_spectral_engine.md` v1.0 (ou v1.2 si validée)** ← spec principale
6. `ableton_devices_mapping_v2_2.json` (référence technique)

**Optionnel mais crucial :**
- **Accès au repo Mix-Analyzer** (pour lecture des modules existants à refactorer)

---

## ===PROMPT===

```
Hello Claude Code. Développement de la Feature 10 : High-Resolution Spectral Engine.

OBJECTIF DE LA SESSION
======================
Refactor le moteur d'analyse spectrale du Mix Analyzer pour supporter 5 presets de résolution configurable (economy, standard, fine, ultra, maximum), un threshold de peak detection indépendant, et une architecture double rapport (FULL local sans limite + SHAREABLE < 25 MB pour upload Claude.ai).

Cette feature est en PRIORITÉ ABSOLUE avant toute autre feature, y compris le pilote F1 sur Bass Rythm qui était initialement prévu mais qui est reporté jusqu'à livraison F10.

DOCUMENTS JOINTS
================
1. documentation_discipline.md — règles permanentes, notamment Section 7 pour Claude Code
2. qrust_professional_context.md — invariant Qrust, philosophie 100% dynamique
3. mix_engineer_brief_v2_3.md — méthodologie mix/mastering (contexte philosophique)
4. roadmap_features_1_8_v*.md — vue d'ensemble roadmap
5. feature_10_high_resolution_spectral_engine.md v1.0 — SPEC PRINCIPALE À IMPLÉMENTER
6. ableton_devices_mapping_v2_2.json — référence technique

CONTEXTE CRITIQUE
=================
Le Mix Analyzer actuel (v2.7.0) produit des rapports avec résolution temporelle 166 ms (2.82 frames/beat à 128 BPM) et résolution spectrale non uniforme (excellente dans les graves, dégradée dans les highs). Alexandre a identifié cette limitation comme incompatible avec sa philosophie "100% dynamique / tout passe par EQ8 piloté par Mix Analyzer".

La cible est :
- Résolution temporelle > 4 frames/beat (preset ultra atteint 4.69)
- Résolution spectrale uniforme sur tout le spectre (2.69 Hz/bin avec N_FFT 16384)
- Architecture double rapport pour respecter la contrainte 30 MB d'upload Claude.ai sans sacrifier la résolution pour usage local

ÉTAT DU PROJET
==============
- Repo : Mix-Analyzer (privé). Branche main, dernier commit be371f7.
- Tests baseline : 429/429 passants (Feature 1 livrée, v2.7.0).
- Version cible après F10 : v2.8.0
- Fichier test : Acid_Drops_Sections_STD.als (pour validation terrain post-dev)

SCOPE STRICT — 7 SUB-FEATURES (F10a à F10g)
============================================

Suivre exactement le plan de livraison de la spec Section 8 :

**F10a** — Infrastructure presets et constants (45 min)
**F10b** — Refactor spectral engine (1h30)
**F10c** — Mise à jour sheets time-based (1h30)
**F10d** — Mise à jour sheets spectral (1h30)
**F10e** — Nouvelle sheet _analysis_config + Index update (45 min)
**F10f** — Double rapport FULL + SHAREABLE (2h)
**F10g** — CLI integration (1h)

Total : 10h-14h, 14 commits (7 code + 7 tests séparés), ~40-55 tests.

PROCÉDURE DÉTAILLÉE
===================

Étape 1 — Préparation
---------------------
1. Lire intégralement TOUS les documents joints, dans l'ordre listé. Spec F10 d'abord en profondeur.
2. Confirmer ta compréhension en résumant en 15 lignes max :
   - Les 5 presets et leurs caractéristiques
   - Le paramètre threshold et son usage
   - L'architecture double rapport
   - Les sheets impactées
   - Les 7 sub-features du plan de livraison
3. STOP ICI pour validation Alexandre.

Étape 2 — Audit du code existant
---------------------------------
1. Cloner/pull le repo Mix-Analyzer, vérifier tests baseline (429/429 green)
2. Créer branche `feature/F10_high_resolution_engine` depuis main
3. Identifier les modules à modifier (leurs noms exacts peuvent différer de la spec) :
   - Module générant _track_peak_trajectories
   - Module générant _track_spectra
   - Module orchestrateur principal
   - Module d'écriture Excel
   - Constants hardcodées actuelles (N_FFT, hop size)
4. Reporter dans la conversation :
   - Noms exacts des fichiers à modifier
   - Valeurs hardcodées actuelles identifiées
   - Structure générale du pipeline Mix Analyzer
5. STOP ICI pour validation Alexandre du plan de modification concret.

Étape 3 — Développement F10a (Infrastructure presets)
------------------------------------------------------
Créer `mix_analyzer/resolution_presets.py` avec :
- Dataclass `ResolutionPreset` (frozen)
- Dict `RESOLUTION_PRESETS` avec les 5 entries
- Helpers `get_effective_hop_ms`, `get_effective_delta_freq`, `get_preset_by_name`
- Constante `DEFAULT_RESOLUTION_PRESET = "standard"`

Correction importante vs spec : le preset "economy" dans la spec a hop=10240 > n_fft=8192 (invalide). Ajuster :
- economy : hop_samples=6144 (139 ms à 44.1 kHz), n_fft=8192, overlap 25%, 2.37 frames/beat
- Valider avec Alexandre avant de continuer si tu trouves une autre config préférable

Tests F10a (commit séparé) :
- Validation des 5 presets présents
- Validation des overlaps tous valides (0 < overlap < 1)
- Validation des hop <= n_fft
- Helpers produisent des valeurs correctes à 44.1 kHz et 48 kHz
- Preset inconnu lève `InvalidPresetError`

Commits :
- `feat(F10): resolution presets infrastructure`
- `test(F10): unit tests for resolution presets`

STOP entre commits pour validation.

Étape 4 — F10b (Spectral engine refactor)
------------------------------------------
Modifier le moteur FFT du Mix Analyzer pour accepter preset + threshold :
- Signature des fonctions de STFT prennent maintenant `preset: ResolutionPreset`
- Paramètre `peak_threshold_db` propagé depuis orchestrateur
- `compute_stft` utilise `preset.n_fft` et `preset.hop_samples`
- `detect_peaks` utilise `peak_threshold_db`

Tests F10b (commit séparé) :
- Test de non-régression : preset "standard" produit des résultats identiques à l'ancien comportement (à ±1%)
- Test preset "ultra" : nombre de frames correspond à duration/hop
- Test threshold : -40 dBFS produit moins de peaks que -70 dBFS
- Edge cases : très court signal, silence, sine pure

Commits :
- `feat(F10): spectral engine accepts preset and threshold`
- `test(F10): unit tests for spectral engine refactor`

STOP.

Étape 5 — F10c (Sheets time-based)
-----------------------------------
Modifier les modules générant :
- _track_peak_trajectories
- _track_valley_trajectories
- _track_multiband_time
- _track_dynamics_time

Pour qu'ils :
- Acceptent preset + threshold
- Produisent des sheets avec la bonne résolution temporelle
- Respectent la limite Excel 1M rows (ajouter garde-fou)

Tests F10c (commit séparé) :
- Sheets valides pour tous les presets
- Nombre de lignes correspond attendu
- Warning si >1M rows

Commits :
- `feat(F10): time-based sheets use preset resolution`
- `test(F10): unit tests for time-based sheets`

STOP.

Étape 6 — F10d (Sheets spectral)
---------------------------------
Modifier les modules générant :
- _track_spectra
- _track_spectral_descriptors
- _track_stereo_bands

Pour qu'ils adoptent résolution fréquentielle LINÉAIRE UNIFORME avec N_FFT du preset.

Note CRITIQUE : le passage de logarithmique à linéaire uniforme change le format de _track_spectra. Cela peut casser les consommateurs de cette sheet. 
- Auditer les modules qui lisent _track_spectra (CDE engine ?)
- Ajouter code de compatibilité si nécessaire
- Si casse inévitable, documenter dans la conversation et proposer migration path

Tests F10d (commit séparé) :
- Δf = sr / n_fft dans _track_spectra
- Descripteurs spectraux cohérents avec les nouveaux spectres
- Non-régression sur preset standard

Commits :
- `feat(F10): spectral sheets use preset frequency resolution`
- `test(F10): unit tests for spectral sheets`

STOP.

Étape 7 — F10e (Sheet _analysis_config + Index update)
-------------------------------------------------------
Créer la nouvelle sheet `_analysis_config` avec les 13 paramètres (Section 5.5 de la spec).
Enrichir la sheet `Index` avec les métadonnées de résolution.

Important : vérifier aussi que CDE engine n'a pas de hardcoded dependencies sur hop 166 ms (Section 10.2 de la spec, section Risques Section 11).

Tests F10e (commit séparé) :
- Sheet présente et complète
- Tous les champs documentés
- Valeurs cohérentes avec le preset utilisé

Commits :
- `feat(F10): analysis config sheet and Index update`
- `test(F10): unit tests for config metadata`

STOP.

Étape 8 — F10f (Double rapport FULL + SHAREABLE)
-------------------------------------------------
Modifier l'orchestrateur principal pour générer les deux rapports en parallèle.

Implémenter l'algorithme d'ajustement dynamique du threshold SHAREABLE (Section 4.3 de la spec) :
- Commencer à shareable_initial_threshold_db (défaut -60)
- Si taille > target_mb, retry à -55, puis -50, -45, -40
- Warning si target non atteignable même à -40
- Documenter le threshold final dans Index sheet du shareable

Tests F10f (commit séparé) :
- Rapport FULL respecte le threshold utilisateur
- Rapport SHAREABLE auto-ajuste threshold
- Test fixture projet long/dense : shareable > 25 MB force retry threshold
- Test fixture projet court/simple : shareable OK à -60 dBFS
- Exception `ShareableTargetUnreachableError` si impossible

Commits :
- `feat(F10): dual report generation with dynamic threshold adjustment`
- `test(F10): integration tests for dual report`

STOP.

Étape 9 — F10g (CLI integration)
---------------------------------
Modifier le CLI principal du Mix Analyzer pour exposer les nouveaux flags :
- --resolution (economy|standard|fine|ultra|maximum)
- --peak-threshold (-80 à -40)
- --generate-shareable / --no-shareable
- --shareable-target-mb
- --shareable-initial-threshold
- --output-dir
- --verbose

Output console formaté (Section 7.4 de la spec).

Tests F10g (commit séparé) :
- Parsing flags corrects
- Exit codes corrects (0 succès, 1 input invalide, etc.)
- Output console conforme au format
- Smoke tests : --resolution ultra, --peak-threshold -60, --no-shareable

Commits :
- `feat(F10-cli): new flags for resolution and shareable`
- `test(F10-cli): smoke tests for CLI`

STOP.

Étape 10 — Validation terrain sur Acid Drops
---------------------------------------------
Une fois les 14 commits passés et tests d'acceptation validés :

1. Lancer l'analyse sur Acid Drops en preset ultra :
   python -m mix_analyzer.analyze \
       --als "Acid_Drops_Sections_STD.als" \
       --resolution ultra \
       --peak-threshold -70 \
       --generate-shareable \
       --output-dir "reports/"

2. Vérifier :
   - Les deux rapports produits (full + shareable)
   - Tailles respectent les attentes (~33 MB full, <25 MB shareable)
   - Temps de génération acceptable (< 5 min)
   - Ouvrent correctement dans Excel/LibreOffice
   - Sheet _analysis_config présente et correcte
   - Les métriques Mix Health Score cohérentes avec rapport v2.7.0 (±5%)
   - Nouveau rapport a ~1900 frames (duration 190s / hop 100ms) sur _track_peak_trajectories

3. Partager le rapport SHAREABLE avec Alexandre pour validation finale

4. Si validation OK : merger branche dans main, bumper version à v2.8.0, mettre à jour :
   - roadmap_features_1_8.md (F10 → Livrée)
   - CHANGELOG.md du repo
   - README du repo

RÈGLES CRITIQUES
================

Format de réponse (cohérent avec qrust_professional_context.md Section 5) :
- Diagnostiquer → Options → Recommandation → Étapes cliquables
- Étapes précises et copiables

Stratégie anti-timeout (cohérent avec documentation_discipline.md Section 7) :
- Chaque commit ~30 min max
- Séparation stricte code commits et test commits
- STOP entre chaque micro-commit pour validation

Sécurité code (cohérent avec mix_engineer_brief_v2_3.md) :
- Tests existants NE DOIVENT JAMAIS casser (429 baseline)
- Coverage > 85% sur nouveaux modules
- Coverage > 80% sur modules modifiés
- Non-régression preset "standard" === ancien comportement

Pas de modification silencieuse :
- Si spec doit être ajustée pendant dev, SIGNALER dans la conversation
- Ne PAS modifier la spec silencieusement
- Si découverte technique invalide une décision de la spec, proposer alternative

Anti-patterns à éviter (cohérent avec session_bootstrap_template.md Section 10) :
- Ne PAS skip les tests pour gagner du temps
- Ne PAS merger dans main avant validation terrain
- Ne PAS commit sans test associé (sauf exception documentée)

DÉMARRAGE
=========
1. Lire tous les documents joints dans l'ordre.
2. Confirmer ta compréhension en résumant les points clés (Étape 1).
3. STOP pour validation Alexandre.
4. Procéder ensuite étape par étape, avec STOP entre chaque commit.

Ne PAS démarrer Étape 2 avant validation explicite Alexandre de ton résumé Étape 1.

Go.
```

## ===FIN PROMPT===

---

## Note pour Alexandre — préparation de la session

**Avant de copier le prompt, vérifie :**

- [ ] Tu as lu la spec F10 au moins une fois
- [ ] Les 5 presets te conviennent (ou tu as tranché ajustements)
- [ ] Threshold par défaut -70 dBFS te convient
- [ ] Tu acceptes que le pilote F1 soit reporté jusqu'à F10 livré
- [ ] Repo Mix-Analyzer est à jour (git pull sur main)
- [ ] Branche de travail peut être créée
- [ ] Tu as 2-3 sessions disponibles pour suivre le dev (~12h total étalé)

**Pendant la session :**

- Claude Code va STOP après chaque commit. C'est volontaire.
- À chaque stop, tu peux :
  - Valider et continuer
  - Demander ajustement
  - Pauser et reprendre plus tard

**Après la session F10 :**

Une fois F10 livrée et validée terrain sur Acid Drops (rapport haute résolution généré), on pourra enchaîner avec le pilote F1 sur Bass Rythm avec les bonnes données. À ce moment, le prompt F1 pilote (déjà rédigé : `CLAUDE_CODE_PROMPT_F1_pilote_bass_rythm.md`) sera exécuté sur les nouvelles données haute résolution.

**Séquence complète :**

1. **Maintenant → session Claude Code F10** (~10-14h étalé sur 2-3 sessions)
2. **Après F10 livrée → régénération rapport Acid Drops en preset ultra**
3. **Après nouveau rapport disponible → session Claude Code F1 pilote Bass Rythm** (avec le prompt déjà préparé)
4. **Après validation F1 sur Bass Rythm → décisions sur F1.5, F6, F7, F8**
