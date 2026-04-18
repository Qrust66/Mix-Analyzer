# Implémentation Feature 1 — Correction conditionnelle

## Lis d'abord

- `docs/prompts/feature_1_correction_conditionnelle.md` — le spec complet avec les critères, la cascade de décision, les dataclasses, et les 7 tests d'acceptance.
- `ableton_devices_mapping.json` (ou `ableton_devices_mapping_v1_7.json`) — source de vérité pour les paramètres EQ8.
- `eq8_automation.py` — les fonctions write_* existantes à modifier.
- `genre_profiles.json` — les profils par genre × track type. Certains champs nouveaux doivent être ajoutés (voir plus bas).

## Contexte

Actuellement, les fonctions write_* dans eq8_automation.py appliquent des corrections dès qu'un symptôme est détecté : peak → notch, énergie sub → HPF, etc. Aucune vérification n'est faite pour savoir si la correction est musicalement justifiée.

Résultat : des corrections inutiles ou nuisibles (couper la fondamentale d'un son acid, HPF sur une guitare qui ne masque personne, notches sur des résonances qui font partie du character du genre).

## Ce qu'il faut construire

### Étape 1 — Nouveau module : correction_logic.py

Crée `correction_logic.py` avec :

#### Dataclasses

```python
@dataclass
class CorrectionContext:
    """Contexte du mix pour décider si une correction est justifiée."""
    is_audible: np.ndarray                       # bool[n_buckets]
    zone_energy: np.ndarray                      # dB[n_buckets] pour la zone ciblée
    content_threshold_db: float                  # défaut -60.0
    other_tracks_energy: dict[str, np.ndarray]   # {track_name: dB[n_buckets]}
    masking_threshold: float                     # depuis genre_profiles
    track_mean_spectrum: np.ndarray | None       # dB[freq_bins] moyenné
    isolated_threshold_db: float                 # depuis genre_profiles
    tracks_active_count: np.ndarray | None       # int[n_buckets]
    accumulation_threshold: int                  # défaut 4
    track_priority: int                          # 1=kick/bass, 5=noise/pad
    require_justification: bool                  # True = vérifie, False = rétro-compatible

@dataclass
class JustificationResult:
    """Résultat de l'évaluation."""
    justified: bool
    flags: list[str]              # ex: ["masking_conflict:Sub Bass"]
    severity: float               # 0.0 à 1.0
    dynamic_mask: np.ndarray      # bool[n_buckets] — True = corriger ce bucket
    explanation: str              # texte lisible
```

#### Fonctions

```python
def evaluate_justification(
    track_name: str,
    track_type: str,
    correction_type: str,
    target_freq_hz: float,
    context: CorrectionContext,
    genre_profile: dict,
) -> JustificationResult:
```

Cette fonction implémente la cascade de décision décrite dans le spec :
1. Contenu inaudible (< content_threshold) → correction statique OK, flag "static_noise_removal"
2. Masking actif → correction dynamique, flag "masking_conflict:{track_name}"
3. Peak isolé extrême → correction dynamique, flag "extreme_isolated_peak"
4. Accumulation multi-track → correction sur basse priorité, flag "multi_track_accumulation"
5. Aucun critère → justified=False

Le `dynamic_mask` indique quels buckets temporels doivent être corrigés (True) et lesquels non (False). Par exemple, masking avec le Kick seulement dans le drop → dynamic_mask=True dans les buckets du drop, False dans l'intro.

La `severity` combine les scores : max(masking_score, peak_delta/isolated_threshold). Sert à scaler la réduction : reduction_effective = reduction_base × severity.

```python
def compute_masking_score(
    track_a_energy: np.ndarray,
    track_b_energy: np.ndarray,
) -> np.ndarray:
    """Score de masking frame par frame. Retourne float[n_buckets] entre 0 et 1."""
```

Masking = min(energy_a, energy_b) normalisé. Deux tracks avec forte énergie à la même fréquence au même moment = score haut.

```python
def get_track_priority(track_type: str, genre_profile: dict) -> int:
    """Retourne la priorité (1=haute, 5=basse) depuis genre_profiles."""
```

```python
def build_correction_context(
    track_name: str,
    target_zone: str,
    zone_energy: np.ndarray,
    all_tracks_zone_energy: dict[str, np.ndarray],
    is_audible: np.ndarray,
    track_mean_spectrum: np.ndarray | None,
    track_type: str,
    genre_profile: dict,
) -> CorrectionContext:
    """Construit un CorrectionContext depuis les données disponibles."""
```

### Étape 2 — Mise à jour genre_profiles.json

Ajoute les champs manquants dans chaque track_type. Les champs à ajouter sont :
- `isolated_peak_threshold_db` : dépassement minimum pour justifier un notch isolé
- `content_threshold_db` : en-dessous = bruit (utilisé pour les safety HPF/LPF)
- `priority` : priorité de la track (1=kick/bass haute, 5=noise/pad basse)

Valeurs pour Industrial (le profil le plus détaillé) :

```json
{
  "Kick": {
    "isolated_peak_threshold_db": 10,
    "content_threshold_db": -55,
    "priority": 1
  },
  "Sub Bass": {
    "isolated_peak_threshold_db": 12,
    "content_threshold_db": -50,
    "priority": 1
  },
  "Bass": {
    "isolated_peak_threshold_db": 10,
    "content_threshold_db": -50,
    "priority": 1
  },
  "Acid Bass": {
    "isolated_peak_threshold_db": 10,
    "content_threshold_db": -50,
    "priority": 1
  },
  "Lead Synth": {
    "isolated_peak_threshold_db": 8,
    "content_threshold_db": -55,
    "priority": 2
  },
  "Snare/Clap": {
    "isolated_peak_threshold_db": 8,
    "content_threshold_db": -55,
    "priority": 2
  },
  "Tom": {
    "isolated_peak_threshold_db": 7,
    "content_threshold_db": -55,
    "priority": 2
  },
  "Guitar Distorted": {
    "isolated_peak_threshold_db": 7,
    "content_threshold_db": -55,
    "priority": 2
  },
  "Lead Vocal": {
    "isolated_peak_threshold_db": 7,
    "content_threshold_db": -55,
    "priority": 2
  },
  "Arpeggio/Sequence": {
    "isolated_peak_threshold_db": 6,
    "content_threshold_db": -55,
    "priority": 3
  },
  "Pluck/Stab": {
    "isolated_peak_threshold_db": 6,
    "content_threshold_db": -55,
    "priority": 3
  },
  "Percussion": {
    "isolated_peak_threshold_db": 6,
    "content_threshold_db": -55,
    "priority": 3
  },
  "Pad/Drone": {
    "isolated_peak_threshold_db": 6,
    "content_threshold_db": -50,
    "priority": 4
  },
  "Texture/Atmosphere": {
    "isolated_peak_threshold_db": 5,
    "content_threshold_db": -50,
    "priority": 4
  },
  "Backing/Harmony Vocal": {
    "isolated_peak_threshold_db": 6,
    "content_threshold_db": -55,
    "priority": 3
  },
  "Noise/Ambience": {
    "isolated_peak_threshold_db": 5,
    "content_threshold_db": -45,
    "priority": 5
  },
  "Vocal FX/Chop": {
    "isolated_peak_threshold_db": 5,
    "content_threshold_db": -50,
    "priority": 4
  },
  "FX/Riser/Impact": {
    "isolated_peak_threshold_db": 6,
    "content_threshold_db": -50,
    "priority": 3
  },
  "Drum Loop/Bus": {
    "priority": 0,
    "skip_corrections": true
  }
}
```

Ajoute ces valeurs au profil Industrial dans genre_profiles.json (merge dans les track_profiles existants, ne pas écraser les champs déjà présents). Pour les autres genres, utilise des valeurs raisonnables ou copie les defaults de Generic.

### Étape 3 — Intégration dans eq8_automation.py

Ajoute `context: CorrectionContext = None` comme paramètre optionnel à TOUTES les fonctions write_* :

- write_adaptive_hpf
- write_adaptive_lpf
- write_safety_hpf
- write_dynamic_notch
- write_dynamic_bell_cut
- write_resonance_suppression
- write_adaptive_presence_boost
- write_adaptive_air_boost
- write_masking_reciprocal_cuts
- write_targeted_sidechain_eq
- write_transient_aware_cut
- write_section_aware_eq
- write_dynamic_deesser
- write_spectral_match

Au DÉBUT de chaque fonction, avant toute écriture :

```python
if context is not None and context.require_justification:
    result = evaluate_justification(
        track_name=track_id,
        track_type=...,          # à déduire ou passer en paramètre
        correction_type="...",   # "hpf", "notch", "bell_cut", etc.
        target_freq_hz=...,      # la fréquence ciblée
        context=context,
        genre_profile=...,       # à charger ou passer
    )
    if not result.justified:
        return AutomationReport(
            success=False,
            breakpoints_written=0,
            eq8_band_index=-1,
            warnings=[result.explanation]
        )
    # Si justifié, utiliser result.dynamic_mask pour masquer les breakpoints
    # Et result.severity pour scaler la réduction
```

Si `context is None` → comportement actuel inchangé (rétro-compatibilité).

### Étape 4 — Tests

Crée `tests/test_correction_logic.py` avec les 7 tests d'acceptance du spec :

1. Peak non-justifié → skip (Acid Bass 248 Hz, pas de masking, sous le seuil isolé)
2. Peak justifié par masking → correction dynamique (Toms Rack 248 Hz, masking avec Acid Bass)
3. HPF justifié par bruit (ARP Glitter Box, sub < -60 dB permanent)
4. HPF NON justifié (Guitar dans l'intro, sub à -35 dB, pas de masking)
5. HPF dynamique par section (Guitar dans le drop, masking avec Kick)
6. Accumulation sur basse priorité (248 Hz sur 6 tracks, correction sur les priorités 3+)
7. Rétro-compatibilité (context=None → comportement inchangé)

Pour chaque test, crée des données synthétiques (np.arrays) qui représentent le scénario. Pas besoin de fichiers audio réels.

## Contraintes

- **Rétro-compatible** : si context=None, rien ne change. Les tests existants (98) doivent toujours passer.
- **Ne pas modifier** les signatures existantes de manière breaking — context est OPTIONNEL.
- **Un module, pas dispersé** : toute la logique de décision dans correction_logic.py, pas éparpillée dans eq8_automation.py.
- **Lis genre_profiles.json** : ne hardcode pas les seuils dans le code. Charge le JSON.

## Découpage anti-timeout

- Session 1 : correction_logic.py (dataclasses + evaluate_justification + tests unitaires)
- Session 2 : Mise à jour genre_profiles.json + build_correction_context
- Session 3 : Intégration dans eq8_automation.py (ajouter context aux write_*)
- Session 4 : Tests d'intégration

Commit entre chaque session.
