#!/usr/bin/env bash
# Deploy new commits pushed to the tracked branch. Run by pantry-update.timer as root;
# git/uv/pytest run as the service user.
#
#   1. Fast-forward the data repo (restart if it changed).
#   2. Fetch the app repo. If upstream moved: fast-forward, uv sync, run tests.
#      Tests pass -> restart the service. Tests fail -> roll back and skip that commit.
#
# Manual run: sudo systemctl start pantry-update && journalctl -u pantry-update -n 30

set -euo pipefail

RUN_USER=""; REPO_DIR=""; DATA_DIR=""; SERVICE=pantry; PORT=5000
while [[ $# -gt 0 ]]; do
    case "$1" in
        --user) RUN_USER="$2"; shift 2 ;;
        --repo) REPO_DIR="$2"; shift 2 ;;
        --data-dir) DATA_DIR="$2"; shift 2 ;;
        --service) SERVICE="$2"; shift 2 ;;
        --port) PORT="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done
[[ -n "$RUN_USER" && -n "$REPO_DIR" ]] || { echo "--user and --repo are required" >&2; exit 1; }

USER_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
as_user() { runuser -u "$RUN_USER" -- env HOME="$USER_HOME" PATH="$PATH" "$@"; }
BAD_FILE="$REPO_DIR/web/instance/.bad_commits"
restart=0

# --- Data repo ---------------------------------------------------------------
if [[ -n "$DATA_DIR" && -d "$DATA_DIR/.git" ]]; then
    before="$(as_user git -C "$DATA_DIR" rev-parse HEAD)"
    if as_user git -C "$DATA_DIR" pull --ff-only -q; then
        after="$(as_user git -C "$DATA_DIR" rev-parse HEAD)"
        if [[ "$before" != "$after" ]]; then
            echo "Data repo: ${before:0:7} -> ${after:0:7}"
            restart=1
        fi
    else
        echo "Data repo: pull --ff-only failed (local edits or diverged); skipping." >&2
    fi
fi

# --- App repo ----------------------------------------------------------------
cd "$REPO_DIR"
as_user git fetch -q origin
current="$(as_user git rev-parse HEAD)"
target="$(as_user git rev-parse '@{u}')"

if [[ "$current" != "$target" ]]; then
    if [[ -f "$BAD_FILE" ]] && grep -qx "$target" "$BAD_FILE"; then
        echo "App: ${target:0:7} previously failed tests; waiting for a newer commit."
    else
        echo "App: ${current:0:7} -> ${target:0:7}"
        as_user git merge --ff-only -q "$target"
        if as_user uv sync --frozen -q && as_user uv run --frozen pytest -q; then
            restart=1
        else
            echo "App: tests failed on ${target:0:7}; rolling back to ${current:0:7}." >&2
            as_user git reset -q --hard "$current"
            as_user uv sync --frozen -q
            echo "$target" | as_user tee -a "$BAD_FILE" >/dev/null
            exit 1
        fi
    fi
fi

# --- Restart -----------------------------------------------------------------
if [[ "$restart" -eq 1 ]]; then
    systemctl restart "$SERVICE"
    for _ in $(seq 1 20); do
        if curl -fsS -o /dev/null "http://localhost:${PORT}/"; then
            echo "Deployed: app $(as_user git rev-parse --short HEAD), service healthy."
            exit 0
        fi
        sleep 1
    done
    echo "Service did not come back after restart. Check: journalctl -u $SERVICE -n 50" >&2
    exit 1
fi
