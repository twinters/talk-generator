#!/usr/bin/env python3
"""Release helper for talkgenerator.

Commands
--------
  uv run python scripts/release.py bump <patch|minor|major|X.Y.Z> [--dry-run] [--trailer TEXT]
      Prepare a release on the current branch, locally and reversibly. It first checks
      that there are no uncommitted changes, that the branch isn't behind its upstream,
      that the tag is free (locally and on origin) and that CHANGELOG.md has an
      [Unreleased] section, and stops before changing anything if one of those fails.
      Then it:
        * sets the new version in pyproject.toml (via ``uv version``)
        * syncs CITATION.cff (version + date-released)
        * rolls the [Unreleased] section of CHANGELOG.md into a dated section
        * refreshes uv.lock
        * commits those files and creates the annotated tag vX.Y.Z
      It then PRINTS the commands that publish (one atomic push + the GitHub release);
      it never pushes or publishes by itself. ``--dry-run`` runs the checks and shows
      the version change without writing anything. ``--trailer`` adds a trailer such
      as "Co-Authored-By: ..." to the release commit (repeatable).

  uv run python scripts/release.py check
      Fail if pyproject.toml and CITATION.cff disagree on the version. Run in CI
      so the package version and the citation metadata can't silently drift.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CITATION = ROOT / "CITATION.cff"
CHANGELOG = ROOT / "CHANGELOG.md"
NOTES = ROOT / ".release-notes.md"
REPO = "https://github.com/twinters/talk-generator"

UNRELEASED_PLACEHOLDER = (
    "<!-- Add changes here as you merge them; release.py moves them under the new version at release time. -->"
)
UNRELEASED_SECTION = re.compile(r"## \[Unreleased\]\n(?P<body>.*?)(?=\n## \[|\Z)", re.DOTALL)


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True, text=True)


def git(*args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command and capture its output, without raising when it fails."""
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)


