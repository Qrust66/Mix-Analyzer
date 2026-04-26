# Mix Analyzer → ALS Correction API Spec

**Version**: 1.0 (basé sur rapport v2.7.0 — Acid Drops 2026-04-22)
**Principe**: 1 correction = 1 appel API. Fonctions atomiques, autonomes, idempotentes.
**Stratégie devices**: stock-only (XML lisible/scriptable).

---

## Architecture commune

### Signature standard

Toutes les fonctions write_* respectent ce contrat:

```python
def write_<correction>(
    als_path: str,
    track_name: str,
    *params,
    # Common kwargs
    backup: bool = True,           # backup_als() avant write
    dry_run: bool = False,          # retourne diff XML sans écrire
    overwrite: bool = False,        # écrase device existant si True
    device_position: str = "end",   # 'start', 'end', or index int
    return_report: bool = True      # dict avec changements
) -> dict:
    """
    Returns:
        {
            "status": "ok" | "skipped" | "error",
            "track": str,
            "device_added": str,           # nom du device stock
            "device_id": int,              # ID Ableton dans XML
            "params_set": dict,            # params réellement écrits
            "automation_targets": list,    # PointeeIds créés
            "xml_diff": str (if dry_run),
            "warnings": list[str],
            "backup_path": str
        }
    """
```

### Track resolver

Tous les `track_name` doivent supporter:
- Match exact sur `EffectiveName`
- Match partiel via fuzzy (ex: `"Acid Bass"` matche `"[H_M] Acid Bass.wav"`)
- Match par track ID Ableton si int
- Resolver doit retourner liste si ambigu, raise si aucun match

### Validation pré-écriture

Chaque fonction valide:
- Track existe
- Device cible n'existe pas déjà (sauf overwrite=True)
- Params dans ranges valides selon `ableton_devices_mapping.json`
- XML structure valide après transformation (parse + reserialize sans erreur)

---

## Famille 1 — Résonances (`RES:` codes)

**Trigger rapport**: colonnes `peak1_hz` à `peak6_hz` + `peak1_db` à `peak6_db` dans AI Context.
**Ex Acid Drops**: Glider Lead `RES:781,248,490`, peak1=780.6 Hz (0 dB ref), peak2=247.6 (-1.7), peak3=489.9 (-1.7).

### `write_resonance_notch()`
**Cas**: pic résonant chirurgical sur 1 fréquence.

```python
write_resonance_notch(
    als_path,
    track_name,
    freq_hz: float,                 # ex: 780.6
    depth_db: float = -4.0,         # cut depth, calculé selon peakX_db
    q: float = 6.0,                 # tight notch
    band_index: int = None,         # 1-8, auto si None
    eq8_position: str = "end",
    label: str = None               # nom auto si None: "RES_780Hz"
) -> dict
```

**Params XML EQ Eight**:
- `<Bands.X.Mode>` = `1` (Bell)
- `<Bands.X.Frequency>` = freq_hz (log scale, voir mapping)
- `<Bands.X.Gain>` = depth_db
- `<Bands.X.Q>` = q
- `<Bands.X.IsOn>` = `true`

### `write_resonance_batch()`
**Cas**: appliquer notches multiples d'un coup pour un track avec `peak1-6`.

```python
write_resonance_batch(
    als_path,
    track_name,
    peaks: list[tuple[float, float]],   # [(freq_hz, depth_db), ...]
    threshold_db: float = -3.0,         # ignore peaks above this (already minor)
    max_notches: int = 4,               # don't fill all 8 bands
    auto_q_from_db: bool = True         # Q calculated from depth severity
) -> dict
```

### `write_dynamic_resonance_tame()`
**Cas**: pic intermittent (apparaît à certains moments seulement).

```python
write_dynamic_resonance_tame(
    als_path,
    track_name,
    freq_hz: float,
    depth_db: float = -6.0,
    q: float = 4.0,
    threshold_db: float = -12.0,        # EnvelopeFollower threshold
    rise_ms: float = 5.0,
    fall_ms: float = 80.0,
    detection_band: tuple = None        # (low_hz, high_hz) si side-chain bandé
) -> dict
```

**Devices**: EQ Eight + Envelope Follower (M4L) → map sur Gain de la bande.

---

## Famille 2 — Phase / Mono compat (`PHASE:` codes)

