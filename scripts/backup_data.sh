#!/usr/bin/env bash
# Commit and push recipe edits made through the web app to the diehl_recipes repo.
# Run by pantry-backup.timer as the service user. Does nothing if there are no changes.
#
#   scripts/backup_data.sh --data-dir DIR
#
# Manual run: sudo systemctl start pantry-backup && journalctl -u pantry-backup -n 20

set -euo pipefail

DATA_DIR=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --data-dir) DATA_DIR="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done
[[ -n "$DATA_DIR" && -d "$DATA_DIR/.git" ]] || { echo "--data-dir must be a git repo" >&2; exit 1; }
cd "$DATA_DIR"

# Commits need an identity; fall back to a generic one if git has none configured.
GIT=(git)
git config user.email >/dev/null || GIT+=(-c user.name="Pantry" -c user.email="pantry@$(hostname)")

git add -A
if git diff --cached --quiet; then
    echo "No recipe changes to back up."
else
    summary="$(git diff --cached --name-only | cut -d/ -f2,3 | sort -u | head -20 | sed 's/^/- /')"
    count="$(git diff --cached --name-only | wc -l)"
    "${GIT[@]}" commit -q -m "Backup from $(hostname) $(date +%F): $count file(s) changed" -m "$summary"
    echo "Committed $count changed file(s)."
fi

# Push anything not yet on the remote (including commits from a previous failed push).
git fetch -q origin
if [[ -n "$(git rev-list '@{u}..HEAD')" ]]; then
    # Someone pushed to GitHub directly: replay our commits on top of theirs.
    if [[ -n "$(git rev-list 'HEAD..@{u}')" ]]; then
        "${GIT[@]}" rebase -q '@{u}' || { git rebase --abort; echo "Rebase conflict; resolve by hand in $DATA_DIR." >&2; exit 1; }
    fi
    git push -q origin HEAD
    echo "Pushed to $(git remote get-url origin)."
else
    echo "Remote is up to date."
fi
