# Guide de manipulation des fichiers .als

Guide **générique** (tout projet Ableton, pas juste Acid Drops) pour manipuler
des fichiers `.als` en Python. Documente les APIs utilisées et les pièges
rencontrés en production.

Format `.als` = XML gzippé. Un fichier .als Live 11/12 contient un XML
(généralement 30-60 MB décompressé) encapsulé dans un gzip standard.

---

## 1. Compression gzip — écriture correcte (piège majeur)

### Bug : double compression

```python
# MAUVAIS : double compression, Ableton refuse d'ouvrir
with gzip.open('out.als', 'wb') as f:
    f.write(gzip.compress(xml.encode('utf-8')))
```

`gzip.open(..., 'wb')` écrit déjà un flux gzip. Lui passer `gzip.compress(...)`
gzippe une deuxième fois. Ableton décompresse une fois puis tombe sur du
binaire gzip au lieu de XML → refus d'ouverture.

### Options correctes

```python
# Option A : gzip.open écrit le stream
with gzip.open('out.als', 'wb', compresslevel=9) as f:
    f.write(xml.encode('utf-8'))

# Option B : écriture binaire + compression explicite
with open('out.als', 'wb') as f:
    f.write(gzip.compress(xml.encode('utf-8'), compresslevel=9))
```

### Vérification post-écriture (à faire systématiquement)

```python
with gzip.open('out.als', 'rb') as f:
    head = f.read(80)
assert head.startswith(b'<?xml'), "Double compression détectée"
```

---

## 2. Lecture d'un .als

```python
import gzip
with gzip.open('project.als', 'rb') as f:
    xml = f.read().decode('utf-8')
```

Le XML commence par `<?xml version="1.0" encoding="UTF-8"?>` et la racine est
`<Ableton MajorVersion="..." MinorVersion="..." ...>`.

---

## 3. Recherche de track par nom (EffectiveName vs UserName)

### EffectiveName (display name)

`<EffectiveName Value="..."/>` — nom affiché dans Ableton. **Toujours
chercher par EffectiveName**, pas par UserName.

```python
# Plusieurs tracks peuvent avoir le même nom — la première occurrence peut
# ne pas être la bonne si UserName et EffectiveName divergent.
en_pos = xml.find('<EffectiveName Value="Kick 1"')
```

### Bornes exactes d'une track (CRITIQUE)

Les tags de section (`<Devices>`, `<AutomationEnvelopes>`, etc.) apparaissent
dans chaque track. Une recherche non bornée peut déborder sur la track
suivante. **Toujours borner la recherche aux limites réelles de la track**.

```python
import re

def get_track_bounds(xml, track_name):
    en = xml.find(f'<EffectiveName Value="{track_name}"')
    if en < 0:
        raise ValueError(f"Track '{track_name}' absente")
    # Remonter au conteneur (AudioTrack / MidiTrack / GroupTrack / ReturnTrack)
    starts = list(re.finditer(
        r'<(AudioTrack|MidiTrack|GroupTrack|ReturnTrack) Id="\d+"', xml[:en]))
    ts = starts[-1].start()
    # Fin = début de la track suivante (même niveau)
    candidates = [x for x in [
        xml.find('<AudioTrack Id="', en + 1),
        xml.find('<MidiTrack Id="', en + 1),
        xml.find('<GroupTrack Id="', en + 1),
        xml.find('<ReturnTrack Id="', en + 1),
    ] if x > 0]
    te = min(candidates) if candidates else len(xml)
    return ts, te
```

---

## 4. Injection de device — cas `<Devices />` self-closing (piège majeur)

### Bug : la track sans device a `<Devices />` auto-fermant

Une track **sans aucun device** a `<Devices />` (self-closing), pas
`<Devices></Devices>`. Une recherche naïve `xml.find('<Devices>', track_start)`
**ne matche pas** le self-closing et saute sur la `<Devices>` de la track
suivante → le device injecté se retrouve sur la mauvaise track.

### Détection et conversion

