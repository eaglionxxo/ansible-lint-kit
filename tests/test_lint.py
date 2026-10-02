import json
import subprocess

from alk import lint as lint_mod
from alk.lint import Finding, parse_ansible_lint_json, parse_yamllint_parsable, sort_key


def _fake_ansible_lint(monkeypatch, returncode, stdout, stderr=""):
    monkeypatch.setattr(lint_mod.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(lint_mod, "_run", lambda cmd, cwd: subprocess.CompletedProcess(cmd, returncode, stdout, stderr))


def test_lint_tool_failure_is_not_clean(monkeypatch, tmp_path):
    _fake_ansible_lint(monkeypatch, 3, "", "Invalid configuration file .ansible-lint")
    findings = lint_mod.lint(tmp_path)
    assert [f.rule for f in findings] == ["run-error"]
    assert "Invalid configuration" in findings[0].message


def test_lint_clean_run(monkeypatch, tmp_path):
    _fake_ansible_lint(monkeypatch, 0, "[]")
    assert lint_mod.lint(tmp_path) == []


def test_parse_ansible_lint_json():
    data = [
        {
            "check_name": "name[missing]",
            "severity": "major",
            "description": "All tasks should be named.",
            "location": {"path": "site.yml", "lines": {"begin": 7}},
        },
        {
            "check_name": "yaml[truthy]",
            "severity": "minor",
            "description": "Truthy value should be one of [false, true]",
            "location": {"path": "roles/web/tasks/main.yml", "lines": {"begin": {"line": 3, "column": 5}}},
        },
    ]
    findings = parse_ansible_lint_json(json.dumps(data))
    assert [f.rule for f in findings] == ["name[missing]", "yaml[truthy]"]
    assert findings[0].line == 7
    assert findings[1].line == 3
    assert findings[1].severity == "minor"


def test_parse_ansible_lint_empty():
    assert parse_ansible_lint_json("") == []
    assert parse_ansible_lint_json("[]") == []


def test_parse_yamllint_parsable():
    out = (
        "site.yml:3:1: [warning] missing document start \"---\" (document-start)\n"
        "site.yml:12:81: [error] line too long (95 > 80 characters) (line-length)\n"
        "not a finding line\n"
    )
    findings = parse_yamllint_parsable(out)
    assert len(findings) == 2
    assert findings[0].rule == "document-start"
    assert findings[0].severity == "minor"
    assert findings[1].rule == "line-length"
    assert findings[1].severity == "major"
    assert findings[1].line == 12


def test_sort_by_severity():
    items = [
        Finding("t", "r", "minor", "a.yml", 1, ""),
        Finding("t", "r", "critical", "b.yml", 1, ""),
        Finding("t", "r", "major", "a.yml", 2, ""),
    ]
    assert [f.severity for f in sorted(items, key=sort_key)] == ["critical", "major", "minor"]
