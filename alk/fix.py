"""Apply `ansible-lint --fix` safely: on a new git branch, never on the current one."""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path


class FixError(RuntimeError):
    pass


def git(repo: Path, *args: str) -> str:
    res = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if res.returncode != 0:
        raise FixError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout


def repo_root(path: Path) -> Path:
    workdir = path if path.is_dir() else path.parent
    try:
        return Path(git(workdir, "rev-parse", "--show-toplevel").strip())
    except FixError:
        raise FixError(f"{path} is not inside a git repository: `git init` and commit first, "
                       "so fixes can go on a separate branch.") from None


def has_changes(repo: Path) -> bool:
    """Tracked-file changes only: untracked files (reports, scratch) never block a fix."""
    return bool(git(repo, "status", "--porcelain", "--untracked-files=no").strip())


def current_branch(repo: Path) -> str:
    return git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()


def branch_name(now: datetime | None = None) -> str:
    return "alk/fix-" + (now or datetime.now()).strftime("%Y%m%d-%H%M%S")


def run_ansible_lint_fix(target: Path) -> None:
    if not shutil.which("ansible-lint"):
        raise FixError("ansible-lint not installed (run `alk doctor`).")
    workdir = target if target.is_dir() else target.parent
    args = ["ansible-lint", "--fix=all", "--nocolor"]
    if not target.is_dir():
        args.append(str(target))
    # Non-zero exit is normal when unfixable issues remain.
    subprocess.run(args, cwd=workdir, capture_output=True, text=True)


def commit_all(repo: Path, message: str, extra_files: list[Path] = ()) -> bool:
    """Stage modified tracked files (+ extra new files) and commit. False if nothing changed."""
    git(repo, "add", "-u")
    for f in extra_files:
        git(repo, "add", str(f))
    if not git(repo, "diff", "--cached", "--name-only").strip():
        return False
    git(repo, "commit", "-m", message)
    return True


def fix(target: Path) -> str:
    """Create a fix branch, run ansible-lint --fix, commit. Returns the branch name."""
    target = target.resolve()
    repo = repo_root(target)
    if has_changes(repo):
        raise FixError("Working tree has uncommitted changes. Commit or stash them first.")

    original = current_branch(repo)
    branch = branch_name()
    git(repo, "switch", "-c", branch)
    try:
        run_ansible_lint_fix(target)
        changed = commit_all(repo, "alk: apply ansible-lint automatic fixes")
    finally:
        git(repo, "reset", "--hard", "-q")
        git(repo, "switch", original)
    if not changed:
        git(repo, "branch", "-D", branch)
        raise FixError("Nothing to fix automatically.")
    print(git(repo, "diff", "--stat", f"{original}...{branch}"))
    return branch
