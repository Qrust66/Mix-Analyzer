# MIX_ENGINE_ROADMAP.md — Plan de développement mix+mastering

État au commit `5199c70` (Phase 4.9.1 + DEVICE_MAPPING_EXTENSION_GUIDE).

Ce document trace ce qui est fait, ce qui reste, et 3 ordres de priorité
possibles selon l'objectif. À mettre à jour à chaque phase complétée.

---

## ✅ Done — Tier A décisionnel (8 agents)

| # | Agent | Phase | Scope |
|---|---|---|---|
| 1 | `mix-diagnostician` | 4.1 | Infrastructure (DiagnosticReport) |
| 2 | `eq-corrective-decider` | 4.2 | Pivot — peaks, masking, HPF/LPF, M/S |
| 3 | `dynamics-corrective-decider` | 4.3 | Comp/expand/limit/gate corrective |
| 4 | `routing-and-sidechain-architect` | 4.4 | Bus, sends, sidechain |
| 5 | `stereo-and-spatial-engineer` | 4.5 | Width, M/S, bass mono |
| 6 | `chain-builder` | 4.6 | Second-order chain assembly |
| 7 | `automation-engineer` | 4.8 | Envelopes corrective + mastering scope |
| 8 | `mastering-engineer` | 4.9 | Master bus + sub-bus glue |

Tous Tier A : décident en JSON, **n'écrivent jamais le `.als`**.

---

## 🔴 GROS chantier 1 — Tier B "writers" (XML écrivains)

**Le gap critique** : aujourd'hui les decisions Tier A finissent en JSON
mais aucun agent ne traduit en patches XML Ableton. Le système est
purement décisionnel.

| Tier B agent | Consomme | Écrit dans .als | Status |
|---|---|---|---|
| `eq8-configurator` | `EQCorrectiveDecision` | Eq8 devices, 8 bandes max, Mode 0-7 mapping | ✅ **Phase 4.10 done** (5 steps, 60 tests) |
| `dynamics-configurator` | `DynamicsCorrectiveDecision` | GlueCompressor + Limiter (Phase 4.11), Compressor2/Gate/DrumBuss (Phase 4.12) | ✅ **Phase 4.11 v1 done** (4 steps, 32 tests, REUSE-only) |
| `routing-configurator` | `RoutingDecision` | Bus, sidechain refs, sends | 🟡 1 jour |
| `spatial-configurator` | `SpatialDecision` | Utility/StereoGain devices | 🟡 1 jour |
| `chain-assembler` | `ChainBuildDecision` | Ordre absolu devices par track | 🟡 1-2 jours |
| `automation-writer` | `AutomationDecision` | `<AutomationEnvelope>` XML | 🟡 partiel (eq8_automation.py existe pour Eq8 only) — 1-2 jours pour étendre |
| `master-bus-configurator` | `MasteringDecision` | Master track chain entière | 🟡 1 jour |

**Total Tier B restant** : ~7-10 jours (eq8-configurator livré).

### Pattern Tier B établi (référence Phase 4.10)

eq8-configurator livre la méthodologie réutilisable :
1. Step 1 : skeleton + translation table semantic→XML + apply basique
2. Step 2 : chain_position support (find_or_create_X_at_position parallèle)
3. Step 3 : envelope writing (cross-lane handoff sections-relative bars)
4. Step 4 : processing_mode (M/S) + idempotency by params
5. Step 5 : safety_guardian post-write (8 deterministic checks subset)

