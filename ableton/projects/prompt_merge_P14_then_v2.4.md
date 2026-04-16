# 🎯 Prompt Claude Code — Merge P14 + Mix Analyzer v2.4 : AI Context exhaustif per-track

## Étape 0 — Merge de la PR P14 (préalable obligatoire)

Avant toute chose, merge la PR P14 ouverte (celle qui contient `Acid_drops_Code_P14.als` avec le hotfix Non-unique list ids) dans `main`.

```
git checkout main
git pull origin main
# Identifie la branche P14 (probablement claude/execute-p14-instructions-* ou claude/p14-*)
git branch -a | grep -i p14
# Merge la branche P14 dans main
git merge <branche-p14> --no-ff -m "Merge P14: master rebalance + EQ8 reorder + phase fixes"
git push origin main
```

Confirme dans le chat : « PR P14 mergée dans main, hash: [commit]. » avant de continuer.

---

## Étape 1 — Contexte v2.4

Mix Analyzer v2.3.1 (sur `main` après merge P14) génère 3 modes Excel : `full`, `globals`, `ai_optimized`. Le mode `ai_optimized` (~50 KB) ne contient que 6 sheets et exclut les sheets per-track parce qu'elles sont massivement visuelles (8 images matplotlib + 3 charts Excel par track) et lourdes.

**Problème :** dans le mode `ai_optimized`, l'AI perd l'accès à TOUTES les données per-track détaillées : waveforms, spectres, chromagrammes, multiband timelines, dynamic range timelines, M/S spectrums, panoramas spectraux, peaks de résonance, etc. Ces données existent en mémoire mais ne sont consommées que pour générer des images destinées à un humain qui regarde Excel — l'AI ne les voit pas.

**Objectif v2.4 :** intégrer **TOUTES les données analytiques per-track** sous forme dense, structurée et AI-friendly dans le sheet **AI Context**, organisé pour exploiter la largeur (pas la longueur) afin que le sheet reste navigable même avec 100+ tracks. Toutes ces données seront alors disponibles dans les 3 modes (puisque AI Context est commun aux 3).

À l'issue de cette feature, l'AI doit pouvoir répondre à des questions comme « quel track a la plus forte résonance entre 600 et 800 Hz à 30 secondes du début ? » ou « le pad évolue-t-il vers les aigus dans la 2ᵉ moitié du morceau ? » sans jamais avoir besoin de regarder une image.

## Investigation préalable obligatoire (à faire AVANT de coder)

1. Lis `mix_analyzer.py` autour de :
   - `analyze_track()` (qui agrège tout)
   - Les 8 fonctions `analyze_*` (loudness, spectrum, temporal, tempo_dynamic, musical, stereo, multiband_timeline, dynamic_range_timeline)
   - Les 8 fonctions `page_*` (identity, temporal, spectral, spectrogram, musical, stereo, multiband_timeline, characteristics) pour voir EXACTEMENT quelles données chaque visuel exploite
   - Les 3 fonctions `_write_*_chart_data` et `_create_*chart` pour voir les données alimentant les charts Excel natifs
   - `build_ai_context_sheet()` pour comprendre la structure existante du sheet

2. Recense de manière exhaustive **toute donnée numérique ou vectorielle** stockée dans l'objet `analysis` retourné par `analyze_track()`. Distingue clairement :
   - **Scalaires déjà présents dans la table consolidée AI Context** (38 colonnes actuelles) → ne pas dupliquer
   - **Scalaires absents** (ex : 6 peaks de résonance, n_onsets per period, etc.)
   - **Séries temporelles** (RMS envelope, multiband timeline, dynamic range timeline, tempogram_over_time, onset_times)
   - **Séries fréquentielles** (spectre FFT, M/S spectrums, panorama spectral, width_per_band, hires band energies)
   - **Données 2D** (chromagramme 12×N, tempogram bins×N)

3. Pour chaque catégorie de données, propose une **stratégie de représentation dense** dans Excel (downsampling, agrégation par buckets, top-N extraction, etc.). Voir la section « Spec détaillée » plus bas pour les contraintes.

