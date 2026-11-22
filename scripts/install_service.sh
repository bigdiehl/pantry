#!/usr/bin/env bash
# Install the recipe app as a systemd service on this machine.
# Run as the user who should own the service (not root). Safe to re-run.
#
#   scripts/install_service.sh [--port 5000] [--data-dir DIR] [--data-repo URL]
#
# Recipe data comes from the diehl_recipes repo, cloned next to this one by default.

set -euo pipefail

SERVICE=recipes
PORT=5000
DATA_REPO=git@github.com:bigdiehl/diehl_recipes.git
ENV_FILE=/etc/recipes_app.env
UNIT_FILE=/etc/systemd/system/${SERVICE}.service
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_USER="$(id -un)"
DATA_DIR="$(dirname "$REPO_DIR")/diehl_recipes"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port) PORT="$2"; shift 2 ;;
        --data-dir) DATA_DIR="$2"; shift 2 ;;
        --data-repo) DATA_REPO="$2"; shift 2 ;;
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

step "Python dependencies"
cd "$REPO_DIR"
uv sync --frozen --no-dev
mkdir -p web/instance output

step "Recipe data ($DATA_DIR)"
if [[ -d "$DATA_DIR/recipes" ]]; then
    echo "Exists."
else
    git clone "$DATA_REPO" "$DATA_DIR"
fi
mkdir -p "$DATA_DIR/recipes/pending" "$DATA_DIR/recipes/archived"

step "Environment file ($ENV_FILE)"
if sudo test -f "$ENV_FILE"; then
    echo "Exists, leaving it alone."
else
    SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    sudo tee "$ENV_FILE" >/dev/null <<EOF
# Recipe app environment. Edit, then: sudo systemctl restart ${SERVICE}
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

step "systemd unit ($UNIT_FILE)"
sudo tee "$UNIT_FILE" >/dev/null <<EOF
[Unit]
Description=Diehl Recipes web app
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

# Retire the old hand-installed unit if present.
if systemctl list-unit-files web_app.service >/dev/null 2>&1; then
    sudo systemctl disable --now web_app.service 2>/dev/null || true
fi

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE" >/dev/null
sudo systemctl restart "$SERVICE"

step "Health check"
PORT="$(sudo sed -n 's/^RECIPES_PORT=//p' "$ENV_FILE" | tail -1)"
PORT="${PORT:-5000}"
for _ in $(seq 1 20); do
    if curl -fsS -o /dev/null "http://localhost:${PORT}/"; then
        echo "Running at http://$(hostname):${PORT}/"
        echo "Logs: journalctl -u ${SERVICE} -f"
        echo "For phone install (needs HTTPS): scripts/setup_tailscale.sh"
        exit 0
    fi
    sleep 1
done
echo "Service did not respond. Check: journalctl -u ${SERVICE} -n 50" >&2
exit 1
