"""`alk check`: whole-repository pass.

1. install dependencies (requirements.yml)
2. scan for Ansible 2.9 legacy syntax and collections that are now needed
3. lint (ansible-lint + yamllint) and syntax-check every playbook
4. with --fix: on a new git branch, apply migration fixes, add missing collections,
   reinstall dependencies, run ansible-lint --fix, then re-lint and re-check
5. report: what was fixed automatically, what still needs a human (with guidance)
"""

from __future__ import annotations

import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import deps, fix as fixmod, lint, migrate
from .discover import find_playbooks
from .hints import DOCS, hint_for


@dataclass
class SyntaxResult:
    playbook: str
    ok: bool
    error: str = ""


@dataclass
class CheckResult:
    root: Path
    deps: list = field(default_factory=list)
    migration: migrate.MigrationReport = field(default_factory=migrate.MigrationReport)
    before: list = field(default_factory=list)
    after: list | None = None
    syntax: list = field(default_factory=list)
    branch: str | None = None
    fix_notes: list = field(default_factory=list)

    @property
    def remaining(self) -> list:
        return self.before if self.after is None else self.after

    @property
    def ok(self) -> bool:
        return not self.remaining and all(s.ok for s in self.syntax)


def syntax_check(root: Path) -> list[SyntaxResult]:
    base = root if root.is_dir() else root.parent
    if not shutil.which("ansible-playbook"):
        return [SyntaxResult("-", False, "ansible-playbook not installed (run `alk doctor`)")]
    results = []
    for pb in find_playbooks(root):
        rel = str(pb.relative_to(base))
        res = subprocess.run(["ansible-playbook", "--syntax-check", "-i", "localhost,", rel],
                             cwd=base, capture_output=True, text=True)
        err = ""
        if res.returncode != 0:
            lines = [ln for ln in (res.stderr + res.stdout).splitlines() if ln.strip()]
            err = " ".join(ln for ln in lines if "ERROR" in ln)[:300] or " ".join(lines[-3:])[:300]
        results.append(SyntaxResult(rel, res.returncode == 0, err))
    return results


def run(root: Path, apply_fix: bool, install_deps: bool = True) -> CheckResult:
    root = root.resolve()
    result = CheckResult(root=root)
    if install_deps:
        result.deps = deps.install(root, quiet=True)
    result.migration = migrate.scan(root)
    result.before = lint.lint(root)
    if not apply_fix:
        result.syntax = syntax_check(root)
        return result

    repo = fixmod.repo_root(root)
    if fixmod.has_changes(repo):
        raise fixmod.FixError("Working tree has uncommitted changes. Commit or stash them first.")
    original = fixmod.current_branch(repo)
    branch = fixmod.branch_name()
    fixmod.git(repo, "switch", "-c", branch)
    try:
        changed = migrate.apply(root)
        if changed:
            result.fix_notes.append(f"migrated legacy syntax in {len(changed)} file(s)")
        req_file, added, note = migrate.update_requirements(root, result.migration.collections)
        result.fix_notes.append(note)
        if added and install_deps:
            result.deps = deps.install(root, quiet=True)
        fixmod.run_ansible_lint_fix(root)
        result.after = lint.lint(root)
        result.syntax = syntax_check(root)
        extra = [req_file] if req_file else []
        if fixmod.commit_all(repo, "alk: automatic lint fixes and Ansible migration", extra):
            result.branch = branch
    finally:
        fixmod.git(repo, "reset", "--hard", "-q")
        fixmod.git(repo, "switch", original)
    if not result.branch:
        fixmod.git(repo, "branch", "-D", branch)
    return result


def _group(findings) -> dict:
    groups = defaultdict(list)
    for f in findings:
        groups[(f.tool, f.rule)].append(f)
    return groups


def to_markdown(r: CheckResult) -> str:
    out = ["# alk check report", ""]
    remaining = r.remaining
    syntax_bad = [s for s in r.syntax if not s.ok]
    out.append(f"- Project: `{r.root}`")
    if r.after is None:
        out.append(f"- Findings: **{len(r.before)}** (no fixes applied: run `alk check --fix`)")
    else:
        out.append(f"- Findings: **{len(r.before)} before -> {len(r.after)} after** automatic fixes")
        out.append(f"- Fix branch: `{r.branch}` (review: `git diff ...{r.branch}`, keep: `git merge {r.branch}`)"
                   if r.branch else "- Fix branch: none (nothing could be fixed automatically)")
    out.append(f"- Playbook syntax check: {len(r.syntax) - len(syntax_bad)}/{len(r.syntax)} OK")
    out.append(f"- Result: **{'PASS' if r.ok else 'NEEDS WORK'}**")
    out.append("")

    if r.deps:
        out += ["## Dependencies", ""] + [f"- {'OK' if d.ok else 'FAILED'} `{d.file}` {d.detail}" for d in r.deps] + [""]
    if r.fix_notes:
        out += ["## Automatic changes", ""] + [f"- {n}" for n in r.fix_notes] + [""]

    mig = r.migration
    if mig.issues or mig.collections:
        out += ["## Ansible 2.9 migration", ""]
        if mig.collections:
            out.append(f"Collections required: {', '.join(f'`{c}`' for c in sorted(mig.collections))}")
            out.append("")
        for i in sorted(mig.issues, key=lambda x: (x.autofix, x.path, x.line)):
            out.append(f"- {'auto' if i.autofix else '**human**'} `{i.path}:{i.line}` {i.message}")
        out.append("")

    if syntax_bad:
        out += ["## Syntax errors (fix these first)", ""] + [f"- `{s.playbook}`: {s.error}" for s in syntax_bad] + [""]

    if remaining:
        out += ["## Needs human intervention", ""]
        groups = sorted(_group(remaining).items(), key=lambda kv: lint.sort_key(kv[1][0]))
        for (tool, rule), items in groups:
            base = rule.split("[", 1)[0]
            link = f" ([docs]({DOCS}{base}/))" if tool == "ansible-lint" else ""
            out.append(f"### `{rule}` ({tool}, {items[0].severity}) x{len(items)}{link}")
            out.append(f"**How to fix:** {hint_for(rule)}")
            for f in sorted(items, key=lambda x: (x.path, x.line))[:15]:
                out.append(f"- `{f.path}:{f.line}` {f.message}")
            if len(items) > 15:
                out.append(f"- ... and {len(items) - 15} more")
            out.append("")
    elif r.ok:
        out += ["Everything is clean.", ""]
    return "\n".join(out)


def print_summary(r: CheckResult) -> None:
    syntax_bad = [s for s in r.syntax if not s.ok]
    if r.after is None:
        print(f"Findings: {len(r.before)}")
    else:
        print(f"Findings: {len(r.before)} before -> {len(r.after)} after automatic fixes")
        print(f"Fix branch: {r.branch}" if r.branch else "Nothing could be fixed automatically.")
    for n in r.fix_notes:
        print(f"  - {n}")
    for d in r.deps:
        if not d.ok:
            print(f"  ! dependencies from {d.file} failed: {d.detail}")
    for s in syntax_bad:
        print(f"  ! syntax error in {s.playbook}: {s.error}")
    manual = len(r.remaining) + len(r.migration.manual)
    print(f"Needs human intervention: {manual} item(s)" if manual else "Nothing left for a human.")
    print("PASS" if r.ok else "NEEDS WORK")
