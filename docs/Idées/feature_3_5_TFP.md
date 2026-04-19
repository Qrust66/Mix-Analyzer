# Feature 3.5 — Track Function Profile (TFP)

## Référence : Mix Analyzer v3.1 / Feature 3.5 de N

---

## 1. Problème métier

Feature 1 classe les tracks par `priority` (1=kick/bass, 5=noise/pad). C'est trop grossier. Une même track joue des rôles différents selon les sections — la basse peut être hero dans le drop et support dans le breakdown. Le pad qui sature dans l'intro peut devenir l'élément central dans le break.

Feature 3 mesure ce qui se passe (qui joue, où, quelle énergie) mais ne sait pas **ce que ça doit faire** dans l'arrangement.

Sans intention déclarée, le système prend des décisions par défaut (couper le 248 Hz du Acid Bass parce que ça masque) qui peuvent détruire la signature de la production.

**Conséquences :**
- Pas de protection des fréquences signatures (le 248 Hz qui définit le character d'un patch)
- Pas de différenciation par section (la basse héroïque dans le drop = traitée comme la basse en arrière-plan dans le verse)
- Les corrections "intelligentes" deviennent des corrections **uniformément agressives**

Un ingénieur de mix demande à l'artiste : "qui doit être devant, qui doit être derrière, qu'est-ce qui doit briller, qu'est-ce qui doit se faire petit ?" Le système doit poser cette question.

---

## 2. Objectif

Créer un système de classification fonctionnelle des tracks par section qui combine :

1. **Mesures objectives** calculées automatiquement (rang d'énergie, densité d'onsets, stabilité de pitch, largeur stéréo, fundamental_zone)
2. **Déclaration d'intention** par l'utilisateur dans un fichier YAML par projet
3. **Validation croisée** entre mesures et déclaration (si l'utilisateur déclare "lead" mais la track n'a aucune énergie dans la zone presence, alerter)

Le TFP devient un input de toutes les décisions de correction (Features 1, 4, 5) via le `CorrectionContext`.

---

## 3. Structure du TFP

### Fichier YAML par projet

Convention de nom : `<projet>_TFP.yaml` à côté du `.als`.

```yaml
# Acid_Drops_TFP.yaml
project: Acid Drops
genre: dark_industrial_techno
generated_at: 2026-04-18T16:35:00
schema_version: 1.0

# Sections (importées de Feature 3, juste pour référence)
sections:
  - {index: 0, label: INTRO, start_s: 0.0, end_s: 29.3}
  - {index: 1, label: BUILD, start_s: 29.3, end_s: 44.0}
  - {index: 2, label: DROP, start_s: 44.0, end_s: 95.4}
  - {index: 3, label: BREAK, start_s: 95.4, end_s: 110.0}
  # ...

# Profil par track
tracks:
  Bass Rythm:
    # MESURES OBJECTIVES (calculées par le système)
    measured:
      energy_rank_overall: 6           # 6e track la plus énergique du mix
      energy_rank_by_section:
        INTRO: 12
        BUILD: 8
        DROP: 4                        # parmi top 5 dans le drop
        BREAK: 25                      # quasi inactive dans le break
      onset_density: high              # > 4 onsets/sec
      pitch_stability: stable          # peu de variation de fondamentale
      stereo_width: narrow             # < 0.2
      fundamental_zone: Low
      harmonic_zones: [LowMid, Mud]
      protection_freqs_detected:       # peaks persistants > 70% du temps actif
        - {freq_hz: 127, persistence: 0.92, suggestion: signature}
        - {freq_hz: 247, persistence: 0.45, suggestion: parasite}

    # DÉCLARATION D'INTENTION (utilisateur)
    declared:
      function_default: rhythmic_bass
      function_by_section:             # override par section si différent
        DROP: rhythmic_bass_hero
        BREAK: skip                    # ignore cette track dans le break
      protect_zones:                   # zones à NE PAS toucher
        - Low                          # zone d'expression
        - LowMid                       # harmoniques essentielles
      protect_freqs:                   # fréquences spécifiques à protéger
        - {freq_hz: 127, max_cut_db: -1, reason: "fondamentale signature"}
      allow_aggressive_cuts_in:        # zones où on peut taper fort
        - Mud
        - Body
      sidechain_priority: 3            # 1=kick, 2=sub, 3=rhythmic_bass, etc.
      stereo_intent: mono_centered     # mono_centered | narrow | natural | wide

  Pluck Lead:
    measured:
      energy_rank_overall: 11
      energy_rank_by_section:
        DROP: 5
        BREAK: 30
      onset_density: medium
      pitch_stability: variable
      stereo_width: medium
      fundamental_zone: Mid
      harmonic_zones: [HighMid, Presence]
      protection_freqs_detected:
        - {freq_hz: 247, persistence: 0.68, suggestion: signature}
    declared:
      function_default: lead_synth
      function_by_section:
        DROP: lead_synth_hero
        BREAK: lead_synth_atmosphere
      protect_zones: [Mid, HighMid, Presence]
      protect_freqs:
        - {freq_hz: 247, max_cut_db: 0, reason: "lead fundamental"}
      allow_aggressive_cuts_in: [Sub, Low]
      sidechain_priority: 6
      stereo_intent: natural

# Métadonnées
metadata:
  user_validated: false               # true quand l'utilisateur a relu et validé
  warnings:                           # incohérences détectées
    - "Bass Rythm declared 'rhythmic_bass' but energy_rank_in_drop=4 suggests 'rhythmic_bass_hero'"
```

### Vocabulaire des fonctions

Vocabulaire emprunté au métier, pas inventé :

| Function | Description | Exemples |
|---|---|---|
| `rhythmic_bass` | Basse rythmique support | walking bass, basse de pad |
| `rhythmic_bass_hero` | Basse rythmique en avant | basse acid d'un drop, sub d'un drum&bass |
| `sub_anchor` | Ancrage sub permanent | 808 sub continu |
| `kick_pulse` | Pulse rythmique principal | kick |
| `percussion_layer` | Couche percussive | toms, claps, hi-hats |
| `lead_synth` | Synth mélodique support | nappe, arpège léger |
| `lead_synth_hero` | Synth mélodique en avant | lead chargé du drop |
| `harmonic_pad` | Pad harmonique | nappe, drone tonal |
| `atmosphere` | Texture d'ambiance | bruit, drone, FX |
| `vocal_lead` | Voix principale | lead vocal, hook |
| `vocal_support` | Voix d'accompagnement | harmonies, doublures |
| `transition` | Élément transitionnel | riser, downer, sweep |
| `glue` | Élément de cohésion | reverb send, room |
| `skip` | Ignorer cette track | track inactive ou hors mix |

L'utilisateur peut ajouter des fonctions custom dans son TFP — le système ne valide que la cohérence entre measured et declared.

### Vocabulaire des stereo_intent

| Intent | Largeur attendue | Exemples |
|---|---|---|
| `mono_centered` | width = 0 | kick, sub, lead vocal |
| `narrow` | width 0.1-0.3 | basse rythmique, percussion centrale |
| `natural` | width 0.3-0.5 | la plupart des instruments |
| `wide` | width 0.5-0.8 | pads, FX |
| `extreme` | width > 0.8 | atmospheres, drones spatialisés |

---

## 4. Pipeline de génération du TFP

### Mode auto (premier passage)

```
INPUT : .als + rapport Excel + sections (de Feature 3)

POUR chaque track :
  1. Calculer les mesures objectives :
     - energy_rank_overall depuis _track_zone_energy moyenné
     - energy_rank_by_section depuis _track_copresence (Feature 3)
     - onset_density depuis _track_transients
     - pitch_stability depuis _track_peak_trajectories (variance des fréquences)
     - stereo_width depuis _track_stereo_bands moyenné
     - fundamental_zone : zone avec énergie max
     - harmonic_zones : zones secondaires > -20 dB
     - protection_freqs_detected : peaks persistants > 70% du temps actif

  2. Proposer une function_default basée sur des heuristiques :
     - energy_rank_overall <= 5 + zone=Low + width=0 → kick_pulse
     - energy_rank_overall <= 10 + zone=Sub + width=0 → sub_anchor
     - zone=Low + onset_density=high → rhythmic_bass
     - zone=Mid + pitch_stability=variable → lead_synth
     - zone=Presence + onset_density=high → vocal_lead
     - ... (table d'heuristiques complète dans le code)

  3. Proposer protect_zones :
     - fundamental_zone : toujours protégé
     - harmonic_zones : protégé sauf si overlap avec accumulation_warning de Feature 3

  4. Proposer allow_aggressive_cuts_in :
     - Zones où l'énergie de cette track est < -25 dB ET masking_score avec d'autres tracks > 0.4

ÉCRIRE le YAML avec metadata.user_validated = false
```

### Mode validation (utilisateur ouvre le YAML)

L'utilisateur peut :
- Modifier les `declared` (function, protect_zones, etc.)
- Garder les valeurs proposées
- Ajouter des fonctions custom
- Mettre `metadata.user_validated = true` quand satisfait

Le pipeline détecte les incohérences entre `measured` et `declared` :
- Si `declared.function_by_section.DROP = atmosphere` mais `measured.energy_rank_by_section.DROP = 3` → warning "track classée atmosphere mais 3e plus énergique du drop"

### Mode itératif (re-run après modifications)

À chaque re-run du pipeline :
- Les `measured` sont recalculés (le mix change)
- Les `declared` sont préservés (intention de l'utilisateur)
- Les warnings sont régénérés

Le YAML devient un compagnon vivant du projet.

---

## 5. Intégration avec CorrectionContext

`CorrectionContext` (de Feature 1) reçoit un nouveau champ :

```python
@dataclass
class CorrectionContext:
    # ... champs existants ...

    tfp: TrackFunctionProfile | None      # profil de la track courante
    section_tfp: dict[str, TrackFunctionProfile] | None  # tous les profils, pour lookup
```

```python
@dataclass
class TrackFunctionProfile:
    track_name: str
    function_default: str
    function_by_section: dict[str, str]
    protect_zones: list[str]
    protect_freqs: list[ProtectFreq]
    allow_aggressive_cuts_in: list[str]
    sidechain_priority: int
    stereo_intent: str
    measured: MeasuredMetrics              # pour audit

@dataclass
class ProtectFreq:
    freq_hz: float
    max_cut_db: float                       # 0 = pas de cut autorisé
    reason: str
```

### Méthodes utilitaires

```python
def get_function_in_section(tfp: TrackFunctionProfile, section_label: str) -> str:
    """Retourne function_by_section[section] sinon function_default."""

def is_freq_protected(tfp: TrackFunctionProfile, freq_hz: float, tolerance_semitones: float = 0.5) -> ProtectFreq | None:
    """Retourne le ProtectFreq si la fréquence est dans la zone de protection, sinon None."""

def get_max_cut_for_zone(tfp: TrackFunctionProfile, zone: str) -> float:
    """Retourne le cut max autorisé dans cette zone (0 si protected, -inf si aggressive_allowed)."""
```

---

## 6. Refactor de Feature 1

`track_priority` (1-5 entier) → `tfp.sidechain_priority` (entier, plus contextuel)

`evaluate_justification()` consulte le TFP :

```
ÉTAPE 0.5 — Vérifier les protect_zones et protect_freqs
  Si la fréquence ciblée est dans tfp.protect_freqs :
    → Si max_cut_db = 0 : skip (pas touchable)
    → Sinon : limiter le cut à max_cut_db et continuer

  Si la zone ciblée est dans tfp.protect_zones :
    → Réduire l'intensité de 50%
    → Continuer la cascade

  Si la zone ciblée est dans tfp.allow_aggressive_cuts_in :
    → Augmenter l'intensité autorisée de 30%
    → Continuer la cascade

ÉTAPE 1 — Audibilité (existant)
ÉTAPE 2 — Contenu présent (existant)
ÉTAPE 3 — Masking (existant, mais utilise function_in_section pour pondération)
ÉTAPE 4 — Peak isolé extrême (existant)
ÉTAPE 5 — Accumulation (existant, mais skip si tfp.function = hero)
ÉTAPE 6 — Décision finale
```

---

## 7. Stockage et exposition

### Fichier YAML
Source de vérité, versionné avec le projet.

### Sheet Excel `_track_function_profile`

Pour visualisation rapide dans le rapport :

| Track | Function (default) | Function (DROP) | Protect zones | Protect freqs | Sidechain prio | Stereo intent | Validated |
|---|---|---|---|---|---|---|---|
| Bass Rythm | rhythmic_bass | rhythmic_bass_hero | Low, LowMid | 127 Hz | 3 | mono_centered | ✅ |
| Pluck Lead | lead_synth | lead_synth_hero | Mid, HighMid, Presence | 247 Hz | 6 | natural | ⚠️ |

### API Python

```python
def load_tfp(yaml_path: Path) -> dict[str, TrackFunctionProfile]:
    """Charge le YAML et retourne un dict track_name → profile."""

def generate_tfp(als_path: Path, report_path: Path, sections: list[Section]) -> dict:
    """Génère un TFP from scratch avec auto-classification."""

def update_tfp(yaml_path: Path, als_path: Path, report_path: Path, sections: list[Section]) -> dict:
    """Recalcule les measured, préserve les declared, régénère les warnings."""

def validate_tfp(tfp: dict) -> list[str]:
    """Retourne la liste des incohérences entre measured et declared."""
```

---

## 8. Tests d'acceptance

### Test 1 — Auto-classification cohérente
- Acid Drops, génération auto
- **Attendu :** Kick 1 classée `kick_pulse`, Sub Bass classée `sub_anchor`, Bass Rythm classée `rhythmic_bass`

### Test 2 — Protect freqs détectées
- Bass Rythm a un peak à 127 Hz présent 92% du temps actif
- **Attendu :** `protection_freqs_detected` contient 127 Hz avec suggestion `signature`

### Test 3 — Function par section
- Pluck Lead a `energy_rank_by_section.DROP = 5` et `BREAK = 30`
- **Attendu :** auto-suggestion `lead_synth_hero` dans DROP, `lead_synth_atmosphere` dans BREAK

### Test 4 — Préservation des declared après re-run
- Utilisateur édite `declared.function_default = atmosphere` sur une track
- Pipeline re-run
- **Attendu :** `declared.function_default` reste `atmosphere`, `measured` est mis à jour

### Test 5 — Détection d'incohérences
- `declared.function = atmosphere` mais `measured.energy_rank_by_section.DROP = 3`
- **Attendu :** warning généré dans `metadata.warnings`

### Test 6 — Intégration avec Feature 1
- Bass Rythm avec `protect_freqs: [{freq: 127, max_cut: -1}]`
- Feature 1 essaie d'écrire un notch -6 dB à 127 Hz
- **Attendu :** notch limité à -1 dB

---

## 9. Dépendances

- **Feature 3 (sections)** : OBLIGATOIRE — TFP est défini par section
- **`_track_zone_energy`, `_track_transients`, `_track_stereo_bands`, `_track_peak_trajectories`** : sources des `measured`
- **PyYAML** : nouvelle dépendance Python pour lire/écrire le YAML
- **Feature 1** : sera refactorisé pour consulter TFP

---

## 10. Plan de développement

### Phase A — Calcul des measured
- Module `track_function_profile.py`
- `compute_measured_metrics(track_name, sections, report) -> MeasuredMetrics`
- Tests : Acid Drops doit produire les rangs corrects

### Phase B — Heuristiques de classification auto
- Table de règles function_default (configurable)
- `propose_function(measured) -> str`
- Tests : Test 1 et 3

### Phase C — YAML I/O
- `load_tfp()`, `generate_tfp()`, `update_tfp()`
- Préservation des declared après re-run
- Tests : Test 4

### Phase D — Validation et warnings
- `validate_tfp()` détecte les incohérences
- Tests : Test 5

### Phase E — Sheet Excel et intégration CorrectionContext
- Ajout du sheet `_track_function_profile`
- Refactor Feature 1 pour consommer TFP
- Tests : Test 6

---

## 11. Décisions techniques par défaut

Ces choix sont **proposés**, à challenger :

1. **YAML plutôt que JSON** : YAML est plus lisible pour un humain qui édite à la main. Commentaires possibles. Convention DAW/audio.

2. **Auto + validation utilisateur** (option C de la discussion) : pas de full auto, pas de full manuel. Le système propose, l'utilisateur valide.

3. **Vocabulaire fonctionnel emprunté au métier** : pas de hero/support/glue inventés. Termes empruntés (rhythmic_bass, lead_synth, sub_anchor) avec extensibilité (custom OK).

4. **Function_by_section optionnel** : si non spécifié, function_default s'applique partout. Pas de redondance forcée.

5. **Protection à deux niveaux** : zones (large) + freqs (chirurgical). Permet de protéger une zone tout en autorisant des cuts hors des fondamentales.

6. **Re-run préserve les declared** : l'utilisateur n'est jamais écrasé par un re-run automatique.
