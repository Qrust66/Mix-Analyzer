# Feature 7 — Dynamic musical EQ / enhancement

**Version spec :** 1.1
**Date dernière modification :** 2026-04-23
**Statut :** Planifiée, non démarrée — Q1-Q4 en attente de validation utilisateur (voir section 13)
**Hérite de :** `documentation_discipline.md` (règles de rédaction), `qrust_professional_context.md` (philosophie 100% dynamique justifiant la feature)
**Brief méthodologique de référence :** `mix_engineer_brief_v2_3.md` (notamment règle 5.9 EQ8 max, règle 5.10 dynamique par défaut, Phase 6 enhancement dynamique)
**Feature parent dans la roadmap :** voir `roadmap_features_1_8.md`
**Dépendances technique :** Feature 1 livrée ✅, Feature 6 souhaitable mais pas bloquante

**Historique d'évolution de la spec :**
- v1.0 — création initiale (2026-04-23 après-midi). Première rédaction post-validation philosophie 100% dynamique. Couvrait objectif, contraste avec F1/F6, cas d'usage, données consommées, algorithme par mode, écriture EQ8, API, CLI YAML, plan de livraison, validation, risques, hors scope, questions Q1-Q4.
- v1.1 (ce document) — audit complétude pour Claude Code. Préservation intégrale du contenu v1.0 + 17 ajouts/clarifications signalés explicitement : header conforme à `documentation_discipline.md`, correction effort estimé incohérent (6-7h confirmé), redesign de `EnhancementIntent` avec discriminator pour lever ambiguïté, spécification complète du mode `peaks_dense_mix` (formats, normalisation, formule), clarification dépendance Q1-de-F6 pour bandes 0/7, logique de gestion de fréquences proches inter-intents, modes CLI étendus (single intent, revert, garde-fou batch), spécification du format YAML/JSON avec schema, définition des modules sources, stratégie anti-timeout détaillée (séparation code/tests), ajout section "Tests d'acceptation", ajout section "Rétrocompatibilité", validation des Mode IDs EQ8 contre device mapping JSON, clarification de l'optimisation 5.4 (renommée 5.5 et reformulée), résolution explicite de l'ambiguïté `peaks_dense_mix` dans le scope v1, ajout quick card.

**Principe de préservation :** cette spec préserve intégralement le contenu de v1.0. Aucune section, aucun exemple, aucune décision validée n'a été supprimée — seulement étendue ou clarifiée. Les ajouts et clarifications de v1.1 sont signalés explicitement avec annotation "(nouveau en v1.1)" ou "(clarifié en v1.1)".

**Effort estimé :** 6h-7h Claude Code, ~25-34 tests, 12 micro-commits (6 code + 6 tests, séparés pour anti-timeout). **Note v1.1 :** correction de l'incohérence v1.0 qui mentionnait "4-6 heures / 5-8 micro-commits" en header puis "6-7h / 6 micro-commits" en Section 8 — la valeur correcte est 6-7h, désormais 12 commits avec séparation code/tests.

---

## 1 — Objectif et justification

### 1.1 Ce que fait la feature

Produire des automations contextuelles pour les **boosts musicaux** (présence, air, shelf, excitation harmonique) qui s'adaptent par section à l'intention artistique plutôt qu'être fixes.

### 1.2 Contraste avec les features précédentes

| Feature | Type | Rôle |
|---|---|---|
| **Feature 1 (CDE)** | Réducteur | Corrige les problèmes de masking et accumulation inter-track |
| **Feature 6 (HPF/LPF)** | Réducteur | Nettoie les extrêmes du spectre par section |
| **Feature 7 (Enhancement)** | **Additif** | **Enrichit, colore, met en avant musicalement** |

Feature 7 est la seule feature **additive** de la roadmap. Là où F1 et F6 enlèvent ce qui ne va pas, F7 ajoute ce qui améliore. Cette différence de nature implique des règles différentes :
- Pas de cap "réducteur" mais un cap "boost maximum" du genre profile
- Risque de mix déséquilibré si abusée (alors que F1/F6 ont un risque inverse de mix maigre)
- Justification artistique requise (pas juste une analyse spectrale)

### 1.3 Pourquoi cette feature

Dans un mix industrial Qrust, certains enhancements sont désirables mais pas constants :

- Un boost de présence 3 kHz sur la voix pour couper dans le mix — utile dans les drops denses, superflu dans les breakdowns solo
- Un shelf d'air à 12 kHz sur les cymbales — bénéfique en chorus quand tout remplit, excessif en intro quand l'auditeur a déjà l'attention
- Une excitation harmonique sur un lead — puissante en chorus 2 pour le climax, trop agressive en intro

Un enhancement statique ignore cette dynamique. Un enhancement dynamique renforce le morceau dans les moments où ça aide, s'efface là où ça gênerait.

### 1.4 Ancrage dans la philosophie Qrust

Cette feature implémente la **règle 5.10 du `mix_engineer_brief_v2_3.md`** ("traitement dynamique par défaut") pour le cas spécifique des enhancements. Elle complète Features 1 et 6 pour réaliser la vision "100% dynamique" :

- Toute correction (F1) : dynamique par section ou peak-follow
- Toute coupure HPF/LPF (F6) : dynamique par section
- Tout enhancement (F7) : dynamique par section ou densité

**Sans Feature 7 :**
- Soit les enhancements sont posés statiquement → viole la philosophie
- Soit ils sont automatisés manuellement dans Live → lourd, error-prone
- Soit ils sont absents → mix moins expressif

### 1.5 Résultat attendu

Une fonction `write_dynamic_enhancement_from_intent` qui :

1. Reçoit une **intention d'enhancement** (ex: "+2 dB à 3 kHz Q=1.5 pour présence voix")
2. Reçoit une **carte de sections où cet enhancement doit être actif** (ex: Drops et Chorus uniquement)
3. Reçoit des métriques Mix Analyzer pour ajuster l'intensité par section selon le contexte mix
4. Écrit dans un EQ8 `Musical Enhancement` dédié (4ème EQ8 autorisé par la règle 5.9 du brief) les automations qui activent/désactivent ou modulent l'enhancement selon la section

---

## 2 — Cas d'usage typiques

### 2.1 Cas 1 — Boost de présence voix conditionnel

**Intention utilisateur :** "La voix a besoin de présence 3 kHz quand elle se bat contre le kick, pas quand elle est seule."

**Configuration :**
- Enhancement : shelf high ou bell à 3 kHz, +3 dB, Q 1.5
- Sections actives : Drop 1, Drop 2, Chorus 1, Chorus 2
- Sections inactives : Intro, Build 1, Break 1, Breakdown 1, Outro

**Comportement F7 :** écrit une automation Gain qui alterne 0 dB ↔ +3 dB selon la section, avec crossfade pour éviter les pops.

### 2.2 Cas 2 — Air progressif sur climax

**Intention utilisateur :** "Ajouter de l'air progressivement jusqu'au Climax."

