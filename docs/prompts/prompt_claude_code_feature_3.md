# TÂCHE : Implémenter Feature 3 — Détection de sections + Locators + Onglet timeline

## Anti-timeout : règles strictes

**Tu vas timeout si tu fais trop dans une seule opération.** Découpe en 4 phases (A, B, C, D), chacune testée et commitée avant de passer à la suivante.

1. **Ne lis PAS tout le repo d'un coup.** Consulte seulement les fichiers pertinents pour la phase en cours.
2. **Pas d'analyse exploratoire inutile.** Tu as toutes les infos nécessaires dans la spec et ce prompt.
3. **Pickle les états intermédiaires** si une phase est longue.
4. **Commit après chaque phase** pour ne pas perdre de travail si interruption.
5. **Arrête-toi après chaque phase** et demande confirmation avant de continuer.

## Lecture préalable obligatoire

1. `feature_3_sections_locators_v1_1.md` — spec de référence (mais lis attentivement les RÈGLES SIMPLIFIÉES ci-dessous qui surchargent certaines parties)
2. `ableton_devices_mapping.json` — sections `$device_list_id`, `$id_replacement_rules`, `$tempo_mapping`, `$sections_integration`
3. `CLAUDE.md` — conventions du repo
4. Repo : survole `spectral_evolution.py`, `feature_storage.py`, `als_utils.py`, `mix_analyzer.py` pour comprendre l'architecture

**Ne lis PAS** : autres Features (1, 2, 3.5, 3.6, 4, 5). Feature 3 est autonome dans cette implémentation.

## Règles simplifiées (PRIMENT sur la spec si conflit)

### 1. Workflow de détection des sections

```
SI le .als ne contient AUCUN Locator :
  → Claude Code détecte les sections automatiquement
  → Écrit les Locators avec noms simples : "Section 1", "Section 2", "Section 3", ..., "Section N"
  → Écriture directe (pas de confirmation préalable)

SI le .als contient au moins 1 Locator :
  → Skip la détection
  → Lit les Locators existants tels quels (peu importe leur nom)
  → Ces Locators sont la source de vérité
  → NE TOUCHE À RIEN
```

L'utilisateur est roi. Il peut renommer "Section 3" en "Drop principal", déplacer un Locator, en ajouter un manuellement, en supprimer un. Le système respecte tout ce qu'il fait.

### 2. Convention de nommage

- Auto-généré : `Section 1`, `Section 2`, ..., `Section N` (espace entre "Section" et le numéro)
- Pas de préfixe `v3.1_` ou autre
- Pas de labels suggestifs (DROP, BUILD, etc.) — l'utilisateur décide

### 3. Onglet Excel : `_sections_timeline`

**Apparaît UNIQUEMENT si des Locators sont détectés** (auto-générés ou utilisateur).

Sinon → pas d'onglet, pas d'erreur, juste absence silencieuse.

**Lecture seule** — l'utilisateur ne modifie JAMAIS ce sheet. Toute modification se fait dans Ableton via les Locators.

### 4. Pas de modification des autres sheets

`_track_zone_energy`, `Freq Conflicts`, `_track_peak_trajectories`, `Anomalies`, etc. restent **identiques**. On ajoute SEULEMENT `_sections_timeline`.

### 5. Pas de Section.tfp_summary ni diagnostic_summary

Ces champs existent dans la spec pour Features 3.5/3.6 futures. Pour Feature 3 maintenant, ne les implémente PAS. Le dataclass `Section` peut les avoir comme champs `Optional[None]` mais ils restent toujours `None`.

## Découpage en 4 phases

### Phase A — `section_detector.py` + détection des sections

**Objectif** : module autonome qui détecte les sections depuis delta_spectrum, OU lit les Locators existants.

**Fichiers à créer** :
- `section_detector.py` — nouveau module
- `tests/test_section_detector.py` — tests unitaires

**Fonctions à implémenter** :

