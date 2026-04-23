# Feature 6 — Dynamic HPF/LPF per section

**Version spec :** 1.0 (draft)
**Date :** 2026-04-23
**Statut :** Planifiée, non démarrée
**Dépendances :** Feature 1 livrée, infrastructure `cde_apply.py` et `eq8_automation.py` disponibles
**Effort estimé :** 4-6 heures Claude Code (6-10 micro-commits selon découpage anti-timeout)

---

## 1 — Objectif et justification

### Ce que fait la feature

Produire des automations contextuelles pour les bandes HPF (High-Pass Filter) et LPF (Low-Pass Filter) d'EQ Eight, de sorte que la fréquence de coupe **s'adapte par section** et/ou **suit le contenu réel de la track** dans le temps.

Remplace les HPF/LPF statiques traditionnels par un comportement adaptatif précis, fidèle à la philosophie "traitement dynamique par défaut" du contexte artistique Qrust.

### Pourquoi cette feature

Dans l'approche traditionnelle, un HPF à 80 Hz sur une voix est posé de manière fixe pour toute la durée du morceau. Cette approche ignore que :

- Dans l'intro, la voix peut être basse et intime — HPF à 80 Hz enlève du corps utile
- Dans le drop, la voix peut être plus agressive et concurrente avec le kick/sub — HPF à 120 Hz est plus approprié pour dégager l'espace
- Dans le breakdown, la voix peut devenir solo — HPF à 60 Hz pour retrouver la pleine chaleur

Un HPF statique fige un compromis moyen qui n'est optimal nulle part. Un HPF dynamique par section est optimal partout.

### Résultat attendu

Une fonction `write_dynamic_hpf_lpf_from_analysis` qui :

1. Consomme les données `_track_zone_energy` (énergie par zone spectrale et par section) et `_track_peak_trajectories` (peaks dans le temps)
2. Détermine la fréquence de coupe HPF optimale par section selon le contenu réel de la track dans cette section
3. Détermine la fréquence de coupe LPF optimale par section selon le contenu réel
4. Écrit dans l'EQ8 cible (typiquement le `Static Cleanup` ou `Peak Resonance` existant) des automations synchronisées Freq + IsOn sur les bandes 0 (HPF) et 7 (LPF)

---

## 2 — Données consommées

### Inputs

**Source 1 — `_track_zone_energy` (rapport Mix Analyzer)**

Sheet Excel contenant par track et par section l'énergie dans chaque zone fréquentielle (Sub 20-60 Hz, Bass 60-250 Hz, Low-Mid 250-500 Hz, Mid 500-2k Hz, High-Mid 2-4k Hz, Presence 4-8k Hz, Air 8-20k Hz).

Utilité : savoir où se situe le "vrai contenu utile" de la track à chaque section.

**Source 2 — `_track_peak_trajectories` (rapport Mix Analyzer)**

Peaks détectés dans le temps avec fréquence, amplitude, durée. Déjà consommés par Feature 1 (mode peak-follow) et par `write_resonance_suppression`.

Utilité : identifier les fréquences où la track émet vraiment de l'énergie dans le temps.

**Source 3 — `_track_spectral_descriptors` (rapport Mix Analyzer)**

Descripteurs agrégés (centroid, rolloff, flatness) par track et par section.

Utilité : la fréquence de rolloff 85% donne une estimation conservative du bord haut utile ; le centroid indique la tendance globale.

**Source 4 — `genre_music_profiles.json`**

Caps de HPF et LPF par style × track type :
- `hpf_max_hz` : fréquence maximale de coupe HPF acceptable dans ce contexte
- `lpf_min_hz` : fréquence minimale de coupe LPF acceptable dans ce contexte

Utilité : bornes dures qui empêchent la feature de couper trop agressivement par rapport à l'esthétique du genre.

**Source 5 — Locators (via `als_utils.read_locators`)**

Bornes temporelles des sections pour aligner les automations.

### Format de consommation

