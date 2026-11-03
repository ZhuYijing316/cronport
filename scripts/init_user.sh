#!/usr/bin/env bash
# Replace the placeholder with your GitHub username.
#
#   ./scripts/init_user.sh your-username
#
# Run this once, right after you clone the repository.
#
# The placeholder is assembled from two pieces on purpose: that way this
# script never rewrites itself and stays usable more than once.
set -euo pipefail

USERNAME="${1:-}"
if [[ -z "$USERNAME" ]]; then
  echo "usage: $0 <github-username>" >&2
  exit 2
fi

if ! [[ "$USERNAME" =~ ^[A-Za-z0-9-]+$ ]]; then
  echo "that does not look like a GitHub username: $USERNAME" >&2
  exit 2
fi

PLACEHOLDER="__GITHUB""_USER__"

cd "$(dirname "$0")/.."

FILES=$(grep -rl "$PLACEHOLDER" . \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=dist \
  --exclude-dir=build \
  --exclude="$(basename "$0")" \
  || true)

if [[ -z "$FILES" ]]; then
  echo "no placeholders left, nothing to do"
  exit 0
fi

while IFS= read -r file; do
  sed -i "s/${PLACEHOLDER}/${USERNAME}/g" "$file"
  echo "updated ${file}"
done <<< "$FILES"

echo
echo "Done. Check the result with:"
echo "  grep -rn '$PLACEHOLDER' . --exclude-dir=.git || echo '  no placeholders left'"
