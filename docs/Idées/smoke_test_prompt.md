# Smoke Test — Premières corrections EQ8 sur Acid Drops

## Contexte

Le pipeline v2.5.1 est complet : analyse spectrale, automation_map, masquage NaN. Il est temps de tester l'écriture d'automations EQ8 dans le .als pour la première fois sur un projet réel.

**RÈGLE CRITIQUE : travailler sur une COPIE du .als, jamais l'original.**

## Setup

1. Copie le fichier .als le plus récent du projet Acid Drops (dans le dossier `ableton/`) vers un fichier de travail :
   ```
   cp ableton/Acid_drops_Code_P14.als ableton/Acid_drops_SMOKE_TEST.als
   ```
   (Adapte le nom si le fichier est différent — vérifie avec `ls ableton/*.als`)

2. Lance le Mix Analyzer sur ce .als pour générer le rapport Excel frais avec les features v2.5.

3. Charge le rapport Excel + le .als dans le script de test.

## Corrections à appliquer

### Étape 1 — Safety HPF 30 Hz (Passe 2, la plus safe)

Applique `write_safety_hpf()` sur les tracks suivantes qui n'ont PAS de contenu sub utile (énergie sub < -40 dB dans le rapport) :

Tracks cibles (à confirmer avec les données zone_energy du rapport) :
- Hi-Hat/Cymbal (China, Tambourine Hi-Hat)
- Clap
- Guitar PM A, Guitar PM B
- Xylo Percussion, Xylo Texture
- Harmony Vocal Female
- Lead Vocal Hey, Lead Vocal Shhh
- Voice FX Dark Whispers

Pour chaque track :
```python
from eq8_automation import write_safety_hpf

# Charger les features de la track depuis le rapport ou recalculer
# sub_energy = zone_energy['Sub'] pour cette track (array de 64 valeurs)
# times = centres des 64 buckets temporels en secondes

report = write_safety_hpf(
    als_path='ableton/Acid_drops_SMOKE_TEST.als',
    track_id='China',  # nom de la track dans le .als
    sub_energy=sub_energy,
    times=times,
    threshold_db=-30,
    band_index=0  # utiliser Band 0 pour les HPF
)
print(f"Track: China — {report}")
```

**Validation :** ouvre le .als dans Ableton, vérifie que chaque track a un EQ8 avec Band 0 en LowCut48 à 30 Hz avec une automation IsOn.

### Étape 2 — HPF adaptatif sur Toms Rack (Passe 2)

```python
from eq8_automation import write_adaptive_hpf
from spectral_evolution import extract_all_features
import librosa

# Charger l'audio Toms Rack
y, sr = librosa.load('chemin/vers/Acid_drops Toms Rack.wav', sr=None, mono=True)
features = extract_all_features(y, sr, n_buckets=64)

report = write_adaptive_hpf(
    als_path='ableton/Acid_drops_SMOKE_TEST.als',
    track_id='5-Toms Rack',  # nom dans le .als (vérifier)
    low_rolloff_curve=features['spectral_descriptors']['low_rolloff'],
    valley_trajectories=features.get('valley_trajectories', []),
    times=features['times'],
    safety_hz=10,
    band_index=0
)
print(f"Toms Rack HPF adaptatif — {report}")
```

**Validation :** dans Ableton, le EQ8 du Toms Rack doit avoir une automation de fréquence sur Band 0 (LowCut48) qui suit le rolloff bas de la track.

### Étape 3 — Notch dynamique 248 Hz sur Toms Rack (Passe 3)

248 Hz est la résonance la plus récurrente du projet (8+ tracks). On la traite d'abord sur Toms Rack (Drums/Tom, nettoyage agressif OK selon le profil Industrial).