**Trigger rapport**: `phase_corr` < 0.3 ou `WIDTH_HIGH:`.
**Ex Acid Drops**: Toms Overhead phase_corr -0.00, Arp Roaming -0.11.

### `write_mono_below()`
**Cas**: stéréo en sub-bass cause cancellations en mono.

```python
write_mono_below(
    als_path,
    track_name,
    crossover_hz: float = 120.0,
    method: str = "utility",            # "utility" or "eq8_ms"
    fade_octave: float = 0.5            # transition smoothness
) -> dict
```

**Devices**:
- `method="utility"`: Utility avec `<BassMono>` = true, `<BassMonoFreq>` = crossover_hz
- `method="eq8_ms"`: EQ Eight Mode_global=2 (M/S), bande Low Shelf sur Side, gain -inf

### `write_phase_invert()`
**Cas**: track suspectée invertie (rare mais arrive).

```python
write_phase_invert(
    als_path,
    track_name,
    channels: str = "both"              # "L", "R", or "both"
) -> dict
```

**Device**: Utility avec `<PhaseL>` et/ou `<PhaseR>` = -1.

### `write_haas_correction()`
**Cas**: phase corr basse + width perçue OK → probablement Haas mal calibré.

```python
write_haas_correction(
    als_path,
    track_name,
    target_phase_corr: float = 0.5,
    method: str = "delay_compensation"  # "delay_compensation" or "narrow"
) -> dict
```

---

## Famille 3 — Niveaux / Loudness (`PEAK_HOT`, `PEAK_CLIP`, `TP_OVER`, `RMS_LOW`)

**Trigger rapport**: colonnes `peak_db`, `true_peak_db`, `rms_db`, `lufs_int`.
**Ex Acid Drops**: tracks avec peak proche de 0, ou Toms Overhead RMS -120 dBFS (probablement vide).

### `write_track_gain()`
**Cas**: gain staging — aligner vers cible LUFS ou peak.

```python
write_track_gain(
    als_path,
    track_name,
    target: float,                       # dB or LUFS
    target_type: str = "lufs",           # "lufs", "peak_db", "rms_db", "delta_db"
    method: str = "mixer"                # "mixer", "utility_pre", "utility_post"
) -> dict
```

**Note**: `mixer` modifie `<Volume>` du Mixer track (le fader). `utility_*` ajoute Utility avec Gain pour préserver le fader visible.

### `write_track_disable()`
**Cas**: track quasi-silencieuse identifiée comme erreur (RMS_LOW extrême).

```python
write_track_disable(
    als_path,
    track_name,
    reason: str,                         # logged in track comment
    method: str = "mute"                 # "mute" or "freeze_and_remove"
) -> dict
```

### `write_truepeak_limiter()`
**Cas**: TP_OVER détecté.

```python
write_truepeak_limiter(
    als_path,
    track_name,
    ceiling_db: float = -1.0,
    lookahead_ms: float = 3.0,
    release_ms: float = 50.0
) -> dict
```

**Device**: Limiter stock avec lookahead activé.

---

## Famille 4 — Dynamique (`CREST_LOW`)

**Trigger rapport**: `crest_db` hors range (idéal 8-14 dB), `plr_db`, `psr_db`.

### `write_glue_compressor()`
**Cas**: bus avec crest élevé, besoin de cohésion.

```python
write_glue_compressor(
    als_path,
    track_name,
    threshold_db: float = -12.0,
    ratio: float = 2.0,                  # 2:1
    attack_ms: float = 30.0,
    release_ms: float = 100.0,
    release_auto: bool = True,
    makeup_db: float = 0.0,
    sidechain_filter: dict = None        # {"enabled": True, "freq_hz": 100, "type": "highpass"}
) -> dict
```

### `write_compressor()`
**Cas**: compression individuelle (drum, vocal, bass).

```python
write_compressor(
    als_path,
    track_name,
    threshold_db: float,
    ratio: float = 4.0,
    attack_ms: float = 10.0,
    release_ms: float = 100.0,
    knee_db: float = 6.0,
    model: str = "Peak",                 # "Peak", "RMS", "Opto", "Glue"
    sidechain_track: str = None,         # for ducking
    sidechain_eq: dict = None
) -> dict
```

