# Recipe Management App

Personal web app for managing recipes, generating shopping lists, and scheduling weekly meal planning emails.

## Setup

```bash
# Install dependencies
uv sync

# Set environment variables
export GMAIL_SENDER="your@gmail.com"
export GMAIL_APP_PASSWORD="your-app-password"
export GEMINI_API_KEY="your-key"

# Run
uv run web/app.py
# Access at http://localhost:5000
```

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

**Working:**
- Recipe browsing and selection
- Shopping list generation and merging
- PDF export and email
- Weekly scheduling
- Recipe editor (YAML + markdown)
- Gemini-based recipe import
- Basic PWA (offline browsing)

**In Progress:**
- PWA testing on mobile
- Remote access setup (Tailscale/Cloudflare)
- Interactive shopping list integration
- Import verification with retry

**Known Issues:**
- Some recipes need fixing (see working/NOTES.md)
- Import needs validation step
- Shopping list demo not integrated with real data

## Tech Stack

Python 3.11+, Flask, Pint, Pydantic, Google GenAI, WeasyPrint, APScheduler

Package manager: uv

## License

Personal project
