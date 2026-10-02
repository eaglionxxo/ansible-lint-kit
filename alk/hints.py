"""Human guidance for findings that cannot be fixed automatically."""

from __future__ import annotations

HINTS = {
    "name": "Give the task/play a short descriptive name starting with a capital letter (name: Install nginx).",
    "risky-file-permissions": "Set an explicit, quoted mode, e.g. mode: \"0644\" for files or \"0755\" for directories.",
    "no-changed-when": "command/shell always report 'changed': add changed_when: false, or a real condition "
                       "(changed_when: \"'created' in result.stdout\").",
    "command-instead-of-module": "Use the dedicated module instead of command/shell (e.g. ansible.builtin.git, "
                                 "ansible.builtin.service, ansible.builtin.get_url).",
    "command-instead-of-shell": "Use ansible.builtin.command unless you need pipes, redirects or env expansion.",
    "risky-shell-pipe": "Start the shell script with 'set -o pipefail &&' so a failing command in the pipe fails the task.",
    "package-latest": "Use state: present (or pin a version) so runs are reproducible; reserve 'latest' for upgrade playbooks.",
    "latest": "Pin a version (version: <tag or sha>) for git/hg checkouts.",
    "var-naming": "Rename the variable: lowercase snake_case, and prefix role variables with the role name.",
    "no-handler": "Move the 'when: x.changed' task into a handler and notify it from the task that changes things.",
    "ignore-errors": "Avoid ignore_errors: true; use failed_when with a precise condition, or 'block/rescue'.",
    "literal-compare": "Compare booleans directly: 'when: var' or 'when: not var' instead of '== true/false'.",
    "no-relative-paths": "Put files/templates in the role's files/ or templates/ folder and reference them by name.",
    "partial-become": "Set become: true together with become_user (same level).",
    "no-free-form": "Use YAML arguments (module:\\n  key: value) instead of key=value strings.",
    "jinja": "Fix the Jinja spacing/syntax reported, e.g. '{{ var }}' with one space inside the braces.",
    "role-name": "Role names must be lowercase snake_case: rename the role directory.",
    "schema": "The file does not match the Ansible schema: check the key names and indentation at that line.",
    "syntax-check": "ansible-playbook --syntax-check failed: fix the reported error first, other rules depend on it.",
    "load-failure": "The file could not be read (bad YAML, missing include, encoding): fix it first.",
    "internal-error": "ansible-lint crashed on this file: usually a missing collection or role. Run `alk deps`.",
    "parser-error": "YAML parse error: check indentation and quoting at that line.",
    "meta-no-info": "Fill galaxy_info (author, description, license, min_ansible_version, platforms) in meta/main.yml.",
    "meta-runtime": "Set requires_ansible in meta/runtime.yml to a supported version, e.g. '>=2.15.0'.",
    "galaxy": "Fix galaxy.yml: version must follow semver and a CHANGELOG is expected.",
    "deprecated-module": "This module was removed or deprecated: switch to its replacement (see the rule docs).",
    "fqcn": "Use the fully-qualified name (ansible.builtin.copy). If it is a collection module, install the collection "
            "(`alk deps`) and re-run `alk check --fix`.",
    "yaml": "YAML style: see the yamllint rule named in brackets.",
    "line-length": "Split the long line (YAML folded '>' blocks, or variables) or raise the limit in .yamllint.",
    "truthy": "Use true/false instead of yes/no/on/off.",
    "document-start": "Add '---' as the first line of the file.",
    "indentation": "Fix the indentation (2 spaces, list items indented under their key).",
    "comments": "Comments need a space after '#' and two spaces before inline comments.",
    "with-loop": "Replace with_items: X by loop: X (with_dict: d -> loop: \"{{ d | dict2items }}\").",
    "always_run": "Replace always_run: true by check_mode: false.",
}

DOCS = "https://ansible.readthedocs.io/projects/lint/rules/"


def hint_for(rule: str) -> str:
    base = rule.split("[", 1)[0]
    return HINTS.get(rule) or HINTS.get(base) or f"See {DOCS}{base}/"
