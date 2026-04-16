# Prompt Claude Code — v2.5.1 : Automation Map + Résolution temporelle

## Contexte

Les automations EQ8 générées par v2.5 ignorent les automations existantes dans le .als (Utility gain, volume fader, track mute, device bypass). Résultat : les features spectrales sont calculées sur de l'audio brut sans savoir que la track est mutée ou atténuée à certains moments. Ça génère des automations EQ8 incorrectes sur les sections inaudibles.

Exemple concret : Solo Lead Synth a 915 events de mute Utility. Les Toms sont mutés ~50% du temps. L'Acid Bass a 48 events de toggle gain.

## Objectif

1. **Mapper toutes les automations gain-affecting** de chaque track du `.als` dans un sheet lisible.
2. **Calculer une courbe de gain effectif** par track (combinaison de toutes les sources).
3. **Utiliser cette courbe comme masque** dans le pipeline v2.5 : les frames où le gain effectif est sous un seuil sont ignorés (NaN) dans les features et les automations EQ8.
4. **Augmenter la résolution temporelle** des features de 32 à 64 buckets.

## Phase A — Nouveau module : `automation_map.py`

### Fonction 1 : `extract_track_automations(track_element, tempo) -> TrackAutomationMap`

Dataclass `TrackAutomationMap` :
```python
@dataclass
class AutomationCurve:
    target_id: int
    param_name: str          # ex: "Volume", "Utility.Gain", "Speaker", "Device.On"
    device_name: str         # ex: "MixerDevice", "Utility", "EQ Eight"
    times_beats: np.ndarray  # timestamps en beats
    values: np.ndarray       # valeurs brutes (linéaire pour gain, 0/1 pour on/off)
    
@dataclass
class TrackAutomationMap:
    track_name: str
    curves: list[AutomationCurve]
    effective_gain: np.ndarray    # gain combiné, résolution au beat
    effective_gain_times: np.ndarray  # axe temporel en secondes
    is_audible: np.ndarray        # bool array, True si gain > threshold
```

Pour chaque track, extraire :

a) **Volume fader** (`MixerDevice` → child `Volume` → `AutomationTarget`)
   - Valeur linéaire (0.0 = -inf dB, ~0.85 = 0 dB, 1.0 = +6 dB selon le mapping Ableton)
   - Si pas d'automation → valeur statique du `Manual`

b) **Utility gain** (device de type `StereoGain` → `Gain` parameter)
   - Peut y avoir plusieurs Utility sur une track — les multiplier
   - Si pas d'automation → valeur statique

c) **Track activator / Speaker** (`MixerDevice` → `Speaker`)
   - Valeur 0 ou 1 (mute/unmute)
   - Si pas d'automation → valeur statique

d) **Device On/Off** (pour chaque device, `On` → `Manual` ou automation)
   - Seulement pour les devices en position pre-EQ8 dans la chaîne
   - Un device bypass = signal passe through, donc pas de mute, MAIS si c'est un instrument/synth qui est off, le signal s'arrête

**Calcul du gain effectif :**
```python
effective_gain = volume_fader * utility_gain_1 * utility_gain_2 * ... * speaker_onoff
```

**Seuil d'audibilité :** `effective_gain < 0.001` (≈ -60 dB) → frame marqué non-audible.

### Fonction 2 : `extract_all_track_automations(als_path) -> dict[str, TrackAutomationMap]`

Parse le .als, extrait les automations pour toutes les tracks. Retourne un dict track_name → TrackAutomationMap.

### Fonction 3 : `resample_effective_gain(automation_map, target_times) -> np.ndarray`

Rééchantillonne la courbe de gain effectif sur l'axe temporel des features v2.5 (les 64 buckets). Retourne un array aligné.

## Phase B — Nouveau sheet : `_track_automation_map`

Structure du sheet (caché) :

