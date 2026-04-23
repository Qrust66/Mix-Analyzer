# Feature 7 — Dynamic musical EQ / enhancement

**Version spec :** 1.0 (draft)
**Date :** 2026-04-23
**Statut :** Planifiée, non démarrée
**Dépendances :** Feature 1 livrée, Feature 6 souhaitable mais pas bloquante
**Effort estimé :** 4-6 heures Claude Code (5-8 micro-commits)

---

## 1 — Objectif et justification

### Ce que fait la feature

Produire des automations contextuelles pour les **boosts musicaux** (présence, air, shelf, excitation harmonique) qui s'adaptent par section à l'intention artistique plutôt qu'être fixes.

### Contraste avec les features précédentes

- **Feature 1 (CDE)** — corrige des problèmes (masking, accumulation). Réducteur. Corrige ce qui ne va pas.
- **Feature 6 (HPF/LPF)** — nettoie les extrêmes du spectre. Réducteur. Enlève ce qui n'est pas utile.
- **Feature 7 (Enhancement)** — enrichit, colore, met en avant. Additif. Ajoute ce qui améliore musicalement.

### Pourquoi cette feature

Dans un mix industrial Qrust, certains enhancements sont désirables mais pas constants :

- Un boost de présence 3 kHz sur la voix pour couper dans le mix — utile dans les drops denses, superflu dans les breakdowns solo
- Un shelf d'air à 12 kHz sur les cymbales — bénéfique en chorus quand tout remplit, excessif en intro quand l'auditeur a déjà l'attention
- Une excitation harmonique sur un lead — puissante en chorus 2 pour le climax, trop agressive en intro

Un enhancement statique ignore cette dynamique. Un enhancement dynamique renforce le morceau dans les moments où ça aide, s'efface là où ça gênerait.

### Résultat attendu

Une fonction `write_dynamic_enhancement_from_intent` qui :

1. Reçoit une **intention d'enhancement** (ex: "+2 dB à 3 kHz Q=1.5 pour présence voix")
2. Reçoit une **carte de sections où cet enhancement doit être actif** (ex: Drops et Chorus uniquement)
3. Reçoit des métriques Mix Analyzer pour ajuster l'intensité par section selon le contexte mix
4. Écrit dans un EQ8 `Musical Enhancement` dédié (4ème EQ8 autorisé par la règle v2.2) les automations qui activent/désactivent ou modulent l'enhancement selon la section

---

## 2 — Cas d'usage typiques

### Cas 1 — Boost de présence voix conditionnel

Intention utilisateur : "La voix a besoin de présence 3 kHz quand elle se bat contre le kick, pas quand elle est seule."

Configuration :
- Enhancement : shelf high ou bell à 3 kHz, +3 dB, Q 1.5
- Sections actives : Drop 1, Drop 2, Chorus 1, Chorus 2
- Sections inactives : Intro, Build 1, Break 1, Breakdown 1, Outro

Feature 7 écrit une automation Gain qui alterne 0 dB ↔ +3 dB selon la section, avec crossfade pour éviter les pops.

### Cas 2 — Air progressif sur climax

Intention utilisateur : "Ajouter de l'air progressivement jusqu'au Climax."

Configuration :
- Enhancement : shelf high à 12 kHz, gain variable
- Intro/Build : 0 dB
- Chorus 1 : +1 dB
- Drop 2 : +1.5 dB
- Chorus 2 : +2 dB
- Climax : +3 dB
- Outro : +0.5 dB

Feature 7 écrit une automation Gain qui monte progressivement.

### Cas 3 — Intensité modulée par densité du mix

Intention utilisateur : "Plus le mix est dense, plus l'enhancement est nécessaire pour faire ressortir cet élément."

Automatisation basée sur `_track_multiband_time` et `Freq Conflicts` — Feature 7 lit la densité spectrale de la section et calcule l'intensité d'enhancement proportionnelle.

---

## 3 — Données consommées

### Inputs principaux

**Source 1 — Intention d'enhancement (input utilisateur)**

Dataclass `EnhancementIntent` :

```python
@dataclass
class EnhancementIntent:
    name: str                               # label descriptif ex: "Voice presence boost"
    target_track: str                        # nom track Ableton
    mode: str                                # "bell", "high_shelf", "low_shelf", "notch"
    frequency_hz: float                      # fréquence centrale ou cutoff
    q_factor: float                          # largeur
    gain_db_by_section: dict[str, float]    # dict section_name -> gain_db
    # ou alternativement :
    gain_db_profile: str                     # "off", "constant", "progressive_up", "peaks_dense_mix"
    gain_db_range: tuple[float, float]       # (min, max) si profile non-constant
```

**Source 2 — Rapport Mix Analyzer (Excel)**

Pour le profil `peaks_dense_mix` : lecture de la densité par section pour moduler l'intensité.

**Source 3 — Locators (via `als_utils.read_locators`)**

