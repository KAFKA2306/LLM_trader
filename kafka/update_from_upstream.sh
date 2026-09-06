#!/usr/bin/env bash
set -euo pipefail

UPSTREAM_URL="${UPSTREAM_URL:-https://github.com/qrak/LLM_trader.git}"
WORK_BRANCH="${WORK_BRANCH:-master}"
MIRROR_BRANCH="${MIRROR_BRANCH:-upstream}"
LEGACY_ALIAS_BRANCH="${LEGACY_ALIAS_BRANCH:-kafka}"

if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: working tree is not clean."
  exit 2
fi

current_branch="$(git branch --show-current)"
if [ "$current_branch" != "$WORK_BRANCH" ]; then
  echo "ERROR: run this script on $WORK_BRANCH, current=$current_branch"
  exit 3
fi

if git remote get-url upstream >/dev/null 2>&1; then
  git remote set-url upstream "$UPSTREAM_URL"
else
  git remote add upstream "$UPSTREAM_URL"
fi

git fetch upstream master
git fetch origin "$MIRROR_BRANCH" "$LEGACY_ALIAS_BRANCH" 2>/dev/null || true

local_head="$(git rev-parse HEAD)"
upstream_sha="$(git rev-parse upstream/master)"
preserve_file="$(mktemp)"
trap 'rm -f "$preserve_file"' EXIT

git ls-tree -r --name-only "$local_head" | while IFS= read -r path; do
  lower="$(printf '%s' "$path" | tr '[:upper:]' '[:lower:]')"
  case "$lower" in
    *.md)
      printf '%s\n' "$path"
      ;;
    kafka/*)
      printf '%s\n' "$path"
      ;;
    .github/workflows/kafka-*.yml|.github/workflows/kafka-*.yaml|.github/workflows/upstream-sync.yml|.github/workflows/upstream-sync.yaml)
      printf '%s\n' "$path"
      ;;
  esac
done > "$preserve_file"

git read-tree --reset -u "$upstream_sha"

git ls-files -z | while IFS= read -r -d '' path; do
  lower="$(printf '%s' "$path" | tr '[:upper:]' '[:lower:]')"
  case "$lower" in
    *.md)
      git rm -q -f -- "$path"
      ;;
  esac
done

while IFS= read -r path; do
  [ -n "$path" ] || continue
  git checkout "$local_head" -- "$path"
done < "$preserve_file"

git add -A

if git diff --cached --quiet; then
  echo "No downstream tree change after overlay."
else
  git commit -m "chore(sync): import upstream non-Markdown snapshot $upstream_sha"
fi

new_head="$(git rev-parse HEAD)"

git push --force-with-lease origin "$upstream_sha:refs/heads/$MIRROR_BRANCH"
git push origin "$WORK_BRANCH"
git push --force-with-lease origin "$new_head:refs/heads/$LEGACY_ALIAS_BRANCH"

echo "OK"
echo "upstream=$upstream_sha"
echo "master=$new_head"
echo "Markdown preserved from KAFKA branch."