def pyproject_version() -> str:
    with PYPROJECT.open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def citation_version(text: str) -> str | None:
    m = re.search(r"^version:\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip().strip('"') if m else None


def next_version(current: str, spec: str) -> str:
    if re.fullmatch(r"\d+\.\d+\.\d+", spec):
        return spec
    try:
        major, minor, patch = (int(p) for p in current.split("."))
    except ValueError:
        sys.exit(f"current version {current!r} is not X.Y.Z; pass an explicit version")
    bumped = {
        "major": f"{major + 1}.0.0",
        "minor": f"{major}.{minor + 1}.0",
        "patch": f"{major}.{minor}.{patch + 1}",
    }.get(spec)
    if bumped is None:
        sys.exit(f"not a bump level or X.Y.Z version: {spec!r}")
    return bumped


def check() -> int:
    py = pyproject_version()
    cit = citation_version(CITATION.read_text(encoding="utf-8"))
    if cit != py:
        sys.stderr.write(
            f"version mismatch: pyproject.toml={py!r} CITATION.cff={cit!r}\n"
            "run `uv run python scripts/release.py bump ...` to set both together\n"
        )
        return 1
    print(f"ok: pyproject.toml and CITATION.cff agree on {py}")
    return 0


def preflight(branch: str, tag: str) -> list[str]:
    """Everything that stops a release from starting right now; empty when it can start."""
    problems: list[str] = []
    if branch == "HEAD":
        problems.append("not on a branch (detached HEAD)")
    status = git("status", "--porcelain", "--untracked-files=no")
    if status.returncode != 0:
        return [*problems, f"git status failed: {status.stderr.strip()}"]
    if status.stdout.strip():
        problems.append("there are uncommitted changes; commit or stash them first")
    if not UNRELEASED_SECTION.search(CHANGELOG.read_text(encoding="utf-8")):
        problems.append("CHANGELOG.md has no '## [Unreleased]' section")
    if git("rev-parse", "--quiet", "--verify", f"refs/tags/{tag}").returncode == 0:
        problems.append(f"tag {tag} already exists locally")
    if git("remote", "get-url", "origin").returncode == 0:
        remote = git("ls-remote", "--tags", "origin", f"refs/tags/{tag}")
        if remote.returncode != 0:
            problems.append(f"couldn't check origin for tag {tag}: {remote.stderr.strip()}")
        elif remote.stdout.strip():
            problems.append(f"tag {tag} already exists on origin")
    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if upstream.returncode == 0:
        name = upstream.stdout.strip()
        remote_name = name.split("/", 1)[0]
        if git("remote", "get-url", remote_name).returncode == 0:
            git("fetch", "--quiet", remote_name)
        behind = git("rev-list", "--count", "HEAD..@{upstream}").stdout.strip()
        if behind not in ("", "0"):
            problems.append(f"this branch is {behind} commit(s) behind {name}; pull first")
    return problems


def sync_citation(version: str, today: str) -> None:
    text = CITATION.read_text(encoding="utf-8")
    text = re.sub(r"^version:.*$", f"version: {version}", text, count=1, flags=re.MULTILINE)
    text = re.sub(r"^date-released:.*$", f'date-released: "{today}"', text, count=1, flags=re.MULTILINE)
    CITATION.write_text(text, encoding="utf-8")


def roll_changelog(version: str, today: str) -> str:
    text = CHANGELOG.read_text(encoding="utf-8")
    m = UNRELEASED_SECTION.search(text)
    if not m:
        sys.exit("CHANGELOG.md has no '## [Unreleased]' section")
    body = "\n".join(ln for ln in m.group("body").splitlines() if ln.strip() != UNRELEASED_PLACEHOLDER).strip("\n")
    section = f"## [Unreleased]\n\n{UNRELEASED_PLACEHOLDER}\n\n## [{version}] - {today}"
    if body:
        section += f"\n\n{body}"
    text = text[: m.start()] + section + "\n\n" + text[m.end() :].lstrip("\n")
    # Repoint the Unreleased compare link and add a link for the new release.
    if re.search(r"^\[Unreleased\]:", text, re.MULTILINE):
        text = re.sub(
            r"^\[Unreleased\]:.*$",
            f"[Unreleased]: {REPO}/compare/v{version}...HEAD",
            text,
            count=1,
            flags=re.MULTILINE,
        )
        if not re.search(rf"^\[{re.escape(version)}\]:", text, re.MULTILINE):
            text = re.sub(
                r"^(\[Unreleased\]:.*\n)",
                rf"\1[{version}]: {REPO}/releases/tag/v{version}\n",
                text,
                count=1,
                flags=re.MULTILINE,
            )
    CHANGELOG.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    return body


def bump(spec: str, dry_run: bool, trailers: list[str]) -> int:
    current = pyproject_version()
    target = next_version(current, spec)
    tag = f"v{target}"
    today = date.today().isoformat()
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    print(f"branch:  {branch}\ncurrent: {current}\ntarget:  {target}\ndate:    {today}", flush=True)

    problems = preflight(branch, tag)
    if problems:
        print("\nNot releasing:", *(f"  - {p}" for p in problems), sep="\n", file=sys.stderr)
        return 1
    if dry_run:
        print("\n--dry-run: all checks passed; nothing written, committed or tagged.")
        return 0

    run("uv", "version", target, "--no-sync")
    got = pyproject_version()
    if got != target:
        sys.exit(f"uv set the version to {got!r}, expected {target!r}; aborting")
    sync_citation(target, today)
    body = roll_changelog(target, today)
    run("uv", "lock")
    NOTES.write_text((body or f"talkgenerator {target}.") + "\n", encoding="utf-8")

    run("git", "add", "pyproject.toml", "uv.lock", "CITATION.cff", "CHANGELOG.md")
    commit = ["git", "commit", "-m", f"Release {target}"]
    for trailer in trailers:
        commit += ["--trailer", trailer]
    run(*commit)
    run("git", "tag", "-a", tag, "-m", f"talkgenerator {target}")

    print(
        "\n".join(
            [
                f"\nPrepared {tag} on {branch}: committed and tagged locally, nothing pushed.",
                "",
                "Publish it:",
                f"  git push --atomic origin HEAD refs/tags/{tag}",
                f'  gh release create {tag} --verify-tag --title "talkgenerator {target}" --notes-file .release-notes.md',
                "",
                "Publishing the GitHub release builds, tests and uploads to PyPI (after your approval).",
                f"Undo before pushing:  git tag -d {tag} && git reset --hard HEAD~1",
            ]
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and verify talkgenerator releases.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bump", help="prepare a release (version, changelog, tag)")
    b.add_argument("spec", help="patch | minor | major | explicit X.Y.Z")
    b.add_argument("--dry-run", action="store_true", help="run the checks and show the new version, write nothing")
    b.add_argument(
        "--trailer",
        action="append",
        default=[],
        metavar="TEXT",
        help='trailer for the release commit, e.g. "Co-Authored-By: Name <email>" (repeatable)',
    )
    sub.add_parser("check", help="verify pyproject.toml and CITATION.cff agree (for CI)")
    args = parser.parse_args()
    if args.cmd == "check":
        return check()
    return bump(args.spec, args.dry_run, args.trailer)


if __name__ == "__main__":
    raise SystemExit(main())
