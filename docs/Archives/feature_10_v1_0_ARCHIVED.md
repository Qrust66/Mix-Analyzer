> **⚠️ ARCHIVÉ** — cette version (v1.0) a été remplacée par
> `docs/Features/feature_10_high_resolution_spectral_engine_v1_1.md`
> après le Pass 2 audit du 2026-05-02 qui a relevé 5 disconnects
> critiques entre la spec et le code Mix Analyzer v2.7.0 réel
> (notamment : pipeline CQT non couvert, paradigme `peak_threshold_db`
> incompatible, "standard preset = v2.7.0 équivalent" impossible avec
> une seule config).
>
> Préservation intégrale de v1.0 ci-dessous pour traçabilité historique.

---

# Feature 10 — High-Resolution Spectral Engine

**Version spec :** 1.0
**Date dernière modification :** 2026-04-23
**Statut :** Planifiée, non démarrée — architecture validée par Alexandre 2026-04-23 soir
**Hérite de :** `documentation_discipline.md` (règles de rédaction), `qrust_professional_context.md` (philosophie 100% dynamique justifiant le besoin de haute résolution)
**Brief méthodologique de référence :** `mix_engineer_brief_v2_3.md`
**Feature parent dans la roadmap :** voir `roadmap_features_1_8_v2_1.md` (priorité absolue, précède F1 pilote)
**Dépendances technique :** Mix Analyzer v2.7.0 livré ✅

**Historique d'évolution de la spec :**
- v1.0 — création initiale (2026-04-23 soir). Trigger : question d'Alexandre sur la résolution du rapport Excel face aux attentes de haute qualité. Analyse des données réelles du rapport Acid Drops : résolution temporelle 166 ms (2.82 frames/beat à 128 BPM), résolution spectrale non uniforme (~2.5 Hz dans graves, ~600 Hz dans l'air). Cible : résolution temporelle >4 frames/beat + résolution spectrale uniforme sur tout le spectre. Architecture validée : presets de résolution + threshold configurable + double rapport (full + shareable).

**Principe de préservation :** cette spec est la version initiale. Toute évolution suivra `documentation_discipline.md` section 4.

**Effort estimé :** 10h-14h Claude Code, ~40-55 tests, 14 micro-commits (7 code + 7 tests, séparés pour anti-timeout).

**Note de priorité :** Feature 10 est en **priorité absolue** dans la roadmap. Elle doit être livrée avant le pilote F1 sur Bass Rythm (reporté en attente). Raison : pilote F1 sur résolution insuffisante serait une validation biaisée.

---

## 1 — Objectif et justification

### 1.1 Problème identifié

L'audit de résolution du rapport Mix Analyzer actuel (v2.7.0) sur Acid Drops révèle deux limitations structurelles :

**Limitation 1 — Résolution temporelle insuffisante**
- Hop size actuel : ~166 ms par frame
- À 128 BPM : 2.82 frames par beat
- **Cible utilisateur : > 4 frames par beat**
- Impact : les transients courts (< 150 ms) peuvent passer entre deux frames, réduisant la précision du peak detection pour les éléments rythmiques

**Limitation 2 — Résolution spectrale non uniforme**
- Quantification logarithmique : ~1/2 semitone par bin
- Précision réelle : ±2.5 Hz dans les graves (excellent), ±600 Hz dans l'air 8-20 kHz (médiocre)
- **Cible utilisateur : résolution uniforme sur tout le spectre**
- Impact : les corrections dans les hautes fréquences (présence, air, de-essing) manquent de précision. La philosophie Qrust "tout passe par EQ8 + automation piloté par Mix Analyzer" exige précision homogène.

### 1.2 Ancrage dans la philosophie Qrust

Cette feature est **directement alignée avec la philosophie documentée dans `qrust_professional_context.md` section 4** :

- **100% dynamique par défaut** exige précision suffisante pour distinguer peaks contextuels
- **EQ Eight + automation** remplace les plugins commerciaux (Pro-Q 4 Dynamic, soothe2, Gullfoss) qui opèrent en interne à haute résolution
- **Transparence totale** : pour que Claude Code puisse piloter EQ8 aussi précisément que Pro-Q 4 Dynamic opère, Mix Analyzer doit fournir les données à résolution équivalente

### 1.3 Ce que fait la feature

Refactor le moteur d'analyse spectrale du Mix Analyzer pour :

