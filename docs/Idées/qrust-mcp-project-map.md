# qrust-mcp — Project Map

> Mapping projet pour réalisation future. Document vivant, à itérer.
> 
> **Statut :** design / pré-implémentation
> **Pré-requis bloquant :** Acid Drops bouncé, masterisé, distribué
> **Stack agents existants :** Mix Analyzer + 7 agents Tier A (mix-diagnostician, eq-corrective, dynamics-corrective, routing-architect, stereo-engineer, chain-builder, automation-engineer)

---

## 1. Vision

Un MCP server custom qui expose Ableton Live à Claude via un vocabulaire **sémantique aligné sur tes agents**, pas un wrapper LOM générique. Permet d'exécuter en live session les ChainPlans et AutomationPlans produits par tes agents Tier A — un move à la fois, validé, snapshotté, réversible.

**Ce qui distingue ton MCP des MCP communautaires existants :** ils parlent LOM brut (`set_device_param(track=3, idx=2, param=12, value=0.45)`). Le tien parle Qrust (`apply_corrective_eq_cut(track="Sub-Bass", band=2, freq_hz=80, q=1.8, gain_db=-3, rationale="...")`). Tes agents produisent déjà ce vocabulaire — le MCP n'a pas à traduire.

---

## 2. Principes directeurs

1. **Natif Ableton uniquement en v1.** Les 10 devices de l'automation-engineer Phase 4.8 + EQ Eight, Spectral Resonator, Hybrid Reverb, Spectral Time. Pas de plugins tiers (Pro-Q 4, Saturn 2, Kickstart 2…). VST adapter en option post-MVP.
2. **Tier A intouchable.** Aucun changement aux 7 agents existants. Le MCP est un nouveau Tier B qui consomme leur output JSON, point.
3. **Sémantique > mécanique.** Tools nommés par intent (`apply_corrective_eq_cut`, `apply_sidechain_pump`), pas par opération LOM.
4. **Réversibilité par défaut.** Snapshot auto avant chaque batch. Rollback en un tool call.
5. **Confirm-each par défaut.** Batch silencieux uniquement opt-in, jamais default.
6. **Conventions Qrust baked-in.** Le MCP refuse les moves qui violent gain staging anchors, ordre canonique de chain, hiérarchie descendante.
7. **Dumb Remote Script, smart MCP server.** Toute la logique sémantique côté MCP server. Le Remote Script est un proxy LOM typé sans intelligence.

---

## 3. Non-goals (v1)