```python
@dataclass
class Section:
    index: int                    # 1, 2, 3, ... (1-indexed pour matcher "Section 1")
    name: str                     # "Section 1" ou nom utilisateur si édité
    start_bucket: int
    end_bucket: int
    start_seconds: float
    end_seconds: float
    start_beats: float
    end_beats: float
    total_energy_db: float
    tracks_active: list[str]
    track_energy: dict[str, dict[str, float]]
    # Champs Optional pour futures features (toujours None pour Feature 3)
    tfp_summary: Optional[dict] = None
    diagnostic_summary: Optional[dict] = None

def detect_sections_from_audio(
    delta_spectrum: np.ndarray,
    zone_energy: np.ndarray,
    times: np.ndarray,
    threshold_multiplier: float = 2.5,
) -> list[Section]:
    """Détecte les sections depuis l'analyse audio.
    Algorithme :
    1. delta_spectrum_smoothed = moyenne glissante (fenêtre 3 buckets)
    2. seuil = mediane(delta_spectrum) × threshold_multiplier
    3. transitions = frames où delta > seuil
    4. fusionner transitions trop proches (< 4 buckets apart)
    5. chaque segment entre transitions = une section
    Nomme les sections "Section 1", "Section 2", ..., "Section N".
    """

def get_or_detect_sections(
    als_path: Path,
    delta_spectrum: np.ndarray,
    zone_energy: np.ndarray,
    times: np.ndarray,
    tempo_events: list[tuple[float, float]],
) -> tuple[list[Section], bool]:
    """Logique principale :
    - Si .als a des Locators : les lire, retourner sections + False (pas écrites)
    - Sinon : détecter, écrire les Locators, retourner sections + True (écrites)
    Retourne (sections, were_written).
    """
```

**Tests à passer** :
- Test 1 : audio synthétique silence→bruit→silence→sinus → 4 sections détectées, nommées "Section 1" à "Section 4"
- Test 2 : `.als` sans Locators → détection + écriture
- Test 3 : `.als` avec Locators existants → skip détection, lecture des Locators

**Livrable Phase A** : module testé, commit avec message "Feature 3 Phase A: section detector + auto/manual workflow", STOP, demander confirmation.

### Phase B — Lecture/écriture des Locators dans le .als

**Objectif** : utilitaires XML pour lire et écrire des Locators sans casser les existants.

**Fichiers à modifier/créer** :
- `als_utils.py` — ajouter `read_locators()` et `write_locators()`
- `tests/test_locators.py` — tests

**Fonctions à implémenter** :

```python
def read_locators(als_path: Path) -> list[dict]:
    """Lit tous les Locators depuis LiveSet/Locators/Locators.
    Retourne liste de dicts avec keys: id, time_beats, name, annotation.
    """

def write_locators(
    als_path: Path,
    new_locators: list[dict],
    output_path: Path = None,
) -> int:
    """Écrit de nouveaux Locators dans le .als.
    PRESERVE TOUS LES LOCATORS EXISTANTS — n'écrit que si la liste est vide.
    Utilise max(existing_ids) + 1 pour les nouveaux Ids (règle $device_list_id).
    Si output_path est None, sauvegarde sous als_path + "_with_sections.als".
    Retourne le nombre de locators écrits.
    """

def seconds_to_beats(time_s: float, tempo_events: list[tuple[float, float]]) -> float:
    """Conversion tempo-aware (voir $tempo_mapping)."""
```

**Règles XML strictes** :
- Locators vont dans `LiveSet/Locators/Locators`
- Modification du XML comme TEXTE BRUT (jamais ET.tostring(), voir `$id_replacement_rules`)
- Ids uniques dans la liste (max+1)
- `Time Value` en BEATS (conversion via tempo map)
- gzip.compress() standard pour sauvegarder
- Jamais écraser le fichier original

**Tests à passer** :
- Test : écriture de 5 Locators, relecture donne les mêmes données
- Test : `.als` avec Locators existants + appel write_locators avec liste vide → fichier inchangé
- Test : Time des Locators correspond aux beats attendus avec tempo map non-triviale

**Livrable Phase B** : Locators fonctionnels dans Acid Drops (test sur `.als` réel), commit, STOP, confirmation.

### Phase C — Onglet `_sections_timeline` dans Excel

**Objectif** : générer le sheet user-friendly qui croise sections + données existantes.

**Fichiers à modifier** :
- `feature_storage.py` — ajouter `build_sections_timeline_sheet()`
- `section_detector.py` — ajouter les helpers d'analyse par section
- `tests/test_sections_timeline.py` — tests

**Format de l'onglet** (à reproduire fidèlement) :

