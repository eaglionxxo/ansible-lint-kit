"""Apply `ansible-lint --fix` safely: on a new git branch, never on the current one."""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path


class FixError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if res.returncode != 0:
        raise FixError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout


def branch_name(now: datetime | None = None) -> str:
    return "alk/fix-" + (now or datetime.now()).strftime("%Y%m%d-%H%M%S")


def fix(target: Path) -> str:
    """Create a fix branch, run ansible-lint --fix, commit. Returns the branch name."""
    if not shutil.which("ansible-lint"):
        raise FixError("ansible-lint not installed (run `alk doctor`).")
    target = target.resolve()
    workdir = target if target.is_dir() else target.parent
    repo = Path(_git(workdir, "rev-parse", "--show-toplevel").strip())
    if _git(repo, "status", "--porcelain").strip():
        raise FixError("Working tree has uncommitted changes. Commit or stash them first.")

    original = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    branch = branch_name()
    _git(repo, "switch", "-c", branch)

    args = ["ansible-lint", "--fix", "--nocolor"]
    if not target.is_dir():
        args.append(str(target))
    subprocess.run(args, cwd=workdir)  # non-zero exit is normal when unfixable issues remain

    if not _git(repo, "status", "--porcelain").strip():
        _git(repo, "switch", original)
        _git(repo, "branch", "-D", branch)
        raise FixError("Nothing to fix automatically.")

    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "alk: apply ansible-lint automatic fixes")
    print(_git(repo, "diff", "--stat", f"{original}...{branch}"))
    _git(repo, "switch", original)
    return branch