| track_name | param_name | device_name | t0 | t1 | t2 | ... | t63 |
|---|---|---|---|---|---|---|---|
| Kick 1 | Volume | MixerDevice | 0.85 | 0.85 | 0.85 | ... | 0.85 |
| Kick 1 | Utility.Gain | Utility | 1.0 | 1.0 | 0.5 | ... | 1.0 |
| Kick 1 | Speaker | MixerDevice | 1 | 1 | 1 | ... | 1 |
| Kick 1 | **effective_gain** | — | 0.85 | 0.85 | 0.425 | ... | 0.85 |
| Kick 1 | **is_audible** | — | TRUE | TRUE | TRUE | ... | TRUE |
| Toms Rack | Volume | MixerDevice | 0.25 | 0.25 | 0.25 | ... | 0.25 |
| Toms Rack | Utility.Gain | Utility | 1.0 | 1.0 | 0.0003 | ... | 1.0 |
| Toms Rack | **effective_gain** | — | 0.25 | 0.25 | 0.0001 | ... | 0.25 |
| Toms Rack | **is_audible** | — | TRUE | TRUE | FALSE | ... | TRUE |

Ceci donne une vue complète et temporelle de TOUTES les automations par track, lisible dans Excel.

## Phase C — Intégration dans le pipeline v2.5

### Modification de `spectral_evolution.py`

1. `extract_all_features(mono, sr, n_buckets=64)` — changer le défaut de 32 à 64 buckets. Le paramètre existe déjà (ou l'ajouter si absent).

### Modification de `mix_analyzer.py`

1. Après l'analyse audio, charger le `.als` path et appeler `extract_all_track_automations()`.
2. Passer `n_buckets=64` à `extract_all_features()`.
3. Stocker le résultat dans `result['_automation_map']`.

### Modification de `feature_storage.py`

1. Ajouter `build_automation_map_sheet(wb, automation_maps, n_buckets=64)`.

### Modification de `eq8_automation.py`

1. Dans `_prepare_track_eq8()`, extraire le `TrackAutomationMap` pour la track.
2. Ajouter un helper `_mask_by_audibility(breakpoints, automation_map) -> breakpoints` :
   - Pour chaque breakpoint, vérifier si la track est audible à ce timestamp
   - Si non audible : supprimer le breakpoint (pas d'automation pendant les sections mutées)
   - Ça évite d'écrire des automations EQ8 qui corrigent du silence
3. Appeler `_mask_by_audibility()` dans chaque fonction `write_*` avant d'écrire les breakpoints.

## Phase D — Tests

1. **test_extract_utility_gain** : .als fixture avec Utility mute à mi-track → courbe correcte.
2. **test_extract_volume_fader** : .als fixture avec fader automation → courbe correcte.
3. **test_effective_gain_combines** : volume 0.5 × utility 0.5 = effective 0.25.
4. **test_audibility_mask** : frame avec effective_gain < 0.001 → is_audible = False.
5. **test_eq8_skips_muted_sections** : write_adaptive_hpf sur une track mutée dans la 2e moitié → pas de breakpoints après la moitié.
6. **test_automation_map_sheet** : sheet `_track_automation_map` contient les bonnes courbes.

## Contraintes

- **Résolution du sheet automation_map** : 64 buckets temporels (même axe que les features v2.5).
- **Résolution interne de effective_gain** : au beat (tempo-dépendant), rééchantillonnée ensuite sur les 64 buckets.
- **Aucune régression** : les sheets v2.4 et v2.5 existants restent identiques (sauf le nombre de buckets qui passe de 32 à 64 — vérifier que feature_storage.py gère dynamiquement).
- **Performance** : l'extraction des automations du .als est rapide (parsing XML, pas d'audio). Pas de budget temps supplémentaire significatif.
- **Anti-timeout** : découper en 2 sessions si nécessaire — Phase A+B d'abord, Phase C+D ensuite.

## Question avant de commencer

Le `.als` path est-il déjà accessible dans le pipeline de `mix_analyzer.py` au moment de l'analyse, ou faut-il l'ajouter comme paramètre ? Vérifie comment le Mix Analyzer reçoit ses inputs (dossier de WAV ? .als directement ?) et adapte l'intégration en conséquence.