```
═══════════════════════════════════════════════════════════════
VUE MAÎTRE — TOUTES LES SECTIONS
═══════════════════════════════════════════════════════════════

| # | Section    | Start | End  | Durée | Tracks | Énergie | Conflits crit. | Conflits mod. |
| 1 | Section 1  | 0:00  | 0:29 | 29s   | 5      | -28 dB  | 0              | 1             |
| 2 | Section 2  | 0:29  | 0:44 | 15s   | 12     | -22 dB  | 1              | 3             |
| 3 | Section 3  | 0:44  | 1:35 | 51s   | 25     | -8 dB   | 4              | 8             |
... (une ligne par section)

═══════════════════════════════════════════════════════════════
SECTION 1 — "Section 1" (0:00 - 0:29, durée 29s, 5 tracks actives)
═══════════════════════════════════════════════════════════════

TRACKS ACTIVES PAR ZONE D'ÉNERGIE DOMINANTE
─────────────────────────────────────────────────────────────
| ZONE             | TRACKS DOMINANTES                       |
| Sub (20-60 Hz)   | (aucune track significative)            |
| Low (60-200 Hz)  | Bass Rythm (-15 dB)                     |
| Mud (200-500 Hz) | Pluck Lead (-22 dB), Ambience (-25 dB)  |
... (8 zones)

CONFLITS DE FRÉQUENCES (par sévérité)
─────────────────────────────────────────────────────────────
| SÉVÉRITÉ | FRÉQ    | TRACKS EN CONFLIT                    | SCORE |
| MODÉRÉ   | 247 Hz  | Pluck Lead (-22 dB) ↔ Ambience (-25) | 0.55  |

ACCUMULATIONS (4+ tracks à la même fréquence)
─────────────────────────────────────────────────────────────
(Aucune accumulation dans cette section)

PEAK MAX PAR TRACK DANS CETTE SECTION
─────────────────────────────────────────────────────────────
| TRACK        | FRÉQ DU PEAK MAX | AMPLITUDE | DURÉE ACTIVE |
| Bass Rythm   | 127 Hz           | +5 dB     | 29 / 29s (100%) |
| Pluck Lead   | 247 Hz           | +3 dB     | 12 / 29s (41%)  |
... (toutes les tracks actives)

OBSERVATIONS
─────────────────────────────────────────────────────────────
• Section calme (5 tracks actives, énergie -28 dB)
• Bass Rythm joue en continu — possible élément ambient
• Pas d'accumulation, pas de conflit critique

═══════════════════════════════════════════════════════════════
SECTION 2 — "Section 2" (0:29 - 0:44, durée 15s, 12 tracks actives)
═══════════════════════════════════════════════════════════════
... (même format)
```

**Fonctions à implémenter** :

```python
def build_sections_timeline_sheet(
    workbook: openpyxl.Workbook,
    sections: list[Section],
    all_tracks_zone_energy: dict,
    all_tracks_peak_trajectories: dict,
    masking_scores: dict,
) -> None:
    """Crée le sheet '_sections_timeline' avec vue maître + bloc par section.
    Pas de couleurs, pas de formules, juste du texte/tableau brut.
    """

def detect_conflicts_in_section(
    section: Section,
    all_tracks_zone_energy: dict,
    masking_scores: dict,
) -> list[dict]:
    """Identifie les paires de tracks en conflit DANS CETTE SECTION SPÉCIFIQUE.
    Sévérité : score > 0.7 = critique, 0.4-0.7 = modéré, < 0.4 = léger (skip).
    """

def detect_accumulations_in_section(
    section: Section,
    all_tracks_zone_energy: dict,
    frequency_tolerance_semitones: float = 1.0,
    min_tracks: int = 4,
) -> list[dict]:
    """Identifie les fréquences où 4+ tracks ont de l'énergie significative."""

def generate_observations(section: Section, conflicts, accumulations) -> list[str]:
    """Génère 2-5 observations en langage naturel (pattern recognition basique).
    Exemples :
    - "Section dense (25 tracks actives, énergie -8 dB)"
    - "5 tracks compètent à 247 Hz — zone la plus encombrée"
    - "Pluck Lead a un peak signature à 247 Hz (présent 94% du temps)"
    - "Sub Bass et Kick 1 entrent en collision permanente sous 100 Hz"
    """
```

