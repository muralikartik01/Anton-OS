# Core framework rules

- Workflows define execution structure and checkpoints; agents perform bounded tasks within them. No agent runs outside a workflow stage.
- Retrieve project context before executing a task; do not re-scan the full repository or re-derive facts already captured in context/MCP.
- Distinguish verified facts, inferred information, and unresolved assumptions in every output. Never state an assumption as a verified fact.
- Approval is required before any artifact generation that follows a migration blueprint, and before any write to a connection tagged production.
- Prefer deterministic checks (SQL engines, linters, schema diffs, tests) over subjective LLM judgment wherever one exists.
- Do not claim a source was inspected, a test was run, or a check passed when it was not.
- Reference rules and skills by name from agent contracts; do not duplicate their content inline.
