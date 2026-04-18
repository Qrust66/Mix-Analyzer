# Méthodologie EQ8 — Spec complète

## Approche exhaustive pour la correction spectrale automatisée

---

## 1. Philosophie

Un EQ8 n'est pas un outil à problèmes — c'est un sculpteur de spectre. Chaque bande a un rôle précis, chaque paramètre est calculé depuis les données, et chaque correction est justifiée par une mesure.

**Principes :**
- Corriger seulement ce qui est mesuré comme problématique
- Dynamique quand le problème varie dans le temps, statique quand il est constant
- Soustraire avant d'additionner (couper les problèmes avant de booster les qualités)
- Respecter le budget de bandes (max 8 par instance, max 2 instances par track)
- La correction est indépendante du projet — la méthode s'applique à tout .als

---

## 2. Types de corrections et quand les appliquer

### 2.1 — Nettoyage du plancher (HPF / LPF)

**Objectif :** Retirer ce qui ne sert pas — rumble sub, bruit haute fréquence.

**Mode :** LC48 (mode 0) pour HPF, HC48 (mode 7) pour LPF

**Quand :**
- HPF : énergie sub (20-80 Hz) < -50 dB de manière permanente → la track n'a pas de contenu sub utile. Couper le bruit.
- LPF : énergie air (10-20 kHz) < -50 dB de manière permanente → la track n'a pas de contenu high utile.

**Type :** Statique (la fréquence de coupure ne bouge pas).

**Calcul :**
- HPF Freq = fréquence en-dessous de laquelle l'énergie est < -50 dB en permanence. Safety floor : 20 Hz pour les basses, 30 Hz pour le reste.
- LPF Freq = fréquence au-dessus de laquelle l'énergie est < -50 dB en permanence.
- Q = 0.71 (Butterworth, pas de résonance au point de coupure).
- Gain = inopérant sur LC48/HC48 (pas d'automation Gain).

**Données :** `_track_zone_energy` zones Sub et Air.

**Bande :** HPF sur Band 0, LPF sur Band 7 (convention — les filtres aux extrémités).

---

### 2.2 — HPF / LPF adaptatif (dynamique)

**Objectif :** Couper le bas/haut seulement quand ça cause un conflit, laisser vivre quand c'est safe.

**Mode :** LC48 (mode 0) pour HPF, HC48 (mode 7) pour LPF

**Quand :**
- Le contenu sub/high existe par moments mais masque une autre track dans certaines sections.
- Exemple : guitare distortée a du contenu à 80 Hz. Dans l'intro (pas de kick), c'est OK. Dans le drop (kick actif), ça masque → HPF actif dans le drop seulement.

**Type :** Dynamique — la Freq ou le IsOn varie dans le temps.

**Deux approches :**
1. **IsOn toggle (BoolEvent)** : le filtre s'active/désactive par section. Plus simple, moins d'artefacts.
2. **Freq sweep (FloatEvent)** : la fréquence de coupure monte quand le conflit augmente, descend quand il diminue. Plus précis mais potentiellement audible.

**Calcul :**
- Si approche IsOn : activer quand masking_score > seuil dans la zone sub/high.
- Si approche Freq : Freq = fréquence du rolloff naturel de la track (depuis `spectral_descriptors.low_rolloff`), plafonnée par le genre/track_type.

**Données :** `_track_zone_energy` + `_track_automation_map` (masking entre tracks) + sections.

**Bande :** HPF sur Band 0, LPF sur Band 7.

---

### 2.3 — Notch dynamique (peak following)

**Objectif :** Suivre un peak de résonance frame-par-frame et le réduire proportionnellement.

**Mode :** Bell (mode 3) — PAS Notch (mode 4) car le Gain est inopérant en mode Notch.

**Quand :**
- Un peak de résonance est détecté dans `_track_peak_trajectories`.
- Le peak est justifié comme problématique (masking, extrême isolé, ou accumulation — voir Feature 1).

**Type :** Dynamique — Freq, Gain, et Q varient frame-par-frame.

**Calcul :**
- **Freq** = fréquence exacte du peak à chaque frame. Suit le drift naturel.
- **Gain** = proportionnel à l'amplitude du peak :
  ```
  Si amp > 0 dB  : gain = -amp × 0.5 (couper la moitié du dépassement)
  Si amp -10..0   : gain = amp × 0.3 (réduction légère)
  Si amp < -10    : gain = 0 (peak faible, pas de correction)
  Clamp à max_reduction (depuis genre_profiles)
  ```
- **Q** = adaptatif à l'amplitude :
  ```
  amp > 5 dB  : Q = 14 (chirurgical — peak très fort)
  amp 0..5    : Q = 10
  amp -5..0   : Q = 6
  amp -10..-5 : Q = 3
  amp < -10   : Q = 1 (large — presque inactif)
  ```
- **Avant/après le peak** : Gain = 0, Q = 1 (bande inactive quand le peak n'existe pas).

**Données :** `_track_peak_trajectories` (freq, amp, time par frame).

**Bande :** N'importe quelle bande libre (pas 0 ni 7, réservées aux filtres).

---

### 2.4 — Correction de masking inter-tracks

**Objectif :** Quand deux tracks se marchent dessus dans la même bande fréquentielle, réduire le conflit.

**Mode :** Bell (mode 3)

**Quand :**
- `detect_masking()` retourne un score > seuil du genre entre deux tracks dans une zone.
- La track courante est de priorité inférieure à l'autre (depuis la matrice de priorités par section).

**Trois stratégies :**

**A) Cut unilatéral** — la track de basse priorité est coupée dans la zone de conflit.
```
Freq = centre de la zone de masking
Gain = -masking_score × max_reduction × intensity
Q = largeur de la zone / freq_centre (Q qui couvre la zone)
```

**B) Cuts réciproques** — les deux tracks se font une place mutuellement.
```
Track A : cut à freq_centre - offset (côté bas de la zone)
Track B : cut à freq_centre + offset (côté haut de la zone)
Gain = -masking_score × max_reduction × 0.5 (partagé)
```

