# Cost-discipline rules (Mix Analyzer)

Règles comportementales que Claude (orchestrateur) doit respecter pour
ne pas gaspiller le budget tokens de l'utilisateur. Source de vérité
canonique. Les versions résumées en `memory/cost_discipline.md` (user-level)
et le hook `.claude/hooks/cost_discipline_reminder.py` y pointent.

1. **Réponses courtes par défaut.** <300 mots sauf demande explicite.
2. **Pas de "tu valides ?" répétitifs.** Confirmer seulement les actions
   destructrices/irréversibles (force-push, suppression trackée, master
   JSON, ré-écriture massive).
3. **Mini-pilote avant scale.** Pour 5+ fichiers similaires : pilote +
   validation puis scale.
4. **Cadrer le scope avant le pilote.** "in-scope = X, out = Y, tu
   confirmes ?".
5. **Déléguer à `graph-first-explorer`** pour les questions
   archi/cross-module/"comment marche X".
6. **Trust the git hooks** pour les checks mécaniques (version sync,
   pre-push regression, ALS pitfalls). Ne pas ré-implémenter en LLM.
7. **Subagents parallèles : UNE référence canonique on-disk** lue par
   chaque subagent, pas duplication du format dans chaque prompt.
8. **Pas de switch de modèle proactif.** L'utilisateur décide via
   `/model sonnet` / `/model opus`.
9. **Suggérer `/clear` ou `/compact`** aux transitions de sujet réelles.
10. **Ne pas re-lire les fichiers déjà chargés** dans la session courante.

## Détails et motivations

Voir `~/.claude/projects/<project>/memory/cost_discipline.md` (user-level)
pour le **Why:** et **How to apply:** de chaque règle, ancrés dans des
incidents observés.

## Quand le hook se déclenche

`.claude/hooks/cost_discipline_reminder.py` injecte un rappel ciblé dans
mon contexte quand le prompt utilisateur matche un pattern à risque
(scale-without-pilot, vague open brief, etc.). Il pointe ici pour les
détails.
