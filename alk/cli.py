"""Command-line entry point: `alk doctor | lint | fix | setup-vscode`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, doctor, fix, lint, vscode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="alk", description="ansible-lint-kit: diagnose, lint and safely fix Ansible playbooks.")
    parser.add_argument("--version", action="version", version=f"alk {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check WSL, Python, Ansible tools and VS Code extensions")
    p_lint = sub.add_parser("lint", help="run ansible-lint + yamllint and print a report")
    p_lint.add_argument("path", nargs="?", default=".", type=Path)
    p_fix = sub.add_parser("fix", help="apply automatic fixes on a new git branch")
    p_fix.add_argument("path", nargs="?", default=".", type=Path)
    p_vs = sub.add_parser("setup-vscode", help="configure .vscode/ for Ansible linting through WSL")
    p_vs.add_argument("path", nargs="?", default=".", type=Path)

    args = parser.parse_args(argv)

    if args.command == "doctor":
        return doctor.print_report(doctor.run_checks())
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
    if args.command == "setup-vscode":
        for action in vscode.setup(args.path):
            print(" -", action)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
