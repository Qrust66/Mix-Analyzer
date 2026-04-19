# Feature 3 — Détection de sections et Locators

## Référence : Mix Analyzer v3.1 / Feature 3 de N

**Version** : 1.1 (mise à jour pour intégration avec Features 3.5 TFP et 3.6 CDE)

---

## 1. Problème métier

Le système traite les 64 buckets temporels comme une séquence plate. Il ne sait pas que les buckets 0-10 sont l'intro, 24-45 sont le drop, 45-48 sont le break. Chaque correction est calculée avec le même contexte du début à la fin.

**Conséquences :**
- Un HPF justifié dans le drop (kick présent) est aussi appliqué dans l'intro (kick absent).
- Le masking Kick ↔ Sub Bass est calculé comme un score moyen, alors qu'il n'existe que dans les sections où les deux jouent.
- Les seuils d'accumulation sont faussés : 6 tracks jouent à 248 Hz en moyenne, mais en réalité 2 jouent dans l'intro et 6 dans le drop.

Un morceau de musique a des sections. L'ingénieur pense en sections. Le système doit aussi.

**Note v1.1 :** Feature 3 reste autonome — elle peut tourner sans 3.5 (TFP) ni 3.6 (CDE). Mais ses outputs sont **enrichis automatiquement** quand 3.5 et 3.6 sont disponibles.

---

## 2. Objectif

1. Détecter automatiquement les sections du morceau (intro, build, drop, break, outro) à partir des features spectrales.
2. Écrire des **Locators** dans le `.als` pour que l'utilisateur voie les sections dans Ableton, avec annotations enrichies si TFP et CDE sont présents.
3. Construire une **matrice de co-présence** : pour chaque section, quelles tracks jouent et avec quelle énergie.
4. Exposer les sections comme données pour les Features 1, 2, 3.5, 3.6, 4, 5.

---

## 3. Détection de sections

### Méthode

Le `delta_spectrum` (déjà extrait dans v2.5) mesure le changement spectral frame-to-frame. Un spike dans le delta = transition de section.

**Algorithme :**

```
1. Calculer delta_spectrum_smoothed = moyenne glissante du delta_spectrum (fenêtre 3 buckets)
2. Calculer le seuil adaptatif = médiane(delta_spectrum) × multiplicateur (ex: 2.5)
3. Les frames où delta_spectrum_smoothed > seuil = candidats de transition
4. Fusionner les candidats trop proches (< 4 buckets apart = même transition)
5. Chaque segment entre deux transitions = une section
```

### Labellisation automatique

Chaque section reçoit un label basé sur ses caractéristiques :

| Caractéristique | Label |
|---|---|
| Première section | "INTRO" |
| Dernière section | "OUTRO" |
| Énergie totale > 80e percentile | "DROP" ou "CHORUS" |
| Énergie totale < 20e percentile | "BREAK" ou "BRIDGE" |
| Énergie croissante sur 4+ buckets | "BUILD" |
| Énergie décroissante sur 4+ buckets | "BREAKDOWN" |
| Ni haute ni basse | "VERSE" ou "SECTION_N" |

Les labels sont des suggestions — l'utilisateur peut les renommer dans Ableton via les Locators.

### Données produites

```python
@dataclass
class Section:
    index: int                    # 0, 1, 2, ...
    label: str                    # "INTRO", "DROP", etc.
    start_bucket: int             # index du bucket de début
    end_bucket: int               # index du bucket de fin
    start_seconds: float          # en secondes
    end_seconds: float            # en secondes
    start_beats: float            # en beats
    end_beats: float              # en beats
    total_energy_db: float        # énergie RMS totale de la section
    tracks_active: list[str]      # noms des tracks audibles dans cette section
    track_energy: dict[str, dict[str, float]]  # {track_name: {zone: avg_energy_db}}

    # NOUVEAU v1.1 — enrichissements optionnels (None si TFP/CDE absent)
    tfp_summary: SectionTFPSummary | None        # résumé des fonctions par track (Feature 3.5)
    diagnostic_summary: SectionDiagnosticSummary | None  # résumé des diagnostics (Feature 3.6)
```

```python
# NOUVEAU v1.1
@dataclass
class SectionTFPSummary:
    """Résumé des fonctions de tracks dans cette section (depuis Feature 3.5)."""
    heroes: list[str]                    # tracks classées *_hero dans cette section
    rhythmic_engine: list[str]           # tracks rhythmic_*
    harmonic_layer: list[str]            # tracks harmonic_pad, lead_synth
    atmosphere: list[str]                # tracks atmosphere
    skipped: list[str]                   # tracks marquées skip dans cette section

@dataclass
class SectionDiagnosticSummary:
    """Résumé des diagnostics CDE pour cette section (depuis Feature 3.6)."""
    total_diagnostics: int
    by_severity: dict[str, int]          # {"critical": 2, "moderate": 4, "minor": 1}
    by_issue_type: dict[str, int]        # {"masking_conflict": 3, "resonance_buildup": 2}
    top_conflicts: list[str]             # ["Kick↔Sub Bass (Low: 0.82)", ...]
```