1. **Exposer un paramètre `resolution`** avec 5 presets (economy, standard, fine, ultra, maximum)
2. **Exposer un paramètre `peak_threshold_db`** indépendant (défaut -70 dBFS, configurable -40 à -80)
3. **Adopter N_FFT = 16384 pour les presets fine/ultra/maximum** (au lieu de 8192 actuel) — résolution spectrale uniforme 2.69 Hz
4. **Générer deux rapports en parallèle** : FULL (sans limite de taille, usage local + Claude Code) + SHAREABLE (< 25 MB, upload vers Claude.ai)
5. **Ajuster dynamiquement le threshold du rapport shareable** pour garantir la contrainte de taille, indépendamment de la complexité du projet

### 1.4 Ce que la feature ne fait PAS (scope)

- Ne modifie pas les diagnostics CDE existants (ils bénéficient automatiquement via upstream)
- Ne change pas le format des sheets Excel (juste plus de lignes / meilleure précision des valeurs)
- Ne recalcule pas rétroactivement les rapports existants
- Ne fait pas de suggestion automatique de preset (contrôle manuel Alexandre, validé 2026-04-23)

### 1.5 Backward compatibility

Les rapports générés par Mix Analyzer v2.7.0 restent lisibles. Les anciens scripts qui consomment les sheets `_track_peak_trajectories` etc. fonctionnent de manière identique. Le nouveau moteur ajoute des colonnes metadata dans l'Index sheet pour identifier la résolution utilisée (preset + threshold).

---

## 2 — Presets de résolution

### 2.1 Définitions

Les 5 presets couvrent une gamme de besoins, du rapide/léger au détaillé/lourd.

**Constants module-level (dans `mix_analyzer/resolution_presets.py`) :**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ResolutionPreset:
    """Configuration d'un preset de résolution."""
    name: str
    hop_samples: int      # à 44.1 kHz
    n_fft: int
    description: str
    frames_per_beat_128: float
    delta_freq_hz_at_441khz: float

RESOLUTION_PRESETS = {
    "economy": ResolutionPreset(
        name="economy",
        hop_samples=10240,    # ~232 ms @ 44.1 kHz
        n_fft=8192,
        description="Analyse rapide pour projets longs ou itérations fréquentes",
        frames_per_beat_128=2.02,
        delta_freq_hz_at_441khz=5.38,
    ),
    "standard": ResolutionPreset(
        name="standard",
        hop_samples=7320,     # ~166 ms @ 44.1 kHz (équivalent Mix Analyzer v2.7.0)
        n_fft=8192,
        description="Configuration par défaut confortable, compatible rapports v2.7.0",
        frames_per_beat_128=2.82,
        delta_freq_hz_at_441khz=5.38,
    ),
    "fine": ResolutionPreset(
        name="fine",
        hop_samples=5120,     # ~116 ms @ 44.1 kHz
        n_fft=16384,
        description="Validation soignée, premier niveau haute résolution",
        frames_per_beat_128=4.04,
        delta_freq_hz_at_441khz=2.69,
    ),
    "ultra": ResolutionPreset(
        name="ultra",
        hop_samples=4410,     # 100 ms @ 44.1 kHz (pile 100ms)
        n_fft=16384,
        description="Session pilote F1, corrections de précision, usage production",
        frames_per_beat_128=4.69,
        delta_freq_hz_at_441khz=2.69,
    ),
    "maximum": ResolutionPreset(
        name="maximum",
        hop_samples=2560,     # ~58 ms @ 44.1 kHz
        n_fft=16384,
        description="Debug, analyse micro, cas d'exception (lourd)",
        frames_per_beat_128=8.08,
        delta_freq_hz_at_441khz=2.69,
    ),
}

DEFAULT_RESOLUTION_PRESET = "standard"  # Rétrocompatibilité avec v2.7.0
```

### 2.2 Scaling avec sample rate

Les presets sont définis à 44.1 kHz de référence. Si le projet Ableton utilise un autre sample rate (48 kHz, 88.2 kHz, 96 kHz), le hop en samples reste fixe mais le temps en ms se décale :

```python
def get_effective_hop_ms(preset: ResolutionPreset, sample_rate: int) -> float:
    """Retourne le hop en ms pour un sample rate donné."""
    return preset.hop_samples / sample_rate * 1000

def get_effective_delta_freq(preset: ResolutionPreset, sample_rate: int) -> float:
    """Retourne la résolution spectrale pour un sample rate donné."""
    return sample_rate / preset.n_fft
