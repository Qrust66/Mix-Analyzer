# CLAUDE.md — Hub du projet Mix Analyzer

Ce fichier est chargé automatiquement à chaque session Claude Code. Il est
volontairement court (~100 lignes) ; les détails sont dans `docs/CLAUDE_*.md`
et chargés à la demande quand pertinent.

## Projet

Mix Analyzer v2.7.0 — Outil d'analyse audio qui génère des rapports Excel
et des automations EQ8 dynamiques pour Ableton Live. Depuis v2.7.0, produit
également un fichier `<projet>_diagnostics.json` à côté du `.als` via le
Correction Diagnostic Engine (Feature 3.6 B1, cf. `cde_engine.py`).

## Communication avec l'utilisateur

- **Toujours indiquer si les changements sont disponibles sur `main`** après
  un commit/push. L'utilisateur utilise **GitHub Desktop**. Dire explicitement :
  "C'est pushé sur main, tu peux faire **Pull** dans GitHub Desktop."
- Si le travail est sur une branche feature, le préciser.
- L'utilisateur n'est pas familier avec git/GitHub — guider simplement, pas
  de jargon inutile. Workflow : on travaille ici → je push → l'utilisateur
  fait Pull dans GitHub Desktop.

## Économiser des tokens

10 règles comportementales canoniques dans **`.claude/COST_DISCIPLINE.md`**.
Le hook `cost_discipline_reminder.py` injecte un rappel ciblé quand le
prompt utilisateur matche un pattern à risque. Détails et incidents
motivants en mémoire user-level (`memory/cost_discipline.md`).

Voir aussi **`docs/CODING_PRINCIPLES.md`** pour les principes coding
(Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven
Execution, Use the Knowledge Graph).

## Tests

- `tests/test_spectral_evolution.py` — 22 tests
- `tests/test_eq8_automation.py` — 45 tests
- `tests/test_v25_integration.py` — 4 tests d'intégration pipeline
- Lancer : `python -m pytest tests/ -v`
- Toujours lancer les tests avant de push (le hook `pre-push` le fait
  automatiquement).

## Conventions essentielles

- Style : black, type hints, docstrings.
- **Zéro régression v2.4** : sheets et analyses existants ne doivent pas
  changer. Le hook `pre-push` le vérifie via pytest.
- Commits format conventionnel : `feat(scope):`, `fix(scope):`, etc.
- Anti-timeout : max 3 fichiers modifiés par réponse, checkpoint commits
  fréquents.

## Détails (chargés à la demande via Read)

| Document | Contenu |
|----------|---------|
| **`docs/CLAUDE_PROJECT.md`** | Versioning (8 fichiers), fichiers de production, observations ALS, guide manipulation `.als`, **5 pièges critiques** déjà rencontrés |
| **`docs/CLAUDE_AGENTS.md`** | Hooks git (pre-commit, pre-push, post-commit), hooks Claude Code, 4 subagents (`als-safety-guardian`, `version-sync-checker`, `graph-first-explorer`, `regression-detector`), composition engine architecture (Phase 1) |
| **`docs/CLAUDE_GRAPHIFY.md`** | Knowledge graph `graphify-out/graph.json` — quand consulter, commandes `/graphify`, god nodes, maintenance |
| **`docs/CODING_PRINCIPLES.md`** | 5 principes coding (Think Before, Simplicity, Surgical, Goal-Driven, Use Graph) |
| **`.claude/COST_DISCIPLINE.md`** | 10 règles d'économie de tokens |

Quand une tâche concerne explicitement un de ces sujets, lire le document
associé. Sinon ne pas le charger (économise contexte).
