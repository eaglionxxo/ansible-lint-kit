#!/usr/bin/env bash
# End-to-end test: an Ansible 2.9-style repository must come out of `alk check --fix`
# with valid modern syntax, the right collections, and a passing syntax check.
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
cp -r "$here/examples/legacy-2.9/." "$work"
cd "$work"
git init -q -b main
git config user.email ci@example.com
git config user.name ci
git add -A
git commit -qm "legacy Ansible 2.9 playbooks"

echo "== before: legacy content must fail the check"
if alk check . --no-fix --report before.md; then
  echo "FAIL: legacy content passed the check"; exit 1
fi
grep -q "sudo -> become" before.md || grep -q "Syntax errors" before.md

echo "== fix"
alk check . --fix --report after.md || true
cat after.md

branch="$(git branch --list 'alk/fix-*' --format='%(refname:short)' | head -n1)"
[ -n "$branch" ] || { echo "FAIL: no fix branch created"; exit 1; }
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || { echo "FAIL: not back on main"; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "FAIL: main was modified"; exit 1; }

git switch -q "$branch"
echo "== verify fixes on $branch"
grep -qE '^\s+become: (yes|true)' site.yml          || { echo "FAIL: sudo not migrated"; exit 1; }
! grep -qE '^\s*sudo\s*:' site.yml                  || { echo "FAIL: sudo still present"; exit 1; }
grep -q 'ansible.builtin.include_tasks: extra.yml' site.yml || { echo "FAIL: task include not migrated"; exit 1; }
grep -q 'ansible.builtin.import_playbook: site.yml' main.yml || { echo "FAIL: play include not migrated"; exit 1; }
grep -q 'result is failed' site.yml                 || { echo "FAIL: |failed filter not migrated"; exit 1; }
grep -q 'ansible.posix' requirements.yml            || { echo "FAIL: ansible.posix not added to requirements"; exit 1; }
! grep -q 'community.general' requirements.yml      || { echo "FAIL: variable mistaken for a module"; exit 1; }

echo "== syntax check of the fixed playbooks"
ansible-playbook --syntax-check -i localhost, main.yml
ansible-playbook --syntax-check -i localhost, site.yml

if grep -q 'ansible.posix.sysctl' site.yml; then
  echo "OK: ansible-lint converted sysctl to its FQCN"
else
  echo "NOTE: sysctl not converted to FQCN by this ansible-lint version"
fi
echo "E2E PASSED"