---

## 4. Matrice de co-présence

Pour chaque section, une matrice qui répond à : "qui joue avec qui, et où dans le spectre?"

```
SECTION 3: DROP (T=88.0s–168.0s, buckets 24-45)

Tracks actives (25/35):
  Kick 1          | Sub: -6   Low: -14  Mud: -42  Mid: -65  Pres: -70
  Sub Bass        | Sub: -3   Low: -18  Mud: -55  Mid: -70  Pres: -80
  Acid Bass       | Sub: -10  Low: -8   Mud: -12  Mid: -25  Pres: -40
  Toms Rack       | Sub: -25  Low: -22  Mud: -35  Mid: -38  Pres: -42
  NINja Lead      | Sub: -50  Low: -30  Mud: -18  Mid: -12  Pres: -15
  ...

Conflits dans cette section:
  Kick ↔ Sub Bass  | Low: 0.82  ← CRITIQUE
  Kick ↔ Acid Bass | Low: 0.45
  Acid Bass ↔ Sub  | Sub: 0.71  ← CRITIQUE
  Toms ↔ Acid Bass | Mud: 0.38

Accumulations:
  248 Hz: 6 tracks simultanées ← MUD RISK
  120 Hz: 3 tracks ← OK
```

### Stockage

Nouveau sheet caché : `_track_sections`

| Section | Label | Start (s) | End (s) | Tracks actives | Total energy | Heroes (TFP) | Diagnostics (CDE) |
|---|---|---|---|---|---|---|---|
| 0 | INTRO | 0.0 | 29.3 | 5 | -35.2 | — | 0 |
| 1 | BUILD | 29.3 | 44.0 | 12 | -22.1 | — | 1 |
| 2 | DROP | 44.0 | 95.4 | 25 | -8.5 | Pluck Lead, NINja | 12 |
| 3 | BREAK | 95.4 | 110.0 | 8 | -28.3 | Ambience | 3 |

Les colonnes "Heroes (TFP)" et "Diagnostics (CDE)" sont vides si 3.5/3.6 ne sont pas disponibles.

Nouveau sheet caché : `_track_copresence`

| Section | Track | Sub | Low | Mud | Body | Mid | Pres | Sib | Air |
|---|---|---|---|---|---|---|---|---|---|
| DROP | Kick 1 | -6.0 | -14.2 | -41.5 | ... | ... | ... | ... | ... |
| DROP | Sub Bass | -2.7 | -18.3 | ... | ... | ... | ... | ... | ... |

---

## 5. Locators dans le .als

### Structure XML d'un Locator Ableton

```xml
<Locators>
    <Locators>
        <Locator Id="0">
            <Time Value="0.0" />
            <Name Value="INTRO" />
            <Annotation Value="" />
            <IsSongStart Value="false" />
            <LockEnvelope Value="0" />
        </Locator>
        <Locator Id="1">
            <Time Value="352.0" />
            <Name Value="v3.1_DROP" />
            <Annotation Value="..." />
            <IsSongStart Value="false" />
            <LockEnvelope Value="0" />
        </Locator>
    </Locators>
</Locators>
```

**Localisation dans le XML :** `LiveSet/Locators/Locators`

**Convention de nommage :** préfixer `v3.1_` pour distinguer les locators générés des locators manuels de l'utilisateur. Ne jamais supprimer/modifier les locators existants.

### Annotations — trois niveaux selon les features disponibles

**Niveau 1 — Feature 3 seule (basique) :**
```xml
<Annotation Value="25 tracks, energy -8.5 dB" />
```

**Niveau 2 — Feature 3 + 3.5 (TFP) :**
```xml
<Annotation Value="25 tracks. Heroes: Pluck Lead, NINja Lead Synth. Rhythm: Kick 1, Sub Bass, Bass Rythm." />
```

**Niveau 3 — Feature 3 + 3.5 + 3.6 (TFP + CDE) :**
```xml
<Annotation Value="25 tracks. Heroes: Pluck Lead, NINja. 12 diagnostics (2 critical). Top conflict: Kick↔Sub Bass (Low: 0.82)." />
```

