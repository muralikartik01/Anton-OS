# DB-Kit V1 — Data Engineering Migration Framework

**Version:** 1.0  
**Status:** Initial specification  
**Primary implementation environment:** Claude Code  
**Initial domain:** Legacy-to-Medallion data migration  
**Initial target scope:** Legacy/source pipeline → Bronze → Silver, with validation

---

## 1. Purpose

DB-Kit is a reusable, repository-based framework for using Claude Code to execute structured data-engineering workflows. V1 focuses on medallion-architecture migration: discovering and understanding an existing data estate, planning migration, generating implementation artifacts, validating outcomes, and preparing changes for human review.

DB-Kit is intended to make work repeatable, context-aware, auditable, and bounded. It is **workflow-first**, with agents used where analysis or reasoning is required. It is not intended to be an unrestricted agent swarm or a replacement for deterministic engineering tools.

### V1 objectives

- Onboard a data-engineering project and its relevant sources.
- Build a structured, retrievable project-context model.
- Establish project and framework rules.
- Provide specialized subagents, skills, hooks, and tools.
- Support registered and bounded dynamic workflows.
- Execute a first migration workflow from legacy/source logic to Bronze and Silver.
- Validate generated or changed artifacts against available evidence.
- Record workflow execution, decisions, approvals, failures, and results.

### Out of scope for V1

- Autonomous production deployments or destructive operations.
- Full enterprise orchestration platform.
- General-purpose migration across every warehouse, lakehouse, and ETL platform.
- Unbounded workflow self-modification.
- Fully automated migration of ambiguous business logic without review.
- A dedicated UI or SaaS control plane; the initial interface is Claude Code and the repository.

---

## 2. Design principles

1. **Workflow-first:** workflows define the execution structure and checkpoints; agents perform bounded tasks within them.
2. **Context before execution:** agents retrieve project context instead of repeatedly scanning the entire project.
3. **Evidence over assumptions:** generated outputs must distinguish discovered facts, inferred information, and unresolved assumptions.
4. **Human approval at consequential boundaries:** approvals are required before sensitive changes, external writes, or potentially destructive operations.
5. **Deterministic checks where possible:** use SQL engines, tests, linters, schema checks, and scripts for verification rather than relying solely on LLM judgment.
6. **Modular and extensible:** workflows, skills, rules, agents, integrations, and validators should be reusable.
7. **Platform-aware:** target-platform-specific generation and validation should be selected explicitly.
8. **Traceable:** workflow outputs, source evidence, changes, and validation results should be recorded.
9. **No fabricated project facts:** missing information is surfaced as an assumption, question, or blocker.
10. **Incremental implementation:** start with a reliable single workflow before adding complex orchestration.

---

## 3. Conceptual architecture

DB-Kit consists of the following logical components.

### 3.1 DB-Kit Core

The core provides:

- Framework-level instructions and conventions.
- Project configuration loading.
- Workflow discovery and registry access.
- Context retrieval coordination.
- Execution policy and approval boundaries.
- Artifact organization.
- Basic execution logging.

### 3.2 Context Engine

Responsible for constructing and retrieving a structured Project Context Model containing:

- Repository and project information.
- Source systems and datasets.
- Schemas and metadata.
- Pipelines and transformations.
- Data dependencies and lineage.
- Business rules.
- Medallion-layer mappings.
- Quality checks and validation evidence.
- Migration status and decisions.

The context model should be logically graph-shaped. V1 may store it in structured files or a lightweight index; a dedicated graph database is not a prerequisite. The implementation should define a stable model and retrieval interface so storage can evolve.

### 3.3 Workflow Engine

Responsible for:

- Discovering registered workflows.
- Loading workflow definitions.
- Resolving inputs and prerequisites.
- Selecting bounded dynamic workflow plans.
- Managing workflow steps, state, checkpoints, retries, and failure handling.
- Enforcing approval gates.
- Recording execution outcomes.

In V1, Claude Code may implement orchestration through workflow instructions, scripts, and structured definitions rather than a separate runtime service.

### 3.4 Agent Runtime

Provides specialized agents for discrete responsibilities. Agents must have explicit scope, input requirements, permitted tools, expected output format, and escalation conditions.

### 3.5 Validation Engine

Provides deterministic and agent-assisted validation, including:

- Schema checks.
- SQL/code checks.
- Data-quality tests.
- Row-count comparisons.
- Reconciliation.
- Business-rule checks.
- Dependency checks.
- Review checklists.

