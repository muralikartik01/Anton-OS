"""
create_pr.py
------------
Tiger Data Engineering — Skill 09: Create Pull Request from VS Code
Optimised for Azure Repos (Azure DevOps).

Creates an Azure DevOps Pull Request for the current branch using:
  1. Azure CLI  (`az repos pr create`)  — primary method
  2. Azure DevOps REST API              — fallback when az CLI is unavailable

Usage:
    python .github/skills/create-pull-request/scripts/create_pr.py [OPTIONS]

Options:
    --base          Target / base branch (default: main)
    --title         PR title (auto-generated if omitted)
    --body          PR body as a string (mutually exclusive with --body-file)
    --body-file     Path to a Markdown file containing the PR body
    --reviewers     Comma-separated reviewer emails or ADO display names
    --work-items    Comma-separated ADO work-item IDs to link (e.g. 12345,67890)
    --draft         Open PR as a draft (flag, no value required)
    --auto-complete Enable auto-complete on the PR (flag, no value required)
    --delete-source Delete source branch after PR is merged (flag)
    --dry-run       Print the az command without executing it
    --output-dir    Directory to save output files (default: Output/PR_Creation)

Environment Variables:
    AZURE_DEVOPS_EXT_PAT    Personal Access Token for az CLI / REST API fallback
    AZURE_DEVOPS_ORG        Override the Azure DevOps organisation URL
                            (e.g. https://dev.azure.com/tigeranalytics)

Examples:
    # Minimal — auto-generate everything from current branch
    python .github/skills/create-pull-request/scripts/create_pr.py

    # Full control
    python .github/skills/create-pull-request/scripts/create_pr.py \\
        --base main \\
        --title "feat: add icedq reconciliation rules [ADO #12345]" \\
        --body-file Output/PR_Creation/pr_description.md \\
        --reviewers "alice@tigeranalytics.com,bob@tigeranalytics.com" \\
        --work-items "12345,67890" \\
        --auto-complete \\
        --delete-source

    # Dry run — print command without executing
    python .github/skills/create-pull-request/scripts/create_pr.py --dry-run
"""

import argparse
import base64
import ctypes
import getpass
import json
import os
import platform
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_BASE_BRANCH = "main"
DEFAULT_OUTPUT_DIR = "Output/PR_Creation"
ADO_API_VERSION = "7.1"

BRANCH_TITLE_PATTERNS = [
    (r"^feature/skill-(.+)$", "feat: add {0} skill"),
    (r"^feature/(.+)$", "feat: {0}"),
    (r"^fix/(.+)$", "fix: {0}"),
    (r"^bugfix/(.+)$", "fix: {0}"),
    (r"^hotfix/(.+)$", "hotfix: {0}"),
    (r"^refactor/(.+)$", "refactor: {0}"),
    (r"^chore/(.+)$", "chore: {0}"),
    (r"^docs/(.+)$", "docs: {0}"),
]

PR_BODY_TEMPLATE = """\
## Summary
{summary}

## Changes
{changes_section}

## Type of Change
- [ ] New Feature
- [ ] Bug Fix
- [ ] Refactoring / Code Quality
- [ ] Documentation
- [ ] Infrastructure / Config

## Testing
- [ ] Unit tests added / updated (`Output/UnitTesting/`)
- [ ] Code review completed (`Output/CodeReview/`)
- [ ] Tested in Dev environment

## Related Work Items
- ADO Story / Bug: #{ado_number}

## Checklist
- [ ] Follows Tiger coding standards (PEP 8, no `display()`/`show()`, Unity Catalog naming)
- [ ] No hardcoded values or secrets
- [ ] Audit Framework calls included (`log_audit_data`)
- [ ] Notebook header block complete (creator, date, ADO reference)
"""


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def get_current_branch() -> str:
    result = _run(["git", "branch", "--show-current"])
    return result.stdout.strip()