Similaire à Feature 1 : la fonction reçoit une signature avec :

```python
def write_dynamic_hpf_lpf_from_analysis(
    als_path,
    track_name,
    zone_energy_by_section,    # dict par section -> dict zone -> pct
    peak_trajectories,          # list[PeakTrajectory]
    spectral_descriptors,       # per-section descriptors
    locators,                   # list of (time_beats, name)
    *,
    genre_profile,              # dict loaded from genre_music_profiles.json
    track_type,                 # ex: "Lead Vocal", "Kick", etc.
    hpf_enabled=True,
    lpf_enabled=True,
    target_eq8_username="Peak Resonance",   # ou "Static Cleanup"
    transition_crossfade_beats=2.0,
    dry_run=False,
)
```

---

## 3 — Algorithme de calcul des fréquences de coupe

### 3.1 HPF — fréquence de coupe par section

Pour chaque section du projet :

**Étape A —** Identifier la track_type via `qrust_artistic_context` ou input utilisateur. Ex: "Lead Vocal".

**Étape B —** Récupérer `hpf_max_hz` du genre_profile pour ce track_type. Ex: Industrial + Lead Vocal = 80 Hz.

**Étape C —** Calculer le seuil plancher théorique basé sur l'énergie réelle par zone dans cette section :
- Sub Energy + Bass Energy de la section
- Si pct_sub < 2% et pct_bass < 5% : la track est quasi-silencieuse dans le bas → HPF peut monter à 95% de hpf_max_hz (économise des ressources sans perte)
- Si pct_sub > 5% : il y a du contenu utile sous 60 Hz → HPF doit descendre à 40-50 Hz ou moins
- Sinon : HPF à hpf_max_hz * 0.8

**Étape D —** Appliquer la contrainte dure du profil : `hpf_this_section = min(hpf_theoretical, hpf_max_hz)`

**Étape E —** Vérifier cohérence avec les peak_trajectories : si un peak amplitude > -20 dBFS existe à une fréquence inférieure à hpf_this_section dans cette section, **réduire le HPF** de 1 semitone pour préserver ce peak.

**Résultat —** Un dict `{section_name: hpf_freq_hz}` avec une fréquence de coupe par section.

### 3.2 LPF — fréquence de coupe par section

Symétrique à HPF, avec :

