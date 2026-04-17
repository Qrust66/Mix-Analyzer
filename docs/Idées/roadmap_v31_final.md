# Mix Analyzer v3.1 — Document Maître Final

## Plan d'implémentation complet

---

## Prérequis absolu

### Milestone 0 — Smoke Test EQ8

Le moteur d'écriture EQ8 doit être validé dans Ableton avant toute autre implémentation.

**Action utilisateur :**
1. Ouvrir `Acid_drops_SMOKE_TEST.als` dans Ableton Live 12
2. Vérifier sur Toms Rack : EQ8 présent, bandes actives, Gain A a une automation non-plate
3. Écouter A/B avec l'original

**Si le Gain est plat ou l'EQ8 est absent :** fixer `find_or_create_eq8()` et le pipeline d'écriture. Ne pas avancer.

**Si le Gain bouge :** Milestone 0 validé. Passer à Session 0.

---

### Session 0 — Durcissement du moteur EQ8

**Contexte :** On a découvert que le moteur écrivait des EQ8 sans bandes, des Notch avec Gain inopérant, et ne lisait pas le mapping JSON. Des fix ont été envoyés mais jamais validés bout en bout.

**Livrable :** `eq8_validator.py` + intégration dans `eq8_automation.py`

#### Fonctions

```python
def load_device_mapping(json_path: Path = None) -> dict:
    """Charge ableton_devices_mapping.json. Cherche dans le repo par défaut."""

def validate_band_config(mode: int, freq: float, gain: float, q: float, mapping: dict) -> list[str]:
    """Vérifie une config de bande AVANT écriture.
    
    Checks :
    - Mode valide (0-7)
    - Freq dans le range (10-22000 Hz)
    - Gain dans le range (-15 à +15 dB)
    - Q dans le range (0.1 à 18.0)
    - Gain sur mode avec gain_inoperative (0,1,4,6,7) → ERROR
    
    Returns: liste d'erreurs (vide = OK).
    Raise ValueError si erreur critique.
    """

def validate_automation_values(param_name: str, values: np.ndarray, mapping: dict) -> list[str]:
    """Vérifie les valeurs d'automation AVANT écriture.
    
    Checks :
    - Toutes les valeurs dans le range du paramètre
    - Valeurs non constantes (WARNING si toutes identiques — automation inutile)
    - Encodage correct (brut pour EQ8, confirmé par calibration)
    
    Returns: liste de warnings.
    """
```

#### Intégration

Au début de chaque fonction write_* dans eq8_automation.py :
```python
errors = validate_band_config(mode, freq, gain, q, MAPPING)
if errors:
    return AutomationReport(success=False, warnings=errors)
```

Le mapping JSON est chargé UNE FOIS au module load (pas à chaque appel).

#### Tests

1. Bell (mode 3) + gain -3 dB → OK
2. Notch (mode 4) + gain -3 dB → ERROR "Gain inoperant en mode Notch"
3. Freq = 50000 Hz → ERROR "hors range"
4. Automation Gain toutes à 0.0 → WARNING "automation constante"
5. Les 98+ tests existants passent (rétro-compatible)

**Commit :** `feat(eq8): add validation layer from device mapping JSON`

---

## Vue d'ensemble des phases

```
Session 0  — Durcissement moteur EQ8 + validation
PHASE 1    — Infrastructure projet (sessions 1-3.5)
PHASE 2    — Sections et priorités (sessions 4-7)
PHASE 3    — Correction conditionnelle (sessions 8-13)
PHASE 4    — Q dynamique (sessions 14-15)
PHASE 5    — Calibration devices dynamiques (sessions 16-17) ← UTILISATEUR
PHASE 6    — Stéréo et expansion (sessions 18-20)
PHASE 7    — Devices dynamiques (sessions 21-27)
PHASE 8    — Application et rapport (sessions 28-29)
```

---

# PHASE 1 — Infrastructure projet

## Objectif

Solidifier les fondations : persistance des décisions, identification des tracks, analyse incrémentale, séparation source/bus/full_mix.

---

### Session 1 — Persistance projet + corrections_config.json

**Contexte :** Chaque run repart de zéro. Les décisions ne persistent pas.

**Livrable :** module `project_config.py`

#### Fonctions

```python
def get_or_create_project_dir(als_path: Path) -> Path:
    """Crée projects/<nom_projet>/ si inexistant.
    Nom du projet = nom du .als sans suffixe de version.
    'Acid_drops_Code_P14.als' → projet 'Acid_drops_Code'
    """

def load_project_config(project_dir: Path) -> dict:
    """Charge corrections_config.json ou crée un config par défaut."""

def save_project_config(project_dir: Path, config: dict):
    """Sauvegarde le config JSON."""

def validate_config_against_als(config: dict, als_path: Path) -> dict:
    """Vérifie que les références du config matchent le .als actuel.
    Track names orphelins → flaggés, pas supprimés.
    als_hash changé → flaggé.
    """
```

#### Structure corrections_config.json

```json
{
  "project_name": "Acid_drops_Code",
  "als_source": "Acid_drops_Code_P14.als",
  "als_hash": "a3f8c2...",
  "created": "2026-04-17",
  "last_run": "2026-04-17",
  "genre": "Industrial",
  "character": 0.2,
  "track_roles": {},
  "track_types": {},
  "priority_overrides": {},
  "refused_corrections": [],
  "intensity_overrides": {},
  "wav_hashes": {},
  "_validation": {}
}
```