- Plugins tiers (Pro-Q 4, Saturn 2, smart:EQ, Kickstart 2, Trackspacer, JMG, Sonible)
- Création de clips MIDI ou édition de notes (scope mix engineering, pas composition)
- Browser navigation complexe (charger preset spécifique d'un instrument tiers)
- Max for Live device manipulation
- Multi-session orchestration
- UI graphique (tout passe par Claude Desktop)
- Master engineering complet (vient après — agent dédié à venir)
- Génération créative (laissé aux humains et aux agents créatifs futurs)

---

## 4. Architecture

### 4.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────┐
│              Claude Desktop                         │
│  consomme les tools MCP, présente à l'utilisateur   │
└─────────────────────┬───────────────────────────────┘
                      │ MCP protocol (stdio)
                      ▼
┌─────────────────────────────────────────────────────┐
│         qrust-mcp-server (Python, FastMCP)          │
│  ┌───────────────────────────────────────────────┐  │
│  │ Sémantique layer                              │  │
│  │  - Tools sémantiques (~15-20)                 │  │
│  │  - Validators (gain staging, chain order…)    │  │
│  │  - Translations symboliques                   │  │
│  │  - Conventions Qrust enforcement              │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │ Plan executor                                 │  │
│  │  - consume ChainPlan + AutomationPlan         │  │
│  │  - dry-run / confirm-each / batch modes       │  │
│  │  - snapshot manager                           │  │
│  │  - operation log                              │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │ Live client                                   │  │
│  │  - socket TCP localhost:9876                  │  │
│  │  - JSON-RPC framing                           │  │
│  │  - typed responses                            │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────┘
                      │ socket TCP (localhost only)
                      ▼
┌─────────────────────────────────────────────────────┐
│      qrust-remote-script (Python, dans Live)        │
│  ┌───────────────────────────────────────────────┐  │
│  │ Socket server                                 │  │
│  │  - JSON-RPC over TCP                          │  │
│  │  - request/response avec correlation IDs      │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │ LOM proxy                                     │  │
│  │  - typed accessors (get_track, get_device…)   │  │
│  │  - undo-aware operations                      │  │
│  │  - error reporting structured                 │  │
│  │  - automation envelope read/write             │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────┘
                      │ Live API (LOM)
                      ▼
┌─────────────────────────────────────────────────────┐
│              Ableton Live 12                        │
└─────────────────────────────────────────────────────┘
```

### 4.2 Décision : socket custom vs ableton-js

**Choix : socket TCP custom Python**, pas ableton-js (Node).

Rationale :
- Stack cohérent avec tes agents (Python partout)
- Une seule dépendance runtime à maintenir
- ableton-js apporte du typage TypeScript, mais le Remote Script Python a accès direct au LOM — pas de gain de typage en pratique côté Live
- Tu peux étudier ableton-js comme référence d'API design sans en dépendre

Pattern proven : ahujasid utilise socket TCP custom et marche en prod. AbletonOSC aussi (mais en OSC plutôt que TCP-JSON).

### 4.3 Pourquoi deux processus

Le Remote Script tourne **dans** le process Ableton Live (sandboxed Python embedded). Le MCP server tourne dehors comme process Claude Desktop child. Communication via socket localhost. Cette séparation est **structurelle, pas un choix** — Ableton n'autorise pas FastMCP ou des libs externes lourdes dans son embedded Python.

Conséquence : le Remote Script doit rester minimal (stdlib Python uniquement, pas de FastMCP, pas de pydantic). Le MCP server peut avoir tout l'écosystème Python.

---

## 5. Contrats d'interface

### 5.1 Le contrat clé : `ExecutionPlan`

Format unifié consommé par le MCP server, produit par tes agents Tier A (chain-builder + automation-engineer).

```json
{
  "plan_id": "uuid",
  "session_path": "/path/to/AcidDrops_v1.4.als",
  "created_at": "ISO-8601",
  "source_agents": ["eq-corrective-decider", "chain-builder", "automation-engineer"],
  "diagnostic_report_ref": "diagnostic_report_uuid",
  
  "execution_mode": "dry_run | confirm_each | batch",
  "auto_snapshot": true,
  
  "moves": [
    {
      "move_id": "uuid",
      "sequence": 1,
      "type": "device_add | device_remove | param_set | routing | automation | snapshot",
      "target": {
        "track_name": "Sub-Bass",
        "track_id_hint": "optional fallback identifier",
        "chain_position": "pre-comp | post-comp | pre-color | tonal | send-fx",
        "device_name": "EQ Eight",
        "device_index_hint": null
      },
      "operation": { /* type-specific payload */ },
      "rationale": "kick conflict in 60-100Hz drop section",
      "source_section": "drop",
      "expected_audible_change": "reduce sub conflict, gain headroom on kick",
      "rollback_safe": true,
      "validators_passed": ["gain_staging", "chain_order", "qrust_conventions"]
    }
  ],
  
  "post_execution": {
    "verify_lufs_target": -9.9,
    "compare_to_reference_track": null,
    "trigger_re_diagnostic": true
  }
}
```

### 5.2 Payload `operation` par type

#### `param_set`
```json
{
  "param_name": "Frequency Band 2",
  "param_value": 80.0,
  "param_unit": "Hz",
  "ramp_ms": 0,
  "snap_to_value_grid": false
}
```

#### `device_add`
```json
{
  "device_class": "EqEight | Compressor2 | Limiter | GlueCompressor | MultibandDynamics | Saturator | Utility | AutoFilter2 | DrumBuss | StereoGain | SpectralResonator | HybridReverb | SpectralTime",
  "insert_position": "before | after | end_of_chain",
  "anchor_device": "Compressor2 (optional, reference)",
  "preset_initial_state": { /* optional default param overrides */ }
}
```

#### `automation`
```json
{
  "param_path": "tracks/Sub-Bass/devices/EqEight/Frequency Band 2",
  "envelope_type": "linear | curved | step",
  "breakpoints": [
    { "time_beats": 64.0, "value": 80.0 },
    { "time_beats": 80.0, "value": 120.0 },
    { "time_beats": 96.0, "value": 80.0 }
  ],
  "curve_tension": 0.0,
  "section_anchor": "drop"
}
```

#### `routing`
```json
{
  "operation_subtype": "create_send | set_send_amount | create_group | set_sidechain",
  "source_track": "Kick",
  "destination_track": "Sub-Bass",
  "send_amount": 0.0,
  "sidechain_target_param": "tracks/Sub-Bass/devices/Compressor2/Sidechain Source"
}
```

### 5.3 Format de réponse `MoveResult`

Chaque move produit une réponse uniforme :

```json
{
  "move_id": "uuid",
  "status": "success | dry_run_ok | rejected | failed",
  "executed_at": "ISO-8601",
  "before_state_snapshot_ref": "snapshot_uuid",
  "after_state_summary": {
    "param_value_actual": 80.2,
    "device_index_actual": 3
  },
  "rejection_reason": null,
  "validators_failed": [],
  "live_log_excerpt": null,
  "rollback_available": true
}
```

---

## 6. Surface MCP — tools exposés

### 6.1 Catégorisation

| Catégorie | Cardinalité | Exemples |
|---|---|---|
| Query (read-only) | ~6 | list_tracks, get_track_state, get_device_chain, get_session_info, find_track_by_role, read_automation |
| Mutation correctives | ~8 | apply_corrective_eq_cut, apply_corrective_eq_dynamic, apply_compression, apply_sidechain_pump, apply_stereo_width, apply_routing, add_send, remove_device |
| Plan execution | ~3 | execute_plan, validate_plan, dry_run_plan |
| Snapshot / rollback | ~4 | snapshot_session, list_snapshots, restore_snapshot, diff_snapshots |
| Master / monitoring | ~3 | get_master_lufs, get_track_metrics, set_master_chain |

Total : 20-24 tools. Grossit graduellement par phase.

### 6.2 Signatures détaillées (extrait critique)

```python
# Query
list_tracks() -> list[TrackSummary]
get_track_state(track_name: str) -> TrackState  # devices, params, sends, routing
get_device_chain(track_name: str) -> list[DeviceSummary]
find_track_by_role(role: TFP_role) -> list[str]  # consumes mix-diagnostician output

# Corrective EQ — aligné sur eq-corrective-decider
apply_corrective_eq_cut(
    track: str,
    band: int,             # 1-8, EQ Eight
    freq_hz: float,
    q: float,
    gain_db: float,
    rationale: str,
    section: str | None = None,
    confirm_required: bool = True
) -> MoveResult

apply_corrective_eq_dynamic(
    track: str,
    band: int,
    freq_hz: float,
    q: float,
    threshold_db: float,
    range_db: float,
    rationale: str,
    section: str | None = None
) -> MoveResult
# Implémentation : EQ Eight + envelope follower modulation, ou Multiband Dynamics

apply_hpf(track: str, freq_hz: float, slope: int, rationale: str) -> MoveResult
apply_lpf(track: str, freq_hz: float, slope: int, rationale: str) -> MoveResult

# Dynamics — aligné sur dynamics-corrective-decider
apply_compression(
    track: str,
    threshold_db: float,
    ratio: float,
    attack_ms: float,
    release_ms: float,
    knee: str,                   # soft | hard
    sidechain_source: str | None,
    rationale: str
) -> MoveResult

apply_sidechain_pump(
    target_track: str,           # ce qui ducke
    trigger_track: str,          # ce qui déclenche
    depth_db: float,
    attack_ms: float,
    release_ms: float,
    rationale: str
) -> MoveResult
# Translation symbolique Kickstart 2 → Compressor2 sidechain

apply_limiting(
    track: str,
    ceiling_db: float,
    threshold_db: float,
    lookahead_ms: int,
    rationale: str
) -> MoveResult

# Routing
apply_routing(routing_spec: RoutingSpec) -> MoveResult
add_send(source: str, destination: str, amount_db: float) -> MoveResult
create_group(track_names: list[str], group_name: str) -> MoveResult

# Stereo
apply_stereo_width(track: str, width: float, mid_side_balance: float, rationale: str) -> MoveResult
apply_bass_mono(track: str, freq_below_hz: float, rationale: str) -> MoveResult

# Plan execution
validate_plan(plan: ExecutionPlan) -> ValidationResult
dry_run_plan(plan: ExecutionPlan) -> list[MoveResult]
execute_plan(plan: ExecutionPlan, mode: str = "confirm_each") -> ExecutionReport

# Snapshot
snapshot_session(label: str, scope: str = "full") -> SnapshotRef
list_snapshots(session_path: str) -> list[SnapshotRef]
restore_snapshot(snapshot_id: str, confirm: bool = True) -> RestoreResult
diff_snapshots(snapshot_a: str, snapshot_b: str) -> DiffReport
```

### 6.3 Vocabulaire `chain_position` (de chain-builder, à enforcer)

| Position | Devices typiques | Fonction |
|---|---|---|
| gain-stage | Utility | Pre-fader trim |
| corrective-eq | EQ Eight (HPF, cuts) | Cleaning |
| corrective-dyn | Compressor2, Multiband | Control |
| pre-comp | Saturator (input drive) | Pre-compression color |
| post-comp | Saturator, Drum Buss | Post-compression saturation |
| tonal-eq | EQ Eight (tonal shaping) | Aesthetic shaping |
| stereo | StereoGain, Utility | Width / M/S |
| pre-color | Spectral Resonator, Spectral Time | Creative frequency shaping |
| send-fx | Hybrid Reverb, Echo | Spatial sends |

Le MCP refuse un `device_add` qui place un device en violation de cet ordre canonique.

---

## 7. Layer sémantique Qrust

### 7.1 Validators (côté MCP server, avant tout call socket)

| Validator | Vérifie | Action en violation |
|---|---|---|
| gain_staging | Kick à -12 dB peak comme ancre, hiérarchie descendante respectée | reject + suggest correction |
| chain_order | Ordre canonique respecté | reject + suggest insert position |
| sidechain_consistency | Trigger track existe et a un signal | reject |
| section_anchor_valid | section référencée existe dans Locators | reject |
| automation_resolution | time_beats float aligné sur grain Mix Analyzer | normalize |
| qrust_lufs_target | Master LUFS dans target -9.9 (YouTube/SC) ou -14 (DistroKid) | warn |
| no_double_processing | Pas deux compresseurs back-to-back sans rationale | warn |

### 7.2 Translations symboliques (déjà dans tes agents, formalisées MCP-side)

| Intent agent | Implémentation MCP native |
|---|---|
| Kickstart 2 sidechain | Compressor2 + sidechain routing depuis kick |
| Trackspacer auto-duck | EQ Eight sidechain (Live 12 feature) |
| Pro-Q 4 dynamic band | EQ Eight + envelope follower M4L sur band gain |
| Saturn 2 multi-stage | Saturator + Drum Buss en série |
| smart:Limiter master | Limiter + GlueCompressor + Multiband Dynamics |
| Sonible reverb | Hybrid Reverb (vintage / hall mode) |

Maintenu dans `qrust-mcp/translations.py` comme dict explicite, pas hardcodé dans les tools.

### 7.3 Conventions Qrust enforced

- Kick peak anchor : -12 dB
- Hiérarchie descendante par couche : kick > sub > mid bass > leads > pads > FX
- Master chain canonique : Smart:EQ → Smart:Comp → Smart:Limiter (translation : EQ Eight master → Glue → Limiter)
- Cible LUFS-I : -9.9 (YouTube/SoundCloud), -14 (DistroKid)
- Zéro intervention non mesurée (NO CONFLICT, NO CUT — règle north-star de eq-corrective-decider)

---

## 8. Sécurité, réversibilité, snapshots

### 8.1 Modes d'exécution

| Mode | Usage | Default |
|---|---|---|
| `dry_run` | Simulation, retourne ce qui serait fait, ne touche rien | par défaut sur première exécution d'un plan |
| `confirm_each` | Move-par-move, validation utilisateur entre chaque | par défaut sur plans validés |
| `batch` | Tous les moves en séquence sans interruption | opt-in explicite seulement |

### 8.2 Snapshots

**Auto-snapshot** avant tout `execute_plan` ou tout move solo qui n'est pas dry_run. Pas de configuration possible — c'est non-désactivable.

**Format snapshot :** copie du `.als` dans `<session_dir>/.qrust-mcp/snapshots/<timestamp>_<label>.als`. Plus métadonnées dans `<session_dir>/.qrust-mcp/snapshots/manifest.json`.

**Rétention :** rolling 50 snapshots par session. Au-delà, suppression FIFO. Snapshots taggés `keep` exempts.

**Pas de snapshot en RAM/in-memory state.** Toujours fichier sur disque. Pourquoi : si Ableton crash, ton état est sauf.

### 8.3 Operation log

Chaque move loggé dans `<session_dir>/.qrust-mcp/operations.jsonl` (append-only). Format :

```json
{"move_id": "...", "plan_id": "...", "executed_at": "...", "operation": {...}, "result": {...}, "snapshot_before": "..."}
```

Permet replay, audit, et reconstruction d'un plan a posteriori.

### 8.4 Rollback

`restore_snapshot(snapshot_id)` :
1. Demande confirmation explicite
2. Snapshot l'état actuel (avant rollback) — au cas où
3. Demande à l'utilisateur de fermer la session courante
4. Replace le `.als` par le snapshot
5. Demande à l'utilisateur de rouvrir

**Important** : pas de hot-reload de session via LOM (Ableton ne le supporte pas proprement). Le rollback implique un round-trip ouverture/fermeture manuel.

---

## 9. Stack technique

### 9.1 qrust-mcp-server (process externe)

| Composant | Choix | Raison |
|---|---|---|
| Language | Python 3.11+ | Cohérent avec agents |
| MCP framework | [FastMCP](https://gofastmcp.com/) | Standard, bien maintenu |
| Validation | Pydantic v2 | Cohérent avec stack agents |
| Async | asyncio | Pour socket non-bloquant |
| Tests | pytest + pytest-asyncio | Standard |
| Logging | structlog | Logs JSON parsables |
| Snapshot storage | filesystem direct | Simplicité, pas de DB |

### 9.2 qrust-remote-script (process Live)

| Composant | Choix | Raison |
|---|---|---|
| Language | Python 2.7 / 3.x selon Live version | Imposé par Ableton embedded |
| Dépendances externes | **aucune** | Stdlib uniquement, contrainte Live |
| Socket | `socket` stdlib + `threading` | Pas de asyncio dispo |
| Serialization | `json` stdlib | Idem |

→ Important : la doc officielle Ableton Live 12 spécifie la version Python embedded. À vérifier en P0.

### 9.3 Communication

- Protocole : JSON-RPC 2.0 over TCP
- Port : `9876` localhost (configurable)
- Framing : Content-Length headers (style LSP) ou newline-delimited JSON
- Authentification : aucune (localhost only) en v1. Token partagé en v2 si multi-user.

---

## 10. Structure des repos

### 10.1 Deux repos séparés

```
github.com/Qrust66/qrust-mcp                  # MCP server
github.com/Qrust66/qrust-remote-script        # Live Remote Script
```

Pourquoi séparés : cycles de release différents, contraintes Python différentes (stdlib only vs full ecosystem), audit de sécurité plus simple pour le Remote Script (qui tourne avec ton DAW).

### 10.2 qrust-mcp (server)

```
qrust-mcp/
├── README.md
├── pyproject.toml
├── src/qrust_mcp/
│   ├── __init__.py
│   ├── server.py                  # FastMCP entry point
│   ├── client/
│   │   ├── live_client.py         # Socket TCP client
│   │   └── protocol.py            # JSON-RPC framing
│   ├── tools/
│   │   ├── query.py               # list_tracks, get_track_state…
│   │   ├── eq.py                  # apply_corrective_eq_cut…
│   │   ├── dynamics.py            # apply_compression, sidechain_pump…
│   │   ├── routing.py
│   │   ├── stereo.py
│   │   ├── plan.py                # validate_plan, execute_plan…
│   │   └── snapshot.py
│   ├── validators/
│   │   ├── gain_staging.py
│   │   ├── chain_order.py
│   │   └── qrust_conventions.py
│   ├── translations.py            # Kickstart 2 → Compressor2 etc.
│   ├── schemas/
│   │   ├── execution_plan.py      # Pydantic models
│   │   ├── move_result.py
│   │   └── snapshot.py
│   └── snapshot/
│       ├── manager.py
│       └── filesystem.py
├── tests/
└── docs/
    ├── tools-reference.md
    ├── execution-plan-spec.md
    └── integration-with-agents.md
```

### 10.3 qrust-remote-script (in-Live)

```
qrust-remote-script/
├── README.md
├── install.md                     # Procédure copy vers User Library
├── QrustMCP/
│   ├── __init__.py                # Live entry point
│   ├── socket_server.py
│   ├── lom_proxy.py               # Typed accessors
│   ├── handlers/
│   │   ├── track.py
│   │   ├── device.py
│   │   ├── automation.py
│   │   └── transport.py
│   └── protocol.py                # JSON-RPC framing
└── tests/
    └── manual/                    # Scripts pour test interactif
```

Install path Live 12 (Windows) : `%USERPROFILE%\Documents\Ableton\User Library\Remote Scripts\QrustMCP\`

---

## 11. Roadmap par phases

### P0 — R&D et coverage LOM
**But :** valider la faisabilité avant tout investissement.

Livrables :
- Install ahujasid/ableton-mcp sur projet Ableton vide
- Test exhaustif des 13 devices natifs cibles : EqEight, Compressor2, Limiter, GlueCompressor, MultibandDynamics, Saturator, Utility, AutoFilter2, DrumBuss, StereoGain, SpectralResonator, HybridReverb, SpectralTime
- Pour chaque device : matrice get_param / set_param / list_params / add / remove → ✅ / ⚠️ / ❌
- Test sidechain routing entre tracks
- Test création de send et de group
- Test lecture et écriture d'automation envelope (le morceau le plus risqué)
- Document `research/lom-coverage-natif.md` dans Mix Analyzer repo

Done criteria :
- Couverture ≥ 80% des opérations cibles fonctionnelles
- Liste claire des contournements nécessaires pour les 20% manquants
- Décision go / no-go documentée

### P1 — qrust-remote-script MVP
**But :** brique communicante minimale dans Ableton.

Livrables :
- Socket TCP server stable (gestion connexion, déconnexion, reconnect)
- LOM proxy avec accessors typés pour : tracks, devices, params, sends, routing
- Handlers : query (read), mutation (write) basiques
- Protocole JSON-RPC clean avec correlation IDs
- Logs vers fichier dans User Library (debug Ableton est pénible sans logs)
- Install procedure documentée

Done criteria :
- REPL Python externe peut faire 50 ops séquentielles sans crash Live
- Reconnect après fermeture/réouverture session marche
- Pas de leak mémoire visible après 1h d'utilisation

### P2 — qrust-mcp-server MVP
**But :** server FastMCP qui parle au Remote Script et expose 5-7 tools query.

Livrables :
- FastMCP server bootable depuis Claude Desktop
- Live client (socket) avec error handling et timeouts
- 5-7 tools query : list_tracks, get_track_state, get_device_chain, get_session_info, find_track_by_role, read_automation
- Mode dry-run par défaut sur tools de mutation (pas encore implémentés mais flag présent)
- Tests d'intégration end-to-end (Claude Desktop → MCP → socket → Live → réponse)

Done criteria :
- Claude peut interroger un projet Ableton ouvert et obtenir un état complet en JSON
- Latence < 200ms pour query simple

### P3 — Première lane mutation : EQ corrective end-to-end
**But :** prouver la chaîne complète sur un agent réel.

Livrables :
- Tools mutation EQ : apply_corrective_eq_cut, apply_corrective_eq_dynamic, apply_hpf, apply_lpf
- Validators : gain_staging, chain_order, qrust_conventions
- Snapshot manager intégré (auto avant chaque mutation)
- Plan executor : validate_plan, dry_run_plan, execute_plan en confirm_each
- Intégration avec output de eq-corrective-decider : un ChainPlan EQ-only s'exécute end-to-end

Done criteria :
- Un cycle complet sur projet Qrust test : Mix Analyzer → eq-corrective-decider → ChainPlan → MCP → Live → modifs entendables
- Rollback fonctionnel
- Operation log complet et reparsable

### P4 — Élargissement aux autres lanes
**But :** couvrir dynamics, routing, stereo.

Livrables :
- Tools dynamics : apply_compression, apply_sidechain_pump, apply_limiting
- Tools routing : add_send, create_group, apply_routing
- Tools stereo : apply_stereo_width, apply_bass_mono
- Translation Kickstart 2 → Compressor2 sidechain implémentée
- Intégration avec dynamics-corrective-decider, routing-architect, stereo-engineer

Done criteria :
- Un ChainPlan multi-lane (EQ + dynamics + routing + stereo) s'exécute end-to-end
- Toutes les conventions Qrust enforced

### P5 — Automation engineer
**But :** la frontière dure : envelopes via LOM.

Livrables :
- Read automation envelope (récupération breakpoints existants)
- Write automation envelope avec time_beats float
- Support des 5 scénarios CORRECTIVE A→E de automation-engineer
- Support automation MASTERING (LUFS true peak ramps)
- Validators automation_resolution

Done criteria :
- Un AutomationPlan complet s'exécute et les envelopes sont visibles/audibles dans Live
- Précision sub-bar correcte (alignement Mix Analyzer grain)

### P6 — VST adapter (optionnel, post-MVP stable)
**But :** réintégrer Pro-Q 4, Kickstart 2 si nécessaire.

Livrables :
- Système de mapping plugin par fichier JSON (`vst_mappings/Pro-Q 4.json`, etc.)
- Tools tier qui acceptent un plugin tiers et résolvent les indices via le mapping
- Documentation de la procédure de mapping (capture exhaustive des params)

Done criteria :
- Pro-Q 4 et Kickstart 2 mappés et utilisables via tools sémantiques
- Procédure documentée pour ajouter un nouveau plugin

### P7 — Master engineering (dépend de l'agent dédié à venir)
À cadrer quand l'agent existe.

### P8 — Gain staging agent (dépend de l'agent dédié à venir)
À cadrer quand l'agent existe.

---

## 12. Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| LOM ne couvre pas certaines ops critiques | Moyenne | Élevé | P0 mappe la couverture avant tout dev. Plan B : OSC custom complémentaire pour les trous. |
| Update Live 12.x casse le Remote Script | Élevée (sur 18 mois) | Moyen | Tests d'intégration regression. Pin Live version dans repo README. CI manuel après chaque update Live. |
| Latence socket pénible en confirm-each | Faible | Moyen | Profiling P2, batch endpoints si nécessaire. |
| Snapshot `.als` lent sur gros projets (Summit Infinite ~70 tracks) | Moyenne | Faible | Snapshot async, ou snapshot différentiel (XML diff vs full copy). |
| Conflit avec édition manuelle simultanée dans Live | Moyenne | Moyen | Lock advisory (avertir l'utilisateur), ou refresh state avant chaque move. |
| Remote Script Python embedded version vs server externe Python 3.11 | Élevée | Moyen | Protocol JSON-RPC over wire, pas de pickle/marshal cross-process. |
| Tu pivotes l'architecture des agents en cours de route | Élevée (pattern documenté) | Élevé | Geler le contrat ExecutionPlan AVANT P1. Toute évolution agent = adapter compat-layer côté MCP, pas changement de contrat. |
| Le projet bouffe la production musicale | Élevée | Critique | Discipline : Acid Drops bouncé avant P0. Une track Qrust release entre P3 et P4. Une autre entre P4 et P5. |

---

## 13. Décisions ouvertes (à trancher avant P1)

1. **Version Live cible.** 12.0, 12.1, 12.2, ou 12.3 ? Affecte les features dispo (sidechain EQ Eight = 12.x ?).
2. **Format snapshot.** Full `.als` copy (simple, lourd) vs XML diff (compact, plus complexe à restaurer) ?
3. **Naming convention tracks.** Le MCP cherche par `track_name`. Convention forcée ou tolérance ? Comment gérer les doublons ?
4. **Précision time_beats.** Quelle résolution exacte aligne avec Mix Analyzer ? 1/64 ? 1/128 ? Float libre ?
5. **Strategy si Remote Script crash en plein plan.** Resume from last move ? Rollback total ? User decides ?
6. **Multi-set support.** v1 single set ouvert. Acceptable ?
7. **Distribution Remote Script.** Manual install vs script bash/powershell ?
8. **Versioning protocole JSON-RPC.** v1 dans tous les messages, ou negotiate handshake ?

---

## 14. Done criteria global (v1.0 release)

Le projet qrust-mcp v1.0 est considéré "released" quand :

- [ ] Une track Qrust complète (mix engineering, pas master final) a été produite via boucle Mix Analyzer → agents Tier A → qrust-mcp → Live, avec ≥ 80% des moves automatisés
- [ ] Workflow confirm-each fluide, latence acceptable subjectivement
- [ ] Zéro perte de données sur 50+ sessions cumulées
- [ ] Snapshots et rollback testés en condition réelle (≥ 5 rollbacks effectifs sans incident)
- [ ] Documentation utilisateur complète : install, usage, troubleshooting
- [ ] Le projet survit à au moins une update Live 12.x avec correctifs documentés
- [ ] Tu peux mixer une track sans toucher au workflow direct dans Live à 100% — l'option de tout faire via MCP existe (même si tu choisis de ne pas l'utiliser tout le temps)

---

## 15. Ordre d'attaque recommandé

1. **Termine Acid Drops.** Master, distribution. Non négociable.
2. **Sors la track suivante avec workflow actuel** (manuel + Mix Analyzer rapport Excel lu par Claude). Ça valide que le pipeline agents Tier A produit des décisions actionables AVANT d'investir dans l'exécuteur.
3. **P0 sur un weekend dédié.** Si la couverture LOM est insuffisante, le projet pivote ou s'arrête là — perte limitée.
4. **P1 + P2 ensemble** comme premier vrai sprint. Sans P2, P1 n'est pas testable end-to-end.
5. **P3 = milestone décisif.** Première chaîne complète. Si P3 marche, le reste est itération.
6. **Entre chaque phase : produire de la musique.** Une track Qrust minimum entre P3 et P4, idem P4-P5.

---

## Annexes

### A. Référence repos open-source à étudier

- [ahujasid/ableton-mcp](https://github.com/ahujasid/ableton-mcp) — Architecture socket TCP + Remote Script. Référence directe pour P1.
- [leolabs/ableton-js](https://github.com/leolabs/ableton-js) — TypeScript LOM wrapper. Référence d'API design (typed accessors).
- [ideoforms/AbletonOSC](https://github.com/ideoforms/AbletonOSC) — Alternative OSC. Plan B si TCP-JSON insuffisant.
- [xiaolaa2/ableton-copilot-mcp](https://github.com/xiaolaa2/ableton-copilot-mcp) — Snapshot/history pattern. Référence pour section 8.
- [uisato/ableton-mcp-extended](https://github.com/uisato/ableton-mcp-extended) — Fork ahujasid étendu. Référence patterns d'extension.
- [FastMCP](https://gofastmcp.com/) — Framework MCP server Python.

### B. Documentation Ableton à consulter

- [Live Object Model reference (Live 12)](https://docs.cycling74.com/legacy/max8/vignettes/live_object_model) — schema LOM officiel
- [Live API guide](https://structure-void.com/PythonLiveAPI_documentation/Live11.0.xml) — Structure-Void docs (référence communautaire de Julien Bayle, plus lisibles)
- [MIDI Remote Scripts guide](https://help.ableton.com/hc/en-us/articles/209072009-Live-MIDI-Remote-Scripts) — install et lifecycle Remote Scripts

### C. Conventions Qrust documentées (à factoriser dans le MCP)

- Kick anchor : -12 dB peak
- LUFS targets : -9.9 (YouTube/SoundCloud), -14 (DistroKid)
- Master chain : Smart:EQ → Smart:Comp → Smart:Limiter (mappé natif : EQ Eight master → Glue → Limiter)
- BPM cible Acid Drops : 128
- Hiérarchie descendante : kick > sub > mid bass > leads > pads > FX
- Workflow 6 étapes : niveaux → EQ → sidechain → compression → master chain → bounce
- Bounce convention : "Bounce de la piste sur place" (terminologie Ableton FR)
- Règle north-star EQ : NO CONFLICT, NO CUT
- Phrygian Dominant comme scale de référence dark industrial (chaîne MIDI générative)
- Locators Ableton = source de vérité des sections pour Mix Analyzer + automation-engineer

---

*Fin du document. Itérer librement.*
