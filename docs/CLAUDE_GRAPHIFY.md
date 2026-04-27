# CLAUDE_GRAPHIFY.md — Knowledge graph (graphify) du projet

Document chargé à la demande quand Claude doit consulter le knowledge graph.
Le hub `CLAUDE.md` à la racine du repo y pointe.

## Vue d'ensemble

Le projet a un knowledge graph persistant à `graphify-out/graph.json`.
Couvre code Python + docs + briefs + composition_engine. Mis à jour
automatiquement par le hook `post-commit` quand le code change.

Stats indicatives (varient avec l'évolution du repo) :
- ~4000 nœuds
- ~7000-10000 arêtes
- ~400 communautés (étiquetées dans `GRAPH_REPORT.md`)

## Quand consulter le graph (réflexe à adopter)

- **Avant d'explorer le code par grep/Glob/Read** pour répondre à une
  question d'architecture ou trouver "qui appelle quoi" — `13×` moins de
  tokens en moyenne, jusqu'à `100×+` pour les questions cross-module.
- **Avant de modifier un fichier de production** : vérifier ses connexions
  sortantes (qui en dépend) pour estimer le rayon de blast.
- **Quand l'utilisateur référence un concept abstrait** (ex. "le moteur
  CDE", "les sections", "TFP") plutôt qu'un fichier précis — le graph
  trouve le bon point d'entrée.

## Commandes

- `/graphify query "<question>"` — réponse cross-fichiers via traversée BFS
- `/graphify query "<question>" --dfs` — trace une chaîne de dépendances
- `/graphify path "X" "Y"` — chemin le plus court entre deux concepts
- `/graphify explain "X"` — tout ce qui se connecte au nœud X
- `/graphify . --update` — re-extraction (LLM) après modif de docs/briefs

Pour multi-query + synthèse : déléguer au subagent `graph-first-explorer`
plutôt que de lancer les commandes en série dans le contexte principal.

## God nodes (abstractions centrales — toucher avec précaution)

`Section`, `CorrectionDiagnostic`, `CorrectionRecipe`, `ProblemMeasurement`,
`PeakTrajectory`, `TFPContext`, `SectionContext`. Modifier l'un de ces
types propage à >130 voisins — toujours vérifier via `/graphify explain`
avant de toucher.

## Maintenance du graph

- **Code modifié** : le post-commit hook (`.githooks/post-commit`)
  recalcule l'AST automatiquement. Rien à faire.
- **Docs / briefs / features modifiés ou ajoutés** : nécessite re-extraction
  sémantique (LLM, ~50-200K tokens). Lancer `/graphify . --update`
  manuellement après une session de modifs documentaires.
- **`graphify-out/`** : artefact local, déjà ignoré dans `.gitignore`.
  Ne jamais commit.

## Hook UserPromptSubmit (rappel automatique)

`.claude/hooks/graphify_reminder.py` détecte les patterns d'architecture
dans les prompts (`comment marche`, `qui utilise`, `pipeline`, `relation
entre`, etc.) et injecte un rappel pour consulter le graph. Coût ~50
tokens si match, 0 sinon.

Cf. `docs/CLAUDE_AGENTS.md` pour les détails du hook et de l'agent
`graph-first-explorer`.
