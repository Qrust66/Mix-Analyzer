# CLAUDE_PROJECT.md — Conventions et architecture du codebase Mix Analyzer

Document chargé à la demande quand Claude (ou un agent) a besoin des détails
projet. Le hub `CLAUDE.md` à la racine du repo y pointe.

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
- `section_detector.py` docstring ligne 4
- `cde_engine.py` docstring ligne 4 (depuis v2.7.0)

La version est estampillée dans chaque rapport Excel (Index + AI Context).
Ne jamais laisser des versions désynchronisées entre fichiers.

Le hook `pre-commit` (`.githooks/check_version_sync.py`) bloque les commits
qui touchent un de ces 8 fichiers si les versions sont désynchronisées.

## Fichiers de production (8 fichiers, racine du repo)

| Fichier | Rôle |
|---------|------|
| `mix_analyzer.py` | App principale (UI tkinter + analyse + rapport Excel + orchestration CDE depuis v2.7.0) |
| `spectral_evolution.py` | Moteur CQT + extraction features v2.5 |
| `feature_storage.py` | Écriture des sheets cachés Excel v2.5 |
| `als_utils.py` | Manipulation des fichiers .als (lecture/écriture EQ8) |
| `eq8_automation.py` | 15 fonctions d'automation EQ8 dynamique |
| `section_detector.py` | Détection / lecture des sections Ableton + sheet Sections Timeline (Feature 3/3.5/3.6 hooks) |
| `tfp_parser.py` + `tfp_coherence.py` | TFP roles (Feature 3.5) — parsing + score de cohérence par section |
| `cde_engine.py` | Correction Diagnostic Engine (Feature 3.6 B1) — diagnostics masking + JSON dump |

## Conventions

- Style : black, type hints, docstrings sur chaque fonction publique.
- **Zéro régression v2.4** : les sheets et analyses existants ne doivent pas
  changer. Le hook `pre-push` lance pytest pour le vérifier mécaniquement.
- Pas de nouvelle dépendance sans justification (stack : numpy, scipy,
  librosa, openpyxl, soundfile, pyloudnorm).
- Commits format conventionnel : `feat(scope):`, `fix(scope):`, `chore:`,
  `test:`, `docs:`, `refactor:`, `build:`.
- Anti-timeout : max 3 fichiers modifiés par réponse, checkpoint commits
  fréquents.
- Voir aussi `docs/CODING_PRINCIPLES.md` pour les principes coding généraux
  (Think Before Coding, Simplicity First, Surgical Changes,
  Goal-Driven Execution, Use the Knowledge Graph).

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

### Pièges critiques déjà rencontrés

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

5. **Nommer tout device injecté** : chaque device créé par Claude doit
   avoir un `<UserName Value="..." />` explicite révélant sa fonction
   (ex. `"Peak Resonance"`). Ne jamais laisser vide — l'utilisateur doit
   voir d'un coup d'œil à quoi sert chaque device dans sa chain. Voir
   `ableton/ALS_MANIPULATION_GUIDE.md` section "Nommer un device injecté".
