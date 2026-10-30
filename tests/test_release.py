"""Unit tests for tools/release.py (SemVer detection, changelog, version bump)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import release
from release import ReleaseError, bump_version, classify, render_section


def test_classify_feat_is_minor():
    bump, entries = classify([("feat: add vault support", "")])
    assert bump == "minor"
    assert entries == [("Added", "add vault support")]


def test_classify_fix_is_patch():
    bump, entries = classify([("fix: correct sudo regex", "")])
    assert bump == "patch"
    assert entries == [("Fixed", "correct sudo regex")]


def test_classify_highest_wins():
    bump, _ = classify([("fix: a", ""), ("feat: b", "")])
    assert bump == "minor"


def test_classify_breaking_is_major():
    bump, _ = classify([("feat!: drop python 3.9", "")])
    assert bump == "major"
    bump, _ = classify([("fix: tweak", "BREAKING CHANGE: new CLI flags")])
    assert bump == "major"


def test_classify_unknown_type_ignored():
    bump, entries = classify([("wip: stuff", "")])
    assert bump is None and entries == []


def test_classify_no_conventional_is_ambiguous():
    bump, entries = classify([("random message", ""), ("another one", "")])
    assert bump is None and entries == []


def test_classify_security_and_deprecated_sections():
    bump, entries = classify([
        ("fix: patch security hole in deps", ""),
        ("feat: deprecate old flag", ""),
    ])
    sections = {subject: section for section, subject in entries}
    assert sections["patch security hole in deps"] == "Security"
    assert sections["deprecate old flag"] == "Deprecated"


def test_bump_version():
    assert bump_version("1.2.3", "patch") == "1.2.4"
    assert bump_version("1.2.3", "minor") == "1.3.0"
    assert bump_version("1.2.3", "major") == "2.0.0"
    with pytest.raises(ReleaseError):
        bump_version("1.2", "patch")


def test_render_section_order_and_dedup():
    section = render_section("1.3.0", "2026-10-30", [
        ("Fixed", "a"), ("Added", "b"), ("Added", "b"), ("Fixed", "c"),
    ])
    assert section.startswith("## [1.3.0] - 2026-10-30")
    assert section.index("### Added") < section.index("### Fixed")
    assert section.count("- b") == 1


def _tmp_repo(tmp_path, monkeypatch):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.2.0"\n', encoding="utf-8")
    init = tmp_path / "__init__.py"
    init.write_text('__version__ = "0.2.0"\n', encoding="utf-8")
    monkeypatch.setattr(release, "PYPROJECT", pyproject)
    monkeypatch.setattr(release, "INIT", init)
    monkeypatch.setattr(release, "CHANGELOG", tmp_path / "CHANGELOG.md")
    return tmp_path


def test_set_version_updates_both_files(tmp_path, monkeypatch):
    _tmp_repo(tmp_path, monkeypatch)
    release.set_version("0.3.0")
    assert 'version = "0.3.0"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '__version__ = "0.3.0"' in (tmp_path / "__init__.py").read_text(encoding="utf-8")


def test_update_changelog_prepends_without_dup(tmp_path, monkeypatch):
    _tmp_repo(tmp_path, monkeypatch)
    release.update_changelog("## [0.3.0] - 2026-10-30\n\n### Added\n- x\n", "0.3.0")
    text = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.startswith("# Changelog")
    assert "## [0.3.0]" in text
    with pytest.raises(ReleaseError):
        release.update_changelog("## [0.3.0] - 2026-10-30\n", "0.3.0")


def test_plan_ambiguous_without_conventional(monkeypatch, tmp_path):
    _tmp_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(release, "last_tag", lambda: None)
    monkeypatch.setattr(release, "commits_since", lambda ref: [("random", "")])
    with pytest.raises(ReleaseError, match="ambiguous"):
        release.plan()


def test_plan_version_override(monkeypatch, tmp_path):
    _tmp_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(release, "last_tag", lambda: None)
    monkeypatch.setattr(release, "commits_since", lambda ref: [])
    new, section, _ = release.plan("1.0.0")
    assert new == "1.0.0"
    assert "## [1.0.0]" in section
    with pytest.raises(ReleaseError, match="invalid --version"):
        release.plan("nope")
    with pytest.raises(ReleaseError, match="already the current version"):
        release.plan("0.2.0")


def test_plan_auto_from_commits(monkeypatch, tmp_path):
    _tmp_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(release, "last_tag", lambda: "v0.2.0")
    monkeypatch.setattr(release, "commits_since",
                        lambda ref: [("feat: add timeouts", ""), ("fix: typo", "")])
    new, section, entries = release.plan()
    assert new == "0.3.0"
    assert "### Added" in section and "### Fixed" in section
    assert len(entries) == 2


def test_update_changelog_inserts_after_unreleased(tmp_path, monkeypatch):
    _tmp_repo(tmp_path, monkeypatch)
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(release.HEADER + "## [Unreleased]\n\n### Added\n- wip\n", encoding="utf-8")
    release.update_changelog("## [0.3.0] - 2026-10-30\n\n### Fixed\n- x\n", "0.3.0")
    text = cl.read_text(encoding="utf-8")
    assert text.index("## [Unreleased]") < text.index("## [0.3.0]")


def test_extract_notes():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    import publish
    changelog = ("# Changelog\n\n## [0.3.0] - 2026-10-30\n\n### Added\n- x\n\n"
                 "## [0.2.0] - 2026-10-01\n\n### Fixed\n- y\n")
    notes = publish.extract_notes(changelog, "0.3.0")
    assert "### Added" in notes and "- x" in notes
    assert "0.2.0" not in notes
    with pytest.raises(publish.PublishError):
        publish.extract_notes(changelog, "9.9.9")