Bornes temporelles des sections pour aligner les automations.

**Source 4 — `genre_music_profiles.json`**

Caps par track type :
- `presence_boost_max_db` : plafond absolu sur les boosts de présence
- Notes naturelles sur ce qui est "sacré" ou "à protéger"

Feature 7 respecte ces caps : si l'intention utilisateur propose +4 dB mais le profil dit max +2.5 dB pour un Lead Vocal en Industrial, l'enhancement est cappé à +2.5 dB avec warning dans le report.

---

## 4 — Algorithme de modulation par section

### 4.1 Mode "explicit" (utilisateur fournit gain_db_by_section)

Mapping direct des valeurs fournies vers les sections. Crossfade entre sections pour transitions douces. Cap par genre_profile si dépassement.

### 4.2 Mode "progressive" (ex: progressive_up)

Interpolation linéaire du gain entre les sections selon l'ordre temporel :
- Sections listées comme actives
- Gain commence à `gain_db_range[0]` sur la première active
- Gain atteint `gain_db_range[1]` sur la dernière active
- Sections intermédiaires : interpolation linéaire

### 4.3 Mode "peaks_dense_mix" (adaptatif à la densité du mix)

Pour chaque section active :
- Lire `Freq Conflicts` matrice pour quantifier la densité spectrale autour de la frequency_hz de l'enhancement
- Si densité élevée (beaucoup de tracks émettent dans cette zone) → enhancement plus fort (jusqu'à `gain_db_range[1]`)
- Si densité faible → enhancement plus léger (jusqu'à `gain_db_range[0]`)

Formule : `gain = range[0] + (range[1] - range[0]) * normalized_density`

### 4.4 Mode "section_lock" (on/off par section)

Binaire : gain = valeur cible dans les sections listées, 0 dB ailleurs. Avec crossfade de transition pour éviter pops.

---

## 5 — Écriture dans l'EQ8

### 5.1 Cible : EQ8 Musical Enhancement

Par convention Qrust (brief v2.2), c'est le **4ème EQ8 autorisé** sur une track, placé après les effets non-correctifs (saturation, compression, sidechain) mais avant le glue final.

Feature 7 crée cet EQ8 s'il n'existe pas sur la track cible, ou réutilise l'existant pour ajouter une nouvelle bande.

Nom : "Musical Enhancement" ou `"Musical Enhancement ({n} bands)"` similaire au nommage CDE Correction.

### 5.2 Allocation des bandes

Chaque `EnhancementIntent` occupe une bande. Les bandes 1-6 sont disponibles (0 et 7 réservés HPF/LPF même dans cet EQ8 pour uniformité).

Feature 7 trouve la première bande libre via `_find_available_band` existant.

### 5.3 Paramètres écrits

Pour une bande :
- `Mode` : selon l'intent (2=Bell, 1=Low Shelf, 4=High Shelf, 3=Notch)
- `IsOn` : True tant qu'au moins une section a gain != 0 ; sinon automatisé off-on
- `Freq` : constant à la fréquence de l'intent (pas d'automation freq en enhancement par défaut)
- `Gain` : automation dense avec valeurs par section + crossfades
- `Q` : constant à q_factor

### 5.4 Optimisation : ne pas écrire d'automation Gain inutile

Si toutes les sections ont la même valeur gain (cas dégénéré de "dynamique" = en fait statique), Feature 7 écrit juste la valeur manual et pas d'automation. Avec warning : "Enhancement constant across all sections — considered as static. Move to Static Cleanup EQ8 or reconsider."

Cela garde Feature 7 aligné avec la philosophie "dynamique par défaut" — si le résultat est statique, c'est une anomalie à signaler.

---

## 6 — API proposée

### 6.1 Fonction principale

```python
def write_dynamic_enhancement_from_intent(
    als_path: Path | str,
    intent: EnhancementIntent,
    *,
    report_xlsx_path: Optional[Path] = None,     # pour mode peaks_dense_mix
    locators: Optional[list[tuple[float, str]]] = None,
    genre_profile: Optional[dict] = None,
    track_type: Optional[str] = None,
    target_eq8_username: str = "Musical Enhancement",
    transition_crossfade_beats: float = 2.0,
    dry_run: bool = False,
) -> EnhancementApplicationReport
```

### 6.2 Batch function pour plusieurs intents

```python
def write_dynamic_enhancements_batch(
    als_path: Path | str,
    intents: list[EnhancementIntent],
    *,
    # ... mêmes kwargs
) -> list[EnhancementApplicationReport]
```

### 6.3 Report dataclass

```python
@dataclass
class EnhancementApplicationReport:
    applied: bool
    intent_name: str
    target_track: str
    target_eq8_device_id: str
    band_assigned: int
    gain_by_section_final: dict[str, float]    # après cap par profile
    gain_capped_warnings: list[str]             # sections où le gain a été réduit
    warnings: list[str]
    envelopes_written: int
```

---

## 7 — CLI wrapper

Nouveau script `scripts/apply_dynamic_enhancement.py` qui consomme un fichier YAML ou JSON décrivant les intents.

Exemple `enhancements_config.yaml` :

```yaml
enhancements:
  - name: "Voice presence boost"
    target_track: "[H/M] Lead Vocal Shhh"
    mode: "bell"
    frequency_hz: 3000
    q_factor: 1.5
    gain_db_by_section:
      Drop_1: 3.0
      Drop_2: 3.5
      Chorus_1: 2.5
      Chorus_2: 2.5
      Outro: 1.0

  - name: "Cymbals air progressive"
    target_track: "[S/R] Tambourine Hi-Hat"
    mode: "high_shelf"
    frequency_hz: 12000
    q_factor: 0.71
    gain_db_profile: "progressive_up"
    gain_db_range: [0.0, 3.0]
```

CLI :
```bash
python scripts/apply_dynamic_enhancement.py \
    --als "project.als" \
    --config "enhancements_config.yaml" \
    --report-xlsx "project_report.xlsx" \
    --dry-run
```

---

## 8 — Plan de livraison

### F7a — Dataclasses + loading YAML/JSON

- `EnhancementIntent`, `EnhancementApplicationReport`
- Helper loader pour config YAML/JSON
- Tests unitaires parsing

Durée : 45min-1h
Tests : 4-5
Commit : `feat(enhancement): intent dataclasses + config loader`

### F7b — Calcul des gains par section par mode

- `_compute_gains_for_explicit_mode`
- `_compute_gains_for_progressive_mode`
- `_compute_gains_for_peaks_dense_mode`
- `_compute_gains_for_section_lock_mode`
- Tests unitaires avec fixtures

Durée : 1.5h
Tests : 8-10
Commit : `feat(enhancement): gain profile computation for all modes`

### F7c — Cap par genre_profile

- Application des caps `presence_boost_max_db` et autres
- Warnings quand cap activé
- Tests

Durée : 45min
Tests : 3-4
Commit : `feat(enhancement): genre profile cap enforcement`

### F7d — Écriture automations Gain + IsOn dans EQ8

- Allocation de bande, find or create EQ8
- Écriture des automations avec crossfades
- Protection des autres bandes

Durée : 1.5h
Tests : 5-6
Commit : `feat(enhancement): write dynamic gain automations to EQ8`

### F7e — API principale + integration tests

- Fonction publique + orchestration
- Tests end-to-end

Durée : 1h
Tests : 4-6
Commit : `feat(enhancement): public API + integration tests`

### F7f — CLI wrapper

Script avec flags + preview + batch mode.

Durée : 45min-1h
Tests : 2-3
Commit : `feat(cli): dynamic enhancement application script`

**Total F7 :** 6h-7h, ~25-34 tests, 6 micro-commits.

---

## 9 — Validation terrain

Après livraison F7, tester sur Acid Drops avec deux intents typiques :

- Voice presence boost conditionnel (Drops + Chorus)
- Air progressif sur Climax

Protocole A/B avec et sans enhancement dynamique.

---

## 10 — Risques techniques identifiés

| Risque | Mitigation |
|---|---|
| Utilisateur mal configure les gains → mix déséquilibré | Cap automatique par genre profile + preview obligatoire avant write |
| Gain automation cause pops au crossfade | Crossfade long par défaut (2 beats), alternative : fade Q au lieu de Gain |
| Trop de `Musical Enhancement` bandes → EQ8 surchargé | Cap à 6 bandes, warning si dépassement |
| Chevauchement de fréquences entre plusieurs enhancements | Détection et warning dans le report |
| Peaks_dense_mix mal calibré → résultats erratiques | Mode explicit par défaut, peaks_dense_mix opt-in avec documentation |

---

## 11 — Hors scope F7

- Enhancements multi-bandes corrélés (ex: smile curve combinée) → batch de intents simples suffit
- Enhancement M/S séparé Mid vs Side → Feature 4 (eq8_stereo_ms déjà specifiée)
- Harmonic excitation / saturation dynamique → hors EQ8, scope autre feature
- Compensation de volume automatique post-enhancement → manuel pour l'instant

---

## 12 — Dépendances validation utilisateur avant dev

**Q1 —** Le format de config (YAML vs JSON) te convient-il ? Ou préférer un autre format ?
**Q2 —** La convention "Musical Enhancement" comme 4ème EQ8 autorisé est-elle acceptable ?
**Q3 —** Le mode "peaks_dense_mix" adaptatif est-il prioritaire, ou on commence avec seulement explicit + progressive + section_lock ?
**Q4 —** Priorité F7 vs autres features dans la roadmap ?

---

**Fin spec Feature 7. Validation utilisateur attendue avant démarrage dev.**