4. **Réfléchis au scaling 1 → 100+ tracks** :
   - Combien de cellules Excel par track une fois le format stabilisé ?
   - Excel limit hard : 1 048 576 lignes × 16 384 colonnes par sheet, max ~32 KB par cellule
   - Mode `ai_optimized` doit rester < 500 KB total, mode `globals` < 5 MB
   - Avec 100 tracks, combien de bytes au total ? Estime et dis-le-moi.

5. **Résume dans le chat** ta compréhension complète :
   - Liste exhaustive de chaque donnée à intégrer (par track et globale)
   - Stratégie de représentation pour chacune (downsampling, structure)
   - Estimation de poids pour 1, 10, 50, 100 tracks
   - Architecture du sheet AI Context après v2.4 (ordre des sections, layout horizontal envisagé)
   - Points d'incertitude ou de friction qui méritent ma décision

   **Attends mon GO avant d'écrire la moindre ligne de code.**

## Spec détaillée — Données à intégrer

### Catégorie A — Données déjà présentes (à conserver telles quelles)
- Header (style, n_tracks, date)
- PROJECT CONTEXT (4 blocs)
- ANOMALY CODES LEGEND
- COLUMN LEGEND
- Track table consolidée (38 colonnes scalaires per-track)
- MIX HEALTH SCORE BREAKDOWN
- PER-FAMILY AGGREGATES

### Catégorie B — Scalaires per-track manquants (à ajouter)

À faire entrer dans la table consolidée existante OU dans une 2e table per-track adjacente, au choix selon ce qui est le plus lisible :

| Donnée | Source | Format proposé |
|---|---|---|
| 6 peaks de résonance (freq + magnitude_db) | `spectrum['peaks']` | colonnes `peak1_hz`, `peak1_db`, ..., `peak6_hz`, `peak6_db` (12 colonnes) |
| Nb d'onsets total | `temporal['num_onsets']` | déjà présent en colonne `num_onsets` |
| Densité d'onsets (onsets/sec) | calculé | nouvelle colonne `onsets_per_sec` |
| Tempo std + min + max | `tempo['tempo_std']`, `tempo_min`, `tempo_max` | 3 nouvelles colonnes (only Full Mix non-zero) |
| Tonal_strength + dominant_note (déjà présents) | — | OK |

### Catégorie C — Séries fréquentielles per-track (NOUVEAU, dense)

#### C1 — Spectre FFT downsampled per-track
Pour chaque track, le spectre moyen FFT (`spectrum['freqs']` + `spectrum_db_normalized`) doit être **downsamplé en 32 buckets log-fréquentiels** entre 20 Hz et 20 kHz. Format proposé : un sheet caché `_track_spectra` avec 1 row = 1 bucket fréquentiel et 1 col = 1 track. Header de row = label de bucket (ex: `20-29 Hz`, `30-44 Hz`, ..., `14k-20k Hz`). Header de col = nom de track. Valeur = magnitude dB normalisée (-80 à 0).

→ 32 rows × N tracks. Pour 100 tracks : 3 200 cellules + headers. ~50 KB.

Représentation utile pour l'AI : « voir d'un coup d'œil quel track a un creux à 800 Hz », « quel track porte le 16 kHz ».

#### C2 — Stereo width per hires band per-track
Pour chaque track stéréo, les 22 bandes hires (`FREQ_BANDS_HIRES`) avec leur stereo width respective. Sheet caché `_track_stereo_bands` : 22 rows (bandes) × N tracks (cols). Valeur = width 0-1.

→ 22 × N. Pour 100 tracks : 2 200 cellules.

### Catégorie D — Séries temporelles per-track (NOUVEAU, dense)

#### D1 — Multiband energy timeline downsampled
Pour chaque track, les 7 bandes (`FREQ_BANDS`) sur le temps. Données actuelles : ~200 frames par track. Downsampling cible : **64 buckets temporels**. Format : sheet caché `_track_multiband_time` structuré comme une stack — chaque track occupe **8 rows** (1 header avec nom track + 7 rows pour les 7 bandes), et **64 cols** pour les 64 buckets temporels. Les valeurs sont en dB.

→ 8 × N rows × 64 cols. Pour 100 tracks : 800 rows × 64 cols = 51 200 cellules. ~700 KB.

