# File Integrity Checker

A small defensive cybersecurity learning project: create a SHA-256 baseline
for local files, then detect added, changed, or missing files. Python 3.10+
is required. No third-party packages, network access, or elevated privileges
are needed.

## Try it in VS Code

Open this folder in VS Code. Install Microsoft's Python extension if needed
and select an interpreter using **Python: Select Interpreter**.
Open **Terminal > New Terminal** (PowerShell on Windows):

```powershell
New-Item -ItemType Directory -Path .\demo-files
Set-Content -Path .\demo-files\example.txt -Value "Original content"
python .\integrity_checker.py baseline --directory .\demo-files --output ..\baseline-demo.json
python .\integrity_checker.py check --directory .\demo-files --baseline ..\baseline-demo.json
Set-Content -Path .\demo-files\example.txt -Value "Changed content"
python .\integrity_checker.py check --directory .\demo-files --baseline ..\baseline-demo.json
$LASTEXITCODE
```

If `python` is unavailable but the Windows Python launcher is installed, use
`py -3` instead. Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | Baseline saved, or all files match |
| 1 | Changes detected |
| 2 | Invalid input, unreadable files, or another operational error |

Store the baseline **outside** the scanned directory. Its parent folder must
already exist. Creating a baseline replaces an existing baseline at that path.
File paths in the baseline are relative to the scanned folder and use `/`,
so a baseline can be compared against a copy on another computer.

The checker skips `.git` directories and symbolic links. Other files, including
hidden files, are scanned. File-read and directory-traversal errors fail the
operation rather than silently reporting success.

### Limitations

This detects content changes, not malware or the cause of a change. A matching
baseline does not prove files are safe. It does not check permissions, timestamps,
empty directories, or provide a filesystem snapshot: stop writes while scanning.
Keep a trusted baseline protected from modification. A baseline is not signed;
an attacker who can change both the files and baseline can defeat this check.
Do not commit sensitive files or real baselines: baseline paths can disclose
private filenames. Inspect staged changes before every public commit.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

GitHub Actions also runs the tests for pushes to `main` and `dev`, and pull
requests targeting either branch.

## GitHub, Git, and VS Code sign-in

These are related but separate:

- **Git author identity** (`git config user.name` / `git config user.email`)
  labels commits; it does not authenticate you.
- **Git Credential Manager** authenticates terminal pushes on Windows.
  A successful push confirms write access. Never paste a token into chat.
- **VS Code Accounts menu** (bottom-left profile icon) shows editor sign-in.
  Use **Sign in with GitHub** if needed, completing authentication yourself.
  The GitHub Pull Requests extension uses this to show and create PRs.
- **Browser sign-in** is separate again; use it to view the repository and PRs.

Public commit email metadata is visible to everyone. This repository uses a
GitHub noreply address. On your second computer, set a local noreply email too.

## Work on two computers

GitHub is the shared remote. Each computer has its own clone and credentials.
Branches are not separate machines or folders: switching branches changes the
files in your local working folder.

- `main`: stable, tested code.
- `dev`: ongoing development.
- Commit on `dev`, push, then open a pull request **from `dev` into `main`**.
  Review the diff and test results before merging.
- Finish, commit, and push on one computer before starting on the other.
  Uncommitted files and ignored files do not sync through GitHub.

### Computer 2: initial setup

Install Git, Python, and VS Code; authenticate GitHub separately on that machine.
In PowerShell, choose an existing parent folder:

```powershell
Set-Location E:\py-code
git clone https://github.com/copeland-cyber/file-integrity-checker.git
Set-Location .\file-integrity-checker
git config user.name "marshall copeland"
git config user.email "168665468+copeland-cyber@users.noreply.github.com"
git switch --track origin/dev
code .
```

The `E:\py-code` location is an example; choose a location that exists on
computer 2. Never copy `.git` or credentials between computers.

### On either computer: start work

First run `git status`. Commit or stash unfinished work before switching.

```powershell
git fetch origin
git switch dev
git pull --ff-only origin dev
```

Make changes and run tests. Then inspect and stage only intended files:

```powershell
python -m unittest discover -s tests -v
git status
git diff
git add .\integrity_checker.py .\tests\test_integrity_checker.py
git diff --cached
git commit -m "Describe the change"
git push origin dev
```

Adapt the `git add` paths to the files you actually changed. In VS Code you can
instead use **Source Control** to review diffs, stage files, commit, and push.
The branch name in the bottom-left status bar should say `dev` during development.
For learning, explicit fetch/pull/push commands make the direction clear;
VS Code's **Sync Changes** combines pull and push.

### Promote dev to main

On GitHub, open **Pull requests > New pull request** with base `main` and compare
`dev`. After checks pass, use **Create a merge commit** for this long-lived-branch
workflow. Keep the `dev` branch; do not delete it after merging.

Update the branches on your current computer:

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
git switch dev
git pull --ff-only origin dev
git merge origin/main
git push origin dev
```

This brings `dev` up to the merged `main` history. On the other computer,
fetch and pull again before editing.

### If Git refuses a pull or push

A `--ff-only` failure means your local and remote histories have diverged.
Do not force-push or reset away work. For already committed work on `dev`,
fetch and merge `origin/dev`, resolve conflicts in VS Code, run tests,
commit the merge if required, then push. If you have uncommitted work,
commit or stash it first. When both machines must work concurrently, use
separate feature branches and pull requests instead of editing the same `dev`.

## Recommended repository settings

The initial setup creates branches but does not automatically protect `main`.
In GitHub **Settings > Rules > Rulesets** (or **Branches**, depending on the UI),
protect `main`: require a pull request and passing Python tests, and block
force pushes/deletion. Avoid requiring another reviewer's approval if you are
the only contributor. Branch protection is a server-side setting, not a
property of a local branch.