#### Tests

1. Premier run → config créé avec defaults
2. Deuxième run → config chargé, décisions persistées
3. `.als` renommé (P14 → P15) → même projet détecté
4. Track renommée → orphan flaggé
5. `.als` modifié (hash différent) → als_changed = true

**Commit :** `feat(project): add project persistence and corrections_config.json`

---

### Session 2 — Rôles de tracks + exclusion BUS/Full Mix

**Contexte :** Les BUS et le Full Mix polluent les calculs de masking et reçoivent des corrections inappropriées.

**Livrable :** modifications dans `project_config.py` + `mix_analyzer.py`

```python
def detect_track_roles(als_path: Path) -> dict[str, str]:
    """Détecte source/bus/full_mix depuis la structure du .als.
    GroupTrack, ReturnTrack → bus
    Nommé BUS*, Full Mix → correspondant
    Tout le reste → source
    """
```

Seules les tracks `source` participent aux calculs de masking, d'accumulation et de priorité.

#### Tests

1. BUS Kick → "bus", Kick 1 → "source", Full Mix → "full_mix"
2. Masking entre 2 sources → OK
3. Masking avec un bus → exclu automatiquement

**Commit :** `feat(project): detect and persist track roles`

---

### Session 3 — Analyse incrémentale + hash WAV

**Contexte :** Chaque run réanalyse 39 tracks (~2-3 min) même si rien n'a changé.

**Livrable :** modifications dans `mix_analyzer.py`

```python
def compute_wav_hash(wav_path: Path) -> str:
    """Hash MD5 rapide (premiers 1 MB + taille)."""

def should_reanalyze(wav_path: Path, config: dict) -> bool:
    """True si le WAV est nouveau ou modifié."""
```

Le rapport Excel précédent sert de cache — si le hash matche, les features sont lues depuis les sheets existants au lieu d'être recalculées.

#### Tests

1. Premier run → toutes analysées, hash stockés
2. Deuxième run sans changement → 0 réanalysées
3. Un WAV modifié → seulement cette track réanalysée

**Commit :** `feat(project): incremental analysis with WAV hash caching`

---

### Session 3.5 — Genre et character persistants

**Contexte :** L'utilisateur retape `--genre Industrial` à chaque run.

**Livrable :** intégration dans `project_config.py`

Premier run : `--genre` fourni ou suggestion automatique basée sur les features du full mix. Sauvé dans le config. Runs suivants : lu depuis le config.

```python
def suggest_genre(full_mix_features: dict) -> str:
    """Suggestion heuristique basée sur les features spectrales."""
```

**Commit :** `feat(project): persist genre and character in project config`

---

# PHASE 2 — Sections et priorités

## Objectif

Le système comprend la structure temporelle du morceau et assigne des priorités contextuelles.

---

### Session 4 — Lecture des Locators existants

**Livrable :** fonctions dans `als_utils.py`

```python
@dataclass
class Locator:
    time_beats: float
    time_seconds: float
    name: str
    is_user: bool       # True si placé par l'utilisateur (pas préfixé v3_)

def read_locators(als_path: Path) -> list[Locator]:
    """Lit les Locators du .als, triés par time. Distingue user vs générés."""
```

#### Tests

1. `.als` avec 3 Locators manuels → 3 lus, is_user=True
2. `.als` sans Locators → liste vide
3. Mix de manuels et v3_ → distingués

**Commit :** `feat(sections): read existing locators from .als`

---

### Session 5 — Détection automatique des sections

**Livrable :** nouveau module `section_detector.py`

```python
@dataclass
class Section:
    index: int
    label: str                      # INTRO, DROP, BREAK, BUILD, OUTRO, SECTION_N
    start_seconds: float
    end_seconds: float
    start_beats: float
    end_beats: float
    bucket_range: tuple[int, int]
    energy_profile: str             # high, medium, low, building, falling
    tracks_active: list[str]
    track_count: int
    source: str                     # user_locator ou auto_detected

def detect_sections(
    delta_spectrum, full_mix_zone_energy, times, tempo,
    existing_locators, sensitivity=2.5
) -> list[Section]:
    """Si Locators existants → sections depuis les Locators.
    Sinon → détection auto via delta_spectrum."""
```

#### Tests

1. Audio synthétique → sections détectées
2. Acid Drops → 4-8 sections
3. Locators manuels → sections depuis Locators, pas de détection auto

**Commit :** `feat(sections): auto-detect sections from delta_spectrum`

---

### Session 6 — Matrice de priorités par section

**Livrable :** fonctions dans `section_detector.py`

```python
@dataclass
class TrackPriority:
    track_name: str
    section_label: str
    priority: int           # 1 (haute) à 5 (basse)
    method: str             # auto:dominant_sub, auto:support, user_override
    energy_score: float

def compute_section_priorities(
    sections, all_tracks_zone_energy, track_types, track_roles,
    genre_profile, priority_overrides
) -> list[TrackPriority]:
    """Priorité contextuelle par section.
    
    Poids = énergie_max_zone × facteur_genre_track_type
    Top 10% → 1, 10-30% → 2, 30-60% → 3, 60-85% → 4, 85-100% → 5
    Track seule dans une zone → priorité 1
    Overrides utilisateur appliqués en dernier
    BUS et Full Mix exclus
    """
```