- `lpf_min_hz` du profil comme plancher absolu
- Check sur les zones High-Mid, Presence, Air au lieu de Sub, Bass
- Prioriser conservative : si doute, LPF haut (garde l'air plutôt que couper)

### 3.3 Transitions entre sections

Pour éviter les clicks ou artefacts audibles au changement de section :

**Crossfade linéaire de `transition_crossfade_beats` beats** (défaut 2.0 beats = ~0.94s à 128 BPM) autour de la frontière entre deux sections.

Exemple : HPF passe de 60 Hz (Drop 1) à 80 Hz (Build 2).
- De (boundary - 1.0 beat) à boundary : HPF tient à 60 Hz
- De boundary à (boundary + 1.0 beat) : interpolation linéaire 60 → 80 Hz
- De (boundary + 1.0 beat) à fin Build 2 : HPF tient à 80 Hz

Pour les sections courtes (< 3 beats), le crossfade est réduit proportionnellement.

### 3.4 Mode peak-follow intra-section (optionnel, advanced)

Pour les tracks avec grande variabilité de contenu intra-section (ex: un lead qui a des moments silencieux et des moments agressifs dans la même section), offrir un mode où le HPF/LPF s'adapte non seulement par section mais aussi par peak intra-section.

Implémentation : reuse du `_collect_active_peak_frames` de Feature 1, appliqué avec logique HPF/LPF au lieu de cut.

Paramètre : `peak_follow_within_section=False` par défaut, `True` en option avancée.

---

## 4 — Écriture dans l'EQ8

### 4.1 Cible des automations

Par convention Qrust, le HPF occupe la **bande 0** et le LPF occupe la **bande 7** d'un EQ Eight. Ces bandes sont réservées par la règle v2.2 du brief.

**Target EQ8 :** par défaut, l'EQ8 nommé "Peak Resonance" existant sur la track (le plus courant). Alternative : "Static Cleanup" si l'utilisateur veut séparer les rôles.

Si l'EQ8 cible n'existe pas sur la track, Feature 6 en clone un depuis le `Pluggin Mapping.als` (pattern existant utilisé par `write_resonance_suppression`).

### 4.2 Paramètres écrits

Pour la **bande 0 (HPF)** :
- `Mode` : forcé à 0 (High-Pass)
- `IsOn` : automation qui bascule True/False selon les sections (False si la track n'a rien à couper dans une section = pas d'activation inutile)
- `Freq` : automation avec les valeurs calculées par section + crossfades
- `Gain` : 0 dB (non utilisé en mode HPF)
- `Q` : constant à 0.71 (default) ou paramétrable

Pour la **bande 7 (LPF)** :
- `Mode` : forcé à 5 (Low-Pass)
- `IsOn` : automation similaire
- `Freq` : automation avec valeurs calculées
- `Gain` : 0 dB
- `Q` : constant à 0.71

### 4.3 Contrainte de coexistence avec les bandes 1-6 existantes

Feature 6 ne touche **jamais** aux bandes 1-6 d'un EQ8 existant. Ces bandes sont le territoire du Peak Resonance (automation dynamique sur peaks spectraux) et doivent être préservées.

Si la bande 0 ou la bande 7 est déjà utilisée à d'autres fins dans un EQ8 existant, Feature 6 :
- Signale l'incompatibilité dans le `CdeApplicationReport` équivalent
- Demande confirmation utilisateur avant overwrite
- Si refus : cible un autre EQ8 de la track ou crée un nouveau "HPF/LPF Dynamic" EQ8 dédié

---

## 5 — API proposée

### 5.1 Fonction principale

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

### 5.2 Report dataclass

```python
@dataclass
class HpfLpfApplicationReport:
    applied: bool
    hpf_frequencies_by_section: dict[str, float]
    lpf_frequencies_by_section: dict[str, float]
    hpf_bypassed_sections: list[str]      # sections où HPF IsOn=False
    lpf_bypassed_sections: list[str]      # sections où LPF IsOn=False
    target_eq8_device_id: str
    warnings: list[str]
    envelopes_written: int
```

### 5.3 Fonctions helpers internes

- `_compute_hpf_freq_for_section(zone_energy, peaks, profile, track_type) -> float`
- `_compute_lpf_freq_for_section(zone_energy, peaks, profile, track_type) -> float`
- `_build_freq_curve_with_crossfades(sections_freq_dict, locators, tempo, crossfade_beats) -> np.ndarray`
- `_build_ison_curve(sections_active_list, locators, tempo) -> np.ndarray`
- `_find_or_create_target_eq8(tree, track_name, target_username) -> Element`

---

## 6 — CLI wrapper

Extension de `scripts/apply_cde_corrections.py` ou nouveau script dédié `scripts/apply_dynamic_hpf_lpf.py`.

```bash
python scripts/apply_dynamic_hpf_lpf.py \
    --als "project.als" \
    --report-xlsx "project_report.xlsx" \
    --track "[H/M] Lead Vocal Shhh" \
    --track-type "Lead Vocal" \
    --genre Industrial \
    --target-eq8 "Peak Resonance" \
    --crossfade-beats 2.0 \
    --dry-run
```

Flag `--batch` pour traiter plusieurs tracks d'un coup avec un fichier CSV décrivant track_name + track_type par ligne.

---

## 7 — Plan de livraison

### F6a — Calcul des fréquences HPF/LPF par section (pur, data-prep)

Fonctions :
- `_compute_hpf_freq_for_section`
- `_compute_lpf_freq_for_section`
- Load de zone_energy depuis Excel
- Tests unitaires avec fixtures synthétiques

Durée : 1.5h-2h
Tests : 6-8
Commit : `feat(dynamic-hpf-lpf): per-section frequency computation helpers`

### F6b — Génération des curves avec crossfades

Fonctions :
- `_build_freq_curve_with_crossfades`
- `_build_ison_curve`
- Tests unitaires

Durée : 1h-1.5h
Tests : 4-6
Commit : `feat(dynamic-hpf-lpf): curve generation with crossfade transitions`

### F6c — Écriture dans l'EQ8 (bande 0 HPF, bande 7 LPF)

Fonctions :
- `_find_or_create_target_eq8`
- Écriture des automations Mode/Freq/IsOn
- Protection des bandes 1-6 existantes

Durée : 1.5h
Tests : 4
Commit : `feat(dynamic-hpf-lpf): write HPF/LPF automations on bands 0 and 7`

### F6d — Integration function + tests end-to-end

Fonction publique `write_dynamic_hpf_lpf_from_analysis` orchestrant tout.

Durée : 1h
Tests : 4-6
Commit : `feat(dynamic-hpf-lpf): public API + integration tests`

### F6e — CLI wrapper

Script `apply_dynamic_hpf_lpf.py` avec flags et preview.

Durée : 45min-1h
Tests : 2-3
Commit : `feat(cli): dynamic HPF/LPF application script`

**Total F6 :** 5.5h-7.5h, ~20-27 tests, 5 micro-commits.

---

## 8 — Validation terrain

Après livraison F6, tester sur Acid Drops :

- Sélectionner une track vocal (ex: `[H/M] Lead Vocal Shhh`)
- Comparer HPF statique à 80 Hz vs HPF dynamique par section
- Critère : la voix gagne-t-elle en chaleur dans les sections calmes sans perdre la dégage dans les drops ?

Protocole F1.5-like : dry-run, application sur copie, bounce, re-run Mix Analyzer, A/B écoute.

---

## 9 — Risques techniques identifiés

| Risque | Mitigation |
|---|---|
| Automation IsOn cause clicks au bypass | Utiliser automation Freq très haute / très basse plutôt que bypass, ou crossfade Gain |
| Bande 0 ou 7 déjà utilisée par un autre plugin | Détecter, avertir, offrir création nouvelle EQ8 dédiée |
| Zone energy absente pour section (section trop courte < 3s) | Fallback sur moyenne des sections voisines |
| Tracks sans peak trajectories matchées | HPF conservative à hpf_max_hz du profil par défaut |
| Crossfades qui débordent sections courtes | Réduction automatique proportionnelle |
| Dérive float des fréquences dans l'XML | Reuse validation EQ8 existante (`_freq_to_eq8_value` + tolerance) |

---

## 10 — Hors scope F6

- Peak-follow intra-section complexe → `peak_follow_within_section=True` livré en V2 si pertinent
- Consolidation automatique avec autres EQ8 existants → Feature 8
- Dynamic shelf / Dynamic bell pour enhancement musical → Feature 7
- Intégration des profils par genre au cœur du CDE engine → Feature 9 (future)

---

## 11 — Dépendances validation utilisateur avant dev

Avant de lancer F6, confirmer :

**Q1 —** La convention "bande 0 = HPF, bande 7 = LPF" est-elle acceptable par défaut ?
**Q2 —** La fonction écrit-elle dans le "Peak Resonance" existant ou crée-t-elle toujours un nouveau "HPF/LPF Dynamic" dédié ?
**Q3 —** Transition crossfade par défaut (2.0 beats) est-elle appropriée ou préférer 1.0 / 4.0 ?
**Q4 —** La logique "IsOn=False si la track n'a rien à couper" est-elle intuitive, ou préférer toujours IsOn=True avec Freq conservative ?
**Q5 —** Priorité F6 vs autres features (F1.5, F7, F8) dans la roadmap ?

---

**Fin spec Feature 6. Validation utilisateur attendue avant démarrage dev.**