#### D2 — Peak / RMS / Crest timeline downsampled
Pour chaque track, les 3 séries du `dynamic_range_timeline`. Downsampling cible : **64 buckets temporels**. Sheet caché `_track_dynamics_time` : chaque track occupe 4 rows (header + 3 séries).

→ 4 × N rows × 64 cols. Pour 100 tracks : 400 rows × 64 cols = 25 600 cellules.

### Catégorie E — Données 2D per-track (NOUVEAU, sélection)

#### E1 — Chromagramme moyen per-track
Le chromagramme 12 × N existe pour chaque track. **Moyenne sur le temps** → 12 valeurs (une par classe de hauteur C/C#/D/.../B). Sheet caché `_track_chroma` : 12 rows (notes) × N tracks (cols). Valeur normalisée 0-1.

→ 12 × N. Pour 100 tracks : 1 200 cellules.

#### E2 — Tempogram (Full Mix uniquement)
Le tempogram n'est calculé que pour le Full Mix (`compute_tempo=True`). Représentation dense : **`tempo_over_time` sur 32 buckets temporels** + le tempo médian par bucket. Une simple ligne dans AI Context « SECTION TEMPO TIMELINE (Full Mix) » avec 32 valeurs.

→ 32 cellules total.

### Catégorie F — Onset times per-track (NOUVEAU, agrégé)

Au lieu de stocker tous les onsets (peut être >1000 par track), agréger en **un histogramme de 32 buckets temporels** comptant les onsets par bucket. Sheet caché `_track_onsets` : 1 row par track × 32 cols.

→ 1 × N rows × 32 cols. Pour 100 tracks : 100 × 32 = 3 200 cellules.

### Catégorie G — Caractéristiques descriptives per-track (NOUVEAU)
La liste `analysis['characteristics']` (5-8 lignes texte par track) et `analysis['anomalies']` (déjà encodées via `encode_anomalies` dans la colonne `anomaly_codes`).

Ajouter dans la table principale d'AI Context **une nouvelle colonne `description`** avec les caractéristiques descriptives jointes par ` ; ` (max ~300 chars), ou un sheet annexe `_track_descriptions` si trop verbeux.

## Architecture AI Context proposée (à valider dans ton résumé)

Garder la structure actuelle d'AI Context **inchangée** dans son ordre logique, mais **enrichir la section principale** :

```
[Header existant]
[Navigation existante]
[PROJECT CONTEXT 4 blocs — inchangé]
[ANOMALY CODES LEGEND — inchangé]
[COLUMN LEGEND — étendre avec les nouvelles colonnes]
[TRACK TABLE consolidée — étendre de 38 → ~50 colonnes (Catégorie B)]
[NEW SECTION: TRACK SPECTRA REFERENCE]
   « Voir sheet _track_spectra (32 buckets log-freq × N tracks) »
   + petit rappel des bornes de buckets (1 ligne)
[NEW SECTION: TRACK MULTIBAND TIMELINE REFERENCE]
   « Voir sheet _track_multiband_time »
[NEW SECTION: TRACK DYNAMICS TIMELINE REFERENCE]
   « Voir sheet _track_dynamics_time »
[NEW SECTION: TRACK CHROMA REFERENCE]
   « Voir sheet _track_chroma »
[NEW SECTION: TRACK STEREO BANDS REFERENCE]
   « Voir sheet _track_stereo_bands »
[NEW SECTION: TRACK ONSET HISTOGRAM REFERENCE]
   « Voir sheet _track_onsets »
[NEW SECTION: FULL MIX TEMPO TIMELINE]
   32 valeurs inline (pas besoin de sheet séparé pour 32 valeurs)
[MIX HEALTH SCORE BREAKDOWN — inchangé]
[PER-FAMILY AGGREGATES — inchangé]
```

**Pourquoi cette architecture :**
- AI Context reste lisible humainement (sections clairement nommées)
- Les blobs denses (spectra, timelines) sont dans des sheets cachés (`_*`) avec **layout horizontal** (1 row = 1 dimension fixe, 1 col = 1 track) → la longueur ne grandit JAMAIS avec le nombre de tracks, seule la largeur grandit
- L'AI sait où regarder grâce aux REFERENCE sections inline dans AI Context
- Excel garde 16 384 colonnes max → théoriquement on tient 16 000 tracks

**À discuter dans ton résumé :**
- Faut-il rendre les sheets cachés (`sheet_state = 'hidden'`) ou visibles avec un onglet d'avertissement ? Mon avis : cachés (l'AI les lit quand même, l'humain n'a aucune raison de les ouvrir).
- Faut-il aussi générer ces sheets pour les BUS et le Full Mix, ou Individual seulement ? Mon avis : tous, mais avec une convention de nommage de colonne explicite (`Acid_drops Kick 1.wav` vs `*** FULL MIX ***`).
- Si une track est mono, ses cellules dans `_track_stereo_bands` doivent contenir quoi ? Mon avis : `0.0` partout avec un commentaire dans la légende précisant que mono → width=0.

