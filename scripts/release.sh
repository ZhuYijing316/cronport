#!/usr/bin/env bash
# Publish a new release of cronport: PyPI, the git tag and the GitHub
# release, in one command.
#
#   ./scripts/release.sh 0.1.0
#
# You need two tokens in the environment:
#
#   export TWINE_USERNAME=ZhuYijing316
#   export TWINE_PASSWORD=pypi-...          # from https://pypi.org/manage/account/token/
#   export GITHUB_TOKEN=github_pat_...       # a PAT with the 'repo' scope
#
# Before you run it, update the version in pyproject.toml and add a section
# for it at the top of CHANGELOG.md.  The script checks both and stops if
# they do not match.
set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "usage: $0 <version>" >&2
  echo "example: $0 0.1.0" >&2
  exit 2
fi

cd "$(dirname "$0")/.."

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
fail() { printf '\033[1;31m%s\033[0m\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------- checks

step "checking that everything is in order"

grep -q "^version = \"${VERSION}\"" pyproject.toml || fail \
  "pyproject.toml does not say version = \"${VERSION}\" -- update it first"

grep -q "^## \[${VERSION}\]" CHANGELOG.md || fail \
  "CHANGELOG.md has no section for ${VERSION} -- add one first"

if [[ -n "$(git status --porcelain)" ]]; then
  fail "there are uncommitted changes -- commit them first"
fi

if git rev-parse "v${VERSION}" >/dev/null 2>&1; then
  fail "the tag v${VERSION} already exists"
fi

command -v python >/dev/null || fail "python is not on the PATH"
command -v twine >/dev/null || fail "twine is not installed -- run: pip install twine build"

if [[ -z "${TWINE_PASSWORD:-}" ]]; then
  fail "TWINE_PASSWORD is not set -- see the comment at the top of this script"
fi

# ---------------------------------------------------------------- release

step "running the tests"
python -m pytest -q || fail "the tests failed"

step "building the distributions"
rm -rf dist
python -m build || fail "the build failed"

step "checking the distributions"
python -m twine check dist/* || fail "twine check failed"

step "uploading to PyPI"
python -m twine upload dist/* || fail "the upload failed"

step "tagging"
git tag -a "v${VERSION}" -m "v${VERSION}"
git push origin "v${VERSION}" || fail "pushing the tag failed"

# -------------------------------------------------------------- github

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  step "creating the GitHub release"
  NOTES=$(python - "$VERSION" <<'PY'
import re
import sys

version = sys.argv[1]
text = open("CHANGELOG.md", encoding="utf-8").read()
match = re.search(
    rf"^## \[{re.escape(version)}\].*?$(.*?)(?=^## \[|\Z)",
    text,
    re.MULTILINE | re.DOTALL,
)
print(match.group(1).strip() if match else f"Release {version}")
PY
)
  RESPONSE=$(curl -sS -w '\n%{http_code}' \
    -X POST \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/${GITHUB_USER:-ZhuYijing316}/cronport/releases" \
    -d "$(python - "$VERSION" "$NOTES" <<'PY'
import json
import sys

version, notes = sys.argv[1], sys.argv[2]
print(json.dumps({"tag_name": f"v{version}", "name": f"v{version}", "body": notes}))
PY
)")
  STATUS=$(printf '%s' "$RESPONSE" | tail -n1)
  if [[ "$STATUS" != "201" ]]; then
    printf '%s\n' "$RESPONSE"
    fail "creating the GitHub release failed (HTTP ${STATUS})"
  fi
  echo "created the release"
else
  echo
  echo "GITHUB_TOKEN is not set, so the GitHub release was skipped."
  echo "Create it by hand:"
  echo "  https://github.com/${GITHUB_USER:-ZhuYijing316}/cronport/releases/new"
fi

printf '\n\033[1;32m==> v%s is out\033[0m\n' "$VERSION"
echo "  PyPI:           https://pypi.org/project/cronport/${VERSION}/"
echo "  GitHub release: https://github.com/${GITHUB_USER:-ZhuYijing316}/cronport/releases/tag/v${VERSION}"
echo
echo "Announce it: see LAUNCH.md for the Hacker News, Reddit and"
echo "Chinese community posts, ready to copy and paste."
