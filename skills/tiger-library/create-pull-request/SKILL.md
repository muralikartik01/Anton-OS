---
name: create-pull-request
---

# Skill 09 — Create Pull Request from VS Code

## Activation Keywords
`create pr`, `new pr`, `open pr`, `raise pr`, `submit pr`, `create pull request`, `new pull request`,
`open pull request`, `raise pull request`, `push and pr`, `pr from vscode`, `pr vscode`

## Purpose
Automates the full Pull Request lifecycle from within VS Code:
1. Inspects the current git branch and uncommitted/committed changes
2. Computes the diff against the target branch (default: `main`)
3. Generates a structured PR title and description from changed files and commit messages
4. Creates the PR on GitHub using the GitHub CLI (`gh`) or the GitHub REST API
5. Optionally assigns reviewers, labels, and a milestone

---

## Prerequisites

| Requirement | How to Verify |
|---|---|
| Azure CLI installed | `az --version` |
| azure-devops extension installed | `az extension show --name azure-devops` → install with `az extension add --name azure-devops` |
| Authenticated to Azure DevOps | `az login` or set `AZURE_DEVOPS_EXT_PAT` env variable |
| Current branch pushed to remote | `git status` (no "Your branch is ahead") |
| Clean / committed working tree | `git status` |

> If the Azure CLI is not installed, the skill falls back to the Azure DevOps REST API using a Personal Access Token stored in the environment variable `AZURE_DEVOPS_EXT_PAT`.

---

## Input Requirements

| Input | Source | Default |
|---|---|---|
| Target / base branch | User-supplied or auto-detected | `main` |
| PR title | Auto-generated from branch name + commits, or user-supplied | Auto |
| PR description | Auto-generated structured Markdown | Auto |
| Reviewers (emails / ADO display names) | User-supplied (optional) | None |
| Work Item IDs | User-supplied or auto-detected from branch/commits | None |
| Draft PR | User flag (optional) | `false` |
| Auto-complete | User flag (optional) | `false` |
| Delete source branch | User flag (optional) | `false` |

---

## Workflow

### Phase 1 — Branch & Remote Validation
1. Run `git branch --show-current` to confirm the active branch
2. Run `git remote get-url origin` to identify the Azure DevOps remote URL and parse `org / project / repo`
   - Supports `https://dev.azure.com/{org}/{project}/_git/{repo}` and `git@ssh.dev.azure.com:v3/{org}/{project}/{repo}`
3. Run `git status --porcelain` — warn if uncommitted changes exist
4. Run `git log origin/main..HEAD --oneline` to list commits on this branch

### Phase 2 — Change Analysis
1. Run `git diff origin/main...HEAD --stat` to get changed files summary
2. Run `git diff origin/main...HEAD --name-only` to categorise changes:
   - **Notebooks** (`.py`, `.ipynb` under `databricks/`)
   - **Configuration** (`configuration/`, `audit_databricks/`)
   - **ADF Pipelines** (`adf/pipeline/`)
   - **Skills / Copilot** (`.github/skills/`, `Copilot/`)
   - **Unit Tests** (`*test*`, `*_test*`)
   - **Infrastructure** (`devops/`, `synapse/`)
3. Detect primary change type for smart title generation

### Phase 3 — PR Description Generation
Auto-generate a PR description following this template:

```markdown
## Summary
<one-sentence description of what this PR does>

## Changes
### Notebooks / Code
- <list of changed notebooks with brief descriptions>

### Configuration
- <list of config changes>

### Other
- <any remaining changes>

## Type of Change
- [ ] New Feature
- [ ] Bug Fix
- [ ] Refactoring / Code Quality
- [ ] Documentation
- [ ] Infrastructure / Config

## Testing
- [ ] Unit tests added / updated (Output/UnitTesting/)
- [ ] Code review completed (Output/CodeReview/)
- [ ] Tested in Dev environment

## Related Work Items
- ADO Story / Bug: #<extracted from branch name or commit messages>

## Checklist
- [ ] Follows Tiger coding standards (PEP 8, no display()/show(), Unity Catalog naming)
- [ ] No hardcoded values or secrets
- [ ] Audit Framework calls included (`log_audit_data`)
- [ ] Notebook header block complete (creator, date, ADO reference)
```

### Phase 4 — PR Creation
Execute the Python script at `.github/skills/create-pull-request/scripts/create_pr.py`:

```bash
python .github/skills/create-pull-request/scripts/create_pr.py \
  --base main \
  --title "feat: <generated title>" \
  --body-file Output/PR_Creation/pr_description.md \
  --reviewers "alice@pepsico.com,bob@pepsico.com" \
  --work-items "12345" \
  --auto-complete \
  --delete-source
```

Or directly via Azure CLI:
```bash
az repos pr create \
  --organization https://dev.azure.com/pepsico \
  --project SNP \
  --repository cdo-mdip-snt-snp \
  --source-branch <branch> \
  --target-branch main \
  --title "<generated title>" \
  --description @Output/PR_Creation/pr_description.md \
  --reviewers "alice@pepsico.com" \
  --work-items 12345 \
  --auto-complete true \
  --delete-source-branch true
```

### Phase 5 — Output & Confirmation
- Save the generated PR description to `Output/PR_Creation/pr_description_<branch_name>.md`
- Print the PR URL returned by `gh` / GitHub API
- Display reviewer links and PR number

---

## Output Location
```
Output/
└── PR_Creation/
    ├── pr_description_<branch_name>.md     ← Generated PR body
    └── pr_creation_log_<timestamp>.json    ← Creation result (PR number, URL, status)
```

---

## Smart Title Generation Rules

| Branch Name Pattern | Generated Title |
|---|---|
| `feature/skill-*` | `feat: add <skill-name> skill` |
| `feature/*` | `feat: <branch-description>` |
| `fix/*` or `bugfix/*` | `fix: <branch-description>` |
| `hotfix/*` | `hotfix: <branch-description>` |
| `refactor/*` | `refactor: <branch-description>` |
| `chore/*` | `chore: <branch-description>` |
| Any branch with ADO # | Appends `[ADO #<number>]` suffix |

---

## Error Handling

| Condition | Action |
|---|---|
| Azure CLI not installed | Falls back to REST API using `AZURE_DEVOPS_EXT_PAT`; prints install instructions |
| `azure-devops` extension missing | Print `az extension add --name azure-devops` instructions |
| `AZURE_DEVOPS_EXT_PAT` not set | Error with clear instructions to set the PAT |
| Remote URL not an Azure DevOps URL | Error with suggestion to set `AZURE_DEVOPS_ORG` env variable |
| Branch not pushed to remote | Runs `git push --set-upstream origin <branch>` automatically |
| PR already exists for branch | Shows existing PR URL and exits |
| Uncommitted changes detected | Warns user, does not block execution |
| Reviewer email not resolvable | Logs a warning and skips that reviewer |

---

## Script Reference
`.github/skills/create-pull-request/scripts/create_pr.py`

## Assets
`.github/skills/create-pull-request/assets/pr_template.md`

# Make sure the description is not more than 4000 characters.