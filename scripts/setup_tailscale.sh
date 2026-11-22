#!/usr/bin/env bash
# Expose the recipe app over HTTPS on your tailnet via `tailscale serve`.
# PWAs need HTTPS to install and run offline; plain http://host:5000 will not work.
#
# Prerequisite (one time, in the Tailscale admin console > DNS):
#   enable MagicDNS and HTTPS Certificates.
#
#   scripts/setup_tailscale.sh [--port 5000]

set -euo pipefail

PORT=5000
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port) PORT="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if ! command -v tailscale >/dev/null; then
    curl -fsSL https://tailscale.com/install.sh | sh
fi

if ! tailscale status >/dev/null 2>&1; then
    sudo tailscale up
fi

# Persistent: survives reboots, proxies https://<host>.<tailnet>.ts.net -> localhost:PORT
sudo tailscale serve --bg "$PORT"

DNS_NAME="$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
echo
echo "App URL: https://${DNS_NAME}/"
echo "On your phone: install Tailscale, sign in, open the URL, then Add to Home Screen."
echo "Undo: sudo tailscale serve --https=443 off"