## Contraintes techniques strictes

1. **Pas de breaking change** sur les sheets existants. Le schéma `column_schema` actuel d'AI Context peut être étendu (nouvelles colonnes en fin), pas réordonné.
2. **Tous les nouveaux sheets cachés** doivent avoir un préfixe `_` et être en `sheet_state = 'hidden'` pour ne pas polluer la liste visible de l'utilisateur.
3. **Layout horizontal partout** : les sheets per-track ont les tracks en colonnes, pas en rows. Cela garantit que la longueur du sheet ne dépend que des dimensions fixes (32 buckets, 22 bandes, 12 notes…).
4. **Mode `ai_optimized` doit rester < 500 KB pour 50 tracks**. Mode `globals` < 5 MB. Si tes calculs montrent un dépassement, propose dans ton résumé une réduction de granularité (32 → 16 buckets, etc.) avant d'écrire le code.
5. **Performance de génération** : les sheets cachés se construisent en mémoire, donc l'overhead doit rester < 5 sec pour 50 tracks. Pas de double calcul — réutilise les arrays déjà calculés dans `analysis`.
6. **Backward compat** : si une donnée est manquante dans `analysis` (ex : track tellement courte que `multiband_timeline` est vide), écrire `None` dans les cellules concernées plutôt que de crasher.
7. **Modes** :
   - Sheets `_track_*` toujours générés dans les 3 modes (puisque AI Context est dans les 3 modes et y fait référence)
   - Cohérence : si on les génère pour `ai_optimized`, le poids doit rester acceptable (cf. contrainte 4)

## Workflow technique

1. Crée une branche `claude/ai-context-per-track-v2.4-XXX` depuis `main` (post-merge P14).
2. Lis le code, fais l'investigation des 5 points listés, **résume dans le chat ton plan complet et attends mon GO**.
3. Implémente dans cet ordre :
   - **Étape 1** — Étendre `column_schema` et `_extract_row_values` pour ajouter les ~12 nouvelles colonnes scalaires (Catégorie B). Tester sur Acid Drops que la table reste lisible et que les 39 tracks sont bien remplies.
   - **Étape 2** — Créer la fonction helper `_downsample_log_freq(freqs, values, n_buckets)` (downsampling logarithmique des spectres) et `_downsample_time(times, values, n_buckets)` (downsampling linéaire des séries temporelles). Tests unitaires inline.
   - **Étape 3** — Créer la fonction `_build_track_spectra_sheet(wb, analyses_with_info, log_fn)` (Catégorie C1). Implémentation + sheet caché + REFERENCE section inline dans AI Context.
   - **Étape 4** — Créer `_build_track_multiband_time_sheet` (D1) + REFERENCE.
   - **Étape 5** — Créer `_build_track_dynamics_time_sheet` (D2) + REFERENCE.
   - **Étape 6** — Créer `_build_track_chroma_sheet` (E1) + REFERENCE.
   - **Étape 7** — Créer `_build_track_stereo_bands_sheet` (C2) + REFERENCE.
   - **Étape 8** — Créer `_build_track_onsets_sheet` (F) + REFERENCE.
   - **Étape 9** — Ajouter la section inline `FULL MIX TEMPO TIMELINE` (E2) dans AI Context.
   - **Étape 10** — Ajouter colonne `description` (G) dans la table consolidée.