### 3.6 Integration Layer

Connects to project systems using approved integrations, including MCP where available:

- Source and target databases.
- Warehouses and lakehouses.
- Git repositories.
- Documentation.
- Metadata systems.
- Existing pipeline platforms.

Integrations are optional and must be configured explicitly.

### 3.7 Observability

V1 observability should capture:

- Workflow ID and run ID.
- Trigger and input.
- Workflow plan and version.
- Context references used.
- Agent and skill invocations.
- Tool activity where available.
- Artifacts created or changed.
- Validation outcomes.
- Approvals and decisions.
- Failures and recovery actions.
- Completion status.

Logs should not unnecessarily store secrets or sensitive raw data.

---

## 4. Project onboarding

Onboarding is the entry point for a new project.

### 4.1 Inputs

The framework may collect:

- Project name and description.
- Repository path and repository structure.
- Source platforms.
- Target platform and environment.
- Existing ETL/ELT tools.
- Data architecture and conventions.
- Relevant documentation.
- Available MCP connections.
- Project-specific constraints.
- User-provided assumptions and migration goals.

### 4.2 Onboarding process

1. Read the framework and project configuration.
2. Inspect the repository and relevant project files.
3. Discover available integration connections and permissions.
4. Collect relevant metadata, schemas, code, and documentation within approved access.
5. Identify pipelines, transformations, datasets, dependencies, and business rules.
6. Classify information as verified, inferred, or unknown.
7. Build or update the Project Context Model.
8. Produce an onboarding summary and list of gaps.
9. Ask the user to confirm material assumptions or missing project details.
10. Persist approved context and decisions.

### 4.3 Onboarding output

- Project profile.
- Source/target technology profile.
- Repository inventory.
- Initial pipeline and dependency inventory.
- Initial context model.
- Context gaps and assumptions.
- Onboarding report.

Onboarding must not imply that a source was inspected when access was unavailable.

---

## 5. Project Context Model

The Project Context Model is a foundational framework artifact.

### 5.1 Conceptual entities

| Entity | Description |
|---|---|
| Project | Project identity, purpose, constraints, and configuration |
| Repository | Code repository and relevant paths |
| Source System | Upstream system or data provider |
| Dataset | Table, view, file, API dataset, or logical dataset |
| Schema | Columns, types, constraints, and metadata |
| Pipeline | Ingestion or transformation process |
| Transformation | SQL, Python, Spark, dbt, or other transformation logic |
| Dependency | Relationship between jobs, datasets, and transformations |
| Layer | Bronze, Silver, Gold, or explicitly defined equivalent |
| Business Rule | Business logic or semantic expectation |
| Data Quality Check | Test or quality expectation |
| Migration Mapping | Source-to-target mapping or migration relationship |
| Artifact | Code, configuration, documentation, plan, or report |
| Decision | Approved design decision or exception |
| Validation Result | Test, reconciliation, or review result |
| Workflow Run | Execution record, status, and output references |

### 5.2 Relationships

Examples:

- Source System → produces → Dataset.
- Pipeline → reads → Dataset.
- Pipeline → executes → Transformation.
- Transformation → produces → Dataset.
- Dataset → belongs to → Layer.
- Dataset → depends on → Dataset.
- Business Rule → applies to → Dataset/Transformation.
- Validation → validates → Dataset/Artifact.
- Migration Mapping → maps → Source Dataset to Target Dataset.
- Workflow Run → creates/updates → Artifact.
- Decision → governs → Workflow/Artifact.

### 5.3 Context retrieval

Context retrieval should:

- Retrieve only task-relevant context.
- Include provenance and references where possible.
- Prioritize verified facts.
- Include unresolved assumptions when relevant.
- Avoid unnecessarily loading large files or sensitive data.
- Provide a summary with links or paths to source evidence.

### 5.4 Context updates

After a workflow run, the model may be updated with:

- Newly discovered metadata.
- Verified dependencies.
- Approved migration mappings.
- New artifacts and their relationships.
- Validation results.
- Workflow status.
- Decisions and exceptions.

Unverified agent claims must not be promoted to verified project facts automatically.

### 5.5 Storage

V1 may use structured repository artifacts such as YAML, JSON, Markdown, or a local index. Storage must be version-controlled when appropriate and must avoid committing secrets or sensitive data.

---

## 6. Framework rules and memory

### 6.1 Rules

