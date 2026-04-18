# Feature 5 — Autres devices automatisables

## Référence : Mix Analyzer v3.1 / Feature 5 de 5

---

## 1. Problème métier

Le système ne manipule que l'EQ8. Pourtant, un mix ne se corrige pas uniquement avec de l'égalisation. La dynamique (compression), l'image stéréo (Utility width), le filtrage créatif (Auto Filter), et le gating participent tous à la clarté du mix.

Le mapping JSON `ableton_devices_mapping.json` contient déjà 9 devices natifs Ableton avec leurs paramètres documentés : Eq8, StereoGain (Utility), GlueCompressor, Limiter, AutoFilter2, Saturator, Compressor2, Gate, DrumBuss.

Si l'architecture de correction conditionnelle (Feature 1) et l'écriture d'automations fonctionnent pour l'EQ8, elles peuvent s'étendre à tout device mappé.

---

## 2. Objectif

Étendre le système d'automation à 3 devices prioritaires en plus de l'EQ8, en réutilisant l'architecture existante (CorrectionContext, genre_profiles, automation_map). Chaque device résout un problème spécifique que l'EQ8 ne peut pas résoudre seul.

---

## 3. Devices prioritaires et cas d'usage

### Device 1 — Utility (StereoGain) : Width adaptatif

**Problème résolu :** une track trop wide dans les sections denses crée du masking stéréo et des problèmes de phase. La même track peut bénéficier de largeur dans les sections calmes.

**Paramètre automatisé :** `Width` (range XML : 0.0 mono → 1.0 stereo, `transform_kind: direct`)

**Logique contextuelle :**
- Section dense (DROP, 20+ tracks) → Width réduit (ex: 0.6) pour serrer le centre
- Section calme (BREAK, <10 tracks) → Width augmenté (ex: 1.0) pour l'espace
- Track avec phase < 0 → Width réduit proportionnellement à la sévérité de la phase
- Track type "Sub Bass" ou "Kick" → Width toujours 0.0 (mono)

**Justification (Feature 1) :**
- Width réduit seulement si la largeur actuelle cause du masking stéréo ou de la phase négative
- Width augmenté seulement si le full mix manque de largeur dans la section

**Données nécessaires :**
- `_track_stereo_bands` : largeur et phase actuelles ✅
- Section info (Feature 3) : densité par section
- `genre_profiles.json` : target_width_range par track_type ✅

**Fonction :**
```python
def write_adaptive_width(
    als_path: Path,
    track_id: str,
    current_width_curve: np.ndarray,    # largeur stéréo par bucket
    phase_correlation_curve: np.ndarray, # phase par bucket
    section_density: np.ndarray,         # nombre de tracks actives par bucket
    times: np.ndarray,
    target_width_range: tuple[float, float] = (0.3, 1.0),
    context: CorrectionContext = None,
) -> AutomationReport:
```

### Device 2 — Compressor : Compression section-aware

**Problème résolu :** une track qui sonne bien dans le drop (dense, compressé) peut sonner écrasée dans le break (calme, aéré). La compression devrait s'adapter à la section.

**Paramètres automatisés :**
- `Threshold` (range : -40 à 0 dB, `transform_kind: direct`)
- `Ratio` — potentiellement, mais risqué en automation

**Logique contextuelle :**
- Section dense → threshold plus bas (compression active)
- Section calme → threshold plus haut (compression relâchée)
- Track percussive (Kick, Snare) → compression constante (transients doivent être prévisibles)
- Track sustain (Pad, Vocal) → compression adaptative par section

**Justification :**
- Compression ajustée seulement si le crest factor de la track varie significativement entre sections (données `_track_crest_by_zone`)
- Si le crest est constant → la compression actuelle (manuelle) est probablement correcte

**Limitation importante :** le Compressor2 dans le mapping a `0 params` — ses paramètres individuels ne sont pas encore mappés en détail. Il faut d'abord les mapper avec la méthode de calibration (comme pour l'EQ8).

**Données nécessaires :**
- `_track_crest_by_zone` : crest factor par zone × temps ✅
- `_track_dynamics_time` : peak/RMS par temps ✅
- Sections (Feature 3)
- **Mapping Compressor2 à compléter** ❌

