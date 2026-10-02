import json

from alk.cli import main
from alk.doctor import is_wsl
from alk.vscode import merge_extensions, merge_settings, setup


def test_merge_settings_keeps_user_values():
    current = {"ansible.validation.lint.path": "/custom/ansible-lint", "files.associations": {"*.j2": "jinja"}}
    merged = merge_settings(current, {"ansible.validation.lint.path": "ansible-lint",
                                      "files.associations": {"*.yml": "ansible", "*.j2": "other"},
                                      "yaml.validate": True})
    assert merged["ansible.validation.lint.path"] == "/custom/ansible-lint"
    assert merged["files.associations"] == {"*.yml": "ansible", "*.j2": "jinja"}
    assert merged["yaml.validate"] is True


def test_merge_extensions_no_duplicates():
    merged = merge_extensions({"recommendations": ["redhat.ansible"]}, ["redhat.ansible", "ms-vscode-remote.remote-wsl"])
    assert merged["recommendations"] == ["redhat.ansible", "ms-vscode-remote.remote-wsl"]


def test_setup_writes_files_and_backup(tmp_path):
    vs = tmp_path / ".vscode"
    vs.mkdir()
    (vs / "settings.json").write_text(json.dumps({"editor.tabSize": 2}), encoding="utf-8")
    setup(tmp_path)
    settings = json.loads((vs / "settings.json").read_text(encoding="utf-8"))
    assert settings["editor.tabSize"] == 2
    assert settings["ansible.validation.lint.enabled"] is True
    assert (vs / "settings.json.bak").exists()
    assert "ms-vscode-remote.remote-wsl" in json.loads((vs / "extensions.json").read_text())["recommendations"]


def test_setup_leaves_jsonc_alone(tmp_path):
    vs = tmp_path / ".vscode"
    vs.mkdir()
    (vs / "settings.json").write_text('{\n  // my comment\n  "a": 1\n}\n', encoding="utf-8")
    setup(tmp_path)
    assert "// my comment" in (vs / "settings.json").read_text(encoding="utf-8")
    assert (vs / "settings.alk-suggested.json").exists()


def test_is_wsl():
    assert is_wsl("Linux version 5.15.153.1-microsoft-standard-WSL2")
    assert not is_wsl("Linux version 6.8.0-45-generic (buildd@lcy02)")


def test_cli_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    assert "alk" in capsys.readouterr().out
