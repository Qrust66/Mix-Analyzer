# PROMPT CLAUDE CODE — Peak Resonance EQ8 sur Acid Drops

## Contexte

Tu travailles sur le projet Mix Analyzer (Qrust66/Mix-Analyzer). L'objectif de cette session est d'ajouter des EQ Eight "Peak Resonance" sur toutes les tracks sources du projet Ableton `Acid_drops`.

**Bass Rythm est déjà traitée** dans le .als de départ. Tu continues avec les tracks restantes.

## AVANT TOUTE CHOSE

1. **Lis le fichier `ableton_devices_mapping_v2_3.json`** en entier — c'est ta source de vérité technique. En particulier :
   - `$eq8_template_method` — les 10 étapes validées
   - `$device_list_id` — le device Id doit être unique par track
   - `$id_replacement_rules` — ne remplacer QUE les IDs de 5+ digits
   - `$instrument_group_device` — skip les tracks avec InstrumentGroupDevice
   - `$tempo_mapping` — conversion secondes→beats tempo-aware obligatoire
   - `$track_lookup` — recherche par EffectiveName exclusivement
   - `$known_bugs_resolved` — les 9 bugs trouvés et corrigés

2. **Lis le rapport Excel** `_track_peak_trajectories` pour les données de résonance

3. **Lis la tempo automation** du .als (MasterTrack) pour construire la tempo map

## Fichiers d'entrée

