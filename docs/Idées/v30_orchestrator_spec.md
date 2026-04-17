# Mix Analyzer v3.0 — Orchestrateur de Corrections

## Document de référence — Phase majeure suivante

---

## 1. Pourquoi

Le Mix Analyzer a deux systèmes qui ne se parlent pas :

- **Système A (analyse)** : `.als` + WAV → features spectrales → rapport Excel
- **Système B (correction)** : features + `.als` → automations EQ8

Entre les deux, il n'y a rien. Pour lancer une correction, il faut écrire du Python à la main, connaître les noms de fonctions, les paramètres, les types de données. C'est inutilisable sans un développeur dans la boucle.

L'orchestrateur est le nerf qui connecte A et B. Il lit le rapport, identifie les problèmes, propose un plan lisible, attend la validation humaine, et exécute les corrections sur le `.als`.

---

## 2. Flow utilisateur complet

```
[1] L'utilisateur lance le Mix Analyzer sur son .als
    → Rapport Excel (features v2.5, automation_map, anomalies)

[2] L'utilisateur lance l'orchestrateur
    → Input : rapport Excel + .als + genre_profiles.json + corrections_config.json
    → Output : plan de corrections en Markdown (correction_plan.md)

[3] L'utilisateur lit le plan, modifie, coche/décoche
    → Option : envoyer le plan à Claude pour avis sur les items ambigus

[4] L'utilisateur relance l'orchestrateur en mode "exécute"
    → Input : correction_plan.md validé + .als original
    → Output : .als corrigé (copie, jamais l'original) + rapport d'exécution

[5] L'utilisateur ouvre le .als corrigé dans Ableton et écoute
    → Si satisfait : terminé
    → Si ajustements nécessaires : modifie le plan, relance étape 4
```

**Commandes concrètes (CLI) :**

```bash
# Étape 2 — Générer le plan
python orchestrator.py plan --report Acid_drops_MixAnalyzer.xlsx --als Acid_drops.als --genre Industrial

# Étape 4 — Exécuter le plan validé
python orchestrator.py apply --plan correction_plan.md --als Acid_drops.als

# Raccourci — tout d'un coup (pour les corrections safe)
python orchestrator.py auto --report Acid_drops_MixAnalyzer.xlsx --als Acid_drops.als --genre Industrial --passes 1,2
```

---

## 3. Architecture des fichiers

```
Mix Analyzer/
├── mix_analyzer.py              # Analyse (existant)
├── spectral_evolution.py        # Features v2.5 (existant)
├── feature_storage.py           # Sheets Excel (existant)
├── automation_map.py            # Carte des automations (existant)
├── als_utils.py                 # Manipulation .als (existant)
├── eq8_automation.py            # Écriture automations EQ8 (existant)
│
├── orchestrator.py              # ← NOUVEAU — cerveau de l'orchestrateur
├── plan_generator.py            # ← NOUVEAU — génère le plan Markdown
├── plan_parser.py               # ← NOUVEAU — lit le plan validé
├── track_classifier.py          # ← NOUVEAU — détecte le type de track
├── genre_profiles.json          # ← NOUVEAU — profils par genre × track type
│
├── projects/                    # ← NOUVEAU — un dossier par projet
│   └── acid_drops/
│       ├── corrections_config.json    # Préférences persistantes du projet
│       ├── correction_plan.md         # Plan en cours
│       └── execution_log.md           # Historique des corrections appliquées
│
├── defaults/
│   └── qrust_defaults.json      # Préférences globales de l'artiste
│
└── docs/prompts/                # Specs et prompts (existant)
```

---

## 4. Les 6 passes

L'orchestrateur suit le workflow de mix en 6 passes séquentielles. Chaque passe est indépendante — l'utilisateur peut s'arrêter après n'importe laquelle, ouvrir le `.als` dans Ableton, écouter, puis reprendre.

### Passe 1 — Gain Staging

**Objectif :** Niveaux relatifs corrects avant tout traitement.

**Ce que l'orchestrateur analyse :**
- LUFS par track (depuis le rapport Excel, sheet AI Context)
- Écarts par rapport à la hiérarchie attendue pour le genre (kick > bass > leads > pads > fx)
- Tracks anormalement fortes ou faibles vs la médiane

