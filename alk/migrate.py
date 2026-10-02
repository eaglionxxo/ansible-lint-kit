"""Ansible 2.9 -> modern ansible-core migration: detect legacy syntax, fix what is safe,
and work out which collections the content now needs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .discover import find_requirements, in_role, iter_yaml_files, is_playbook, only_play_includes

# Modules that left ansible core in 2.10 (short name -> collection). Only unambiguous names.
MODULE_COLLECTIONS = {
    "ansible.posix": ["acl", "authorized_key", "firewalld", "mount", "seboolean", "selinux", "synchronize", "sysctl"],
    "community.general": ["ufw", "timezone", "npm", "homebrew", "modprobe", "nmcli", "parted", "lvg", "lvol",
                          "filesystem", "alternatives", "locale_gen", "pam_limits", "ini_file", "archive", "snap",
                          "flatpak", "zypper", "pacman", "apk", "supervisorctl", "sefcontext", "pipx"],
    "community.docker": ["docker_container", "docker_image", "docker_network", "docker_volume", "docker_compose",
                         "docker_login"],
    "community.mysql": ["mysql_db", "mysql_user", "mysql_query", "mysql_variables"],
    "community.postgresql": ["postgresql_db", "postgresql_user", "postgresql_query", "postgresql_privs",
                             "postgresql_ext"],
    "community.crypto": ["openssl_privatekey", "openssl_csr", "openssl_certificate", "x509_certificate",
                         "openssh_keypair"],
    "ansible.windows": ["win_service", "win_copy", "win_file", "win_shell", "win_command", "win_feature",
                        "win_package", "win_updates", "win_reboot", "win_template", "win_user"],
    "community.windows": ["win_firewall_rule", "win_scheduled_task"],
    "kubernetes.core": ["k8s", "k8s_info", "helm"],
    "amazon.aws": ["ec2_instance", "s3_bucket", "ec2_vpc_net"],
}
SHORT_TO_COLLECTION = {mod: coll for coll, mods in MODULE_COLLECTIONS.items() for mod in mods}

_KEY = re.compile(r"^(\s*-\s+|\s+)([a-z_][a-z0-9_]*)\s*:")
_FQCN_KEY = re.compile(r"^(?:\s*-\s+|\s+)([a-z0-9_]+\.[a-z0-9_]+)\.[a-z0-9_]+\s*:")
_INCLUDE = re.compile(r"^(\s*-\s+|\s+)include(\s*:)")
_SUDO = re.compile(r"^(\s*-\s+|\s+)sudo(_user)?(\s*:)")
_WITH = re.compile(r"^\s*-?\s*(with_[a-z_]+)\s*:")
_ALWAYS_RUN = re.compile(r"^\s*-?\s*always_run\s*:")
_TEST_FILTER = re.compile(r"\s*\|\s*(failed|succeeded|success|changed|skipped)\b")
_ITERITEMS = re.compile(r"\.iteritems\(\)")


@dataclass
class Issue:
    path: str
    line: int
    kind: str
    message: str
    autofix: bool


@dataclass
class MigrationReport:
    issues: list[Issue] = field(default_factory=list)
    collections: set[str] = field(default_factory=set)

    @property
    def manual(self) -> list[Issue]:
        return [i for i in self.issues if not i.autofix]


def fix_text(text: str, playbook: bool) -> tuple[str, list[tuple[int, str]]]:
    """Apply safe legacy-syntax fixes. Returns new text and (line, description) changes."""
    out, changes = [], []
    for n, line in enumerate(text.splitlines(keepends=True), 1):
        new = line
        m = _INCLUDE.match(new)
        if m:
            target = "ansible.builtin.import_playbook" if playbook and m.group(1).startswith("-") and not line[0].isspace() \
                else "ansible.builtin.include_tasks"
            new = _INCLUDE.sub(lambda mm: f"{mm.group(1)}{target}{mm.group(2)}", new, count=1)
            changes.append((n, f"include -> {target}"))
        m = _SUDO.match(new)
        if m:
            key = "become_user" if m.group(2) else "become"
            new = _SUDO.sub(lambda mm: f"{mm.group(1)}{key}{mm.group(3)}", new, count=1)
            changes.append((n, f"sudo{m.group(2) or ''} -> {key}"))
        if _TEST_FILTER.search(new) and ("when" in new or "until" in new or "{{" in new):
            new = _TEST_FILTER.sub(lambda mm: f" is {mm.group(1)}", new)
            changes.append((n, "'|failed'-style filter -> 'is failed' test"))
        if _ITERITEMS.search(new):
            new = _ITERITEMS.sub(".items()", new)
            changes.append((n, ".iteritems() -> .items() (Python 3)"))
        out.append(new)
    return "".join(out), changes


def scan_text(text: str, rel: str, playbook: bool, report: MigrationReport) -> None:
    _, changes = fix_text(text, playbook)
    for n, desc in changes:
        report.issues.append(Issue(rel, n, "legacy-syntax", desc, True))
    for n, line in enumerate(text.splitlines(), 1):
        m = _WITH.match(line)
        if m:
            report.issues.append(Issue(rel, n, "with-loop",
                                       f"{m.group(1)} still works but 'loop:' is preferred; convert when you touch this task",
                                       False))
        if _ALWAYS_RUN.match(line):
            report.issues.append(Issue(rel, n, "always_run", "always_run was removed: use 'check_mode: false'", False))
        m = _KEY.match(line)
        # A module call has either a nested argument block (nothing after ':') or key=value args;
        # a plain scalar (timezone: Europe/Paris) is a variable, not a module.
        value = line[m.end():].strip() if m else ""
        if m and m.group(2) in SHORT_TO_COLLECTION and (not value or value.startswith("#") or "=" in value):
            coll = SHORT_TO_COLLECTION[m.group(2)]
            report.collections.add(coll)
            report.issues.append(Issue(rel, n, "module-moved",
                                       f"module '{m.group(2)}' now lives in {coll} (added to requirements; FQCN fixed by ansible-lint)",
                                       True))
        m = _FQCN_KEY.match(line)
        if m and m.group(1) != "ansible.builtin":
            report.collections.add(m.group(1))


def _is_playbook_file(path: Path, base: Path, text: str) -> bool:
    return is_playbook(text) or (not in_role(path, base) and only_play_includes(text))


def scan(root: Path) -> MigrationReport:
    root = root.resolve()
    base = root if root.is_dir() else root.parent
    report = MigrationReport()
    for path in iter_yaml_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        scan_text(text, str(path.relative_to(base)), _is_playbook_file(path, base, text), report)
    return report


def apply(root: Path) -> list[Path]:
    """Rewrite files in place with fix_text(). Returns changed files."""
    root = root.resolve()
    base = root if root.is_dir() else root.parent
    changed = []
    for path in iter_yaml_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new, changes = fix_text(text, _is_playbook_file(path, base, text))
        if changes and new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(path)
    return changed


def _listed_collections(data) -> set[str]:
    names = set()
    items = data.get("collections", []) if isinstance(data, dict) else []
    for item in items or []:
        if isinstance(item, str):
            names.add(item.split(":")[0].strip())
        elif isinstance(item, dict) and item.get("name"):
            names.add(str(item["name"]).strip())
    return names


def update_requirements(root: Path, needed: set[str]) -> tuple[Path | None, list[str], str]:
    """Make sure `needed` collections are listed in a requirements file.

    Returns (file written or None, collections added, human-readable note).
    """
    if not needed:
        return None, [], "no extra collections needed"
    root = root.resolve()
    base = root if root.is_dir() else root.parent
    existing = find_requirements(base)
    coll_files = [p for p in existing if p.name.startswith("requirements") and "roles" not in p.parts[-2:-1]]
    if not coll_files:
        target = base / "requirements.yml"
        lines = ["---", "collections:"] + [f"  - name: {c}" for c in sorted(needed)]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return target, sorted(needed), f"created {target.name}"

    target = coll_files[0]
    text = target.read_text(encoding="utf-8")
    try:
        import yaml  # provided by ansible-core
        data = yaml.safe_load(text) or {}
    except Exception:  # noqa: BLE001 - PyYAML missing or invalid file
        return None, [], f"could not parse {target.name}: add {', '.join(sorted(needed))} under 'collections:' by hand"
    missing = sorted(needed - _listed_collections(data))
    if not missing:
        return None, [], f"{target.name} already lists the needed collections"
    if re.search(r"^collections\s*:\s*$", text, re.M) and not re.search(r"^collections\s*:\s*\[", text, re.M):
        # Append right after the 'collections:' line, keeping the user's comments and layout.
        indent = "  "
        m = re.search(r"^collections\s*:\s*\n((?:[ \t]*#.*\n)*)([ \t]+)-", text, re.M)
        if m:
            indent = m.group(2)
        new_lines = "".join(f"{indent}- name: {c}\n" for c in missing)
        text = re.sub(r"^(collections\s*:\s*\n)", lambda mm: mm.group(1) + new_lines, text, count=1, flags=re.M)
    elif "collections" not in data:
        text = text.rstrip("\n") + "\ncollections:\n" + "".join(f"  - name: {c}\n" for c in missing)
    else:
        return None, [], f"{target.name} uses an unusual layout: add {', '.join(missing)} under 'collections:' by hand"
    target.write_text(text, encoding="utf-8")
    return target, missing, f"added {', '.join(missing)} to {target.name}"


def print_report(report: MigrationReport) -> int:
    if not report.issues:
        print("No legacy (Ansible 2.9) syntax found.")
    for i in sorted(report.issues, key=lambda x: (x.path, x.line)):
        tag = "AUTO " if i.autofix else "HUMAN"
        print(f"  [{tag}] {i.path}:{i.line}  {i.message}")
    if report.collections:
        print(f"\nCollections needed: {', '.join(sorted(report.collections))}")
    print("\nRun `alk check --fix` to apply the automatic fixes on a separate git branch.")
    return 1 if report.issues else 0
