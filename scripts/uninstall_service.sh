#!/usr/bin/env bash
# Stop and remove the Pantry service and its update/backup timers. Keeps /etc/pantry.env and all data.

set -euo pipefail

SERVICE=pantry

sudo systemctl disable --now "${SERVICE}-update.timer" 2>/dev/null || true
sudo systemctl disable --now "${SERVICE}-backup.timer" 2>/dev/null || true
sudo systemctl disable --now "${SERVICE}.service" 2>/dev/null || true
sudo rm -f /etc/systemd/system/${SERVICE}.service \
           /etc/systemd/system/${SERVICE}-update.service \
           /etc/systemd/system/${SERVICE}-update.timer \
           /etc/systemd/system/${SERVICE}-backup.service \
           /etc/systemd/system/${SERVICE}-backup.timer
sudo systemctl daemon-reload
echo "Removed ${SERVICE} service and timers. Env file kept at /etc/pantry.env."
