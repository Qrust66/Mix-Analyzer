# CLAUDE.md — Instructions récurrentes pour Claude Code

## Projet

Mix Analyzer v2.5.2 — Outil d'analyse audio qui génère des rapports Excel
et des automations EQ8 dynamiques pour Ableton Live.

## Versioning

La version canonique est la constante `VERSION` dans `mix_analyzer.py`.
Tous les fichiers .py de production doivent afficher la même version.
Endroits à maintenir synchronisés si la version change :

- `mix_analyzer.py` `VERSION = 'X.Y.Z'` (constante canonique)
- `mix_analyzer.py` ligne 4 (docstring)
- `mix_analyzer.py` titre fenêtre, Help, logo subtitle (utilisent `VERSION`)
- `als_utils.py` docstring ligne 4
- `spectral_evolution.py` docstring ligne 4
- `feature_storage.py` docstring ligne 4
- `eq8_automation.py` docstring ligne 4
- `automation_map.py` docstring ligne 4

La version est estampillée dans chaque rapport Excel (Index + AI Context).
Ne jamais laisser des versions désynchronisées entre fichiers.

## Communication avec l'utilisateur

- **Toujours indiquer si les changements sont disponibles sur `main`** après un commit/push.
  L'utilisateur utilise **GitHub Desktop** pour synchroniser. Dire explicitement :
  "C'est pushé sur main, tu peux faire **Pull** dans GitHub Desktop."
- Si le travail est sur une branche feature, le préciser : "C'est sur la branche X,
  pas encore sur main. Je te dirai quand merger."
- L'utilisateur n'est pas familier avec git/GitHub — toujours guider simplement,
  pas de jargon inutile. Le workflow est :
  1. On travaille ici dans Claude Code
  2. Je push sur GitHub quand c'est prêt
  3. L'utilisateur fait **Pull** dans GitHub Desktop → fichiers locaux à jour

## Fichiers de production (5 fichiers, même dossier)

| Fichier | Rôle |
|---------|------|
| `mix_analyzer.py` | App principale (UI tkinter + analyse + rapport Excel) |
| `spectral_evolution.py` | Moteur CQT + extraction features v2.5 |
| `feature_storage.py` | Écriture des sheets cachés Excel v2.5 |
| `als_utils.py` | Manipulation des fichiers .als (lecture/écriture EQ8) |
| `eq8_automation.py` | 15 fonctions d'automation EQ8 dynamique |

## Tests

- `tests/test_spectral_evolution.py` — 22 tests (phases 1-2)
- `tests/test_eq8_automation.py` — 45 tests (phases 3-8)
- `tests/test_v25_integration.py` — 4 tests d'intégration pipeline
- Lancer : `python -m pytest tests/ -v`
- Toujours lancer les tests avant de push.

## Conventions

- Style : black, type hints, docstrings sur chaque fonction publique.
- Zéro régression v2.4 : les sheets et analyses existants ne doivent pas changer.
- Pas de nouvelle dépendance sans justification (stack : numpy, scipy, librosa,
  openpyxl, soundfile, pyloudnorm).
- Commits format conventionnel : `feat(scope):`, `fix(scope):`, `chore:`, `test:`.
- Anti-timeout : max 3 fichiers modifiés par réponse, checkpoint commits fréquents.

## Observations techniques ALS (référence)

- EQ8 bands : `Bands.0` à `Bands.7`, chaque band a `ParameterA` avec
  `IsOn`, `Mode`, `Freq`, `Gain`, `Q`
- Modes EQ8 : 0=LowCut48, 1=LowCut12, 2=LowShelf, 3=Bell, 4=Notch,
  5=HighShelf, 6=HighCut12, 7=HighCut48
- Automation : `AutomationEnvelopes/Envelopes/AutomationEnvelope` au niveau track
- FloatEvent : `Id` (unique), `Time` (en beats), `Value`
- Time=-63072000 = event pré-song (état initial)
- DeviceChain path = `DeviceChain/DeviceChain/Devices` (doublé)

## Guide technique manipulation .als

Voir **`ableton/ALS_MANIPULATION_GUIDE.md`** pour les APIs Python génériques
(applicable à tout projet Ableton, pas seulement Acid Drops) : lecture/écriture
gzip, bornage de track, injection de device avec `<Devices />` self-closing,
calcul de `safe_id`, règle des grands IDs, tempo map, automations.

**Pièges critiques déjà rencontrés** :

1. **Double gzip** : `gzip.open('wb').write(gzip.compress(...))` → Ableton
   refuse d'ouvrir. Utiliser soit `gzip.open('wb').write(xml.encode())` soit
   `open('wb').write(gzip.compress(...))`, pas les deux.

2. **`<Devices />` self-closing** : les tracks sans device ont `<Devices />`
   auto-fermant. `xml.find('<Devices>', ...)` ne matche pas cette forme et
   saute sur la track suivante → device injecté sur la mauvaise track.
   Toujours borner la recherche aux limites de la track et détecter les
   deux formes (`<Devices />` et `<Devices>`).

3. **`<Envelopes />` self-closing** : même piège côté AutomationEnvelopes
   pour une track sans automation existante.

4. **Vérification post-écriture obligatoire** : relire le fichier produit,
   premiers octets doivent être `<?xml` (sinon double-gzip), et vérifier
   que le nouveau device Id se trouve bien dans les bornes de la track cible.