**Ce qu'il propose :**
- Ajustements de fader volume dans le `.als`
- Ajustements de Utility gain si le fader est déjà à sa limite

**Ce qu'il écrit dans le `.als` :**
- `MixerDevice/Volume/Manual` (valeur statique du fader)
- Ou `StereoGain/Gain/Manual` (Utility)
- PAS d'automation — c'est un réglage de base

**Paramètres genre :**
- Hiérarchie de niveaux par track type (kick à -12 dB, bass à -14, leads à -18, etc.)
- Tolérance d'écart acceptable avant correction

**Fonctions existantes nécessaires :** `als_utils.py` (lecture/écriture XML)
**Fonctions à créer :** `write_fader_adjustment()`, `write_utility_gain_adjustment()`

**Exemple de plan :**
```markdown
# PASSE 1 — Gain Staging
# Genre: Industrial | Intensité: 100%

## Anomalies de niveau détectées

  5-Toms Rack (Drums/Tom): -15.35 LUFS
    Médiane projet: -25 LUFS | Écart: +10 dB | Seuil genre: ±6 dB
    - [x] Baisser fader de -8 dB → cible -23 LUFS

  Solo Noise (Synth/Texture): -66 dB RMS
    Quasi inaudible. Intentionnel?
    - [ ] Monter fader de +12 dB — À VALIDER

  Riser (FX): +4 dB LUFS au-dessus du kick
    L'effet de transition ne devrait pas dominer
    - [x] Baisser fader de -6 dB
```

---

### Passe 2 — HPF / LPF (nettoyage fréquentiel)

**Objectif :** Couper ce qui ne sert pas, protéger ce qui compte.

**Ce que l'orchestrateur analyse :**
- `low_rolloff_curve` et `high_rolloff_curve` (features v2.5)
- Énergie sub par track (zone_energy Sub 20-80 Hz)
- Track type → HPF max acceptable (depuis genre_profiles.json)

**Ce qu'il propose :**
- HPF adaptatifs (automation EQ8 qui suit le rolloff)
- HPF safety à 30 Hz pour les tracks sans contenu sub
- LPF adaptatifs pour les tracks à spectre borné (kick, sub bass)

**Ce qu'il écrit dans le `.als` :**
- Automations EQ8 via `write_adaptive_hpf()`, `write_adaptive_lpf()`, `write_safety_hpf()`

**Paramètres genre (exemples Industrial) :**
- Kick : HPF max 30 Hz (ne pas toucher au sub du kick)
- Bass : HPF max 30 Hz
- Pad/Drone : HPF max 100 Hz (nettoyage OK)
- Noise/Ambience : HPF max 150 Hz (nettoyage agressif)

**Exemple de plan :**
```markdown
# PASSE 2 — HPF / LPF
# Genre: Industrial | Intensité: 80%

## HPF adaptatifs
  Toms Rack (Drums/Tom): rolloff oscille 55–85 Hz | HPF genre max: 60 Hz
    - [x] HPF adaptatif, safety 10 Hz → cutoff effectif ~50-75 Hz

  Guitar Distorted (Guitar/Distorted): rolloff 90–120 Hz | HPF genre max: 80 Hz
    - [x] HPF adaptatif, safety 10 Hz → cutoff effectif ~70-80 Hz (plafonné)

## Safety HPF 30 Hz (tracks sans contenu sub)
  14 tracks identifiées avec énergie sub < -60 dB
    - [x] Appliquer HPF 30 Hz à : Hi-Hat, Clap, China, Tambourine, Xylo Perc,
          Xylo Texture, Harmony Vocal, Lead Vocal Hey, Lead Vocal Shhh,
          Voice FX, Guitar PM A, Guitar PM B, Pluck Lead, ARP Glitter Box

## LPF adaptatifs
  Sub Bass: rolloff high stable ~200 Hz
    - [x] LPF adaptatif 250 Hz — tout au-dessus est du bruit
```

---

### Passe 3 — Résonances et notches

**Objectif :** Corrections chirurgicales des peaks problématiques.

**Ce que l'orchestrateur analyse :**
- `peak_trajectories` (features v2.5) — fréquence, amplitude, durée
- Résonances récurrentes sur plusieurs tracks (même fréquence)
- Amplitude du peak vs seuil du genre (genre_profiles.json)

