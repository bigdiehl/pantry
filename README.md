# Recipe Management App

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

Install as a service (systemd + HTTPS for phone): `scripts/install_service.sh`, then `scripts/setup_tailscale.sh`.

See `doc/SETUP.md` for detailed setup instructions.

## Features

- **Recipe Management:** Browse, edit, import recipes from URLs
- **Shopping Lists:** Auto-merge ingredients, sum quantities, email/download PDF
- **Scheduling:** Weekly automated shopping list emails
- **PWA:** Install on phone, works offline
- **Interactive List:** Demo of mobile shopping list with checkboxes

## Documentation

- `doc/ARCHITECTURE.md` - System design and data models
- `doc/SETUP.md` - Installation and configuration
- `doc/API.md` - Web routes and endpoints
- `doc/PWA.md` - Progressive web app setup
- `doc/REMOTE_ACCESS.md` - Options for remote access (Tailscale, Cloudflare, etc.)
- `doc/INTERACTIVE_SHOPPING_LIST.md` - Mobile shopping list demo
- `working/TODO.md` - Project TODOs
- `working/NOTES.md` - Development notes

## Project Status

See `working/TODO.md` and `working/NOTES.md`.

## Tech Stack

Python 3.11+, Flask, Pint, Pydantic, Google GenAI, WeasyPrint, APScheduler

Package manager: uv

## License

Personal project
