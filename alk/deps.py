"""Install Ansible dependencies (collections and roles) declared in requirements files."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .discover import find_requirements


@dataclass
class DepResult:
    file: str
    ok: bool
    detail: str


def install(root: Path, quiet: bool = False) -> list[DepResult]:
    root = root.resolve()
    base = root if root.is_dir() else root.parent
    files = find_requirements(base)
    if not files:
        return []
    if not shutil.which("ansible-galaxy"):
        return [DepResult(str(f.relative_to(base)), False, "ansible-galaxy not installed (run `alk doctor`)") for f in files]
    results = []
    for f in files:
        rel = str(f.relative_to(base))
        if not quiet:
            print(f"  installing dependencies from {rel} ...")
        res = subprocess.run(["ansible-galaxy", "install", "-r", str(f)], cwd=base, capture_output=True, text=True)
        tail = (res.stdout + res.stderr).strip().splitlines()[-1:] or [""]
        results.append(DepResult(rel, res.returncode == 0, tail[0][:200]))
    return results


def print_report(results: list[DepResult]) -> int:
    if not results:
        print("No requirements.yml found: nothing to install.")
        return 0
    for r in results:
        print(f"  [{'OK ' if r.ok else 'XX '}] {r.file}  {r.detail}")
    return 0 if all(r.ok for r in results) else 1
