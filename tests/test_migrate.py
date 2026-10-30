from alk import migrate
from alk.discover import find_playbooks, is_playbook

LEGACY = """\
- hosts: all
  sudo: yes
  sudo_user: deploy
  vars:
    timezone: Europe/Paris
  tasks:
  - name: tune kernel
    sysctl: name=vm.swappiness value=10
  - name: mount
    mount:
      path: /data
  - debug: msg="broken"
    when: result|failed
  - debug: msg="{{ item.key }}"
    with_dict: "{{ users }}"
  - include: extra.yml
  - set_fact:
      pairs: "{{ users.iteritems() | list }}"
"""


def test_fix_text_legacy_syntax():
    new, changes = migrate.fix_text(LEGACY, playbook=True)
    assert "  become: yes" in new
    assert "  become_user: deploy" in new
    assert "sudo" not in new
    assert "- ansible.builtin.include_tasks: extra.yml" in new  # task-level include
    assert "when: result is failed" in new
    assert "users.items()" in new
    assert len(changes) == 5


def test_fix_text_success_filter_becomes_is_succeeded():
    # Ansible 2.9 `|success` means "succeeded"; `is success` is not a valid Jinja test.
    new, changes = migrate.fix_text("  when: result|success\n", playbook=False)
    assert new == "  when: result is succeeded\n"
    assert len(changes) == 1
    new, _ = migrate.fix_text("  when: result|succeeded\n", playbook=False)
    assert new == "  when: result is succeeded\n"


def test_update_requirements_missing_pyyaml(monkeypatch, tmp_path):
    import sys
    (tmp_path / "requirements.yml").write_text("---\ncollections:\n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "yaml", None)  # `import yaml` now raises ImportError
    path, added, note = migrate.update_requirements(tmp_path, {"ansible.posix"})
    assert path is None and added == []
    assert "PyYAML is not installed" in note
    assert "ansible.posix" in note


def test_play_level_include_becomes_import_playbook():
    new, _ = migrate.fix_text("- include: site.yml\n", playbook=True)
    assert new == "- ansible.builtin.import_playbook: site.yml\n"
    # same line in a task file is a task include
    new, _ = migrate.fix_text("- include: site.yml\n", playbook=False)
    assert new == "- ansible.builtin.include_tasks: site.yml\n"


def test_apply_master_playbook_and_role_task_file(tmp_path):
    (tmp_path / "main.yml").write_text("- include: site.yml\n- include: db.yml\n", encoding="utf-8")
    tasks = tmp_path / "roles" / "web" / "tasks"
    tasks.mkdir(parents=True)
    (tasks / "main.yml").write_text("- include: install.yml\n", encoding="utf-8")
    migrate.apply(tmp_path)
    assert (tmp_path / "main.yml").read_text().count("ansible.builtin.import_playbook") == 2
    assert (tasks / "main.yml").read_text() == "- ansible.builtin.include_tasks: install.yml\n"


def test_fix_text_leaves_modern_content_alone():
    modern = "- name: x\n  ansible.builtin.include_tasks: a.yml\n  when: result is failed\n"
    new, changes = migrate.fix_text(modern, playbook=False)
    assert new == modern and changes == []


def test_scan_detects_moved_modules_but_not_variables(tmp_path):
    (tmp_path / "site.yml").write_text(LEGACY, encoding="utf-8")
    report = migrate.scan(tmp_path)
    assert report.collections == {"ansible.posix"}  # sysctl + mount; 'timezone: Europe/Paris' is a variable
    kinds = {i.kind for i in report.issues}
    assert {"legacy-syntax", "module-moved", "with-loop"} <= kinds
    assert any(not i.autofix and i.kind == "with-loop" for i in report.issues)


def test_scan_collects_fqcn_collections(tmp_path):
    (tmp_path / "pb.yml").write_text("- hosts: all\n  tasks:\n    - community.general.ufw:\n        rule: allow\n",
                                     encoding="utf-8")
    assert migrate.scan(tmp_path).collections == {"community.general"}


def test_update_requirements_creates_file(tmp_path):
    path, added, _ = migrate.update_requirements(tmp_path, {"ansible.posix", "community.general"})
    assert path == tmp_path / "requirements.yml"
    assert added == ["ansible.posix", "community.general"]
    assert "  - name: ansible.posix" in path.read_text()


def test_update_requirements_appends_and_keeps_comments(tmp_path):
    req = tmp_path / "requirements.yml"
    req.write_text("---\n# our deps\ncollections:\n    - name: community.general\n      version: '>=8.0.0'\n",
                   encoding="utf-8")
    path, added, _ = migrate.update_requirements(tmp_path, {"ansible.posix", "community.general"})
    text = req.read_text()
    assert added == ["ansible.posix"]
    assert "# our deps" in text and "version: '>=8.0.0'" in text
    assert "    - name: ansible.posix\n" in text


def test_update_requirements_unwritable_target(tmp_path):
    # requirements.yml as a directory: not detected as a requirements file, the
    # create path fails cleanly -> note, no traceback.
    (tmp_path / "requirements.yml").mkdir()
    path, added, note = migrate.update_requirements(tmp_path, {"ansible.posix"})
    assert path is None and added == []
    assert "could not write requirements.yml" in note


def test_scan_handles_utf8_bom(tmp_path):
    (tmp_path / "site.yml").write_bytes(b"\xef\xbb\xbf- hosts: all\n  sudo: yes\n")
    report = migrate.scan(tmp_path)
    assert any("sudo -> become" in i.message for i in report.issues)
    migrate.apply(tmp_path)
    assert "become: yes" in (tmp_path / "site.yml").read_text(encoding="utf-8-sig")


def test_fix_text_preserves_crlf():
    new, changes = migrate.fix_text("- hosts: all\r\n  sudo: yes\r\n", playbook=True)
    assert "become: yes\r\n" in new
    assert new.count("\r\n") == 2
    assert len(changes) == 1


def test_update_requirements_nothing_needed(tmp_path):
    assert migrate.update_requirements(tmp_path, set())[0] is None


def test_playbook_detection(tmp_path):
    assert is_playbook("- hosts: all\n  tasks: []\n")
    assert is_playbook("- name: Web\n  hosts: web\n  tasks: []\n")
    assert is_playbook("- import_playbook: web.yml\n")
    assert not is_playbook("- name: a task\n  ansible.builtin.debug:\n    msg: hi\n")
    (tmp_path / "site.yml").write_text("- hosts: all\n  tasks: []\n")
    role_tasks = tmp_path / "roles" / "web" / "tasks"
    role_tasks.mkdir(parents=True)
    (role_tasks / "main.yml").write_text("- hosts: weird\n")
    assert [p.name for p in find_playbooks(tmp_path)] == ["site.yml"]