### `write_multiband_tame()`
**Cas**: bande spécifique trop dynamique (ex: pic mid 2-4kHz d'une voix).

```python
write_multiband_tame(
    als_path,
    track_name,
    band: int,                           # 1=low, 2=mid, 3=high
    crossovers_hz: tuple = (250, 2500),
    threshold_db: float = -18.0,
    ratio: float = 3.0,
    attack_ms: float = 5.0,
    release_ms: float = 80.0,
    above_below: str = "above"           # "above" (compress) or "below" (expand)
) -> dict
```

**Device**: Multiband Dynamics — 100% mappable XML.

### `write_parallel_compression()`
**Cas**: track manque punch sans vouloir tuer dynamique.

```python
write_parallel_compression(
    als_path,
    track_name,
    send_db: float = -6.0,               # niveau du send
    return_track_name: str = "Parallel Comp",  # créé si absent
    threshold_db: float = -28.0,
    ratio: float = 8.0,
    attack_ms: float = 1.0,
    release_ms: float = 50.0
) -> dict
```

---

## Famille 5 — Conflits fréquentiels (Freq Conflicts sheet)

**Trigger rapport**: matrice band×track, énergies %max sur même bande.
**Ex Acid Drops**:
- Bass 50-80 Hz: Sub Bass=100%, Kick 1=57.1%, Kick 2=69%, Floor Toms=85.2%
- Mid 800-1k Hz: Clap=100%, Glider Lead=44%, NINja Lead=15.8%
- Acid Bass dom: peak2 220.7 Hz (-3.6 dB) clash avec Bass Rythm peak2 366 Hz et Sub Bass 50-80

### `write_complementary_carve()`
**Cas**: deux tracks rivalisent sur même bande → cut sur secondaire, boost léger sur primaire.

```python
write_complementary_carve(
    als_path,
    primary_track: str,                  # gagne la bande
    secondary_track: str,                # perd la bande
    band_hz: tuple,                      # (low, high) ex: (200, 250)
    primary_boost_db: float = 1.0,
    secondary_cut_db: float = -3.0,
    q: float = 1.5,
    apply_to: str = "both"               # "primary", "secondary", "both"
) -> dict
```

### `write_freq_duck()`
**Cas**: ducking fréquentiel dynamique (kick → cut basse à 60 Hz quand kick frappe).

```python
write_freq_duck(
    als_path,
    source_track: str,                   # ex: "Kick 1"
    target_track: str,                   # ex: "Acid Bass"
    band_hz: float = 60.0,
    band_q: float = 2.0,
    duck_amount_db: float = -8.0,
    rise_ms: float = 2.0,
    fall_ms: float = 80.0,
    sidechain_filter_hz: tuple = None    # bandpass on EF input
) -> dict
```

**Devices**: EQ Eight (target) + Envelope Follower M4L (target, audio source = source).

### `write_volume_sidechain()`
**Cas**: ducking volume classique (kick vs basse globale).

```python
write_volume_sidechain(
    als_path,
    source_track: str,
    target_track: str,
    threshold_db: float = -20.0,
    ratio: float = 4.0,
    attack_ms: float = 0.0,
    release_ms: float = 100.0,
    release_synced: str = None           # "1/16", "1/8", etc.
) -> dict
```

### `write_frequency_split_carve()`
**Cas**: 2 tracks doivent occuper bandes complémentaires (ex: 2 leads).

```python
write_frequency_split_carve(
    als_path,
    track_a: str,
    track_b: str,
    crossover_hz: float = 1000.0,
    slope_db_oct: float = 24.0,
    method: str = "lpf_hpf"              # "lpf_hpf" or "shelf"
) -> dict
```

---

## Famille 6 — Spectral balance (Mix Health sheet)

**Trigger rapport**: `Spectral Balance score`, `pct_sub`/`pct_air`, `dom_band` overweight.
**Ex Acid Drops**: Air Energy 0.2% (cible >0.5%), Bass band dominant 58.5% (cible <35%).

### `write_master_air_boost()`
**Cas**: Air Energy bas globalement.

```python
write_master_air_boost(
    als_path,
    boost_db: float = 2.0,
    freq_hz: float = 12000.0,
    q: float = 0.7,
    target: str = "master"               # "master" or specific bus
) -> dict
```

### `write_master_tilt()`
**Cas**: déséquilibre tilt (trop de bas vs haut ou inverse).

```python
write_master_tilt(
    als_path,
    low_shelf_db: float = -1.5,          # ex pour Acid Drops: réduire bass dominance
    low_freq_hz: float = 200.0,
    high_shelf_db: float = 1.5,
    high_freq_hz: float = 6000.0,
    target: str = "master"
) -> dict
```

### `write_low_mid_cleanup()`
**Cas**: track qui contribue trop au mud band (200-500 Hz).

```python
write_low_mid_cleanup(
    als_path,
    track_name: str,
    cut_db: float = -2.5,
    freq_hz: float = 350.0,
    q: float = 1.0
) -> dict
```

### `write_high_pass_filter()`
**Cas**: tracks non-bass avec pct_sub > 5% inutilement.

```python
write_high_pass_filter(
    als_path,
    track_name: str,
    cutoff_hz: float = 80.0,
    slope_db_oct: float = 12.0,
    band_index: int = 1
) -> dict
```

**(déjà existant: `write_highpass_filter` dans `eq8_automation.py`)**

---

## Famille 7 — Stéréo / Image (Stereo Image score)

**Trigger rapport**: `stereo_width`, `phase_corr`, Stereo Image score.
**Ex Acid Drops**: Full Mix Width 0.145 (cible 0.40-0.70 — TOO NARROW).

### `write_track_width()`
**Cas**: élargir/rétrécir une track stéréo.

```python
write_track_width(
    als_path,
    track_name: str,
    width_pct: float,                    # 0.0=mono, 1.0=natural, 2.0=200%
    bass_mono: bool = False,
    bass_mono_freq_hz: float = 120.0
) -> dict
```

**Device**: Utility — `<Width>` param direct.

### `write_haas_widening()`
**Cas**: track mono qu'on veut élargir sans midside.

```python
write_haas_widening(
    als_path,
    track_name: str,
    delay_ms: float = 12.0,              # 5-30 ms typical
    side_channel: str = "R",             # which side gets delayed
    output_width_pct: float = 1.5
) -> dict
```

**Devices**: Simple Delay (channel offset) + Utility.

### `write_midside_balance()`
**Cas**: contrôle fin Mid vs Side.

```python
write_midside_balance(
    als_path,
    track_name: str,
    mid_db: float = 0.0,
    side_db: float = 2.0,
    side_low_cut_hz: float = 200.0       # mono below this on side
) -> dict
```

**Device**: EQ Eight Mode_global=2 ou Utility + EQ Eight chain.

---

## Famille 8 — Saturation / Caractère

**Trigger rapport**: subjectif — manque de caractère sur bus, ou demande explicite.
**Live 12**: Roar disponible (multiband saturator stock).

### `write_saturator()`
**Cas**: saturation simple (drive bass, glue bus).

```python
write_saturator(
    als_path,
    track_name: str,
    drive_db: float = 6.0,
    color: float = 0.0,                  # -1.0 to 1.0
    mode: str = "soft_sine",             # "analog_clip", "soft_sine", "hard_curve", "medium_curve"
    output_db: float = 0.0,
    dry_wet: float = 1.0
) -> dict
```

### `write_roar_multiband()`
**Cas**: caractère par bande (ex: drive bass low, clean mid, fizz high).

```python
write_roar_multiband(
    als_path,
    track_name: str,
    bands: list[dict]                    # [{"freq_low":20, "freq_high":250, "drive":6, "shape":"warm"}, ...]
) -> dict
```

**Device**: Roar (Live 12 stock) — params multiband en XML.

---

## Famille 9 — Reverb / Espace

**Trigger rapport**: subjectif post-correction, ou tracks sèches identifiées par cohérence section.

### `write_reverb_send()`
**Cas**: créer/configurer return reverb partagé.

```python
write_reverb_send(
    als_path,
    track_name: str,                     # source
    send_db: float = -12.0,
    return_track_name: str = "Reverb Hall",   # créé si absent
    reverb_type: str = "hybrid",         # "reverb" or "hybrid"
    decay_ms: float = 1800.0,
    predelay_ms: float = 20.0,
    high_cut_hz: float = 8000.0,
    low_cut_hz: float = 250.0
) -> dict
```

### `write_spectral_resonator_send()`
**Cas**: texture industrielle Qrust — résonance accordée.

```python
write_spectral_resonator_send(
    als_path,
    track_name: str,
    send_db: float = -18.0,
    return_track_name: str = "Spectral Res",
    note: str = "G#1",                   # alignée tonalité projet
    decay: float = 0.7,
    mode: str = "midi"                   # "midi" or "audio"
) -> dict
```

---

## Famille 10 — Section-aware automation

**Trigger rapport**: `Sections Timeline` sheet + `_track_automation_map`.
**Ex Acid Drops**: 20 sections détectées (Intro, Build 1, Acid 1, Drop 1...).

### `write_section_volume_automation()`
**Cas**: ducker une track durant une section précise.

```python
write_section_volume_automation(
    als_path,
    track_name: str,
    section_name: str,                   # "Drop 1", "Breakdown 1"
    delta_db: float,                     # +/- relative to current
    fade_in_ms: float = 200.0,
    fade_out_ms: float = 200.0,
    curve_type: str = "linear"           # "linear", "exponential", "log"
) -> dict
```

### `write_section_eq_automation()`
**Cas**: ouvrir/fermer EQ band à une section.

```python
write_section_eq_automation(
    als_path,
    track_name: str,
    section_name: str,
    band_index: int,
    target_state: dict,                  # {"gain": -12, "freq": 800, "q": 4}
    fade_ms: float = 100.0
) -> dict
```

### `write_section_send_automation()`
**Cas**: augmenter reverb send pendant breakdown.

```python
write_section_send_automation(
    als_path,
    track_name: str,
    return_track: str,
    section_name: str,
    delta_db: float,
    fade_ms: float = 500.0
) -> dict
```

---

## Famille 11 — Master bus (Mix Health Loudness)

**Trigger rapport**: Master Plugins None + LUFS hors cible.
**Ex Acid Drops**: Full Mix LUFS -19.22 (cible -9.9 YouTube ou -14 streaming).

### `write_master_chain()`
**Cas**: build master complet d'un coup.

```python
write_master_chain(
    als_path,
    target_lufs: float = -9.9,
    target_true_peak_db: float = -1.0,
    chain: list[str] = ["eq8", "glue", "limiter"],
    eq8_params: dict = None,
    glue_params: dict = None,
    limiter_params: dict = None
) -> dict
```

### `write_master_lufs_target()`
**Cas**: ajuster gain du limiter master pour atteindre LUFS cible (itératif).

```python
write_master_lufs_target(
    als_path,
    target_lufs: float = -9.9,
    measurement_section: str = "Drop 1",   # section utilisée pour mesure
    max_iterations: int = 5,
    tolerance_lu: float = 0.5
) -> dict
```

**Note**: nécessite intégration avec moteur de mesure (peut être dry_run avec estimation).

---

## Famille 12 — Diagnostic / Inspection (read-only)

Helpers qui lisent l'ALS sans écrire — utiles pour l'API Feature 1 conversationnelle.

### `inspect_track()`
```python
inspect_track(
    als_path,
    track_name: str,
    include_devices: bool = True,
    include_automation: bool = True,
    include_routing: bool = True
) -> dict
```

### `inspect_master_chain()`
```python
inspect_master_chain(als_path) -> dict
```

### `list_tracks_by_anomaly()`
```python
list_tracks_by_anomaly(
    report_path: str,                    # xlsx Mix Analyzer
    anomaly_type: str                    # "RES", "PHASE", "RMS_LOW", etc.
) -> list[dict]
```

### `simulate_correction()`
```python
simulate_correction(
    als_path,
    correction_function: callable,
    *args,
    **kwargs
) -> dict
```
Wraps any write_* with `dry_run=True` and returns expected XML diff.

---

## Mapping rapport → fonction (cheat sheet)

| Donnée rapport | Fonction API |
|---|---|
| `anomaly_codes: RES:f1,f2,f3` | `write_resonance_batch` |
| `peak1_hz` à `peak6_hz` | `write_resonance_notch` (chacun) |
| `anomaly_codes: PHASE:val` | `write_mono_below` ou `write_phase_invert` |
| `anomaly_codes: PHASE_CRIT:val` | `write_mono_below` + `write_track_width(0.5)` |
| `anomaly_codes: RMS_LOW:val` | Diag → `write_track_disable` ou `write_track_gain` |
| `anomaly_codes: PEAK_HOT:val` | `write_track_gain` (réduire) |
| `anomaly_codes: PEAK_CLIP:val` | `write_track_gain` + `write_truepeak_limiter` |
| `anomaly_codes: TP_OVER:val` | `write_truepeak_limiter` |
| `anomaly_codes: CREST_LOW:val` | Diag (pas de fix auto, signaler over-comp) |
| `anomaly_codes: WIDTH_HIGH:val` | `write_track_width` (réduire) |
| Freq Conflicts matrix | `write_complementary_carve` (batch) |
| Mix Health: Spectral Balance < 50 | `write_master_tilt` + `write_master_air_boost` |
| Mix Health: Stereo Image "Too narrow" | `write_track_width` (selectif) ou `write_midside_balance` |
| Mix Health: LUFS off | `write_master_lufs_target` |
| Section trop dense (TFP) | `write_section_volume_automation` |

---

## Priorisation développement (Acid Drops driven)

### Phase 1 — quick wins (extension `eq8_automation.py`)
1. `write_resonance_batch` (déjà 90% du code via `write_notch`)
2. `write_complementary_carve` (combine `write_cut_band` + `write_boost`)
3. `write_track_gain` (Mixer Volume direct)
4. `write_mono_below` (Utility BassMono)

### Phase 2 — dynamique
5. `write_glue_compressor`
6. `write_compressor` (avec sidechain)
7. `write_truepeak_limiter`
8. `write_multiband_tame`

### Phase 3 — sidechain dynamique
9. `write_freq_duck` (EQ8 + EnvelopeFollower) — KEY pour Qrust
10. `write_volume_sidechain` (Compressor sidechain)

### Phase 4 — master
11. `write_master_chain`
12. `write_master_air_boost`, `write_master_tilt`
13. `write_master_lufs_target`

### Phase 5 — créatif Qrust
14. `write_saturator`, `write_roar_multiband`
15. `write_spectral_resonator_send`
16. `write_section_*_automation` (toutes les variantes)
17. `write_haas_widening`

---

## Cas d'usage concrets — Acid Drops

Avec le rapport actuel, voici les premiers appels exécutables:

```python
# 1. Tame résonance dominante Glider Lead
write_resonance_notch("acid_drops.als", "Glider Lead", freq_hz=780.6, depth_db=-3.5, q=6.0)

# 2. Tame résonance Lead Vocal Shhh
write_resonance_batch("acid_drops.als", "Lead Vocal Shhh",
    peaks=[(818.3, -3), (1254.3, -2.5), (710.6, -2.5)])

# 3. Conflit Snare Riser vs ARP Glitter Box sur 200-250 Hz
write_complementary_carve("acid_drops.als",
    primary_track="Snare Riser", secondary_track="ARP Glitter Box",
    band_hz=(200, 250), primary_boost_db=0, secondary_cut_db=-3, q=1.2)

# 4. Mono compat Toms Overhead
write_mono_below("acid_drops.als", "Toms Overhead", crossover_hz=150)

# 5. Sidechain Kick → Acid Bass (60 Hz duck)
write_freq_duck("acid_drops.als",
    source_track="Kick 1", target_track="Acid Bass",
    band_hz=60.0, duck_amount_db=-8, rise_ms=2, fall_ms=80)

# 6. Largir image stéréo (full mix trop narrow 0.145)
write_master_chain("acid_drops.als", target_lufs=-9.9,
    eq8_params={"high_shelf_db": 2, "high_shelf_freq": 10000})
```

---

## Gotchas / risques connus

1. **Fader vs Utility gain**: modifier `<Volume>` du Mixer change le fader visible. Préférer Utility pre-chain pour gain staging programmatique sans toucher l'interaction utilisateur.

2. **Bands EQ Eight Mode L/R/M/S**: en mode 1 (L/R) ou 2 (M/S), les params se dédoublent (`ParameterA` et `ParameterB`). L'API doit gérer les deux.

3. **PointeeId conflicts**: si on génère plusieurs automations sur même paramètre, vérifier unicité des IDs.

4. **EnvelopeFollower est M4L**: assurer `<MaxForLiveDevice>` correctement référencé, et que le device `.adv` est dispo.

5. **Roar specific to Live 12**: vérifier version Live avant d'écrire.

6. **Backup mandatory**: `backup_als()` AVANT toute modification, jamais après.

7. **Idempotence**: si on appelle `write_resonance_notch` 2x avec mêmes params, le 2e appel doit no-op (ou overwrite si flag).

8. **Reading peakX_db = 0**: dans le rapport, la colonne `peak1_db` est souvent 0 — c'est la référence (le pic dominant), les autres peaks sont relatifs. L'API doit interpréter en conséquence.
