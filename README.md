# ansible-lint-kit (`alk`)

Lint and safely fix your Ansible playbooks from Windows, with WSL and VS Code set up for you.

> 🇫🇷 Outil pour diagnostiquer votre poste (WSL, Ansible, VS Code), analyser vos playbooks avec
> ansible-lint + yamllint et appliquer les corrections automatiques sur une branche git séparée.

## Why

Ansible does not run natively on Windows. Getting `ansible-lint` to work in VS Code means installing
WSL, a Linux distribution, Python tooling and the right extensions, then wiring them together.
`alk` does that, then gives you readable reports and safe auto-fixes.

## Install (Windows)

```powershell
git clone https://github.com/eaglionxxo/ansible-lint-kit.git
cd ansible-lint-kit
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer asks before each step:

1. WSL + Ubuntu (needs an elevated PowerShell and a reboot, only if WSL is missing)
2. Inside WSL: `python3`, `pipx`, `git`, `ansible-core`, `ansible-lint`, `yamllint`, `alk`
3. VS Code extensions: Remote - WSL, Ansible (Red Hat), YAML (Red Hat)
4. `alk doctor` to confirm

On Linux/WSL directly: `pipx install "git+https://github.com/eaglionxxo/ansible-lint-kit.git"`.

## Usage (inside WSL)

| Command | What it does |
|---|---|
| `alk doctor` | Checks Linux/WSL, Python, ansible-core, ansible-lint, yamllint, git, VS Code extensions, and tells you how to fix what is missing |
| `alk lint [path]` | Runs ansible-lint + yamllint, prints findings sorted by severity |
| `alk fix [path]` | Creates branch `alk/fix-<date>`, runs `ansible-lint --fix`, commits there, shows the diff. Your current branch is untouched |
| `alk setup-vscode [path]` | Merges Ansible/WSL linting settings into `.vscode/settings.json` and `extensions.json` (keeps your values, writes a `.bak`) |

Try it on the deliberately broken example:

```bash
alk lint examples/bad-playbook.yml
```

## Safety

- `alk fix` refuses to run on a dirty working tree and never commits to your current branch.
- `alk setup-vscode` never overwrites your existing values; files with comments are left alone and a
  suggestion file is written instead.
- The installer never installs anything without asking (unless `-Yes`).

## Development

```bash
pip install -e ".[dev,tools]"
pytest
```

## License

MIT
