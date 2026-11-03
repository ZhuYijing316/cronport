#!/usr/bin/env bash
# Build a release and publish it to PyPI.
#
#   ./scripts/release.sh 0.2.0
#
# You need a PyPI API token in the environment:
#   export TWINE_USERNAME=__GITHUB_USER__
#   export TWINE_PASSWORD=pypi-...
set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "usage: $0 <version>" >&2
  exit 2
fi

cd "$(dirname "$0")/.."

if ! grep -q "^version = \"${VERSION}\"" pyproject.toml; then
  echo "pyproject.toml does not say version = \"${VERSION}\"" >&2
  echo "update it first, then update CHANGELOG.md" >&2
  exit 1
fi

echo "==> running the checks"
make check

echo "==> building"
rm -rf dist
python -m build

echo "==> checking the distributions"
python -m twine check dist/*

echo "==> uploading to PyPI"
python -m twine upload dist/*

echo
echo "Done. Now create the GitHub release:"
echo "  git tag -a v${VERSION} -m 'v${VERSION}'"
echo "  git push origin v${VERSION}"
echo "  gh release create v${VERSION} --generate-notes"
