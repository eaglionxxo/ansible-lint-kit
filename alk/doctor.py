"""Environment diagnosis: is this machine ready to lint Ansible?"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_TOOLS = [
    ("ansible", "ansible-core", "pipx install --include-deps ansible-core"),
    ("ansible-lint", "ansible-lint", "pipx install ansible-lint"),
    ("yamllint", "yamllint", "pipx install yamllint"),
    ("git", "git", "sudo apt install -y git"),
]

RECOMMENDED_EXTENSIONS = {
    "redhat.ansible": "Ansible language support + inline ansible-lint",
    "redhat.vscode-yaml": "YAML schemas and validation",
    "ms-vscode-remote.remote-wsl": "Open the project inside WSL so linting runs on Linux",
}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def is_wsl(proc_version: str | None = None) -> bool:
    """True when running inside WSL (reads /proc/version unless given)."""
    if proc_version is None:
        try:
            proc_version = Path("/proc/version").read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False
    return "microsoft" in proc_version.lower()


def tool_version(cmd: str) -> str | None:
    """First line of `<cmd> --version`, or None if the tool is missing."""
    path = shutil.which(cmd)
    if not path:
        return None
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (out.stdout or out.stderr).strip()
    return text.splitlines()[0] if text else "installed"


def vscode_extensions() -> list[str] | None:
    """Installed VS Code extensions (lower-case ids), or None if `code` is unavailable."""
    code = shutil.which("code")
    if not code:
        return None
    try:
        out = subprocess.run([code, "--list-extensions"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return [line.strip().lower() for line in out.stdout.splitlines() if line.strip()]


def run_checks() -> list[Check]:
    checks: list[Check] = []

    linux = platform.system() == "Linux"
    checks.append(Check(
        "Linux / WSL",
        linux,
        ("WSL" if is_wsl() else "native Linux") if linux else f"{platform.system()} (Ansible needs Linux)",
        "" if linux else "Run install.ps1 from Windows to set up WSL, then run alk inside WSL.",
    ))

    py_ok = sys.version_info >= (3, 9)
    checks.append(Check("Python >= 3.9", py_ok, platform.python_version(),
                        "" if py_ok else "sudo apt install -y python3 python3-venv pipx"))

    for cmd, label, fix in REQUIRED_TOOLS:
        version = tool_version(cmd)
        checks.append(Check(label, version is not None, version or "not found", "" if version else fix))

    exts = vscode_extensions()
    if exts is None:
        checks.append(Check("VS Code CLI", False, "`code` not on PATH",
                            "Open VS Code once from WSL with `code .` (installs the server)."))
    else:
        for ext_id, why in RECOMMENDED_EXTENSIONS.items():
            ok = ext_id in exts
            checks.append(Check(f"VS Code: {ext_id}", ok, why, "" if ok else f"code --install-extension {ext_id}"))
    return checks


def print_report(checks: list[Check]) -> int:
    width = max(len(c.name) for c in checks)
    for c in checks:
        mark = "OK " if c.ok else "XX "
        print(f"  [{mark}] {c.name.ljust(width)}  {c.detail}")
        if not c.ok and c.fix:
            print(f"        -> {c.fix}")
    missing = sum(not c.ok for c in checks)
    print()
    print("All good: ready to lint." if not missing else f"{missing} item(s) to fix.")
    return 0 if not missing else 1