Rules define stable constraints and conventions.

Suggested categories:

- Core framework rules.
- Data-engineering rules.
- Medallion architecture rules.
- Target-platform rules.
- SQL and code standards.
- Security and privacy rules.
- Workflow execution rules.
- Validation and evidence rules.

Rules should be scoped, concise, and prioritized. Avoid duplicating large workflow instructions inside rules.

### 6.2 Memory and decisions

Memory is not a substitute for source evidence. It should contain durable context such as:

- Project decisions.
- Approved assumptions.
- Architecture conventions.
- Migration preferences.
- Known constraints.
- Prior workflow outcomes that remain relevant.

Each important decision should include its date, scope, status, and rationale when practical. Temporary run state belongs in workflow execution records, not permanent memory.

---

## 7. Subagents

V1 begins with a small set of specialized agents.

### 7.1 Discovery Agent

**Purpose:** Analyze project sources and identify relevant data-engineering assets.

**Responsibilities:**

- Inventory repositories, scripts, schemas, pipelines, and dependencies.
- Identify source datasets and transformation logic.
- Extract metadata and evidence.
- Identify gaps and ambiguities.
- Produce structured discovery output.

**Must not:** claim inaccessible sources were inspected or invent lineage.

### 7.2 Migration Architect Agent

**Purpose:** Design the migration approach and target medallion mappings.

**Responsibilities:**

- Review discovery output and project context.
- Propose Bronze, Silver, and future Gold mappings.
- Identify transformation patterns and dependencies.
- Assess risks and migration complexity.
- Recommend sequencing and checkpoints.
- Produce a migration blueprint.

**Must not:** silently resolve ambiguous business logic or authorize production changes.

### 7.3 Transformation Agent

**Purpose:** Generate or modify migration artifacts within an approved plan.

**Responsibilities:**

- Generate SQL, Python, pipeline definitions, configuration, and documentation.
- Follow project and target-platform conventions.
- Respect approved mapping and workflow scope.
- Explain material changes and assumptions.
- Prepare artifacts for validation.

**Must not:** bypass approval gates, introduce unapproved architecture changes, or execute destructive operations.

### 7.4 Validation Agent

**Purpose:** Create and interpret validation evidence.

**Responsibilities:**

- Generate test cases and validation plans.
- Identify source-to-target checks.
- Prepare reconciliation logic.
- Review schema and business-rule compliance.
- Analyze validation failures.
- Report limitations and evidence.

Where possible, the agent should use deterministic validation tools rather than rely on subjective LLM assessment.

### 7.5 Review Agent

**Purpose:** Conduct a final review of migration artifacts.

**Responsibilities:**

- Review correctness, consistency, and standards.
- Identify risks and missing tests.
- Review workflow completeness.
- Check evidence and assumptions.
- Produce actionable findings.

The Review Agent is not a replacement for human approval.

### 7.6 Agent contract

Every agent should define:

- Name and purpose.
- Scope and non-goals.
- Required inputs.
- Context retrieval instructions.
- Permitted tools.
- Output format.
- Evidence requirements.
- Error and escalation behavior.
- Approval boundaries.

---

## 8. Skills

Skills are reusable procedural capabilities that agents or workflows can invoke.

Initial skills:

- Project discovery.
- Repository analysis.
- Source schema analysis.
- Pipeline and lineage analysis.
- Business-rule extraction.
- Medallion architecture design.
- Source-to-target mapping.
- SQL migration.
- Incremental load design.
- Data-quality test generation.
- Data reconciliation.
- Migration documentation.
- Code review.

Skills should be task-oriented and reusable. They should not unnecessarily repeat framework-wide rules or duplicate complete agent definitions.

---

## 9. Hooks and guardrails

Hooks should enforce procedural and safety checks where the Claude Code environment supports them.

### 9.1 Pre-execution checks

- Validate workflow inputs.
- Check prerequisites.
- Confirm configured target and environment.
- Check permissions and tool availability.
- Ensure relevant rules are loaded.
- Require approval for sensitive operations.

### 9.2 Post-execution checks

- Verify expected artifacts exist.
- Run applicable formatters, tests, and validators.
- Capture execution results.
- Update run status.
- Report errors and unresolved issues.

### 9.3 Safety boundaries

- Do not expose or commit secrets.
- Do not perform destructive operations without explicit approval.
- Do not write to production systems by default.
- Do not perform unapproved external writes.
- Do not treat agent-generated code as validated until checks are completed.
- Respect project permissions and integration boundaries.
- Surface any check that could not be executed.

