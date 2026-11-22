# Setup

## Install

```bash
cd pantry
uv sync
git clone git@github.com:bigdiehl/diehl_recipes.git ../diehl_recipes
```

## Run

```bash
uv run web/app.py
# Access at http://localhost:5000
```

App runs without any environment variables. Features requiring external services are disabled by default.

## Optional: Enable Features

**Email Features** (shopping list emails, scheduling)

Requires Gmail account with app password:

```bash
export GMAIL_SENDER="your@gmail.com"
export GMAIL_APP_PASSWORD="your-app-password"
```

Get app password: https://myaccount.google.com/apppasswords (requires 2FA enabled)

**Recipe Import** (extract recipes from URLs via Gemini AI)

Requires Google Gemini API key:

```bash
export GEMINI_API_KEY="your-key"
```

Get API key: https://aistudio.google.com/app/apikey

**Optional Security**

```bash
export FLASK_SECRET_KEY="random-secret"  # Defaults to "dev-secret-change-me"
```

## Production (systemd)

```bash
scripts/install_service.sh          # deps, uv sync, /etc/pantry.env, pantry.service, pantry-update.timer
sudo nano /etc/pantry.env           # add GMAIL_* / GEMINI_API_KEY
sudo systemctl restart pantry
scripts/setup_tailscale.sh          # HTTPS URL for phone/PWA install
```

| Env var | Default | Purpose |
|---------|---------|---------|
| `RECIPES_PORT` | 5000 | Listen port |
| `RECIPES_HOST` | 0.0.0.0 | Listen address |
| `RECIPES_DEBUG` | 1 | Flask debugger/reloader. Installer sets 0 |
| `FLASK_SECRET_KEY` | dev value | Installer generates one |

Re-running the installer is safe. It migrates `/etc/recipes_app.env` and disables old units (`frank_web_server`, `web_app`, `recipes`). Remove with `scripts/uninstall_service.sh`.

## Auto-deploy

`pantry-update.timer` runs `scripts/auto_update.sh` every 5 min (`--update-interval` to change):

| Change | Action |
|--------|--------|
| New commit on app branch | Fast-forward, `uv sync`, `pytest`. Pass: restart. Fail: roll back, skip that commit |
| New commit in diehl_recipes | `pull --ff-only`, restart |
| Local edits block a fast-forward | Skip, log warning |

```bash
sudo systemctl start pantry-update     # deploy now
journalctl -u pantry-update -n 30      # deploy log
```

Recipe edits made in the web UI on the server are not committed back. Commit them in diehl_recipes on the server, or data pulls stop fast-forwarding.

## Troubleshooting

**Gemini model errors:**
```bash
uv run python scripts/list_gemini_models.py --recommended
```

**Check logs:**
```bash
journalctl -u pantry -f
```