```

À 48 kHz : preset `ultra` produit hop 92 ms (au lieu de 100 ms) et Δf 2.93 Hz (au lieu de 2.69 Hz). Différence marginale, acceptable.

### 2.3 Paramètres windowing

Pour tous les presets, window = `hann` par défaut (cohérent avec pratique actuelle Mix Analyzer).

Overlap = `1 - hop_samples/n_fft` :
- economy : 1 - 10240/8192 = **-25%** (impossible, samples > fenêtre — doit être ajusté)
- standard : 1 - 7320/8192 = 11% (proche "no overlap")
- fine : 1 - 5120/16384 = 69%
- ultra : 1 - 4410/16384 = 73%
- maximum : 1 - 2560/16384 = 84%

**Problème identifié en v1.0 (clarifié dans spec) :** preset `economy` a hop > n_fft, ce qui n'est pas un cas valide en STFT. **Correction :** ajuster economy à `hop=8192, n_fft=8192` (overlap 0%, hop 186 ms) ou `hop=6144, n_fft=8192` (overlap 25%, hop 139 ms). À valider avant dev.

**Décision par défaut :** economy passe à `hop=6144, n_fft=8192` → 139 ms, 2.37 frames/beat, overlap 25%. Mise à jour des valeurs en section 2.1 lors du dev.

---

## 3 — Threshold de peak detection

### 3.1 Définition

Paramètre `peak_threshold_db` indépendant du preset de résolution. Contrôle le seuil minimum d'amplitude pour qu'un peak spectral soit enregistré dans `_track_peak_trajectories`.

**Valeurs :**
- **Min :** -80 dBFS (très permissif, capture tout ce qui est techniquement détectable)
- **Max :** -40 dBFS (très sélectif, seulement les peaks très présents)
- **Défaut :** -70 dBFS (équivalent Mix Analyzer v2.7.0)

### 3.2 Impact sur le volume des rapports

Plus le threshold est bas (-80), plus il y a de peaks stockés → rapport plus volumineux.
Plus le threshold est haut (-40), moins il y a de peaks → rapport plus léger.

**Justification musicale des valeurs par défaut :**
- **-70 dBFS :** capture peaks inaudibles individuellement mais qui peuvent participer à des accumulations multi-track → défaut prudent
- **-60 dBFS :** peaks généralement inaudibles en contexte mix → défaut rapport shareable (auto)
- **-55 dBFS :** peaks audibles en écoute solo mais masqués dans mix dense → shareable agressif
- **-50 dBFS :** peaks clairement audibles → shareable ultra-agressif
- **-40 dBFS :** peaks dominants → debug uniquement

### 3.3 Paramètre CLI

```bash
--peak-threshold -70    # défaut
--peak-threshold -60    # plus léger
--peak-threshold -55    # léger
```

### 3.4 Paramètre Python

```python
peak_threshold_db=-70  # défaut
```

---

## 4 — Architecture double rapport

### 4.1 Rapport FULL

**Caractéristiques :**
- Threshold utilisateur (par défaut -70 dBFS)
- Tous les peaks/valleys détectés préservés
- Taille illimitée (peut atteindre 50-100+ MB pour projets complexes)
- Usage : **local Alexandre + Claude Code** (pas uploadé vers Claude.ai)

**Naming :**
```
<project_name>_MixAnalyzer_<YYYY-MM-DD_HH-MM>_<preset>_full.xlsx
```

Exemples :
- `Acid_Drops_MixAnalyzer_2026-04-24_14-30_ultra_full.xlsx`
- `Acid_Drops_MixAnalyzer_2026-04-24_14-30_fine_full.xlsx`

### 4.2 Rapport SHAREABLE

**Caractéristiques :**
- Auto-généré en parallèle du rapport FULL (même pass d'analyse, filtrage en post)
- **Threshold dynamiquement ajusté** pour garantir taille < 25 MB
- Algorithme d'ajustement (section 4.3)
- Usage : **upload vers Claude.ai** pour sessions conversationnelles

**Naming :**
```
<project_name>_MixAnalyzer_<YYYY-MM-DD_HH-MM>_<preset>_shareable.xlsx
```

### 4.3 Algorithme d'ajustement dynamique du threshold

**Objectif :** garantir taille < 25 MB pour le rapport shareable, indépendamment de la complexité du projet.

**Algorithme :**

```python
def generate_shareable_report(
    full_data: MixAnalyzerData,
    target_size_mb: float = 25.0,
    initial_threshold_db: float = -60.0,
) -> tuple[Path, float]:
    """
    Génère le rapport shareable avec threshold dynamiquement ajusté.
    
    Returns:
        (output_path, final_threshold_db_used)
    """
    # Séquence de thresholds à essayer
    thresholds_to_try = [-60, -55, -50, -45, -40]
    # Commence à initial_threshold_db, progresse vers plus sélectif
    
    start_idx = thresholds_to_try.index(initial_threshold_db) if initial_threshold_db in thresholds_to_try else 0
    
    for threshold in thresholds_to_try[start_idx:]:
        # Filtrer les données avec ce threshold
        filtered_data = filter_by_peak_threshold(full_data, threshold)
        
        # Générer le rapport temporaire
        temp_path = write_xlsx(filtered_data, temp=True)
        
        # Mesurer la taille
        size_mb = temp_path.stat().st_size / 1024 / 1024
        
        if size_mb <= target_size_mb:
            # Renommer en version finale
            final_path = rename_temp_to_final(temp_path)
            return (final_path, threshold)
    
    # Si même -40 dBFS ne suffit pas → warning et dernière version
    logger.warning(
        f"Cannot reach target {target_size_mb} MB even with threshold -40 dBFS. "
        f"Final report is {size_mb:.1f} MB. Consider using a lighter preset."
    )
    return (final_path, -40.0)
