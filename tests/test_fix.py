"""Tests for alk.fix: branch/commit helpers (git identity, staging, branch naming)."""

import subprocess

import pytest

from alk import fix as fixmod


def _git(repo, *args):
    res = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return res.stdout.strip()


@pytest.fixture()
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "ci")
    _git(tmp_path, "config", "user.email", "ci@example.com")
    (tmp_path / "site.yml").write_text("---\n- hosts: all\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def test_branch_name_format():
    name = fixmod.branch_name()
    assert name.startswith("alk/fix-")
    assert len(name) == len("alk/fix-") + 15  # YYYYMMDD-HHMMSS


def test_has_changes_detects_tracked_modifications(repo):
    assert not fixmod.has_changes(repo)
    (repo / "site.yml").write_text("---\n- hosts: all\n# changed\n", encoding="utf-8")
    assert fixmod.has_changes(repo)


def test_has_changes_ignores_untracked_files(repo):
    (repo / "alk-report.md").write_text("scratch", encoding="utf-8")
    assert not fixmod.has_changes(repo)


def test_commit_all_commits_tracked_changes(repo):
    (repo / "site.yml").write_text("---\n- hosts: all\n# changed\n", encoding="utf-8")
    assert fixmod.commit_all(repo, "test commit")
    assert "test commit" in _git(repo, "log", "--format=%s", "-1")


def test_commit_all_false_when_nothing_changed(repo):
    assert not fixmod.commit_all(repo, "nothing")


def test_commit_all_includes_extra_new_files(repo):
    extra = repo / "requirements.yml"
    extra.write_text("---\ncollections:\n", encoding="utf-8")
    assert fixmod.commit_all(repo, "add requirements", [extra])
    assert "requirements.yml" in _git(repo, "show", "--name-only", "--format=", "HEAD")


def test_ensure_identity_ok(repo):
    fixmod.ensure_identity(repo)  # must not raise


def test_ensure_identity_missing_email(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "ci")
    with pytest.raises(fixmod.FixError, match="user.email"):
        fixmod.ensure_identity(tmp_path)


def test_ensure_identity_missing_name(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    with pytest.raises(fixmod.FixError, match="user.name"):
        fixmod.ensure_identity(tmp_path)


def test_current_branch(repo):
    assert fixmod.current_branch(repo) == "main"


def test_repo_root_not_a_repo(tmp_path):
    with pytest.raises(fixmod.FixError, match="not inside a git repository"):
        fixmod.repo_root(tmp_path)
