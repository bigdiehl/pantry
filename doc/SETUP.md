# Setup

## Install

```bash
cd /home/sdiehl/personal/recipes
uv sync
```

## Environment Variables

```bash
# Email (shopping lists)
export GMAIL_SENDER="your@gmail.com"
export GMAIL_APP_PASSWORD="your-app-password"  # https://myaccount.google.com/apppasswords

# Recipe import
export GEMINI_API_KEY="your-key"  # https://aistudio.google.com/app/apikey

# Optional
export FLASK_SECRET_KEY="random-secret"
```

## Run

```bash
uv run web/app.py
# Access at http://localhost:5000
```

## Production (systemd)

```bash
sudo cp web_app.service /etc/systemd/system/
sudo systemctl enable web_app
sudo systemctl start web_app
```

## Troubleshooting

**Gemini model errors:**
```bash
uv run python scripts/list_gemini_models.py --recommended
```

**Check logs:**
```bash
journalctl -u web_app -f
```
