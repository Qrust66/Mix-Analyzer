# Access Mix Analyzer — Spec v2.5

## Spectral Evolution Features & Dynamic EQ Automation Engine

---

## 0. Pour Claude Code — À lire avant de coder

### Workflow obligatoire

Ce spec est découpé en **8 phases atomiques**. Chaque phase suit cette procédure sans exception :

1. **Nouvelle branche** : `git checkout -b v2.5/phase-N-<nom-court>` depuis `main` (ou `develop` selon la convention du repo).
2. **Coder la phase entière** dans cette branche.
3. **Tests** : ajouter/faire passer les tests spécifiques à la phase avant toute chose.
4. **Validation manuelle** sur un `.als` réel (projet test, pas `Acid Drops`).
5. **Commits atomiques** en cours de route, format conventionnel :
   - `feat(spectral): add CQT matrix generator`
   - `test(spectral): validate matrix energy conservation`
   - `docs(spectral): document feature extraction contracts`
6. **PR** avec description claire pointant vers la section correspondante de ce spec.
7. **Ne jamais merger plus d'une phase à la fois.**

### Anti-timeout (erreurs 500)

Le projet a déjà subi des erreurs 500 sur des sessions d'édition longues. Stratégie :

- **Un fichier par responsabilité.** Si tu te retrouves à éditer plus de 3 fichiers dans une même réponse, split la session.
- **Pas de refactor horizontal** pendant une phase. Si tu vois un truc à nettoyer hors scope, note-le dans `TODO.md` et continue.
- **Checkpoint commits** toutes les 30–45 minutes de travail. Permet de reprendre si la session crash.
- **Lis d'abord, code après.** Avant chaque fichier modifié, lis-le en entier une fois. Évite les edits basés sur des suppositions stales.
- Si une édition foire (500, ou résultat inattendu), **pull le dernier commit**, relis, recommence. Jamais d'édit par-dessus du code dont t'es pas sûr.
- **Utilise `/compact` ou équivalent** si le contexte de session dépasse 50% — repartir avec un contexte propre au début de la phase suivante.

### Règles du repo

- **Style** : respecte le style existant (black, ruff, type hints si déjà présents). Ne le change pas en cours de route.
- **Docstrings** : chaque fonction publique a une docstring avec : description, params, return, exceptions. Format existant du repo.
- **Zéro régression sur v2.4** : les analyses et sheets existants doivent rester identiques. Les v2.4 sheets restent, v2.5 s'ajoute.
- **Dependencies** : ne pas introduire de nouvelle librairie sans justifier dans le PR. Stack attendu : `numpy`, `scipy`, `librosa` (déjà probablement présent), `openpyxl`/`pandas` selon le stack actuel.

### Ce que tu ne fais PAS

- Pas de ML / modèles entraînés. DSP classique déterministe seulement.
- Pas de real-time. Tout offline.
- Pas d'UI dans ce spec. Les features exposées via API Python, l'UI viendra dans un spec séparé.
- Pas de modification de l'audio lui-même. Seulement génération d'automations EQ8 dans le `.als`.

---

## 1. Contexte

### État actuel (v2.4)

Access Mix Analyzer produit par track :
- 6 peaks de résonance statiques (moyennés sur toute la durée)
- Multiband timeline : 7 bandes × 32 buckets temporels
- Spectre FFT : 32 buckets log-freq, moyenné toute la durée

### Limitation identifiée

Impossible de suivre l'évolution fréquentielle fine au fil du temps. Un peak qui migre de 620 Hz à 680 Hz entre T=30s et T=45s est invisible.

### Objectif v2.5

Ajouter un **moteur d'analyse spectrale évolutive** qui :

1. Génère une matrice spectrale 2D haute résolution **en RAM seulement** (transitoire).
2. Extrait une **banque de features temporels** couvrant tous les besoins d'automation (peaks, drops, rolloffs, transients, masking, sibilance, dynamique).
3. Stocke **uniquement les features** dans des sheets cachés compacts.
4. Expose une API Python qui consomme les features pour générer des **automations EQ8 dynamiques** écrites directement dans le `.als` via `als_utils.py`.

---

## 2. Architecture

### Principe directeur

```
[audio track]
      │
      ▼
[Matrice brute CQT 2D]  ←─── transitoire, RAM, jetée après extraction
      │
      ▼
[Banque de features]    ←─── stockée dans sheets cachés, compacte
      │
      ▼
[API d'automations]     ←─── consomme features, écrit dans .als
      │
      ▼
[EQ8 automations dans .als]
```

**Règle stricte :** les automations ne lisent jamais la matrice brute. Elles consomment uniquement des features. Ça force une abstraction propre et rend les features réutilisables pour tout type d'automation future.

### Modules attendus

