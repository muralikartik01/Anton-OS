# DB-Kit multi-persona workflow: GitLab as the state machine

Status: draft for approval · Date: 2026-11-25 · Applies to: `legacy_to_bronze_silver_migration` (other workflows later)

## 1. Intent and why

DB-Kit users each clone the repo, so anything local is invisible to teammates. Today that breaks multi-person workflows:

- `observability/run-records/*.yaml` is git-ignored, so one person's run cannot be resumed by another.
- The Stage 4 approval is a line in that local file. `hooks/validation/require_blueprint_approval.py` only checks that the line exists. It cannot tell who wrote it, whether they were allowed to, or whether it still matches the blueprint.
- Personas do not exist in the framework. Agents are AI roles; nothing maps stages to people.

Goal: let a **data engineer** and a **data architect** run one migration across two machines, with the architect's sign-off being a real, attributable, tamper-evident GitLab approval, using only infrastructure the team already has (the self-hosted GitLab at `git.tigeranalytics.com`).

## 2. Goals, non-goals, anti-goals

**Goals**
- Run state is shared through git; any persona can resume any run.
- Approvals come from GitLab merge requests, are attributed to a GitLab user in the architect group, and are bound to the exact file contents approved.
- The same check runs locally (fast feedback, hook) and on the server (authoritative, CI).
- The central "approval source" sits behind a small interface so a different backend can replace GitLab later.
- Demo works with two personas.

**Non-goals**
- GitHub support, a hosted state service, dashboards, quorum or multi-approver rules, more than two personas, Gold layer, production release.
- Changing the discovery, generation or validation logic of the workflow.
- Moving the Neo4j context graph (it stays the shared store for discovery knowledge).

**Anti-goals (failure even if it "works")**
- An approval that can be forged by hand-editing a YAML file.
- An engineer approving their own blueprint without an explicit, visible override.
- Breaking solo/local use for people who have no GitLab access.
- Credentials (GitLab token) landing in the repo, run records or artifacts.

## 3. Constraints

- Host: self-hosted GitLab (`origin`). Tooling: `glab` CLI or REST API with a personal/project access token read from an environment variable (`DB_KIT_GITLAB_TOKEN`); never in a file.
- Local hooks can be bypassed by a user, so enforcement that matters lives in GitLab (protected branches, `CODEOWNERS`, CI), and hooks are guardrails and fast feedback.
- Existing hook and safety rules (`block_secrets`, destructive-SQL, production, allowlist) stay unchanged and keep passing their tests.
- Run records must contain references and hashes only, never secrets or source data.

## 4. Approaches considered

| | Description | Trade-off |
|---|---|---|
| **A. Git-native, GitLab MRs as state machine (chosen)** | Run record committed on a run branch; handoffs are MRs; approvals are MR approvals by a `CODEOWNERS` group; hook and CI verify them. | No new infrastructure, full audit trail. State changes are commits, so no live view. |
| B. Central state service | New MCP server on a database/Neo4j holding runs, roles, approvals. | Strong identity and live status, but a service to build, host and secure. |
| C. Hybrid ledger | Git for content plus GitLab labels/issues or Neo4j as a ledger. | Live state without a full service, at the cost of more moving parts. |

Chosen: **A**, with approvals bound to file hashes (the useful idea from C). Reason: matches "a reviewer approves a document, then the next person builds from it", and needs nothing new. The approval lookup is isolated behind an interface (section 7) so B or C can replace it.

## 5. Personas and flow (demo: two personas)

| Persona | GitLab group | Owns |
|---|---|---|
| Data engineer | `db-kit-engineers` | Starts the run; `discovery`, `assessment`, `migration_blueprint`; then `artifact_generation`, `documentation`, `validation` |
| Data architect | `db-kit-architects` | Approves the blueprint (Gate 1) and signs off the final result (Gate 2) |

Decided with the user: the **engineer authors the blueprint, the architect approves it**.

```
Engineer                         GitLab                          Architect
--------                         ------                          ---------
/db-kit-migrate ...
 branch run/<run-id>
 discovery -> assessment ->
 blueprint, commit run record
 /db-kit-submit-blueprint  ---> MR #1 (blueprint)  ------------> reviews, approves
                                 CODEOWNERS: architects           (not the author)
                                 merge to main
/db-kit-resume <run-id>   <--- merged; approval fetched
 approval written to run record (MR id, approver, hashes)
 artifact_generation ->
 documentation -> validation
 (execute_statement allowed)
 review step, commit results
 /db-kit-submit-result  -----> MR #2 (result)  ----------------> approves = sign-off
                                 merge to main                    run -> completed
```

Gate 1 sits where the current Stage 4 gate is (before `artifact_generation`). Gate 2 is new and wraps the existing `review` step and the Stage 8 release note. That the architect also signs off Gate 2 is **the designer's call**, not yet confirmed by the user.

## 6. What changes

