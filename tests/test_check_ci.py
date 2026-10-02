from pathlib import Path

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


def test_ci_setup_writes_workflow_once(tmp_path):
    path, written = ci.setup(tmp_path, core_version="2.17")
    assert written and path.exists()
    text = path.read_text()
    assert 'ansible-core==2.17.*' in text and "alk check . --no-fix" in text
    _, written_again = ci.setup(tmp_path)
    assert not written_again
