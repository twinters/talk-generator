#!/usr/bin/env python3
"""Release helper for talkgenerator.

Commands
--------
  uv run python scripts/release.py bump <patch|minor|major|X.Y.Z> [--dry-run]
      Prepare a release, locally and reversibly:
        * set the new version in pyproject.toml (via ``uv version``)
        * sync CITATION.cff (version + date-released)
        * roll the [Unreleased] section of CHANGELOG.md into a dated section
        * refresh uv.lock
        * commit those files and create the annotated tag vX.Y.Z
      It then PRINTS the commands that actually publish (push + GitHub release);
      it never pushes or publishes by itself. ``--dry-run`` previews the version
      change and writes nothing.

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


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True, text=True)


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


def sync_citation(version: str, today: str) -> None:
    text = CITATION.read_text(encoding="utf-8")
    text = re.sub(r"^version:.*$", f"version: {version}", text, count=1, flags=re.MULTILINE)
    text = re.sub(r"^date-released:.*$", f'date-released: "{today}"', text, count=1, flags=re.MULTILINE)
    CITATION.write_text(text, encoding="utf-8")


def roll_changelog(version: str, today: str) -> str:
    text = CHANGELOG.read_text(encoding="utf-8")
    m = re.search(r"## \[Unreleased\]\n(?P<body>.*?)(?=\n## \[|\Z)", text, re.DOTALL)
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


def bump(spec: str, dry_run: bool) -> int:
    current = pyproject_version()
    target = next_version(current, spec)
    today = date.today().isoformat()
    print(f"current: {current}\ntarget:  {target}\ndate:    {today}")
    if dry_run:
        print("\n--dry-run: nothing written, committed or tagged.")
        return 0

    run("uv", "version", target)
    got = pyproject_version()
    if got != target:
        sys.exit(f"uv set the version to {got!r}, expected {target!r}; aborting")
    sync_citation(target, today)
    body = roll_changelog(target, today)
    run("uv", "lock")
    NOTES.write_text((body or f"talkgenerator {target}.") + "\n", encoding="utf-8")

    run("git", "add", "pyproject.toml", "uv.lock", "CITATION.cff", "CHANGELOG.md")
    run("git", "commit", "-m", f"Release {target}")
    run("git", "tag", "-a", f"v{target}", "-m", f"talkgenerator {target}")

    print(
        "\n".join(
            [
                f"\nPrepared v{target}: committed and tagged locally, nothing pushed.",
                "",
                "Publish it:",
                "  git branch -f master HEAD                     # point master at the release (when on dev)",
                "  git push origin HEAD master --follow-tags     # push the branch, master and the tag",
                f'  gh release create v{target} --verify-tag --title "talkgenerator {target}" --notes-file .release-notes.md',
                "",
                "Publishing the GitHub release builds, tests and uploads to PyPI (after your approval).",
                f"Undo before pushing:  git tag -d v{target} && git reset --hard HEAD~1",
            ]
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and verify talkgenerator releases.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bump", help="prepare a release (version, changelog, tag)")
    b.add_argument("spec", help="patch | minor | major | explicit X.Y.Z")
    b.add_argument("--dry-run", action="store_true", help="preview the version change, write nothing")
    sub.add_parser("check", help="verify pyproject.toml and CITATION.cff agree (for CI)")
    args = parser.parse_args()
    if args.cmd == "check":
        return check()
    return bump(args.spec, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
