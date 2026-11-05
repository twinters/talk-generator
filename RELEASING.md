# Releasing talkgenerator

Releases go to [PyPI](https://pypi.org/project/talkgenerator/) through the `Release` workflow
(`.github/workflows/release.yml`), using PyPI's
[trusted publishing](https://docs.pypi.org/trusted-publishers/): GitHub Actions proves to PyPI
that it runs this repository's workflow, so no API token needs to be stored anywhere.

## One-time setup

1. **PyPI**: sign in with an account that is an *Owner* of the `talkgenerator` project, open
   *Your projects → talkgenerator → Manage → Publishing*, and add a GitHub publisher:
   - Owner: `twinters`
   - Repository: `talk-generator`
   - Workflow: `release.yml`
   - Environment: `pypi`
2. **TestPyPI** (optional, for dry runs): do the same on [test.pypi.org](https://test.pypi.org/)
   with environment `testpypi`. If the project doesn't exist there yet, add it as a *pending*
   publisher (*Your account → Publishing*) with project name `talkgenerator`.
3. **GitHub**: create the environments `pypi` and `testpypi` under *Settings → Environments*.
   Adding yourself as a required reviewer on `pypi` means every upload waits for your approval.

## Releasing a version

Releases are cut from `master`. Everything up to the push is one command:

```sh
uv run python scripts/release.py bump patch    # or: minor | major | an explicit 4.2.0
```

It first checks that there are no uncommitted changes, that `master` isn't behind GitHub,
that the tag is still free (locally and on GitHub) and that `CHANGELOG.md` has an
`[Unreleased]` section, and stops before touching anything if one of those fails. Then it
bumps the version in `pyproject.toml`, keeps `CITATION.cff` in step, moves the
`[Unreleased]` notes in `CHANGELOG.md` into a dated section, refreshes `uv.lock`, and
commits and tags `vX.Y.Z`, all locally. `--dry-run` runs the checks and shows the new
version without changing anything. It then prints the two commands that publish:

```sh
git push --atomic origin HEAD refs/tags/vX.Y.Z   # the branch and the tag: both or neither
gh release create vX.Y.Z --verify-tag --title "talkgenerator X.Y.Z" --notes-file .release-notes.md
```

Publishing the GitHub release runs the workflow, which checks the tag matches the version,
runs the offline tests, builds the sdist and wheel, and waits for your approval before
uploading to PyPI. CI runs `release.py check` so `CITATION.cff` and `pyproject.toml` can't
drift apart. To rehearse the upload itself, *Actions → Release → Run workflow* uploads to
TestPyPI (needs the test.pypi.org publisher from the setup above).

PyPI never accepts the same version twice, so a fix after a release needs a new version number.

## Branches

`master` is the released 4.x line: fixes and Dependabot updates land there, and every
release is a tag on it. Bigger work, like the v5 overhaul, happens on its own branch and
merges into `master` when it's ready to ship. talkgenerator.com stays stable because it
pins a released version from PyPI, not because of a branch.
