#!/usr/bin/env bash
set -euo pipefail

UPSTREAM_URL="https://github.com/qrak/LLM_trader.git"

if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: working tree is not clean."
  exit 2
fi

if ! git remote get-url upstream >/dev/null 2>&1; then
  git remote add upstream "$UPSTREAM_URL"
fi

git fetch origin master kafka
git fetch upstream master

if [ "$(git rev-list --count upstream/master..origin/master)" -ne 0 ]; then
  echo "ERROR: origin/master contains commits not present in upstream/master."
  echo "Refusing to overwrite mirror history."
  exit 3
fi

if ! git merge-base --is-ancestor origin/master upstream/master; then
  echo "ERROR: origin/master cannot fast-forward to upstream/master."
  exit 4
fi

git switch master
git merge --ff-only upstream/master
git push origin master

git switch kafka
if ! git merge --no-edit master; then
  git merge --abort || true
  echo "ERROR: upstream merge conflict. No automatic conflict resolution was attempted."
  exit 5
fi

changed="$(git diff --name-only master...kafka)"
invalid="$(printf '%s\n' "$changed" | grep -Ev '^(kafka/|KAFKA_DOWNSTREAM\.md$|\.github/workflows/kafka-[^/]+\.ya?ml$)' || true)"

if [ -n "$invalid" ]; then
  echo "ERROR: downstream branch modifies upstream-owned paths:"
  printf '%s\n' "$invalid"
  exit 6
fi

git push origin kafka

echo "OK: master mirrors upstream and kafka contains only downstream-owned changes."