#### Tests

1. DROP avec Kick → Kick priorité 1
2. BREAK sans Kick, Pad dominant → Pad monte
3. Track seule dans Sub → priorité 1
4. Override utilisateur → respecté

**Commit :** `feat(sections): compute contextual priorities per section`

---

### Session 7 — Sheet _track_sections + intégration rapport

**Livrable :** modifications dans `feature_storage.py` + `mix_analyzer.py`

Sheet caché `_track_sections` — UN seul nouveau sheet :

**Partie haute :** info sections (label, source, start, end, energy, track count)
**Partie basse :** priorités (section × track × priority × method × override)

Pas de sheet `_track_copresence` séparé — la co-présence est calculée au runtime depuis `_track_zone_energy`.

#### Tests

1. Sheet créé avec sections et priorités
2. Overrides rechargés au prochain run
3. Pas de doublon data

**Commit :** `feat(sections): add _track_sections sheet to Excel report`

---

# PHASE 3 — Correction conditionnelle

## Objectif

Chaque correction est justifiée avant d'être écrite. La logique est **device-agnostic** — elle s'appliquera à l'EQ8 maintenant et aux Compressors/Gate plus tard.

---

### Session 8 — correction_logic.py : dataclasses + cascade de base

**Livrable :** nouveau module `correction_logic.py`

```python
@dataclass
class CorrectionContext:
    is_audible: np.ndarray
    zone_energy: np.ndarray
    content_threshold_db: float
    other_tracks_energy: dict[str, np.ndarray]
    masking_threshold: float
    track_mean_spectrum: np.ndarray | None
    isolated_threshold_db: float
    tracks_active_count: np.ndarray | None
    accumulation_threshold: int
    track_priority: int | None          # priorité DANS LA SECTION COURANTE
    sections: list | None
    current_section_index: int | None
    track_role: str
    require_justification: bool
    device_type: str                    # "eq8", "compressor", "gate", etc.

@dataclass
class JustificationResult:
    justified: bool
    flags: list[str]
    severity: float
    dynamic_mask: np.ndarray
    explanation: str

def evaluate_justification(
    track_name, track_type, correction_type, target_freq_hz,
    context, genre_profile
) -> JustificationResult:
    """Cascade device-agnostic :
    0. Role != source → skip
    1. Contenu < threshold → correction statique OK
    2. Masking cumulatif (1 vs tous) > seuil → correction dynamique
    3. Peak isolé extrême → correction
    4. Accumulation pondérée par énergie → correction sur basse priorité
    5. Aucun → skip
    """
```

