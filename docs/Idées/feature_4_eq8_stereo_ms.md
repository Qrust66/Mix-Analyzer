# Feature 4 — EQ8 stéréo (L/R et M/S)

## Référence : Mix Analyzer v3.1 / Feature 4 de 5

---

## 1. Problème métier

Toutes les corrections EQ8 actuelles opèrent en mode Stereo — la même courbe EQ est appliquée aux canaux L et R identiquement. Ça ignore les problèmes spatiaux :

- Une résonance présente seulement dans le canal L (micro placement, room mode asymétrique) → le notch Stereo coupe aussi le R inutilement.
- Un pad très wide qui masque le centre du mix dans le low-mid → impossible de couper le mid-content du pad au centre sans affecter les côtés.
- Un lead centré qui manque de largeur → un boost stéréo uniforme ne crée pas de largeur.
- L'Acid Drops a 7 tracks avec phase négative (NINja Lead à -0.59, Roaming à -0.80, etc.) — des corrections M/S pourraient réduire le problème sans sacrifier le character stéréo.

---

## 2. Objectif

Ajouter la capacité de créer des corrections EQ8 en mode L/R ou M/S quand le problème est spatial. Le système détecte automatiquement si un problème est stéréo (vs mono/centré) et choisit le mode approprié.

**Implémentation :** créer une **deuxième instance d'EQ8** en mode M/S (ou L/R) sur la track, en plus de l'EQ8 Stereo existant. Les deux EQ8 coexistent, chacun avec son rôle.

---

## 3. Détection des problèmes spatiaux

### Données déjà disponibles

Le sheet `_track_stereo_bands` (v2.4) contient la corrélation de phase et la largeur stéréo par bande fréquentielle pour chaque track. Le rapport Anomalies liste les tracks avec PHASE_CRIT.

### Critères de détection

| Situation détectée | Données | Action EQ8 |
|---|---|---|
| Corrélation de phase < 0 dans une bande | `_track_stereo_bands` | M/S : cut Side dans cette bande pour améliorer la mono-compat |
| Largeur stéréo > 0.8 dans le low-mid | `_track_stereo_bands` | M/S : cut Side dans Low-Mid (le low-mid doit être centré) |
| Largeur stéréo asymétrique (L ≠ R) | Nouveau calcul depuis features v2.5 L/R séparés (v2.6) | L/R : correction indépendante par canal |
| Track trop étroite (width < 0.1) qui devrait avoir de la largeur | `_track_stereo_bands` + track_type | M/S : boost Side dans Presence/Air |
| Masking au centre mais pas sur les côtés | Nouveau : masking calculé en Mid vs Side | M/S : cut Mid dans la zone de masking, laisser Side intact |

### Priorité des cas

Pour la v3.1, se concentrer sur les 2 cas les plus impactants :

1. **Phase négative → cut Side** : impact direct sur la compatibilité mono, mesurable, pas subjectif.
2. **Low-mid trop wide → cut Side low-mid** : le low-mid doit être centré dans quasi tous les genres. Mesurable.

Les cas L/R (asymétrie) nécessitent des features v2.6 (analyse L et R séparés). Reportés.

---

## 4. Structure EQ8 M/S dans le XML

Le mapping `ableton_devices_mapping.json` confirme :

```json
"Mode_global": {
    "values": {"0": "Stereo", "1": "L/R", "2": "M/S"}
},
"band_params": {
    "description": "ParameterA = L ou Mid, ParameterB = R ou Side"
}
```

En mode M/S :
- `ParameterA` (Freq/Gain/Q/IsOn) contrôle le canal **Mid**
- `ParameterB` (Freq/Gain/Q/IsOn) contrôle le canal **Side**
- Les deux jeux de paramètres ont leurs propres `AutomationTarget` Id

**Instance séparée :** pour ne pas interférer avec l'EQ8 Stereo existant, on crée une **deuxième instance** d'EQ8 sur la track, positionnée APRÈS l'EQ8 Stereo dans la chaîne.

---

## 5. Fonctions nouvelles

### `write_ms_side_cut()`

Réduit l'énergie Side dans une zone spécifique pour améliorer la compatibilité mono ou réduire le masking stéréo.

```python
def write_ms_side_cut(
    als_path: Path,
    track_id: str,
    zone: str,                        # "low", "mud", "low-mid", etc.
    zone_center_hz: float,
    side_energy: np.ndarray,          # énergie Side dans la zone × 64 buckets
    times: np.ndarray,
    reduction_db: float = -4.0,
    proportional: bool = True,
    context: CorrectionContext = None,
    band_index: int = None,
) -> AutomationReport:
    """Crée un EQ8 M/S et coupe le Side dans la zone spécifiée."""
```

