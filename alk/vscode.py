"""Configure a project's .vscode folder so the Ansible extension lints through WSL."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

SETTINGS = {
    "ansible.validation.enabled": True,
    "ansible.validation.lint.enabled": True,
    "ansible.validation.lint.path": "ansible-lint",
    "files.associations": {"*.yml": "ansible", "*.yaml": "ansible"},
    "yaml.validate": True,
}

EXTENSIONS = ["redhat.ansible", "redhat.vscode-yaml", "ms-vscode-remote.remote-wsl"]


def merge_settings(current: dict, wanted: dict) -> dict:
    """Add wanted keys without overwriting the user's existing values (dicts merged one level)."""
    merged = dict(current)
    for key, value in wanted.items():
        if key not in merged:
            merged[key] = value
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = {**value, **merged[key]}
    return merged


def merge_extensions(current: dict, wanted: list[str]) -> dict:
    recs = list(current.get("recommendations", []))
    for ext in wanted:
        if ext not in recs:
            recs.append(ext)
    return {**current, "recommendations": recs}


def _load(path: Path) -> dict | None:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None  # JSON with comments: leave the user's file alone


def setup(project: Path) -> list[str]:
    """Write/merge settings.json and extensions.json. Returns human-readable actions."""
    vs = project.resolve() / ".vscode"
    vs.mkdir(exist_ok=True)
    actions = []
    settings = dict(SETTINGS)
    py = shutil.which("python3")
    if py:
        settings["ansible.python.interpreterPath"] = py

    for name, wanted, merge in (("settings.json", settings, merge_settings),
                                ("extensions.json", EXTENSIONS, merge_extensions)):
        path = vs / name
        current = _load(path)
        if current is None:
            suggestion = path.with_suffix(".alk-suggested.json")
            suggestion.write_text(json.dumps(merge({}, wanted), indent=2) + "\n", encoding="utf-8")
            actions.append(f"{path} has comments; wrote suggestions to {suggestion.name} instead")
            continue
        if path.exists():
            backup = path.with_suffix(".json.bak")
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(json.dumps(merge(current, wanted), indent=2) + "\n", encoding="utf-8")
        actions.append(f"updated {path}" + (" (backup: .bak)" if current else ""))
    return actions
