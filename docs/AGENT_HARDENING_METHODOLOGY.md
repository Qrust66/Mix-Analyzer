# AGENT_HARDENING_METHODOLOGY.md

Methodology for transforming an audited weakness into a force,
applicable to **every** mix/composition agent. Established Phase 4.2.3.

> **Use this file as the canonical pattern when fixing any agent
> weakness identified by the audio-engineer audit.**

## Why a methodology

Audit produces a list of weaknesses. Each weakness, applied in one shot,
is risky : schema breaks, parser breaks, tests break, agent .md doesn't
match the schema, downstream agents fail to consume new fields.

Decomposing each weakness into 8 robustness-preserving sub-steps gives :
- Atomic verifiability — each sub-step is independently checkable
- Reversibility — if sub-step 4 reveals a problem, you stop without a
  half-broken commit
- Token discipline — small focused diffs, easier to review
- Standardization — same pattern across agents = predictable
  development velocity

## The 8 sub-steps per weakness

For every audited weakness, execute in this order :

### 1. Plan + semantics
- Restate the weakness in one sentence
- Define the contract (what value/field/scenario you're adding)
- Enumerate allowed values / canonical enums if applicable
- Identify cross-cutting impacts (other agents, parsers, tests that
  could break)

### 2. Schema change (if applicable)
- Add field/constant to the relevant schema module
- Use `frozenset` for canonical enums (single source of truth)
- Default value choice : "default" string for "let downstream decide",
  None for "not applicable"
- Update `__all__`

### 3. Parser change (if applicable)
- Add validation against the canonical enum
- Cross-field consistency checks (e.g., "field X only valid when
  field Y in {…}")
- Lenient input where reasonable, strict output always
- Update parser `__all__`

### 4. Re-export in package `__init__.py`
- Public API surface stays clean
- Constants + types + parsers all re-exported

### 5. Tests
At minimum :
- Default value preserved (backward compat for old payloads)
- Each valid enum value parses correctly (parametrized)
- Invalid value rejected with clear error message
- Cross-field consistency violations rejected
- Realistic end-to-end payload using the new field

### 6. Agent .md update
- Schema section : new field documented with semantics
- Each scenario that uses the new field : explicit guidance
- Anti-patterns : "don't set X to Y when…"
- Reference any new constants / enums

### 7. Smoke test
- Build a Python payload exercising the new feature
- Parse it
- Verify the resulting Decision matches expectations
- Optionally : exercise the downstream Tier B if available

### 8. CHANGELOG + commit
- New CHANGELOG entry under the agent's phase (e.g., 4.2.3, 4.2.4)
- Conventional commit message
- DO NOT push without explicit user authorization

## Stop conditions (sub-step gate)

After each sub-step, verify :
- Tests pass (or the failures are expected and documented)
- No unrelated files modified
- The diff is reviewable in one pass

If any condition fails, **stop and diagnose** before proceeding to the
next sub-step.

## Wait-for-go cadence

After completing all 8 sub-steps for one weakness, **stop and wait**
for explicit user approval before starting the next weakness. The user
audits the work via `git log` / `git diff`, calls out anything they
disagree with, and either approves the next step or requests revision.

## Application across agents

This methodology applies to :
- Composition agents (motif-decider, structure-decider, etc.)
- Mix Tier A agents (eq-corrective-decider, dynamics-corrective-decider, …)
- Mix Tier B agents (eq8-configurator, automation-writer, …)
- Knowledge oracles (device-mapping-oracle, etc.)

Each agent's audit produces N weaknesses → N execution loops of these
8 sub-steps → N CHANGELOG entries → N commits.

## Phase versioning

Within an agent's hardening lifecycle :
- Phase X.Y = initial agent ship
- Phase X.Y.1 = first audit cleanup batch (multiple weaknesses fixed
  in same commit, used early before this methodology was established)
- Phase X.Y.Z (Z ≥ 2) = single weakness fix using the 8-sub-step
  methodology, one commit per Z

Example for eq-corrective-decider :
- Phase 4.2 = initial ship
- Phase 4.2.1 = expand to all EQ families (audit fix batch — pre-methodology)
- Phase 4.2.2 = hard-rule vs adaptive heuristic clarification
- Phase 4.2.3 = chain_position field (single weakness, methodology applied)
- Phase 4.2.4 = processing_mode field
- Phase 4.2.5 = bus elevation scenario
- … etc.