| Module | Responsabilité |
|--------|----------------|
| `spectral_evolution.py` | Génération matrice brute + extraction features |
| `feature_storage.py` | Écriture/lecture features dans sheets cachés |
| `eq8_automation.py` | API de génération d'automations EQ8 par cas d'usage |
| `als_utils.py` (existant) | Écriture automations dans `.als` (étendu si nécessaire) |

---

## 3. Matrice brute (transitoire)

### Spécifications

- **Type** : Constant-Q Transform (CQT), pas FFT linéaire. Résolution fréquentielle fine dans les basses, plus grossière dans les hautes — aligné sur la perception musicale.
- **Résolution fréquentielle** : 256 bins log-spaced (20 Hz → 20 kHz), soit ~24 bins par octave.
- **Résolution temporelle** : ~6 frames/sec, soit ~1800 frames pour une track de 5 min. Adaptatif selon durée.
- **Valeur par cellule** : amplitude en dBFS.
- **Stéréo** : moyenne L+R pour v2.5. Support L/R séparé déféré à v2.6.
- **Storage** : jamais persisté. Vit en RAM le temps de l'extraction des features, puis jetée.

### Librairie recommandée

`librosa.cqt()` avec `n_bins=256`, `bins_per_octave=24`, `hop_length` calculé pour viser ~6 frames/sec à 44.1 kHz (donc ~7350 samples).

### Performance cible

- Génération matrice : < 3 sec par track de 5 min sur Ryzen 9 5900XT.
- Extraction features : < 2 sec.
- **Total par track : < 5 sec.**
- Pour `Acid Drops` (28 tracks) : < 2.5 min de rendu complet.

---

## 4. Banque de features

### Philosophie

Chaque feature est une projection 1D (ou liste d'événements) de la matrice 2D. Compact, réutilisable, lisible dans le sheet.

### Features à extraire

#### 4.1 Trajectoires freq × temps

**`peak_trajectories`** — Les N peaks spectraux les plus saillants suivis dans le temps.
- Par peak : `[(frame_idx, freq_hz, amplitude_db), ...]`
- N = 6 par défaut, paramétrable.
- Algo : détection de peaks par frame, association inter-frames via distance fréquentielle (< 1 demi-ton de migration autorisée entre frames adjacents).

**`valley_trajectories`** — Les creux (drops) spectraux suivis dans le temps.
- Même structure que peaks, mais sur les minima locaux.
- Usage clé : cas HPF qui doit pas couper dans la présence.

**`harmonic_ridges`** (optionnel, si détectable proprement)
- Fondamentale + harmoniques suivies dans le temps pour tracks harmoniques.

#### 4.2 Courbes d'enveloppe

**`low_rolloff_curve`** — Par frame, fréquence où l'énergie cumulée depuis 20 Hz dépasse un seuil (ex : -40 dB par rapport au max).

**`high_rolloff_curve`** — Idem en haut.

**`spectral_centroid_curve`** — Centre de gravité spectral par frame.

**`spectral_spread_curve`** — Largeur de la distribution spectrale.

**`spectral_flatness_curve`** — Tonal (0) vs bruité (1) par frame.

#### 4.3 Énergie par zone perceptuelle × temps

Courbes temporelles de l'énergie RMS dans chaque zone :

| Zone | Range |
|------|-------|
| Sub | 20–80 Hz |
| Low | 80–250 Hz |
| Mud | 200–500 Hz |
| Body | 250–800 Hz |
| Low-mid | 500–2000 Hz |
| Mid | 1–4 kHz |
| Presence | 2–5 kHz |
| Sibilance | 5–10 kHz |
| Air | 10–20 kHz |

(Zones se chevauchent volontairement — pour analyse, pas pour décomposition exclusive.)

#### 4.4 Dynamique

**`crest_by_zone`** — Crest factor (peak/RMS) par zone × temps. Permet de distinguer transient vs sustained.

**`delta_spectrum`** — Magnitude du changement frame-to-frame. Détection de transitions de section.

**`transient_events`** — Liste de timestamps avec transient détecté + bande dominante + magnitude.

#### 4.5 Cross-track (généré en phase 6)

**`masking_scores`** — Pour chaque paire de tracks, score d'overlap fréquentiel × temps par zone.

### Storage

Sheet caché par type de feature, un par track :

- `_track_peak_trajectories`
- `_track_valley_trajectories`
- `_track_rolloff_curves`
- `_track_spectral_descriptors` (centroid, spread, flatness)
- `_track_zone_energy`
- `_track_crest_by_zone`
- `_track_transients`
- `_track_masking` (phase 6)

Format tabulaire : ligne = timestamp ou événement, colonnes = features. Floats arrondis 0.1 dB pour compacité.

**Total storage estimé par track** : ~5 000 cellules. Pour 28 tracks : ~140k cellules. Lisible via Mix Analyzer sans slowdown notable.

---

## 5. Cas d'usage d'automations (consommateurs des features)

Chaque cas → une fonction dans `eq8_automation.py`. Chacune prend des features en input, écrit dans le `.als` via `als_utils.py`.

### A. Filtres adaptatifs (phase 3)

1. **`write_adaptive_hpf(als_path, track_id, low_rolloff_curve, valley_trajectories, safety_hz=10)`**
   - Le cutoff HPF suit `low_rolloff_curve`, mais recule de `safety_hz` pour préserver la présence low-mid.
   - Tient compte de `valley_trajectories` pour éviter de couper dans une zone qui a du contenu musical au-dessus d'un trou.

2. **`write_adaptive_lpf(als_path, track_id, high_rolloff_curve, safety_hz=500)`**
   - Symétrique en haut.

3. **`write_safety_hpf(als_path, track_id, zone_energy['sub'], threshold_db=-30)`**
   - Coupe à 30 Hz seulement quand l'énergie sub tombe sous le seuil (= c'est du rumble, pas du contenu).