Patterns clés :
- Module Python déterministe (pas LLM), réutilise als_utils primitives
- Backward-compat strict sur als_utils (fonctions parallèles, jamais
  toucher l'API existante utilisée par eq8_automation.py)
- Idempotency-by-params : re-applying same decision = no-op
- Tests : happy + cross-field rejections + integration sur fixture .als
- Skip if template absent (graceful degradation pour CI sans
  Pluggin Mapping.als)

**Méthodologie Tier B** (différente de Tier A) : XML patches, beaucoup plus
simple que decisional, mais demande mastery du XML Ableton. Oracles
existants suffisent : `als-manipulation-oracle` + `device-mapping-oracle`.

---

## 🟡 Chantier 2 — Orchestrator / DAG executor

`mix-director` : exécute la DAG mix_engine dans le bon ordre.

```
mix-diagnostician
  ↓ DiagnosticReport
4 lanes parallèles : eq-corrective || dynamics-corrective || routing || stereo-and-spatial
  ↓ MixDecisions
chain-builder (sérialise)
  ↓ ChainBuildDecision
automation-engineer (overlay)
  ↓ AutomationDecision
mastering-engineer (final)
  ↓ MasteringDecision
[Tier B writers exécutent]
  ↓ patches .als
mix-safety-guardian (verify)
```

Sans orchestrator, user doit invoquer chaque agent à la main.

**Effort** : 2-3 jours.

---

## 🟡 Chantier 3 — Safety/audit niveau mix

`mix-safety-guardian` : équivalent du `als-safety-guardian` existant mais
pour la **cohérence inter-lanes** AVANT Tier B :
- 2 EQ corrections sur même bande/track avec params contradictoires
- Sidechain route vers track muté
- Chain budget dépassé (> 8 Eq8 bands)
- Cross-field cohérence eq-corrective + chain-builder + automation-engineer

Aujourd'hui chaque parser Tier A vérifie sa propre lane ; rien ne vérifie
au niveau MixBlueprint complet.

**Effort** : 1-2 jours.

---

## 🟢 Chantier 4 — Tier A "creative" complément (deferred par user)

User feedback Phase 4.8 : *"pour les automations créatives, on fera un autre
agent éventuellement, pour l'instant on focus sur les correction et le
mastering"*. À faire **éventuellement** :

- `eq-creative-colorist` — boosts décoratifs, character EQ, vocal sweetening, presence
- `saturation-creative-colorist` — drum warmth, parallel saturation, tape sim
- `automation-creative` — risers, drops, filter sweeps, fx swells, pan automation

**Effort** : ~2 jours par agent (méthodologie Tier A appliquée).

---

## 🟢 Chantier 5 — Phase 4.9.X (mastering gaps documentés)

Du audit pro audio post-Phase 4.9 :

| Gap | Priorité | Effort |
|---|---|---|
| `MultibandDynamics` mapping + Scenario MASTER-E activé | Moyenne | 🟡 2-4h |
| Reference matching workflow (vrai MASTER-J, pas stub) | Moyenne | 🔴 1-2 jours |
| M/S compression master (séparé de M/S EQ) | Faible | 🟡 ~3h |
| VST3 plugins additionnels (Pro-L 2, Soothe2, bx_xl V2, Ozone) | Selon user partage | Variable |

Procédure : `docs/DEVICE_MAPPING_EXTENSION_GUIDE.md`.

---

## 🟢 Chantier 6 — FX / niche (pas encore touché)

- `fx-decider` (reverb / delay / spatial FX) — out-of-scope mix corrective +
  mastering, mais nécessaire pour workflow complet

---

## 3 ordres de priorité possibles

### Ordre A — "Système end-to-end"
**Objectif** : un mix qui s'exécute du début à la fin et produit un .als modifié.

1. Tier B `eq8-configurator` (réutilise eq8_automation.py)
2. Tier B `dynamics-configurator`
3. Tier B `automation-writer` étendu (au-delà d'Eq8)
4. Tier B autres writers (routing, spatial, chain, master-bus)
5. `mix-director` orchestrator
6. `mix-safety-guardian`
7. Creative + Phase 4.9.X gaps

**Effort total** : ~3 semaines. Output : système opérationnel.

### Ordre B — "Couverture décisionnelle maximale"
**Objectif** : Tier A couvre 100% du scope mix+mastering.

1. Phase 4.9.X gaps (MultibandDynamics + reference matching + M/S compression)
2. Creative agents (eq-creative, saturation-creative, automation-creative)
3. Tier B + orchestrator après

**Effort total** : ~2 semaines décisionnel + 3 semaines Tier B après.
Output : décisions complètes mais toujours pas d'écriture .als.

### Ordre C — "Déliverable client minimum viable" ⭐ (recommandé)
**Objectif** : sortir du système opérationnel ASAP avec couverture 60-70%
des cas correctifs.

1. Tier B `eq8-configurator` seul (couvre ~60% des moves correctifs)
2. Tier B `dynamics-configurator` (couvre +20% du scope)
3. `mix-director` minimal (eq + dynamics workflow seulement)
4. Test end-to-end sur 1 vrai projet
5. Itération feedback-driven sur ce qui manque vraiment

**Effort total** : ~5-7 jours. Output : déliverable testable réel,
roadmap suivante drivée par feedback.

---

## Référence canonique

À consulter avant de démarrer une phase :
- Méthodologie Tier A : `~/.claude/projects/.../memory/tier_a_mix_agent_methodology.md`
- Device mapping checklist : `docs/DEVICE_MAPPING_EXTENSION_GUIDE.md`
- Architecture : `docs/MIX_ENGINE_ARCHITECTURE.md`
- Pitfalls .als : `ableton/ALS_MANIPULATION_GUIDE.md`
- Coding principles : `docs/CODING_PRINCIPLES.md`
