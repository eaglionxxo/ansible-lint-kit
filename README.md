# ansible-lint-kit (`alk`)

Check a whole Ansible repository, fix everything that can be fixed automatically, migrate Ansible 2.9
content to modern ansible-core, and tell you exactly what still needs a human. Works from Windows,
with WSL and VS Code set up for you, and in GitHub Actions.

> 🇫🇷 Analyse tout un dépôt Ansible, corrige automatiquement ce qui peut l'être (sur une branche git
> séparée), migre le code Ansible 2.9 vers ansible-core moderne, installe les dépendances et liste,
> avec la solution, ce qui demande une intervention humaine. Installe aussi WSL + VS Code sous Windows.

## Project Status

[![CI](https://github.com/eaglionxxo/ansible-lint-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/eaglionxxo/ansible-lint-kit/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/eaglionxxo/ansible-lint-kit)](https://github.com/eaglionxxo/ansible-lint-kit/releases)
[![License: MIT](https://img.shields.io/github/license/eaglionxxo/ansible-lint-kit)](LICENSE)

## Technologies & Stack

![Python >=3.9](https://img.shields.io/badge/python-%3E%3D3.9-blue?logo=python&logoColor=white)
![Windows + WSL](https://img.shields.io/badge/platform-Windows_%2B_WSL-blue?logo=windows&logoColor=white)
![VS Code](https://img.shields.io/badge/VS_Code-setup--vscode-blue?logo=visualstudiocode&logoColor=white)

## Frameworks & Dependencies

| Technology | Used in this project | Latest stable (live) |
|---|---|---|
| [ansible-core](https://docs.ansible.com/ansible-core/) | ≥ 2.15 (CI: 2.16, 2.18) | [![PyPI](https://img.shields.io/pypi/v/ansible-core)](https://pypi.org/project/ansible-core/) |
| [ansible-lint](https://docs.ansible.com/projects/lint/) | ≥ 24.2 | [![PyPI](https://img.shields.io/pypi/v/ansible-lint)](https://pypi.org/project/ansible-lint/) |
| [yamllint](https://yamllint.readthedocs.io/) | ≥ 1.35 | [![PyPI](https://img.shields.io/pypi/v/yamllint)](https://pypi.org/project/yamllint/) |
| [pytest](https://docs.pytest.org/) | ≥ 8 (CI: Python 3.10, 3.12) | [![PyPI](https://img.shields.io/pypi/v/pytest)](https://pypi.org/project/pytest/) |
| [pytest-cov](https://pytest-cov.readthedocs.io/) | ≥ 5 | [![PyPI](https://img.shields.io/pypi/v/pytest-cov)](https://pypi.org/project/pytest-cov/) |
| [PyYAML](https://pyyaml.org/) | via ansible-core (used by `alk.migrate`) | [![PyPI](https://img.shields.io/pypi/v/pyyaml)](https://pypi.org/project/pyyaml/) |
| [pip-audit](https://github.com/pypa/pip-audit) | CI security gate | [![PyPI](https://img.shields.io/pypi/v/pip-audit)](https://pypi.org/project/pip-audit/) |

The "latest stable" badges are live: they always show the current PyPI release,
no README update needed. The "used" column reflects `pyproject.toml` and the CI matrix.

## DevOps & CI/CD

[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI-2088FF?logo=githubactions&logoColor=white)](https://github.com/eaglionxxo/ansible-lint-kit/actions)
[![Self-hosted runners](https://img.shields.io/badge/runners-self--hosted-success?logo=github&logoColor=white)](docs/CI-CD.md)
[![Release workflow](https://img.shields.io/badge/release-manual_SemVer-2088FF?logo=github&logoColor=white)](docs/CI-CD.md)

## Testing & Quality

![pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)
![coverage](https://img.shields.io/badge/coverage-xml_artifact_in_CI-0A9EDC)
![e2e](https://img.shields.io/badge/e2e-ansible--core_2.16_%7C_2.18-0A9EDC)

Coverage (`coverage.xml`) is uploaded as a CI artifact on every run — see the
[CI documentation](docs/CI-CD.md).

## Security

[![pip-audit](https://img.shields.io/badge/security-pip--audit-green?logo=python&logoColor=white)](https://github.com/eaglionxxo/ansible-lint-kit/actions/workflows/ci.yml)

Dependencies are audited for known vulnerabilities on every CI run
(`pip-audit --strict` fails the build if a vulnerability is found).

## Releases & Versions

Releases are published through the manual **Release** workflow: automatic SemVer
detection from conventional commits, generated changelog, `vX.Y.Z` tag, GitHub
Release with sdist/wheel artifacts. Details in [docs/CI-CD.md](docs/CI-CD.md).

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

- unit tests (Python 3.10 and 3.12) with coverage (`coverage.xml` uploaded as an artifact);
- an **end-to-end migration test** (`tests/e2e.sh`) with ansible-core 2.16 and 2.18: a real Ansible 2.9-style
  repo (`examples/legacy-2.9`) must fail the check, then `alk check --fix` must produce a branch where `sudo`,
  `include` and `|failed` are migrated, `ansible.posix` is added to `requirements.yml`, `main` is untouched,
  and `ansible-playbook --syntax-check` passes;
- yamllint on the workflows;
- a dependency security audit (`pip-audit --strict`).

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