### B. Notches et bells dynamiques (phase 4)

4. **`write_dynamic_notch(als_path, track_id, peak_trajectory, reduction_db=-4)`**
   - Notch EQ8 qui suit un peak trajectory. Fréquence + amplitude automatisées.

5. **`write_dynamic_bell_cut(als_path, track_id, zone_energy, zone, threshold_db, max_cut_db=-6)`**
   - Bell cut proportionnel à l'énergie d'une zone au-dessus d'un seuil.

6. **`write_resonance_suppression(als_path, track_id, peak_trajectories, sensitivity=0.5)`**
   - Soothe-style programmatique : détecte accumulations résonantes courtes, réduction ciblée temporaire.

### C. Boosts adaptatifs (phase 5)

7. **`write_adaptive_presence_boost(als_path, track_id, zone_energy['presence'], threshold_db=-18, max_boost_db=+3)`**
   - Boost 2–4 kHz uniquement quand la zone est faible.

8. **`write_adaptive_air_boost(als_path, track_id, high_rolloff_curve, threshold_hz=8000, max_boost_db=+2)`**
   - Shelf high uniquement quand rolloff trop bas.

### D. Cross-track (phase 6)

9. **`detect_masking(track_a_features, track_b_features, zones=['low', 'low-mid', 'mid']) -> MaskingReport`**

10. **`write_masking_reciprocal_cuts(als_path, track_a, track_b, masking_report, reduction_db=-3)`**
    - Notches réciproques dans les zones et moments où les deux tracks se masquent.

11. **`write_targeted_sidechain_eq(als_path, ducking_track, trigger_track, zone, reduction_db=-6)`**
    - Sidechain EQ ciblée par zone.

### E. Événements temporels (phase 7)

12. **`write_transient_aware_cut(als_path, track_id, existing_cut_params, transient_events, release_ms=50)`**
    - Module un cut existant pour s'atténuer sur les transients.

13. **`write_section_aware_eq(als_path, track_id, delta_spectrum, threshold=0.3)`**
    - Détecte transitions, génère automations en escalier.

### F. De-essing (phase 7)

14. **`write_dynamic_deesser(als_path, track_id, zone_energy['sibilance'], threshold_db=-18, reduction_db=-4)`**

### G. Reference matching (phase 8, optionnel)

15. **`write_spectral_match(als_path, track_id, target_features, time_window=(start, end))`**
    - Matcher une section spécifique d'une track à un target.

---

## 6. Exigences techniques

### API Python — contrats

Chaque fonction d'automation suit la signature pattern :

```python
def write_<automation_name>(
    als_path: Path,
    track_id: str,
    feature: Feature,        # feature extrait, pas matrice brute
    **params
) -> AutomationReport:
    """
    Génère l'automation <nom> dans le .als pour la track donnée.
    
    Args:
        als_path: Chemin vers le .als cible.
        track_id: Identifiant de la track (nom ou UID).
        feature: Feature extrait nécessaire (type varie selon automation).
        **params: Paramètres spécifiques à l'automation.
    
    Returns:
        AutomationReport avec : success, breakpoints_written, eq8_band_index, warnings.
    
    Raises:
        TrackNotFoundError: Si track_id n'existe pas dans le .als.
        EQ8SlotFullError: Si pas de bande EQ8 disponible.
    """
```

### Contraintes `.als`