```

**Documenter dans Index sheet :**

Le rapport shareable doit contenir dans son `Index` sheet :
- `preset_used: "ultra"`
- `peak_threshold_full: -70 dBFS`
- `peak_threshold_shareable: -55 dBFS` (la valeur finale utilisée)
- `shareable_target_mb: 25`
- `shareable_actual_size_mb: 23.4`
- `shareable_filtering_note: "Peaks below -55 dBFS removed to meet size target"`

Ceci permet à Claude en session de savoir qu'il regarde un rapport filtré et d'ajuster ses analyses en conséquence.

### 4.4 Paramètre pour désactiver shareable

```bash
--no-shareable              # ne génère que le rapport FULL
--shareable-target-mb 20    # override du target 25 MB
```

---

## 5 — Sheets impactées

### 5.1 Sheets time-based (résolution temporelle affectée)

Ces sheets auront plus de lignes en preset haute résolution :

- `_track_peak_trajectories` — scaling direct avec nombre de frames
- `_track_valley_trajectories` — idem
- `_track_multiband_time` — scaling direct
- `_track_dynamics_time` — scaling direct
- `_track_transients` — indirect (basé sur onset detection, mais précision améliorée)
- `_track_onsets` — indirect
- `_track_chroma` — scaling direct

### 5.2 Sheets spectral (résolution fréquentielle affectée)

Ces sheets auront une meilleure précision des valeurs en preset haute résolution :

- `_track_spectra` — **passage de quantification logarithmique à linéaire uniforme** (2.69 Hz/bin)
- `_track_spectral_descriptors` — bénéficie de meilleure FFT upstream (centroid, rolloff plus précis)
- `_track_stereo_bands` — résolution spectrale améliorée
- `_track_zone_energy` — indirect (plus de frames analysées, moyennes plus fines)

### 5.3 Sheets indirectement améliorées

Ces sheets consomment les sheets ci-dessus et bénéficient automatiquement :

- `Sections Timeline` — métriques par section plus précises
- `Freq Conflicts` — meilleure détection des masking zones
- `Anomalies` — meilleure caractérisation
- `Mix Health Score` — pondération plus juste
- `AI Context` — synthèse bénéficie de tout l'upstream

### 5.4 Sheets non-impactées

- `_track_automation_map` — basé sur data .als, invariant
- `Index` — meta-info, enrichi avec les nouveaux paramètres

### 5.5 Sheets nouvelles

**`_analysis_config`** (nouvelle) — documente la configuration utilisée pour l'analyse :

| Paramètre | Valeur |
|---|---|
| preset_name | ultra |
| hop_samples | 4410 |
| hop_ms | 100.0 |
| n_fft | 16384 |
| window_type | hann |
| overlap_pct | 73.1 |
| sample_rate | 44100 |
| peak_threshold_db | -70 |
| frames_per_beat_128 | 4.69 |
| delta_freq_hz | 2.69 |
| is_shareable_version | false |
| mix_analyzer_version | v2.8.0 |
| generated_at | 2026-04-24T14:30:00 |

Cette sheet permet à tout consommateur (Claude en session, Claude Code, F1 CLI) de savoir exactement dans quelle configuration le rapport a été généré.

---

## 6 — API proposée

### 6.1 Module source

**Nouveau module :** `mix_analyzer/resolution_presets.py` (constants + helpers)

**Modules modifiés :**
- `mix_analyzer/mix_analyzer.py` (orchestration principale, ajout paramètres)
- `mix_analyzer/spectral_engine.py` (moteur FFT, adopte preset)
- `mix_analyzer/peak_detector.py` (consomme threshold)
- `mix_analyzer/excel_writer.py` (génère les deux rapports)

Note : les noms exacts des modules à modifier sont à confirmer en début de dev en lisant le code actuel.

### 6.2 Fonction principale

```python
from pathlib import Path
from typing import Optional, Literal