4. **Test programmatique** sur Acid Drops (39 tracks, dossier de bounces que tu identifieras dans le repo ou les fichiers locaux) :
   - Génère un rapport en mode `ai_optimized` → mesure poids final (target < 200 KB pour 39 tracks)
   - Génère un rapport en mode `globals` → mesure poids
   - Vérifie qu'aucun sheet caché n'est crashé (open/close + check max_row, max_col cohérents avec dimensions attendues)
   - Vérifie scaling : génère un test synthétique avec 100 tracks (juste duplique 100× le même WAV court de 5 sec si tu n'as pas 100 vrais bounces) → mesure poids et temps de génération
5. **Validation manuelle pour moi** : ouvre le rapport ai_optimized et vérifie que la section AI Context principale reste lisible (pas trop scrollée).
6. Commit : `v2.4: AI Context per-track exhaustive enrichment (N new hidden sheets + extended track table)`
7. Push, ouvre la PR, **NE PAS auto-merger** — j'inspecterai un rapport généré sur Acid Drops avant de valider le merge.

## Format de retour attendu

```
## v2.4 — AI Context Per-Track Enrichment Summary

### Merge P14
Merged branch [branche] into main, hash: [commit]

### Branche v2.4
claude/ai-context-per-track-v2.4-XXX

### Commit
[hash] v2.4: AI Context per-track exhaustive enrichment

### PR
#XX (status: open, awaiting Alex's review of generated report before merge)

### Fichiers modifiés
- mix_analyzer.py : N lines added/changed
  - Étendu column_schema : ~12 nouvelles colonnes scalaires (peaks, onsets_per_sec, tempo_std/min/max, description)
  - Ajouté N fonctions _build_track_*_sheet
  - Ajouté 2 helpers _downsample_log_freq, _downsample_time
  - Ajouté section FULL MIX TEMPO TIMELINE dans build_ai_context_sheet
  - Ajouté REFERENCE sections pour chaque sheet caché

### Sheets cachés ajoutés
1. _track_spectra        : 32 buckets log-freq × N tracks    (Catégorie C1)
2. _track_stereo_bands   : 22 bandes hires × N tracks        (Catégorie C2)
3. _track_multiband_time : 8 rows × N tracks × 64 cols       (Catégorie D1)
4. _track_dynamics_time  : 4 rows × N tracks × 64 cols       (Catégorie D2)
5. _track_chroma         : 12 notes × N tracks               (Catégorie E1)
6. _track_onsets         : N tracks × 32 buckets temporels   (Catégorie F)

### Mesures de poids et performance
| Mode | Tracks | Avant v2.4 | Après v2.4 | Time gen |
|---|---|---|---|---|
| ai_optimized | 39 (Acid Drops) | 50 KB | XXX KB | X.X s |
| globals      | 39 (Acid Drops) | 2.5 MB | X.X MB | X.X s |
| ai_optimized | 100 (synthetic) | -- | XXX KB | X.X s |
| globals      | 100 (synthetic) | -- | X.X MB | X.X s |

### Validation programmatique
- Tous les checks passés : ✓ / ✗ [détails si ✗]
- AI Context principal reste lisible : ✓ (X rows visibles, sections bien séparées)

### Hors scope (non touché)
- Pas de modification de analyze_track() ni des fonctions analyze_* (réutilisation pure des données déjà calculées)
- Pas de modification des sheets visuels existants
- Pas de modification du mode full (qui garde ses sheets per-track image-based en plus)
- Pas de modification du Mix Health Score, Per-Family Aggregates

### Décisions prises
- Sheets cachés vs visibles : [hidden, justification]
- Tracks couvertes : [Individual + BUS + Full Mix, justification]
- Mono dans _track_stereo_bands : [0.0 + commentaire dans légende]
```

## Garde-fous récap

- **Merge P14 d'abord** — ne pas commencer v2.4 sur une base sans le merge
- **Pas de breaking change** sur les sheets existants
- **Layout horizontal** pour tous les nouveaux sheets per-track (tracks en colonnes)
- **Sheets cachés** avec préfixe `_`
- **Sentinelles `None`** pour données manquantes, jamais de crash
- **Réutilisation des arrays** déjà dans `analysis`, pas de recalcul audio
- **Si poids dépasse les targets**, demande-moi avant de réduire la granularité
- **PR ouverte sans merge** pour que je valide sur Acid Drops d'abord