**Configuration :**
- Enhancement : shelf high à 12 kHz, gain variable
- Intro/Build : 0 dB
- Chorus 1 : +1 dB
- Drop 2 : +1.5 dB
- Chorus 2 : +2 dB
- Climax : +3 dB
- Outro : +0.5 dB

**Comportement F7 :** écrit une automation Gain qui monte progressivement section par section.

### 2.3 Cas 3 — Intensité modulée par densité du mix

**Intention utilisateur :** "Plus le mix est dense spectralement autour de 3 kHz, plus l'enhancement est nécessaire pour faire ressortir cet élément."

**Comportement F7 :** lit `Freq Conflicts` matrix de Mix Analyzer pour quantifier la densité spectrale autour de la `frequency_hz` de l'enhancement par section, calcule l'intensité d'enhancement proportionnelle entre `gain_db_range[0]` et `gain_db_range[1]`.

**Note v1.1 :** ce mode `peaks_dense_mix` est en **scope v1 mais marqué experimental**. Le mode `explicit` reste recommandé par défaut pour la prédictibilité. Voir section 4.4 pour spec détaillée et section 13 Q3 pour validation utilisateur.

---

## 3 — Données consommées

### 3.1 Inputs principaux

**Source 1 — Intention d'enhancement (input utilisateur)**

Dataclass `EnhancementIntent` redessinée en v1.1 pour lever l'ambiguïté de v1.0 (mélange `gain_db_by_section` et `gain_db_profile`). Voir section 3.4 pour la définition complète.

**Source 2 — Rapport Mix Analyzer (Excel)**

Pour le profil `peaks_dense_mix` : lecture de la densité spectrale par section.

**Sheets requises :**
- `Freq Conflicts` — matrice de masking inter-tracks
- `_track_multiband_time` — énergie par bande dans le temps
- `_track_zone_energy` — énergie par zone et section (déjà consommé par F6)

**Source 3 — Locators (via `als_utils.read_locators`)**

Bornes temporelles des sections pour aligner les automations.

**Format :** liste de tuples `(time_beats: float, name: str)`.

**Source 4 — `genre_music_profiles.json`**

Caps par track type :
- `presence_boost_max_db` : plafond absolu sur les boosts de présence
- `air_boost_max_db` : plafond absolu sur les boosts d'air (à confirmer dans le profil)
- `shelf_boost_max_db` : plafond générique pour shelfs (à confirmer)
- Notes naturelles sur ce qui est "sacré" ou "à protéger"

**Logique de cap (clarifié en v1.1) :** Feature 7 cherche le cap le plus spécifique applicable :
1. Si la fréquence de l'intent est entre 2-5 kHz → utiliser `presence_boost_max_db`
2. Si la fréquence est > 8 kHz → utiliser `air_boost_max_db`
3. Sinon → utiliser `shelf_boost_max_db` ou un cap générique

Si l'intention utilisateur propose +4 dB mais le profil dit max +2.5 dB pour ce track type et cette zone, l'enhancement est cappé à +2.5 dB avec warning explicite dans le report.

**Source 5 — Tempo du projet** (nouveau en v1.1)

Lu depuis le `.als` via `als_utils.read_tempo`. Nécessaire pour les conversions beats → samples.

### 3.2 Source 1 détaillée — Format YAML/JSON pour la config (clarifié en v1.1)

**Schema YAML versioned :**

```yaml
# enhancement_config.yaml
version: "1.0"  # Version du schema, validée au load

enhancements:
  - name: "Voice presence boost"
    target_track: "[H/M] Lead Vocal Shhh"
    mode: "bell"  # bell | high_shelf | low_shelf | notch
    frequency_hz: 3000
    q_factor: 1.5
    
    # Une et une seule des trois options suivantes :
    gain_strategy: "explicit"  # explicit | progressive | section_lock | peaks_dense_mix
    
    # Si gain_strategy == "explicit"
    gain_db_by_section:
      Drop_1: 3.0
      Drop_2: 3.5
      Chorus_1: 2.5
      Chorus_2: 2.5
      Outro: 1.0
    
    # Si gain_strategy == "progressive" ou "section_lock" ou "peaks_dense_mix"
    # gain_db_range: [min, max]
    # active_sections: [Drop_1, Drop_2, Chorus_1, Chorus_2]
```

**Validation au chargement (nouveau en v1.1) :**

- `version` doit être présent et reconnu (lever `UnsupportedSchemaVersionError` sinon)
- Chaque entry doit avoir `name`, `target_track`, `mode`, `frequency_hz`, `q_factor`, `gain_strategy`
- Selon `gain_strategy`, les champs additionnels requis sont vérifiés
- Les valeurs `mode` doivent être dans `{bell, high_shelf, low_shelf, notch}`
- `frequency_hz` doit être dans `[20, 20000]`
- `q_factor` doit être dans `[0.1, 18.0]`
- Les valeurs de gain doivent être dans `[-12, +12]` (sera ensuite cappé par genre profile)

**Évolution future du schema :** nouvelle version `version: "1.1"` à introduire si ajouts non rétrocompatibles. Le loader doit gérer plusieurs versions en parallèle.

**JSON équivalent supporté :** même schema, syntaxe JSON. Détection automatique par extension de fichier (`.yaml`, `.yml`, `.json`).

### 3.3 Pourquoi YAML par défaut (justification, nouveau en v1.1)

**YAML est recommandé par défaut** pour la config Feature 7 parce que :
- Plus lisible humainement (syntaxe naturelle)
- Permet les commentaires (utile pour documenter pourquoi un enhancement est configuré)
- Multiline strings pratiques pour les notes
- Standard dans les outils de prod (Ansible, Kubernetes, GitHub Actions)

**JSON également supporté** pour compatibilité programmatique (génération automatique, intégration avec autres outils).

À valider en Q1 (section 13).

### 3.4 Définition complète de `EnhancementIntent` (redessinée en v1.1)

**Problème de v1.0 :** la dataclass mélangeait deux modes (gain explicite vs gain calculé par profile) sans discriminator clair, créant ambiguïté pour Claude Code.

**Solution v1.1 :** un seul champ `gain_strategy` agit comme discriminator, et selon sa valeur, des champs additionnels sont requis.

