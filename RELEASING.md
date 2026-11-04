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

1. Set the version in `pyproject.toml` (e.g. `version = "4.0.0"`), run `uv lock`, and merge into `master`.
2. Optionally, rehearse: *Actions → Release → Run workflow* builds, tests and uploads to TestPyPI.
3. Create a GitHub release with tag `v4.0.0` (*Releases → Draft a new release*, target `master`).
   Publishing it runs the workflow, which checks that the tag matches the version, runs the
   offline tests, builds the sdist and wheel, and uploads them to PyPI.

PyPI never accepts the same version twice, so a fix after a release needs a new version number.
