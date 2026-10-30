#!/usr/bin/env python3
"""Release automation for ansible-lint-kit.

Determines the next SemVer version from conventional commits since the last
tag, updates CHANGELOG.md, and bumps the version in pyproject.toml and
alk/__init__.py (kept in sync).

Bump rules (conventional commits):
  feat: ...            -> MINOR (new feature, backwards compatible)
  fix:, perf:, ...     -> PATCH (bug fixes and compatible changes)
  BREAKING CHANGE / !  -> MAJOR (incompatible change)

If no conventional commit is found the bump is ambiguous: the tool refuses
to guess and asks for an explicit --version instead of publishing blindly.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"
INIT = REPO / "alk" / "__init__.py"
CHANGELOG = REPO / "CHANGELOG.md"

HEADER = """# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

"""

SECTION_ORDER = ["Added", "Changed", "Fixed", "Security", "Deprecated", "Removed"]

CONVENTIONAL = re.compile(r"^(?P<type>[a-z]+)(?P<bang>!)?:\s*(?P<subject>.+)$", re.IGNORECASE)
VERSION_RE = re.compile(r'^version\s*=\s*"(?P<v>[^"]+)"', re.MULTILINE)
INIT_VERSION_RE = re.compile(r'^__version__\s*=\s*"(?P<v>[^"]+)"', re.MULTILINE)

TYPE_TO_BUMP = {"feat": "minor"}
TYPE_TO_SECTION = {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Changed",
    "refactor": "Changed",
    "docs": "Changed",
    "test": "Changed",
    "chore": "Changed",
    "ci": "Changed",
    "build": "Changed",
}

BUMP_RANK = {"patch": 0, "minor": 1, "major": 2}


class ReleaseError(Exception):
    """A release step refused to proceed."""


def git(*args: str) -> str:
    res = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    if res.returncode != 0:
        raise ReleaseError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout


def last_tag() -> str | None:
    out = git("tag", "--list", "v*").split()
    if not out:
        return None
    # Sort by version, not lexicographically.
    def key(t: str) -> tuple[int, ...]:
        return tuple(int(p) for p in re.sub(r"^v", "", t).split(".") if p.isdigit())
    return sorted(out, key=key)[-1]


def commits_since(ref: str | None) -> list[tuple[str, str]]:
    """Return (subject, body) for commits after ref (exclusive)."""
    rev = f"{ref}..HEAD" if ref else "HEAD"
    out = git("log", rev, "--pretty=format:%s%x1f%b%x1e")
    commits = []
    for chunk in out.split("\x1e"):
        chunk = chunk.strip()
        if not chunk:
            continue
        subject, _, body = chunk.partition("\x1f")
        commits.append((subject.strip(), body.strip()))
    return commits


def classify(commits: list[tuple[str, str]]) -> tuple[str | None, list[tuple[str, str]]]:
    """Return (bump, entries). bump is None when nothing is classifiable."""
    bump: str | None = None
    entries: list[tuple[str, str]] = []
    for subject, body in commits:
        m = CONVENTIONAL.match(subject)
        if not m:
            continue
        ctype = m.group("type").lower()
        if ctype not in TYPE_TO_SECTION:
            continue  # unknown conventional type: ignored
        breaking = bool(m.group("bang")) or "BREAKING CHANGE" in body
        level = "major" if breaking else TYPE_TO_BUMP.get(ctype, "patch")
        if bump is None or BUMP_RANK[level] > BUMP_RANK[bump]:
            bump = level
        section = TYPE_TO_SECTION.get(ctype, "Changed")
        if "deprecat" in subject.lower():
            section = "Deprecated"
        if "secur" in subject.lower() and ctype == "fix":
            section = "Security"
        entries.append((section, m.group("subject").strip()))
    return bump, entries


def bump_version(version: str, level: str) -> str:
    parts = [int(p) for p in version.split(".")]
    if len(parts) != 3:
        raise ReleaseError(f"cannot bump non-SemVer version: {version!r}")
    major, minor, patch = parts
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ReleaseError(f"unknown bump level: {level!r}")


def read_version() -> str:
    m = VERSION_RE.search(PYPROJECT.read_text(encoding="utf-8"))
    if not m:
        raise ReleaseError("version not found in pyproject.toml")
    return m.group("v")


def set_version(new: str) -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    new_text, n = VERSION_RE.subn(f'version = "{new}"', text, count=1)
    if n != 1:
        raise ReleaseError("could not update version in pyproject.toml")
    PYPROJECT.write_text(new_text, encoding="utf-8")

    init = INIT.read_text(encoding="utf-8")
    new_init, n = INIT_VERSION_RE.subn(f'__version__ = "{new}"', init, count=1)
    if n != 1:
        raise ReleaseError("could not update __version__ in alk/__init__.py")
    INIT.write_text(new_init, encoding="utf-8")


def render_section(version: str, date: str, entries: list[tuple[str, str]]) -> str:
    lines = [f"## [{version}] - {date}", ""]
    for section in SECTION_ORDER:
        items = sorted({subject for sec, subject in entries if sec == section})
        if not items:
            continue
        lines.append(f"### {section}")
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def update_changelog(section: str, version: str) -> None:
    if CHANGELOG.exists():
        text = CHANGELOG.read_text(encoding="utf-8")
    else:
        text = HEADER
    if f"## [{version}]" in text:
        raise ReleaseError(f"CHANGELOG.md already contains version {version} (duplicate release?)")
    if not text.startswith(HEADER):
        text = HEADER + text.lstrip("\n")
    body = text[len(HEADER):]
    # Insert after the [Unreleased] block when present, else right after the header.
    unreleased = "## [Unreleased]"
    if body.startswith(unreleased):
        nxt = body.find("\n## [", len(unreleased))
        cut = len(body) if nxt == -1 else nxt + 1
        new_body = body[:cut].rstrip() + "\n\n" + section + "\n" + body[cut:].lstrip("\n")
    else:
        new_body = section + "\n" + body.lstrip("\n")
    CHANGELOG.write_text(HEADER + new_body, encoding="utf-8")


def plan(version_override: str | None = None) -> tuple[str, str, list[tuple[str, str]]]:
    """Return (new_version, section, entries). Raises ReleaseError when blocked."""
    ref = last_tag()
    commits = commits_since(ref)
    bump, entries = classify(commits)
    current = read_version()
    if version_override:
        if not re.fullmatch(r"\d+\.\d+\.\d+", version_override):
            raise ReleaseError(f"invalid --version: {version_override!r} (expected X.Y.Z)")
        new = version_override
        if new == current:
            raise ReleaseError(f"version {new} is already the current version (duplicate release?)")
    else:
        if bump is None:
            raise ReleaseError(
                "ambiguous: no conventional commit found since "
                f"{ref or 'the beginning'}; pass an explicit --version to release"
            )
        new = bump_version(current, bump)
    date = dt.date.today().isoformat()
    section = render_section(new, date, entries)
    return new, section, entries


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compute and apply the next release.")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, change nothing")
    ap.add_argument("--apply", action="store_true", help="write CHANGELOG.md and bump versions")
    ap.add_argument("--version", default=None, help="force version X.Y.Z (skips auto-detection)")
    args = ap.parse_args(argv)

    if not args.dry_run and not args.apply:
        ap.error("choose --dry-run or --apply")

    try:
        new, section, entries = plan(args.version)
    except ReleaseError as exc:
        print(f"release blocked: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"next version: {new}")
        print(f"entries: {len(entries)}")
        print()
        print(section)
        return 0

    update_changelog(section, new)
    set_version(new)
    print(f"released {new}: CHANGELOG.md updated, version bumped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
