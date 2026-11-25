# Skill 09 — Create Pull Request from VS Code (Azure Repos)

Automated Azure DevOps Pull Request creation for Tiger Data Engineering workflows.

## Quick Start

```bash
# Auto-generate everything from current branch
python .github/skills/create-pull-request/scripts/create_pr.py

# Specify base branch + reviewers + ADO work items
python .github/skills/create-pull-request/scripts/create_pr.py \
  --base main \
  --reviewers "alice@tigeranalytics.com,bob@tigeranalytics.com" \
  --work-items "12345,67890"

# Draft PR with auto-complete and source branch deletion
python .github/skills/create-pull-request/scripts/create_pr.py \
  --title "feat: add reconciliation rules for PBNA" \
  --auto-complete \
  --delete-source

# Dry run (print command, do not execute)
python .github/skills/create-pull-request/scripts/create_pr.py --dry-run
```

## Prerequisites

### Option A — Azure CLI (recommended)
1. Install Azure CLI: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli
2. Install azure-devops extension: `az extension add --name azure-devops`
3. Authenticate: `az login`

### Option B — REST API fallback
Set the `AZURE_DEVOPS_EXT_PAT` environment variable to your Azure DevOps Personal Access Token.

```powershell
$env:AZURE_DEVOPS_EXT_PAT = "your-pat-here"
```

## File Structure

```
.github/skills/create-pull-request/
├── SKILL.md                   ← Full skill instructions
├── README.md                  ← This file
├── assets/
│   └── pr_template.md         ← PR body template
└── scripts/
    └── create_pr.py           ← Main automation script
```

## Output

```
Output/PR_Creation/
├── pr_description_<branch>.md      ← Generated PR body
└── pr_creation_log_<timestamp>.json
```