```python
def inject_device(xml, track_name, device_xml):
    ts, te = get_track_bounds(xml, track_name)
    track = xml[ts:te]

    m_self = re.search(r'<Devices\s*/>', track)
    m_open = re.search(r'<Devices>', track)

    if m_self and (not m_open or m_self.start() < m_open.start()):
        # <Devices /> → <Devices>...</Devices>
        abs_pos = ts + m_self.start()
        abs_end = ts + m_self.end()
        line_start = xml.rfind('\n', 0, abs_pos) + 1
        indent = xml[line_start:abs_pos]
        inner_indent = indent + '\t'
        device_reindented = _reindent(device_xml, inner_indent)
        replacement = f'<Devices>\n{device_reindented}\n{indent}</Devices>'
        return xml[:abs_pos] + replacement + xml[abs_end:]

    if m_open:
        # Devices déjà ouvert : insérer juste après <Devices>
        abs_pos = ts + m_open.start() + len('<Devices>')
        nl = xml.find('\n', abs_pos) + 1
        ti = re.match(r'(\t+)', xml[nl:nl+50])
        target_indent = ti.group(1) if ti else '\t'
        device_reindented = _reindent(device_xml, target_indent)
        return xml[:abs_pos] + '\n' + device_reindented + xml[abs_pos:]

    raise RuntimeError(f"Pas de <Devices> dans track {track_name}")


def _reindent(block, target_indent):
    lines = block.split('\n')
    first = lines[0]
    current = first[:len(first) - len(first.lstrip('\t'))]
    diff = len(target_indent) - len(current)
    if diff > 0:
        return '\n'.join('\t' * diff + l for l in lines)
    if diff < 0:
        return '\n'.join(
            l[abs(diff):] if l.startswith('\t' * abs(diff)) else l
            for l in lines)
    return block
```

---

## 5. Device Id unique — calcul de `safe_id`

Chaque device a un attribut `Id=` (petit entier, 1-N) unique **au sein de
son conteneur direct** (le bloc `<Devices>` de la track). Un nouveau device
injecté doit prendre un Id non utilisé.

```python
def next_device_id(xml, ts, te):
    track = xml[ts:te]
    # Récupère tous les Id courts (1-4 chiffres) — les grands IDs sont des
    # références internes (LomId, AutomationTarget, etc.), pas des Id device.
    short_ids = [int(x) for x in re.findall(r'Id="(\d{1,4})"', track)]
    return (max(short_ids) if short_ids else 0) + 1
```

### Règle de remplacement des IDs du template

Quand on clone un template EQ8 depuis une track existante, il faut
**remplacer les grands IDs (5+ chiffres) uniquement** — ce sont les
références internes (AutomationTarget, LomId, etc.). Les petits Id=
appartiennent à la structure locale du device et ne doivent pas être touchés.

```python
big_ids = sorted(set(int(x) for x in re.findall(
    r'(?:Id|Value)="(\d{5,})"', template)))
new = template
for old in sorted(big_ids, reverse=True):
    new = new.replace(f'"{old}"', f'"{id_counter + (old - big_ids[0])}"')
```

---

## 6. `NextPointeeId` — maintenance

Au niveau racine du XML il existe `<NextPointeeId Value="N" />`. Live
l'utilise pour allouer de nouveaux PointeeId quand l'utilisateur crée une
automation. Quand on injecte manuellement des automations, il faut
**incrémenter cette valeur** au-delà du plus grand Id utilisé, sinon Live
peut écraser nos IDs.

```python
max_used = max(all_new_ids_we_created)
npi = re.search(r'(<NextPointeeId Value=")(\d+)(" />)', xml)
xml = xml[:npi.start(2)] + str(max_used + 100000) + xml[npi.end(2):]
```

---

## 7. Tempo map — conversion secondes → beats

Le temps dans les FloatEvent est exprimé en **beats**, pas en secondes. Si
le projet a des changements de tempo, utiliser la tempo map extraite depuis
`MasterTrack/AutomationEnvelopes`.

