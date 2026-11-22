# Pantry

[![CI](https://github.com/bigdiehl/pantry/actions/workflows/ci.yml/badge.svg)](https://github.com/bigdiehl/pantry/actions/workflows/ci.yml)

Personal web app for managing recipes, generating shopping lists, and scheduling weekly meal planning emails.

## Setup

```bash
# Install dependencies; recipe data is a separate repo cloned alongside
uv sync
git clone git@github.com:bigdiehl/diehl_recipes.git ../diehl_recipes

# Run (all features work without env vars, some are disabled)
uv run web/app.py
# Access at http://localhost:5000
```

**Optional: Enable email and import features**

```bash
# For email features (shopping list emails, scheduling)
export GMAIL_SENDER="your@gmail.com"
export GMAIL_APP_PASSWORD="your-app-password"

# For recipe import from URLs
export GEMINI_API_KEY="your-key"
```

Tests: `uv run pytest`. CI runs them on every push.

Install as a service (systemd + auto-deploy timer + HTTPS for phone): `scripts/install_service.sh`, then `scripts/setup_tailscale.sh`.

Deployment details: `docs/DEPLOYMENT.md`.

## Features

- **Recipe Management:** Browse, edit, import recipes from URLs
- **Shopping Lists:** Auto-merge ingredients, sum quantities, email/download PDF
- **Scheduling:** Weekly automated shopping list emails
- **PWA:** Install on phone, works offline
- **Auto-deploy:** Server pulls, tests, and restarts on new commits

## Documentation

Developer documentation on the design lives in [`docs/`](docs/README.md). Tasks and notes: `working/`.

## Project Status

See `working/TODO.md` and `working/NOTES.md`.

## Tech Stack

Python 3.11+, Flask, Pint, Pydantic, Google GenAI, WeasyPrint, APScheduler

Package manager: uv

## License

Personal project
