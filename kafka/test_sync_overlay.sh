#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
SYNC_SCRIPT="$ROOT/kafka/update_from_upstream.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git_init_work() {
  local dir="$1"
  git init -q -b master "$dir"
  git -C "$dir" config user.name "sync-test"
  git -C "$dir" config user.email "sync-test@example.invalid"
}

# Build initial upstream.
git_init_work "$TMP/upstream-work"
cat > "$TMP/upstream-work/README.md" <<'EOF'
upstream readme v1
EOF
cat > "$TMP/upstream-work/OLD.md" <<'EOF'
upstream old md
EOF
cat > "$TMP/upstream-work/code.py" <<'EOF'
VALUE = 1
EOF
cat > "$TMP/upstream-work/delete_me.py" <<'EOF'
DELETE_ME = True
EOF
git -C "$TMP/upstream-work" add -A
git -C "$TMP/upstream-work" commit -qm "upstream v1"
git clone -q --bare "$TMP/upstream-work" "$TMP/upstream.git"

# Build downstream origin from v1.
git clone -q --bare "$TMP/upstream-work" "$TMP/origin.git"
git clone -q "$TMP/origin.git" "$TMP/downstream"
git -C "$TMP/downstream" config user.name "sync-test"
git -C "$TMP/downstream" config user.email "sync-test@example.invalid"

mkdir -p "$TMP/downstream/kafka" "$TMP/downstream/docs"
cp "$SYNC_SCRIPT" "$TMP/downstream/kafka/update_from_upstream.sh"
cat > "$TMP/downstream/README.md" <<'EOF'
日本語 README
EOF
cat > "$TMP/downstream/OLD.md" <<'EOF'
日本語で保持する旧文書
EOF
cat > "$TMP/downstream/docs/local.md" <<'EOF'
ローカル文書
EOF
cat > "$TMP/downstream/kafka/local.py" <<'EOF'
LOCAL = True
EOF
git -C "$TMP/downstream" add -A
git -C "$TMP/downstream" commit -qm "downstream owned files"
git -C "$TMP/downstream" push -q origin master

initial_downstream_sha="$(git -C "$TMP/downstream" rev-parse HEAD)"
initial_upstream_sha="$(git -C "$TMP/upstream-work" rev-parse HEAD)"
git -C "$TMP/downstream" branch upstream "$initial_upstream_sha"
git -C "$TMP/downstream" branch kafka "$initial_downstream_sha"
git -C "$TMP/downstream" push -q origin upstream kafka

# Upstream v2: change/add/delete Markdown and non-Markdown.
cat > "$TMP/upstream-work/README.md" <<'EOF'
upstream readme v2 SHOULD NOT APPEAR
EOF
cat > "$TMP/upstream-work/NEW.md" <<'EOF'
new upstream markdown SHOULD NOT APPEAR
EOF
rm "$TMP/upstream-work/OLD.md"
cat > "$TMP/upstream-work/code.py" <<'EOF'
VALUE = 2
EOF
cat > "$TMP/upstream-work/new_code.py" <<'EOF'
NEW = True
EOF
rm "$TMP/upstream-work/delete_me.py"
git -C "$TMP/upstream-work" add -A
git -C "$TMP/upstream-work" commit -qm "upstream v2"
git -C "$TMP/upstream-work" remote add bare "$TMP/upstream.git"
git -C "$TMP/upstream-work" push -q bare master

(
  cd "$TMP/downstream"
  UPSTREAM_URL="$TMP/upstream.git" bash kafka/update_from_upstream.sh
)

# Markdown must remain downstream-owned.
grep -qx '日本語 README' "$TMP/downstream/README.md"
grep -qx '日本語で保持する旧文書' "$TMP/downstream/OLD.md"
grep -qx 'ローカル文書' "$TMP/downstream/docs/local.md"
test ! -e "$TMP/downstream/NEW.md"

# Non-Markdown must follow upstream.
grep -qx 'VALUE = 2' "$TMP/downstream/code.py"
grep -qx 'NEW = True' "$TMP/downstream/new_code.py"
test ! -e "$TMP/downstream/delete_me.py"

# Downstream-owned code remains.
grep -qx 'LOCAL = True' "$TMP/downstream/kafka/local.py"

# Mirror and alias refs must be exact.
latest_upstream_sha="$(git -C "$TMP/upstream-work" rev-parse HEAD)"
master_sha="$(git -C "$TMP/downstream" rev-parse master)"
test "$(git --git-dir="$TMP/origin.git" rev-parse upstream)" = "$latest_upstream_sha"
test "$(git --git-dir="$TMP/origin.git" rev-parse master)" = "$master_sha"
test "$(git --git-dir="$TMP/origin.git" rev-parse kafka)" = "$master_sha"

# Re-running against the same upstream SHA must be a no-op.
before="$(git -C "$TMP/downstream" rev-parse HEAD)"
(
  cd "$TMP/downstream"
  UPSTREAM_URL="$TMP/upstream.git" bash kafka/update_from_upstream.sh
)
after="$(git -C "$TMP/downstream" rev-parse HEAD)"
test "$before" = "$after"

echo "sync overlay test: PASS"