**Fonction :**
```python
def write_section_compression(
    als_path: Path,
    track_id: str,
    crest_by_section: dict[str, float],  # crest factor par section
    times: np.ndarray,
    threshold_range_db: tuple[float, float] = (-30, -10),
    context: CorrectionContext = None,
) -> AutomationReport:
```

### Device 3 — Gate : Nettoyage dynamique des tracks avec bleed

**Problème résolu :** certaines tracks (toms, overheads) ont du bleed — du signal indésirable entre les coups. Un gate qui s'ouvre sur le signal voulu et se ferme sur le bleed. Actuellement fait manuellement ou pas du tout.

**Paramètres automatisés :**
- `Threshold` : seuil d'ouverture du gate
- `Return` (hysteresis) : seuil de fermeture
- Potentiellement automatisé par section si le bleed varie

**Logique contextuelle :**
- Track avec transients détectés (`_track_transients`) + énergie inter-transient haute → candidat pour gate
- Le threshold est calibré pour que les transients passent et le bleed non
- Section-aware : dans un break calme, le gate peut être relâché (threshold bas) pour laisser passer le sustain naturel

**Limitation :** même que Compressor — mapping Gate à compléter.

**Données nécessaires :**
- `_track_transients` : timestamps et magnitudes ✅
- `_track_dynamics_time` : pour calculer le ratio signal/bleed ✅
- **Mapping Gate à compléter** ❌

**Fonction :**
```python
def write_adaptive_gate(
    als_path: Path,
    track_id: str,
    transient_events: list,
    inter_transient_energy: np.ndarray,
    times: np.ndarray,
    context: CorrectionContext = None,
) -> AutomationReport:
```

---

## 4. Architecture commune

### Pattern réutilisable pour tout device

Chaque device suit le même pattern que l'EQ8 :

```
1. find_or_create_<device>(tree, track)     → trouve ou crée le device
2. get_<device>_param(device, param_name)   → récupère le paramètre
3. get_automation_target_id(param)           → récupère le target ID
4. evaluate_justification(context)            → vérifie si c'est nécessaire
5. compute_automation_values(features, ...)   → calcule les breakpoints
6. write_automation_envelope(tree, track, target_id, breakpoints)  → écrit
```

Les étapes 3, 4, 5, 6 sont **identiques** à l'EQ8. Seules les étapes 1 et 2 changent par device.

### Abstraction proposée

```python
class DeviceAutomator:
    """Classe de base pour automatiser n'importe quel device Ableton."""
    
    def __init__(self, device_name: str, mapping_json: dict):
        self.device_name = device_name
        self.mapping = mapping_json['devices'][device_name]
    
    def find_or_create(self, tree, track) -> ET.Element:
        """Trouve ou crée le device sur la track."""
        raise NotImplementedError
    
    def get_param(self, device, param_name) -> ET.Element:
        """Récupère un paramètre du device."""
        # Logique commune basée sur le mapping
    
    def validate_value(self, param_name, value) -> bool:
        """Vérifie que la valeur est dans le range du mapping."""
        param_info = self.mapping['params'].get(param_name) or self.mapping.get('band_params', {}).get(param_name)
        # Vérifier range, transform_kind, disabled_when, etc.
    
    def write(self, als_path, track_id, param_name, values, times, context=None):
        """Écrit une automation pour un paramètre du device."""
        # Pattern commun : backup, parse, find track, find device, validate, write, save
```

Les fonctions spécifiques (`write_adaptive_width`, `write_section_compression`, etc.) utilisent `DeviceAutomator` en interne au lieu de dupliquer la logique XML.

---

## 5. Prérequis : compléter le mapping

### Devices déjà complets dans le mapping

| Device | Params mappés | Status |
|---|---|---|
| Eq8 | global + 8 bandes | ✅ Complet |
| StereoGain (Utility) | 15 params | ✅ Complet |
| GlueCompressor | 9 params | ✅ Complet |
| Limiter | 13 params | ✅ Complet |

### Devices à compléter (même méthode de calibration)

| Device | Params mappés | Status | Action |
|---|---|---|---|
| Compressor2 | 0 | ❌ Structure observée | Calibration nécessaire |
| Gate | 0 | ❌ Structure observée | Calibration nécessaire |
| AutoFilter2 | 0 | ❌ Structure observée | Calibration si nécessaire |
| Saturator | 0 | ❌ Structure observée | Basse priorité |
| DrumBuss | 0 | ❌ Structure observée | Basse priorité |