ResolutionPresetName = Literal["economy", "standard", "fine", "ultra", "maximum"]

def analyze(
    als_path: Path | str,
    *,
    resolution: ResolutionPresetName = "standard",
    peak_threshold_db: float = -70.0,
    generate_shareable: bool = True,
    shareable_target_mb: float = 25.0,
    shareable_initial_threshold_db: float = -60.0,
    output_dir: Path | str = "reports/",
    # ... autres paramètres existants du Mix Analyzer
) -> AnalyzeResult:
    """
    Analyse un projet Ableton et génère le(s) rapport(s) Mix Analyzer.
    
    Args:
        als_path: Chemin vers le .als
        resolution: Preset de résolution (economy/standard/fine/ultra/maximum)
        peak_threshold_db: Seuil pour le rapport FULL (défaut -70 dBFS)
        generate_shareable: Si True, génère aussi le rapport shareable
        shareable_target_mb: Taille cible pour le rapport shareable (défaut 25 MB)
        shareable_initial_threshold_db: Threshold initial à tester pour shareable
        output_dir: Répertoire de sortie
    
    Returns:
        AnalyzeResult avec chemins des rapports générés et métadonnées
    
    Raises:
        InvalidPresetError: si resolution n'est pas un preset valide
        InvalidThresholdError: si peak_threshold_db hors [-80, -40]
    """
```

### 6.3 Result dataclass

```python
@dataclass
class AnalyzeResult:
    """Résultat d'une analyse Mix Analyzer."""
    full_report_path: Path
    full_report_size_mb: float
    full_report_threshold_db: float
    
    shareable_report_path: Optional[Path]     # None si generate_shareable=False
    shareable_report_size_mb: Optional[float]
    shareable_threshold_db: Optional[float]   # Peut différer de full si auto-ajusté
    
    preset_used: str
    generated_at: datetime
    
    warnings: list[str]
    decisions_log: list[str]
```

### 6.4 Exceptions custom

```python
class ResolutionEngineError(Exception):
    """Base exception pour Feature 10."""

class InvalidPresetError(ResolutionEngineError):
    """Preset de résolution inconnu."""

class InvalidThresholdError(ResolutionEngineError):
    """peak_threshold_db hors range [-80, -40]."""

class ShareableTargetUnreachableError(ResolutionEngineError):
    """Impossible d'atteindre shareable_target_mb même avec threshold sélectif."""
```

---

## 7 — CLI wrapper

### 7.1 Script principal

Modification du script existant de Mix Analyzer. Nouveau flag :

```bash
python -m mix_analyzer.analyze \
    --als "Acid_Drops_Sections_STD.als" \
    --resolution ultra \
    --peak-threshold -70 \
    --generate-shareable \
    --shareable-target-mb 25 \
    --output-dir "reports/"
```

### 7.2 Flags principaux

| Flag | Type | Défaut | Description |
|---|---|---|---|
| `--als` | path | (requis) | Chemin du .als source |
| `--resolution` | str | `standard` | economy/standard/fine/ultra/maximum |
| `--peak-threshold` | float | `-70` | Threshold en dBFS (range -80 à -40) |
| `--generate-shareable` | flag | True (défaut) | Génère aussi rapport shareable |
| `--no-shareable` | flag | - | Désactive la génération du shareable |
| `--shareable-target-mb` | float | `25` | Taille cible du shareable |
| `--shareable-initial-threshold` | float | `-60` | Threshold initial du shareable (ajustable à la hausse si taille dépasse) |
| `--output-dir` | path | `reports/` | Répertoire de sortie |
| `--verbose` | flag | - | Logs détaillés (decisions_log) |

### 7.3 Exit codes

- `0` : succès
- `1` : erreur d'input (fichier .als manquant, paramètre invalide)
- `2` : erreur d'écriture (permissions, disque plein)
- `3` : shareable target non atteignable (warning, rapport full OK tout de même)
- `4` : exception interne

### 7.4 Output console

**Pré-exécution :**
```
Mix Analyzer v2.8.0
Projet: Acid_Drops_Sections_STD.als
Preset: ultra (hop 100 ms, N_FFT 16384, Δf 2.69 Hz, 4.69 frames/beat @128 BPM)
Peak threshold FULL: -70 dBFS
Generate shareable: yes (target 25 MB)
Output dir: reports/
Démarrage analyse...
```

**Post-exécution :**
```
✓ Analyse terminée en 3m 24s

