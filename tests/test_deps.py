"""Tests for alk.deps: requirements discovery and ansible-galaxy install handling."""

import subprocess

from alk import deps as deps_mod
from alk.discover import find_requirements


def _fake_run(monkeypatch, returncode, out="done"):
    monkeypatch.setattr(deps_mod.shutil, "which",
                        lambda name: "/usr/bin/ansible-galaxy" if name == "ansible-galaxy" else None)
    monkeypatch.setattr(deps_mod.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a[0], returncode, out, ""))


def test_find_requirements(tmp_path):
    assert find_requirements(tmp_path) == []
    (tmp_path / "requirements.yml").write_text("---\n", encoding="utf-8")
    roles = tmp_path / "roles"
    roles.mkdir()
    (roles / "requirements.yml").write_text("---\n", encoding="utf-8")
    found = {p.name for p in find_requirements(tmp_path)}
    assert found == {"requirements.yml"}


def test_install_ok(monkeypatch, tmp_path):
    (tmp_path / "requirements.yml").write_text("---\ncollections:\n", encoding="utf-8")
    _fake_run(monkeypatch, 0)
    results = deps_mod.install(tmp_path)
    assert len(results) == 1
    assert results[0].ok and results[0].file == "requirements.yml"


def test_install_failure_reported(monkeypatch, tmp_path):
    (tmp_path / "requirements.yml").write_text("---\ncollections:\n", encoding="utf-8")
    _fake_run(monkeypatch, 1, "ERROR: network unreachable")
    results = deps_mod.install(tmp_path)
    assert len(results) == 1
    assert not results[0].ok
    assert "network unreachable" in results[0].detail


def test_install_without_galaxy(monkeypatch, tmp_path):
    (tmp_path / "requirements.yml").write_text("---\ncollections:\n", encoding="utf-8")
    monkeypatch.setattr(deps_mod.shutil, "which", lambda name: None)
    results = deps_mod.install(tmp_path)
    assert len(results) == 1
    assert not results[0].ok
    assert "not installed" in results[0].detail


def test_install_no_requirements_files(tmp_path):
    assert deps_mod.install(tmp_path) == []


def test_print_report_exit_codes(capsys):
    assert deps_mod.print_report([]) == 0
    from alk.deps import DepResult
    assert deps_mod.print_report([DepResult("r.yml", True, "ok")]) == 0
    assert deps_mod.print_report([DepResult("r.yml", False, "ko")]) == 1
