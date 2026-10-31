# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-30

### Added
- `alk check --fix`: full-repo pass — Ansible 2.9 migration (`include`/`sudo`/filters/moved modules), `requirements.yml` update + collection install, `ansible-lint --fix` on a dedicated `alk/fix-*` branch, markdown report with remaining findings and fixes
- `alk doctor`, `alk migrate`, `alk deps`, `alk lint`, `alk fix`, `alk setup-vscode`, `alk ci-setup` commands
- CI/CD pipeline on self-hosted Alienware runners: unit tests (Python 3.10/3.12) with coverage, e2e migration tests (ansible-core 2.16/2.18), quality gates (yamllint + alk self-check), `pip-audit` security audit
- Automatic SemVer releases: version detection from conventional commits, changelog generation, GitHub Releases with sdist/wheel artifacts (`tools/release.py`, `tools/publish.py`, `release.yml`)
- Dynamic README badges: project status, technologies & stack, live dependency versions, CI/CD, testing, security

### Fixed
- `migrate`: `|success` -> `is succeeded` (was generating invalid Jinja tests that broke `--syntax-check`)
- `git diff main...<branch>` commands corrected in check report and `fix` command
- Clear error when PyYAML is missing (was misleading "could not parse"); clean notes on unreadable/unwritable `requirements.yml`
- Clear error when `git user.name`/`user.email` are not configured (was raw traceback)
- ansible-lint JSON parsing tolerant to prefixed warnings; `location: null` no longer crashes
- Failed dependency installs now fail the check verdict (was incorrectly reported PASS)
- Missing `git` binary, detached HEAD, and branch-name collisions handled with clear errors
- Subprocess timeouts: ansible-lint / syntax-check (300s), ansible-galaxy / --fix (600s)
- UTF-8 BOM stripped on read; CRLF line endings preserved by `fix_text`
- `setup-vscode`: `.vscode` existing as a file handled gracefully; `.bak` rewritten only on change

### Changed
- CI-CD job table matches reconciled workflow
- CI-CD security job notes
- dynamic GitHub badges in README (project status, technologies, live dependency versions, CI/CD, testing, security, releases)
- quote yamllint config in workflow
- run Linux jobs on the self-hosted Alienware runners
- run unit, e2e migration and quality gates on Alienware self-hosted runners