```python
def seconds_to_beats(time_s, tempo_events):
    """tempo_events = [(beat, bpm), ...] triée par beat."""
    beat = 0.0
    prev_sec = 0.0
    prev_bpm = tempo_events[0][1]
    for cb, nb in tempo_events[1:]:
        cs = prev_sec + (cb - beat) * 60.0 / prev_bpm
        if time_s <= cs:
            return round(beat + (time_s - prev_sec) * prev_bpm / 60.0, 4)
        beat = cb
        prev_sec = cs
        prev_bpm = nb
    return round(beat + (time_s - prev_sec) * prev_bpm / 60.0, 4)
```

---

## 8. AutomationEnvelope — structure

Un FloatEvent `Time="-63072000"` représente l'état pré-song (valeur
initiale avant beat 0). Tout envelope doit en avoir un comme premier event.

```xml
<AutomationEnvelope Id="...">
  <EnvelopeTarget>
    <PointeeId Value="..."/>  <!-- = AutomationTarget Id de la cible -->
  </EnvelopeTarget>
  <Automation>
    <Events>
      <FloatEvent Id="..." Time="-63072000" Value="..."/>  <!-- init -->
      <FloatEvent Id="..." Time="0.0" Value="..."/>
      ...
    </Events>
    <AutomationTransformViewState>
      <IsTransformPending Value="false"/>
      <TimeAndValueTransforms/>
    </AutomationTransformViewState>
  </Automation>
</AutomationEnvelope>
```

### Injection — `<Envelopes />` self-closing

Même piège que `<Devices />` : une track sans automation a
`<Envelopes />` auto-fermant.

```python
ae = xml.find('<AutomationEnvelopes>', ts)
ae_e = xml.find('</AutomationEnvelopes>', ae)
es = xml.find('<Envelopes />', ae, ae_e)  # self-closing
ec = xml.rfind('</Envelopes>', ae, ae_e)  # close tag
if 0 < es < ae_e:
    line_start = xml.rfind('\n', 0, es) + 1
    indent = xml[line_start:es]
    xml = (xml[:line_start] + f'{indent}<Envelopes>\n{envs_xml}\n{indent}</Envelopes>'
           + xml[es + len('<Envelopes />'):])
elif ec > 0:
    xml = xml[:ec] + envs_xml + '\n' + xml[ec:]
```

---

## 9. Validation finale

```python
import xml.etree.ElementTree as ET
ET.fromstring(xml)  # lève si XML invalide

# Sanity : vérifier absence de doublons d'Id parmi nos injections
# Sanity : vérifier que chaque PointeeId d'envelope pointe bien vers
#          un AutomationTarget Id existant dans notre nouveau device
```

---

## 10. EQ8 — modes et paramètres

| Mode | Nom |
|------|-----|
| 0 | LowCut48 |
| 1 | LowCut12 |
| 2 | LowShelf |
| 3 | Bell |
| 4 | Notch |
| 5 | HighShelf |
| 6 | HighCut12 |
| 7 | HighCut48 |

Bandes : `Bands.0` à `Bands.7`. Chaque bande a `ParameterA` contenant
`IsOn`, `Mode`, `Freq`, `Gain`, `Q`, chacun avec `<Manual Value="..."/>` et
un `<AutomationTarget Id="..."/>` pour automation.

Fréquences valides : 10 Hz - 22050 Hz. Q : 0.1 - 18. Gain : -15 dB à +15 dB.

---

## Checklist bugs récurrents

Avant de livrer un .als modifié, vérifier :

- [ ] Un seul layer gzip (lecture `gzip.open` → premiers octets = `<?xml`)
- [ ] XML parse avec `ET.fromstring()`
- [ ] Le nouveau device est bien dans la track visée (chercher l'Id dans
  les bornes de track, pas dans tout le fichier)
- [ ] Aucun doublon d'Id dans le bloc `<Devices>` de la track
- [ ] Tous les `PointeeId` des envelopes pointent vers un
  `AutomationTarget Id` existant dans le nouveau device
- [ ] `NextPointeeId` > max des Ids utilisés
- [ ] Taille du fichier final cohérente (~0-30% plus grand que l'original,
  pas la moitié = compression double, pas double = non compressé)
