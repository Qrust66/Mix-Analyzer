# CLAUDE.md — Instructions récurrentes pour Claude Code

## Projet

Mix Analyzer v2.5 — Outil d'analyse audio qui génère des rapports Excel
et des automations EQ8 dynamiques pour Ableton Live.

## Versioning

Tous les fichiers .py de production doivent afficher **v2.5** de manière cohérente.
Endroits à maintenir synchronisés si la version change :

- `mix_analyzer.py` ligne 4 (docstring)
- `mix_analyzer.py` `self.root.title(...)` (titre fenêtre tkinter)
- `mix_analyzer.py` dialog Help title
- `mix_analyzer.py` logo subtitle + UI label (`'v2.5 — Visual Mix Diagnostic'`)
- `als_utils.py` docstring ligne 4
- `spectral_evolution.py` docstring ligne 4
- `feature_storage.py` docstring ligne 4
- `eq8_automation.py` docstring ligne 4

Ne jamais laisser des versions désynchronisées entre fichiers.

## Communication avec l'utilisateur

- **Toujours indiquer si les changements sont disponibles sur `main`** après un commit/push.
  L'utilisateur n'est pas familier avec git — dire explicitement :
  "C'est pushé sur main, tu peux télécharger les fichiers mis à jour depuis GitHub."
- Si le travail est sur une branche feature, le préciser : "C'est sur la branche X,
  pas encore sur main."
- Guider l'utilisateur sur comment récupérer les fichiers (téléchargement GitHub,
  git pull, etc.) quand pertinent.

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