def get_remote_url() -> str:
    result = _run(["git", "remote", "get-url", "origin"], check=False)
    return result.stdout.strip()


def get_commits_ahead(base: str) -> list[str]:
    result = _run(["git", "log", f"origin/{base}..HEAD", "--oneline"], check=False)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_changed_files(base: str) -> list[str]:
    result = _run(["git", "diff", f"origin/{base}...HEAD", "--name-only"], check=False)
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def has_uncommitted_changes() -> bool:
    result = _run(["git", "status", "--porcelain"], check=False)
    return bool(result.stdout.strip())


def push_current_branch(branch: str) -> bool:
    result = _run(["git", "push", "--set-upstream", "origin", branch], check=False)
    return result.returncode == 0


def is_branch_pushed(branch: str) -> bool:
    result = _run(["git", "ls-remote", "--heads", "origin", branch], check=False)
    return bool(result.stdout.strip())


# ---------------------------------------------------------------------------
# Azure DevOps remote URL parsing
# ---------------------------------------------------------------------------

class AdoCoords:
    """Parsed Azure DevOps coordinates from a git remote URL."""

    def __init__(self, org_url: str, project: str, repo: str):
        self.org_url = org_url.rstrip("/")   # e.g. https://dev.azure.com/tigeranalytics
        self.project = project               # e.g. SNP
        self.repo = repo                     # e.g. cdo-mdip-snt-snp

    @property
    def org(self) -> str:
        """Short org name extracted from the URL."""
        return self.org_url.rstrip("/").split("/")[-1]

    def __str__(self) -> str:
        return f"{self.org_url}/{self.project}/_git/{self.repo}"


def parse_ado_remote(remote_url: str) -> Optional[AdoCoords]:
    """
    Parse an Azure DevOps git remote URL and return AdoCoords.

    Supported formats:
      HTTPS : https://dev.azure.com/{org}/{project}/_git/{repo}
      HTTPS : https://{org}.visualstudio.com/{project}/_git/{repo}
      SSH   : git@ssh.dev.azure.com:v3/{org}/{project}/{repo}
      SSH   : ssh://{org}@vs-ssh.visualstudio.com:22/{project}/_ssh/{repo}
    """
    # dev.azure.com HTTPS (with or without username@ prefix)
    # e.g. https://dev.azure.com/org/project/_git/repo
    #      https://username@dev.azure.com/org/project/_git/repo
    m = re.match(
        r"https://(?:[^@]+@)?dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+?)(?:\.git)?$",
        remote_url,
    )
    if m:
        org, project, repo = m.group(1), m.group(2), m.group(3)
        return AdoCoords(f"https://dev.azure.com/{org}", project, repo)

    # visualstudio.com HTTPS
    m = re.match(
        r"https://([^.]+)\.visualstudio\.com/([^/]+)/_git/([^/]+?)(?:\.git)?$",
        remote_url,
    )
    if m:
        org, project, repo = m.group(1), m.group(2), m.group(3)
        return AdoCoords(f"https://dev.azure.com/{org}", project, repo)

    # dev.azure.com SSH  git@ssh.dev.azure.com:v3/{org}/{project}/{repo}
    m = re.match(r"git@ssh\.dev\.azure\.com:v3/([^/]+)/([^/]+)/([^/]+?)(?:\.git)?$", remote_url)
    if m:
        org, project, repo = m.group(1), m.group(2), m.group(3)
        return AdoCoords(f"https://dev.azure.com/{org}", project, repo)

    # visualstudio.com SSH  ssh://{org}@vs-ssh.visualstudio.com:22/{project}/_ssh/{repo}
    m = re.match(
        r"ssh://([^@]+)@vs-ssh\.visualstudio\.com:\d+/([^/]+)/_ssh/([^/]+?)(?:\.git)?$",
        remote_url,
    )
    if m:
        org, project, repo = m.group(1), m.group(2), m.group(3)
        return AdoCoords(f"https://dev.azure.com/{org}", project, repo)

    return None


