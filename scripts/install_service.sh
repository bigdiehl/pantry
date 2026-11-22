#!/usr/bin/env bash
# Install Pantry as a systemd service on this machine, plus a timer that
# auto-deploys new commits (see scripts/auto_update.sh).
# Run as the user who should own the service (not root). Safe to re-run.
#
#   scripts/install_service.sh [--port 5000] [--data-dir DIR] [--data-repo URL] [--update-interval 5min]
#
# Recipe data comes from the diehl_recipes repo, cloned next to this one by default.

set -euo pipefail

SERVICE=pantry
PORT=5000
DATA_REPO=git@github.com:bigdiehl/diehl_recipes.git
ENV_FILE=/etc/pantry.env
LEGACY_ENV_FILES=(/etc/recipes_app.env)
LEGACY_UNITS=(web_app frank_web_server recipes)
UPDATE_INTERVAL=5min
UNIT_DIR=/etc/systemd/system
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_USER="$(id -un)"
DATA_DIR="$(dirname "$REPO_DIR")/diehl_recipes"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port) PORT="$2"; shift 2 ;;
        --data-dir) DATA_DIR="$2"; shift 2 ;;
        --data-repo) DATA_REPO="$2"; shift 2 ;;
        --update-interval) UPDATE_INTERVAL="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if [[ $EUID -eq 0 ]]; then
    echo "Run as the service user, not root. sudo is used where needed." >&2
    exit 1
fi

step() { printf '\n==> %s\n' "$*"; }

step "System packages (WeasyPrint needs Pango)"
if command -v apt-get >/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq curl git libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0
else
    echo "Not a Debian/Ubuntu system. Install Pango and curl manually."
fi

step "uv"
if ! command -v uv >/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
uv --version
UV_DIR="$(dirname "$(command -v uv)")"

step "Python dependencies"
cd "$REPO_DIR"
uv sync --frozen   # includes pytest: auto_update.sh runs the tests before deploying
mkdir -p web/instance output

step "Recipe data ($DATA_DIR)"
if [[ -d "$DATA_DIR/recipes" ]]; then
    echo "Exists."
else
    git clone "$DATA_REPO" "$DATA_DIR"
fi
mkdir -p "$DATA_DIR/recipes/pending" "$DATA_DIR/recipes/archived"

step "Environment file ($ENV_FILE)"
for legacy in "${LEGACY_ENV_FILES[@]}"; do
    if ! sudo test -f "$ENV_FILE" && sudo test -f "$legacy"; then
        echo "Migrating $legacy"
        sudo cp "$legacy" "$ENV_FILE"
        for kv in "RECIPES_DEBUG=0" "RECIPES_PORT=${PORT}" "RECIPES_DATA_DIR=${DATA_DIR}"; do
            sudo grep -q "^${kv%%=*}=" "$ENV_FILE" || echo "$kv" | sudo tee -a "$ENV_FILE" >/dev/null
        done
        sudo chown "root:${RUN_USER}" "$ENV_FILE"
        sudo chmod 640 "$ENV_FILE"
    fi
done
if sudo test -f "$ENV_FILE"; then
    # systemd EnvironmentFile ignores "export KEY=..." lines; strip the prefix.
    if sudo grep -q '^export ' "$ENV_FILE"; then
        echo "Stripping 'export ' prefixes (systemd ignores those lines)."
        sudo sed -i 's/^export //' "$ENV_FILE"
    fi
    echo "Exists."
else
    SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    sudo tee "$ENV_FILE" >/dev/null <<EOF
# Pantry environment. Edit, then: sudo systemctl restart ${SERVICE}
FLASK_SECRET_KEY=${SECRET}
RECIPES_DEBUG=0
RECIPES_PORT=${PORT}
RECIPES_DATA_DIR=${DATA_DIR}

# Email (shopping list emails, weekly schedule)
#GMAIL_SENDER=you@gmail.com
#GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Recipe import
#GEMINI_API_KEY=
EOF
    sudo chown "root:${RUN_USER}" "$ENV_FILE"
    sudo chmod 640 "$ENV_FILE"
    echo "Created. Add email/Gemini keys to enable those features."
fi

step "systemd units"
sudo tee "${UNIT_DIR}/${SERVICE}.service" >/dev/null <<EOF
[Unit]
Description=Pantry recipe web app
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${REPO_DIR}/.venv/bin/python web/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo tee "${UNIT_DIR}/${SERVICE}-update.service" >/dev/null <<EOF
[Unit]
Description=Pull and deploy new Pantry commits
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
Environment=PATH=${UV_DIR}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=${REPO_DIR}/scripts/auto_update.sh --user ${RUN_USER} --repo ${REPO_DIR} --data-dir ${DATA_DIR} --service ${SERVICE} --port ${PORT}
EOF

sudo tee "${UNIT_DIR}/${SERVICE}-update.timer" >/dev/null <<EOF
[Unit]
Description=Check for new Pantry commits every ${UPDATE_INTERVAL}

[Timer]
OnBootSec=2min
OnUnitActiveSec=${UPDATE_INTERVAL}

[Install]
WantedBy=timers.target
EOF

# Retire older hand-installed units.
for unit in "${LEGACY_UNITS[@]}"; do
    [[ "$unit" == "$SERVICE" ]] && continue
    if [[ -n "$(systemctl list-unit-files "${unit}.service" --no-legend 2>/dev/null)" ]]; then
        echo "Retiring ${unit}.service"
        sudo systemctl disable --now "${unit}.service" 2>/dev/null || true
    fi
done

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE" >/dev/null
sudo systemctl restart "$SERVICE"
sudo systemctl enable --now "${SERVICE}-update.timer" >/dev/null

step "Health check"
PORT="$(sudo sed -n 's/^RECIPES_PORT=//p' "$ENV_FILE" | tail -1)"
PORT="${PORT:-5000}"
for _ in $(seq 1 20); do
    if curl -fsS -o /dev/null "http://localhost:${PORT}/"; then
        echo "Running at http://$(hostname):${PORT}/"
        echo "Logs:        journalctl -u ${SERVICE} -f"
        echo "Deploy logs: journalctl -u ${SERVICE}-update"
        echo "For phone install (needs HTTPS): scripts/setup_tailscale.sh"
        exit 0
    fi
    sleep 1
done
echo "Service did not respond. Check: journalctl -u ${SERVICE} -n 50" >&2
exit 1
