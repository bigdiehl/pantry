# Developer Documentation

How Pantry is designed and why. For running it, see the root `README.md`.

| Doc | Covers |
|-----|--------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, request flow, modules, background work, config |
| [DATA.md](DATA.md) | Recipe files, state.json, food registry, unit merging |
| [FRONTEND.md](FRONTEND.md) | Pages, navigation, view patterns, styling, client state |
| [PWA.md](PWA.md) | Service worker caching, offline behavior, push notifications |
| [AI.md](AI.md) | Gemini recipe import (URL, text, photo) and recipe chat |
| [WEEKLY_PLAN.md](WEEKLY_PLAN.md) | Scheduled auto-pick, reminders, email |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Server (frank), systemd units, auto-deploy, Tailscale, env vars |
| [API.md](API.md) | Route reference |

Project tracking lives in `working/TODO.md` and `working/NOTES.md`.

## Keeping these current

These docs describe the design as it is, not as it was. When a change alters
behavior, data formats, routes, caching, or deployment, update the matching doc
in the same commit. Delete sections that stop being true rather than annotating them.
