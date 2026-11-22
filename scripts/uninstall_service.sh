#!/usr/bin/env bash
# Stop and remove the Pantry service and its auto-update timer. Keeps /etc/pantry.env and all data.

set -euo pipefail

SERVICE=pantry

sudo systemctl disable --now "${SERVICE}-update.timer" 2>/dev/null || true
sudo systemctl disable --now "${SERVICE}.service" 2>/dev/null || true
sudo rm -f /etc/systemd/system/${SERVICE}.service \
           /etc/systemd/system/${SERVICE}-update.service \
           /etc/systemd/system/${SERVICE}-update.timer
sudo systemctl daemon-reload
echo "Removed ${SERVICE} service and update timer. Env file kept at /etc/pantry.env."