**Tests à passer** :
- Test : sheet généré pour Acid Drops avec format correct
- Test : conflits triés par sévérité
- Test : observations générées pour chaque section
- Test : si pas de Locators dans le .als → pas de sheet `_sections_timeline`

**Livrable Phase C** : sheet fonctionnel dans le rapport Excel, commit, STOP, confirmation.

### Phase D — Intégration dans `mix_analyzer.py`

**Objectif** : Feature 3 appelée automatiquement par le pipeline principal.

**Fichiers à modifier** :
- `mix_analyzer.py` — appeler `get_or_detect_sections()` et `build_sections_timeline_sheet()`
- Tests d'intégration bout-en-bout

**Intégration** :

```python
# Dans mix_analyzer.py, après extraction des features v2.5

# 1. Lire ou détecter les sections
sections, were_written = get_or_detect_sections(
    als_path=als_path,
    delta_spectrum=full_mix_delta_spectrum,
    zone_energy=full_mix_zone_energy,
    times=times,
    tempo_events=tempo_events,
)

if were_written:
    print(f"  → {len(sections)} sections détectées et écrites comme Locators dans le .als")
else:
    print(f"  → {len(sections)} sections lues depuis les Locators existants")

# 2. Si on a des sections, ajouter le sheet timeline
if sections:
    build_sections_timeline_sheet(
        workbook=wb,
        sections=sections,
        all_tracks_zone_energy=all_tracks_zone_energy,
        all_tracks_peak_trajectories=all_tracks_peak_trajectories,
        masking_scores=masking_scores,
    )
```

**Tests d'intégration** :
- Run complet sur Acid Drops produit le rapport + Locators dans le .als
- Re-run du même .als : skip détection, lit les Locators
- Vérifier visuellement dans Ableton que les Locators sont aux bonnes positions
- Vérifier visuellement dans Excel que le sheet `_sections_timeline` est lisible

**Livrable Phase D** : Pipeline complet fonctionnel, commit, STOP.

## Règles absolues

1. **Modifier le XML comme du texte** (jamais ET.tostring(), voir `$id_replacement_rules`)
2. **Préserver TOUS les Locators existants** — ne JAMAIS modifier ou supprimer ce qui est déjà dans le .als
3. **Ids uniques dans LiveSet/Locators/Locators** (max+1, voir `$device_list_id`)
4. **Conversion tempo-aware** des secondes vers beats (voir `$tempo_mapping`)
5. **Convention de nommage** : `Section 1`, `Section 2`, ..., `Section N` (avec espace, 1-indexed)
6. **gzip.compress() standard** pour sauvegarder le `.als`
7. **Jamais écraser le fichier original** — sauvegarder sous un nouveau nom
8. **Excel = read-only** — l'utilisateur ne modifie JAMAIS le sheet `_sections_timeline`
9. **Toute modification se fait dans Ableton** via les Locators
10. **Commit après chaque phase** avec message clair

## Règles spécifiques Claude Code

1. **Arrête-toi après chaque phase** et attends confirmation avant de continuer
2. **Si tu timeout** : pickle l'état, sauvegarde ce que tu as, indique clairement où tu en es
3. **Lis les fichiers du repo seulement quand nécessaire** pour la phase en cours
4. **Utilise les tests** pour valider — ne passe pas à la phase suivante sans tests verts
5. **Demande clarification** si tu tombes sur une ambiguïté dans la spec, ne devine pas

## Validation finale après les 4 phases

1. Ouvre Acid Drops dans Ableton
2. Vérifie que les Locators sont visibles à la bonne position musicale
3. Si la détection auto a des erreurs : renomme/déplace/supprime dans Ableton, sauvegarde
4. Re-run Mix Analyzer → vérifie que le système respecte tes modifications
5. Vérifie que le rapport Excel contient le sheet `_sections_timeline`
6. Vérifie que le sheet est lisible et actionnable

Puis demande-moi si on passe à la suite (Feature 3.5 ou Cleaning) ou si on fait des ajustements sur Feature 3.

## Si tu bloques

**Timeout** : pickle l'état, commit, informe-moi de la dernière phase complétée.

**Ambiguïté dans la spec** : liste les options possibles, demande mon arbitrage.

**Bug dans le code existant** : isole le bug, documente-le, ne contourne pas silencieusement.

**Conflit de version de bibliothèque** : utilise celle du `requirements.txt` actuel, ne l'upgrade pas sans me demander.