**Méthode de calibration :** identique à ce qui a été fait pour l'EQ8. Créer un set Ableton avec le device, des valeurs connues sur chaque paramètre, des automations dessinées, sauvegarder le `.als`, parser le XML, comparer les valeurs XML aux valeurs affichées dans Ableton.

---

## 6. Intégration avec genre_profiles.json

Nouveaux champs par track_type :

```json
{
  "Kick": {
    "utility_width": {
      "target": 0.0,
      "adaptive": false,
      "notes": "Toujours mono"
    },
    "compression": {
      "section_adaptive": false,
      "notes": "Compression constante sur le kick"
    },
    "gate": {
      "applicable": false,
      "notes": "Pas de gate sur le kick"
    }
  },
  "Pad/Drone": {
    "utility_width": {
      "target_range": [0.4, 0.9],
      "adaptive": true,
      "narrow_in_dense_sections": true,
      "notes": "Largeur adaptative selon la densité"
    },
    "compression": {
      "section_adaptive": true,
      "threshold_range_db": [-25, -10],
      "notes": "Plus compressé dans les sections denses"
    },
    "gate": {
      "applicable": false
    }
  },
  "Tom": {
    "utility_width": {
      "target_range": [0.1, 0.5],
      "adaptive": true
    },
    "compression": {
      "section_adaptive": false,
      "notes": "Transients doivent être prévisibles"
    },
    "gate": {
      "applicable": true,
      "threshold_auto": true,
      "notes": "Gate pour nettoyer le bleed entre les coups"
    }
  }
}
```

---

## 7. Tests d'acceptance

### Utility Width

**Test 1 :** Track Pad dans une section DROP (20 tracks actives) → width réduit à 0.6
**Test 2 :** Même track dans BREAK (5 tracks) → width à 0.9
**Test 3 :** Sub Bass → width toujours 0.0, pas d'automation
**Test 4 :** Track avec phase > 0.5 → width non modifié (pas de problème)

### Compressor (après mapping)

**Test 5 :** Track Vocal avec crest factor qui varie de 6 dB (intro) à 12 dB (drop) → threshold adaptatif
**Test 6 :** Track Kick avec crest constant → pas de modification

### Gate (après mapping)

**Test 7 :** Toms Rack avec 20 transients détectés, énergie inter-transient -45 dB → gate threshold entre -45 et -25 dB
**Test 8 :** Track sans transients → pas de gate

---

## 8. Dépendances

- **Feature 1 (correction conditionnelle)** : CorrectionContext s'applique à tous les devices
- **Feature 3 (sections)** : section_density nécessaire pour width adaptatif et compression section-aware
- **ableton_devices_mapping.json** : source de vérité pour tous les paramètres
- **Calibration Compressor2 et Gate** : nécessaire avant implémentation des fonctions correspondantes

---

## 9. Plan de développement

### Phase A — DeviceAutomator (abstraction commune)
- Classe de base dans un nouveau `device_automator.py`
- Lecture du mapping JSON, validation des valeurs
- `find_or_create_device()` générique
- Tests : création device, validation range

### Phase B — Utility Width adaptatif
- `write_adaptive_width()` dans `utility_automation.py`
- Utilise les données stéréo existantes + sections
- Tests d'acceptance 1-4
- **Peut être livré immédiatement** — mapping StereoGain déjà complet

### Phase C — Calibration Compressor2 et Gate
- Créer des `.als` de calibration pour chaque device
- Compléter le mapping JSON
- Validation des transforms

### Phase D — Compressor section-aware
- `write_section_compression()` dans `compressor_automation.py`
- Tests d'acceptance 5-6
- **Dépend de Phase C**

### Phase E — Gate adaptatif
- `write_adaptive_gate()` dans `gate_automation.py`
- Tests d'acceptance 7-8
- **Dépend de Phase C**

---

## 10. Hors scope v3.1

- Saturator automation (créatif, pas correctif — pertinent pour v4.0)
- DrumBuss automation (niche, pertinent si beaucoup de drums)
- AutoFilter automation (créatif, overlap avec EQ8 pour les corrections)
- Chaînes d'effets automatisées (ex: EQ → Comp → Gate en séquence coordonnée)
- Sidechain externe via Compressor (nécessite routing, pas juste automation)