L'annotation est **construite dynamiquement** selon ce qui est disponible. Si TFP est absent, on saute la mention des heroes. Si CDE est absent, on saute le compte de diagnostics.

### Fonction

```python
def write_section_locators(
    als_path: Path,
    sections: list[Section],
    prefix: str = "v3.1_",
    overwrite_existing: bool = False,
) -> int:
    """Écrit des Locators dans le .als pour chaque section détectée.

    Si overwrite_existing=True, supprime les locators préfixés existants avant d'écrire.
    Si False, ajoute sans toucher aux existants.

    L'annotation de chaque locator est construite selon les enrichissements disponibles
    dans Section (tfp_summary, diagnostic_summary).

    Returns: nombre de locators écrits.
    """

def build_locator_annotation(section: Section) -> str:
    """Construit l'annotation textuelle selon les enrichissements présents.

    Niveau 1 (Feature 3 seule) : "N tracks, energy X dB"
    Niveau 2 (+ TFP) : ajoute "Heroes: ..., Rhythm: ..."
    Niveau 3 (+ CDE) : ajoute "N diagnostics (M critical). Top conflict: ..."
    """
```

---

## 6. Intégration avec les autres features

Feature 3 produit des `Section` qui sont consommées par tous les modules en aval. Le contrat est unidirectionnel : Feature 3 ne dépend de personne, mais ses outputs sont enrichis quand TFP et CDE sont présents.

### Avec Feature 1 (correction conditionnelle)

Le `CorrectionContext` reçoit le champ `current_section`. La cascade de décision devient section-aware (voir spec Feature 1 § 4).

```
ÉTAPE 3 — Masking ?
  AVANT : masking score moyen sur toute la durée
  APRÈS : masking score DANS LA SECTION COURANTE

  → Le HPF sur Guitar Distorted est justifié dans le DROP (masking avec Kick)
    mais PAS dans l'INTRO (Kick absent dans cette section)
```

**Note v1.1 :** quand Feature 3.6 (CDE) est implémenté, Feature 1 consomme CDE qui consomme les sections. La logique reste équivalente, mais passe par un intermédiaire.

### Avec Feature 3.5 (TFP)

TFP **dépend de Feature 3** — les `function_by_section` requièrent que les sections soient détectées.

Feature 3 enrichit ses propres outputs avec TFP **a posteriori** : après que TFP a tourné, les `Section.tfp_summary` sont remplies.

```
PIPELINE COMPLET :
  1. Feature 3 produit Section (sans tfp_summary)
  2. Feature 3.5 consomme Section, produit TrackFunctionProfile par track
  3. Feature 3 enrichit Section.tfp_summary avec les profils
  4. Feature 3 réécrit les Locators avec annotations niveau 2
```

### Avec Feature 3.6 (CDE)

CDE **dépend de Feature 3 et 3.5**. Génère des diagnostics par section.

Même pattern d'enrichissement a posteriori :

```
  5. Feature 3.6 consomme Section + TFP, produit CorrectionDiagnostic par décision
  6. Feature 3 enrichit Section.diagnostic_summary avec les comptes
  7. Feature 3 réécrit les Locators avec annotations niveau 3
```

### Avec Features 4 (M/S) et 5 (autres devices)

Ces features consomment les sections via Feature 1 (qui consomme CDE qui consomme Sections). Pas de dépendance directe.

---

## 7. Tests d'acceptance

### Test 1 — Détection de transitions
- Audio synthétique : 5 sec silence → 5 sec bruit rose → 5 sec silence → 5 sec sinus
- **Attendu :** 4 sections détectées avec transitions à ~5s, ~10s, ~15s

### Test 2 — Labellisation
- Section avec max énergie → label contient "DROP" ou "CHORUS"
- Première section → "INTRO"
- Dernière section → "OUTRO"

### Test 3 — Locators dans le .als (niveau 1, sans TFP/CDE)
- Après écriture, le `.als` contient des Locators préfixés "v3.1_"
- Les Time correspondent aux transitions détectées (en beats)
- Les annotations contiennent "N tracks, energy X dB"
- Les locators existants de l'utilisateur sont intacts

### Test 4 — Matrice de co-présence
- Section DROP : tracks avec énergie > -40 dB dans au moins une zone sont listées comme "actives"
- Section BREAK : moins de tracks actives que le DROP

### Test 5 — Intégration Feature 1
- Correction HPF sur Guitar dans la section INTRO = non justifiée (pas de masking)
- Même correction dans la section DROP = justifiée (masking avec Kick)
- Le `dynamic_mask` reflète cette différence section par section