Rapport FULL :
  Path: reports/Acid_Drops_MixAnalyzer_2026-04-24_14-30_ultra_full.xlsx
  Taille: 33.8 MB
  Threshold: -70 dBFS

Rapport SHAREABLE :
  Path: reports/Acid_Drops_MixAnalyzer_2026-04-24_14-30_ultra_shareable.xlsx
  Taille: 24.2 MB
  Threshold: -55 dBFS (ajusté depuis -60 pour respecter target 25 MB)
  Warning: Peaks entre -70 et -55 dBFS absents du shareable (mais présents dans full)
```

---

## 8 — Plan de livraison

**Stratégie anti-timeout :** 14 micro-commits (7 code + 7 tests) avec séparation stricte.

### F10a — Infrastructure presets et constants

**Fichiers créés :**
- `mix_analyzer/resolution_presets.py` (constants + dataclass ResolutionPreset)

**Fonctions implémentées :**
- `ResolutionPreset` dataclass
- `RESOLUTION_PRESETS` dict avec les 5 presets
- `get_effective_hop_ms`
- `get_effective_delta_freq`
- `get_preset_by_name`
- Validation des valeurs (N_FFT puissance de 2, hop <= n_fft, etc.)

**Durée :** 45min
**Tests :** 4-5
**Commits :**
- `feat(F10): resolution presets infrastructure`
- `test(F10): unit tests for presets`

### F10b — Refactor spectral engine pour accepter preset + threshold

**Fichiers modifiés :**
- `mix_analyzer/spectral_engine.py` (ou équivalent, à identifier en début de dev)

**Modifications :**
- Signature des fonctions FFT acceptent maintenant `preset: ResolutionPreset` au lieu de constants hardcodées
- Paramètre `peak_threshold_db` propagé depuis l'orchestrateur
- Fonction `compute_stft` utilise `preset.n_fft` et `preset.hop_samples`
- Fonction `detect_peaks` utilise `peak_threshold_db`

**Durée :** 1h30
**Tests :** 6-8 (couvrant les 5 presets + threshold edge cases)
**Commits :**
- `feat(F10): spectral engine accepts preset and threshold`
- `test(F10): unit tests for spectral engine refactor`

### F10c — Mise à jour sheets time-based

**Fichiers modifiés :**
- Modules générant `_track_peak_trajectories`, `_track_valley_trajectories`, `_track_multiband_time`, `_track_dynamics_time`

**Modifications :**
- Accept preset + threshold
- Time columns reflètent la nouvelle résolution
- Volume scale approprié

**Durée :** 1h30
**Tests :** 6-8
**Commits :**
- `feat(F10): time-based sheets use preset resolution`
- `test(F10): unit tests for time-based sheets`

### F10d — Mise à jour sheets spectral

**Fichiers modifiés :**
- Modules générant `_track_spectra`, `_track_spectral_descriptors`, `_track_stereo_bands`

**Modifications :**
- Adopter résolution fréquentielle linéaire uniforme (2.69 Hz pour N_FFT 16384)
- Descripteurs spectraux recalculés sur nouvelle base

**Durée :** 1h30
**Tests :** 6-8
**Commits :**
- `feat(F10): spectral sheets use preset frequency resolution`
- `test(F10): unit tests for spectral sheets`

### F10e — Nouvelle sheet _analysis_config + Index update

**Fichiers modifiés :**
- Module de génération Index sheet
- Module de génération `_analysis_config` (nouveau)

**Modifications :**
- Sheet `_analysis_config` créée avec les 13 paramètres (voir section 5.5)
- Sheet `Index` enrichi avec `preset_used`, `peak_threshold`, `mix_analyzer_version`

**Durée :** 45min
**Tests :** 3-4
**Commits :**
- `feat(F10): analysis config sheet and Index update`
- `test(F10): unit tests for config metadata`

### F10f — Double rapport : FULL + SHAREABLE avec ajustement dynamique

**Fichiers modifiés :**
- Orchestrateur principal (`mix_analyzer/mix_analyzer.py` ou équivalent)

**Fonctions implémentées :**
- `generate_shareable_report` avec l'algorithme d'ajustement dynamique
- `filter_by_peak_threshold` (filtrage post-analyse)
- Logique de retry threshold -60, -55, -50, -45, -40
- Warning si target non atteignable

**Durée :** 2h
**Tests :** 5-6 (avec fixtures .als de différentes complexités)
**Commits :**
- `feat(F10): dual report generation with dynamic threshold adjustment`
- `test(F10): integration tests for dual report`

### F10g — CLI integration + documentation

**Fichiers modifiés :**
- Script CLI principal de Mix Analyzer

**Fonctions implémentées :**
- Parsing des nouveaux flags
- Validation des inputs
- Affichage console pré/post exécution
- Exit codes

**Durée :** 1h
**Tests :** 3-4 (smoke tests CLI)
**Commits :**
- `feat(F10-cli): new flags for resolution and shareable`
- `test(F10-cli): smoke tests for CLI`

### Total

**Effort total F10 :** 10h-14h, ~40-55 tests, **14 micro-commits**.

---

## 9 — Tests d'acceptation

### 9.1 Tests unitaires
- ✅ ~40 tests passants
- ✅ Coverage > 85% sur nouveaux modules (`resolution_presets.py`, etc.)
- ✅ Coverage > 80% sur modules modifiés

### 9.2 Tests d'intégration
- ✅ Tous les presets produisent des rapports valides (ouvrables Excel)
- ✅ Test de non-régression : rapport preset `standard` équivaut à rapport v2.7.0 (même nombre de frames ±1%, mêmes peaks)
- ✅ Rapport `ultra` a effectivement 4.69 frames/beat (à 128 BPM, mesurable)
- ✅ Rapport `ultra` a effectivement 2.69 Hz par bin (mesurable dans `_track_spectra`)
- ✅ Rapport shareable respecte target_mb (avec warning si impossible)
- ✅ Sheet `_analysis_config` présente et complète dans tous les rapports

### 9.3 Tests CLI
- ✅ `--resolution ultra` fonctionne
- ✅ `--peak-threshold -60` fonctionne
- ✅ `--no-shareable` désactive le shareable
- ✅ `--shareable-target-mb 15` force ajustement threshold à une valeur plus sélective
- ✅ Preset invalide → erreur claire avec liste des presets valides
- ✅ Threshold hors range → erreur claire

### 9.4 Validation terrain (post-livraison code)
- ✅ Générer rapport Acid Drops en preset `ultra` (full + shareable)
- ✅ Ouverture correcte dans Excel / LibreOffice
- ✅ Validation des métriques cohérentes (Mix Health Score, anomalies, etc.)
- ✅ Shareable < 25 MB
- ✅ Generation time acceptable (< 5 min pour preset ultra sur Acid Drops)

### 9.5 Documentation
- ✅ Spec mise à jour si divergence pendant dev
- ✅ `roadmap_features_1_8.md` mis à jour (F10 → Livrée)
- ✅ `CHANGELOG.md` du repo enrichi
- ✅ README du repo mis à jour avec exemples d'usage des nouveaux flags

---

## 10 — Impact sur les features existantes

### 10.1 Feature 1 (CDE auto-apply)

**Comportement attendu :** F1 consomme les rapports Excel + diagnostics JSON. F1 fonctionne identiquement, mais bénéficie de meilleures données en amont :
- Peak-follow plus précis (hop 100ms vs 166ms)
- Diagnostics plus fins dans les hautes fréquences

**Action nécessaire :** aucune modification F1 requise. Les diagnostics CDE seront régénérés depuis les nouveaux rapports avant le pilote Bass Rythm.

### 10.2 Feature 3.6 (CDE engine)

**Comportement attendu :** CDE engine génère diagnostics à partir des sheets du rapport. Avec haute résolution, les diagnostics deviennent plus nombreux (plus de frames analysées) et plus précis en fréquence.

**Action nécessaire :** vérifier que CDE engine n'a pas de constantes hardcodées qui dépendaient de l'ancienne résolution. À auditer pendant F10e.

### 10.3 Features 6, 7, 8 (en roadmap)

**Comportement attendu :** bénéficient automatiquement de la haute résolution quand elles seront développées.

**Impact sur les specs :** les specs F6, F7, F8 v1.1 mentionnent des seuils calibrés sur l'ancienne résolution. **À vérifier** lors du dev de chaque feature si les seuils doivent être ajustés (probablement pas, car ils sont en fréquence et dBFS, pas en frames).

---

## 11 — Risques techniques identifiés

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| CDE engine a des hardcoded dependencies sur hop 166 ms | Moyenne | Logique | Audit pendant F10e, mise à jour si nécessaire |
| N_FFT 16384 trop lourd pour machines modestes | Faible | Performance | Machine desktop Alexandre a 64 GB RAM, marge confortable |
| Certains projets Ableton utilisent SR 48 kHz → décalage hop_ms | Moyenne | Précision | Conversion dynamique (section 2.2), documenté dans report metadata |
| Target 25 MB non atteignable même avec -40 dBFS | Faible | Bloquant upload | Warning explicite + suggestion preset plus léger |
| Overlap preset economy invalide (hop > n_fft) | Haute | Bug | Ajustement en section 2.3, validé avant dev |
| Rapport standard différent du rapport v2.7.0 | Moyenne | Regression | Test de non-régression explicite en F10b |
| Scaling volumétrique sous-estimé pour projets denses | Moyenne | Dépassement target | Algorithme d'ajustement a retry jusqu'à -40, + warning |
| Temps de génération prohibitif en preset maximum | Moyenne | UX | Documenter clairement, usage recommandé pour debug uniquement |

---

## 12 — Hors scope F10 v1

**Reportés à F10 v2 ou autres features :**

- **Suggestion automatique de preset** (refusé par Alexandre 2026-04-23, contrôle manuel préféré)
- **Presets adaptatifs par genre** (logic de "Industrial → preset X, Ambient → preset Y") — possible en F10 v2 si besoin
- **Streaming de gros rapports** (si fichier > 100 MB, chunking par track) — pas urgent
- **Format alternatif au .xlsx** (HDF5, parquet pour performance) — question future
- **Visualisation graphique des trajectories haute résolution** — hors scope, outil externe

---

## 13 — Pas de Q en attente validation

Contrairement aux specs F6/F7/F8, cette spec n'a pas de Q1-QN en attente parce que toutes les décisions d'architecture ont été validées dans la conversation du 2026-04-23 avant rédaction :

- Q "priorité F10 vs F1 pilote" → F10 d'abord ✓
- Q "quelles features impactées" → toutes ✓
- Q "compromis résolution vs taille" → preset ultra 100ms + shareable <25 MB ✓
- Q "slider vs presets" → presets ✓
- Q "suggestion automatique" → non, contrôle manuel ✓
- Q "threshold séparé" → oui, paramètre indépendant ✓

**La spec passe directement en v1.2 si Alexandre valide telle quelle** (pas d'itération v1.1 → v1.2).

**Si Alexandre veut ajuster après lecture** (ex: changer les valeurs de presets, modifier les thresholds par défaut), on itère en v1.1.

---

## 14 — Procédure d'évolution

Suivre `documentation_discipline.md` section 4.

**Triggers probables :**
- Alexandre ajuste des valeurs après lecture spec → v1.1
- Découverte technique pendant dev (ex: overlap economy invalide confirmé) → v1.2
- Validation terrain révèle que preset ultra produit rapports trop lourds → v1.3 avec ajustements

---

## 15 — Référence rapide (quick card)

**Statut :** Spec en attente de validation globale. Pas de Q en attente (toutes résolues en amont).

**Effort estimé total :** 10h-14h, ~40-55 tests, 14 commits

**Modules à créer :**
- `mix_analyzer/resolution_presets.py`

**Modules à modifier :**
- `mix_analyzer/spectral_engine.py` (ou équivalent)
- `mix_analyzer/peak_detector.py` (ou équivalent)
- `mix_analyzer/excel_writer.py` (ou équivalent)
- `mix_analyzer/mix_analyzer.py` (orchestration)
- CLI principal Mix Analyzer

**Presets clés :**

| Preset | Hop ms | Frames/beat 128 | Δf Hz |
|---|---|---|---|
| economy | 139 | 2.37 | 5.38 |
| standard | 166 | 2.82 | 5.38 |
| fine | 116 | 4.04 | 2.69 |
| ultra | 100 | 4.69 | 2.69 |
| maximum | 58 | 8.08 | 2.69 |

**Threshold :**
- Range : -80 à -40 dBFS
- Défaut FULL : -70 dBFS
- Défaut SHAREABLE initial : -60 dBFS (auto-ajuste jusqu'à -40 si target taille non atteint)

**Architecture double rapport :**
- FULL : local + Claude Code, sans limite de taille
- SHAREABLE : upload Claude.ai, <25 MB, threshold dynamique

**Dépendances roadmap :**
- Mix Analyzer v2.7.0 livré ✅
- F1 pilote Bass Rythm en attente F10 livrée
- F6/F7/F8 bénéficient automatiquement

**Documents associés :**
- `qrust_professional_context.md` section 4
- `mix_engineer_brief_v2_3.md` (à mettre à jour en v2.4 avec références F10)
- `roadmap_features_1_8_v2_1.md` (mise à jour prévue pour F10)
- `documentation_discipline.md`

---

**Fin spec Feature 10 v1.0. Pas de Q en attente validation — si architecture validée telle quelle par Alexandre, passage direct en v1.2 et démarrage dev. Si ajustement nécessaire, itération v1.1 puis v1.2.**
