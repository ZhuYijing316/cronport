#!/usr/bin/env bash
# Connect this repository to GitHub and push it, for the first time.
#
#   ./scripts/first_publish.sh
#
# It works out whether you can use SSH (you already have a key) or whether
# it should use HTTPS (you paste a personal access token instead), sets the
# git identity if it is missing, adds the remote and pushes.
#
# Run it from the repository root:
#
#   cd cronport
#   ./scripts/first_publish.sh
set -euo pipefail

GITHUB_USER="${GITHUB_USER:-ZhuYijing316}"
BRANCH="main"

cd "$(dirname "$0")/.."

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
hint() { printf '\033[90m    %s\033[0m\n' "$1"; }
fail() { printf '\n\033[1;31m%s\033[0m\n' "$1" >&2; exit 1; }

command -v git >/dev/null || fail "git is not installed. Install it from https://git-scm.com/downloads"

step "checking the repository"
if [[ ! -d .git ]]; then
  fail "this is not a git repository -- unzip the archive first and run this from inside the cronport folder"
fi
hint "branch: $(git rev-parse --abbrev-ref HEAD), commits: $(git rev-list --count HEAD)"

# ---------------------------------------------------------------- identity

step "checking the git identity"
if git config user.name >/dev/null 2>&1 && git config user.email >/dev/null 2>&1; then
  hint "already set to $(git config user.name) <$(git config user.email)>"
else
  git config user.name "${GITHUB_USER}"
  git config user.email "${GITHUB_USER}@users.noreply.github.com"
  hint "set to ${GITHUB_USER} <${GITHUB_USER}@users.noreply.github.com>"
fi

# ---------------------------------------------------------------- transport

step "working out how to connect"

HAS_SSH=0
for key in "$HOME/.ssh/id_ed25519" "$HOME/.ssh/id_rsa"; do
  if [[ -f "$key" ]]; then
    HAS_SSH=1
    hint "found an SSH key: $key"
  fi
done

if [[ "$HAS_SSH" == "1" ]]; then
  REMOTE="git@github.com:${GITHUB_USER}/cronport.git"
  hint "using SSH"
else
  REMOTE="https://github.com/${GITHUB_USER}/cronport.git"
  hint "using HTTPS with a personal access token"
  cat <<'EOF'

    No SSH key found, so this will ask you for two things:
      Username : your GitHub username
      Password : a personal access token (NOT your GitHub password)

    Create a token here:  https://github.com/settings/tokens
      -> Generate new token (classic)
      -> tick the "repo" box
      -> Generate token
      -> copy the ghp_... string (it is shown only once)

EOF
fi

# ---------------------------------------------------------------- remote

step "checking the remote"
if git remote get-url origin >/dev/null 2>&1; then
  CURRENT=$(git remote get-url origin)
  if [[ "$CURRENT" == "$REMOTE" ]]; then
    hint "origin is already $CURRENT"
  else
    hint "origin currently points at $CURRENT"
    read -r -p "    Change it to $REMOTE? [y/N] " answer
    if [[ "${answer,,}" == "y" ]]; then
      git remote set-url origin "$REMOTE"
      hint "updated"
    fi
  fi
else
  git remote add origin "$REMOTE"
  hint "added origin -> $REMOTE"
fi

# ---------------------------------------------------------------- push

step "pushing to GitHub"
if git push -u origin "$BRANCH"; then
  printf '\n\033[1;32m==> pushed\033[0m\n'
else
  printf '\n\033[1;31m==> the push did not work\033[0m\n'
  cat <<'EOF'

    Common reasons:

    * "could not read Username" -- GitHub no longer accepts a password for
      git operations. Paste a personal access token instead.
    * "Permission denied (publickey)" -- SSH is not set up. Delete the
      remote and run this script again, it will fall back to HTTPS:
          git remote set-url origin https://github.com/ZhuYijing316/cronport.git
    * "repository not found" -- the repository does not exist on GitHub yet.
      Create it first:  https://github.com/new   (name it exactly "cronport",
      make it public, and do NOT tick "Add a README")

EOF
  exit 1
fi

# ---------------------------------------------------------------- next

cat <<'EOF'

==> next

  1. Open https://github.com/ZhuYijing316/cronport
     It should show your 5 commits and the README with the demo animation.

  2. Go to Settings -> Pages, set Source to "main / root", save.
     Your README will then also be readable at:
     https://ZhuYijing316.github.io/cronport/

  3. Publish to PyPI and GitHub Releases with one command:
       export TWINE_USERNAME=ZhuYijing316
       export TWINE_PASSWORD=pypi-...
       export GITHUB_TOKEN=github_pat_...
       ./scripts/release.sh 0.1.0

  4. Read LAUNCH.md and announce it.

EOF