Hooks should be practical and enforceable. Instructions that cannot be reliably enforced should be documented as policy rather than presented as a technical guarantee.

---

## 10. Workflow system

DB-Kit supports three workflow usage modes.

### 10.1 Registered workflow

A versioned, reusable workflow definition.

Example: `legacy_to_silver_migration`

A registered workflow should define:

- Workflow ID and version.
- Description.
- Inputs.
- Prerequisites.
- Steps.
- Agent and skill assignments.
- Context requirements.
- Tool requirements.
- Checkpoints.
- Approval gates.
- Validation requirements.
- Outputs.
- Failure and recovery behavior.

### 10.2 Dynamic workflow

A workflow plan assembled for a user request based on context and available capabilities.

Process:

1. Interpret the user request.
2. Retrieve relevant context.
3. Identify goals, prerequisites, constraints, and missing information.
4. Select registered steps, agents, skills, tools, and validators.
5. Construct a bounded plan.
6. Check plan validity and safety.
7. Present the plan for approval when required.
8. Execute.
9. Validate.
10. Report and update context.

Dynamic workflows should use registered capabilities where possible. They must not invent arbitrary tools or bypass policies. When the framework lacks a required capability, it should report the limitation.

### 10.3 Customized registered workflow

A user may request changes to a registered workflow for a specific run, such as skipping an already completed profiling step.

Customization must:

- Preserve the original workflow definition.
- Record run-specific modifications.
- Check dependencies and required validations.
- Reject unsafe or invalid overrides.
- Require approval when the change crosses an approval boundary.

---

## 11. Initial migration workflow

### Workflow ID

`legacy_to_bronze_silver_migration`

### Goal

Analyze a legacy data pipeline and prepare a migration into Bronze and Silver layers, including implementation artifacts and validation evidence.

### Stage 1 — Discovery

- Inventory relevant source assets.
- Identify source datasets and schemas.
- Analyze legacy jobs and transformations.
- Map dependencies and lineage.
- Extract business rules.
- Identify load patterns and scheduling.
- Identify data quality expectations.
- Collect evidence and report gaps.

**Output:** Discovery report and context updates.

### Stage 2 — Assessment

- Assess complexity.
- Identify dependency risks.
- Identify ambiguous or undocumented logic.
- Identify data volume and incremental processing considerations where known.
- Identify platform compatibility concerns.
- Recommend migration order.

**Output:** Assessment report, risk register, migration priority.

### Stage 3 — Migration blueprint

- Define source-to-Bronze mappings.
- Define Silver transformations.
- Define expected schemas and conventions.
- Define load and incremental strategies.
- Define quality and reconciliation requirements.
- Identify migration dependencies and checkpoints.
- Identify unresolved decisions.

**Output:** Migration blueprint for review.

### Stage 4 — Approval checkpoint

The user reviews and approves the migration blueprint before code generation or consequential writes.

Approval may be scoped to a plan/version. Changes to the plan that materially alter scope should trigger reapproval.

### Stage 5 — Artifact generation

- Generate ingestion or Bronze artifacts.
- Generate Silver transformations.
- Generate configuration and metadata.
- Generate validation scripts/tests.
- Generate supporting documentation.
- Follow project standards and approved plan.

**Output:** Proposed migration artifacts.

### Stage 6 — Validation

Perform applicable checks:

- Syntax and compilation checks.
- Schema checks.
- Transformation tests.
- Data-quality checks.
- Source-to-target reconciliation.
- Row-count comparison.
- Key/duplicate checks.
- Null and value checks.
- Business-rule checks.
- Incremental processing checks.
- Dependency checks.

Tests must be adapted to the source/target platforms and available access. Do not claim tests passed when they were not run.

**Output:** Validation report with pass/fail/blocked status and evidence.

### Stage 7 — Review

- Review generated artifacts.
- Review validation results.
- Identify unresolved risks and assumptions.
- Check conventions and scope.
- Prepare a final migration summary.

**Output:** Review findings and release-readiness summary.

### Stage 8 — Human release decision

Production deployment and other consequential actions remain outside the default V1 workflow. A user may separately authorize specific deployment or external-write actions if the environment and safeguards support them.

---

## 12. Workflow state and execution records

Each workflow run should maintain a state record.

Suggested states:

