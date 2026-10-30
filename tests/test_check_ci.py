from pathlib import Path

import pytest

from alk import ci
from alk.check import CheckResult, SyntaxResult, to_markdown
from alk.hints import hint_for
from alk.lint import Finding


def test_hint_for_known_and_subrules():
    assert "mode" in hint_for("risky-file-permissions")
    assert "name" in hint_for("name[casing]").lower()
    assert hint_for("some-new-rule[x]").endswith("/some-new-rule/")


def test_report_lists_human_items_with_guidance():
    r = CheckResult(root=Path("/repo"))
    r.before = [Finding("ansible-lint", "no-changed-when", "major", "site.yml", 4, "Commands should not change things"),
                Finding("ansible-lint", "fqcn[action-core]", "major", "site.yml", 2, "Use FQCN")]
    r.after = [r.before[0]]
    r.branch = "alk/fix-20261002-080000"
    r.syntax = [SyntaxResult("site.yml", True)]
    md = to_markdown(r)
    assert "Lint findings: 2 before -> 1 after ansible-lint --fix" in md
    assert "alk/fix-20261002-080000" in md
    assert "### `no-changed-when`" in md and "changed_when" in md
    assert "NEEDS WORK" in md
    assert not r.ok


def test_report_explains_counts_masked_by_syntax_errors():
    from alk.migrate import Issue
    r = CheckResult(root=Path("/repo"))
    r.before = [Finding("ansible-lint", "syntax-check[specific]", "blocker", "site.yml", 2, "'sudo' is not valid")]
    r.migration.issues = [Issue("site.yml", 2, "legacy-syntax", "sudo -> become", True)]
    r.migrated = [Finding("ansible-lint", "name[play]", "major", "site.yml", 1, "")] * 6
    r.after = r.migrated[:4]
    md = to_markdown(r)
    assert "Ansible 2.9 legacy syntax fixed: 1" in md
    assert "Lint findings: 6 after migration -> 4 after ansible-lint --fix" in md
    assert "could only report 1 finding(s) before the migration" in md


def test_report_pass_when_clean():
    r = CheckResult(root=Path("/repo"), before=[], after=[], syntax=[SyntaxResult("site.yml", True)])
    assert r.ok
    assert "PASS" in to_markdown(r)


def test_failed_dependencies_fail_the_check():
    from alk.deps import DepResult
    r = CheckResult(root=Path("/repo"), before=[], after=[],
                    syntax=[SyntaxResult("site.yml", True)],
                    deps=[DepResult("requirements.yml", False, "network unreachable")])
    assert not r.ok
    assert "NEEDS WORK" in to_markdown(r)


def test_syntax_check_timeout(monkeypatch, tmp_path):
    import subprocess as sp
    from alk import check as checkmod
    (tmp_path / "site.yml").write_text("- hosts: all\n  tasks: []\n", encoding="utf-8")
    monkeypatch.setattr(checkmod.shutil, "which", lambda name: "/usr/bin/ansible-playbook")

    def _hang(*args, **kwargs):
        raise sp.TimeoutExpired(args[0], 300)

    monkeypatch.setattr(checkmod.subprocess, "run", _hang)
    results = checkmod.syntax_check(tmp_path)
    assert len(results) == 1
    assert not results[0].ok and "timed out" in results[0].error


def test_check_run_rejects_missing_path(tmp_path):
    from alk import check as checkmod
    from alk import fix as fixmod
    with pytest.raises(fixmod.FixError, match="path does not exist"):
        checkmod.run(tmp_path / "nope", apply_fix=False)


def test_cli_check_creates_report_parent_dir(tmp_path, capsys):
    from alk.cli import main
    report = tmp_path / "sub" / "deep" / "r.md"
    rc = main(["check", "--no-deps", str(tmp_path), "--report", str(report)])
    assert report.exists()
    assert "alk check report" in report.read_text(encoding="utf-8")
    assert rc in (0, 1)  # 1 when ansible-lint is missing in this environment
    capsys.readouterr()


def test_ci_setup_writes_workflow_once(tmp_path):
    path, written = ci.setup(tmp_path, core_version="2.17")
    assert written and path.exists()
    text = path.read_text()
    assert 'ansible-core==2.17.*' in text and "alk check . --no-fix" in text
    _, written_again = ci.setup(tmp_path)
    assert not written_again
