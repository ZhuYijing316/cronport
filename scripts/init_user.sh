#!/usr/bin/env bash
# Replace the __GITHUB_USER__ placeholder with your GitHub username.
#
#   ./scripts/init_user.sh your-username
#
# Run this once, right after you clone the repository.
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

cd "$(dirname "$0")/.."

FILES=$(grep -rl '__GITHUB_USER__' . --exclude-dir=.git --exclude-dir=.venv || true)
if [[ -z "$FILES" ]]; then
  echo "no placeholders left, nothing to do"
  exit 0
fi

while IFS= read -r file; do
  sed -i "s/__GITHUB_USER__/${USERNAME}/g" "$file"
  echo "updated ${file}"
done <<< "$FILES"

echo
echo "Done. Check the result with:"
echo "  grep -rn '__GITHUB_USER__' . --exclude-dir=.git || echo '  no placeholders left'"