### Test 6 — Annotation niveau 2 (avec TFP) — NOUVEAU v1.1
- TFP disponible avec heroes identifiés dans le DROP
- **Attendu :** annotation du locator DROP contient "Heroes: ..., Rhythm: ..."

### Test 7 — Annotation niveau 3 (avec TFP + CDE) — NOUVEAU v1.1
- TFP et CDE disponibles
- **Attendu :** annotation contient "N diagnostics (M critical). Top conflict: ..."

### Test 8 — Enrichissement a posteriori — NOUVEAU v1.1
- Feature 3 tourne seule → sections sans tfp_summary
- TFP tourne → Section.tfp_summary remplis
- Feature 3 réécrit les locators (overwrite_existing=True)
- **Attendu :** annotations passent de niveau 1 à niveau 2

---

## 8. Dépendances

### Dépendances de Feature 3 (ce dont elle a besoin)

- **`delta_spectrum`** (v2.5) : déjà extrait. Source primaire pour la détection de transitions.
- **`_track_zone_energy`** : pour calculer l'énergie par section et par track.
- **`_track_automation_map`** : pour savoir quelles tracks sont audibles par section.
- **als_utils.py** : ajout de fonctions pour écrire/lire des Locators.

### Dépendants de Feature 3 (ce qui consomme ses outputs)

- **Feature 1** : `CorrectionContext.current_section`
- **Feature 3.5 (TFP)** : `function_by_section` requiert les sections
- **Feature 3.6 (CDE)** : diagnostics par section
- **Feature 4 (M/S)** : corrections section-aware
- **Feature 5 (devices)** : compression et width section-aware

### Enrichissements optionnels (ce qui enrichit les outputs de Feature 3)

- **Feature 3.5** : remplit `Section.tfp_summary`
- **Feature 3.6** : remplit `Section.diagnostic_summary`

Feature 3 reste fonctionnelle même sans ces enrichissements (annotations niveau 1).

---

## 9. Plan de développement

### Phase A — Détection de sections (v1.0)
- Nouveau module `section_detector.py`
- `detect_sections(delta_spectrum, zone_energy, times, threshold_multiplier=2.5) -> list[Section]`
- Labellisation automatique
- Tests sur fixture synthétique + Acid Drops

### Phase B — Matrice de co-présence (v1.0)
- `build_copresence_matrix(sections, all_tracks_zone_energy, automation_maps) -> dict`
- Sheet `_track_sections` et `_track_copresence`
- Tests : vérifier le nombre de tracks actives par section

### Phase C — Locators dans le .als (v1.0)
- `write_section_locators()` dans `als_utils.py`
- `build_locator_annotation()` avec support niveau 1
- Lecture du XML Locators, ajout sans écraser
- Tests : round-trip écriture → relecture

### Phase D — Intégration Feature 1 (v1.0)
- Enrichir `CorrectionContext` avec les sections
- Adapter la cascade de décision pour être section-aware
- Tests : même correction justifiée dans une section mais pas une autre

### Phase E — Enrichissements TFP (v1.1) — NOUVEAU
- `Section.tfp_summary` rempli a posteriori
- `build_locator_annotation()` étendu pour niveau 2
- API `enrich_sections_with_tfp(sections, tfp) -> list[Section]`
- Tests : Test 6 et 8

### Phase F — Enrichissements CDE (v1.1) — NOUVEAU
- `Section.diagnostic_summary` rempli a posteriori
- `build_locator_annotation()` étendu pour niveau 3
- API `enrich_sections_with_diagnostics(sections, diagnostics) -> list[Section]`
- Tests : Test 7

---

## 10. Pipeline d'exécution recommandé

Pour profiter de tous les enrichissements :

```python
# Étape 1 — Détection des sections (toujours nécessaire)
sections = detect_sections(delta_spectrum, zone_energy, times)
sections = build_copresence_matrix(sections, ...)
write_section_locators(als_path, sections, prefix="v3.1_")
# → annotations niveau 1

# Étape 2 — TFP (optionnel mais recommandé)
tfp = generate_tfp(als_path, report_path, sections)  # Feature 3.5
sections = enrich_sections_with_tfp(sections, tfp)
write_section_locators(als_path, sections, prefix="v3.1_", overwrite_existing=True)
# → annotations niveau 2

# Étape 3 — CDE (optionnel)
diagnostics = generate_diagnostics(als_path, report_path, sections, tfp)  # Feature 3.6
sections = enrich_sections_with_diagnostics(sections, diagnostics)
write_section_locators(als_path, sections, prefix="v3.1_", overwrite_existing=True)
# → annotations niveau 3
```

Chaque étape est **autonome** : on peut s'arrêter à n'importe quel niveau et avoir un résultat utilisable.
