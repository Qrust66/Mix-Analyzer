# Feature 3 — Détection de sections et Locators

## Référence : Mix Analyzer v3.1 / Feature 3 de 6

---

## 1. Problème métier

Le système traite les 64 buckets temporels comme une séquence plate. Il ne sait pas que les buckets 0-10 sont l'intro, 24-45 sont le drop, 45-48 sont le break. Chaque correction est calculée avec le même contexte du début à la fin.

**Conséquences :**
- Un HPF justifié dans le drop (kick présent) est aussi appliqué dans l'intro (kick absent).
- Le masking Kick ↔ Sub Bass est calculé comme un score moyen, alors qu'il n'existe que dans les sections où les deux jouent.
- Les seuils d'accumulation sont faussés : 6 tracks jouent à 248 Hz en moyenne, mais en réalité 2 jouent dans l'intro et 6 dans le drop.

Un morceau de musique a des sections. L'ingénieur pense en sections. Le système doit aussi.

---

## 2. Objectif

1. Détecter automatiquement les sections du morceau (intro, build, drop, break, outro) à partir des features spectrales.
2. Écrire des **Locators** dans le `.als` pour que l'utilisateur voie les sections dans Ableton.
3. Construire une **matrice de co-présence** : pour chaque section, quelles tracks jouent et avec quelle énergie.
4. Exposer les sections comme données pour les Features 1 et 2 (correction conditionnelle section-aware).

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

| Section | Label | Start (s) | End (s) | Tracks actives | Total energy |
|---|---|---|---|---|---|
| 0 | INTRO | 0.0 | 29.3 | 5 | -35.2 |
| 1 | BUILD | 29.3 | 44.0 | 12 | -22.1 |
| 2 | DROP | 44.0 | 95.4 | 25 | -8.5 |
| 3 | BREAK | 95.4 | 110.0 | 8 | -28.3 |

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
            <Name Value="v2.5_DROP" />
            <Annotation Value="25 tracks, energy -8.5 dB" />
            <IsSongStart Value="false" />
            <LockEnvelope Value="0" />
        </Locator>
    </Locators>
</Locators>
```

**Localisation dans le XML :** `LiveSet/Locators/Locators`

**Convention de nommage :** préfixer `v2.5_` pour distinguer les locators générés des locators manuels de l'utilisateur. Ne jamais supprimer/modifier les locators existants.

### Fonction

```python
def write_section_locators(
    als_path: Path,
    sections: list[Section],
    prefix: str = "v2.5_",
    overwrite_existing: bool = False,
) -> int:
    """Écrit des Locators dans le .als pour chaque section détectée.
    
    Si overwrite_existing=True, supprime les locators préfixés existants avant d'écrire.
    Si False, ajoute sans toucher aux existants.
    
    Returns: nombre de locators écrits.
    """
```

---

## 6. Intégration avec Feature 1 (correction conditionnelle)

Le `CorrectionContext` de Feature 1 reçoit un champ supplémentaire :

```python
@dataclass
class CorrectionContext:
    # ... champs existants ...
    
    sections: list[Section] | None       # sections détectées
    current_section: Section | None      # section du bucket en cours d'évaluation
    section_copresence: dict | None      # tracks actives dans cette section
```

La cascade de décision de Feature 1 devient section-aware :

```
ÉTAPE 3 — Masking ?
  AVANT : masking score moyen sur toute la durée
  APRÈS : masking score DANS LA SECTION COURANTE
  
  → Le HPF sur Guitar Distorted est justifié dans le DROP (masking avec Kick)
    mais PAS dans l'INTRO (Kick absent dans cette section)
```

---

## 7. Tests d'acceptance

### Test 1 — Détection de transitions
- Audio synthétique : 5 sec silence → 5 sec bruit rose → 5 sec silence → 5 sec sinus
- **Attendu :** 4 sections détectées avec transitions à ~5s, ~10s, ~15s

### Test 2 — Labellisation
- Section avec max énergie → label contient "DROP" ou "CHORUS"
- Première section → "INTRO"
- Dernière section → "OUTRO"

### Test 3 — Locators dans le .als
- Après écriture, le `.als` contient des Locators préfixés "v2.5_"
- Les Time correspondent aux transitions détectées (en beats)
- Les locators existants de l'utilisateur sont intacts

### Test 4 — Matrice de co-présence
- Section DROP : tracks avec énergie > -40 dB dans au moins une zone sont listées comme "actives"
- Section BREAK : moins de tracks actives que le DROP

### Test 5 — Intégration Feature 1
- Correction HPF sur Guitar dans la section INTRO = non justifiée (pas de masking)
- Même correction dans la section DROP = justifiée (masking avec Kick)
- Le `dynamic_mask` reflète cette différence section par section

---

## 8. Dépendances

- **`delta_spectrum`** (v2.5) : déjà extrait. Source primaire pour la détection de transitions.
- **`_track_zone_energy`** : pour calculer l'énergie par section et par track.
- **`_track_automation_map`** : pour savoir quelles tracks sont audibles par section.
- **Feature 1** : la détection de sections enrichit le CorrectionContext. Peut être implémenté avant ou après Feature 1, mais les deux se renforcent.
- **als_utils.py** : ajout de fonctions pour écrire/lire des Locators.

---

## 9. Plan de développement

### Phase A — Détection de sections
- Nouveau module `section_detector.py`
- `detect_sections(delta_spectrum, zone_energy, times, threshold_multiplier=2.5) -> list[Section]`
- Labellisation automatique
- Tests sur fixture synthétique + Acid Drops

### Phase B — Matrice de co-présence
- `build_copresence_matrix(sections, all_tracks_zone_energy, automation_maps) -> dict`
- Sheet `_track_sections` et `_track_copresence`
- Tests : vérifier le nombre de tracks actives par section

### Phase C — Locators dans le .als
- `write_section_locators()` dans `als_utils.py`
- Lecture du XML Locators, ajout sans écraser
- Tests : round-trip écriture → relecture

### Phase D — Intégration Feature 1
- Enrichir `CorrectionContext` avec les sections
- Adapter la cascade de décision pour être section-aware
- Tests : même correction justifiée dans une section mais pas une autre
