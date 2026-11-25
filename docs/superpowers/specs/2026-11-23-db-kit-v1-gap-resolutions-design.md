# DB-Kit V1 / Phase 1 — Gap Resolutions

**Status:** Approved
**Scope:** Resolves six open design questions in `DB-Kit-V1-spec.md` that were left unresolved before Milestone 0 implementation. This doc is additive to the spec, not a replacement — where the two conflict, this doc wins for Phase 1.

---

## 1. Context Engine / retrieval

**Decision:** The Project Context Model's discovery-side entities (Source System, Dataset, Schema, Pipeline, Transformation, Dependency, Business Rule) are **not built by DB-Kit**. They live in a Neo4j graph prepared and owned by another team, accessed exclusively via MCP.

- DB-Kit reads this graph via MCP for all discovery/context retrieval.
- DB-Kit **writes annotations back** onto existing graph nodes via MCP — gaps, assumptions, verified-status — as a separate `DbKitAnnotation` node type connected via `ANNOTATES`, never by mutating canonical node properties. This means a refresh of the canonical graph by the owning team cannot clobber DB-Kit's contributions.
- Run-specific entities — Migration Mapping, Decision, Validation Result, Workflow Run, Layer assignment — are **not** written to the graph. They stay as DB-Kit-owned repo files keyed by run ID, because they're tied to a specific approval/run rather than being durable facts about the data estate.
- The real Neo4j MCP server is being built in parallel by the other team. DB-Kit develops against a **mock MCP server** implementing the same tool contract (see `integrations/mcp/neo4j-context/CONTRACT.md`) until the real one is ready.

**Rationale:** avoids rebuilding a knowledge graph that already exists elsewhere, keeps DB-Kit's write footprint isolated from the canonical data so there's no contention over who owns graph integrity, and unblocks DB-Kit development from the other team's timeline via a mock.

## 2. Hooks — enforced vs. policy

**Decision:** every safety boundary in spec §9.3 gets a real enforcement mechanism, not just a documented instruction. Three mechanism types:

- **(A) Content-pattern hooks** — PreToolUse hooks scan content before it's written/executed: secret-shaped strings before any write/commit; a destructive-SQL keyword blocklist (`DROP`, `TRUNCATE`, `DELETE` without `WHERE`, `ALTER ... DROP COLUMN`, etc.) before anything executes against a real connection, blocking unless the run record carries an explicit per-statement approval. **This is documented honestly as pattern-based, not a semantic guarantee** — it catches known destructive keywords, not every possible destructive operation (e.g. obfuscated or multi-statement scripts).
- **(B) Config-driven allowlist hooks** — PreToolUse hooks check the target of a write/external call against `project.yaml`/`integrations.yaml`: block writes to any connection tagged production unless `production_writes_enabled` is true *and* the run has an explicit approval; block calls to any integration not declared in `integrations.yaml`.
- **(C) Workflow-state gates** — block the Stage 6 → Stage 7 transition unless the validation report explicitly enumerates a pass/fail/blocked status for every planned check (no silent omission of a check that couldn't run).

**Rationale:** an MVP meant to demonstrate the framework's power should prove its safety claims are real gates, not prompt instructions an agent could ignore under pressure.

## 3. Workflow state & cross-session resume

**Decision:** Option A — a **run-record file is the single source of truth** for a workflow run's state.

- `observability/run-records/<run-id>.yaml` holds: workflow ID/version, current state, current stage, and **file-path references** to every artifact produced so far (never inlined content).
- A dedicated resume command (`.claude/commands/db-kit-resume.md`) reads the run record, loads only the referenced artifacts, prints a resume summary, and continues from the recorded stage — in a brand-new session if needed.
- This is the mechanism that makes cross-session resume (pause at approval, come back days later) possible without re-deriving prior stages' work.
- **Deferred:** a fully deterministic non-LLM workflow runner that would make stage-order violations structurally impossible. Revisit if the pilot shows the LLM-driven resume isn't being followed reliably.

**Rationale:** cheapest mechanism that satisfies the actual requirement (cross-session resume), consistent with "context before execution" — load only what's referenced, not everything.

## 4. Dynamic workflow planning

**Decision:** deferred to post-pilot (Milestone 8+). Phase 1 only implements the registered `legacy_to_bronze_silver_migration` workflow, end-to-end, reliably.

**Rationale:** dynamic planning is the highest-risk, hardest-to-bound part of the spec. A single well-executed registered workflow with real safety gates and resumability is a stronger demo than a partially-working dynamic planner layered on an unproven foundation.

## 5. Rules / skills / agent-contract ownership

**Decision:** three distinct, non-overlapping layers, kept separate even at V1's small scale (5 agents):

- **Rules** (`rules/*`) — always-loaded, stable constraints. Short and declarative, no procedure (e.g. "never write to a connection tagged production").
- **Skills** (`skills/*`) — invocable how-to procedures for a bounded task (e.g. "how to perform source-to-target mapping"). The method, not the constraint.
- **Agent contracts** (`agents/*.md`) — who does it: scope, inputs, permitted tools, output format, escalation. Reference rules/skills by name rather than restating their content.

**Rationale:** prevents the same standard or procedure from drifting into multiple inconsistent copies as the framework grows post-pilot.

## 6. Token/context budget guardrail

**Decision:** soft warning only for V1. Agents proceed regardless of discovery scope size, but must record actual usage (files read, approximate content size) in the run report.

**Rationale:** keeps friction low for the pilot; a hard pre-execution cap is deferred until real usage data from the pilot shows it's needed.

---

## Deliverables implied by this doc

- `integrations/mcp/neo4j-context/CONTRACT.md` — the tool contract to hand to the team building the real Neo4j MCP server.
- `integrations/mcp/neo4j-context/mock_server/` — a runnable mock implementing that same contract, backed by fixture data.
- Hook scripts under `hooks/` wired into `.claude/settings.json` implementing mechanism types A/B/C from §2.
- `observability/run-records/` schema + `.claude/commands/db-kit-resume.md`.
- Filled-out `rules/`, `agents/*.md`, `skills/*`, and `workflows/registry.yaml` + `workflows/templates/legacy-to-bronze-silver.yaml` per the ownership split in §5.
