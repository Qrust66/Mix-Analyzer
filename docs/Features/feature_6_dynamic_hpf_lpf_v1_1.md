# Feature 6 — Dynamic HPF/LPF per section

**Version spec :** 1.1
**Date dernière modification :** 2026-04-23
**Statut :** Planifiée, non démarrée — Q1-Q5 en attente de validation utilisateur (voir section 12)
**Hérite de :** `documentation_discipline.md` (règles de rédaction), `qrust_professional_context.md` (philosophie 100% dynamique justifiant la feature)
**Brief méthodologique de référence :** `mix_engineer_brief_v2_3.md` (notamment règle 5.9 EQ8 max, règle 5.10 dynamique par défaut, Phase 3 dynamique HPF/LPF)
**Feature parent dans la roadmap :** voir `roadmap_features_1_8.md`

**Historique d'évolution de la spec :**
- v1.0 — création initiale (2026-04-23 après-midi). Première rédaction post-validation philosophie 100% dynamique. Couvrait objectif, données consommées, algorithme général, écriture EQ8, API, CLI, plan de livraison, validation, risques, hors scope, questions de validation.
- v1.1 (ce document) — audit complétude pour Claude Code. Préservation intégrale du contenu v1.0 + 15 ajouts/clarifications signalés explicitement : header conforme à `documentation_discipline.md`, correction effort estimé incohérent, mise à jour références documentaires (`qrust_artistic_context` → `project_<nom>_context.md` et `qrust_professional_context.md`), justification de tous les seuils numériques magiques (-20 dBFS, 95%, 0.8, 1 semitone, etc.), spécification complète algorithme LPF (ne plus dire "symétrique"), définition explicite des dataclasses référencées (`PeakTrajectory`), précision des modules sources à modifier ou créer, stratégie anti-timeout détaillée, conventions de tests (pytest, fixtures, répertoire), référence au CHANGELOG du repo Mix-Analyzer, ajout section "Tests d'acceptation", ajout section "Rétrocompatibilité", clarification mode single vs batch.

**Principe de préservation :** cette spec préserve intégralement le contenu de v1.0. Aucune section, aucun exemple, aucune décision validée n'a été supprimée — seulement étendue ou clarifiée. Les ajouts et clarifications de v1.1 sont signalés explicitement avec annotation "(clarifié en v1.1)" ou "(nouveau en v1.1)".

**Effort estimé :** 5.5h-7.5h Claude Code, ~20-27 tests unitaires/integration, 5 micro-commits (voir Section 7). **Note v1.1 :** correction de l'incohérence v1.0 qui mentionnait "4-6 heures" en header puis "5.5h-7.5h" en Section 7 — la valeur correcte est 5.5h-7.5h, basée sur le détail des micro-commits.

---

## 1 — Objectif et justification

### 1.1 Ce que fait la feature

Produire des automations contextuelles pour les bandes HPF (High-Pass Filter) et LPF (Low-Pass Filter) d'EQ Eight, de sorte que la fréquence de coupe **s'adapte par section** et/ou **suit le contenu réel de la track** dans le temps.

Remplace les HPF/LPF statiques traditionnels par un comportement adaptatif précis, fidèle à la philosophie "traitement dynamique par défaut" du `qrust_professional_context.md` (section 4.1).

### 1.2 Pourquoi cette feature

Dans l'approche traditionnelle, un HPF à 80 Hz sur une voix est posé de manière fixe pour toute la durée du morceau. Cette approche ignore que :

- Dans l'intro, la voix peut être basse et intime — HPF à 80 Hz enlève du corps utile
- Dans le drop, la voix peut être plus agressive et concurrente avec le kick/sub — HPF à 120 Hz est plus approprié pour dégager l'espace
- Dans le breakdown, la voix peut devenir solo — HPF à 60 Hz pour retrouver la pleine chaleur

Un HPF statique fige un compromis moyen qui n'est optimal nulle part. Un HPF dynamique par section est optimal partout.

### 1.3 Ancrage dans la philosophie Qrust

Cette feature implémente concrètement la **règle 5.10 du `mix_engineer_brief_v2_3.md`** ("traitement dynamique par défaut") pour le cas spécifique des HPF/LPF. Sans Feature 6, les HPF/LPF doivent être :

- Soit appliqués manuellement par automation Live native (lourd, error-prone)
- Soit reportés à plus tard (mauvais)
- Soit appliqués statiquement (viole la philosophie sauf exceptions documentées)

Feature 6 permet l'application programmatique propre.

### 1.4 Résultat attendu

Une fonction `write_dynamic_hpf_lpf_from_analysis` qui :

1. Consomme les données `_track_zone_energy` (énergie par zone spectrale et par section) et `_track_peak_trajectories` (peaks dans le temps)
2. Détermine la fréquence de coupe HPF optimale par section selon le contenu réel de la track dans cette section
3. Détermine la fréquence de coupe LPF optimale par section selon le contenu réel
4. Écrit dans l'EQ8 cible des automations synchronisées Freq + IsOn sur les bandes 0 (HPF) et 7 (LPF)

Le comportement précis (cible EQ8 par défaut, gestion IsOn, etc.) est paramétrable et dépend des décisions sur Q1-Q5 (voir section 12).

---

## 2 — Données consommées

### 2.1 Inputs

**Source 1 — `_track_zone_energy` (rapport Mix Analyzer)**

Sheet Excel contenant par track et par section l'énergie dans chaque zone fréquentielle :
- Sub : 20-60 Hz
- Bass : 60-250 Hz
- Low-Mid : 250-500 Hz
- Mid : 500-2000 Hz
- High-Mid : 2000-4000 Hz
- Presence : 4000-8000 Hz
- Air : 8000-20000 Hz