- `created`
- `context_loading`
- `discovery`
- `planning`
- `awaiting_approval`
- `executing`
- `validating`
- `reviewing`
- `completed`
- `failed`
- `blocked`
- `cancelled`

A run record should contain, where applicable:

- Run ID.
- Workflow ID and version.
- Project ID.
- User request.
- Input parameters.
- Plan.
- Context references.
- Step status.
- Agent invocation records.
- Artifact references.
- Validation evidence.
- Approval records.
- Error details.
- Timestamps.
- Completion summary.

The framework should avoid storing raw credentials or unnecessary sensitive data in records.

---

## 13. Observability

V1 observability is repository-based and lightweight.

### Minimum requirements

- Workflow run summary.
- Step-by-step execution status.
- Agent task and output references.
- Relevant tool activity.
- Artifacts generated or modified.
- Validation results.
- Approvals.
- Failure reasons.
- Final summary.

### Reporting

Every migration run should produce a readable report containing:

1. Request and scope.
2. Project/context references used.
3. Workflow plan.
4. Steps completed.
5. Artifacts created or modified.
6. Validation performed and results.
7. Evidence and limitations.
8. Assumptions and unresolved questions.
9. Risks and review findings.
10. Recommended next step.

---

## 14. Artifact conventions

Workflow artifacts should be organized by project and run when appropriate.

Example:

```text
artifacts/
  migration-plans/
    <project-id>/
      <run-id>/
        blueprint.md
        source-to-target-mapping.yaml
        risks.md
  generated-code/
    <project-id>/
      <run-id>/
        bronze/
        silver/
        config/
  validation/
    <project-id>/
      <run-id>/
        test-plan.md
        results.md
        evidence/
  reports/
    <project-id>/
      <run-id>/
        migration-report.md
```

Artifact paths and names may be adapted to the repository's conventions. Avoid duplicating sensitive raw source data into artifact folders.

---

## 15. Suggested repository structure

The following is a conceptual structure for DB-Kit V1. It must be adapted to the Claude Code version and its native configuration conventions.

```text
db-kit/
├── CLAUDE.md
├── README.md
├── config/
│   ├── project.yaml
│   ├── framework.yaml
│   └── integrations.yaml
├── rules/
│   ├── core/
│   ├── data-engineering/
│   ├── medallion/
│   ├── target-platform/
│   └── security/
├── agents/
│   ├── discovery.md
│   ├── migration-architect.md
│   ├── transformation.md
│   ├── validation.md
│   └── review.md
├── skills/
│   ├── project-discovery/
│   ├── repository-analysis/
│   ├── source-analysis/
│   ├── medallion-design/
│   ├── source-to-target-mapping/
│   ├── sql-migration/
│   ├── data-quality/
│   ├── reconciliation/
│   └── migration-review/
├── workflows/
│   ├── registry.yaml
│   ├── templates/
│   │   └── legacy-to-bronze-silver.yaml
│   └── dynamic/
├── context/
│   ├── graph/
│   ├── metadata/
│   ├── lineage/
│   ├── decisions/
│   └── project-profile/
├── hooks/
│   ├── pre-execution/
│   ├── post-execution/
│   └── validation/
├── integrations/
│   └── mcp/
├── observability/
│   └── run-records/
└── artifacts/
    ├── migration-plans/
    ├── generated-code/
    ├── validation/
    └── reports/
```

---

## 16. Configuration

### `project.yaml` — conceptual example

```yaml
project:
  id: example-project
  name: Example Data Migration
  description: Legacy pipeline migration to medallion architecture

platform:
  source:
    - type: specify-source-platform
  target:
    type: specify-target-platform

migration:
  scope:
    - bronze
    - silver
  production_writes_enabled: false

context:
  repository_paths:
    - .
  documentation_paths: []
  metadata_sources: []

policy:
  require_plan_approval: true
  require_artifact_review: true
  allow_destructive_operations: false
```

This example is illustrative. Actual fields, types, and integration settings should be defined and validated during implementation.

---

## 17. V1 acceptance criteria

DB-Kit V1 is considered ready for an initial pilot when:

### Onboarding

- [ ] A user can onboard a project with repository and configuration inputs.
- [ ] Available integrations are discovered or configured explicitly.
- [ ] A project inventory is generated.
- [ ] Facts, assumptions, and unknowns are clearly distinguished.
- [ ] Context is persisted in a structured format.

### Context

