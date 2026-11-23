# Deployment

## Layout on frank (Debian 12)

| Path | What |
|------|------|
| `~/samba_share/pantry` (= `/srv/samba_share/pantry`) | App checkout, tracks `origin/master` |
| `~/samba_share/diehl_recipes` | Data repo checkout |
| `/etc/pantry.env` | Secrets and settings, `root:sdiehl` 640 |
| `pantry/web/instance/` | `state.json`, VAPID keys, push subscriptions (not in git) |

## systemd units

Written by `scripts/install_service.sh` (idempotent; re-run after changing it):

| Unit | Does |
|------|------|
| `pantry.service` | `.venv/bin/python web/app.py` as the service user, `EnvironmentFile=/etc/pantry.env` |
| `pantry-update.timer` | Fires 2 min after boot, then every 5 min (`--update-interval`) |
| `pantry-update.service` | Oneshot, runs `scripts/auto_update.sh` as root |
| `pantry-backup.timer` | Weekly, `Sun 03:00` (`--backup-schedule`, systemd OnCalendar). `Persistent=true` catches up after downtime |
| `pantry-backup.service` | Oneshot, runs `scripts/backup_data.sh` as the service user |

The installer also migrates `/etc/recipes_app.env`, strips `export ` prefixes (systemd
ignores those lines), and disables older units (`frank_web_server`, `web_app`, `recipes`).

## Auto-deploy (`scripts/auto_update.sh`)

Pull-based, so frank needs no inbound access from GitHub.

```
data repo:  git pull --ff-only     changed -> restart
app repo:   git fetch; behind?
              fast-forward, uv sync --frozen, pytest
              pass -> restart, health check on localhost
              fail -> git reset --hard back, record commit in web/instance/.bad_commits,
                      skip it until a newer commit arrives
```

Git, uv, and pytest run as the service user (`runuser`, its SSH key); only the
restart needs root. Local edits that block a fast-forward are skipped with a warning.

```bash
sudo systemctl start pantry-update     # deploy now (skip the 5 min wait)
journalctl -u pantry-update -n 30      # deploy log
journalctl -u pantry -f                # app log
```

Reading the journal as `sdiehl` needs the `systemd-journal` group.

## Data backup (`scripts/backup_data.sh`)

Recipe data is edited through the web app on frank; the data repo is the backup.

```
git add -A; nothing staged -> done
commit "Backup from frank <date>: N file(s) changed" (body lists touched recipes)
fetch; local ahead -> rebase onto origin if it moved, then push
```

A failed push is retried on the next run (it pushes anything ahead of origin, not
just the new commit). A rebase conflict aborts and logs; resolve by hand on frank.
`auto_update.sh` keeps pulling the data repo with `--ff-only`, so edits pushed to
GitHub from elsewhere still reach frank.

```bash
sudo systemctl start pantry-backup     # back up now
journalctl -u pantry-backup -n 20
```

## HTTPS (Tailscale)

`scripts/setup_tailscale.sh` installs Tailscale, logs in, and runs
`tailscale serve --bg 5000`, which proxies `https://frank.<tailnet>.ts.net` to the app
with a real certificate. Requires MagicDNS and HTTPS Certificates enabled in the
Tailscale admin console. HTTPS is what makes the PWA, offline mode, microphone, and
push work (see [PWA.md](PWA.md)). Step-by-step phone setup: [PHONE_SETUP.md](PHONE_SETUP.md).

## Environment

All optional. Missing keys disable features; their routes return 503.

| Var | Enables / default |
|-----|-------------------|
| `GEMINI_API_KEY` | Import and chat |
| `GEMINI_MODEL`, `GEMINI_FALLBACK_MODELS` | Model choice, see [AI.md](AI.md#models-and-quota-recipe_coregeminipy) |
| `GMAIL_SENDER`, `GMAIL_APP_PASSWORD` | Email |
| `FLASK_SECRET_KEY` | Session signing. Installer generates one |
| `RECIPES_DATA_DIR` | Data repo path. Default `../diehl_recipes` (sibling of the app) |
| `RECIPES_HOST`, `RECIPES_PORT` | `0.0.0.0`, `5000` |
| `RECIPES_DEBUG` | `1` locally. Must be `0` on the server: debug runs a second process and exposes the Werkzeug debugger |

## Local development

```bash
uv sync
git clone git@github.com:bigdiehl/diehl_recipes.git ../diehl_recipes
set -a; . ./.env; set +a          # optional, .env is git-ignored
uv run web/app.py                 # http://localhost:5000
uv run pytest
```

Local runs use the local data repo and their own `web/instance/state.json`. With
Gmail keys loaded and the weekly plan enabled locally, the local app would send real
email; keep the plan off locally.

## CI

`.github/workflows/ci.yml`: Ubuntu, Pango for WeasyPrint, `uv sync --frozen`,
`uv run pytest`, on pushes to `master` and on pull requests.
