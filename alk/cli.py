"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, check, ci, deps, doctor, fix, lint, migrate, vscode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="alk", description="ansible-lint-kit: diagnose, lint and safely fix Ansible playbooks.")
    parser.add_argument("--version", action="version", version=f"alk {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check WSL, Python, Ansible tools and VS Code extensions")

    p = sub.add_parser("check", help="whole repo: deps, migration scan, lint, syntax check, report (--fix to auto-fix on a branch)")
    p.add_argument("path", nargs="?", default=".", type=Path)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--fix", dest="apply_fix", action="store_true", help="apply automatic fixes on a new git branch")
    mode.add_argument("--no-fix", dest="apply_fix", action="store_false", help="report only (default, use in CI)")
    p.add_argument("--no-deps", action="store_true", help="do not install requirements.yml dependencies")
    p.add_argument("--report", type=Path, default=Path("alk-report.md"), help="markdown report path (default: alk-report.md)")
    p.set_defaults(apply_fix=False)

    p = sub.add_parser("lint", help="run ansible-lint and print a report")
    p.add_argument("path", nargs="?", default=".", type=Path)
    p = sub.add_parser("fix", help="apply ansible-lint automatic fixes on a new git branch")
    p.add_argument("path", nargs="?", default=".", type=Path)
    p = sub.add_parser("migrate", help="scan for Ansible 2.9 legacy syntax and collections now needed")
    p.add_argument("path", nargs="?", default=".", type=Path)
    p = sub.add_parser("deps", help="install collections and roles from requirements.yml files")
    p.add_argument("path", nargs="?", default=".", type=Path)
    p = sub.add_parser("setup-vscode", help="configure .vscode/ for Ansible linting through WSL")
    p.add_argument("path", nargs="?", default=".", type=Path)
    p = sub.add_parser("ci-setup", help="add a GitHub Actions workflow that lints the repo on every push")
    p.add_argument("path", nargs="?", default=".", type=Path)
    p.add_argument("--ansible-core", default="", help="pin ansible-core major.minor in CI, e.g. 2.17")
    p.add_argument("--force", action="store_true", help="overwrite an existing workflow")

    args = parser.parse_args(argv)

    if args.command == "doctor":
        return doctor.print_report(doctor.run_checks())
    if args.command == "check":
        try:
            result = check.run(args.path, apply_fix=args.apply_fix, install_deps=not args.no_deps)
        except fix.FixError as exc:
            print(f"alk check: {exc}", file=sys.stderr)
            return 1
        args.report.write_text(check.to_markdown(result), encoding="utf-8")
        check.print_summary(result)
        print(f"Report: {args.report}")
        return 0 if result.ok else 1
    if args.command == "lint":
        return lint.print_report(lint.lint(args.path))
    if args.command == "fix":
        try:
            branch = fix.fix(args.path)
        except fix.FixError as exc:
            print(f"alk fix: {exc}", file=sys.stderr)
            return 1
        print(f"Fixes committed on branch '{branch}'. Review with: git diff ...{branch}")
        print(f"Keep them with: git merge {branch}")
        return 0
    if args.command == "migrate":
        return migrate.print_report(migrate.scan(args.path))
    if args.command == "deps":
        return deps.print_report(deps.install(args.path))
    if args.command == "setup-vscode":
        for action in vscode.setup(args.path):
            print(" -", action)
        return 0
    if args.command == "ci-setup":
        path, written = ci.setup(args.path, args.ansible_core, args.force)
        print(f"Wrote {path}" if written else f"{path} already exists (use --force to overwrite)")
        if written:
            print("Commit and push it: every push / pull request will now run `alk check --no-fix`.")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