**Point clé :** `device_type` dans le CorrectionContext permet à la même cascade de décider pour un EQ, un compresseur, ou un gate. Les critères changent selon le device (un compresseur n'a pas de "peak isolé") mais la structure est la même.

#### Tests (7 cas)

1-7 identiques au spec Feature 1 existant

**Commit :** `feat(correction): add correction_logic.py with device-agnostic justification`

---

### Session 9 — Mise à jour genre_profiles.json

**Livrable :** nouveaux champs par track_type

Ajouter `isolated_peak_threshold_db`, `content_threshold_db`, `priority_weight` à chaque track_type dans chaque style.

**Vérifier d'abord** si certains champs existent déjà dans le JSON — ne pas créer de doublons. Merger intelligemment.

Ajouter aussi une nouvelle section par track_type pour les devices dynamiques :

```json
{
  "Kick": {
    "existing_eq_fields": "...",
    "isolated_peak_threshold_db": 10,
    "content_threshold_db": -55,
    "priority_weight": 2.0,
    "dynamics": {
      "compression_style": "aggressive",
      "attack_ms_range": [5, 30],
      "release_ms_range": [50, 200],
      "ratio_range": [3, 8],
      "threshold_adapt_to_section": false,
      "preserve_transient": true,
      "parallel_compression": false,
      "gate_applicable": false,
      "notes": "Compression constante. Attack long pour laisser passer le transient."
    }
  },
  "Pad/Drone": {
    "dynamics": {
      "compression_style": "gentle",
      "attack_ms_range": [10, 50],
      "release_ms_range": [100, 500],
      "ratio_range": [2, 4],
      "threshold_adapt_to_section": true,
      "preserve_transient": false,
      "parallel_compression": true,
      "gate_applicable": false,
      "notes": "Compression section-aware. Plus actif dans les sections denses."
    }
  },
  "Tom": {
    "dynamics": {
      "compression_style": "moderate",
      "attack_ms_range": [5, 20],
      "release_ms_range": [50, 150],
      "ratio_range": [3, 6],
      "threshold_adapt_to_section": false,
      "preserve_transient": true,
      "parallel_compression": false,
      "gate_applicable": true,
      "gate_threshold_auto": true,
      "notes": "Gate pour nettoyer le bleed. Compression modérée préservant l'attaque."
    }
  },
  "Lead Vocal": {
    "dynamics": {
      "compression_style": "controlled",
      "attack_ms_range": [2, 15],
      "release_ms_range": [50, 200],
      "ratio_range": [3, 6],
      "threshold_adapt_to_section": true,
      "preserve_transient": false,
      "parallel_compression": true,
      "gate_applicable": false,
      "limiter_applicable": true,
      "notes": "Compression pour contrôler la dynamique. Limiter doux pour les peaks."
    }
  }
}
```

**Commit :** `feat(correction): add priority, threshold, and dynamics fields to genre_profiles.json`

---

### Session 10 — build_correction_context()

**Livrable :** fonction dans `correction_logic.py`

```python
def build_correction_context(
    track_name, target_zone, report_path, als_path,
    sections, current_section_index, genre_profile,
    project_config, device_type="eq8"
) -> CorrectionContext:
    """Construit un CorrectionContext depuis le rapport + le config.
    Lit zone_energy, automation_map, spectre moyen, sections, priorités.
    Filtre sur role == source pour other_tracks_energy.
    """
```

**Commit :** `feat(correction): build CorrectionContext from report and config`

---

### Session 11 — Intégration dans eq8_automation.py

**Livrable :** paramètre `context: CorrectionContext = None` ajouté à toutes les fonctions write_*

Si context fourni et require_justification → évaluer avant d'écrire. Si non justifié → return AutomationReport(success=False). La severity scale la réduction. Le dynamic_mask filtre les buckets.

#### Tests

1. Avec context justifié → correction écrite
2. Avec context non justifié → skip
3. Sans context → rétro-compatible
4. 98+ tests existants passent

**Commit :** `feat(correction): integrate CorrectionContext into all write_* functions`

---

### Session 12 — Budget de corrections + arbitrage

**Livrable :** fonctions dans `correction_logic.py`

```python
def allocate_eq8_budget(justified_corrections, max_bands=6):
    """Trie par severity, garde les top max_bands, refuse le reste."""
```

**Commit :** `feat(correction): add EQ8 band budget allocation`

---

### Session 13 — Distinction transient/sustain

**Livrable :** enrichissement de `evaluate_justification()`

Crest factor > 10 (transient dominant) → severity × 0.5
Crest factor < 5 (sustain dominant) → severity × 1.2

**Commit :** `feat(correction): weight justification by transient vs sustain`

---

# PHASE 4 — Q dynamique

---

### Session 14 — Bandwidth dans les peak trajectories

**Livrable :** modification `spectral_evolution.py` + `feature_storage.py`

Ajouter `bandwidth_hz` comme colonne dans `_track_peak_trajectories`. Calculé depuis la matrice CQT : bins adjacents au-dessus de peak_amplitude - 3 dB.

**Commit :** `feat(spectral): add bandwidth_hz to peak trajectories`

---

### Session 15 — Troisième envelope Q

**Livrable :** modification `eq8_automation.py`

Fonctions write_dynamic_notch, write_resonance_suppression, write_dynamic_bell_cut, write_dynamic_deesser écrivent 3 envelopes : Freq, Gain, Q.

Q = freq / bandwidth, clampé 0.5-18.0, rate-limited 2 unités/sec.

**Commit :** `feat(eq8): write dynamic Q automation as third envelope`

---

# PHASE 5 — Calibration des devices dynamiques

## Objectif

Mapper les paramètres des devices non encore documentés dans le JSON. Même méthode empirique que pour l'EQ8 : set de calibration avec valeurs connues → parser le XML → documenter les transforms.

**Cette phase requiert l'UTILISATEUR — pas du code.**

---

### Session 16 — Calibration Compressor2 et Gate

**Action utilisateur :**

Créer `calibration_dynamics.als` dans Ableton avec :

**Track 1 — Compressor2 avec valeurs connues :**
- Threshold : -20 dB
- Ratio : 4:1
- Attack : 10 ms
- Release : 100 ms
- Knee : 6 dB
- Dry/Wet : 50%
- Makeup : +3 dB
- Model : Peak (ou RMS si dispo)
- Dessiner une automation Threshold : -30 → -10 → -20 dB
- Dessiner une automation Ratio : 2 → 6 → 4
- Dessiner une automation Dry/Wet : 0% → 100% → 50%

**Track 2 — Gate avec valeurs connues :**
- Threshold : -30 dB
- Return : -40 dB
- Attack : 0.1 ms
- Hold : 50 ms
- Release : 50 ms
- Floor : -80 dB
- Dessiner une automation Threshold : -40 → -20 → -30 dB
- Dessiner une automation Floor : -inf → -40 → -80 dB

**Track 3 — MultibandDynamics avec valeurs connues :**
- Band Low : Below Threshold -20, Above Threshold -10, Ratio Below 1:2, Ratio Above 3:1
- Band Mid : idem avec d'autres valeurs
- Band High : idem
- Crossover Low : 200 Hz, Crossover High : 2500 Hz
- Amount : 100%
- Dessiner des automations sur Threshold et Amount

**Sauvegarder** sous `calibration_dynamics.als` et uploader.

**Action Claude Code :**

Parser le `.als`, extraire les valeurs XML, comparer aux valeurs Ableton, documenter les transforms dans `ableton_devices_mapping.json`.

```python
# Script de calibration
def calibrate_device(als_path, device_name, known_values):
    """Compare valeurs XML vs valeurs connues, génère le mapping."""
```

#### Livrables

Sections ajoutées dans `ableton_devices_mapping.json` :

```json
{
  "Compressor2": {
    "display_name": "Compressor",
    "status": "complete",
    "params": {
      "Threshold": {"transform_kind": "direct", "unit_live": "dB", "range_xml": [-inf, 0]},
      "Ratio": {"transform_kind": "...", "range_xml": [1, inf]},
      "Attack": {"transform_kind": "...", "unit_live": "ms"},
      "Release": {"transform_kind": "...", "unit_live": "ms"},
      "DryWet": {"transform_kind": "...", "range_xml": [0, 1]},
      "GainCompensation": {"transform_kind": "...", "unit_live": "dB"}
    }
  },
  "Gate": { "..." },
  "MultibandDynamics": { "..." }
}
```

**Commit :** `feat(mapping): calibrate Compressor2, Gate, MultibandDynamics`

---

### Session 17 — Validation du mapping dynamique

**Action Claude Code :**

Créer un set de test avec d'autres valeurs, re-parser, vérifier que le mapping decode correctement. Même méthode de validation que pour l'EQ8.

**Commit :** `test(mapping): validate dynamics device mapping accuracy`

---

# PHASE 6 — Stéréo et expansion EQ

---

### Session 18 — Écriture des Locators dans le .als

**Livrable :** fonction dans `als_utils.py`

```python
def write_section_locators(als_path, sections, prefix="v3_", overwrite_prefixed=True):
    """Écrit des Locators. Ne touche JAMAIS les Locators sans préfixe v3_."""
```

**Commit :** `feat(sections): write section locators to .als`

---

### Session 19 — EQ8 M/S (deuxième instance)

**Livrable :** `find_or_create_ms_eq8()` + fonctions write_ms_*

3 fonctions : `write_ms_side_cut()`, `write_ms_mid_cut()`, `write_ms_side_boost()`
ParameterA = Mid, ParameterB = Side.
Justification via CorrectionContext (phase correlation, width).

**Commit :** `feat(eq8): add M/S EQ8 corrections`

---

### Session 20 — Utility width adaptatif

**Livrable :** nouveau `utility_automation.py`

```python
def write_adaptive_width(als_path, track_id, width_curve, phase_curve, 
                         section_density, times, context=None):
    """Width rétréci dans sections denses, élargi dans calmes.
    Sub Bass → toujours mono. Phase négative → width réduit."""
```

Mapping StereoGain déjà complet (15 params).

**Commit :** `feat(utility): add adaptive width automation`

---

# PHASE 7 — Devices dynamiques

## Objectif

Étendre l'automation contextuelle aux compresseurs, limiteur, gate et multiband dynamics. Chaque device suit le même pattern : justification via CorrectionContext → calcul des paramètres adaptatifs → écriture des envelopes.

**Dépend de :** Phase 5 (calibration) + Phase 3 (correction conditionnelle)

---

### Session 21 — DeviceAutomator (abstraction commune)

**Contexte :** Le code EQ8 duplique la logique de backup → parse → find track → find device → validate → write → save. Chaque nouveau device va la re-dupliquer. Il faut une abstraction.

**Livrable :** nouveau `device_automator.py`

```python
class DeviceAutomator:
    """Classe de base pour automatiser n'importe quel device Ableton."""
    
    def __init__(self, device_tag: str, mapping: dict):
        """device_tag = 'Eq8', 'Compressor2', 'Gate', etc."""
        self.device_tag = device_tag
        self.mapping = mapping
    
    def find_or_create(self, tree, track) -> ET.Element:
        """Trouve le device sur la track, ou le crée avec les defaults du mapping."""
    
    def get_param_element(self, device, param_name) -> ET.Element:
        """Récupère un sous-élément de paramètre."""
    
    def get_automation_target_id(self, param_element) -> str:
        """Récupère le AutomationTarget Id."""
    
    def validate_value(self, param_name, value) -> bool:
        """Vérifie range et transform depuis le mapping."""
    
    def prepare(self, als_path, track_id):
        """Backup, parse, find track, find/create device. Retourne le context d'écriture."""
    
    def write_param_automation(self, param_name, breakpoints, context=None):
        """Écrit une envelope d'automation pour un paramètre, avec validation."""
    
    def finalize(self, output_path=None):
        """Sauvegarde le .als modifié."""
```

Les fonctions write_* existantes dans eq8_automation.py peuvent être **progressivement migrées** vers DeviceAutomator, mais ce n'est pas obligatoire pour cette session. L'abstraction est d'abord utilisée par les nouveaux devices.

#### Tests

1. DeviceAutomator("Eq8", mapping) → find_or_create fonctionne
2. DeviceAutomator("Compressor2", mapping) → idem
3. validate_value("Threshold", -25.0) → OK
4. validate_value("Threshold", 999.0) → ERROR

**Commit :** `feat(devices): add DeviceAutomator base class`

---

### Session 22 — Compressor2 : compression section-aware

**Contexte :** La compression doit s'adapter à la section. Dans le drop (dense), threshold plus bas (compression active). Dans le break (calme), threshold plus haut (respirer). L'attack préserve les transients sur les drums.

**Livrable :** nouveau `compressor_automation.py`

```python
def write_section_compression(
    als_path: Path,
    track_id: str,
    crest_by_zone: dict[str, np.ndarray],  # crest factor par zone × buckets
    section_density: np.ndarray,            # nombre de tracks actives par bucket
    sections: list[Section],
    times: np.ndarray,
    track_type: str,
    genre_profile: dict,
    context: CorrectionContext = None,
) -> AutomationReport:
    """Compression adaptative par section.
    
    Paramètres automatisés :
    - Threshold : calculé depuis crest factor moyen de la section
      Section dense → threshold bas (plus de compression)
      Section calme → threshold haut (moins de compression)
    - Attack : depuis genre_profile[track_type].dynamics.attack_ms_range
      preserve_transient=true → attack long (laisser passer l'attaque)
    - Release : adapté au tempo (release = 60000/BPM × facteur)
    - Dry/Wet : plus de wet dans les sections denses (compression parallèle si applicable)
    
    Paramètres NON automatisés (statiques depuis le genre profile) :
    - Ratio : fixe pour le track type
    - Knee : fixe
    - Model : fixe (Peak pour drums, RMS pour pads/vocaux)
    
    Justification :
    - Si crest factor constant entre sections → pas de compression adaptative
    - Si compression_style = "none" dans le genre profile → skip
    """
```

```python
def write_parallel_compression(
    als_path: Path,
    track_id: str,
    sections: list[Section],
    times: np.ndarray,
    genre_profile: dict,
    wet_range: tuple[float, float] = (0.3, 0.7),
    context: CorrectionContext = None,
) -> AutomationReport:
    """Dry/Wet du compresseur adapté par section.
    Section dense → plus de wet (plus de colle)
    Section calme → moins de wet (plus de dynamique)
    """
```

#### Justification intégrée

Le compresseur utilise le même CorrectionContext que l'EQ8 :
- `context.require_justification = True` → vérifier que la compression est nécessaire
- Critère principal : variation du crest factor entre sections > seuil
- Si le crest est constant → la dynamique est déjà uniforme, pas besoin de compression adaptative
- Track type avec `threshold_adapt_to_section: false` (ex: Kick) → compression statique, pas d'automation

#### Tests

1. Pad avec crest qui varie (6 dB intro, 12 dB drop) → threshold adaptatif
2. Kick avec crest constant → pas de modification
3. Track type avec compression_style = "none" → skip
4. Dry/Wet augmente dans les sections denses
5. Attack respecte le range du genre profile

**Commit :** `feat(compressor): add section-aware compression automation`

---

### Session 23 — GlueCompressor : bus compression section-aware

**Contexte :** Le GlueCompressor est utilisé sur les bus (drums, instruments) et le master pour coller les éléments. Ses paramètres devraient s'adapter à la section comme le Compressor2.

**Livrable :** fonctions dans `compressor_automation.py` (même module)

```python
def write_glue_compression(
    als_path: Path,
    track_id: str,                       # typiquement un bus
    bus_total_energy: np.ndarray,        # énergie totale du bus par bucket
    sections: list[Section],
    times: np.ndarray,
    genre_profile: dict,
    context: CorrectionContext = None,
) -> AutomationReport:
    """GlueCompressor adaptatif sur un bus.
    
    Paramètres automatisés :
    - Threshold : suit l'énergie du bus (monte dans les sections calmes, descend dans les denses)
    - Dry/Wet : plus de colle dans les sections denses
    - Range : limité dans les sections très denses (empêcher la sur-compression)
    
    Paramètres statiques :
    - Ratio : depuis le genre profile (2:1 pour subtil, 4:1 pour agressif)
    - Attack : depuis le genre profile (plus lent sur bus drums)
    
    Sidechain EQ :
    - Si sidechain_eq_on dans le genre profile : HPF le sidechain pour que
      le sub ne trigger pas la compression du bus. Freq adaptative.
    
    Note : cette fonction s'applique aux tracks avec role='bus'.
    C'est une EXCEPTION au principe "ne pas corriger les bus" — 
    la compression de bus est une opération de mix standard, pas une correction.
    """
```

#### Justification

- Pas la même cascade que les sources. Les bus sont corrigés si `bus_compression_enabled: true` dans le genre profile.
- Le critère est la variation d'énergie du bus entre sections : si uniforme → pas besoin.

#### Tests

1. BUS Drums avec énergie variable → threshold adaptatif
2. BUS avec énergie constante → pas de modification
3. Sidechain EQ HPF adaptatif si activé dans le profile
4. Range limité dans les sections les plus denses

**Commit :** `feat(compressor): add bus GlueCompressor automation`

---

### Session 24 — Limiter : protection et loudness

**Contexte :** Le Limiter est le dernier rempart avant le clipping. Sur les tracks individuelles, il protège contre les peaks. Sur le master, il contrôle le loudness final.

**Livrable :** fonctions dans un nouveau `limiter_automation.py`

```python
def write_adaptive_limiter(
    als_path: Path,
    track_id: str,
    peak_levels: np.ndarray,             # peak dBFS par bucket
    target_lufs: float,                   # cible de loudness
    sections: list[Section],
    times: np.ndarray,
    genre_profile: dict,
    context: CorrectionContext = None,
) -> AutomationReport:
    """Limiter avec gain adaptatif par section.
    
    Paramètres automatisés :
    - Gain : pousse plus dans les sections calmes pour uniformiser le loudness
    - Ceiling : fixe (-0.3 dBTP pour mastering, -1.0 pour mix)
    
    Paramètre statique :
    - Release : Auto (Ableton gère bien)
    
    Usage principal :
    - Master bus : uniformiser le loudness entre sections
    - Tracks individuelles avec peaks extrêmes : protéger sans compresser
    
    Justification :
    - Si les peaks sont déjà sous le ceiling → pas de limitation nécessaire
    - Si le loudness est déjà uniforme entre sections → gain constant
    """
```

#### Tests

1. Master avec sections de loudness variable → gain adaptatif
2. Track avec peaks sous le ceiling → skip
3. Ceiling respecte le genre profile (-0.3 dBTP mastering, -1.0 mix)

**Commit :** `feat(limiter): add adaptive limiter automation`

---

### Session 25 — Gate : nettoyage dynamique des drums

**Contexte :** Les tracks de drums live (toms, overheads) ont du bleed entre les coups. Un gate qui s'ouvre sur le signal voulu et se ferme sur le bleed.

**Livrable :** nouveau `gate_automation.py`

```python
def write_adaptive_gate(
    als_path: Path,
    track_id: str,
    transient_events: list,              # depuis _track_transients
    inter_transient_energy: np.ndarray,  # énergie entre les transients
    signal_energy: np.ndarray,           # énergie pendant les transients
    sections: list[Section],
    times: np.ndarray,
    genre_profile: dict,
    context: CorrectionContext = None,
) -> AutomationReport:
    """Gate adaptatif pour nettoyer le bleed.
    
    Paramètres automatisés :
    - Threshold : calibré entre signal et bleed
      threshold = (signal_energy + inter_transient_energy) / 2
      Adapté par section (break = plus ouvert, drop = plus strict)
    - Floor : -inf pour du gating dur (drums percussifs), 
              -20 dB pour de l'expansion douce (toms avec sustain voulu)
    - Hold : adapté à la durée moyenne des coups dans la section
    - Release : plus long dans les sections calmes (sustain naturel)
    
    Paramètres statiques :
    - Attack : très court (< 1ms) pour ne pas couper les transients
    - Return : threshold - 6 dB (hysteresis standard)
    
    Justification :
    - gate_applicable doit être true dans le genre profile pour ce track type
    - Il faut des transients détectés ET de l'énergie inter-transient significative
    - Si le bleed est < -60 dB → pas de gate nécessaire
    """
```

#### Tests

1. Toms Rack avec 20 transients et bleed -45 dB → gate calibré
2. Track sans transients → skip
3. Bleed < -60 dB → skip (pas de bleed significatif)
4. Break → gate plus ouvert (threshold plus bas)
5. gate_applicable: false → skip

**Commit :** `feat(gate): add adaptive gate automation for drums`

---

### Session 26 — MultibandDynamics : mastering dynamique

**Contexte :** Le compresseur multiband est l'outil le plus puissant pour le mastering. Il divise le spectre en 3 bandes et applique compression + expansion indépendamment. Permet du tonal shaping dynamique.

**Livrable :** nouveau `multiband_automation.py`

```python
def write_multiband_dynamics(
    als_path: Path,
    track_id: str,                       # typiquement le master ou un bus
    zone_energy_by_band: dict,           # énergie par bande (low/mid/high) × buckets
    sections: list[Section],
    times: np.ndarray,
    target_balance: dict,                # balance spectrale cible depuis genre profile
    genre_profile: dict,
    context: CorrectionContext = None,
) -> AutomationReport:
    """MultibandDynamics adaptatif.
    
    Paramètres automatisés :
    - Threshold Above (compression) par bande :
      Si l'énergie de la bande dépasse la balance cible → compression
      Plus agressif dans les sections denses
    - Threshold Below (expansion) par bande :
      Si l'énergie tombe sous un plancher → expansion (nettoyage)
    - Output Gain par bande :
      Balance spectrale cible — le vrai tonal shaping
      Si trop de basses dans le drop → réduire Output Low
      Si pas assez d'air dans le break → augmenter Output High
    - Amount :
      Dosage global — plus actif dans les sections denses
    
    Paramètres statiques :
    - Crossover frequencies : depuis le genre profile
      Industrial : Low/Mid = 200 Hz, Mid/High = 2500 Hz
    - Ratios : depuis le genre profile
    
    Justification :
    - Si la balance spectrale est déjà dans la cible → skip
    - Si l'énergie par bande est uniforme entre sections → amount constant
    """
```

#### Données nécessaires

La zone_energy existe déjà dans les features v2.5. Les 9 zones sont mappées sur 3 bandes MultibandDynamics :
- Low = Sub + Low (20-250 Hz)
- Mid = Mud + Body + Low-Mid + Mid (200-4000 Hz)
- High = Presence + Sibilance + Air (2000-20000 Hz)

#### Tests

1. Master avec déséquilibre spectral → output gain par bande adaptatif
2. Section DROP trop de basses → compression Low activée
3. Balance déjà correcte → skip
4. Amount augmente dans les sections denses

**Commit :** `feat(multiband): add adaptive multiband dynamics automation`

---

### Session 27 — Tests d'intégration devices dynamiques

**Livrable :** tests d'intégration sur un `.als` réel

```python
# Smoke test dynamiques
# 1. Compressor sur Acid Bass → threshold adaptatif entre sections
# 2. GlueCompressor sur BUS Drums → dry/wet section-aware
# 3. Gate sur Toms Rack → nettoyage du bleed
# 4. Limiter sur Master → gain adaptatif pour loudness uniforme
# 5. MultibandDynamics sur Master → balance spectrale
```

Chaque test vérifie :
- Le device est créé dans le `.als` avec la bonne structure
- Les automations ont des valeurs non-constantes
- Les valeurs sont dans le range du mapping
- La justification est respectée (pas de correction inutile)

**Commit :** `test(dynamics): integration tests for all dynamic devices`

---

# PHASE 8 — Application et rapport

---

### Session 28 — Script d'application unifié

**Livrable :** `apply_corrections.py`

```bash
python apply_corrections.py --als Acid_drops.als --report report.xlsx
```

Le script :
1. Charge le projet (corrections_config.json — genre, rôles, types, refus)
2. Charge le rapport + le `.als`
3. Détecte les sections et calcule les priorités
4. Pour chaque track source :
   - Construit le CorrectionContext
   - Évalue la justification pour chaque correction possible :
     - EQ8 : HPF, LPF, notches, boosts
     - Compressor : compression section-aware
     - Gate : si applicable au track type
   - Applique les corrections justifiées (budget EQ8 respecté)
5. Pour les bus :
   - GlueCompressor si bus_compression_enabled
6. Pour le master :
   - Limiter adaptatif
   - MultibandDynamics si activé
7. Écrit le `.als` corrigé (`_corrected.als`)
8. Met à jour corrections_config.json
9. Print un résumé

**Commit :** `feat(apply): unified correction application script`

---

### Session 29 — Rapport de corrections

**Livrable :** rapport détaillé (Markdown ou sheet Excel)

```markdown
# Rapport — Acid Drops v14
# Genre: Industrial | Character: 0.2

## EQ8 (32 corrections)
  ✅ Toms Rack | Notch 248 Hz -1.8 dB Q=9.3 | masking:Acid Bass (DROP)
  ⏭ Acid Bass | Notch 248 Hz | skip: haute priorité, pas de conflit

## Compression (8 corrections)
  ✅ Acid Bass | Threshold -18→-25 dB (DROP denser) | crest variation 6 dB
  ⏭ Kick 1 | skip: crest constant, pas besoin d'adaptation

## Gate (2 corrections)
  ✅ Toms Rack | Gate threshold -35 dB | 20 transients, bleed -42 dB

## Bus compression (2 corrections)
  ✅ BUS Drums | Glue threshold adaptatif, Dry/Wet 40%→65%

## Master (1 correction)
  ✅ Master | Limiter gain +2 dB BREAK, +0 dB DROP
  
## Refusé (config) (1)
  ❌ Acid Bass 248 Hz | refusé 2026-04-17: résonance voulue
```

**Commit :** `feat(apply): generate correction report`

---

# Annexes

## Consolidation des sheets

| Sheet | Version | Modifié ? | Nouveau ? |
|---|---|---|---|
| 6 sheets v2.4 | v2.4 | Non | Non |
| 6 sheets v2.5 | v2.5 | `_track_peak_trajectories` +1 colonne (bandwidth) | Non |
| `_track_automation_map` | v2.5.1 | Non | Non |
| **`_track_sections`** | **v3.1** | — | **OUI — seul nouveau** |

**14 sheets cachés total. 1 seul nouveau.**

## Nouveaux modules Python (7)

| Module | Phase | Responsabilité |
|---|---|---|
| `eq8_validator.py` | Session 0 | Validation des valeurs contre le mapping |
| `project_config.py` | Phase 1 | Persistance projet |
| `section_detector.py` | Phase 2 | Détection sections + priorités |
| `correction_logic.py` | Phase 3 | Cerveau de justification (device-agnostic) |
| `device_automator.py` | Phase 7 | Abstraction commune pour tous les devices |
| `compressor_automation.py` | Phase 7 | Compressor2 + GlueCompressor |
| `limiter_automation.py` | Phase 7 | Limiter |
| `gate_automation.py` | Phase 7 | Gate |
| `multiband_automation.py` | Phase 7 | MultibandDynamics |
| `utility_automation.py` | Phase 6 | Utility width |
| `apply_corrections.py` | Phase 8 | Script d'application unifié |

## Calibration requise (action utilisateur)

| Device | Params dans le JSON | Action |
|---|---|---|
| Eq8 | ✅ Complet | Rien |
| StereoGain (Utility) | ✅ 15 params | Rien |
| GlueCompressor | ✅ 9 params | Rien |
| Limiter | ✅ 13 params | Rien |
| **Compressor2** | ❌ 0 params | **Calibration Phase 5** |
| **Gate** | ❌ 0 params | **Calibration Phase 5** |
| **MultibandDynamics** | ❌ Non listé | **Calibration Phase 5** |

## Total estimé

| Phase | Sessions | Effort |
|---|---|---|
| Session 0 | 1 | Faible |
| Phase 1 | 3.5 | Moyen |
| Phase 2 | 4 | Moyen |
| Phase 3 | 6 | Gros |
| Phase 4 | 2 | Faible |
| Phase 5 | 2 | Utilisateur + faible |
| Phase 6 | 3 | Moyen |
| Phase 7 | 7 | Gros |
| Phase 8 | 2 | Moyen |
| **Total** | **~30 sessions** | |
