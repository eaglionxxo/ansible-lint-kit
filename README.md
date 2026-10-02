# ansible-lint-kit (`alk`)

Check a whole Ansible repository, fix everything that can be fixed automatically, migrate Ansible 2.9
content to modern ansible-core, and tell you exactly what still needs a human. Works from Windows,
with WSL and VS Code set up for you, and in GitHub Actions.

> 🇫🇷 Analyse tout un dépôt Ansible, corrige automatiquement ce qui peut l'être (sur une branche git
> séparée), migre le code Ansible 2.9 vers ansible-core moderne, installe les dépendances et liste,
> avec la solution, ce qui demande une intervention humaine. Installe aussi WSL + VS Code sous Windows.

## Why

- Ansible does not run natively on Windows: getting `ansible-lint` to work in VS Code means installing
  WSL, Python tooling and the right extensions. `install.ps1` does it.
- Upgrading from Ansible 2.9 breaks things: `include`, `sudo`, `result|failed`, modules that moved to
  collections. `alk check --fix` migrates what is safe and installs the collections now needed.
- Lint output is long and cryptic: `alk` splits it into "fixed automatically" and "needs a human",
  with a concrete fix for each rule.

## Install

Windows:

```powershell
git clone https://github.com/eaglionxxo/ansible-lint-kit.git
cd ansible-lint-kit
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer asks before each step: WSL + Ubuntu (elevated PowerShell + reboot, only if missing), then
inside WSL `python3`, `pipx`, `git`, `ansible-core`, `ansible-lint`, `yamllint`, `alk`, then the VS Code
extensions (Remote - WSL, Ansible, YAML), then `alk doctor`.

Linux / WSL directly: `pipx install "git+https://github.com/eaglionxxo/ansible-lint-kit.git"`.

## The main command: `alk check`

```bash
cd my-ansible-repo
alk check            # report only
alk check --fix      # + automatic fixes on a new branch alk/fix-<date>
```

What it does, in order:

1. **Dependencies**: `ansible-galaxy install -r` for `requirements.yml`, `collections/requirements.yml`,
   `roles/requirements.yml`.
2. **Ansible 2.9 migration scan**: `include` -> `include_tasks` / `import_playbook`, `sudo` -> `become`,
   `result|failed` -> `result is failed`, `.iteritems()` -> `.items()`, modules that moved to collections
   (`mount`, `sysctl` -> `ansible.posix`, `ufw` -> `community.general`, `docker_*` -> `community.docker`...).
   `with_*` loops and `always_run` are reported for a human.
3. **Lint**: ansible-lint (which also runs yamllint rules) on the whole repository.
4. **Syntax check**: `ansible-playbook --syntax-check` on every playbook.
5. With `--fix`, on a new git branch (your branch is never touched): apply the migration fixes, add the
   needed collections to `requirements.yml`, install them, run `ansible-lint --fix`, then lint and
   syntax-check again.
6. **Report** (`alk-report.md`): before/after counts, the fix branch, and every remaining finding grouped by
   rule with **how to fix it**.

Exit code is 0 only when nothing is left and every playbook passes the syntax check.

Review and keep the fixes:

```bash
git diff main...alk/fix-20261002-080000
git merge alk/fix-20261002-080000
```

## All commands

| Command | What it does |
|---|---|
| `alk doctor` | Checks Linux/WSL, Python, ansible-core, ansible-lint, yamllint, git, VS Code extensions |
| `alk check [path] [--fix] [--no-deps] [--report FILE]` | Whole-repo pass described above |
| `alk migrate [path]` | Ansible 2.9 migration scan only |
| `alk deps [path]` | Install collections and roles from requirements files |
| `alk lint [path]` | ansible-lint report sorted by severity |
| `alk fix [path]` | `ansible-lint --fix` only, on a new branch |
| `alk setup-vscode [path]` | Merge Ansible/WSL lint settings into `.vscode/` (keeps your values, writes a `.bak`) |
| `alk ci-setup [path] [--ansible-core 2.17]` | Add `.github/workflows/ansible-lint.yml` to your repo |

## GitHub Actions in your repository

```bash
alk ci-setup --ansible-core 2.17
git add .github/workflows/ansible-lint.yml && git commit -m "ci: ansible lint" && git push
```

Every push and pull request then installs the dependencies, runs `alk check --no-fix` and uploads
`alk-report.md` as an artifact. A pull request with a `alk check --fix` branch is therefore verified by CI
before you merge it.

## How this project is tested

GitHub Actions runs, on every push:

- unit tests (Python 3.10 and 3.12);
- an **end-to-end migration test** (`tests/e2e.sh`) with ansible-core 2.16 and 2.18: a real Ansible 2.9-style
  repo (`examples/legacy-2.9`) must fail the check, then `alk check --fix` must produce a branch where `sudo`,
  `include` and `|failed` are migrated, `ansible.posix` is added to `requirements.yml`, `main` is untouched,
  and `ansible-playbook --syntax-check` passes;
- yamllint on the workflows.

## Safety

- Fixes only ever happen on a new `alk/fix-*` branch; `alk` refuses to run on uncommitted changes.
- `requirements.yml` edits keep your comments; unusual layouts are reported instead of rewritten.
- `alk setup-vscode` never overwrites your values; files with comments are left alone.
- The installer never installs anything without asking (unless `-Yes`).

## Development

```bash
pip install -e ".[dev,tools]"
pytest
bash tests/e2e.sh
```

## License

MIT