**Format :** valeurs en pourcentage (% de l'énergie totale de la track sur cette section).

**Utilité :** savoir où se situe le "vrai contenu utile" de la track à chaque section. Si la zone Sub est à 1% sur Drop 2, on peut couper agressivement ; si elle est à 10%, on doit être conservateur.

**Source 2 — `_track_peak_trajectories` (rapport Mix Analyzer)**

Peaks détectés dans le temps avec fréquence, amplitude, durée. Déjà consommés par Feature 1 (mode peak-follow) et par `write_resonance_suppression`.

**Format :** voir dataclass `PeakTrajectory` documentée en section 2.3.

**Utilité :** identifier les fréquences où la track émet vraiment de l'énergie dans le temps. Permet de raffiner les seuils HPF/LPF en repérant les peaks proches de la zone de coupe.

**Source 3 — `_track_spectral_descriptors` (rapport Mix Analyzer)**

Descripteurs agrégés par track et par section :
- `centroid_hz` : centre de gravité spectral
- `rolloff_85_hz` : fréquence sous laquelle se trouve 85% de l'énergie
- `rolloff_95_hz` : fréquence sous laquelle se trouve 95% de l'énergie
- `flatness` : platitude spectrale (0 = ton pur, 1 = bruit blanc)

**Utilité pour F6 :**
- `rolloff_85_hz` donne une estimation conservative du **bord haut utile** → guide la fréquence LPF
- `centroid_hz` indique la tendance globale (track grave vs aiguë)
- `flatness` informe sur le caractère tonal vs bruité (un bruit blanc tolère un LPF plus bas qu'un instrument harmonique)

**Source 4 — `genre_music_profiles.json`**

Caps de HPF et LPF par style × track type :
- `hpf_max_hz` : fréquence maximale de coupe HPF acceptable dans ce contexte (plafond absolu)
- `lpf_min_hz` : fréquence minimale de coupe LPF acceptable dans ce contexte (plancher absolu)

**Utilité :** bornes dures qui empêchent la feature de couper trop agressivement par rapport à l'esthétique du genre. Conformément à la règle 5.8 du `mix_engineer_brief_v2_3.md`, le profile JSON est l'autorité finale.

**Source 5 — Locators (via `als_utils.read_locators`)**

Bornes temporelles des sections pour aligner les automations.

**Format :** liste de tuples `(time_beats: float, name: str)` où `time_beats` est la position en beats Ableton et `name` est le nom du Locator (ex: "Drop_1", "Chorus_2").

**Source 6 — Tempo du projet**

Lu depuis le `.als` via `als_utils.read_tempo` (à confirmer si helper existe ou à créer). Nécessaire pour convertir les beats en samples lors de l'écriture des automations.

### 2.2 Format de consommation

La fonction publique reçoit la signature suivante (détail complet en section 5) :

```python
def write_dynamic_hpf_lpf_from_analysis(
    als_path: Path | str,
    track_name: str,
    zone_energy_by_section: dict[str, dict[str, float]],
    peak_trajectories: list[PeakTrajectory],
    spectral_descriptors: dict[str, dict[str, float]],
    locators: list[tuple[float, str]],
    *,
    genre_profile: dict,
    track_type: str,
    hpf_enabled: bool = True,
    lpf_enabled: bool = True,
    target_eq8_username: str = "Peak Resonance",
    transition_crossfade_beats: float = 2.0,
    peak_follow_within_section: bool = False,
    dry_run: bool = False,
) -> HpfLpfApplicationReport
```

### 2.3 Définition des dataclasses référencées (nouveau en v1.1)

**`PeakTrajectory`** — déjà définie dans Mix Analyzer. Référencer le module source dans l'import :

```python
from mix_analyzer.peak_trajectories import PeakTrajectory
# (chemin exact à confirmer en début de dev)
```

**Schéma attendu de `PeakTrajectory`** (à valider contre la définition réelle au démarrage du dev) :
```python
@dataclass
class PeakTrajectory:
    track_name: str
    section_name: str
    time_start_beats: float
    time_end_beats: float
    frequency_hz: float
    amplitude_dbfs: float
    duration_seconds: float
    # Champs additionnels potentiels : Q estimée, prominence, harmonique
```

Si la définition réelle diffère, la spec doit être mise à jour en conséquence avant dev.

**`HpfLpfApplicationReport`** — nouvelle dataclass à créer pour F6, voir section 5.2.

---

## 3 — Algorithme de calcul des fréquences de coupe

### 3.1 HPF — fréquence de coupe par section

Pour chaque section du projet, exécuter les étapes suivantes en séquence :

**Étape A — Récupérer le track_type**

Source de la valeur (par ordre de priorité) :
1. Argument explicite passé à la fonction (`track_type=...`)
2. Configuration externe (CSV ou YAML chargé par le CLI wrapper, voir section 6)
3. Heuristique basée sur le nom de track (ex: "Lead Vocal" dans le nom → "Lead Vocal")

**Note v1.1 :** la v1.0 référençait `qrust_artistic_context` qui n'existe plus. La track_type peut maintenant venir du `project_<nom>_context.md` du projet courant qui inventorie les tracks (voir `project_acid_drops_context.md` section 6.1 pour exemple).

**Étape B — Récupérer le cap absolu du profil**

Charger `hpf_max_hz` du `genre_profile` pour ce track_type. Exemples :
- Industrial + Lead Vocal : `hpf_max_hz: 80`
- Industrial + Sub Bass : `hpf_max_hz: 20`
- Industrial + Kick : `hpf_max_hz: 30`

Cette valeur est un **plafond absolu** — la fréquence HPF calculée ne peut jamais le dépasser.

**Étape C — Calculer le seuil théorique selon l'énergie réelle dans la section**

Lire `pct_sub` et `pct_bass` depuis `zone_energy_by_section[section_name]`.

**Logique avec seuils paramétrables (clarifié en v1.1) :**

```python
# Seuils par défaut (configurables via constants module-level)
DEFAULT_SUB_NEGLIGIBLE_PCT = 2.0    # sub < 2% → considéré comme négligeable
DEFAULT_BASS_NEGLIGIBLE_PCT = 5.0   # bass < 5% → considéré comme négligeable
DEFAULT_SUB_PRESENT_PCT = 5.0       # sub > 5% → contenu utile présent
DEFAULT_HPF_MAX_FRACTION = 0.95     # quand bas négligeable, HPF à 95% du cap
DEFAULT_HPF_NORMAL_FRACTION = 0.80  # cas normal, HPF à 80% du cap
DEFAULT_HPF_MIN_FREQ_PRESENT = 40.0  # quand sub présent, HPF descend à 40 Hz
DEFAULT_HPF_MAX_FREQ_PRESENT = 50.0  # quand sub présent, HPF max 50 Hz
```

**Justification des seuils par défaut (nouveau en v1.1) :**

- **2% pour Sub négligeable** : seuil empirique cohérent avec la perception auditive — une zone à moins de 2% de l'énergie spectrale n'est pas perceptuellement significative (équivalent à -17 dBFS relatif par rapport au pic spectral)
- **5% pour Bass négligeable** : seuil légèrement plus haut car la zone Bass (60-250 Hz) est plus large et donc accumule naturellement plus de pourcentage
- **5% pour Sub présent** : seuil de protection — au-delà, on assume du contenu intentionnel
- **95% du cap quand bas négligeable** : on monte presque au max sans aller à 100% pour garder une marge de sécurité au cas où la prochaine section aurait du contenu
- **80% du cap en cas normal** : valeur par défaut conservative, permet à la track d'avoir un peu de présence basse
- **40-50 Hz quand sub présent** : préserve le contenu sub utile sans descendre jusqu'à 20 Hz par défaut (économie de headroom)

Tous ces seuils sont **configurables** via paramètres module-level. Le CLI peut les exposer en flags `--sub-negligible-pct`, etc., pour ajustement par track ou par projet.

**Algorithme :**

```python
def _compute_hpf_freq_for_section(
    zone_energy: dict[str, float],
    profile_cap_hz: float,
    *,
    sub_negligible_pct: float = DEFAULT_SUB_NEGLIGIBLE_PCT,
    bass_negligible_pct: float = DEFAULT_BASS_NEGLIGIBLE_PCT,
    sub_present_pct: float = DEFAULT_SUB_PRESENT_PCT,
    hpf_max_fraction: float = DEFAULT_HPF_MAX_FRACTION,
    hpf_normal_fraction: float = DEFAULT_HPF_NORMAL_FRACTION,
    hpf_min_freq_present: float = DEFAULT_HPF_MIN_FREQ_PRESENT,
    hpf_max_freq_present: float = DEFAULT_HPF_MAX_FREQ_PRESENT,
) -> float:
    pct_sub = zone_energy.get("Sub", 0.0)
    pct_bass = zone_energy.get("Bass", 0.0)
    
    if pct_sub < sub_negligible_pct and pct_bass < bass_negligible_pct:
        # Track quasi-silencieuse en bas → HPF agressif
        return profile_cap_hz * hpf_max_fraction
    elif pct_sub > sub_present_pct:
        # Sub utile présent → HPF doux pour préserver
        # Interpolation linéaire entre min_freq et max_freq selon intensité
        intensity = min(1.0, (pct_sub - sub_present_pct) / (15.0 - sub_present_pct))
        return hpf_min_freq_present + (1 - intensity) * (hpf_max_freq_present - hpf_min_freq_present)
    else:
        # Cas intermédiaire
        return profile_cap_hz * hpf_normal_fraction
```

**Étape D — Appliquer le cap dur du profil**

```python
hpf_this_section = min(hpf_theoretical, profile_cap_hz)
```

Garantit que la fréquence ne dépasse jamais le plafond du profil genre.

**Étape E — Vérifier cohérence avec les peak_trajectories**

**Justification du seuil -20 dBFS (nouveau en v1.1) :**

-20 dBFS est le seuil empirique en dessous duquel un peak est considéré comme négligeable pour la perception. Au-dessus de -20 dBFS, un peak est audible et doit être protégé du HPF. Ce seuil est aligné avec les pratiques de Mix Analyzer pour la détection de peaks significatifs.

**Justification du décalage de 1 semitone (nouveau en v1.1) :**

1 semitone (~5.95% de différence en fréquence) est un décalage perceptuellement significatif qui garantit que le peak n'est pas dans la zone d'atténuation du HPF (la pente d'un HPF à 12 dB/octave atténue notablement dans les ~1 semitone autour de la fréquence de coupe).

**Algorithme :**

```python
PEAK_PROTECTION_THRESHOLD_DBFS = -20.0  # configurable
PEAK_PROTECTION_SEMITONES = 1.0          # configurable

def _adjust_hpf_for_peaks(
    hpf_hz: float,
    peaks: list[PeakTrajectory],
    section_name: str,
    *,
    peak_threshold_dbfs: float = PEAK_PROTECTION_THRESHOLD_DBFS,
    semitone_offset: float = PEAK_PROTECTION_SEMITONES,
) -> float:
    # Filtrer peaks de cette section avec amplitude significative
    relevant_peaks = [
        p for p in peaks
        if p.section_name == section_name
        and p.amplitude_dbfs > peak_threshold_dbfs
        and p.frequency_hz < hpf_hz
    ]
    
    if not relevant_peaks:
        return hpf_hz
    
    # Trouver le peak le plus bas en fréquence
    lowest_peak = min(relevant_peaks, key=lambda p: p.frequency_hz)
    
    # Réduire le HPF pour passer 1 semitone sous ce peak
    semitone_factor = 2 ** (-semitone_offset / 12)
    safe_hpf = lowest_peak.frequency_hz * semitone_factor
    
    return min(hpf_hz, safe_hpf)
```

**Résultat —** Un dict `{section_name: hpf_freq_hz}` avec une fréquence de coupe par section, garantie d'être dans `[20.0, profile_cap_hz]` et de préserver tous les peaks > -20 dBFS de la track.

### 3.2 LPF — fréquence de coupe par section (clarifié en v1.1, plus seulement "symétrique")

**Note v1.1 :** la v1.0 disait "Symétrique à HPF" ce qui est insuffisant pour l'implémentation. Voici la spécification complète.

Pour chaque section du projet, exécuter les étapes suivantes en séquence :

**Étape A — Récupérer le track_type** (identique à HPF)

**Étape B — Récupérer le cap absolu du profil**

Charger `lpf_min_hz` du `genre_profile`. Exemples :
- Industrial + Lead Vocal : `lpf_min_hz: 12000` (à confirmer dans le profil)
- Industrial + Hi-Hat : `lpf_min_hz: 18000`
- Industrial + Sub Bass : `lpf_min_hz: 200` (cas spécial — la track est censée être limitée en haut)

Cette valeur est un **plancher absolu** — la fréquence LPF calculée ne peut jamais descendre en-dessous.

**Étape C — Calculer le seuil théorique selon l'énergie réelle**

Lire `pct_air`, `pct_presence`, `pct_high_mid` depuis `zone_energy_by_section[section_name]`.

**Constants par défaut (nouveau en v1.1) :**

```python
DEFAULT_AIR_NEGLIGIBLE_PCT = 1.0       # air < 1% → négligeable
DEFAULT_PRESENCE_NEGLIGIBLE_PCT = 3.0  # presence < 3% → négligeable
DEFAULT_AIR_PRESENT_PCT = 4.0           # air > 4% → contenu utile
DEFAULT_LPF_MIN_FRACTION = 1.05         # quand haut négligeable, LPF à 105% du cap
DEFAULT_LPF_NORMAL_FRACTION = 1.20      # cas normal, LPF à 120% du cap
DEFAULT_LPF_MAX_FREQ = 20000.0          # plafond absolu d'EQ8
DEFAULT_LPF_HIGH_FREQ_PRESENT = 16000.0  # quand air présent, LPF haut
```

**Justification des seuils LPF (nouveau en v1.1) :**

- **1% pour Air négligeable** : seuil plus strict que pour Sub car la zone Air (8-20 kHz) est psychoacoustiquement plus importante (perception du "brillant", "ouvert")
- **3% pour Presence négligeable** : zone critique pour intelligibilité, seuil plus généreux pour préserver
- **4% pour Air présent** : protection forte
- **105% du cap min quand haut négligeable** : on coupe juste au-dessus du plancher, économise du CPU et reste transparent
- **120% du cap min en cas normal** : marge confortable au-dessus du plancher pour préserver l'air
- **16000 Hz quand air présent** : préserve l'essentiel du brillant sans aller jusqu'à 20 kHz

**Logique conservatrice (LPF différent de HPF) :**

Le LPF est traité plus conservativement que le HPF. Justification : couper du haut est perceptuellement plus dommageable que couper du bas (l'oreille est plus sensible aux pertes d'air qu'aux pertes de sub). Donc en cas de doute, LPF haut.

**Algorithme :**

```python
def _compute_lpf_freq_for_section(
    zone_energy: dict[str, float],
    profile_min_hz: float,
    *,
    air_negligible_pct: float = DEFAULT_AIR_NEGLIGIBLE_PCT,
    presence_negligible_pct: float = DEFAULT_PRESENCE_NEGLIGIBLE_PCT,
    air_present_pct: float = DEFAULT_AIR_PRESENT_PCT,
    lpf_min_fraction: float = DEFAULT_LPF_MIN_FRACTION,
    lpf_normal_fraction: float = DEFAULT_LPF_NORMAL_FRACTION,
    lpf_max_freq: float = DEFAULT_LPF_MAX_FREQ,
    lpf_high_freq_present: float = DEFAULT_LPF_HIGH_FREQ_PRESENT,
) -> float:
    pct_air = zone_energy.get("Air", 0.0)
    pct_presence = zone_energy.get("Presence", 0.0)
    
    if pct_air < air_negligible_pct and pct_presence < presence_negligible_pct:
        # Track quasi-silencieuse en haut → LPF près du plancher
        return profile_min_hz * lpf_min_fraction
    elif pct_air > air_present_pct:
        # Air utile présent → LPF haut pour préserver
        return min(lpf_high_freq_present, lpf_max_freq)
    else:
        # Cas intermédiaire — conservatif
        return min(profile_min_hz * lpf_normal_fraction, lpf_max_freq)
```

**Étape D — Appliquer le plancher dur du profil**

```python
lpf_this_section = max(lpf_theoretical, profile_min_hz)
```

**Étape E — Vérifier cohérence avec les peak_trajectories**

Symétrique à l'algorithme HPF mais avec inversion du sens : si un peak > -20 dBFS existe à une fréquence **supérieure** à `lpf_this_section`, **augmenter le LPF** de 1 semitone pour préserver ce peak.

```python
def _adjust_lpf_for_peaks(
    lpf_hz: float,
    peaks: list[PeakTrajectory],
    section_name: str,
    *,
    peak_threshold_dbfs: float = PEAK_PROTECTION_THRESHOLD_DBFS,
    semitone_offset: float = PEAK_PROTECTION_SEMITONES,
    lpf_max_freq: float = DEFAULT_LPF_MAX_FREQ,
) -> float:
    relevant_peaks = [
        p for p in peaks
        if p.section_name == section_name
        and p.amplitude_dbfs > peak_threshold_dbfs
        and p.frequency_hz > lpf_hz
    ]
    
    if not relevant_peaks:
        return lpf_hz
    
    highest_peak = max(relevant_peaks, key=lambda p: p.frequency_hz)
    semitone_factor = 2 ** (semitone_offset / 12)
    safe_lpf = highest_peak.frequency_hz * semitone_factor
    
    return min(max(lpf_hz, safe_lpf), lpf_max_freq)
```

**Résultat —** Un dict `{section_name: lpf_freq_hz}` avec une fréquence de coupe par section, garantie d'être dans `[profile_min_hz, 20000.0]` et de préserver tous les peaks > -20 dBFS de la track.

### 3.3 Transitions entre sections

Pour éviter les clicks ou artefacts audibles au changement de section :

**Crossfade linéaire de `transition_crossfade_beats` beats** (défaut 2.0 beats = ~0.94s à 128 BPM) autour de la frontière entre deux sections.

Exemple : HPF passe de 60 Hz (Drop 1) à 80 Hz (Build 2).
- De `(boundary - 1.0 beat)` à `boundary` : HPF tient à 60 Hz
- De `boundary` à `(boundary + 1.0 beat)` : interpolation linéaire 60 → 80 Hz
- De `(boundary + 1.0 beat)` à fin Build 2 : HPF tient à 80 Hz

**Cas particuliers :**

- **Sections courtes (< 3 beats) :** réduction proportionnelle du crossfade pour éviter qu'il déborde la section
- **Première section :** pas de crossfade en amont (juste un fade-in si IsOn alterne)
- **Dernière section :** pas de crossfade en aval

**Algorithme :**

```python
def _compute_crossfade_for_boundary(
    section_duration_beats: float,
    target_crossfade_beats: float,
) -> float:
    """Réduit le crossfade s'il dépasse 1/3 de la section."""
    max_acceptable = section_duration_beats / 3.0
    return min(target_crossfade_beats, max_acceptable)
```

### 3.4 Mode peak-follow intra-section (optionnel, advanced)

Pour les tracks avec grande variabilité de contenu intra-section (ex: un lead qui a des moments silencieux et des moments agressifs dans la même section), offrir un mode où le HPF/LPF s'adapte non seulement par section mais aussi par peak intra-section.

**Implémentation :** reuse du `_collect_active_peak_frames` de Feature 1, appliqué avec logique HPF/LPF au lieu de cut.

**Paramètre :** `peak_follow_within_section=False` par défaut, `True` en option avancée.

**Note v1.1 :** ce mode est **hors scope F6 v1**. À implémenter en F6 v2 si validation terrain confirme l'utilité. Voir section 10.

---

## 4 — Écriture dans l'EQ8

### 4.1 Cible des automations

**Convention F6 (à valider Q1) :** le HPF occupe la **bande 0** et le LPF occupe la **bande 7** d'un EQ Eight.

**Justification de cette convention (clarifié en v1.1) :**

Cette convention n'est pas (encore) formalisée dans le brief méthodologique mais découle logiquement de :
- La règle "max 3 EQ8 correctifs par track" (`mix_engineer_brief_v2_3.md` section 5.9) qui pousse à minimiser le nombre d'EQ8
- Le fait que les bandes 0 et 7 sont les positions extrêmes naturelles pour HPF (bande basse) et LPF (bande haute) dans EQ Eight
- L'économie de devices : si on intègre HPF/LPF dans un EQ8 existant (Peak Resonance), pas besoin d'un EQ8 supplémentaire

Si Q1 est validée, cette convention deviendra une **règle officielle** à intégrer dans le brief méthodologique en v2.4.

**Target EQ8 par défaut (à valider Q2) :** l'EQ8 nommé "Peak Resonance" existant sur la track. Alternative : "Static Cleanup" si l'utilisateur veut séparer les rôles, ou un nouveau "HPF/LPF Dynamic" dédié.

**Création si absent :** si l'EQ8 cible n'existe pas sur la track, Feature 6 en clone un depuis le `Pluggin Mapping.als` (pattern existant utilisé par `write_resonance_suppression`).

### 4.2 Paramètres écrits

**Pour la bande 0 (HPF) :**

| Paramètre | Valeur |
|---|---|
| `Mode` | Forcé à 0 (High-Pass 24 dB/oct par défaut Ableton) |
| `IsOn` | Automation ou constant True selon Q4 |
| `Freq` | Automation avec valeurs calculées par section + crossfades |
| `Gain` | 0 dB (non utilisé en mode HPF) |
| `Q` | Constant à 0.71 (default Ableton) ou paramétrable |

**Pour la bande 7 (LPF) :**

| Paramètre | Valeur |
|---|---|
| `Mode` | Forcé à 5 (Low-Pass 24 dB/oct par défaut Ableton) |
| `IsOn` | Automation ou constant True selon Q4 |
| `Freq` | Automation avec valeurs calculées par section + crossfades |
| `Gain` | 0 dB (non utilisé en mode LPF) |
| `Q` | Constant à 0.71 (default Ableton) ou paramétrable |

### 4.3 Contrainte de coexistence avec les bandes 1-6 existantes

**Règle absolue :** Feature 6 ne touche **jamais** aux bandes 1-6 d'un EQ8 existant. Ces bandes sont le territoire du Peak Resonance (automation dynamique sur peaks spectraux) et doivent être préservées intégralement.

**Conformité avec la règle 5.9 du brief :** la séparation des rôles épistémiques (Peak Resonance, CDE Correction, etc.) est respectée même si Feature 6 partage l'EQ8 Peak Resonance pour les bandes 0/7.

**Si la bande 0 ou 7 est déjà utilisée à d'autres fins dans un EQ8 existant :**

Feature 6 :
1. Détecte l'usage existant (lit la valeur Manual et présence d'automations sur ces bandes)
2. Signale l'incompatibilité dans le `HpfLpfApplicationReport` (warnings)
3. Demande confirmation utilisateur avant overwrite (mode interactif) ou skip avec warning (mode batch)
4. Si refus ou skip : cible un autre EQ8 de la track ou crée un nouveau "HPF/LPF Dynamic" EQ8 dédié en aval

### 4.4 Rétrocompatibilité avec .als déjà processés (nouveau en v1.1)

**Cas critique :** si le .als a déjà été processé par Feature 1 (CDE Correction), il existe un EQ8 "CDE Correction" en aval du Peak Resonance. Feature 6 doit :

1. **Ne pas écraser** le travail de Feature 1
2. **Choisir intelligemment** où poser ses automations HPF/LPF :
   - Priorité 1 : EQ8 "Peak Resonance" existant (bandes 0/7 si libres)
   - Priorité 2 : EQ8 "Static Cleanup" existant si présent
   - Priorité 3 : Nouvel EQ8 "HPF/LPF Dynamic" en début de chain
3. **Documenter** le choix dans le `HpfLpfApplicationReport`
4. **Ne jamais** écrire dans l'EQ8 "CDE Correction" pour respecter la séparation épistémique

---

## 5 — API proposée

### 5.1 Module source (nouveau en v1.1)

**Nouveau module :** `mix_analyzer/dynamic_hpf_lpf.py`

Justification : Feature 6 est suffisamment distincte (pas une correction CDE, pas une suppression de résonance) pour mériter son propre module. Évite la pollution de `cde_apply.py`.

**Modules existants utilisés (imports) :**
- `mix_analyzer.als_utils` — `read_locators`, `read_tempo`, helpers XML
- `mix_analyzer.eq8_automation` — helpers d'écriture EQ8 (à confirmer le module exact)
- `mix_analyzer.peak_trajectories` — dataclass `PeakTrajectory`
- `mix_analyzer.cde_apply` — patterns réutilisables (find_or_create EQ8, etc.)

### 5.2 Fonction principale

```python
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

def write_dynamic_hpf_lpf_from_analysis(
    als_path: Path | str,
    track_name: str,
    zone_energy_by_section: dict[str, dict[str, float]],
    peak_trajectories: list[PeakTrajectory],
    spectral_descriptors: dict[str, dict[str, float]],
    locators: list[tuple[float, str]],
    *,
    genre_profile: dict,
    track_type: str,
    hpf_enabled: bool = True,
    lpf_enabled: bool = True,
    target_eq8_username: str = "Peak Resonance",
    transition_crossfade_beats: float = 2.0,
    peak_follow_within_section: bool = False,
    dry_run: bool = False,
) -> "HpfLpfApplicationReport":
    """
    Applique des automations HPF/LPF dynamiques par section sur une track.
    
    Args:
        als_path: Chemin vers le .als (sera modifié sauf si dry_run=True)
        track_name: Nom Ableton de la track (ex: "[H/M] Lead Vocal Shhh")
        zone_energy_by_section: Données depuis _track_zone_energy
        peak_trajectories: Liste depuis _track_peak_trajectories
        spectral_descriptors: Données depuis _track_spectral_descriptors
        locators: Bornes temporelles des sections [(beats, name), ...]
        genre_profile: Profil chargé depuis genre_music_profiles.json
        track_type: Type de la track pour lookup dans le profil
        hpf_enabled: Si False, pas de HPF écrit
        lpf_enabled: Si False, pas de LPF écrit
        target_eq8_username: Nom de l'EQ8 cible
        transition_crossfade_beats: Durée des crossfades entre sections
        peak_follow_within_section: Mode advanced (V2)
        dry_run: Si True, calcule mais n'écrit pas
        
    Returns:
        HpfLpfApplicationReport avec détails des actions
        
    Raises:
        TrackNotFoundError: si track_name absent du .als
        InvalidProfileError: si genre_profile mal formé
        EQ8WriteError: si écriture XML échoue
    """
```

### 5.3 Report dataclass

```python
@dataclass
class HpfLpfApplicationReport:
    """Rapport d'application des automations HPF/LPF dynamiques."""
    applied: bool                                       # True si écriture effective
    track_name: str
    target_eq8_device_id: Optional[str]                # ID du device EQ8 utilisé
    target_eq8_username: str                           # "Peak Resonance" ou autre
    target_eq8_was_created: bool                       # True si nouveau EQ8 créé
    
    hpf_frequencies_by_section: dict[str, float]       # {section_name: freq_hz}
    lpf_frequencies_by_section: dict[str, float]
    
    hpf_bypassed_sections: list[str]                   # Sections où HPF IsOn=False
    lpf_bypassed_sections: list[str]
    
    crossfade_beats_used: float
    envelopes_written: int                             # Nombre total d'enveloppes écrites
    
    warnings: list[str]                                # Avertissements non bloquants
    decisions_log: list[str]                           # Trace des décisions algorithmiques
    
    # Pour tests et debug
    backup_path: Optional[Path] = None                 # Path du backup avant écriture
    dry_run: bool = False
```

### 5.4 Fonctions helpers internes

**Calcul des fréquences :**
- `_compute_hpf_freq_for_section(zone_energy, profile_cap_hz, **kwargs) -> float`
- `_compute_lpf_freq_for_section(zone_energy, profile_min_hz, **kwargs) -> float`
- `_adjust_hpf_for_peaks(hpf_hz, peaks, section_name, **kwargs) -> float`
- `_adjust_lpf_for_peaks(lpf_hz, peaks, section_name, **kwargs) -> float`

**Génération des courbes :**
- `_build_freq_curve_with_crossfades(sections_freq_dict, locators, tempo, crossfade_beats) -> list[tuple[float, float]]`
  - Retourne liste de `(time_beats, freq_hz)` pour l'enveloppe d'automation
- `_build_ison_curve(sections_active_list, locators, tempo, crossfade_beats) -> list[tuple[float, bool]]`
  - Retourne liste de `(time_beats, is_on)` pour l'enveloppe IsOn
- `_compute_crossfade_for_boundary(section_duration_beats, target_crossfade_beats) -> float`

**Manipulation EQ8 :**
- `_find_or_create_target_eq8(tree, track_name, target_username) -> Element`
- `_check_band_availability(eq8_element, band_index) -> tuple[bool, str]`
  - Retourne `(is_available, reason_if_not)`
- `_write_band_automation(eq8_element, band_index, mode, freq_curve, ison_curve, q_value) -> int`
  - Retourne le nombre d'enveloppes écrites

**Validation :**
- `_validate_inputs(als_path, track_name, ...) -> None`
  - Lève des exceptions précises si inputs invalides

### 5.5 Exceptions custom (nouveau en v1.1)

```python
class HpfLpfError(Exception):
    """Base exception pour Feature 6."""

class TrackNotFoundError(HpfLpfError):
    """La track demandée n'existe pas dans le .als."""

class InvalidProfileError(HpfLpfError):
    """Le genre_profile est mal formé ou ne contient pas le track_type."""

class EQ8WriteError(HpfLpfError):
    """Erreur lors de l'écriture XML de l'EQ8."""

class BandUnavailableError(HpfLpfError):
    """La bande cible (0 ou 7) est déjà utilisée et l'utilisateur a refusé l'overwrite."""
```

---

## 6 — CLI wrapper

### 6.1 Script dédié

**Nouveau script :** `scripts/apply_dynamic_hpf_lpf.py`

Justification : ne pas surcharger `apply_cde_corrections.py` qui a déjà sa propre logique CDE. Un script dédié est plus lisible et plus testable.

### 6.2 Mode single track (recommandé par défaut, nouveau en v1.1)

**Cohérence avec le brief méthodologique :** le brief v2.3 (section 4 Phase 3) recommande l'approche track-par-track. Le CLI doit favoriser ce mode.

```bash
python scripts/apply_dynamic_hpf_lpf.py \
    --als "Acid_Drops_Sections_STD.als" \
    --report-xlsx "Acid_Drops_MixAnalyzer_2026-04-22_15-52.xlsx" \
    --track "[H/M] Lead Vocal Shhh" \
    --track-type "Lead Vocal" \
    --genre-profile "docs/brief/genre_music_profiles.json" \
    --genre Industrial \
    --target-eq8 "Peak Resonance" \
    --crossfade-beats 2.0 \
    --dry-run
```

**Flags principaux :**

| Flag | Type | Description |
|---|---|---|
| `--als` | path | Chemin du .als source |
| `--report-xlsx` | path | Rapport Mix Analyzer (pour zone_energy, peaks, descriptors) |
| `--track` | str | Nom Ableton exact de la track |
| `--track-type` | str | Type pour lookup profil (ex: "Lead Vocal", "Kick") |
| `--genre-profile` | path | Chemin vers `genre_music_profiles.json` |
| `--genre` | str | Famille + style (ex: "Industrial") |
| `--target-eq8` | str | Nom UserName de l'EQ8 cible (default: "Peak Resonance") |
| `--crossfade-beats` | float | Durée crossfade (default: 2.0) |
| `--hpf-only` | flag | Écrit seulement HPF, skip LPF |
| `--lpf-only` | flag | Écrit seulement LPF, skip HPF |
| `--no-peak-protection` | flag | Désactive l'ajustement Étape E |
| `--dry-run` | flag | Calcule sans écrire |
| `--yes` | flag | Skip confirmation interactive |
| `--output` | path | Chemin de sortie (default: `<als>_F6.als`) |

**Flags avancés (configurables si besoin) :**

| Flag | Type | Description |
|---|---|---|
| `--sub-negligible-pct` | float | Override DEFAULT_SUB_NEGLIGIBLE_PCT |
| `--bass-negligible-pct` | float | Override DEFAULT_BASS_NEGLIGIBLE_PCT |
| `--peak-threshold-dbfs` | float | Override PEAK_PROTECTION_THRESHOLD_DBFS |
| `--peak-semitones` | float | Override PEAK_PROTECTION_SEMITONES |

### 6.3 Mode batch (avec garde-fou, clarifié en v1.1)

**Disponible mais non recommandé par défaut, conformément au brief v2.3.**

```bash
python scripts/apply_dynamic_hpf_lpf.py \
    --als "Acid_Drops_Sections_STD.als" \
    --report-xlsx "Acid_Drops_MixAnalyzer_2026-04-22_15-52.xlsx" \
    --batch-csv "tracks_to_process.csv" \
    --genre-profile "docs/brief/genre_music_profiles.json" \
    --genre Industrial \
    --dry-run
```

**Format CSV pour `--batch-csv` :**

```csv
track_name,track_type,target_eq8,hpf_enabled,lpf_enabled
[H/M] Lead Vocal Shhh,Lead Vocal,Peak Resonance,true,true
[H/R] Kick 1,Kick,Peak Resonance,true,false
[S/H] Sub Bass,Sub Bass,Peak Resonance,true,true
```

**Garde-fou batch :** le mode batch affiche un avertissement explicite avant exécution :
```
⚠️  Mode batch: 3 tracks vont être processées en série.
    Le brief méthodologique recommande le mode single track pour validation à l'oreille track-par-track.
    Continuer? [y/N]
```

### 6.4 Mode revert

```bash
python scripts/apply_dynamic_hpf_lpf.py \
    --als "Acid_Drops_F6.als" \
    --revert
```

Restaure le backup créé avant la dernière application F6.

### 6.5 Output et logs

**Stdout :** rendu du `HpfLpfApplicationReport` en format lisible (tableau des fréquences par section, warnings, etc.).

**Stderr :** logs détaillés (decisions_log) si `--verbose` activé.

**Exit codes :**
- 0 : succès
- 1 : erreur input (track absente, profil mal formé)
- 2 : erreur écriture .als
- 3 : utilisateur a refusé en mode interactif

---

## 7 — Plan de livraison

**Stratégie anti-timeout (clarifié en v1.1) :** chaque micro-commit est conçu pour ne pas dépasser ~30 minutes de travail Claude Code, avec séparation stricte entre commits de code et commits de tests pour éviter les contextes trop chargés.

**Convention de commits :** format `feat(F6): <description courte>` pour le code, `test(F6): <description courte>` pour les tests.

### F6a — Calcul des fréquences HPF/LPF par section (pur, data-prep)

**Fichiers créés :**
- `mix_analyzer/dynamic_hpf_lpf.py` (skeleton avec dataclass `HpfLpfApplicationReport`, exceptions custom, constants par défaut)
- `mix_analyzer/dynamic_hpf_lpf_helpers.py` (fonctions helpers de calcul)

**Fonctions implémentées :**
- Constants module-level documentées
- `HpfLpfApplicationReport` dataclass + `HpfLpfError` et sous-exceptions
- `_compute_hpf_freq_for_section`
- `_compute_lpf_freq_for_section`
- `_adjust_hpf_for_peaks`
- `_adjust_lpf_for_peaks`
- Helper de chargement zone_energy depuis Excel (réutilise patterns existants)

**Durée :** 1.5h-2h
**Tests :** 6-8 (commit séparé F6a-tests)
**Commits :**
- `feat(F6): per-section HPF/LPF frequency computation helpers`
- `test(F6): unit tests for frequency computation`

### F6b — Génération des curves avec crossfades

**Fichiers modifiés :** `mix_analyzer/dynamic_hpf_lpf_helpers.py`

**Fonctions implémentées :**
- `_build_freq_curve_with_crossfades`
- `_build_ison_curve`
- `_compute_crossfade_for_boundary`

**Durée :** 1h-1.5h
**Tests :** 4-6
**Commits :**
- `feat(F6): curve generation with crossfade transitions`
- `test(F6): unit tests for curve generation`

### F6c — Écriture dans l'EQ8 (bande 0 HPF, bande 7 LPF)

**Fichiers modifiés :** `mix_analyzer/dynamic_hpf_lpf.py`

**Fonctions implémentées :**
- `_find_or_create_target_eq8`
- `_check_band_availability`
- `_write_band_automation`
- Logique de protection des bandes 1-6 existantes
- Gestion rétrocompatibilité (priorité Peak Resonance > Static Cleanup > nouveau EQ8)

**Durée :** 1.5h
**Tests :** 4
**Commits :**
- `feat(F6): write HPF/LPF automations on bands 0 and 7`
- `test(F6): unit tests for EQ8 band writing`

### F6d — Integration function + tests end-to-end

**Fichiers modifiés :** `mix_analyzer/dynamic_hpf_lpf.py`

**Fonctions implémentées :**
- `write_dynamic_hpf_lpf_from_analysis` (fonction publique orchestratrice)
- `_validate_inputs`
- Backup automatique avant écriture
- Logging détaillé dans `decisions_log` du report

**Durée :** 1h
**Tests :** 4-6 (end-to-end avec fixtures `.als` synthétiques)
**Commits :**
- `feat(F6): public API + integration tests`
- `test(F6): end-to-end integration tests`

### F6e — CLI wrapper

**Fichiers créés :**
- `scripts/apply_dynamic_hpf_lpf.py`

**Fonctions implémentées :**
- Parsing des flags
- Chargement des fichiers (rapport, profile, locators)
- Mode single, batch, revert
- Garde-fou batch
- Affichage du report en stdout

**Durée :** 45min-1h
**Tests :** 2-3 (smoke tests CLI)
**Commits :**
- `feat(F6-cli): dynamic HPF/LPF application script`
- `test(F6-cli): smoke tests for CLI`

### Total

**Effort total F6 :** 5.5h-7.5h, ~20-27 tests, **10 commits** (5 code + 5 tests, séparés pour anti-timeout).

---

## 8 — Tests d'acceptation (nouveau en v1.1)

**Critères pour considérer Feature 6 comme "terminée" :**

### 8.1 Tests unitaires
- ✅ Tous les tests unitaires passent (cible ~20)
- ✅ Coverage > 85% sur `dynamic_hpf_lpf.py` et `dynamic_hpf_lpf_helpers.py`

### 8.2 Tests d'intégration
- ✅ Test end-to-end : appliquer F6 sur un `.als` synthétique de référence, vérifier que le `.als` produit s'ouvre dans Ableton sans erreur
- ✅ Test rétrocompatibilité : appliquer F6 sur un `.als` déjà processé par F1, vérifier que les automations CDE Correction sont préservées
- ✅ Test cap profile : vérifier que les fréquences calculées respectent toujours `hpf_max_hz` et `lpf_min_hz`

### 8.3 Tests CLI
- ✅ Mode single track fonctionne sans erreur sur fixture
- ✅ Mode batch demande confirmation avant exécution
- ✅ Mode revert restaure le backup correctement
- ✅ Dry-run produit un report sans modifier le `.als`

### 8.4 Validation terrain (post-livraison code)
- ✅ Application sur 1 track de Acid Drops, validation visuelle dans Ableton
- ✅ A/B écoute statique vs dynamique sur la même track
- ✅ Validation auditive par Alexandre

### 8.5 Documentation
- ✅ Cette spec est mise à jour si l'implémentation diverge
- ✅ `roadmap_features_1_8.md` est mis à jour pour passer F6 de "Planifiée" à "Livrée"
- ✅ `CHANGELOG.md` du repo Mix-Analyzer est enrichi avec l'entrée F6

---

## 9 — Validation terrain (extension de v1.0)

Après livraison F6 (commits + tests d'acceptation passés), tester sur Acid Drops avec le protocole suivant :

### 9.1 Protocole de validation

**Étape 1 — Sélection track**
Choisir une track avec contenu spectral varié à travers les sections. Recommandation : `[H/M] Lead Vocal Shhh` (présent en plusieurs sections, contenu vocal qui devrait bénéficier d'un HPF dynamique).

**Étape 2 — Baseline**
Bounce de la track avec son état actuel (HPF statique ou aucun HPF). Re-run Mix Analyzer sur le full mix pour baseline Mix Health Score.

**Étape 3 — Application F6**
```bash
python scripts/apply_dynamic_hpf_lpf.py \
    --als "Acid_Drops_Sections_STD.als" \
    --report-xlsx "Acid_Drops_MixAnalyzer_2026-04-22_15-52.xlsx" \
    --track "[H/M] Lead Vocal Shhh" \
    --track-type "Lead Vocal" \
    --genre-profile "docs/brief/genre_music_profiles.json" \
    --genre Industrial \
    --dry-run
```
Examiner le report (fréquences calculées par section).

Si OK : retirer `--dry-run` et exécuter.

**Étape 4 — Vérification visuelle**
Ouvrir le `.als` modifié dans Ableton, vérifier dans la track :
- L'EQ8 cible contient bien des automations Freq sur les bandes 0 et 7
- Les automations s'alignent avec les Locators
- Les autres bandes (1-6) sont préservées intactes

**Étape 5 — Bounce + re-Mix Analyzer**
Bounce le full mix avec F6 appliquée. Re-run Mix Analyzer. Comparer Mix Health Score et zones spécifiques.

**Étape 6 — A/B écoute**
Comparer auditivement avec et sans F6 sur la track ciblée. Critère de validation : "la voix gagne-t-elle en chaleur dans les sections calmes sans perdre la dégage dans les drops ?"

**Étape 7 — Décision**
- **Si validation positive** : appliquer F6 sur d'autres tracks (mode track-par-track)
- **Si validation négative** : revert via `--revert`, ajuster les paramètres (seuils, crossfade), re-tester
- **Si comportement inattendu** : investiguer logs `decisions_log`, ajuster algorithme si nécessaire (modification de spec puis dev)

### 9.2 Documentation post-validation

Indépendamment du résultat, **mettre à jour le `Acid_Drops_CHANGELOG.md`** avec :
- Date d'application F6
- Track concernée
- Fréquences appliquées par section
- Verdict (keep / adjust / revert)
- Notes auditives

---

## 10 — Risques techniques identifiés

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Automation IsOn cause clicks au bypass | Moyenne | Audible | Utiliser automation Freq très haute / très basse plutôt que bypass, ou crossfade Gain. **Décision finale dépend de Q4.** |
| Bande 0 ou 7 déjà utilisée par un autre plugin | Faible | Bloquant | Détecter, avertir, offrir création nouvelle EQ8 dédiée (voir section 4.3) |
| Zone energy absente pour section (section trop courte < 3s) | Moyenne | Calcul erroné | Fallback sur moyenne des sections voisines |
| Tracks sans peak trajectories matchées | Faible | Sous-optimal | HPF conservative à `hpf_max_hz` du profil par défaut |
| Crossfades qui débordent sections courtes | Moyenne | Glitch sonore | Réduction automatique proportionnelle (`_compute_crossfade_for_boundary`) |
| Dérive float des fréquences dans l'XML | Quasi-certaine | Visuel | Reuse validation EQ8 existante (`_freq_to_eq8_value` + tolerance 0.01) |
| Conflit avec EQ8 CDE Correction de Feature 1 | Faible | Logique | Section 4.4 — ne jamais écrire dans CDE Correction |
| Track inexistante dans le .als | Faible | Erreur | `TrackNotFoundError` levée immédiatement avec message clair |
| Genre profile mal formé | Faible | Erreur | `InvalidProfileError` + validation au chargement |
| Test track-par-track contre intuitif pour utilisateurs habitués au batch | Moyenne | UX | Garde-fou batch + warning + documentation |

---

## 11 — Hors scope F6 v1

**Reportés à F6 v2 ou autres features :**

- **Peak-follow intra-section complexe** → `peak_follow_within_section=True` paramètre exposé mais pas implémenté en v1, ou implémentation simpliste. Implémentation complète en F6 v2 si validation terrain confirme l'utilité.
- **Consolidation automatique avec autres EQ8 existants** → Feature 8 (EQ8 Consolidation), voir `feature_8_eq8_consolidation.md`
- **Dynamic shelf / Dynamic bell pour enhancement musical** → Feature 7 (Dynamic Musical Enhancement), voir `feature_7_dynamic_enhancement.md`
- **Intégration des profils par genre au cœur du CDE engine** → Feature 9 (future, non specifiée)
- **GUI/visualisation des courbes calculées** → outil externe, hors scope
- **Auto-détection du track_type via ML/heuristique avancée** → manuel pour l'instant, possibilité future si beaucoup de tracks à processer

---

## 12 — Dépendances validation utilisateur avant dev

**Avant de lancer le développement de F6, l'utilisateur (Alexandre) doit trancher les questions suivantes.** Sans ces réponses, Claude Code va prendre des décisions par défaut potentiellement incorrectes.

### Q1 — Convention "bande 0 = HPF, bande 7 = LPF"

**Question :** acceptes-tu cette convention par défaut pour Feature 6 ?

**Trade-offs :**
- **Pour :** économie de bandes (pas besoin d'EQ8 supplémentaire), cohérent avec règle 3 EQ8 max
- **Contre :** "pollue" l'EQ8 Peak Resonance qui devient mixte (peaks individuels + HPF/LPF)

**Recommandation :** Oui (convention par défaut). Si validée, à formaliser dans le brief méthodologique en v2.4.

**Réponse Alexandre :** _____ (à remplir)

### Q2 — Cible EQ8 par défaut

**Question :** Feature 6 doit-elle écrire dans le "Peak Resonance" existant, ou créer un nouveau EQ8 "HPF/LPF Dynamic" dédié ?

**Trade-offs :**
- **Peak Resonance existant :** moins d'EQ8 (1 seul), plus simple, mais EQ8 mixte
- **Nouveau "HPF/LPF Dynamic" :** séparation épistémique pure, mais ajoute un EQ8 (passe à 4 EQ8 sur certaines tracks)

**Recommandation :** Peak Resonance existant par défaut, fallback nouveau EQ8 si Peak Resonance absent.

**Réponse Alexandre :** _____ (à remplir)

### Q3 — Crossfade par défaut

**Question :** transition crossfade par défaut de 2.0 beats est-elle appropriée ?

**Trade-offs :**
- **2.0 beats (~0.94s à 128 BPM) :** transition douce, peu audible
- **1.0 beat :** plus réactif mais risque d'être audible
- **4.0 beats :** très transparent mais lent à réagir aux changements de section

**Recommandation :** 2.0 beats par défaut, configurable via `--crossfade-beats`.

**Réponse Alexandre :** _____ (à remplir)

### Q4 — Stratégie IsOn

**Question :** quand une section n'a "rien à couper" (track silencieuse en bas pour HPF), faut-il :

**Option A —** `IsOn=False` pour cette section (économise CPU mais risque clic)
**Option B —** `IsOn=True` toujours, avec `Freq=20Hz` (pas d'effet audible mais toujours actif)

**Trade-offs :**
- Option A : économie CPU minime, mais automation IsOn peut causer clicks au switch
- Option B : continuité d'automation Freq, plus sûr, économie CPU négligeable de toute façon (EQ Eight est très léger)

**Recommandation :** Option B (toujours IsOn=True, Freq conservative). Plus sûr.

**Réponse Alexandre :** _____ (à remplir)

### Q5 — Priorité dans la roadmap

**Question :** F6 doit-elle être développée avant ou après F1.5 (sidechain) et F7 (enhancement) ?

**Roadmap suggérée actuelle (`roadmap_features_1_8.md`) :**
1. F1.5 (sidechain) en premier
2. F6 (HPF/LPF dynamique) en deuxième
3. F7 (enhancement) en troisième
4. F8 (consolidation) en dernier

**Recommandation :** suivre la roadmap actuelle. F6 après F1.5.

**Réponse Alexandre :** _____ (à remplir)

---

## 13 — Procédure d'évolution de cette spec

Cette spec suit `documentation_discipline.md` section 4 :

1. Lire la spec intégralement avant modification
2. Identifier précisément ce qui doit changer
3. Si suppression ou restructuration → demander confirmation
4. Modifier in-place en préservant l'existant
5. Incrémenter version + enrichir historique
6. Signaler nouveautés avec annotation "(nouveau en vX.Y)" ou "(clarifié en vX.Y)"
7. Tester complétude
8. Archiver ancienne version dans `docs/archive/`
9. Livrer avec annonce de changements

**Triggers d'évolution typiques pour une spec de feature :**
- Réponses Q1-Q5 reçues → enrichir spec avec décisions validées
- Découverte technique pendant dev → mise à jour algorithme
- Validation terrain négative → ajustement seuils ou logique
- Nouveau cas d'usage identifié → extension scope

---

## 14 — Référence rapide (quick card, nouveau en v1.1)

**Statut :** Spec en attente de validation utilisateur (Q1-Q5)

**Effort estimé total :** 5.5h-7.5h, ~20-27 tests, 10 commits

**Modules à créer :**
- `mix_analyzer/dynamic_hpf_lpf.py` (fonction publique + dataclasses + exceptions)
- `mix_analyzer/dynamic_hpf_lpf_helpers.py` (helpers de calcul)
- `scripts/apply_dynamic_hpf_lpf.py` (CLI)

**Inputs requis :**
- `.als` source
- Rapport Mix Analyzer Excel (zone_energy, peak_trajectories, spectral_descriptors)
- `genre_music_profiles.json`
- Locators du projet

**Output :**
- `.als` modifié avec automations HPF/LPF sur bandes 0/7 d'EQ8 cible
- `HpfLpfApplicationReport` détaillé

**Dépendances roadmap :**
- F1 livrée ✅ (cohérence rétrocompatibilité)
- F1.5 souhaitable mais pas bloquante
- F7 et F8 viendront après

**Documents associés :**
- `qrust_professional_context.md` section 4.1 (philosophie 100% dynamique)
- `mix_engineer_brief_v2_3.md` sections 4 Phase 3, 5.10
- `roadmap_features_1_8.md`
- `documentation_discipline.md`

---

**Fin spec Feature 6 v1.1. Validation utilisateur attendue sur Q1-Q5 avant démarrage dev. Une fois Q1-Q5 résolues, incrémenter la spec en v1.2 avec les décisions intégrées et démarrer le développement selon le plan de livraison de la section 7.**