**C) Sidechain EQ** — une track duck quand l'autre joue.
```
La track B a un Gain qui descend quand la track A a de l'énergie dans la zone.
Plus complexe — nécessite les données temporelles des deux tracks.
```

**Type :** Dynamique (le masking varie dans le temps) ou statique (si le conflit est constant).

**Données :** `_track_zone_energy` des deux tracks, masking scores, sections, priorités.

**Bande :** N'importe quelle bande libre.

---

### 2.5 — Nettoyage de mud

**Objectif :** Réduire l'accumulation d'énergie dans la zone 200-500 Hz (mud) qui rend le mix boueux.

**Mode :** Bell (mode 3) cut large, ou Low Shelf (mode 2) cut doux.

**Quand :**
- L'énergie dans la zone Mud est > seuil du genre pour ce track type.
- Plusieurs tracks (4+) ont de l'énergie significative dans cette zone simultanément.
- La track courante est de basse priorité dans cette zone.

**Type :** Statique ou section-aware (plus de mud toléré dans l'intro, moins dans le drop).

**Calcul :**
```
Freq = centre de la zone Mud (350 Hz typiquement)
Gain = -(accumulation_score × 2) dB, clampé à -4 dB max
Q = 1.0 à 2.0 (large — on nettoie une zone, pas un point)
```

**Données :** `_track_zone_energy` zone Mud, accumulation count.

**Bande :** N'importe quelle bande libre.

---

### 2.6 — De-essing

**Objectif :** Réduire les sibilances (sons "sss", "ttt") sur les vocaux et certains synths.

**Mode :** Bell (mode 3)

**Quand :**
- L'énergie dans la zone Sibilance (5-10 kHz) dépasse le seuil du genre pour les vocaux/synths.
- Détectable via `_track_zone_energy` zone Sibilance ou via `_track_peak_trajectories` dans cette zone.

**Type :** Dynamique — le de-esser agit seulement quand la sibilance est présente.

**Calcul :**
```
Freq = centre de la sibilance (6-8 kHz typiquement, depuis les peaks dans cette zone)
Gain = proportionnel à l'amplitude de la sibilance, max -6 dB
Q = 4 à 8 (assez serré pour ne pas couper l'air général)
```

**Données :** `_track_zone_energy` zone Sibilance, `_track_peak_trajectories` dans la zone 5-10 kHz.

**Bande :** N'importe quelle bande libre.

---

### 2.7 — Boost de présence adaptatif

**Objectif :** Ajouter de la clarté quand la track perd sa présence dans les sections denses.

**Mode :** Bell (mode 3) ou High Shelf (mode 5)

**Quand :**
- L'énergie dans la zone Presence (2-5 kHz) tombe sous le seuil du genre dans certaines sections.
- Le full mix manque de présence dans cette zone (pas juste la track individuelle).
- Boost seulement si justifié — ne pas booster si d'autres tracks fournissent déjà la présence.

**Type :** Dynamique — boost quand la présence manque, plat quand elle est suffisante.

**Calcul :**
```
Freq = 3 kHz (centre de la présence) ou depuis le centroid spectral de la track
Gain = +1 à +3 dB max (boosts toujours conservateurs)
Q = 0.8 à 1.5 (large — boost doux)
```

**Données :** `_track_zone_energy` zone Presence, `_track_spectral_descriptors` centroid.

**Bande :** N'importe quelle bande libre.

---

### 2.8 — Boost d'air adaptatif

**Objectif :** Ajouter de la brillance et de l'ouverture dans les hautes fréquences.

**Mode :** High Shelf (mode 5)

**Quand :**
- Le rolloff high de la track tombe trop bas (< seuil du genre).
- Le full mix manque d'air.

**Type :** Dynamique ou statique selon la variabilité du rolloff.

**Calcul :**
```
Freq = 10 kHz (shelf à partir de 10 kHz)
Gain = +1 à +2 dB max
Q = 0.71 (shelf doux)
```

**Bande :** Band 7 si pas de LPF, sinon une bande libre proche de 7.

---

### 2.9 — Correction stéréo M/S

**Objectif :** Corriger les problèmes spatiaux — phase négative, centre trop wide, manque de largeur.

**Mode :** EQ8 en mode M/S (Mode_global=2). ParameterA = Mid, ParameterB = Side.

**Quand :**
- Phase correlation < -0.3 dans une zone → cut Side dans cette zone.
- Largeur stéréo > 0.8 dans le low-mid → cut Side (le low-mid doit être centré).
- Track trop étroite avec width < 0.1 → boost Side dans Presence/Air.

**Instance séparée :** Toujours une DEUXIÈME instance d'EQ8, distincte de l'EQ8 correctif principal.

**Données :** `_track_stereo_bands` (phase, width par zone).

---

## 3. Allocation des bandes

### Convention de placement

```
Band 0 : HPF (LC48) — réservée au nettoyage sub
Band 1 : Correction basse fréquence (notch/cut 80-250 Hz)
Band 2 : Correction low-mid (notch/cut/mud 200-800 Hz)
Band 3 : Correction mid (notch/cut/masking 500-2000 Hz)
Band 4 : Correction upper-mid (notch/cut/deess 2-6 kHz)
Band 5 : Correction presence (boost/cut 2-5 kHz)
Band 6 : Correction air/sibilance (boost/cut 5-12 kHz)
Band 7 : LPF (HC48) — réservée au nettoyage high
```

**Cette convention est un DEFAULT.** Si une track n'a pas besoin de HPF, Band 0 peut être utilisée pour autre chose. Si elle a besoin de 4 notchs dans le low-mid, les bandes 1-4 sont toutes en Bell cut.

### Priorité d'allocation

Quand il y a plus de corrections nécessaires que de bandes disponibles :

```
Priorité 1 : HPF/LPF (nettoyage — toujours appliqué)
Priorité 2 : Masking inter-tracks (les plus sévères d'abord)
Priorité 3 : Peaks de résonance (les plus forts d'abord)
Priorité 4 : Mud (accumulation dans les zones critiques)
Priorité 5 : De-essing
Priorité 6 : Presence boost
Priorité 7 : Air boost
```

Les corrections soustractives passent avant les additives.

### Multi-instance

Si 8 bandes ne suffisent pas (rare mais possible sur des tracks très problématiques), créer une DEUXIÈME instance d'EQ8. Maximum 2 instances correctives + 1 instance M/S = 3 EQ8 max par track.

**Placement dans la chaîne :**
- EQ8 #1 (correctif) : AVANT le compresseur → corrections pre-compression
- EQ8 #2 (correctif) : APRÈS le compresseur → corrections post-compression (polish)
- EQ8 #3 (M/S) : APRÈS tout → corrections stéréo en dernier

---

## 4. Pipeline de décision par track

Pour chaque track du projet, dans cet ordre :

```
ÉTAPE 1 — Classification
  Quel type de track ? (Kick, Bass, Pad, Lead, etc.)
  Quel rôle ? (source, bus, full_mix)
  → Si bus ou full_mix : skip les corrections individuelles

ÉTAPE 2 — Inventaire spectral
  Lire zone_energy, spectral_descriptors, peak_trajectories
  Identifier :
  - Zones avec contenu significatif (> -40 dB)
  - Zones sans contenu (< -50 dB) → candidats HPF/LPF
  - Peaks de résonance (depuis peak_trajectories)
  - Rolloff bas et haut (depuis spectral_descriptors)

ÉTAPE 3 — Contexte inter-tracks
  Pour chaque zone significative :
  - Quelles autres tracks ont de l'énergie dans cette zone ?
  - Quel est le masking score ?
  - Quelle est la priorité de cette track vs les autres ?
  - Y a-t-il accumulation (4+ tracks) ?

ÉTAPE 4 — Liste des corrections candidates
  Appliquer les règles de la section 2 :
  - HPF/LPF si zones vides
  - Notchs si peaks justifiés
  - Masking cuts si conflits
  - Mud cut si accumulation
  - De-essing si sibilance
  - Boosts si déficit

ÉTAPE 5 — Justification (Feature 1)
  Pour chaque correction candidate :
  - Est-elle justifiée ? (masking, peak extrême, accumulation, bruit)
  - Si non → retirer de la liste
  - Si oui → calculer la severity et le dynamic_mask

ÉTAPE 6 — Budget de bandes
  Trier les corrections justifiées par priorité (section 3)
  Allouer les bandes :
  - Band 0 pour HPF, Band 7 pour LPF
  - Bandes 1-6 pour les corrections spectrales, par ordre de priorité
  - Si > 6 corrections : deuxième instance ou refus des moins critiques

ÉTAPE 7 — Calcul des paramètres
  Pour chaque bande allouée :
  - Mode (Bell pour les cuts/boosts, LC48/HC48 pour filtres, HShelf pour air)
  - Freq, Gain, Q (statiques ou dynamiques selon le type)
  - Breakpoints si dynamique

ÉTAPE 8 — Écriture
  Configurer les Manual values
  Écrire les automation envelopes (FloatEvent pour Freq/Gain/Q, BoolEvent pour IsOn)
  Injecter dans le bon container <Envelopes> de la bonne track (par EffectiveName)
```

---

## 5. Données requises par type de correction

| Correction | zone_energy | peak_traj | spectral_desc | stereo_bands | automation_map | masking | sections |
|---|---|---|---|---|---|---|---|
| HPF statique | Sub | — | low_rolloff | — | — | — | — |
| HPF adaptatif | Sub | — | low_rolloff | — | is_audible | score | oui |
| LPF statique | Air | — | high_rolloff | — | — | — | — |
| Notch dynamique | — | oui | — | — | is_audible | score | — |
| Masking cut | zone du conflit | — | — | — | — | score | oui |
| Mud cut | Mud | — | — | — | — | accum | oui |
| De-essing | Sibilance | zone 5-10k | — | — | — | — | — |
| Presence boost | Presence | — | centroid | — | — | — | oui |
| Air boost | Air | — | high_rolloff | — | — | — | — |
| M/S corrections | — | — | — | phase, width | — | — | — |

Toutes les données sont dans le rapport Excel existant. Aucune nouvelle analyse nécessaire.

---

## 6. Placement dans la chaîne d'effets

### Ordre standard d'une chaîne de mix

```
1. Gain staging (Utility gain)
2. HPF/LPF (nettoyage)           ← EQ8 #1 correctif
3. Corrections soustractives      ← EQ8 #1 (notchs, masking cuts, mud)
4. Compression                    ← Compressor / GlueCompressor
5. Corrections additives          ← EQ8 #2 polish (presence, air boosts)
6. Saturation                     ← Saturator (optionnel)
7. Corrections stéréo             ← EQ8 #3 M/S (optionnel)
8. Limiter                        ← protection (optionnel)
```

**EQ8 #1 (correctif)** AVANT le compresseur :
- Les corrections soustractives réduisent l'énergie → le compresseur travaille sur un signal plus propre
- Le HPF empêche les basses fréquences de triggerer la compression inutilement
- Les notchs réduisent les peaks qui causeraient une sur-compression

**EQ8 #2 (polish)** APRÈS le compresseur :
- La compression peut créer de la dullness (perte de présence) → le boost compense
- L'air boost après compression est plus naturel qu'avant
- Optionnel — seulement si des boosts sont nécessaires

**EQ8 #3 (M/S)** en dernier :
- Les corrections stéréo doivent opérer sur le signal final
- Optionnel — seulement si des problèmes stéréo sont détectés

### Détermination du placement dans le .als

Pour insérer un EQ8 au bon endroit dans la chaîne :

```python
def find_insertion_point(track, position="pre_compressor"):
    """Trouve où insérer l'EQ8 dans la chaîne d'effets.
    
    position: "pre_compressor", "post_compressor", "last"
    
    Parcourir les devices de la track :
    - Si position="pre_compressor" : insérer AVANT le premier Compressor/GlueCompressor
    - Si position="post_compressor" : insérer APRÈS le dernier Compressor/GlueCompressor
    - Si position="last" : insérer à la fin de la chaîne
    
    Si aucun compresseur : insérer à la fin (après les effets existants).
    """
```

---

## 7. Contraintes techniques Ableton

### Valeurs confirmées par calibration (v1.9)

| Paramètre | Encodage | Range | Event type |
|---|---|---|---|
| Freq | Hz direct | 10 – 22000 | FloatEvent |
| Gain | dB direct | -15 – +15 | FloatEvent |
| Q | Q direct | 0.1 – 18.0 | FloatEvent |
| IsOn | true/false | — | BoolEvent |
| Mode | enum 0-7 | — | — (pas d'automation dynamique de mode recommandée) |
| GlobalGain | dB direct | -12 – +12 | FloatEvent |
| Scale | ratio direct | 0 – 2 (0-200%) | FloatEvent |

### Structure XML

- Bandes : `Eq8/Bands.N/ParameterA` (direct, PAS dans un container `<Bands>`)
- ParameterB : pour R (L/R) ou Side (M/S)
- Lookup track : par `<EffectiveName Value="...">`, JAMAIS par texte libre
- Envelopes : injecter dans `<AutomationEnvelopes><Envelopes>` de la bonne track
- Gzip : `gzip.compress()` standard, modifier le XML en texte brut

### Gain inopérant

Le Gain est ignoré par Ableton sur les modes : LC48 (0), LC12 (1), Notch (4), HC12 (6), HC48 (7).
→ Utiliser Bell (3) pour tout cut/boost avec Gain automatable.
→ Les filtres (HPF/LPF) n'ont pas de Gain — seulement Freq et IsOn comme automations utiles.

---

## 8. Ce que l'API expose

### Fonction principale

```python
def apply_eq8_corrections(
    als_path: Path,
    report_path: Path,
    genre: str,
    character: float = 0.5,
    tracks: list[str] = None,      # None = toutes les tracks source
    max_bands_per_track: int = 6,
    max_instances: int = 2,
    output_path: Path = None,
) -> CorrectionReport:
    """Applique les corrections EQ8 complètes sur un .als.
    
    Pipeline :
    1. Charger le rapport + le .als
    2. Pour chaque track source avec EQ8 :
       a. Inventaire spectral
       b. Contexte inter-tracks (masking, accumulation)
       c. Liste des corrections candidates
       d. Justification (Feature 1)
       e. Budget de bandes
       f. Calcul des paramètres
       g. Écriture dans le .als
    3. Sauvegarder le .als corrigé
    4. Retourner un rapport détaillé
    """
```

### Fonctions unitaires (déjà partiellement existantes)

```python
# Nettoyage
write_static_hpf(als_path, track, freq_hz, band=0)
write_static_lpf(als_path, track, freq_hz, band=7)
write_adaptive_hpf(als_path, track, rolloff_curve, times, masking_mask, band=0)

# Peaks
write_peak_following_notch(als_path, track, peak_trajectory, band, max_reduction, genre_profile)

# Masking
write_masking_cut(als_path, track, zone, masking_scores, priority, band, genre_profile)
write_reciprocal_cuts(als_path, track_a, track_b, zone, masking_scores, bands, genre_profile)

# Zones
write_mud_cut(als_path, track, mud_energy, accumulation, band, genre_profile)
write_deesser(als_path, track, sibilance_energy, peaks, band, genre_profile)

# Boosts
write_presence_boost(als_path, track, presence_energy, deficit, band, genre_profile)
write_air_boost(als_path, track, rolloff, deficit, band, genre_profile)

# Stéréo
write_ms_correction(als_path, track, phase_data, width_data, band, genre_profile)
```

---

## 9. Prochaines étapes

1. **Implémenter le pipeline de décision (section 4)** comme module `eq8_decision_engine.py`
2. **Intégrer les données inter-tracks** (masking, accumulation) — dépend de Feature 1
3. **Ajouter le placement dans la chaîne** — `find_insertion_point()` pour pre/post compressor
4. **Tester sur Acid Drops** — appliquer le pipeline complet, valider dans Ableton
5. **Généraliser** — tester sur un projet différent pour valider l'indépendance
