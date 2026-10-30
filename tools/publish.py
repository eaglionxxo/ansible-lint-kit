#!/usr/bin/env python3
"""Publish a prepared release: commit, tag, push, GitHub Release + artifacts.

Run in CI after `tools/release.py --apply`. Environment:
  GITHUB_TOKEN      - token with contents:write
  GITHUB_REPOSITORY - owner/repo
  GIT_BRANCH        - branch to push the release commit to (default: main)

Refuses to proceed when:
  - the tag already exists (locally or on the remote): no duplicate releases
  - the working tree has unrelated uncommitted changes
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class PublishError(Exception):
    pass


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise PublishError(f"{' '.join(args)} failed: {res.stderr.strip()}")
    return res


def read_version() -> str:
    import re
    m = re.search(r'^version\s*=\s*"([^"]+)"', (REPO / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    if not m:
        raise PublishError("version not found in pyproject.toml")
    return m.group(1)


def extract_notes(changelog: str, version: str) -> str:
    """Return the markdown section for a version (without its ## header)."""
    start = changelog.find(f"## [{version}]")
    if start == -1:
        raise PublishError(f"no changelog section for {version}")
    start = changelog.find("\n", start) + 1
    nxt = changelog.find("\n## [", start)
    end = len(changelog) if nxt == -1 else nxt + 1
    return changelog[start:end].strip() + "\n"


def api(method: str, path: str, token: str, repo: str, data=None, host: str = "api.github.com"):
    url = f"https://{host}/repos/{repo}{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:500]
        raise PublishError(f"GitHub API {method} {path}: {exc.code} {detail}") from None


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    branch = os.environ.get("GIT_BRANCH", "main")
    if not token or not repo:
        raise PublishError("GITHUB_TOKEN and GITHUB_REPOSITORY are required")

    version = read_version()
    tag = f"v{version}"

    # No duplicate releases.
    if run("git", "rev-parse", tag, check=False).returncode == 0:
        raise PublishError(f"tag {tag} already exists locally")
    remote_tags = run("git", "ls-remote", "--tags", "origin", tag).stdout
    if tag in remote_tags:
        raise PublishError(f"tag {tag} already exists on the remote")
    existing = api("GET", "/releases", token, repo)
    if any(r.get("tag_name") == tag for r in existing):
        raise PublishError(f"a GitHub Release for {tag} already exists")

    # Only the release files may be dirty.
    dirty = run("git", "status", "--porcelain").stdout.splitlines()
    allowed = {"CHANGELOG.md", "pyproject.toml", "alk/__init__.py"}
    bad = [l for l in dirty if l[3:] not in allowed and "__pycache__" not in l]
    if bad:
        raise PublishError(f"unrelated uncommitted changes: {bad}")

    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "github-actions[bot]@users.noreply.github.com")
    run("git", "add", "CHANGELOG.md", "pyproject.toml", "alk/__init__.py")
    run("git", "commit", "-m", f"chore(release): {version}")
    run("git", "push", "origin", f"HEAD:{branch}")
    run("git", "tag", tag)
    run("git", "push", "origin", tag)

    # Build artifacts.
    run(sys.executable, "-m", "build", check=True)
    dist = sorted((REPO / "dist").glob("*"))
    if not dist:
        raise PublishError("build produced no artifacts")

    notes = extract_notes((REPO / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    rel = api("POST", "/releases", token, repo,
              {"tag_name": tag, "name": tag, "body": notes, "draft": False, "prerelease": False})
    upload_url = rel["upload_url"].split("{")[0]
    for artifact in dist:
        url = f"{upload_url}?name={artifact.name}"
        req = urllib.request.Request(url, data=artifact.read_bytes(), method="POST",
                                     headers={"Authorization": f"Bearer {token}",
                                              "Content-Type": "application/octet-stream"})
        try:
            with urllib.request.urlopen(req):
                pass
        except urllib.error.HTTPError as exc:
            raise PublishError(f"asset upload {artifact.name}: {exc.code}") from None
        print(f"uploaded {artifact.name}")

    print(f"published {tag}: {rel['html_url']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PublishError as exc:
        print(f"publish blocked: {exc}", file=sys.stderr)
        sys.exit(2)