- EQ8 a 8 bandes. Avant d'ajouter une automation, vérifier qu'une bande est disponible OU que l'utilisateur a spécifié quelle bande écraser.
- Breakpoints max par paramètre : viser < 500 par track pour éviter bloat `.als`.
- Densité max : ~10 breakpoints/sec par paramètre (au-delà = zipper noise sur l'EQ).
- Les automations générées doivent avoir un **nom explicite** (ex : `v2.5_adaptive_hpf`) pour que l'utilisateur les identifie dans Ableton.
- **Backup systématique** : toute écriture `.als` doit d'abord créer `<nom>.als.v24.bak` avant modification.

### Tests

Chaque phase livre :
- **Unit tests** : feature extraction déterministe, contrats respectés.
- **Integration test** : sur un `.als` fixture, génère automation, re-parse le `.als`, vérifie que l'automation est écrite correctement.
- **Smoke test** : ouvre le `.als` modifié dans Ableton Live 12 (manuel, à faire par Alexandre ou documentation CI).

---

## 7. Plan de développement en 8 phases

**Règle : une phase = une branche = une PR = un merge.**

### Phase 1 — Matrice brute + feature core
**Branche :** `v2.5/phase-1-spectral-core`

Livrables :
- `spectral_evolution.py::generate_matrix()` avec CQT.
- `spectral_evolution.py::extract_zone_energy()`, `extract_spectral_descriptors()`.
- `feature_storage.py` : écriture des sheets `_track_zone_energy`, `_track_spectral_descriptors`.
- Tests : conservation d'énergie par rapport aux sheets v2.4 existants (sanity check).

**Critère de merge :** pour chaque track du projet test, les sheets v2.5 sont peuplés, les sheets v2.4 inchangés.

### Phase 2 — Trajectoires et transients
**Branche :** `v2.5/phase-2-trajectories`

Livrables :
- `extract_peak_trajectories()`, `extract_valley_trajectories()`.
- `extract_transients()`, `extract_crest_by_zone()`, `extract_rolloff_curves()`.
- Storage correspondant.

**Critère de merge :** toutes les trajectoires sont extraites pour le projet test, visualisables en CSV.

### Phase 3 — Filtres adaptatifs
**Branche :** `v2.5/phase-3-adaptive-filters`

Livrables : automations 1, 2, 3. Tests unitaires + intégration sur `.als`.

**Critère de merge :** ouverture du `.als` modifié dans Ableton, vérification visuelle des automations HPF/LPF.

### Phase 4 — Notches et bells dynamiques
**Branche :** `v2.5/phase-4-dynamic-eq`

Livrables : automations 4, 5, 6.

### Phase 5 — Boosts adaptatifs
**Branche :** `v2.5/phase-5-adaptive-boosts`

Livrables : automations 7, 8.

### Phase 6 — Cross-track masking
**Branche :** `v2.5/phase-6-cross-track`

Livrables : feature `masking_scores`, automations 9, 10, 11.

**Dépendance :** requiert toutes les features des phases 1–2 pour les tracks paire.

### Phase 7 — Événements et vocal
**Branche :** `v2.5/phase-7-events-vocal`

Livrables : automations 12, 13, 14.

### Phase 8 — Reference matching (optionnel)
**Branche :** `v2.5/phase-8-reference-match`

Livrables : automation 15.

---

## 8. Critères de qualité globaux

- **Zéro régression v2.4** : ancien rapport Excel identique, même chiffres, mêmes sheets non-cachés.
- **Performance** : rendu complet < 3 min pour `Acid Drops` (28 tracks) sur la machine d'Alexandre.
- **Documentation** : chaque module a un `README.md` ou section docstring top-level décrivant son rôle et ses dépendances.
- **Automations reversibles** : l'utilisateur peut supprimer les automations v2.5 dans Ableton sans casser le projet (elles sont nommées distinctement et ne touchent pas aux paramètres EQ8 statiques existants).
- **Idempotence** : relancer le pipeline v2.5 sur un `.als` déjà modifié doit mettre à jour les automations, pas en empiler.

---

## 9. Questions à résoudre avant phase 1

Réponds à ces questions dans le PR de phase 1 ou en commentaire avant de commencer :

1. **Matrice CQT** : `librosa.cqt` ou implémentation custom ? (reco : librosa, plus testé)
2. **Résolution temporelle** : fixe à ~6 frames/sec, ou adaptatif selon durée ?
3. **Gestion des tracks courtes** (<30s) : skip, ou analyse avec résolution réduite ?
4. **Tracks bypassed/muted dans le `.als`** : analyser ou skip ?
5. **Convention de nommage des automations** : `v2.5_<type>_<band>` ou autre ?

---

## 10. Hors scope (reporté à v2.6+)

- Support L/R séparé (analyse stéréo fine)
- Machine learning / modèles entraînés
- Real-time / streaming
- UI de contrôle des automations (sélection interactive des cas à appliquer)
- Modification de l'audio lui-même
- Support Max for Live devices
- Analyse cross-projet (comparaison entre `.als` différents)