### 6.1 Run state is shared
- Remove `observability/run-records/*.yaml` from `.gitignore`. Run records are committed on the run branch `run/<run-id>` and reach `main` through the MRs.
- Run record schema gains: `owner` (GitLab username of the persona currently driving), `branch`, `gates[]` (one entry per gate: `mr_iid`, `mr_url`, `status`), and each `approvals[]` entry gains `source: gitlab`, `mr_iid`, `approved_by` (GitLab username), `approver_group`, `approved_at`, `merge_commit`, and `artifact_hashes` (`sha256` of `blueprint.md` and `source-to-target-mapping.yaml`).
- `approvals[]` entries are written by the commands from GitLab data, never typed by the model on its own initiative.
- Only one persona writes to a run's record at a time (the `owner`). A handoff is explicit and changes `owner`.

### 6.2 Roles
- New `config/roles.yaml`: persona → GitLab group, and stage → required persona (`owner_persona`) and gate → required approver group.
- Commands check the caller's GitLab identity (token owner) against `roles.yaml` before running a stage. Wrong persona: stop and say who owns the stage.

### 6.3 Approval verification (hook + CI)
- `require_blueprint_approval.py` stops accepting an approval line on its own. It requires an `approvals[]` entry with `source: gitlab` and verifies:
  1. `artifact_hashes` match the current files on disk (an edit after sign-off invalidates the approval);
  2. `approved_by` is not the run's author (override: `collaboration.allow_self_approval`, default `false`, recorded in the report if used);
  3. optionally, a live GitLab lookup confirms the MR was merged and approved by a member of the approver group (skipped with a warning if the token is absent; CI is the authority).
- New CI job `db-kit-gates` in `.gitlab-ci.yml`, run on MRs: schema-validates the run record, re-checks hashes, author ≠ approver, approver in group. Combined with `main` being protected and `CODEOWNERS` covering `artifacts/migration-plans/` and run records, this is the enforcement that cannot be bypassed locally.
- `CODEOWNERS` entries: `artifacts/migration-plans/` and `observability/run-records/` owned by `@db-kit-architects`.

### 6.4 Commands
- `/db-kit-migrate`: creates branch `run/<run-id>`, commits the run record, stops after `migration_blueprint` with `state: awaiting_approval`, and no longer asks for approval in chat.
- New `/db-kit-submit-blueprint <run-id>` and `/db-kit-submit-result <run-id>`: commit, push, open the MR with a summary body, record the MR in `gates[]`.
- `/db-kit-resume <run-id>`: first `git fetch` and checks out the run branch (or `main` after merge); if awaiting approval, queries GitLab for the MR; if merged and approved, writes the approval entry and continues; if not, reports the MR status and waits. It never assumes a prior approval.
- `/db-kit-help` and the developer handbook are updated.

### 6.5 Approval source interface
`hooks/lib/approval_source.py` defines `get_approval(run_id, gate) -> Approval | None`. The only implementation is `GitLabApprovalSource` (REST API). A future state service or ledger implements the same interface; hooks and commands depend only on the interface.

### 6.6 Solo / local mode
`config/framework.yaml`: `collaboration.mode: gitlab | local`, default `gitlab`. `local` keeps today's behavior (chat approval, local run record) for people without GitLab access, and the run record marks `approval_mode: local` so the report and CI can see it. Demo and shared runs use `gitlab`.

### 6.7 Central framework context
All clones use the same repo, so rules, hooks, agents and skills are shared through git. `config/framework.yaml` `framework.version` is bumped on releases and the `db-kit-gates` job fails MRs from a clone on a different major version. Packaging as a plugin is a later step and out of scope.

## 7. Failure and edge cases

- Approval requested changes or MR closed: run stays `awaiting_approval` with the reason; the engineer revises and updates the same MR. Hashes changing after approval invalidate it.
- Two people start from the same run id: the second sees `owner` and the branch already exists, and must `/db-kit-resume` with an explicit takeover.
- GitLab unreachable: commands that need a lookup stop with `state: blocked` and a reason; they do not fall back to trusting the local file.
- Run record merge conflicts: avoided by single-writer ownership; if one occurs, resolve manually (documented).
- Dry run: follows the same gates in `gitlab` mode; there is no Gate 2 because validation and review do not run.

## 8. Testing

- Unit tests for the new verification logic with a fake `ApprovalSource` (hash match and mismatch, self-approval, wrong group, missing token, GitLab down).
- Existing 31 tests keep passing; `test_hooks.py` extended for the new approval entry shape and the local-mode path.
- A demo script/checklist for two accounts: engineer starts, architect approves, engineer resumes and builds, architect signs off.

## 9. Open items left to the builder

- Choice between `glab` and direct REST calls for the API layer (prefer REST with `requests` or `urllib`, to avoid a new CLI dependency).
- Exact token scopes and whether a project access token is used for CI.
- CI runner image and how `PyYAML` is installed there.
- Exact MR title/body format and label names.

## 10. Calls made by the designer (not confirmed by the user)

1. The architect also signs off Gate 2 (final result).
2. `local` mode retained as the default fallback for people without GitLab.
3. Approval is bound to SHA-256 of the blueprint and mapping files.
4. REST over `glab` as the API layer.
5. The framework-version check in CI, instead of packaging as a plugin.