```python
from dataclasses import dataclass, field
from typing import Optional, Literal
from enum import Enum

class EnhancementMode(str, Enum):
    BELL = "bell"
    HIGH_SHELF = "high_shelf"
    LOW_SHELF = "low_shelf"
    NOTCH = "notch"  # Note : notch n'est techniquement pas un enhancement, à valider

class GainStrategy(str, Enum):
    EXPLICIT = "explicit"             # Valeurs explicites par section
    PROGRESSIVE = "progressive"       # Interpolation linéaire entre min et max
    SECTION_LOCK = "section_lock"     # Binaire on/off avec valeur target
    PEAKS_DENSE_MIX = "peaks_dense_mix"  # Adaptatif à la densité

@dataclass
class EnhancementIntent:
    """Description d'un enhancement musical à appliquer dynamiquement."""
    
    # Champs obligatoires de base
    name: str                                      # Label descriptif ex: "Voice presence boost"
    target_track: str                              # Nom Ableton de la track
    mode: EnhancementMode                          # Type de bande EQ
    frequency_hz: float                            # Fréquence centrale (20-20000)
    q_factor: float                                # Largeur (0.1-18.0)
    gain_strategy: GainStrategy                    # Discriminator
    
    # Champs requis selon gain_strategy
    gain_db_by_section: Optional[dict[str, float]] = None  # Si explicit
    gain_db_range: Optional[tuple[float, float]] = None    # Si non-explicit
    active_sections: Optional[list[str]] = None            # Si non-explicit (sauf peaks_dense_mix qui prend toutes les sections)
    
    # Champs optionnels avec défauts
    crossfade_beats: float = 2.0
    
    def __post_init__(self):
        """Validation après création — lève une exception si configuration invalide."""
        if self.gain_strategy == GainStrategy.EXPLICIT:
            if self.gain_db_by_section is None or len(self.gain_db_by_section) == 0:
                raise ValueError(
                    f"EnhancementIntent '{self.name}': gain_strategy=explicit "
                    "requires non-empty gain_db_by_section"
                )
        elif self.gain_strategy in (GainStrategy.PROGRESSIVE, GainStrategy.SECTION_LOCK):
            if self.gain_db_range is None:
                raise ValueError(
                    f"EnhancementIntent '{self.name}': gain_strategy={self.gain_strategy.value} "
                    "requires gain_db_range"
                )
            if self.active_sections is None or len(self.active_sections) == 0:
                raise ValueError(
                    f"EnhancementIntent '{self.name}': gain_strategy={self.gain_strategy.value} "
                    "requires non-empty active_sections"
                )
        elif self.gain_strategy == GainStrategy.PEAKS_DENSE_MIX:
            if self.gain_db_range is None:
                raise ValueError(
                    f"EnhancementIntent '{self.name}': gain_strategy=peaks_dense_mix "
                    "requires gain_db_range"
                )
        
        # Validation des bornes
        if not (20 <= self.frequency_hz <= 20000):
            raise ValueError(f"frequency_hz {self.frequency_hz} outside [20, 20000]")
        if not (0.1 <= self.q_factor <= 18.0):
            raise ValueError(f"q_factor {self.q_factor} outside [0.1, 18.0]")
```

**Avantage :** Claude Code reçoit une dataclass auto-validante. Configuration invalide = exception claire à l'instantiation.

---

## 4 — Algorithme de modulation par section

### 4.1 Mode "explicit" (utilisateur fournit gain_db_by_section)

**Comportement :** mapping direct des valeurs fournies vers les sections nommées.

**Sections non listées dans `gain_db_by_section` :** gain = 0 dB (enhancement inactif).

**Crossfade :** entre sections pour transitions douces (durée = `crossfade_beats` du intent).

**Cap par genre_profile :** si une valeur dépasse le cap applicable, capper avec warning.

**Algorithme :**

```python
def _compute_gains_for_explicit_mode(
    intent: EnhancementIntent,
    all_sections: list[str],
    genre_profile_cap_db: float,
) -> tuple[dict[str, float], list[str]]:
    """Returns (gain_by_section, warnings)."""
    warnings = []
    result = {}
    
    for section in all_sections:
        if section in intent.gain_db_by_section:
            requested = intent.gain_db_by_section[section]
            if requested > genre_profile_cap_db:
                result[section] = genre_profile_cap_db
                warnings.append(
                    f"Section {section}: gain {requested}dB capped to {genre_profile_cap_db}dB by genre profile"
                )
            else:
                result[section] = requested
        else:
            result[section] = 0.0  # Enhancement inactif sur cette section
    
    return result, warnings
```

### 4.2 Mode "progressive" (interpolation linéaire)

**Comportement :** interpolation linéaire du gain entre les sections actives selon l'ordre temporel.

- Gain commence à `gain_db_range[0]` sur la première section active
- Gain atteint `gain_db_range[1]` sur la dernière section active
- Sections intermédiaires actives : interpolation linéaire selon leur position
- Sections non actives : gain = 0 dB

**Algorithme :**

```python
def _compute_gains_for_progressive_mode(
    intent: EnhancementIntent,
    all_sections: list[str],
    genre_profile_cap_db: float,
) -> tuple[dict[str, float], list[str]]:
    """Returns (gain_by_section, warnings)."""
    warnings = []
    result = {}
    
    # Filtrer les sections actives qui existent réellement dans le projet
    active_in_project = [s for s in intent.active_sections if s in all_sections]
    if len(active_in_project) == 0:
        warnings.append(f"Intent '{intent.name}': no active sections found in project")
        return {s: 0.0 for s in all_sections}, warnings
    
    if len(active_in_project) == 1:
        # Une seule section active → gain = max
        single_gain = min(intent.gain_db_range[1], genre_profile_cap_db)
        if single_gain != intent.gain_db_range[1]:
            warnings.append(f"Section {active_in_project[0]}: capped to {single_gain}dB")
        result = {s: 0.0 for s in all_sections}
        result[active_in_project[0]] = single_gain
        return result, warnings
    
    # Interpolation entre première et dernière active
    n = len(active_in_project)
    for i, section in enumerate(active_in_project):
        # i=0 → gain_min, i=n-1 → gain_max
        ratio = i / (n - 1)
        gain = intent.gain_db_range[0] + ratio * (intent.gain_db_range[1] - intent.gain_db_range[0])
        gain = min(gain, genre_profile_cap_db)
        if gain != intent.gain_db_range[0] + ratio * (intent.gain_db_range[1] - intent.gain_db_range[0]):
            warnings.append(f"Section {section}: capped to {gain}dB")
        result[section] = gain
    
    # Sections non actives → 0 dB
    for s in all_sections:
        if s not in result:
            result[s] = 0.0
    
    return result, warnings
```

### 4.3 Mode "section_lock" (on/off binaire)

**Comportement :** dans les sections listées comme actives, gain = `gain_db_range[1]` (max). Dans les autres, gain = 0 dB.

`gain_db_range[0]` est inutilisé en mode section_lock (mais requis pour la dataclass — pourrait être ignoré ou validé séparément).

**Algorithme :**

```python
def _compute_gains_for_section_lock_mode(
    intent: EnhancementIntent,
    all_sections: list[str],
    genre_profile_cap_db: float,
) -> tuple[dict[str, float], list[str]]:
    """Returns (gain_by_section, warnings)."""
    warnings = []
    result = {}
    
    target_gain = min(intent.gain_db_range[1], genre_profile_cap_db)
    if target_gain != intent.gain_db_range[1]:
        warnings.append(
            f"Intent '{intent.name}': target gain capped from {intent.gain_db_range[1]}dB to {target_gain}dB"
        )
    
    for section in all_sections:
        if section in intent.active_sections:
            result[section] = target_gain
        else:
            result[section] = 0.0
    
    return result, warnings
```

### 4.4 Mode "peaks_dense_mix" (adaptatif à la densité — clarifié en v1.1)

**Comportement :** pour chaque section, calculer la densité spectrale autour de `frequency_hz` du intent et moduler le gain proportionnellement.