```python
from eq8_automation import write_dynamic_notch

# Extraire la trajectoire du peak 248 Hz depuis peak_trajectories
# Filtrer pour le peak le plus proche de 248 Hz

report = write_dynamic_notch(
    als_path='ableton/Acid_drops_SMOKE_TEST.als',
    track_id='5-Toms Rack',
    peak_trajectory=peak_248hz,  # PeakTrajectory filtré
    times=features['times'],
    reduction_db=-3.0,
    proportional=True,
    threshold_db=-40,
    q=8.0,
    band_index=1  # Band 1 (Band 0 = HPF)
)
print(f"Toms Rack notch 248 Hz — {report}")
```

**Validation :** Band 1 du EQ8 en mode Notch, Q=8, avec automation Freq qui suit le peak et Gain proportionnel.

### Étape 4 — Notch 248 Hz sur ARP Glitter Box (Passe 3)

Même résonance, track différente (Synth/Arpeggio). Réduction plus légère car genre Industrial / track ponctuelle.

```python
report = write_dynamic_notch(
    als_path='ableton/Acid_drops_SMOKE_TEST.als',
    track_id='ARP Glitter Box',  # vérifier le nom exact dans le .als
    peak_trajectory=peak_248hz_glitter,
    times=features_glitter['times'],
    reduction_db=-2.0,
    proportional=True,
    threshold_db=-40,
    q=8.0,
    band_index=1
)
```

### Étape 5 — Masking detection Kick ↔ Sub Bass (Passe 4)

```python
from eq8_automation import detect_masking

masking = detect_masking(
    track_a_zone_energy=kick_zone_energy,
    track_b_zone_energy=subbass_zone_energy,
    times=times,
    zones=['low', 'mud']
)
print(f"Masking Kick ↔ Sub Bass: severity={masking.severity:.2f}")
print(f"Scores par zone: {masking.scores}")
```

**PAS d'écriture d'automation pour le masking** dans ce smoke test — juste la détection pour voir les scores. Si severity > 0.5, on pourra appliquer `write_masking_reciprocal_cuts()` dans un prochain run.

## Implémentation

Crée un script `smoke_test_corrections.py` qui :

1. Copie le .als vers `_SMOKE_TEST.als`
2. Charge le rapport Excel le plus récent
3. Extrait les features nécessaires (zone_energy, peak_trajectories, times) depuis le rapport
4. Exécute les étapes 1-5 dans l'ordre
5. Print un résumé de chaque correction appliquée
6. Print le nombre total de bandes EQ8 utilisées par track

**Important pour l'extraction des features depuis le rapport Excel :**
- Les zone_energy sont dans le sheet `_track_zone_energy` (64 buckets)
- Les peak_trajectories sont dans `_track_peak_trajectories`
- Les times (centres des buckets) se calculent depuis les headers de colonnes du sheet zone_energy (ex: "0.0-3.7s" → centre = 1.85s)
- L'automation_map est dans `_track_automation_map` — utilise `is_audible` pour skipper les corrections sur les sections mutées

**Important pour les noms de tracks :**
- Les noms dans le .als ont parfois un préfixe numérique ("5-Toms Rack")
- Les noms dans le rapport Excel ont un préfixe projet ("Acid_drops Toms Rack.wav")
- `find_track_by_name()` dans als_utils.py gère le matching — vérifie qu'il trouve chaque track avant d'écrire

## Validation finale

Après exécution du script :

1. Vérifie que `Acid_drops_SMOKE_TEST.als.bak` existe (backup)
2. Parse le .als modifié et confirme :
   - Nombre de tracks avec EQ8 ajouté
   - Nombre de bandes utilisées par track
   - Nombre de breakpoints écrits
3. **NE PAS ouvrir le .als dans Ableton** — c'est à Alexandre de faire cette validation

## Contraintes

- **UNE seule session** — si ça timeout, découpe en 2 : étapes 1-2 d'abord, puis 3-5
- **Commit après chaque étape réussie** — pas un gros commit à la fin
- **Print verbose** — chaque AutomationReport doit être affiché en entier
- **Si une erreur se produit** (TrackNotFoundError, EQ8SlotFullError), log l'erreur et continue avec la track suivante — ne pas arrêter le script

Commit final : "test(smoke): first real EQ8 corrections on Acid Drops"