**Ce qu'il propose :**
- Notches dynamiques proportionnels (amplitude adaptée frame par frame)
- Résonance suppression multi-band pour les tracks très résonantes
- Identification des résonances harmoniques (fondamentale + multiples)

**Ce qu'il écrit dans le `.als` :**
- `write_dynamic_notch()`, `write_resonance_suppression()`

**Logique de calibration :**
```
reduction_db = peak_amplitude × (genre_max_reduction / reference_amplitude) × intensity × character_factor
```
- `genre_max_reduction` : depuis genre_profiles.json (ex: -2.0 dB pour Acid Bass Industrial)
- `intensity` : slider de passe (0-100%)
- `character_factor` : 1.0 si Abrasif (character=0), 1.5 si Atmosphérique (character=1) — plus propre = corrections plus agressives

**Gestion des résonances récurrentes :**
Si 248 Hz apparaît sur 8+ tracks, le plan le signale comme fondamentale probable du morceau :
```markdown
⚠ FRÉQUENCE RÉCURRENTE : 248 Hz détectée sur 8 tracks
  Probablement la fondamentale (B2/C3). Corriger individuellement, pas globalement.
```

**Exemple de plan :**
```markdown
# PASSE 3 — Résonances
# Genre: Industrial | Intensité: 50% | Character: 0.2 (Abrasif)

## Résonances récurrentes
  ⚠ 248 Hz sur 8 tracks — fondamentale probable (B2)

## Par track
  Toms Rack (Drums/Tom): genre max -4.0 dB × 50% = max -2.0 dB
    248 Hz (peak -4 dB, durée 80%) → notch proportionnel, max -1.8 dB
    - [x] Notch dynamique 248 Hz, Q=8

  Acid Bass (Bass/Acid): genre max -2.0 dB × 50% = max -1.0 dB
    248 Hz (peak -6 dB, durée 90%) → notch -0.7 dB
    - [ ] ~~Notch 248 Hz~~ — REFUSÉ: résonance fait partie du son acid
    129 Hz (peak -8 dB, durée 70%) → notch -0.5 dB
    - [x] Notch dynamique 129 Hz, Q=8
    366 Hz (peak -5 dB, durée 65%) → notch -0.8 dB
    - [x] Notch dynamique 366 Hz, Q=8

  ARP Glitter Box (Synth/Arpeggio): genre max -3.5 dB × 50% = max -1.75 dB
    248 Hz (peak -3 dB, durée 40%) → notch -1.2 dB
    - [x] Notch dynamique 248 Hz, Q=8
```

---

### Passe 4 — Masking / conflits inter-tracks

**Objectif :** Séparer les instruments qui se marchent dessus dans le spectre.

**Ce que l'orchestrateur analyse :**
- `masking_scores` via `detect_masking()` — paires de tracks, score par zone, sévérité
- Track types pour déterminer la priorité (kick > bass > lead > pad)
- `masking_tolerance` du genre (genre_profiles.json)