# ---------------------------------------------------------------------------
# Title / description generation
# ---------------------------------------------------------------------------

def generate_title(branch: str, commits: list[str]) -> str:
    for pattern, template in BRANCH_TITLE_PATTERNS:
        match = re.match(pattern, branch)
        if match:
            slug = match.group(1).replace("-", " ").replace("_", " ")
            title = template.format(slug)
            break
    else:
        title = branch.replace("-", " ").replace("_", " ").replace("/", ": ", 1)

    ado_match = re.search(r"#?(\d{4,6})", branch)
    if not ado_match and commits:
        ado_match = re.search(r"#(\d{4,6})", commits[0])
    if ado_match:
        title = f"{title} [ADO #{ado_match.group(1)}]"

    return title.strip()


def categorise_files(files: list[str]) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {
        "Notebooks / Code": [],
        "Configuration": [],
        "ADF Pipelines": [],
        "Skills / Copilot": [],
        "Unit Tests": [],
        "Infrastructure": [],
        "Other": [],
    }
    for f in files:
        if re.search(r"databricks/.*\.(py|ipynb)$", f, re.IGNORECASE):
            categories["Notebooks / Code"].append(f)
        elif re.search(r"(configuration/|audit_databricks/)", f):
            categories["Configuration"].append(f)
        elif f.startswith("adf/pipeline/"):
            categories["ADF Pipelines"].append(f)
        elif re.search(r"(\.github/skills/|Copilot/)", f):
            categories["Skills / Copilot"].append(f)
        elif re.search(r"(test|_test)", f, re.IGNORECASE):
            categories["Unit Tests"].append(f)
        elif re.search(r"(devops/|synapse/)", f):
            categories["Infrastructure"].append(f)
        else:
            categories["Other"].append(f)
    return {k: v for k, v in categories.items() if v}


def generate_body(branch: str, commits: list[str], files: list[str], work_items: list[int] | None = None) -> str:
    summary = commits[0].split(" ", 1)[-1] if commits else branch.replace("-", " ")

    categories = categorise_files(files)
    changes_lines: list[str] = []
    for category, file_list in categories.items():
        changes_lines.append(f"### {category}")
        for f in file_list:
            changes_lines.append(f"- `{f}`")
        changes_lines.append("")
    changes_section = "\n".join(changes_lines).strip() or "_No file changes detected_"

    # ADO number: prefer resolved work_items, then auto-detect from branch, else placeholder
    if work_items:
        ado_number = ", ".join(f"#{wi}" for wi in work_items)
    else:
        ado_match = re.search(r"#?(\d{4,6})", branch)
        ado_number = ado_match.group(1) if ado_match else "XXXX"

    return PR_BODY_TEMPLATE.format(
        summary=summary,
        changes_section=changes_section,
        ado_number=ado_number,
    )


def extract_ado_work_item_ids(branch: str, commits: list[str]) -> list[int]:
    """
    Extract ADO work item IDs from branch name and commit messages.

    Auto-detection order:
      1. Branch name with #  e.g. feature/#12345-my-change  ->  12345
      2. Branch name digits  e.g. feature/12345-my-change   ->  12345
      3. Commit messages     e.g. "fix: resolve bug #12345"  ->  12345
    """
    raw = branch + " " + " ".join(commits)
    return [int(n) for n in re.findall(r"#(\d{4,6})", raw)]


