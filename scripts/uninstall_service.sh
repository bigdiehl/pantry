#!/usr/bin/env bash
# Stop and remove the recipe app systemd service. Keeps /etc/recipes_app.env and all data.

set -euo pipefail

SERVICE=recipes
sudo systemctl disable --now "$SERVICE" 2>/dev/null || true
sudo rm -f "/etc/systemd/system/${SERVICE}.service"
sudo systemctl daemon-reload
echo "Removed ${SERVICE}.service. Env file kept at /etc/recipes_app.env."
