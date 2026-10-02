"""Find Ansible content in a repository: YAML files, playbooks, requirements files."""

from __future__ import annotations

import re
from pathlib import Path

SKIP_DIRS = {".git", ".github", ".venv", "venv", "node_modules", "__pycache__", ".tox", ".cache", "collections"}
REQUIREMENTS_FILES = ["requirements.yml", "requirements.yaml", "collections/requirements.yml", "roles/requirements.yml"]

_PLAY_HOSTS = re.compile(r"^-\s+hosts\s*:|^\s{2,}hosts\s*:", re.M)
_IMPORT_PLAYBOOK = re.compile(r"^-\s+(ansible\.builtin\.)?import_playbook\s*:", re.M)
_TOP_ITEM = re.compile(r"^-\s", re.M)


def iter_yaml_files(root: Path):
    """All .yml/.yaml files under root, skipping VCS, CI and virtualenv folders."""
    root = root.resolve()
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        if path.suffix not in (".yml", ".yaml") or not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        yield path


def is_playbook(text: str) -> bool:
    """Heuristic: a top-level list whose items are plays (hosts:) or import_playbook entries."""
    if not _TOP_ITEM.search(text):
        return False
    return bool(_IMPORT_PLAYBOOK.search(text) or re.search(r"^-\s+hosts\s*:", text, re.M)
                or (re.search(r"^-\s+name\s*:", text, re.M) and re.search(r"^\s{2}hosts\s*:", text, re.M)))


_TOP_KEYS = re.compile(r"^-\s+([A-Za-z_.]+)\s*:", re.M)


def only_play_includes(text: str) -> bool:
    """A 2.9-style 'master playbook': every top-level item is `- include:` / `- import_playbook:`."""
    keys = _TOP_KEYS.findall(text)
    return bool(keys) and all(k in ("include", "import_playbook", "ansible.builtin.import_playbook") for k in keys)


def in_role(path: Path, root: Path) -> bool:
    parts = path.resolve().relative_to(root.resolve()).parts
    return "roles" in parts[:-1] or "tasks" in parts[:-1] or "handlers" in parts[:-1]


def find_playbooks(root: Path) -> list[Path]:
    root = root.resolve()
    base = root if root.is_dir() else root.parent
    found = []
    for path in iter_yaml_files(root):
        if in_role(path, base):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if is_playbook(text):
            found.append(path)
    return found


def find_requirements(root: Path) -> list[Path]:
    root = root.resolve()
    base = root if root.is_dir() else root.parent
    return [base / name for name in REQUIREMENTS_FILES if (base / name).is_file()]