- `.als` : le fichier Ableton avec Bass Rythm déjà traitée (dans le repo ou fourni par l'utilisateur)
- `.xlsx` : le rapport Mix Analyzer le plus récent
- `.json` : `ableton_devices_mapping_v2_3.json`

## Méthode validée — à suivre EXACTEMENT

### Création d'un EQ8

```python
# 1. Extraire un template depuis un EQ8 existant dans le fichier
#    (celui de Bass Rythm fonctionne bien comme template)
br_pos = xml.find('<EffectiveName Value="Bass Rythm"')
dev_pos = xml.find('<Devices>', br_pos)
eq8_start = xml.find('<Eq8 ', dev_pos)
eq8_end = xml.find('</Eq8>', eq8_start) + len('</Eq8>')
template = xml[eq8_start:eq8_end]

# 2. Extraire les grands IDs SEULEMENT (5+ digits)
big_ids = sorted(set(int(x) for x in re.findall(r'(?:Id|Value)="(\d{5,})"', template)))

# 3. Remplacer les grands IDs avec des IDs séquentiels
new_eq8 = template
for old in sorted(big_ids, reverse=True):
    new_eq8 = new_eq8.replace(f'"{old}"', f'"{id_counter + (old - big_ids[0])}"')

# 4. NE PAS toucher aux petits IDs (0, 1, 2) — structurels

# 5. Changer le device list Id pour éviter les doublons
max_existing = get_max_device_id(xml, track_name)  # voir ci-dessous
safe_id = max_existing + 1
new_eq8 = re.sub(r'<Eq8 Id="\d+"', f'<Eq8 Id="{safe_id}"', new_eq8, count=1)

# 6. Reset toutes les bandes: IsOn=false
# 7. Configurer les bandes nécessaires: Mode(3) → Freq → Gain → Q → IsOn(true)
# 8. Injecter dans <Devices> de la track cible
# 9. Écrire les automations dans <AutomationEnvelopes><Envelopes>
```

### Fonctions critiques

```python
def get_max_device_id(xml, track_name):
    """OBLIGATOIRE avant chaque injection. Retourne le max Id des devices existants."""
    tp = xml.find(f'<EffectiveName Value="{track_name}"')
    dp = xml.find('<Devices>', tp)
    de = xml.find('</Devices>', dp)
    block = xml[dp:de]
    first = re.search(r'\n(\t+)<\w+ Id="(\d+)"', block)
    if not first: return 0
    indent = first.group(1)
    children = re.findall(rf'\n{re.escape(indent)}<\w+ Id="(\d+)"', block)
    return max(int(x) for x in children)

def seconds_to_beats(time_s, tempo_events):
    """OBLIGATOIRE. Conversion tempo-aware."""
    beat = 0.0; prev_sec = 0.0; prev_bpm = tempo_events[0][1]
    for cb, nb in tempo_events[1:]:
        cs = prev_sec + (cb - beat) * 60.0 / prev_bpm
        if time_s <= cs:
            return beat + (time_s - prev_sec) * prev_bpm / 60.0
        beat = cb; prev_sec = cs; prev_bpm = nb
    return beat + (time_s - prev_sec) * prev_bpm / 60.0
```

### Identification des résonances

Pour chaque track, grouper les trajectoires par fréquence similaire (±1.7 demi-tons = `abs(log2(f1/f2)) < 0.1`). Trier par amplitude max décroissante. Prendre les top 6 (max 6 bandes par EQ8). Chaque groupe = 1 bande. Pour chaque frame du groupe, garder le peak le plus fort (peak dominant par frame).

### Calcul des automations par bande

```
Freq = fréquence exacte du peak à cette frame
Gain:
  amp > 5 dB  → gain = max(-6, -amp × 0.5)
  amp 0..5    → gain = max(-6, -amp × 0.6)
  amp -5..0   → gain = max(-2, amp × 0.3)
  amp -10..-5 → gain = max(-1, amp × 0.2)
  amp < -10   → gain = 0
Q:
  amp > 5     → Q = 14
  amp 0..5    → Q = 10
  amp -5..0   → Q = 6
  amp -10..-5 → Q = 3
  amp < -10   → Q = 1
```

## Tracks à traiter — ORDRE DE PRIORITÉ

Traiter **une track à la fois**. Sauvegarder et valider après chaque track.

| # | Track | Score | Résonances | Max dB | Note |
|---|---|---|---|---|---|
| 1 | Bass Rythm | 27137 | 19 | +12 | ✅ DÉJÀ FAIT |
| 2 | Sub Bass | 37630 | 15 | +14 | |
| 3 | Kick 1 | 30210 | 14 | +9 | |
| 4 | Kick 2 | 26128 | 8 | +14 | |
| 5 | Pluck Lead | 10473 | 13 | +12 | |
| 6 | ARP Glitter Box | 7228 | 5 | +8 | |
| 7 | NINja Lead Synth | 7143 | 11 | +11 | |
| 8 | Toms Rack | 5207 | 22 | +18 | |
| 9 | Ambience | 3344 | 1 | +7 | |
| 10 | Floor Toms | 2547 | 12 | +16 | |
| 11 | Xylo Texture | 1987 | 7 | +5 | |
| 12 | Riser | 1184 | 7 | +7 | |
| 13 | Glider Lead Synth | 1087 | 10 | +6 | |
| 14 | Guitar Distorted | 552 | 5 | +4 | |
| 15 | Toms Overhead | 268 | 5 | +3 | |
| 16 | Acid Bass | 42480 | 45 | +12 | ⚠️ InstrumentGroupDevice — EQ8 ajouté manuellement |

**Acid Bass** a un InstrumentGroupDevice — NE PAS créer de nouveau device. L'utilisateur a ajouté manuellement un EQ Eight nommé "EQ Eight Peak Resonnance". Écrire dans ses bandes libres (IsOn=false) et ses Envelopes. Ne pas injecter un nouveau bloc `<Eq8>`. Le traiter en DERNIER (après toutes les autres tracks) pour minimiser le risque.

Les tracks avec un score < 200 (Solo Lead Synth, Xylo Percussion, Guitar PM B, ARP Intense) peuvent être ignorées — résonances trop faibles pour justifier un traitement.

## Règles absolues

1. **1 bande = 1 résonance**. Jamais de zone-based dominant peak qui saute entre deux fréquences.
2. **1 EQ8 par procédé**. Cet EQ8 est "Peak Resonance" uniquement. Pas de HPF, pas de masking cuts dedans.
3. **Ne jamais modifier les devices existants**. Créer un NOUVEL EQ8. Ne pas toucher aux bandes actives d'un EQ8 existant.
4. **Device list Id unique**. Calculer `max(existing_ids) + 1` avant chaque injection.
5. **Tempo-aware**. Lire la tempo map du .als. Ne jamais hardcoder 128 BPM.
6. **Track lookup par EffectiveName**. Jamais de recherche par texte libre.
7. **Grands IDs seulement**. Remplacer les IDs 5+ digits. Garder les 0, 1, 2 intacts.
8. **Modifier le XML comme du texte**. Jamais de ET.tostring() re-sérialisation.
9. **gzip.compress() standard**. Pas de header gzip manuel.
10. **Sauvegarder sous un nouveau nom**. Jamais écraser l'original.

## Validation après chaque track

Après chaque injection :
1. Vérifier que le XML parse correctement avec ET.fromstring()
2. Vérifier qu'il n'y a aucun doublon d'Id dans le <Devices> de la track traitée
3. Vérifier que tous les PointeeId des envelopes pointent vers des AutomationTarget existants dans le nouvel EQ8
4. Sauvegarder et informer l'utilisateur pour test dans Ableton

## Gestion des timeouts et batching

Le fichier .als fait ~37 MB de XML. Chaque EQ8 injecté ajoute ~41K chars + les envelopes. Avec 15 tracks × ~7000 breakpoints chacune, le volume total est massif. **Tu vas probablement manquer de contexte si tu essaies tout d'un coup.**

### Stratégie de batching

- **Maximum 3 tracks par opération**. Après 3 tracks, sauvegarder le .als, faire un checkpoint, et continuer dans une nouvelle opération sur le fichier sauvegardé.
- **Ordre de traitement par batch** :
  - Batch 1 : Sub Bass, Kick 1, Kick 2
  - Batch 2 : Pluck Lead, ARP Glitter Box, NINja Lead Synth
  - Batch 3 : Toms Rack, Ambience, Floor Toms
  - Batch 4 : Xylo Texture, Riser, Glider Lead Synth
  - Batch 5 : Guitar Distorted, Toms Overhead
  - Batch 6 : Acid Bass (seul — cas spécial, EQ8 déjà créé manuellement)

### Quand sauvegarder

- Après **chaque batch de 3 tracks** : sauvegarder sous `Acid_Drops_Code_BatchN.als`
- Le batch suivant **repart du fichier sauvegardé** du batch précédent
- Si une track a plus de 1000 frames de peaks, la traiter **seule** dans son propre batch (Sub Bass = 843 frames, Kick 1 = 1235 frames)

### Estimation de charge par track

| Track | Frames | Résonances | ~Breakpoints | Charge |
|---|---|---|---|---|
| Sub Bass | 843 | 15 | ~10K | Lourde |
| Kick 1 | 1235 | 14 | ~12K | Très lourde |
| Kick 2 | 982 | 8 | ~8K | Lourde |
| Pluck Lead | 258 | 13 | ~3K | Moyenne |
| ARP Glitter Box | 272 | 5 | ~2K | Légère |
| NINja Lead Synth | 205 | 11 | ~3K | Moyenne |
| Toms Rack | 107 | 22 | ~3K | Moyenne |
| Ambience | 477 | 1 | ~1.5K | Légère |
| Floor Toms | 79 | 12 | ~1K | Légère |
| Acid Bass | 476 | 45 | ~8K | Lourde (cas spécial) |

### Si le contexte se remplit

1. **Ne pas tenter de finir** — sauvegarder ce qui est fait proprement
2. Indiquer clairement quelles tracks sont traitées et lesquelles restent
3. Le prochain prompt reprendra avec le fichier sauvegardé et la liste des tracks restantes
4. **Préparer les fonctions utilitaires en premier** (create_eq8, get_resonances, compute_automations) et les réutiliser pour chaque track — ne pas réécrire le code à chaque fois

### Structure de code recommandée

Écrire un **script réutilisable** (`apply_peak_resonance.py`) qui prend en paramètre le .als, le .xlsx, et une liste de tracks à traiter. Comme ça, si le contexte timeout, l'utilisateur peut relancer le script sur les tracks restantes sans repasser par Claude Code.

```python
# Usage:
# python apply_peak_resonance.py Acid_Drops_Code.als rapport.xlsx "Sub Bass" "Kick 1" "Kick 2"
#
# Produit: Acid_Drops_Code_resonance.als
```

## Livrables

- Le `.als` modifié avec les EQ8 Peak Resonance sur toutes les tracks traitées
- Un résumé par track : quelles résonances, combien de breakpoints, amplitude max
- Acid Bass : traité via l'EQ8 ajouté manuellement (pas de nouveau device créé)