def prompt_for_work_items() -> list[int]:
    """
    Interactively ask the user for ADO Story / Bug IDs when none could be
    auto-detected from the branch name or commit messages.
    Returns an empty list if the user skips.
    """
    print("\n" + "-" * 60)
    print("  ADO Work Item — not auto-detected")
    print("-" * 60)
    print("""
No ADO Story or Bug ID was found in the branch name or commits.
To link this PR to an ADO work item, enter the ID(s) now.

Tips for automatic detection next time:
  - Include the ID in your branch name:  feature/12345-my-change
  - Include it in a commit message:       fix: resolve issue #12345
""")
    try:
        raw = input("  ADO Story/Bug ID(s) [comma-separated, or Enter to skip]: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return []

    if not raw:
        return []

    ids: list[int] = []
    for token in raw.replace("#", "").split(","):
        token = token.strip()
        if token.isdigit():
            ids.append(int(token))
        else:
            print(f"  WARNING: '{token}' is not a valid numeric ID — skipping.")
    return ids


# ---------------------------------------------------------------------------
# Azure CLI helpers
# ---------------------------------------------------------------------------

def az_available() -> bool:
    try:
        result = _run(["az", "--version"], check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def az_devops_configured() -> bool:
    """Check that az devops extension is installed."""
    try:
        result = _run(["az", "extension", "show", "--name", "azure-devops"], check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def az_pr_exists(coords: AdoCoords, base: str, branch: str) -> tuple[bool, str]:
    """Return (exists, pr_url) using az repos pr list."""
    result = _run(
        [
            "az", "repos", "pr", "list",
            "--organization", coords.org_url,
            "--project", coords.project,
            "--repository", coords.repo,
            "--source-branch", branch,
            "--target-branch", base,
            "--output", "json",
        ],
        check=False,
    )
    if result.returncode != 0:
        return False, ""
    try:
        data = json.loads(result.stdout)
        if data:
            pr_id = data[0].get("pullRequestId", "")
            url = (
                f"{coords.org_url}/{coords.project}/_git/{coords.repo}"
                f"/pullrequest/{pr_id}"
            )
            return True, url
    except (json.JSONDecodeError, IndexError):
        pass
    return False, ""


def create_pr_via_az(
    coords: AdoCoords,
    base: str,
    branch: str,
    title: str,
    body_file: str,
    reviewers: list[str],
    work_items: list[int],
    draft: bool,
    auto_complete: bool,
    delete_source: bool,
    dry_run: bool,
) -> str:
    """Create an Azure DevOps PR via az repos pr create. Returns PR URL."""
    cmd = [
        "az", "repos", "pr", "create",
        "--organization", coords.org_url,
        "--project", coords.project,
        "--repository", coords.repo,
        "--source-branch", branch,
        "--target-branch", base,
        "--title", title,
        "--description", f"@{body_file}",
        "--output", "json",
    ]
    for reviewer in reviewers:
        cmd += ["--reviewers", reviewer]
    for wi_id in work_items:
        cmd += ["--work-items", str(wi_id)]
    if draft:
        cmd += ["--draft", "true"]
    if auto_complete:
        cmd += ["--auto-complete", "true"]
    if delete_source:
        cmd += ["--delete-source-branch", "true"]

    print(f"\naz command:\n  {' '.join(cmd)}\n")

    if dry_run:
        print("[dry-run] Skipping actual PR creation.")
        return ""

    result = _run(cmd, check=False)
    if result.returncode != 0:
        print(f"ERROR: az repos pr create failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(result.stdout)
        pr_id = data.get("pullRequestId", "")
        return (
            f"{coords.org_url}/{coords.project}/_git/{coords.repo}/pullrequest/{pr_id}"
        )
    except (json.JSONDecodeError, KeyError):
        return result.stdout.strip()


# ---------------------------------------------------------------------------
# PAT setup wizard — first-time configuration
# ---------------------------------------------------------------------------

PAT_ENV_VAR = "AZURE_DEVOPS_EXT_PAT"
_PAT_CRED_TARGET = "git:https://dev.azure.com"
_NETRC_PATH = Path.home() / ".netrc"


def _store_pat_windows(pat: str) -> None:
    """Persist PAT in Windows Credential Manager (persists across reboots)."""
    # Structure mirrors CREDENTIALW in wincred.h
    class _CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.c_ulong),
            ("Type", ctypes.c_ulong),
            ("TargetName", ctypes.c_wchar_p),
            ("Comment", ctypes.c_wchar_p),
            ("LastWritten", ctypes.c_ulonglong),
            ("CredentialBlobSize", ctypes.c_ulong),
            ("CredentialBlob", ctypes.c_char_p),
            ("Persist", ctypes.c_ulong),
            ("AttributeCount", ctypes.c_ulong),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.c_wchar_p),
            ("UserName", ctypes.c_wchar_p),
        ]

    advapi32 = ctypes.windll.advapi32  # type: ignore[attr-defined]
    blob = pat.encode("utf-16-le")
    cred = _CREDENTIAL(
        Flags=0,
        Type=1,           # CRED_TYPE_GENERIC
        TargetName=_PAT_CRED_TARGET,
        Comment="Azure DevOps PAT — stored by create_pr.py",
        LastWritten=0,
        CredentialBlobSize=len(blob),
        CredentialBlob=blob,
        Persist=3,         # CRED_PERSIST_ENTERPRISE (survives reboot)
        AttributeCount=0,
        Attributes=None,
        TargetAlias=None,
        UserName="AZURE_DEVOPS_EXT_PAT",
    )
    ok = advapi32.CredWriteW(ctypes.byref(cred), 0)
    if not ok:
        raise RuntimeError(f"CredWriteW failed (error {ctypes.GetLastError()})")


def _read_pat_windows() -> str:
    """Read PAT from Windows Credential Manager. Returns empty string if not found."""
    try:
        advapi32 = ctypes.windll.advapi32  # type: ignore[attr-defined]
        ptr = ctypes.c_void_p()
        ok = advapi32.CredReadW(_PAT_CRED_TARGET, 1, 0, ctypes.byref(ptr))
        if not ok:
            return ""
        # CredentialBlobSize is at offset 20 bytes (after three c_ulong + c_wchar_p + c_wchar_p)
        # Use a simple approach: call CredFree and re-read via subprocess git credential
        advapi32.CredFree(ptr)
    except Exception:
        pass
    return ""


def _store_pat_netrc(org: str, pat: str) -> None:
    """Append a machine entry to ~/.netrc for non-Windows systems."""
    host = f"dev.azure.com"
    entry = f"\nmachine {host}\n  login {org}\n  password {pat}\n"
    with open(_NETRC_PATH, "a", encoding="utf-8") as fh:
        fh.write(entry)
    _NETRC_PATH.chmod(0o600)


def _store_pat_env_profile(pat: str) -> None:
    """
    Append export to ~/.bashrc and ~/.zshrc so the PAT is available in new shells.
    """
    line = f'\nexport {PAT_ENV_VAR}="{pat}"\n'
    for rc in (Path.home() / ".bashrc", Path.home() / ".zshrc"):
        if rc.exists():
            with open(rc, "a", encoding="utf-8") as fh:
                fh.write(line)
            print(f"  PAT appended to {rc}")


def _print_pat_creation_guide(org_url: str) -> None:
    org = org_url.rstrip("/").split("/")[-1]
    print("\n" + "=" * 60)
    print("  Azure DevOps PAT — First-Time Setup")
    print("=" * 60)
    print("""
No Azure DevOps Personal Access Token (PAT) was found.
Follow these steps to create one and store it securely:

  1. Open your browser and go to:
""")
    print(f"     {org_url}/_usersSettings/tokens")
    print(f"""
  2. Click  [ + New Token ]

  3. Fill in the form:
       Name        :  create_pr_vscode  (or any name you prefer)
       Organisation:  {org}
       Expiration  :  90 days  (recommended)
       Scopes      :  select  "Custom defined"  then tick:
                        Code  →  Read & write
                        Pull Request Threads  →  Read & write  (optional)

  4. Click  [ Create ]  and  COPY the token immediately
     (Azure DevOps will NOT show it again)

  5. Paste the token below when prompted — it will be stored
     securely so you won't need to enter it again.
""")
    print("=" * 60 + "\n")


def resolve_pat(coords: AdoCoords) -> str:
    """
    Return a valid PAT using this priority order:
      1. AZURE_DEVOPS_EXT_PAT environment variable (already set)
      2. Windows Credential Manager  (Windows only)
      3. Interactive wizard: guide the user to create a PAT, then store it
    """
    # 1 — environment variable
    pat = os.environ.get(PAT_ENV_VAR, "").strip()
    if pat:
        return pat

    # 2 — Windows Credential Manager read-back via git credential helper
    if platform.system() == "Windows":
        try:
            inp = (
                f"protocol=https\nhost=dev.azure.com\n"
                f"path={coords.org}/_git/{coords.repo}\n\n"
            )
            result = subprocess.run(
                ["git", "credential", "fill"],
                input=inp,
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                if line.startswith("password="):
                    stored = line.split("=", 1)[1].strip()
                    if stored:
                        print("  PAT found in git credential store.")
                        return stored
        except Exception:
            pass

    # 3 — Interactive first-time wizard
    _print_pat_creation_guide(coords.org_url)

    while True:
        try:
            pat = getpass.getpass("  Paste your PAT here (input hidden): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.", file=sys.stderr)
            sys.exit(1)

        if not pat:
            print("  PAT cannot be empty. Try again.")
            continue

        # Quick sanity-check: verify the PAT works against the ADO profile API
        print("  Verifying PAT...")
        test_url = f"https://dev.azure.com/{coords.org}/_apis/profile/profiles/me?api-version=7.1"
        try:
            _ado_api_request("GET", test_url, pat)
            print("  PAT verified successfully.")
        except SystemExit:
            print("  PAT verification failed. Please check the token and try again.")
            continue

        # Store the verified PAT
        if platform.system() == "Windows":
            try:
                _store_pat_windows(pat)
                print(f"  PAT stored in Windows Credential Manager (target: {_PAT_CRED_TARGET}).")
            except Exception as exc:
                print(f"  WARNING: Could not store in Credential Manager: {exc}")

            # Also store via git credential store so 'git credential fill' finds it
            try:
                inp = (
                    f"protocol=https\nhost=dev.azure.com\n"
                    f"path={coords.org}/_git/{coords.repo}\n"
                    f"username={coords.org}\npassword={pat}\n\n"
                )
                subprocess.run(
                    ["git", "credential", "approve"],
                    input=inp,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                print("  PAT also stored via git credential helper.")
            except Exception:
                pass

            print(f"\n  To set it permanently in your shell, run:")
            print(f'    $env:{PAT_ENV_VAR} = "{pat}"  # current session')
            print(f'    [System.Environment]::SetEnvironmentVariable("{PAT_ENV_VAR}", "{pat}", "User")')
            print("    (or add the above to your PowerShell $PROFILE)\n")
        else:
            _store_pat_env_profile(pat)
            _store_pat_netrc(coords.org, pat)
            print(
                f"  PAT stored in ~/.netrc and appended to shell RC files.\n"
                f"  Run: export {PAT_ENV_VAR}=\"<pat>\"  # for this session"
            )

        # Cache for this session
        os.environ[PAT_ENV_VAR] = pat
        return pat


# ---------------------------------------------------------------------------
# Azure DevOps REST API fallback
# ---------------------------------------------------------------------------

def _ado_api_request(
    method: str,
    url: str,
    pat: str,
    payload: Optional[dict] = None,
) -> dict:
    """Make an authenticated Azure DevOps REST API request."""
    token = base64.b64encode(f":{pat}".encode("utf-8")).decode("utf-8")
    body = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8")
        print(f"ERROR: ADO API {exc.code}  {url}\n{error_body}", file=sys.stderr)
        sys.exit(1)


def resolve_reviewer_ids(coords: AdoCoords, pat: str, reviewer_inputs: list[str]) -> list[dict]:
    """
    Resolve reviewer emails / display names to ADO identity descriptors.
    Falls back gracefully: if resolution fails, the reviewer is skipped with a warning.
    """
    if not reviewer_inputs:
        return []

    resolved: list[dict] = []
    for identity in reviewer_inputs:
        url = (
            f"https://vssps.dev.azure.com/{coords.org}/_apis/identities"
            f"?searchFilter=General&filterValue={urllib.parse.quote(identity)}"
            f"&queryMembership=None&api-version={ADO_API_VERSION}"
        )
        try:
            data = _ado_api_request("GET", url, pat)
            values = data.get("value", [])
            if values:
                resolved.append({"id": values[0]["id"]})
            else:
                print(f"WARNING: Reviewer '{identity}' not found — skipping.")
        except Exception:
            print(f"WARNING: Could not resolve reviewer '{identity}' — skipping.")

    return resolved


def create_pr_via_api(
    coords: AdoCoords,
    base: str,
    branch: str,
    title: str,
    body: str,
    reviewers: list[str],
    work_items: list[int],
    draft: bool,
) -> str:
    """Create an Azure DevOps PR using the REST API. Returns PR URL."""
    pat = resolve_pat(coords)

    reviewer_ids = resolve_reviewer_ids(coords, pat, reviewers)
    wi_refs = [{"id": wi_id, "url": ""} for wi_id in work_items]

    payload: dict = {
        "title": title,
        "description": body,
        "sourceRefName": f"refs/heads/{branch}",
        "targetRefName": f"refs/heads/{base}",
        "isDraft": draft,
        "reviewers": reviewer_ids,
        "workItemRefs": wi_refs,
    }

    url = (
        f"{coords.org_url}/{coords.project}/_apis/git/repositories/{coords.repo}"
        f"/pullrequests?api-version={ADO_API_VERSION}"
    )
    data = _ado_api_request("POST", url, pat, payload)
    pr_id = data.get("pullRequestId", "")
    return (
        f"{coords.org_url}/{coords.project}/_git/{coords.repo}/pullrequest/{pr_id}"
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def save_output(output_dir: str, branch: str, body: str, pr_url: str) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    safe_branch = re.sub(r"[^a-zA-Z0-9_\-]", "_", branch)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    body_path = Path(output_dir) / f"pr_description_{safe_branch}.md"
    body_path.write_text(body, encoding="utf-8")
    print(f"PR description saved: {body_path}")

    log_path = Path(output_dir) / f"pr_creation_log_{timestamp}.json"
    log_data = {
        "branch": branch,
        "pr_url": pr_url,
        "timestamp": timestamp,
        "description_file": str(body_path),
    }
    log_path.write_text(json.dumps(log_data, indent=2), encoding="utf-8")
    print(f"Creation log saved:   {log_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tiger DE Skill 09 — Create an Azure Repos Pull Request from VS Code"
    )
    parser.add_argument("--base", default=DEFAULT_BASE_BRANCH, help="Target base branch")
    parser.add_argument("--title", default="", help="PR title (auto-generated if blank)")
    parser.add_argument("--body", default="", help="PR body as a raw string")
    parser.add_argument("--body-file", default="", help="Path to Markdown file for PR body")
    parser.add_argument(
        "--reviewers", default="",
        help="Comma-separated reviewer emails or ADO display names",
    )
    parser.add_argument(
        "--work-items", default="",
        help="Comma-separated ADO work-item IDs to link (e.g. 12345,67890)",
    )
    parser.add_argument("--draft", action="store_true", help="Open as a draft PR")
    parser.add_argument("--auto-complete", action="store_true", help="Enable auto-complete")
    parser.add_argument(
        "--delete-source", action="store_true",
        help="Delete source branch after merge",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print command without executing")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("  Tiger DE — Skill 09: Create Azure Repos Pull Request")
    print("=" * 60)

    # --- Branch & remote validation ---
    branch = get_current_branch()
    if not branch:
        print("ERROR: Could not determine current branch.", file=sys.stderr)
        sys.exit(1)
    print(f"Branch      : {branch}")
    print(f"Base        : {args.base}")

    remote_url = get_remote_url()
    coords = parse_ado_remote(remote_url)
    if not coords:
        # Allow override via environment variable
        org_url = os.environ.get("AZURE_DEVOPS_ORG", "")
        if org_url:
            print(
                f"WARNING: Could not parse ADO remote from '{remote_url}'.\n"
                f"         Using AZURE_DEVOPS_ORG={org_url} — project/repo may need manual input."
            )
        else:
            print(
                f"ERROR: Remote URL '{remote_url}' does not look like an Azure DevOps repo.\n"
                "       Set AZURE_DEVOPS_ORG environment variable to override.",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Organisation: {coords.org_url}")
    print(f"Project     : {coords.project}")
    print(f"Repository  : {coords.repo}")

    if has_uncommitted_changes():
        print("\nWARNING: You have uncommitted changes. Commit or stash them before creating a PR.")

    # --- Ensure branch is pushed ---
    if not is_branch_pushed(branch):
        print(f"\nBranch '{branch}' is not on remote. Pushing now...")
        if not push_current_branch(branch):
            print("ERROR: Failed to push branch to origin.", file=sys.stderr)
            sys.exit(1)
        print("Branch pushed successfully.")

    # --- Gather diff data ---
    commits = get_commits_ahead(args.base)
    files = get_changed_files(args.base)
    print(f"Commits     : {len(commits)}")
    print(f"Files       : {len(files)}")

    # --- Generate title ---
    title = args.title or generate_title(branch, commits)
    print(f"Title       : {title}")

    # --- Resolve work items (CLI arg overrides auto-detected) ---
    if args.work_items:
        work_items = [int(w.strip()) for w in args.work_items.split(",") if w.strip().isdigit()]
    else:
        work_items = extract_ado_work_item_ids(branch, commits)
        if not work_items and not args.dry_run:
            work_items = prompt_for_work_items()

    if work_items:
        print(f"Work Items  : {work_items}")

    # --- Generate / load body ---
    if args.body_file and Path(args.body_file).exists():
        body = Path(args.body_file).read_text(encoding="utf-8")
    elif args.body:
        body = args.body
    else:
        body = generate_body(branch, commits, files, work_items)

    # --- Save description file ---
    safe_branch = re.sub(r"[^a-zA-Z0-9_\-]", "_", branch)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    body_file_path = str(Path(args.output_dir) / f"pr_description_{safe_branch}.md")
    Path(body_file_path).write_text(body, encoding="utf-8")

    reviewers = [r.strip() for r in args.reviewers.split(",") if r.strip()]

    # --- Check for existing PR (requires az CLI) ---
    if az_available() and az_devops_configured():
        exists, existing_url = az_pr_exists(coords, args.base, branch)
        if exists:
            print(f"\nA PR already exists for this branch:\n  {existing_url}")
            sys.exit(0)

        pr_url = create_pr_via_az(
            coords=coords,
            base=args.base,
            branch=branch,
            title=title,
            body_file=body_file_path,
            reviewers=reviewers,
            work_items=work_items,
            draft=args.draft,
            auto_complete=args.auto_complete,
            delete_source=args.delete_source,
            dry_run=args.dry_run,
        )
    else:
        print("\nAzure CLI / azure-devops extension not available — using REST API fallback.")
        pr_url = create_pr_via_api(
            coords=coords,
            base=args.base,
            branch=branch,
            title=title,
            body=body,
            reviewers=reviewers,
            work_items=work_items,
            draft=args.draft,
        )

    # --- Save output ---
    save_output(args.output_dir, branch, body, pr_url)

    if pr_url:
        print(f"\nPull Request created:\n  {pr_url}\n")
    print("Done.")


if __name__ == "__main__":
    main()
