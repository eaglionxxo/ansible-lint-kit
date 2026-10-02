"""Run ansible-lint / yamllint and turn their output into a readable report."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SEVERITY_ORDER = ["blocker", "critical", "major", "minor", "info"]


@dataclass
class Finding:
    tool: str
    rule: str
    severity: str
    path: str
    line: int
    message: str


def parse_ansible_lint_json(text: str) -> list[Finding]:
    """Parse `ansible-lint -f json` (codeclimate format) output."""
    text = text.strip()
    if not text:
        return []
    data = json.loads(text)
    findings = []
    for item in data:
        loc = item.get("location", {})
        lines = loc.get("lines") or {}
        begin = lines.get("begin", 0)
        if isinstance(begin, dict):  # some versions nest {"line": n, "column": m}
            begin = begin.get("line", 0)
        findings.append(Finding(
            tool="ansible-lint",
            rule=item.get("check_name", "unknown"),
            severity=(item.get("severity") or "minor").lower(),
            path=loc.get("path", "?"),
            line=int(begin or 0),
            message=item.get("description", "").strip(),
        ))
    return findings


def parse_yamllint_parsable(text: str) -> list[Finding]:
    """Parse `yamllint -f parsable` lines: path:line:col: [level] message (rule)."""
    findings = []
    for raw in text.splitlines():
        parts = raw.split(":", 3)
        if len(parts) < 4 or "[" not in parts[3]:
            continue
        path, line, _col, rest = parts
        level = rest.split("[", 1)[1].split("]", 1)[0].strip()
        message = rest.split("]", 1)[1].strip()
        rule = "yaml"
        if message.endswith(")") and "(" in message:
            rule = message[message.rfind("(") + 1:-1]
            message = message[:message.rfind("(")].strip()
        findings.append(Finding(
            tool="yamllint",
            rule=rule,
            severity="major" if level == "error" else "minor",
            path=path,
            line=int(line) if line.isdigit() else 0,
            message=message,
        ))
    return findings


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def lint(target: Path) -> list[Finding]:
    target = target.resolve()
    cwd = target if target.is_dir() else target.parent
    findings: list[Finding] = []

    if shutil.which("ansible-lint"):
        args = ["ansible-lint", "-f", "json", "--nocolor"]
        if not target.is_dir():
            args.append(str(target))
        res = _run(args, cwd)
        try:
            findings += parse_ansible_lint_json(res.stdout)
        except json.JSONDecodeError:
            findings.append(Finding("ansible-lint", "run-error", "blocker", str(target), 0,
                                    (res.stderr or res.stdout).strip()[:500]))
    else:
        findings.append(Finding("ansible-lint", "missing-tool", "blocker", "-", 0,
                                "ansible-lint not installed (run `alk doctor`)."))

    # ansible-lint already runs yamllint through its yaml[...] rules (honouring .yamllint);
    # call yamllint directly only as a fallback, to avoid reporting every issue twice.
    if not shutil.which("ansible-lint") and shutil.which("yamllint"):
        res = _run(["yamllint", "-f", "parsable", str(target)], cwd)
        findings += parse_yamllint_parsable(res.stdout)

    return findings


def sort_key(f: Finding):
    rank = SEVERITY_ORDER.index(f.severity) if f.severity in SEVERITY_ORDER else len(SEVERITY_ORDER)
    return (rank, f.path, f.line)


def print_report(findings: list[Finding]) -> int:
    if not findings:
        print("No issues found. Clean playbooks!")
        return 0
    for f in sorted(findings, key=sort_key):
        print(f"  {f.severity.upper():8} {f.path}:{f.line}  [{f.tool}:{f.rule}] {f.message}")
    counts = Counter(f.severity for f in findings)
    summary = ", ".join(f"{counts[s]} {s}" for s in SEVERITY_ORDER if counts[s])
    print()
    print(f"{len(findings)} finding(s): {summary}")
    print("Tip: `alk fix <path>` applies safe automatic fixes on a separate git branch.")
    return 1