**Spec détaillée du calcul de densité (nouveau en v1.1) :**

**Étape A — Définir la zone de mesure**

Autour de `intent.frequency_hz`, considérer une bande d'analyse de `± Q_zone` semitones. Q_zone par défaut = 6 semitones (1/2 octave de chaque côté), configurable.

**Étape B — Lire la matrice Freq Conflicts**

La matrice `Freq Conflicts` du rapport Mix Analyzer contient, par section et par bande de fréquence, le nombre et l'intensité des conflits de masking entre tracks.

**Format attendu (à confirmer contre l'implémentation Mix Analyzer réelle) :**
```python
freq_conflicts: dict[str, dict[str, dict]]
# {section_name: {freq_band_label: {'n_tracks': int, 'severity': float, 'tracks': list[str]}}}
```

**Étape C — Calculer la densité brute par section**

Pour chaque section, sommer le nombre de tracks émettant dans la zone de mesure, pondéré par leur sévérité de conflit :

```python
def _compute_raw_density(
    section_name: str,
    intent_frequency_hz: float,
    zone_semitones: float,
    freq_conflicts: dict,
) -> float:
    """Densité brute = somme pondérée du nombre de tracks dans la zone."""
    freq_min = intent_frequency_hz * (2 ** (-zone_semitones / 12))
    freq_max = intent_frequency_hz * (2 ** (+zone_semitones / 12))
    
    section_data = freq_conflicts.get(section_name, {})
    raw_density = 0.0
    
    for band_label, band_data in section_data.items():
        band_freq = _parse_band_freq(band_label)  # Helper à implémenter
        if freq_min <= band_freq <= freq_max:
            n_tracks = band_data.get('n_tracks', 0)
            severity = band_data.get('severity', 1.0)
            raw_density += n_tracks * severity
    
    return raw_density
```

**Étape D — Normaliser la densité entre 0 et 1**

Calculer la densité brute pour toutes les sections du projet, puis normaliser :

```python
def _normalize_densities(raw_densities: dict[str, float]) -> dict[str, float]:
    """Normalise entre 0 et 1 par rapport à la section la plus dense."""
    if not raw_densities:
        return {}
    max_density = max(raw_densities.values())
    if max_density == 0:
        return {s: 0.0 for s in raw_densities}
    return {s: d / max_density for s, d in raw_densities.items()}
```

**Étape E — Calculer le gain par section**

```python
def _compute_gain_from_density(
    normalized_density: float,
    gain_range: tuple[float, float],
) -> float:
    """Mappe densité normalisée vers gain en interpolation linéaire."""
    return gain_range[0] + normalized_density * (gain_range[1] - gain_range[0])
```

**Étape F — Cap par genre profile**

```python
gain_capped = min(gain, genre_profile_cap_db)
```

**Algorithme complet :**

```python
def _compute_gains_for_peaks_dense_mode(
    intent: EnhancementIntent,
    all_sections: list[str],
    freq_conflicts: dict,
    genre_profile_cap_db: float,
    *,
    zone_semitones: float = 6.0,
) -> tuple[dict[str, float], list[str]]:
    """Returns (gain_by_section, warnings)."""
    warnings = []
    
    # Calculer densités brutes pour toutes les sections
    raw_densities = {
        s: _compute_raw_density(s, intent.frequency_hz, zone_semitones, freq_conflicts)
        for s in all_sections
    }
    
    if all(d == 0 for d in raw_densities.values()):
        warnings.append(
            f"Intent '{intent.name}': no spectral density detected around {intent.frequency_hz}Hz "
            f"in any section. Enhancement will be inactive."
        )
        return {s: 0.0 for s in all_sections}, warnings
    
    # Normaliser
    normalized = _normalize_densities(raw_densities)
    
    # Calculer gain par section
    result = {}
    for section in all_sections:
        gain = _compute_gain_from_density(normalized[section], intent.gain_db_range)
        gain_capped = min(gain, genre_profile_cap_db)
        if gain_capped != gain:
            warnings.append(f"Section {section}: capped to {gain_capped}dB")
        result[section] = gain_capped
    
    return result, warnings
```

**Statut du mode peaks_dense_mix :** **experimental en v1**. Le mode est livré mais doit être validé sur Acid Drops avant d'être recommandé en production. Voir Q3 section 13.

### 4.5 Crossfades entre sections

Identique à F6 section 3.3 : crossfade linéaire de `crossfade_beats` autour des frontières de section, réduit proportionnellement pour les sections courtes.

**Reuse :** la fonction `_compute_crossfade_for_boundary` de F6 (si livrée) peut être partagée. Sinon, dupliquer en interne.

---

## 5 — Écriture dans l'EQ8

### 5.1 Cible : EQ8 Musical Enhancement

Par convention Qrust (`mix_engineer_brief_v2_3.md` section 5.9), c'est le **4ème EQ8 autorisé** sur une track, placé après les effets non-correctifs (saturation, compression, sidechain) mais avant le glue final.

**Position dans la device chain :**
```
Static Cleanup → Peak Resonance → CDE Correction → Saturation → Compression → Sidechain → [Musical Enhancement] → Glue → Limiter
```

Feature 7 :
- Crée cet EQ8 s'il n'existe pas sur la track cible
- Réutilise l'existant pour ajouter une nouvelle bande si déjà présent
- Insère au bon endroit dans la chain (après les effets non-correctifs, avant glue)

**Nom :** `"Musical Enhancement"` au début, puis `"Musical Enhancement ({n} bands)"` quand plusieurs bandes ajoutées (similaire au nommage CDE Correction par F1).

### 5.2 Allocation des bandes

**Bandes 1-6 disponibles** pour les enhancements F7.

**Bandes 0 et 7 (clarifié en v1.1) :** par cohérence avec la convention F6 (HPF bande 0, LPF bande 7), ces bandes restent réservées même dans l'EQ8 Musical Enhancement. **Cette convention dépend de la validation Q1 de F6.** Si Q1 de F6 est rejetée, cette assomption tombe et les bandes 0/7 deviennent disponibles pour F7 enhancements.

**Allocation :** Feature 7 trouve la première bande libre (1 → 6) via `_find_available_band` (à créer en F7 ou réutiliser de F6 si livré).

**Limite :** maximum 6 enhancements par track. Si dépassement, lever `BandsExhaustedError` ou suggérer Feature 8 (consolidation).

### 5.3 Paramètres écrits

**Mapping Mode EQ8 (validé contre `ableton_devices_mapping_v2_2.json` en v1.1) :**

| EnhancementMode | Mode ID Ableton EQ8 | Description Ableton |
|---|---|---|
| `bell` | 2 | Bell (peak boost/cut) |
| `low_shelf` | 1 | Low Shelf |
| `high_shelf` | 4 | High Shelf |
| `notch` | 3 | Notch |

**Note v1.1 :** ces Mode IDs sont à confirmer définitivement contre le device mapping JSON au début du dev. Si les valeurs réelles diffèrent, mettre à jour cette spec.

**Pour une bande :**

| Paramètre | Valeur |
|---|---|
| `Mode` | Selon `intent.mode` (mapping ci-dessus) |
| `IsOn` | True (constant) — voir 5.4 pour le rationale |
| `Freq` | Constant à `intent.frequency_hz` (pas d'automation freq en enhancement) |
| `Gain` | Automation dense avec valeurs par section + crossfades |
| `Q` | Constant à `intent.q_factor` |

### 5.4 Stratégie IsOn en enhancement (clarifié en v1.1)

**Décision :** `IsOn=True` constant dans tous les cas pour Feature 7.

**Justification :**
- Une bande EQ avec `Gain=0 dB` est mathématiquement transparente (pas d'effet audible)
- Bypass via `IsOn` peut causer clicks au switch
- Garder `IsOn=True` simplifie la logique et évite le risque d'artifacts

Si l'utilisateur veut vraiment une bande désactivée pour économie CPU pure, il peut le faire manuellement dans Ableton après application F7.

### 5.5 Optimisation : détection de l'enhancement statique (clarifié en v1.1)

**Note v1.1 :** la v1.0 avait une formulation ambiguë. Voici la version corrigée.

**Détection :** si toutes les sections ont la **même valeur de gain** (cas dégénéré où "dynamique" = en fait statique), Feature 7 :

1. **Écrit la valeur Manual** sur le paramètre Gain (sans automation)
2. **Émet un warning explicite** dans le report :
   ```
   Warning: Enhancement '<intent.name>' has constant gain across all sections.
   This contradicts the dynamic-by-default philosophy.
   Either:
   - Reconsider if this enhancement should be applied at all (if always same value, may not be needed dynamically)
   - Move to a Static Cleanup EQ8 with explicit justification in changelog (one of the 3 documented exceptions)
   - Refine the intent to genuinely vary by section
   ```

**Justification du warning :** la philosophie 100% dynamique de Qrust (`qrust_professional_context.md` section 4.1) interdit le statique sans justification. Un "enhancement dynamique" qui sort statique est une anomalie de configuration à signaler.

**Note importante :** la suggestion "Move to Static Cleanup EQ8" est conditionnelle aux 3 exceptions autorisées. Pour un enhancement musical, le mouvement vers Static Cleanup est rarement justifié — c'est plutôt l'intent qui doit être reconsidéré.

### 5.6 Gestion des fréquences proches inter-intents (nouveau en v1.1)

**Cas problématique :** deux EnhancementIntent ciblent la même track avec des fréquences proches (ex: intent A à 3000 Hz et intent B à 3200 Hz).

**Détection :** au début du processing batch, Feature 7 vérifie pour chaque paire d'intents sur la même track si :
- `abs(log2(intent_a.frequency_hz / intent_b.frequency_hz) * 12) < 3 semitones`

Si oui, c'est un chevauchement potentiel.

**Comportement :**
1. **Warning automatique** dans le report : `"Intents '{name_a}' and '{name_b}' on track '{track}' have overlapping frequencies ({freq_a}Hz and {freq_b}Hz). Combined effect may be unexpected."`
2. **Continuer le processing** (les deux bandes sont écrites sur des bandes EQ différentes)
3. **Ne pas tenter de fusion automatique** — laisser à l'utilisateur de décider en sessions futures (potentiellement avec Feature 8 consolidation)

### 5.7 Rétrocompatibilité avec autres EQ8 (nouveau en v1.1)

Si la track a déjà :
- Un EQ8 Static Cleanup → ne pas toucher
- Un EQ8 Peak Resonance → ne pas toucher
- Un EQ8 CDE Correction → ne pas toucher
- Un EQ8 HPF/LPF Dynamic (de F6) → ne pas toucher

Feature 7 cible **uniquement** l'EQ8 nommé "Musical Enhancement" (ou créé tel quel).

**Vérification de la règle 3 EQ8 max :** si la track a déjà 3 EQ8 correctifs (Static, Peak Resonance, CDE Correction), l'ajout d'un 4ème EQ8 (Musical Enhancement) reste autorisé car ce dernier est le 4ème non-correctif autorisé par la règle 5.9 du brief.

Si la track a déjà **plus** de 4 EQ8 (signalé par Phase 1 audit), Feature 7 :
- Émet warning dans report
- Suggère Feature 8 consolidation
- Continue tout de même l'opération (l'utilisateur peut décider de consolider après)

---

## 6 — API proposée

### 6.1 Modules sources (nouveau en v1.1)

**Nouveau module :** `mix_analyzer/dynamic_enhancement.py`

Justification : feature suffisamment distincte pour mériter son propre module. Évite la pollution de `dynamic_hpf_lpf.py` (F6) et de `cde_apply.py` (F1).

**Modules existants utilisés (imports) :**
- `mix_analyzer.als_utils` — `read_locators`, `read_tempo`, helpers XML
- `mix_analyzer.eq8_automation` — helpers d'écriture EQ8
- `mix_analyzer.cde_apply` — patterns réutilisables (find_or_create EQ8, etc.)
- `mix_analyzer.dynamic_hpf_lpf` (si F6 livré) — `_compute_crossfade_for_boundary` partagé

### 6.2 Fonction principale

```python
from pathlib import Path
from typing import Optional

def write_dynamic_enhancement_from_intent(
    als_path: Path | str,
    intent: EnhancementIntent,
    *,
    report_xlsx_path: Optional[Path] = None,     # Requis pour mode peaks_dense_mix
    locators: Optional[list[tuple[float, str]]] = None,  # Lus depuis als_path si None
    genre_profile: Optional[dict] = None,         # Optionnel mais fortement recommandé pour cap
    track_type: Optional[str] = None,             # Pour lookup cap dans genre_profile
    target_eq8_username: str = "Musical Enhancement",
    transition_crossfade_beats: float = 2.0,      # Override intent.crossfade_beats si fourni
    dry_run: bool = False,
) -> "EnhancementApplicationReport":
    """
    Applique un enhancement dynamique sur une track.
    
    Args:
        als_path: Chemin vers le .als (sera modifié sauf si dry_run=True)
        intent: Intention d'enhancement (validée à l'instantiation)
        report_xlsx_path: Rapport Mix Analyzer (requis si gain_strategy=peaks_dense_mix)
        locators: Bornes des sections (lues automatiquement si None)
        genre_profile: Profil de calibration genre × track type
        track_type: Type de la track pour lookup dans le profil
        target_eq8_username: Nom de l'EQ8 cible
        transition_crossfade_beats: Override du crossfade de l'intent
        dry_run: Si True, calcule mais n'écrit pas
    
    Returns:
        EnhancementApplicationReport avec détails des actions
    
    Raises:
        TrackNotFoundError: si intent.target_track absent du .als
        InvalidProfileError: si genre_profile mal formé
        BandsExhaustedError: si l'EQ8 Musical Enhancement n'a plus de bandes libres
        EQ8WriteError: si écriture XML échoue
    """
```

### 6.3 Batch function pour plusieurs intents

```python
def write_dynamic_enhancements_batch(
    als_path: Path | str,
    intents: list[EnhancementIntent],
    *,
    report_xlsx_path: Optional[Path] = None,
    genre_profile: Optional[dict] = None,
    track_types_by_track: Optional[dict[str, str]] = None,  # Mapping track_name -> track_type
    target_eq8_username: str = "Musical Enhancement",
    transition_crossfade_beats: float = 2.0,
    dry_run: bool = False,
    stop_on_first_error: bool = False,
) -> list["EnhancementApplicationReport"]:
    """
    Applique plusieurs enhancements en série.
    
    Détecte les fréquences chevauchantes entre intents (voir section 5.6) et émet warnings.
    
    Si stop_on_first_error=True, arrête à la première exception.
    Sinon, continue et collecte toutes les erreurs dans les reports.
    """
```

### 6.4 Report dataclass

```python
@dataclass
class EnhancementApplicationReport:
    """Rapport d'application d'un enhancement dynamique."""
    applied: bool                                  # True si écriture effective
    intent_name: str
    target_track: str
    target_eq8_device_id: Optional[str]            # ID du device EQ8
    target_eq8_was_created: bool                   # True si nouveau EQ8 créé
    band_assigned: int                              # Index de la bande utilisée (1-6)
    
    gain_by_section_final: dict[str, float]        # Gain final après cap
    gain_capped_warnings: list[str]                # Sections où le gain a été cappé
    static_detected: bool                           # True si toutes sections ont même valeur (warning)
    overlap_warnings: list[str]                    # Si chevauchement avec autre intent
    
    crossfade_beats_used: float
    envelopes_written: int
    
    warnings: list[str]                            # Tous les warnings non bloquants
    decisions_log: list[str]                       # Trace des décisions algorithmiques
    
    backup_path: Optional[Path] = None
    dry_run: bool = False
```

### 6.5 Exceptions custom (nouveau en v1.1)

```python
class EnhancementError(Exception):
    """Base exception pour Feature 7."""

class TrackNotFoundError(EnhancementError):
    """La track demandée n'existe pas dans le .als."""

class InvalidProfileError(EnhancementError):
    """Le genre_profile est mal formé ou ne contient pas le track_type."""

class BandsExhaustedError(EnhancementError):
    """L'EQ8 Musical Enhancement n'a plus de bandes libres (max 6)."""

class UnsupportedSchemaVersionError(EnhancementError):
    """Le fichier YAML/JSON utilise une version de schema non supportée."""

class EQ8WriteError(EnhancementError):
    """Erreur lors de l'écriture XML de l'EQ8."""
```

---

## 7 — CLI wrapper

### 7.1 Script dédié

**Nouveau script :** `scripts/apply_dynamic_enhancement.py`

### 7.2 Mode batch via fichier YAML/JSON (recommandé)

```bash
python scripts/apply_dynamic_enhancement.py \
    --als "Acid_Drops_Sections_STD.als" \
    --config "enhancements_acid_drops.yaml" \
    --report-xlsx "Acid_Drops_MixAnalyzer_2026-04-22_15-52.xlsx" \
    --genre-profile "docs/brief/genre_music_profiles.json" \
    --genre Industrial \
    --dry-run
```

### 7.3 Mode single intent via flags CLI (nouveau en v1.1)

Pour les enhancements simples sans avoir à écrire un YAML :

```bash
python scripts/apply_dynamic_enhancement.py \
    --als "Acid_Drops_Sections_STD.als" \
    --report-xlsx "Acid_Drops_MixAnalyzer_2026-04-22_15-52.xlsx" \
    --track "[H/M] Lead Vocal Shhh" \
    --track-type "Lead Vocal" \
    --genre-profile "docs/brief/genre_music_profiles.json" \
    --genre Industrial \
    --intent-name "Voice presence" \
    --mode bell \
    --frequency 3000 \
    --q 1.5 \
    --gain-strategy section_lock \
    --gain-target 3.0 \
    --active-sections "Drop_1,Drop_2,Chorus_1,Chorus_2" \
    --dry-run
```

### 7.4 Mode revert (nouveau en v1.1)

```bash
python scripts/apply_dynamic_enhancement.py \
    --als "Acid_Drops_F7.als" \
    --revert
```

Restaure le backup créé avant la dernière application F7.

### 7.5 Garde-fou batch (nouveau en v1.1)

Cohérence avec brief v2.3 (approche track-par-track recommandée) :

```
⚠️  Mode batch: 3 intents vont être appliqués sur 3 tracks différentes.
    Le brief méthodologique recommande une validation track-par-track.
    Continuer? [y/N]
```

### 7.6 Flags principaux

| Flag | Type | Description |
|---|---|---|
| `--als` | path | Chemin du .als source |
| `--config` | path | Fichier YAML/JSON (mode batch) |
| `--report-xlsx` | path | Rapport Mix Analyzer (requis si peaks_dense_mix) |
| `--genre-profile` | path | Chemin vers `genre_music_profiles.json` |
| `--genre` | str | Famille + style |
| `--track` | str | Nom track (mode single) |
| `--track-type` | str | Type pour cap (mode single) |
| `--intent-name` | str | Label de l'intent (mode single) |
| `--mode` | str | bell / high_shelf / low_shelf / notch |
| `--frequency` | float | Fréquence en Hz |
| `--q` | float | Q factor |
| `--gain-strategy` | str | explicit / progressive / section_lock / peaks_dense_mix |
| `--gain-target` | float | Pour section_lock |
| `--gain-min` `--gain-max` | float | Pour progressive et peaks_dense_mix |
| `--active-sections` | str | Liste séparée par virgules |
| `--gain-by-section` | str | JSON inline pour mode explicit |
| `--target-eq8` | str | UserName EQ8 cible (default: "Musical Enhancement") |
| `--crossfade-beats` | float | Crossfade durée |
| `--dry-run` | flag | Calcule sans écrire |
| `--yes` | flag | Skip confirmations |
| `--revert` | flag | Restore backup |
| `--output` | path | Path de sortie (default: `<als>_F7.als`) |

---

## 8 — Plan de livraison

**Stratégie anti-timeout (clarifié en v1.1) :** chaque micro-commit < 30 min, séparation stricte code/tests.

### F7a — Dataclasses + loading YAML/JSON

**Fichiers créés :**
- `mix_analyzer/dynamic_enhancement.py` (skeleton avec `EnhancementIntent`, `EnhancementApplicationReport`, exceptions, enums)
- `mix_analyzer/dynamic_enhancement_loader.py` (loader YAML/JSON avec validation schema)

**Fonctions implémentées :**
- `EnhancementIntent` avec `__post_init__` validation
- `EnhancementApplicationReport`
- Toutes les exceptions custom
- Enums `EnhancementMode`, `GainStrategy`
- `load_intents_from_yaml(path) -> list[EnhancementIntent]`
- `load_intents_from_json(path) -> list[EnhancementIntent]`
- Validation schema `version: "1.0"`

**Durée :** 45min-1h
**Tests :** 4-5 (commit séparé F7a-tests)
**Commits :**
- `feat(F7): intent dataclasses + config loader`
- `test(F7): unit tests for intents and loader`

### F7b — Calcul des gains par section par mode

**Fichiers créés :** `mix_analyzer/dynamic_enhancement_helpers.py`

**Fonctions implémentées :**
- `_compute_gains_for_explicit_mode`
- `_compute_gains_for_progressive_mode`
- `_compute_gains_for_section_lock_mode`
- `_compute_gains_for_peaks_dense_mode` (avec `_compute_raw_density`, `_normalize_densities`, `_compute_gain_from_density`, `_parse_band_freq`)

**Durée :** 1.5h
**Tests :** 8-10 (couvrant les 4 modes avec fixtures synthétiques)
**Commits :**
- `feat(F7): gain profile computation for all modes`
- `test(F7): unit tests for gain computation modes`

### F7c — Cap par genre_profile

**Fichiers modifiés :** `mix_analyzer/dynamic_enhancement_helpers.py`

**Fonctions implémentées :**
- `_resolve_cap_from_profile(intent, genre_profile, track_type) -> float` (logique de cap selon zone fréquentielle)
- Application des caps avec génération des warnings

**Durée :** 45min
**Tests :** 3-4
**Commits :**
- `feat(F7): genre profile cap enforcement`
- `test(F7): unit tests for cap logic`

### F7d — Écriture automations Gain dans EQ8

**Fichiers modifiés :** `mix_analyzer/dynamic_enhancement.py`

**Fonctions implémentées :**
- `_find_or_create_musical_enhancement_eq8`
- `_find_available_band_in_eq8`
- `_write_band_with_gain_automation` (réutilise patterns F6 si livré)
- Gestion détection statique (section 5.5)
- Gestion fréquences proches (section 5.6)

**Durée :** 1.5h
**Tests :** 5-6
**Commits :**
- `feat(F7): write dynamic gain automations to EQ8`
- `test(F7): unit tests for EQ8 writing`

### F7e — API principale + integration tests

**Fichiers modifiés :** `mix_analyzer/dynamic_enhancement.py`

**Fonctions implémentées :**
- `write_dynamic_enhancement_from_intent` (orchestration complète)
- `write_dynamic_enhancements_batch` (avec détection chevauchements)
- `_validate_inputs`
- Backup automatique avant écriture
- Logging détaillé dans `decisions_log`

**Durée :** 1h
**Tests :** 4-6 (end-to-end avec fixtures `.als`)
**Commits :**
- `feat(F7): public API + integration tests`
- `test(F7): end-to-end integration tests`

### F7f — CLI wrapper

**Fichiers créés :** `scripts/apply_dynamic_enhancement.py`

**Fonctions implémentées :**
- Parsing flags
- Mode single intent (construction de l'EnhancementIntent depuis flags)
- Mode batch (chargement YAML/JSON)
- Mode revert
- Garde-fou batch
- Affichage report

**Durée :** 45min-1h
**Tests :** 2-3 (smoke tests CLI)
**Commits :**
- `feat(F7-cli): dynamic enhancement application script`
- `test(F7-cli): smoke tests for CLI`

### Total

**Effort total F7 :** 6h-7h, ~25-34 tests, **12 commits** (6 code + 6 tests, séparés pour anti-timeout).

---

## 9 — Tests d'acceptation (nouveau en v1.1)

### 9.1 Tests unitaires
- ✅ Tous les tests unitaires passent (cible ~25)
- ✅ Coverage > 85% sur les modules `dynamic_enhancement*.py`

### 9.2 Tests d'intégration
- ✅ Test end-to-end : appliquer F7 sur un `.als` synthétique, vérifier que le `.als` produit s'ouvre dans Ableton sans erreur
- ✅ Test rétrocompatibilité : appliquer F7 sur un `.als` déjà processé par F1 et F6, vérifier que les automations existantes sont préservées
- ✅ Test cap profile : vérifier que tous les gains calculés respectent les caps du profil
- ✅ Test détection statique : vérifier que warning émis si gain constant à travers sections
- ✅ Test détection chevauchement : vérifier que warning émis si deux intents proches en fréquence

### 9.3 Tests CLI
- ✅ Mode single intent fonctionne sans erreur sur fixture
- ✅ Mode batch via YAML fonctionne et applique tous les intents
- ✅ Mode batch demande confirmation avant exécution
- ✅ Mode revert restaure le backup correctement
- ✅ Dry-run produit un report sans modifier le `.als`
- ✅ Schema YAML invalide → erreur claire avec ligne et raison

### 9.4 Validation terrain (post-livraison code)
- ✅ Application sur 1 track de Acid Drops avec un intent simple (mode section_lock)
- ✅ Validation visuelle dans Ableton
- ✅ A/B écoute avec et sans enhancement
- ✅ Validation auditive par Alexandre

### 9.5 Documentation
- ✅ Cette spec mise à jour si l'implémentation diverge
- ✅ `roadmap_features_1_8.md` mis à jour (F7 livrée)
- ✅ `CHANGELOG.md` du repo Mix-Analyzer enrichi avec entrée F7
- ✅ Exemple `enhancements_acid_drops.yaml` ajouté dans `docs/examples/`

---

## 10 — Validation terrain (extension de v1.0)

### 10.1 Protocole

Après livraison F7, tester sur Acid Drops avec deux intents typiques :

**Intent 1 — Voice presence boost conditionnel**
```yaml
- name: "Voice presence Acid Drops"
  target_track: "[H/M] Lead Vocal Shhh"
  mode: bell
  frequency_hz: 3000
  q_factor: 1.5
  gain_strategy: section_lock
  gain_db_range: [0, 2.5]
  active_sections: [Drop_1, Drop_2, Chorus_1, Chorus_2]
```

**Intent 2 — Air progressif sur Climax**
```yaml
- name: "Cymbals air progressive Acid Drops"
  target_track: "[S/R] Tambourine Hi-Hat"
  mode: high_shelf
  frequency_hz: 12000
  q_factor: 0.71
  gain_strategy: progressive
  gain_db_range: [0.0, 2.0]
  active_sections: [Chorus_1, Drop_2, Chorus_2, Climax]
```

**Étapes :**
1. Dry-run pour examiner les gains calculés par section
2. Validation des gains par Alexandre
3. Application réelle (sans dry-run, avec --yes)
4. Vérification visuelle dans Ableton (EQ8 Musical Enhancement créé, bandes correctes, automations Gain)
5. Bounce
6. A/B écoute avec et sans

### 10.2 Documentation post-validation

Mettre à jour `Acid_Drops_CHANGELOG.md` avec :
- Date application F7
- Intents appliqués
- Gains finaux par section
- Verdict (keep / adjust / revert)
- Notes auditives

---

## 11 — Risques techniques identifiés

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Utilisateur mal configure les gains → mix déséquilibré | Moyenne | Audible | Cap automatique par genre profile + dry-run obligatoire avant write |
| Gain automation cause pops au crossfade | Moyenne | Audible | Crossfade long par défaut (2 beats), validation des courbes |
| Trop de Musical Enhancement bandes → EQ8 surchargé | Faible | Bloquant | `BandsExhaustedError` à 6 bandes, suggestion F8 consolidation |
| Chevauchement de fréquences entre plusieurs enhancements | Moyenne | Sous-optimal | Détection automatique (5.6) + warning dans report |
| `peaks_dense_mix` mal calibré → résultats erratiques | Élevée | Inattendu | Mode marqué experimental en v1, mode `explicit` recommandé par défaut |
| Schema YAML modifié par utilisateur sans version bump | Moyenne | Erreur load | Validation `version` au load, exception claire |
| Track type mal identifié → mauvais cap appliqué | Moyenne | Cap erroné | Lookup explicit, fallback sur cap générique avec warning |
| Conflit avec EQ8 existants des features précédentes | Faible | Logique | Séparation stricte (5.7), ne jamais toucher aux autres EQ8 |
| Détection statique trop sensible (cas limite identique gain) | Faible | False positive | Tolérance 0.01 dB sur la détection |
| Mode `notch` peu pertinent comme enhancement | N/A | UX | Documenter comme cas avancé, pas de promotion par défaut |

---

## 12 — Hors scope F7 v1

**Reportés à F7 v2 ou autres features :**

- **Enhancements multi-bandes corrélés** (ex: smile curve combinée) → batch de intents simples suffit pour l'instant
- **Enhancement M/S séparé Mid vs Side** → Feature 4 (`feature_4_eq8_stereo_ms.md`)
- **Harmonic excitation / saturation dynamique** → hors EQ8, scope autre feature future
- **Compensation de volume automatique post-enhancement** → manuel pour l'instant. Si validation terrain montre besoin, F7 v2 pourrait inclure.
- **Mode `peaks_dense_mix` production-ready** → marqué experimental en v1, à graduer en stable après validation terrain
- **Auto-suggestion d'intents par analyse Mix Analyzer** → Feature future (l'utilisateur définit les intents en v1)
- **Visualisation des courbes de gain calculées (GUI)** → outil externe, hors scope

---

## 13 — Dépendances validation utilisateur avant dev

**Avant de lancer le développement de F7, l'utilisateur (Alexandre) doit trancher les questions suivantes.**

### Q1 — Format de config YAML vs JSON

**Question :** YAML par défaut acceptable ? Ou préférer JSON, ou autre format ?

**Trade-offs :**
- **YAML :** lisible humainement, supporte commentaires, syntaxe naturelle, mais nécessite lib `pyyaml`
- **JSON :** standard, supporté nativement Python, mais pas de commentaires, moins lisible
- **TOML :** alternative moderne, supporté natif Python 3.11+, lisible, supporte commentaires

**Recommandation :** YAML par défaut, JSON également supporté pour compatibilité programmatique. TOML envisageable si tu préfères, mais ajout dépendance.

**Réponse Alexandre :** _____ (à remplir)

### Q2 — Convention "Musical Enhancement" comme 4ème EQ8

**Question :** acceptes-tu la convention où Feature 7 ajoute un 4ème EQ8 dédié "Musical Enhancement" en post-chaîne correction ?

**Trade-offs :**
- **Pour :** séparation épistémique claire, conforme à la règle 5.9 du brief, bypass indépendant possible
- **Contre :** ajoute un device sur chaque track avec enhancement, augmente CPU marginal

**Recommandation :** Oui (convention par défaut, déjà documentée dans le brief).

**Réponse Alexandre :** _____ (à remplir)

### Q3 — Mode `peaks_dense_mix` prioritaire ou opt-in

**Question :** le mode adaptatif `peaks_dense_mix` doit-il être livré avec la v1 ou reporté à v2 ?

**Trade-offs :**
- **Livré v1 :** features set complet immédiat, mais mode plus complexe à valider
- **Reporté v2 :** v1 plus simple (3 modes : explicit, progressive, section_lock), validation terrain plus rapide, peaks_dense_mix livré après confirmation utilité

**Recommandation :** **livré v1 mais marqué experimental** dans la documentation. L'utilisateur peut tester mais le mode `explicit` reste recommandé par défaut.

**Réponse Alexandre :** _____ (à remplir)

### Q4 — Priorité dans la roadmap

**Question :** F7 doit-elle être développée avant ou après F1.5 et F6 ?

**Roadmap suggérée actuelle (`roadmap_features_1_8.md`) :**
1. F1.5 (sidechain)
2. F6 (HPF/LPF dynamique)
3. F7 (enhancement)
4. F8 (consolidation)

**Recommandation :** suivre la roadmap (F7 en 3ème position).

**Réponse Alexandre :** _____ (à remplir)

---

## 14 — Procédure d'évolution de cette spec

Suivre `documentation_discipline.md` section 4. Triggers d'évolution typiques :
- Réponses Q1-Q4 reçues → enrichir spec avec décisions validées
- Découverte technique pendant dev → mise à jour algorithme
- Validation terrain → ajustement scope, modes
- Nouveau cas d'usage identifié → extension scope ou hors scope explicite

---

## 15 — Référence rapide (quick card, nouveau en v1.1)

**Statut :** Spec en attente de validation utilisateur (Q1-Q4)

**Effort estimé total :** 6h-7h, ~25-34 tests, 12 commits

**Modules à créer :**
- `mix_analyzer/dynamic_enhancement.py` (fonction publique + dataclasses + exceptions)
- `mix_analyzer/dynamic_enhancement_helpers.py` (helpers de calcul)
- `mix_analyzer/dynamic_enhancement_loader.py` (loader YAML/JSON)
- `scripts/apply_dynamic_enhancement.py` (CLI)

**Inputs requis :**
- `.als` source
- `EnhancementIntent` (via flags CLI ou fichier YAML/JSON)
- `genre_music_profiles.json` (recommandé pour cap)
- Rapport Mix Analyzer Excel (requis pour mode `peaks_dense_mix`)

**Output :**
- `.als` modifié avec EQ8 "Musical Enhancement" et automations Gain par section
- `EnhancementApplicationReport` détaillé

**Modes disponibles :**
- `explicit` (recommandé) — gain par section explicite
- `progressive` — interpolation linéaire entre sections actives
- `section_lock` — binaire on/off
- `peaks_dense_mix` (experimental v1) — adaptatif à la densité spectrale

**4 types de bandes EQ supportées :**
- `bell` (Mode ID 2)
- `low_shelf` (Mode ID 1)
- `high_shelf` (Mode ID 4)
- `notch` (Mode ID 3)

**Dépendances roadmap :**
- F1 livrée ✅
- F6 souhaitable (partage `_compute_crossfade_for_boundary`)
- F8 viendra après pour consolider si besoin

**Documents associés :**
- `qrust_professional_context.md` section 4.1 (philosophie 100% dynamique)
- `mix_engineer_brief_v2_3.md` sections 4 Phase 6, 5.9, 5.10
- `roadmap_features_1_8.md`
- `documentation_discipline.md`

---

**Fin spec Feature 7 v1.1. Validation utilisateur attendue sur Q1-Q4 avant démarrage dev. Une fois Q1-Q4 résolues, incrémenter en v1.2 avec les décisions intégrées et démarrer le développement selon le plan de livraison de la section 8.**