**Logique :**
1. Trouver ou créer un EQ8 en mode M/S sur la track (distinct de l'EQ8 Stereo)
2. Configurer une bande sur ParameterB (Side) en mode Bell
3. Écrire les automations Freq, Gain, Q sur ParameterB
4. ParameterA (Mid) reste à Gain=0 (pas de modification du Mid)

### `write_ms_mid_cut()`

Réduit l'énergie Mid dans une zone pour réduire le masking centré tout en préservant la largeur stéréo.

```python
def write_ms_mid_cut(
    als_path: Path,
    track_id: str,
    zone: str,
    zone_center_hz: float,
    mid_energy: np.ndarray,
    masking_scores: dict,
    times: np.ndarray,
    reduction_db: float = -3.0,
    context: CorrectionContext = None,
    band_index: int = None,
) -> AutomationReport:
    """EQ8 M/S : coupe le Mid dans la zone de masking, préserve le Side."""
```

### `write_ms_side_boost()`

Boost le Side dans la présence/air pour élargir une track trop étroite.

```python
def write_ms_side_boost(
    als_path: Path,
    track_id: str,
    current_width: float,            # largeur stéréo actuelle (0-1)
    target_width: float,             # largeur souhaitée
    zone: str,                       # typiquement "presence" ou "air"
    zone_center_hz: float,
    times: np.ndarray,
    max_boost_db: float = 3.0,
    context: CorrectionContext = None,
    band_index: int = None,
) -> AutomationReport:
```

### `find_or_create_ms_eq8()`

Utilitaire dans `als_utils.py` pour créer une instance EQ8 en mode M/S distincte de l'EQ8 Stereo.

```python
def find_or_create_ms_eq8(
    tree: ET.ElementTree,
    track_element: ET.Element,
) -> ET.Element:
    """Trouve un EQ8 en mode M/S sur la track, ou en crée un.
    
    Ne touche PAS l'EQ8 Stereo existant.
    Le nouvel EQ8 est inséré APRÈS l'EQ8 Stereo dans la chaîne.
    Son Mode_global est configuré à 2 (M/S).
    Retourne l'élément EQ8 M/S.
    """
```

---

## 6. Intégration avec genre_profiles.json

Nouveaux champs par track_type :

```json
{
  "Kick": {
    "stereo_corrections": false,
    "notes": "Kick doit être mono. Pas de correction M/S."
  },
  "Lead Synth": {
    "stereo_corrections": true,
    "side_cut_threshold_phase": -0.3,
    "side_cut_zones": ["low", "mud"],
    "target_width_range": [0.2, 0.6],
    "notes": "Corriger la phase si < -0.3. Low-mid doit être centré."
  },
  "Pad/Drone": {
    "stereo_corrections": true,
    "side_cut_threshold_phase": -0.5,
    "target_width_range": [0.3, 0.8],
    "notes": "Pads naturellement wide. Corriger seulement si phase très négative."
  },
  "Sub Bass": {
    "stereo_corrections": false,
    "notes": "Sub doit être 100% mono. Si width > 0, problème en amont."
  }
}
```

---

## 7. Tests d'acceptance

### Test 1 — Création EQ8 M/S séparé
- Track avec un EQ8 Stereo existant
- Appeler `write_ms_side_cut()`
- **Attendu :** 2 EQ8 sur la track — le premier en mode Stereo (0), le second en mode M/S (2)

### Test 2 — Side cut écrit sur ParameterB
- `write_ms_side_cut()` sur une zone Mud
- **Attendu :** automation Gain sur ParameterB (Side), ParameterA (Mid) inchangé

### Test 3 — Phase négative → side cut justifié
- Track avec phase correlation -0.59 dans Low-Mid
- **Attendu :** side cut proposé avec réduction proportionnelle

### Test 4 — Phase positive → pas de side cut
- Track avec phase correlation +0.8
- **Attendu :** correction non justifiée, skip

### Test 5 — EQ8 Stereo existant non modifié
- Après ajout de l'EQ8 M/S, les bandes et automations de l'EQ8 Stereo sont identiques
- **Attendu :** zéro modification sur l'EQ8 original

### Test 6 — Track mono → skip
- Sub Bass (width = 0.001)
- `stereo_corrections: false` dans genre_profiles
- **Attendu :** skip, aucun EQ8 M/S créé

---

## 8. Données nécessaires

| Donnée | Source | Disponible ? |
|---|---|---|
| Phase correlation par bande | `_track_stereo_bands` (v2.4) | ✅ |
| Largeur stéréo par bande | `_track_stereo_bands` (v2.4) | ✅ |
| Énergie Mid vs Side séparée | Pas encore — calculable si on sépare M/S dans les features | ❌ Nouveau (v2.6) |
| Track type et profil genre | `genre_profiles.json` | ✅ |

**Pour la v3.1 :** utiliser la phase correlation et la largeur stéréo comme proxies. L'énergie Mid/Side séparée viendra en v2.6 avec les features L/R.

---

## 9. Dépendances

- **Feature 1 (correction conditionnelle)** : le `CorrectionContext` s'applique aussi aux corrections M/S. Peut être implémenté indépendamment.
- **Feature 3 (sections)** : les corrections M/S sont plus pertinentes par section (phase peut varier entre sections).
- **als_utils.py** : `find_or_create_ms_eq8()` est un nouveau utilitaire.
- **ableton_devices_mapping.json** : structure ParameterA/ParameterB déjà documentée.

---

## 10. Plan de développement

### Phase A — find_or_create_ms_eq8()
- Dans `als_utils.py`, utilitaire pour créer un EQ8 M/S complet
- Tests : création, coexistence avec EQ8 Stereo, structure ParameterB complète

### Phase B — write_ms_side_cut()
- Dans `eq8_automation.py`
- Écriture Freq/Gain/Q sur ParameterB
- Tests : automations écrites sur Side, Mid intact

### Phase C — write_ms_mid_cut() et write_ms_side_boost()
- Variations pour cut Mid et boost Side
- Tests d'acceptance

### Phase D — Détection automatique des cas stéréo
- Dans `correction_logic.py` (Feature 1) ou nouveau module
- Analyse `_track_stereo_bands` pour identifier les tracks candidates
- Intégration avec le CorrectionContext
