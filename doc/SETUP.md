# Setup

## Install

```bash
cd recipes
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
scripts/install_service.sh          # deps, uv sync, /etc/recipes_app.env, recipes.service
sudo nano /etc/recipes_app.env      # add GMAIL_* / GEMINI_API_KEY
sudo systemctl restart recipes
scripts/setup_tailscale.sh          # HTTPS URL for phone/PWA install
```

| Env var | Default | Purpose |
|---------|---------|---------|
| `RECIPES_PORT` | 5000 | Listen port |
| `RECIPES_HOST` | 0.0.0.0 | Listen address |
| `RECIPES_DEBUG` | 1 | Flask debugger/reloader. Installer sets 0 |
| `FLASK_SECRET_KEY` | dev value | Installer generates one |

Re-running the installer is safe. Remove with `scripts/uninstall_service.sh`.

## Troubleshooting

**Gemini model errors:**
```bash
uv run python scripts/list_gemini_models.py --recommended
```

**Check logs:**
```bash
journalctl -u recipes -f
```