- [ ] The model represents datasets, pipelines, transformations, dependencies, layers, rules, and artifacts.
- [ ] Context retrieval returns relevant references rather than requiring a full context dump.
- [ ] Context updates are traceable.
- [ ] Unverified claims are not automatically treated as verified facts.

### Framework

- [ ] Core rules are defined.
- [ ] Project-specific rules can be added.
- [ ] Initial agents have explicit contracts.
- [ ] Initial skills are reusable and scoped.
- [ ] Hooks or checks enforce applicable safeguards.

### Workflow

- [ ] A registered workflow can be loaded and executed.
- [ ] A bounded dynamic workflow can be proposed.
- [ ] A registered workflow can be customized for a run without modifying its definition.
- [ ] Workflow state and failures are recorded.
- [ ] Approval checkpoints work as intended.

### Migration

- [ ] Discovery output identifies relevant source assets.
- [ ] Migration assessment and blueprint are produced.
- [ ] Bronze and Silver artifacts can be generated for a supported pilot.
- [ ] Validation artifacts are produced.
- [ ] Tests and checks are reported truthfully.
- [ ] A migration report is generated.

### Safety and observability

- [ ] Production writes are disabled by default.
- [ ] Sensitive and destructive operations are gated.
- [ ] Run records capture important execution details.
- [ ] Secrets are not committed or logged.
- [ ] A human can review artifacts and validation evidence before release.

---

## 18. Implementation roadmap

### Milestone 0 — Framework skeleton

- Create repository.
- Define framework entry instructions.
- Define configuration format.
- Establish artifact and logging conventions.
- Establish core rules.

### Milestone 1 — Project onboarding

- Build project inventory procedure.
- Define context schema.
- Implement context persistence.
- Produce onboarding report.
- Add initial metadata and repository analysis capabilities.

### Milestone 2 — Discovery

- Implement Discovery Agent.
- Add repository, SQL, schema, and pipeline discovery skills.
- Generate discovery and dependency reports.
- Distinguish evidence and assumptions.

### Milestone 3 — Medallion blueprint

- Implement Migration Architect Agent.
- Define source-to-Bronze and Bronze-to-Silver mappings.
- Generate migration blueprint.
- Add approval checkpoint.

### Milestone 4 — Transformation generation

- Implement Transformation Agent.
- Generate code and configuration for one selected target platform.
- Add standards and pre-execution checks.
- Store artifacts by workflow run.

### Milestone 5 — Validation

- Implement Validation Agent and deterministic validation scripts.
- Add schema, quality, and reconciliation checks.
- Generate validation report.
- Handle blocked or unavailable validation explicitly.

### Milestone 6 — Workflow registry and execution

- Define workflow schema.
- Register the first migration workflow.
- Add state and checkpoint handling.
- Support run-level workflow customization.
- Add limited dynamic planning.

### Milestone 7 — Review and observability

- Implement Review Agent.
- Add execution records.
- Generate final reports.
- Improve recovery and failure reporting.

### Milestone 8 — Pilot and expansion

- Run the framework on a small, representative migration.
- Evaluate quality, reliability, usability, cost, and context retrieval.
- Refine rules, agents, skills, and workflow.
- Expand toward Gold, other target platforms, and more workflow templates only after the pilot.

---

## 19. Pilot strategy

Select one representative legacy pipeline with:

- Known source datasets.
- A manageable number of transformations.
- Documented or discoverable business logic.
- A testable Bronze and Silver target.
- Non-production validation access.
- A clear owner who can review results.

Pilot evaluation should measure:

- Discovery completeness.
- Accuracy of dependency and mapping analysis.
- Quality of generated artifacts.
- Validation coverage.
- Number and severity of human corrections.
- Workflow reproducibility.
- Execution transparency.
- Time saved versus manual migration.
- Cost and token usage where measurable.

Do not use a successful single pilot as evidence that the framework supports every platform or migration pattern.

---

## 20. V1 definition of done

DB-Kit V1 is a repository-based Claude Code framework that can onboard a supported data project, construct a structured project context, discover a legacy pipeline, produce an approved Bronze/Silver migration blueprint, generate migration artifacts, run available validations, and deliver a traceable report.

The framework is extensible through rules, skills, subagents, hooks, integrations, and registered workflows. Dynamic workflow generation is bounded by the framework's registered capabilities and safety policies.

**The first objective is reliability and traceability for one supported migration path—not broad autonomy.**