**Ce qu'il propose :**
- Cuts réciproques (les deux tracks se font une place)
- Sidechain EQ ciblé (une track duck quand l'autre joue)
- Parfois juste un signal : "le masking est détecté mais toléré pour le genre"

**Logique de décision :**
```
Si masking_score > (1 - masking_tolerance) du track type :
    → Proposer correction
Sinon :
    → Toléré pour le genre (pas dans le plan)
```

**Ce qu'il écrit dans le `.als` :**
- `write_masking_reciprocal_cuts()`, `write_targeted_sidechain_eq()`

**Exemple de plan :**
```markdown
# PASSE 4 — Masking
# Genre: Industrial | Intensité: 60%

## Conflits critiques (score > seuil genre)

  Kick 1 ↔ Sub Bass — zone Low (80-250 Hz)
    Score: 0.82 | Seuil Industrial Kick: 0.3 (1 - tolérance 0.7) → DÉPASSE
    Priorité: Kick (transient) > Sub Bass (sustain)
    - [x] Cuts réciproques centrés 120 Hz, -1.8 dB (base -3 × 60%)

  Acid Bass ↔ Bass Rythm — zone Mud (200-500 Hz)
    Score: 0.65 | Seuil: 0.3 → DÉPASSE
    - [x] Sidechain EQ: Bass Rythm duck quand Acid Bass présent, -2.4 dB

## Conflits tolérés (en dessous du seuil genre)

  Guitar Distorted ↔ Lead Synth — zone Mid (1-4 kHz)
    Score: 0.45 | Seuil Industrial Guitar: 0.5 → TOLÉRÉ
    (Pas de correction proposée — normal pour le genre)
```

---

### Passe 5 — Dynamique et événements temporels

**Objectif :** Corrections sensibles au timing — transients, sections, sibilance.

**Ce que l'orchestrateur analyse :**
- `transient_events` (features v2.5)
- `delta_spectrum` pour la détection de sections (drop, break, intro)
- `crest_by_zone` pour identifier sustain vs transient
- `zone_energy['sibilance']` pour le de-essing

**Ce qu'il propose :**
- Transient-aware cuts : les notches/cuts des passes précédentes s'atténuent pendant les attaques
- Section-aware EQ : paramètres différents par section du morceau (ex: plus de mud toléré dans l'intro, moins dans le drop)
- De-essing dynamique sur les vocaux

**Ce qu'il écrit dans le `.als` :**
- `write_transient_aware_cut()`, `write_section_aware_eq()`, `write_dynamic_deesser()`

**Exemple de plan :**
```markdown
# PASSE 5 — Dynamique
# Genre: Industrial | Intensité: 40%

## Transient-aware
  Toms Rack: le notch 248 Hz (passe 3) relâche pendant les attaques
    - [x] Release 50ms sur le notch existant

  Kick 1: préserver le transient 2-5 kHz
    - [x] Release 30ms sur le cut masking (passe 4)

## Sections détectées
  Transitions à: T=40s (build), T=88s (drop), T=168s (break), T=232s (outro)
    - [ ] Section-aware EQ sur Acid Bass: mud +2 dB dans l'intro, -1 dB dans le drop

## De-essing
  Harmony Vocal (Vocal/Backing): sibilance à 6.5 kHz
    Genre threshold: -22 dB | Réduction: -3.0 dB × 40% = -1.2 dB
    - [x] De-esser dynamique 6.5 kHz, Q=4
```

---

### Passe 6 — Polish / esthétique

**Objectif :** Boosts adaptatifs, reference matching. Tout est optionnel.

**Ce que l'orchestrateur analyse :**
- Déficit de présence (zone_energy Presence 2-5 kHz)
- Rolloff high trop bas (perte d'air)
- Comparaison avec un track de référence (optionnel)

**Ce qu'il propose :**
- Presence boost adaptatif (seulement quand la track perd de la présence)
- Air boost (seulement quand le rolloff high tombe)
- Spectral match vers une référence

**Ce qu'il écrit dans le `.als` :**
- `write_adaptive_presence_boost()`, `write_adaptive_air_boost()`, `write_spectral_match()`

**Exemple de plan :**
```markdown
# PASSE 6 — Polish
# Genre: Industrial | Intensité: 30% | Character: 0.2
# ⚡ Tout est optionnel — ces corrections sont esthétiques

## Présence
  NINja Lead Synth (Synth/Lead): perte 3 kHz dans sections denses
    Genre max boost: +2.5 dB × 30% = +0.75 dB
    - [ ] Boost adaptatif 3 kHz, +0.75 dB max — ton call

## Air
  Full Mix: rolloff high à 12 kHz (genre attend ~15 kHz)
    - [ ] Air boost shelf 10 kHz sur les tracks avec rolloff < 8 kHz
    Candidates: Glider Lead, ARP Intense

## Reference matching
  Pas de track de référence fournie
    - [ ] Skip — ou fournir une référence .wav pour la prochaine analyse
```

---

## 5. Système d'intensité

### Par passe

Chaque passe a un slider d'intensité (0–100%). Les valeurs du `genre_profiles.json` représentent 100%. L'intensité scale linéairement toutes les réductions/boosts de la passe.

**Defaults par genre (Industrial) :**
```json
{
  "gain_staging": 1.0,    // Passe 1 — toujours à 100%, c'est technique
  "hpf_lpf": 0.7,         // Passe 2 — conservateur sur les filtres
  "resonances": 0.5,      // Passe 3 — 50%, industriel = résonances tolérées
  "masking": 0.5,          // Passe 4 — 50%, masking parfois voulu
  "dynamics": 0.4,         // Passe 5 — 40%, pas overcorriger
  "polish": 0.3            // Passe 6 — 30%, touche minimale
}
```

### Par item (override)

L'utilisateur peut modifier la valeur de dB directement sur une ligne du plan :

```markdown
  - [x] Notch dynamique 248 Hz, max -1.8 dB → -2.5 dB  # override manuel
```

L'orchestrateur utilise la valeur overridée au lieu du calcul automatique.

### Spectre Character (Abrasif ↔ Atmosphérique)

Le paramètre `character` (0.0–1.0) modifie l'agressivité globale des corrections :

| Character | Effet |
|---|---|
| 0.0 (Abrasif) | Corrections minimales, préserve la saleté, mud toléré |
| 0.5 (Équilibré) | Corrections standard pour le genre |
| 1.0 (Atmosphérique) | Corrections plus agressives, clarté, séparation |

**Formule :**
```
correction_effective = correction_base × intensity × (0.7 + 0.6 × character)
```
À character=0 : facteur 0.7 (atténué)
À character=0.5 : facteur 1.0 (neutre)
À character=1.0 : facteur 1.3 (amplifié)

---

## 6. Mémoire et préférences

### corrections_config.json (par projet)

Vit dans `projects/<nom_projet>/`. Persiste entre les analyses.

```json
{
  "project": "Acid Drops",
  "genre": "Industrial",
  "character": 0.2,
  "intensity_overrides": {
    "resonances": 0.4
  },
  "track_type_overrides": {
    "Acid Bass": {
      "detected_type": "Bass/Acid",
      "confirmed": true
    },
    "NINja Lead Synth": {
      "detected_type": "Synth/Lead",
      "confirmed": true
    }
  },
  "refused_corrections": [
    {
      "track": "Acid Bass",
      "type": "dynamic_notch",
      "freq_hz": 248,
      "reason": "résonance fait partie du son acid",
      "date": "2026-04-16"
    },
    {
      "track": "Solo Noise",
      "type": "gain_staging",
      "action": "raise_fader",
      "reason": "volume bas intentionnel",
      "date": "2026-04-16"
    }
  ],
  "accepted_corrections_history": [
    {
      "pass": 2,
      "track": "Toms Rack",
      "type": "adaptive_hpf",
      "params": {"safety_hz": 10},
      "date": "2026-04-16"
    }
  ]
}
```

**Comportement :**
- Quand l'utilisateur décoche un item et relance → l'orchestrateur l'ajoute à `refused_corrections`
- Prochaine analyse → l'item refusé apparaît barré avec la raison :
  ```markdown
  - [ ] ~~Notch 248 Hz~~ — REFUSÉ (2026-04-16): résonance fait partie du son acid
  ```
- Pour annuler un refus : l'utilisateur recoche la ligne et relance

### qrust_defaults.json (global, tous les projets)

Vit dans `defaults/`. Contient les préférences de l'artiste qui s'appliquent à tous les projets :

```json
{
  "artist": "Qrust",
  "default_genre": "Industrial",
  "default_character": 0.2,
  "global_rules": {
    "never_hpf_above_hz": {
      "Sub Bass": 25,
      "Acid Bass": 25,
      "808/Pitched Bass": 20
    },
    "always_preserve_transients": ["Kick", "Snare/Clap", "Tom"],
    "skip_corrections_on": ["Drum Loop/Bus"],
    "min_peak_db_for_notch": -40,
    "max_correction_db_any_band": -8
  }
}
```

**Priorité :** `qrust_defaults.json` < `genre_profiles.json` < `corrections_config.json` < override manuel dans le plan

---

## 7. Classification des tracks

### Module : `track_classifier.py`

**Objectif :** Assigner un track type (depuis la liste Mix Analyzer) à chaque track automatiquement.

**Méthode — en 3 étapes :**

1. **Nom de la track** — heuristique sur le nom dans le `.als` :
   - "Kick" → Drums/Kick
   - "Sub Bass", "Sub" → Bass/Sub Bass
   - "Acid" → Bass/Acid Bass
   - "Lead" + "Synth" → Synth/Lead
   - "Pad" → Synth/Pad
   - "Guitar" + "Dist" → Guitar/Distorted
   - "Vocal", "Vox" → Vocal/Lead
   - "FX", "Riser" → FX/Riser
   - "BUS", "Bus" → skip_corrections

2. **Features spectrales** — validation/correction par les données :
   - Spectral centroid < 200 Hz + crest élevé → Drums/Kick ou Bass/Sub
   - Spectral centroid < 200 Hz + crest bas → Bass/Sub ou Bass/Standard
   - Flatness > 0.8 + énergie high → Noise/Ambience ou Hi-Hat/Cymbal
   - Transients dominants + centroid mid → Drums/Percussion
   - Centroid 1-4 kHz + flatness basse → Synth/Lead ou Guitar

3. **Confirmation utilisateur** — dans le plan, chaque track affiche son type détecté :
   ```markdown
   ## Toms Rack
     Type: Drums/Tom (détecté par nom) ← [modifier si incorrect]
   ```
   Si l'utilisateur modifie, c'est sauvé dans `corrections_config.json`.

---

## 8. Format du plan Markdown

### Structure complète

```markdown
# PLAN DE CORRECTIONS
# Projet: Acid Drops v14
# Genre: Industrial | Character: 0.2 (Abrasif)
# Date: 2026-04-16
# Mix Analyzer v3.0

## Configuration
- Genre: Industrial
- Character: 0.2 / 1.0 (Abrasif)
- Intensités: P1=100% P2=70% P3=50% P4=50% P5=40% P6=30%
- Tracks analysées: 35 + 3 BUS
- Tracks corrigeables: 32 (BUS exclus)

## Tracks et types détectés
| Track | Type détecté | Confiance | Modifié? |
|---|---|---|---|
| Kick 1 | Drums/Kick | 95% (nom) | |
| Acid Bass | Bass/Acid | 90% (nom) | |
| NINja Lead Synth | Synth/Lead | 85% (nom+features) | |
| 5-Toms Rack | Drums/Tom | 80% (nom) | |
| Ambience | Noise/Ambience | 70% (features) | |

---

# PASSE 1 — Gain Staging [100%]
(contenu...)

# PASSE 2 — HPF / LPF [70%]
(contenu...)

# PASSE 3 — Résonances [50%]
(contenu...)

# PASSE 4 — Masking [50%]
(contenu...)

# PASSE 5 — Dynamique [40%]
(contenu...)

# PASSE 6 — Polish [30%]
(contenu...)

---

# RÉSUMÉ
- Total corrections proposées: 47
- Cochées: 38
- Refusées: 6
- À valider: 3
- Bandes EQ8 utilisées: ~2.1 par track en moyenne (sur 8 max)
```

### Syntaxe des items

```markdown
# Correction standard — cochée
- [x] Notch dynamique 248 Hz, max -1.8 dB, Q=8

# Correction refusée (décoché)
- [ ] ~~Notch 248 Hz~~ — REFUSÉ: résonance fait partie du son acid

# Correction avec override de valeur
- [x] Notch dynamique 248 Hz, max -1.8 dB → -2.5 dB, Q=8

# Correction à valider (ambiguë)
- [ ] Monter fader de +12 dB — À VALIDER (intentionnel?)

# Correction refusée précédemment (depuis corrections_config.json)
- [ ] ~~Notch 248 Hz~~ — REFUSÉ (2026-04-16): résonance fait partie du son acid
```

---

## 9. Module plan_parser.py

Lit le `correction_plan.md` validé et retourne une liste structurée de corrections à exécuter.

**Parsing :**
- `- [x]` → exécuter
- `- [ ]` → ignorer (si première fois → sauver dans refused_corrections)
- `→ <valeur>` → override de la valeur calculée
- Chaque item est parsé pour extraire : track, type de correction, paramètres

**Output :**
```python
@dataclass
class PlannedCorrection:
    track_name: str
    track_type: str
    pass_number: int
    correction_type: str        # "adaptive_hpf", "dynamic_notch", etc.
    params: dict                # {"freq_hz": 248, "reduction_db": -1.8, "q": 8}
    overridden_params: dict     # {"reduction_db": -2.5} si override manuel
    status: str                 # "accepted", "refused", "pending"
    reason: str | None          # Raison du refus si applicable
```

---

## 10. Module orchestrator.py

### Commande `plan`

```python
def generate_plan(
    report_path: Path,
    als_path: Path,
    genre: str,
    character: float = None,
    config_path: Path = None,
    defaults_path: Path = None,
    output_path: Path = None,
) -> Path:
    """
    Lit le rapport Excel + .als, identifie les corrections, génère le plan .md.
    
    1. Charger genre_profiles.json → profil du genre
    2. Charger corrections_config.json → refus précédents, overrides
    3. Charger qrust_defaults.json → règles globales
    4. Classifier les tracks (track_classifier.py)
    5. Pour chaque passe (1-6) :
       a. Analyser les features pertinentes
       b. Calculer les corrections selon genre × track_type × intensity × character
       c. Filtrer par refused_corrections (barrer les refus)
       d. Filtrer par qrust_defaults (appliquer les règles globales)
       e. Écrire dans le plan
    6. Sauvegarder correction_plan.md
    """
```

### Commande `apply`

```python
def apply_plan(
    plan_path: Path,
    als_path: Path,
    output_als_path: Path = None,
) -> Path:
    """
    Lit le plan validé, exécute les corrections cochées sur une copie du .als.
    
    1. Parser le plan (plan_parser.py)
    2. Backup le .als original
    3. Pour chaque passe, dans l'ordre :
       a. Collecter les corrections acceptées de cette passe
       b. Appeler les fonctions eq8_automation.py correspondantes
       c. Sauvegarder le .als intermédiaire (optionnel)
    4. Sauvegarder le .als final corrigé
    5. Mettre à jour corrections_config.json (refus, historique)
    6. Générer execution_log.md
    """
```

### Commande `auto` (raccourci)

Génère le plan + applique immédiatement les passes spécifiées (pour les corrections safe). Utile pour les passes techniques (1, 2) qui sont rarement refusées.

---

## 11. Rapport d'exécution

Après `apply`, l'orchestrateur génère `execution_log.md` :

```markdown
# RAPPORT D'EXÉCUTION
# Projet: Acid Drops v14
# Date: 2026-04-16 19:45
# .als original: Acid_drops_Code_P14.als
# .als corrigé: Acid_drops_Code_P14_corrected.als

## Résumé
- Corrections appliquées: 38/47
- Corrections refusées: 6
- Corrections en attente: 3
- Bandes EQ8 utilisées: total 67 sur 280 disponibles (35 tracks × 8 bandes)
- Temps d'exécution: 12 secondes

## Détail par passe

### Passe 1 — Gain Staging
  ✅ Toms Rack: fader -8 dB (0.300 → 0.118)
  ✅ Riser: fader -6 dB (1.000 → 0.500)
  ⏭ Solo Noise: en attente (non validé)

### Passe 2 — HPF / LPF
  ✅ Toms Rack: HPF adaptatif Band 0, 187 breakpoints
  ✅ 14 tracks: Safety HPF 30 Hz, Band 0
  ✅ Sub Bass: LPF 250 Hz, Band 7
  ...

### Passe 3 — Résonances
  ✅ Toms Rack: Notch 248 Hz, Band 1, 203 breakpoints, max -1.8 dB
  ❌ Acid Bass 248 Hz: refusé (résonance voulue)
  ✅ Acid Bass 129 Hz: Notch Band 1, 189 breakpoints, max -0.5 dB
  ...

## Warnings
  ⚠ NINja Lead Synth: 6 bandes EQ8 utilisées sur 8 — presque plein
  ⚠ Acid Bass: 4 bandes EQ8 utilisées — attention si corrections manuelles prévues
```

---

## 12. Garde-fous

### Limites techniques
- **Max 6 bandes EQ8 par track** (laisser 2 pour l'utilisateur) — configurable
- **Max 500 breakpoints par paramètre** — déjà implémenté dans eq8_automation.py
- **Backup obligatoire** avant toute écriture `.als`
- **Jamais écraser l'original** — toujours créer `_corrected.als`
- **Idempotence** — relancer sur un `.als` déjà corrigé met à jour, n'empile pas

### Limites musicales
- **Les BUS ne sont jamais corrigés** — corriger les sources
- **Le Full Mix n'est jamais corrigé** — c'est le résultat, pas une source
- **Les tracks mutées (is_audible=false) ne reçoivent pas de corrections** — déjà implémenté
- **Aucune correction sur les plugins tiers** — seulement EQ8 natif

### Sécurité du mix
- **Alerte si > 6 bandes utilisées** sur une track
- **Alerte si correction totale > -8 dB** sur une bande (probablement excessif)
- **Alerte si HPF dépasse le max du genre** pour le track type
- **Log complet** de chaque modification pour audit

---

## 13. Plan de développement

### Phase 1 — Track classifier + CLI squelette
- `track_classifier.py` : détection par nom + features
- `orchestrator.py` : squelette CLI (argparse), commandes `plan`/`apply`/`auto`
- `genre_profiles.json` : intégré au repo
- Tests : classification sur les 35 tracks d'Acid Drops

### Phase 2 — Plan generator (passes 1-3)
- `plan_generator.py` : génération du Markdown pour passes 1, 2, 3
- Lecture des features depuis le rapport Excel
- Calcul des corrections avec genre × intensity × character
- Intégration `corrections_config.json` (refus)
- Tests : plan généré pour Acid Drops, vérification manuelle

### Phase 3 — Plan generator (passes 4-6)
- Passes 4 (masking), 5 (dynamique), 6 (polish)
- `detect_masking()` sur données réelles Acid Drops
- Tests : plan complet

### Phase 4 — Plan parser + exécution
- `plan_parser.py` : lecture du Markdown, extraction des corrections
- `orchestrator.py apply` : exécution des corrections
- Rapport d'exécution
- Tests : round-trip plan → apply → vérifier `.als`

### Phase 5 — Mémoire et polish
- `corrections_config.json` : sauvegarde des refus
- `qrust_defaults.json` : préférences globales
- Gestion des `.als` intermédiaires entre passes
- UI améliorations (couleurs terminal, progress bar)

### Phase 6 — Smoke test end-to-end
- Acid Drops : analyse → plan → validation → apply → ouvrir dans Ableton
- Vérification visuelle des automations EQ8
- Écoute A/B original vs corrigé

---

## 14. Dépendances existantes

Tout le code nécessaire pour les corrections est déjà écrit :

| Fonction | Module | Passe |
|---|---|---|
| `write_adaptive_hpf()` | eq8_automation.py | 2 |
| `write_adaptive_lpf()` | eq8_automation.py | 2 |
| `write_safety_hpf()` | eq8_automation.py | 2 |
| `write_dynamic_notch()` | eq8_automation.py | 3 |
| `write_resonance_suppression()` | eq8_automation.py | 3 |
| `write_dynamic_bell_cut()` | eq8_automation.py | 3 |
| `detect_masking()` | eq8_automation.py | 4 |
| `write_masking_reciprocal_cuts()` | eq8_automation.py | 4 |
| `write_targeted_sidechain_eq()` | eq8_automation.py | 4 |
| `write_transient_aware_cut()` | eq8_automation.py | 5 |
| `write_section_aware_eq()` | eq8_automation.py | 5 |
| `write_dynamic_deesser()` | eq8_automation.py | 5 |
| `write_adaptive_presence_boost()` | eq8_automation.py | 6 |
| `write_adaptive_air_boost()` | eq8_automation.py | 6 |
| `write_spectral_match()` | eq8_automation.py | 6 |
| `extract_all_features()` | spectral_evolution.py | toutes |
| `extract_all_track_automations()` | automation_map.py | toutes |
| `resample_audibility()` | automation_map.py | toutes |

**À créer pour la Passe 1 uniquement :**
- `write_fader_adjustment()` — dans als_utils.py
- `write_utility_gain_adjustment()` — dans als_utils.py

---

## 15. Hors scope (v3.0)

- Interface graphique (GUI) — la CLI + Markdown est le MVP
- Undo/redo sur le `.als` — le backup + fichiers intermédiaires suffisent
- Real-time preview — on écoute dans Ableton, pas dans le programme
- Multi-projet simultané — un projet à la fois
- Automations non-EQ8 (Compressor, Gate, etc.) — reporté à v4.0
- Analyse de tracks de référence intégrée — l'utilisateur fournit les features manuellement
